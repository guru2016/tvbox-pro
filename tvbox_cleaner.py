import requests
import json
import re
import concurrent.futures
import os
import sys
from urllib.parse import quote, urljoin

# ================= 1. 配置区域 =================

MY_GITHUB_TOKEN = "" 
PROXIES = None 

# 【核心配置】
GITHUB_USER = "guru2016"
REPO_NAME = "tvbox-pro"
BRANCH_NAME = "main"

# 【全局唯一 Jar：饭太硬内核】
# 请确保 GitHub 仓库里有 spider.jar (必须是饭太硬的版本)
GLOBAL_SAFE_JAR = f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{REPO_NAME}@{BRANCH_NAME}/spider.jar"

# 【搜刮列表】(包含核心 + 优质大厂)
EXTERNAL_URLS = [
    # --- 核心宿主 ---
    "http://www.饭太硬.com/tv",
    "http://肥猫.com",
    "http://fty.xxooo.cf/tv",
    
    # --- 优质大厂 ---
    "http://rihou.cc:88/荷城茶秀",
    "https://api.hgyx.vip/hgyx.json",
    "https://tv.菜妮丝.top",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://www.252035.xyz/z/FongMi.json",
    "http://52bsj.vip:81/api/v3/file/get/29899/bsj2023.json?sign=3c594b2b985b365bad",
    
    # --- 散户池 ---
    "http://ok321.top/tv",
    "http://tvbox.王二小放牛娃.top",
    "https://android.lushunming.qzz.io/json/index.json",
    "http://home.jundie.top:81/top98.json",
    "https://s2.pub/x",
    "http://tv.nxog.top/m/111.php?ou=公众号欧歌app&mz=all&jar=all&b=欧歌",
    "https://100km.top/0",
    "http://meowtv.cn/tv",
    "http://cdn.qiaoji8.com/tvbox.json" 
]

# 【过滤配置】
ALLOWED_TYPES = [0, 1, 3, 4] 
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "弹幕", "更新", "公众号", "扫码", "微信", "企鹅", "APP", "下载", 
    "推广", "验证", "激活", "授权", "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播",
    "77.110", "mingming"
]

# 【连通性配置】
TIMEOUT = 5        # 超时时间更短，快速过
MAX_WORKERS = 50   # 高并发验活

# ================= 2. 工具函数 =================

def decode_content(content):
    if not content: return None
    try: return json.loads(content)
    except: pass
    try:
        clean = content.replace('**', '').replace('o', '').strip()
        return json.loads(base64.b64decode(clean).decode('utf-8'))
    except:
        try:
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match: return json.loads(match.group())
        except: pass
    return None

def get_json(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False, proxies=PROXIES)
        res.encoding = 'utf-8'
        if res.status_code == 200:
            return decode_content(res.text)
    except: pass
    return None

def clean_name(name):
    name = str(name)
    name = re.sub(r'【.*?】|\[.*?\]|\(.*?\)|（.*?）', '', name)
    name = name.replace("聚合", "").replace("蓝光", "").replace("专线", "").strip()
    return name

# ================= 3. 核心：强制剥离 Jar =================

def process_and_strip_jar(url):
    """抓取并剥离所有接口的 jar 字段"""
    data = get_json(url)
    if not data: return []
    
    extracted_sites = []
    
    def process_site(site):
        # 强制删掉 jar，防止闪退
        if 'jar' in site:
            del site['jar']
        return site

    if 'urls' in data and isinstance(data['urls'], list):
        for item in data['urls']:
            if 'url' in item:
                sub_data = get_json(item['url'])
                if sub_data and 'sites' in sub_data:
                    for s in sub_data['sites']:
                        extracted_sites.append(process_site(s))
    
    if 'sites' in data:
        for s in data['sites']:
            extracted_sites.append(process_site(s))
            
    return extracted_sites

# ================= 4. 流程函数 =================

def fetch_all_sites_stripped():
    print(f">>> [1/4] 极速搜刮 & 剥离Jar...")
    all_sites = []
    unique_urls = list(set(EXTERNAL_URLS))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(process_and_strip_jar, url): url for url in unique_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            try:
                sites = future.result()
                if sites: all_sites.extend(sites)
            except: pass
            
    print(f"    [+] 原始接口数量: {len(all_sites)}")
    return all_sites

def check_connectivity(sites):
    print(f">>> [2/4] 连通性验活 (Ping Mode)...")
    valid_sites = []
    seen_api = set()
    tasks = []
    
    for s in sites:
        name = s.get('name', '')
        api = s.get('api', '')
        stype = s.get('type', 0)
        
        if stype not in ALLOWED_TYPES: continue
        if any(bw in name for bw in BLACKLIST): continue
        if api in seen_api: continue
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): continue

        seen_api.add(api)
        tasks.append(s)

    def ping(site):
        try:
            # 核心优化：只请求 Headers 或者极少量内容，不测速，只看通不通
            # stream=True 配合 chunk读取，只要有数据流回来就算成功
            with requests.get(site['api'], timeout=TIMEOUT, stream=True, verify=False, proxies=PROXIES) as res:
                if res.status_code == 200:
                    site['name'] = clean_name(site['name'])
                    # 统一开启搜索
                    site['searchable'] = 1 
                    site['quickSearch'] = 1
                    
                    # 图标逻辑
                    if site.get('type') == 3:
                        site['name'] = f"🛡️ {site['name']}" # 饭太硬内核 Spider
                    else:
                        site['name'] = f"🚀 {site['name']}" # CMS/App
                        
                    return site
        except: pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(ping, s) for s in tasks]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_sites.append(res)
            
    # 不再按照 latency 排序，因为我们没测速。
    # 这里的顺序基本上是 随机/先连上先得，保证了多样性。
    print(f"    [√] 存活接口: {len(valid_sites)} 个")
    return valid_sites

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox 极速验活版 v27.0")
        
        # 1. 抓取
        raw_sites = fetch_all_sites_stripped()
        
        # 2. 验活
        final_sites = check_connectivity(raw_sites)
        
        # 3. 截断 (保留200个，足够用了)
        max_sites = 200
        if len(final_sites) > max_sites:
            final_sites = final_sites[:max_sites]
        
        # 4. 生成
        config = {
            "spider": GLOBAL_SAFE_JAR,
            "wallpaper": "https://api.kdcc.cn",
            "sites": final_sites,
            "lives": [],
            "parses": [],
            "flags": []
        }
        
        print(f">>> [3/4] 保存配置...")
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 完成！")
        print(f"📊 有效源: {len(final_sites)} 个")
        print(f"🛡️ 全局核心: {GLOBAL_SAFE_JAR}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":"", "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
