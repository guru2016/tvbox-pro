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

# 【底板来源：饭太硬官方配置 (使用镜像站防墙)】
# 我们将以这个文件的结构作为绝对基础
BASE_CONFIG_URL = "http://fty.xxooo.cf/tv"
BASE_CONFIG_URL_BACKUP = "http://www.饭太硬.com/tv"

# 【追加搜刮列表】(在饭太硬的基础上，补充这些源)
ADDITIONAL_URLS = [
    "http://肥猫.com",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",      # 南风
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",          # 宝盒
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",       # 动力
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",              # 道长镜像
    "https://api.hgyx.vip/hgyx.json",
    "https://tv.菜妮丝.top",
    "http://ok321.top/tv",
    "http://tv.nxog.top/m/111.php?ou=公众号欧歌app&mz=all&jar=all&b=欧歌"
]

# 【绞杀名单】(去盘、去搜、去Alist)
# 只要名字、API或Key包含这些字眼，直接删除
KILL_KEYWORDS = [
    "盘", "搜", "alist", "drive", "ali", "quark", "uc", "115", 
    "1359527", "yiso", "push", "推送", "存储"
]

# 【通用黑名单】(去广告)
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "更新", "扫码", "微信", "企鹅", "APP", "下载", "推广", "验证", "激活", "授权", 
    "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播", "77.110", "mingming", "摸鱼"
]

TIMEOUT = 15       
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
    """清洗单个接口"""
    # 1. 强制剥离所有接口自带的 Jar
    if 'jar' in site:
        del site['jar']
        
    name = str(site.get('name', ''))
    api = str(site.get('api', ''))
    key = str(site.get('key', ''))
    
    name_lower = name.lower()
    api_lower = api.lower()
    key_lower = key.lower()
    
    # 2. 【核心绞杀】无差别去盘去搜
    # 哪怕是饭太硬自带的"阿里盘搜"，只要带"盘"或"搜"，照样杀
    for kw in KILL_KEYWORDS:
        kw_lower = kw.lower()
        if kw_lower in name_lower: return None
        if kw_lower in api_lower: return None
        if kw_lower in key_lower: return None

    # 3. 广告过滤
    if any(bw in name for bw in BLACKLIST): return None
    if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): return None
    
    # 4. 标记与美化
    site['name'] = clean_name(name)
    site['searchable'] = 1 
    site['quickSearch'] = 1
    
    if site.get('type') == 3:
        site['name'] = f"🛡️ {site['name']}" 
    else:
        site['name'] = f"🚀 {site['name']}" 
        
    return site

def fetch_sites_from_url(url):
    print(f"    -> 正在抓取: {url}")
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

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox v43.0 (饭皇底板+去盘去搜+私有Jar)")
        
        # 1. 获取饭太硬底板配置
        print(f">>> [1/3] 下载饭太硬底板配置...")
        base_config = get_json(BASE_CONFIG_URL)
        if not base_config:
            print(f"    [!] 镜像站失败，尝试官方直连...")
            base_config = get_json(BASE_CONFIG_URL_BACKUP)
            
        if not base_config:
            print("    [!!!] 严重错误：无法获取饭太硬底板！使用空模板。")
            base_config = {"spider": "", "sites": [], "parses": [], "flags": [], "rules": [], "lives": []}
            
        # 2. 改造主干架构
        base_config['spider'] = GLOBAL_SAFE_JAR   # 换成你的 Jar
        base_config['wallpaper'] = WALLPAPER_URL  # 换壁纸
        base_config['drives'] = []                # 彻底清空网盘挂载点
        
        # 3. 清洗饭太硬自带的接口
        print(">>> [2/3] 清洗饭太硬源 (无情绞杀盘/搜)...")
        clean_base_sites = []
        if 'sites' in base_config:
            for s in base_config['sites']:
                processed = process_site(s)
                if processed:
                    clean_base_sites.append(processed)
        
        # 4. 并发抓取扩展源
        print(f">>> [3/3] 抓取并融合其他大厂源...")
        additional_sites = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(fetch_sites_from_url, url): url for url in ADDITIONAL_URLS}
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    sites = future.result()
                    if sites: additional_sites.extend(sites)
                except: pass
        
        # 5. 合并、去重与截断
        # 保证饭太硬的源排在最前面
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
        
        # 6. 保存输出
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(base_config, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 完成！")
        print(f"📊 最终接口: {len(unique_sites)} 个")
        print(f"🧬 底板架构: 饭太硬 (完全继承解析/规则/直播)")
        print(f"🚫 剔除规则: 盘、搜、Alist、Drive等")
        print(f"🛡️ 核心 Jar: {GLOBAL_SAFE_JAR}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":GLOBAL_SAFE_JAR, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
