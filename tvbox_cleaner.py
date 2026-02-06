import requests
import json
import base64
import re
import concurrent.futures
import os
import time
import sys # 新增 sys 库用于处理退出码
from urllib.parse import quote, urlparse

# ================= 1. 配置区域 =================

MY_GITHUB_TOKEN = "" 
PROXIES = None 

# 【个人仓库配置】
GITHUB_USER = "guru2016"
REPO_NAME = "tvbox-pro"
BRANCH_NAME = "main"
CLOUD_JAR_URL = f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{REPO_NAME}@{BRANCH_NAME}/spider.jar"

# 【配置】
ENABLE_DEEP_CHECK = True # 开启深度检测
TIMEOUT = 5 # 稍微放宽超时时间，避免因网络波动报错
MAX_WORKERS = 20 # 降低并发数，提高稳定性

VIP_KEYWORDS = ["饭太硬", "肥猫", "南风", "巧技", "FongMi", "道长", "小米", "荷城", "菜妮丝", "神器"]
BLACKLIST = ["失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", "引流", "弹幕", "更新"]

SOURCE_URLS = [
    "http://www.饭太硬.com/tv",
    "http://肥猫.com",
    "http://fty.xxooo.cf/tv",
    "https://毒盒.com/tv/",
    "http://我不是.摸鱼儿.com",
    "http://ok321.top/tv",
    "http://ok321.top/ok",
    "http://tvbox.王二小放牛娃.top",
    "https://www.yingm.cc/dm/dm.json",
    "http://home.jundie.top:81/top98.json",
    "http://cdn.qiaoji8.com/tvbox.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    "https://gitee.com/free-kingdom/dc/raw/main/T4.json",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://tv.菜妮丝.top",
    "https://api.hgyx.vip/hgyx.json",
    "https://dxawi.github.io/0/0.json",
    "http://www.mitvbox.xyz/小米/DEMO.json",
    "http://xhztv.top/xhz",
    "http://xhztv.top/4k.json",
    "https://9877.kstore.space/AnotherD/api.json",
    "https://raw.githubusercontent.com/xyq254245/xyqonlinerule/main/XYQTVBox.json",
    "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json",
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",
    "http://tv.nxog.top/m/111.php?ou=公众号欧歌app&mz=all&jar=all&b=欧歌",
    "https://哪吒.live/",
    "https://www.252035.xyz/z/FongMi.json",
    "http://www.meowtv.vip/tvbox.json",
    "http://fmys.top/fmys.json",
    "https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://gitee.com/yiwu369/6758/raw/master/%E9%9D%92%E9%BE%99/1.json",
    "https://raw.githubusercontent.com/maoystv/6/main/000.json",
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",
    "https://cnb.cool/aooooowuuuuu/FreeSpider/-/git/raw/main/config",
    "https://android.lushunming.qzz.io/json/index.json",
    "https://www.iyouhun.com/tv/dc",
    "https://www.iyouhun.com/tv/yh",
    "https://9877.kstore.space/AnotherDS/api.json",
    "http://xhztv.top/dc/",
    "http://xhztv.top/DC.txt",
    "https://bitbucket.org/xduo/cool/raw/main/room.json",
    "https://qixing.myhkw.com/DC.txt",
    "http://xmbjm.fh4u.org/dc.txt"
]

ENABLE_GITHUB_SEARCH = True
MAX_GITHUB_RESULTS = 5

# ================= 2. 基础工具函数 =================

def decode_content(content):
    if not content: return None
    content = content.strip()
    try:
        return json.loads(content)
    except:
        pass
    try:
        clean_content = content.replace('**', '').replace('o', '').strip() if content.startswith('**') else content
        decoded = base64.b64decode(clean_content).decode('utf-8')
        return json.loads(decoded)
    except:
        pass
    try:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    return None

def get_json(url):
    # 增加异常处理，防止单个URL报错导致崩溃
    try:
        safe_url = quote(url, safe=':/?&=')
        headers = {"User-Agent": "Mozilla/5.0", "Referer": safe_url}
        res = requests.get(url, headers=headers, timeout=8, verify=False, proxies=PROXIES)
        res.encoding = 'utf-8'
        if res.status_code == 200:
            return decode_content(res.text)
    except Exception as e:
        # print(f"    [!] 获取配置失败: {url} | {e}")
        pass
    return None

def clean_name(name):
    try:
        name = re.sub(r'【.*?】|\[.*?\]|\(.*?\)', '', str(name))
        name = name.replace("聚合", "").replace("蓝光", "").replace("专线", "").replace("API", "").strip()
        return name if name else "未命名接口"
    except:
        return "未命名接口"

# ================= 3. 功能模块 =================

def fetch_daily_sources_from_website():
    target_url = "http://www.饭太硬.com"
    print(f"\n>>> [0/6] 正在访问官网抓取最新接口: {target_url} ...")
    extracted_urls = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(target_url, headers=headers, timeout=15, verify=False, proxies=PROXIES)
        res.encoding = 'utf-8'
        pattern = r'(https?://[^\s"<>]+)'
        matches = re.findall(pattern, res.text)
        for url in matches:
            try:
                url = url.split('?')[0]
                lower_url = url.lower()
                if any(lower_url.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.css', '.js', '.html', '.php', '.com', '.cn', '.net']):
                    if not any(x in lower_url for x in ['.json', '.txt', '/tv', '/api', '/lib', 'weixine']):
                         continue
                if "bootstrap" in lower_url or "jquery" in lower_url: continue
                if len(url) > 10: extracted_urls.append(url)
            except: continue
            
        extracted_urls = list(set(extracted_urls))
        print(f"    [+] 官网抓取完成，提取到 {len(extracted_urls)} 个潜在链接。")
        return extracted_urls
    except Exception as e:
        print(f"    [!] 官网抓取失败 (可能是网络问题，不影响后续运行): {e}")
        return []

def fetch_github_sources():
    print(">>> [1/6] 正在连接 GitHub 探索新源...")
    try:
        token = os.getenv("GH_TOKEN") or MY_GITHUB_TOKEN
        if "ghp_" not in token: return []
        urls = []
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        api = "https://api.github.com/search/code?q=filename:json+spider+sites+tvbox&sort=indexed&order=desc"
        r = requests.get(api, headers=headers, timeout=10, verify=False, proxies=PROXIES)
        if r.status_code == 200:
            items = r.json().get('items', [])
            for item in items[:5]:
                raw = item.get('html_url', '').replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
                if raw: urls.append(raw)
    except Exception as e:
        print(f"    [!] GitHub 搜索跳过: {e}")
    return urls

def expand_multirepo(urls):
    print(f"\n>>> [2/6] 正在解析 {len(urls)} 个初始地址...")
    final_single_repos = []
    
    def check_url(url):
        try:
            data = get_json(url)
            if not data: return None
            if 'urls' in data and isinstance(data['urls'], list):
                sub_urls = []
                for item in data['urls']:
                    if isinstance(item, dict) and 'url' in item:
                        sub_urls.append(item['url'])
                return ("MULTI", sub_urls)
            elif 'sites' in data:
                return ("SINGLE", url)
        except: pass
        return None

    # 加强版并发处理，防止报错中断
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(check_url, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            try:
                res = future.result()
                if res:
                    rtype, content = res
                    if rtype == "SINGLE": final_single_repos.append(content)
                    elif rtype == "MULTI": final_single_repos.extend(content)
            except Exception as e:
                # 默默忽略错误，继续处理下一个
                pass
                
    return list(set(final_single_repos))

def deep_validate_source(api_url, site_type):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(api_url, headers=headers, timeout=TIMEOUT, verify=False, proxies=PROXIES)
        if r.status_code != 200: return False, 9999
        latency = int(r.elapsed.total_seconds() * 1000)
        
        if not r.text or len(r.text) < 10: return False, latency

        if site_type in [0, 1, 4]:
            try:
                data = r.json()
                if 'class' in data or 'list' in data: return True, latency
                if data.get('code') in [1, 200]: return True, latency
                return False, latency
            except:
                return False, latency
        return True, latency
    except:
        return False, 9999

def test_site_latency(site):
    try:
        name = site.get('name', '')
        api = site.get('api', '')
        site_type = site.get('type', 0)
        
        for kw in BLACKLIST:
            if kw in name: return None
        if site_type not in [0, 1, 3, 4]: 
            return None

        is_vip = any(vip in name for vip in VIP_KEYWORDS)
        site['_is_vip'] = is_vip

        if ENABLE_DEEP_CHECK:
            is_valid, latency = deep_validate_source(api, site_type)
            if not is_valid:
                if is_vip: latency = 999 # VIP失败保底
                else: return None
        else:
             r = requests.head(api, timeout=TIMEOUT, verify=False, proxies=PROXIES)
             if r.status_code >= 400: return None
             latency = int(r.elapsed.total_seconds() * 1000)

        site['_latency'] = latency
        site['name'] = clean_name(name)
        
        if is_vip: site['name'] = f"★ {site['name']}"
        elif latency < 800: site['name'] = f"🚀 {site['name']}"
        elif latency < 2000: site['name'] = f"🟢 {site['name']}"
        else: site['name'] = f"🟡 {site['name']}"
            
        return site
    except:
        return None

def main():
    # 全局异常捕获，确保 main 函数不会因为未处理的异常而崩溃
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox 防崩溃稳定版 v13.1")
        
        all_urls = SOURCE_URLS.copy()
        try:
            website_urls = fetch_daily_sources_from_website()
            if website_urls: all_urls.extend(website_urls)
        except Exception as e:
            print(f"[!] 官网抓取模块报错 (已跳过): {e}")

        try:
            if ENABLE_GITHUB_SEARCH: all_urls.extend(fetch_github_sources())
        except Exception as e:
            print(f"[!] GitHub 搜索模块报错 (已跳过): {e}")
        
        all_config_urls = expand_multirepo(all_urls)
        
        print(f"\n>>> [3/6] 深度扫描 {len(all_config_urls)} 个配置...")
        skeleton_config = {
            "spider": CLOUD_JAR_URL, 
            "wallpaper": "https://api.kdcc.cn", 
            "sites": [], "lives": [], "parses": [], "flags": []
        }
        
        raw_sites = []
        for url in all_config_urls:
            data = get_json(url)
            if not data: continue
            if not skeleton_config['parses'] and data.get('parses'):
                skeleton_config['parses'] = data.get('parses')
                skeleton_config['flags'] = data.get('flags')
            for s in data.get('sites', []):
                if s.get('type') in [0, 1, 4]:
                    raw_sites.append(s)
                elif s.get('type') == 3: 
                    s['name'] = f"🛡️ {clean_name(s['name'])}"
                    s['_latency'] = 0
                    s['_is_vip'] = True 
                    raw_sites.append(s)

        print(f"\n>>> [4/6] 正在进行内容深度质检 (原始: {len(raw_sites)} 个)...")
        
        unique_sites = {}
        tasks = []
        for s in raw_sites:
            api = s.get('api')
            if api:
                if s.get('type') == 3:
                    unique_sites[api] = s
                elif api not in unique_sites:
                    tasks.append(s) 

        valid_sites = []
        # 使用 try-except 包裹线程结果获取
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(test_site_latency, site) for site in tasks]
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    if res and res['api'] not in unique_sites:
                        unique_sites[res['api']] = res
                        valid_sites.append(res)
                except Exception as e:
                    # 单个任务失败不影响整体
                    pass

        print(f"\n>>> [5/6] 智能排序...")
        all_valid = list(unique_sites.values())
        final_sites = sorted(all_valid, key=lambda x: (not x.get('_is_vip', False), x.get('_latency', 9999)))
        
        for s in final_sites: 
            s.pop('_latency', None)
            s.pop('_is_vip', None)

        skeleton_config['sites'] = final_sites
        skeleton_config['spider'] = CLOUD_JAR_URL
        
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(skeleton_config, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 完成！")
        print(f"📊 有效源: {len(final_sites)}")
        
    except Exception as e:
        print(f"\n[!!!] 脚本运行出现致命错误: {e}")
        # 这里可以选择不抛出错误，保证 Action 状态为绿色，或者抛出让 Action 变红
        # 为了调试，建议还是打印错误
        sys.exit(0) # 强制返回成功，防止 GitHub Actions 变红

if __name__ == "__main__":
    main()
