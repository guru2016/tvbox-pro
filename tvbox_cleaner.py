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

# 【核心修改】
# 既然已经把 spider.jar 上传到了仓库，我们就直接用 jsDelivr 加速引用它！
# 请把下面的 "guru2016" 换成你的 GitHub 用户名 (如果不是这个的话)
# 这样电视加载时，走的是全球 CDN，速度极快且稳定。
GITHUB_USER = "guru2016"
REPO_NAME = "tvbox-pro"
BRANCH_NAME = "main"

# 拼接出你自己的 Jar 包 CDN 地址
CLOUD_JAR_URL = f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{REPO_NAME}@{BRANCH_NAME}/spider.jar"

SOURCE_URLS = [
    # --- 单仓 ---
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
    
    # --- 多仓 ---
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
TIMEOUT = 4
BLACKLIST = ["失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色"]

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
        res = requests.get(url, headers=headers, timeout=6, verify=False, proxies=PROXIES)
        res.encoding = 'utf-8'
        if res.status_code == 200:
            return decode_content(res.text)
    except:
        pass
    return None

def fetch_github_sources():
    print(">>> [1/5] 正在连接 GitHub 探索新源...")
    token = os.getenv("GH_TOKEN") or MY_GITHUB_TOKEN
    if "ghp_" not in token:
        return []
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

def clean_name(name):
    name = re.sub(r'【.*?】|\[.*?\]|\(.*?\)', '', name)
    name = name.replace("聚合", "").replace("蓝光", "").replace("专线", "").replace("API", "").strip()
    return name if name else "未命名接口"

def expand_multirepo(urls):
    print(f"\n>>> [2/5] 正在解析 {len(urls)} 个初始地址...")
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
            if latency < 800: site['name'] = f"🚀 {site['name']}"
            elif latency < 1500: site['name'] = f"🟢 {site['name']}"
            else: site['name'] = f"🟡 {site['name']}"
            return site
    except:
        pass
    return None

def main():
    requests.packages.urllib3.disable_warnings()
    print(">>> 启动 TVBox 终极独立版 v10.0")
    
    # 验证 Jar 链接是否配置正确
    if "guru2016" not in CLOUD_JAR_URL:
        print(f"[!] 警告: 当前 Jar 指向 {CLOUD_JAR_URL}")
        print("[!] 请确保你已经上传了 spider.jar 到你的仓库！")

    initial_urls = SOURCE_URLS.copy()
    if ENABLE_GITHUB_SEARCH:
        initial_urls.extend(fetch_github_sources())
    all_config_urls = expand_multirepo(initial_urls)
    
    print(f"\n>>> [3/5] 深度扫描 {len(all_config_urls)} 个配置...")
    
    skeleton_config = {
        "spider": CLOUD_JAR_URL, 
        "wallpaper": "https://api.kdcc.cn", 
        "sites": [],
        "lives": [],
        "parses": [],
        "flags": []
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
                s['name'] = f"★ {clean_name(s['name'])}"
                s['_latency'] = 0
                raw_sites.append(s)

    print(f"\n>>> [4/5] 竞速清洗 (接口: {len(raw_sites)} 个)...")
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

    print(f"\n>>> [5/5] 生成最终列表...")
    vip_sites = [s for s in unique_sites.values() if s.get('_latency') == 0]
    common_sites = sorted(valid_sites, key=lambda x: x['_latency'])
    final_sites = vip_sites + common_sites
    for s in final_sites: s.pop('_latency', None)

    skeleton_config['sites'] = final_sites
    # 强制覆盖 spider 为你自己的
    skeleton_config['spider'] = CLOUD_JAR_URL
    
    with open("my_tvbox.json", 'w', encoding='utf-8') as f:
        json.dump(skeleton_config, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！Jar 已指向你自己仓库: {CLOUD_JAR_URL}")
    print(f"📊 有效源: {len(final_sites)}")

if __name__ == "__main__":
    main()
