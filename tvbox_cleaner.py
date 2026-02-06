import requests
import json
import base64
import re
import concurrent.futures
import os
import time
from urllib.parse import quote, urlparse

# ================= 1. 配置区域 =================

MY_GITHUB_TOKEN = "" 
PROXIES = None 

# 【个人仓库配置】
GITHUB_USER = "guru2016"
REPO_NAME = "tvbox-pro"
BRANCH_NAME = "main"
CLOUD_JAR_URL = f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{REPO_NAME}@{BRANCH_NAME}/spider.jar"

# 【权重配置 - 核心修改】
# 1. VIP 关键词：包含这些词的源，无视速度，强制排在最前面
VIP_KEYWORDS = ["饭太硬", "肥猫", "南风", "巧技", "FongMi", "道长", "小米", "荷城", "菜妮丝", "神器"]

# 2. 黑名单：包含这些词的直接丢弃
BLACKLIST = ["失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", "引流", "弹幕", "更新"]

# 3. 严格模式：超时时间缩短为 3 秒，超过 3 秒的源直接不要
TIMEOUT = 3

# 【基础源列表】
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
    safe_url = quote(url, safe=':/?&=')
    headers = {"User-Agent": "Mozilla/5.0", "Referer": safe_url}
    try:
        res = requests.get(url, headers=headers, timeout=5, verify=False, proxies=PROXIES)
        res.encoding = 'utf-8'
        if res.status_code == 200:
            return decode_content(res.text)
    except:
        pass
    return None

def clean_name(name):
    name = re.sub(r'【.*?】|\[.*?\]|\(.*?\)', '', name)
    name = name.replace("聚合", "").replace("蓝光", "").replace("专线", "").replace("API", "").strip()
    return name if name else "未命名接口"

# ================= 3. 功能模块 =================

def fetch_daily_sources_from_website():
    target_url = "http://www.饭太硬.com"
    print(f"\n>>> [0/6] 正在访问官网抓取最新接口: {target_url} ...")
    extracted_urls = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(target_url, headers=headers, timeout=10, verify=False, proxies=PROXIES)
        res.encoding = 'utf-8'
        pattern = r'(https?://[^\s"<>]+)'
        matches = re.findall(pattern, res.text)
        for url in matches:
            url = url.split('?')[0]
            lower_url = url.lower()
            if any(lower_url.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.css', '.js', '.html', '.php', '.com', '.cn', '.net']):
                if not any(x in lower_url for x in ['.json', '.txt', '/tv', '/api', '/lib', 'weixine']):
                     continue
            if "bootstrap" in lower_url or "jquery" in lower_url: continue
            if len(url) > 10: extracted_urls.append(url)
        extracted_urls = list(set(extracted_urls))
        print(f"    [+] 官网抓取完成，提取到 {len(extracted_urls)} 个潜在链接。")
        return extracted_urls
    except Exception as e:
        print(f"    [!] 官网抓取失败: {e}")
        return []

def fetch_github_sources():
    print(">>> [1/6] 正在连接 GitHub 探索新源...")
    token = os.getenv("GH_TOKEN") or MY_GITHUB_TOKEN
    if "ghp_" not in token: return []
    urls = []
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    api = "https://api.github.com/search/code?q=filename:json+spider+sites+tvbox&sort=indexed&order=desc"
    try:
        r = requests.get(api, headers=headers, timeout=10, verify=False, proxies=PROXIES)
        if r.status_code == 200:
            items = r.json().get('items', [])
            for item in items[:MAX_GITHUB_RESULTS]:
                raw = item.get('html_url', '').replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
                if raw: urls.append(raw)
    except: pass
    return urls

def expand_multirepo(urls):
    print(f"\n>>> [2/6] 正在解析 {len(urls)} 个初始地址...")
    final_single_repos = []
    def check_url(url):
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
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(check_url, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            res = future.result()
            if res:
                rtype, content = res
                if rtype == "SINGLE": final_single_repos.append(content)
                elif rtype == "MULTI": final_single_repos.extend(content)
    return list(set(final_single_repos))

def test_site_latency(site):
    name = site.get('name', '')
    api = site.get('api', '')
    for kw in BLACKLIST:
        if kw in name: return None
    if site.get('type') not in [0, 1, 4]:
        return None
    headers = {"User-Agent": "Mozilla/5.0"}
    start_time = time.time()
    try:
        r = requests.get(api, headers=headers, timeout=TIMEOUT, stream=True, verify=False, proxies=PROXIES)
        if r.status_code < 400:
            latency = (time.time() - start_time) * 1000
            site['_latency'] = int(latency)
            site['name'] = clean_name(name)
            
            # 判断是否是 VIP
            is_vip = any(vip in site['name'] for vip in VIP_KEYWORDS)
            site['_is_vip'] = is_vip
            
            if is_vip:
                site['name'] = f"★ {site['name']}" # 给VIP加星标
            elif latency < 800:
                site['name'] = f"🚀 {site['name']}"
            else:
                site['name'] = f"🟢 {site['name']}"
            return site
    except:
        pass
    return None

def main():
    requests.packages.urllib3.disable_warnings()
    print(">>> 启动 TVBox 智能权重版 v12.0")
    
    # 1. 抓取与合并
    all_urls = SOURCE_URLS.copy()
    website_urls = fetch_daily_sources_from_website()
    if website_urls: all_urls.extend(website_urls)
    if ENABLE_GITHUB_SEARCH: all_urls.extend(fetch_github_sources())
    
    # 2. 展开多仓
    all_config_urls = expand_multirepo(all_urls)
    
    # 3. 提取接口
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
            elif s.get('type') == 3: # 收集别人的 Spider
                s['name'] = f"🛡️ {clean_name(s['name'])}"
                s['_latency'] = 0
                s['_is_vip'] = True # Spider 接口默认 VIP
                raw_sites.append(s)

    # 4. 竞速与权重计算
    print(f"\n>>> [4/6] 竞速与权重分级 (原始: {len(raw_sites)} 个)...")
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(test_site_latency, site) for site in tasks]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res and res['api'] not in unique_sites:
                unique_sites[res['api']] = res
                valid_sites.append(res)

    # 5. 智能排序
    print(f"\n>>> [5/6] 智能排序 (VIP优先 > 速度优先)...")
    
    # 获取所有有效接口
    all_valid = list(unique_sites.values())
    
    # 排序逻辑：
    # 第一优先级：是否是 VIP (True 排在 False 前面) -> Python sort 是 False(0) 在前，所以要用 `not x['_is_vip']`
    # 第二优先级：延迟 (低延迟在前)
    final_sites = sorted(all_valid, key=lambda x: (not x.get('_is_vip', False), x.get('_latency', 9999)))
    
    # 清理临时字段
    for s in final_sites: 
        s.pop('_latency', None)
        s.pop('_is_vip', None)

    skeleton_config['sites'] = final_sites
    skeleton_config['spider'] = CLOUD_JAR_URL
    
    with open("my_tvbox.json", 'w', encoding='utf-8') as f:
        json.dump(skeleton_config, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！")
    print(f"📊 最终有效源: {len(final_sites)}")
    print(f"🌟 其中 VIP/Spider 源: {len([s for s in final_sites if '★' in s['name'] or '🛡️' in s['name']])} 个")

if __name__ == "__main__":
    main()
