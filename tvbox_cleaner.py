import requests
import json
import re
import concurrent.futures
import os
import sys
import base64
from urllib.parse import quote, urljoin

# ================= 1. 配置区域 =================

# 【全局唯一 Jar：用户指定 GitHub 直连】
GLOBAL_SAFE_JAR = "https://github.com/guru2016/tvbox-pro/raw/refs/heads/main/custom_spider.jar"

# 【壁纸】
WALLPAPER_URL = "https://api.kdcc.cn"

# 【底板来源：饭太硬官方配置】
BASE_CONFIG_URL = "https://raw.githubusercontent.com/fantaite/TVBox/main/tvbox.json"

# 【追加搜刮列表（优化，高德、菜妮丝、大厂源优先）】
ADDITIONAL_URLS = [
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",      # 南风
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",          # 宝盒
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",       # 动力
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",             # 道长镜像
    "https://raw.githubusercontent.com/gaode-tvbox/TVBox/main/index.json",  # 高德源
    "https://api.hgyx.vip/hgyx.json",                                       # HGYX VIP
    "https://tv.菜妮丝.top",                                               # 菜妮丝
    "https://raw.githubusercontent.com/fantaite/TVBox/main/XC.json"         # 饭太硬附加源
]

# 【过滤配置】
ALLOWED_TYPES = [0, 1, 3, 4] 

# 【通用黑名单】(去广告)
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "更新", "扫码", "微信", "企鹅", "APP", "下载", "推广", "验证", "激活", "授权", 
    "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播", "77.110", "mingming", "摸鱼"
]

# 【绞杀名单】(只要出现这些字，立刻删除)
KILL_KEYWORDS = [
    "盘", "搜", "alist", "drive", "ali", "quark", "uc", "115", "1359527"
]

TIMEOUT = 20       
MAX_WORKERS = 40   

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
        res = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False)
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

# ================= 3. 核心处理逻辑 =================

def process_site(site):
    if 'jar' in site:
        del site['jar']
        
    name = str(site.get('name', ''))
    api = str(site.get('api', ''))
    key = str(site.get('key', ''))
    
    name_lower = name.lower()
    api_lower = api.lower()
    key_lower = key.lower()
    
    for kw in KILL_KEYWORDS:
        kw_lower = kw.lower()
        if kw_lower in name_lower: return None
        if kw_lower in api_lower: return None
        if kw_lower in key_lower: return None

    if any(bw in name for bw in BLACKLIST): return None
    
    site['name'] = clean_name(name)
    site['searchable'] = 1 
    site['quickSearch'] = 1
    
    if site.get('type') == 3:
        site['name'] = f"🛡️ {site['name']}" 
    else:
        site['name'] = f"🚀 {site['name']}" 
        
    return site

def fetch_sites_from_url(url):
    print(f"    -> 抓取扩展源: {url}")
    try:
        data = get_json(url)
        if not data: return []
        
        extracted = []
        
        if 'urls' in data and isinstance(data['urls'], list):
            for item in data['urls']:
                if 'url' in item:
                    sub = get_json(item['url'])
                    if sub and 'sites' in sub:
                        for s in sub['sites']:
                            p = process_site(s)
                            if p: extracted.append(p)
        
        if 'sites' in data:
            for s in data['sites']:
                p = process_site(s)
                if p: extracted.append(p)
                
        return extracted
    except Exception as e:
        print(f"⚠️ 抓取失败: {url} -> {e}")
        return []

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox (饭太硬底板+去盘去搜去Alist+GitHub直连)")
        
        print(f">>> [1/3] 下载饭太硬底板配置...")
        base_config = get_json(BASE_CONFIG_URL)
        if not base_config:
            base_config = {"spider": "", "sites": [], "parses": [], "flags": [], "rules": []}
            
        base_config['spider'] = GLOBAL_SAFE_JAR
        base_config['wallpaper'] = WALLPAPER_URL 
        base_config['drives'] = []
        
        print(">>> [2/3] 清洗底板接口 (剔除盘/搜/Alist)...")
        clean_base_sites = []
        if 'sites' in base_config:
            for s in base_config['sites']:
                processed = process_site(s)
                if processed:
                    clean_base_sites.append(processed)
        
        print(f">>> [3/3] 融合其他大厂源...")
        additional_sites = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(fetch_sites_from_url, url): url for url in ADDITIONAL_URLS}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    sites = future.result()
                    if sites: additional_sites.extend(sites)
                except Exception as e:
                    print(f"⚠️ 追加源抓取失败: {url} -> {e}")
        
        all_sites = clean_base_sites + additional_sites
        unique_sites = []
        seen_api = set()
        
        for s in all_sites:
            api = s.get('api', '')
            if api and api not in seen_api:
                unique_sites.append(s)
                seen_api.add(api)
        
        if len(unique_sites) > 300:
            unique_sites = unique_sites[:300]
            
        base_config['sites'] = unique_sites
        
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(base_config, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 完成！")
        print(f"📊 最终接口: {len(unique_sites)} 个")
        print(f"🚫 已拦截关键词: 盘、搜、Alist、Drive、Ali、Quark")
        print(f"🛡️ 核心 Jar: {GLOBAL_SAFE_JAR}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":GLOBAL_SAFE_JAR, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()