import requests
import json
import re
import concurrent.futures
import os
import sys
import base64
from urllib.parse import quote, urljoin

# ================= 1. 配置区域 =================

# 【全局唯一 Jar：用户指定代理版】
GLOBAL_SAFE_JAR = "http://hk.gh-proxy/https://raw.githubusercontent.com/yoursmile66/TVBox/main/jar/fan.jar"

# 【壁纸】
WALLPAPER_URL = "https://api.kdcc.cn"

# 【搜刮列表：GitHub 专供版】
# 这些源在 GitHub Actions 环境下连接成功率最高
EXTERNAL_URLS = [
    # --- 核心大厂 (GitHub 镜像) ---
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",      # 南风
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",          # 宝盒
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",       # 动力
    "https://raw.githubusercontent.com/2hacc/TVBox/main/tvbox.json",         # 二哈
    "https://raw.githubusercontent.com/chengxueli818913/maoTV/main/44.json", # 摸鱼镜像
    
    # --- 优质聚合 (GitHub 托管) ---
    "https://cdn.jsdelivr.net/gh/2hacc/TVBox@main/tvbox.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    "https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://raw.githubusercontent.com/1000y/ip/main/tvbox.json",
    
    # --- 备用 CDN 源 ---
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://www.252035.xyz/z/FongMi.json",
    "https://api.hgyx.vip/hgyx.json",
    "https://tv.菜妮丝.top",
    
    # --- 尝试连接的国内大厂 ---
    "https://fty.xxooo.cf/tv",
    "http://我不是.摸鱼儿.com"
]

# 【过滤配置】
ALLOWED_TYPES = [0, 1, 3, 4] 

# 【黑名单：去广告 + 去网盘】
BLACKLIST = [
    # --- 广告/垃圾 ---
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "更新", "扫码", "微信", "企鹅", "APP", "下载", "推广", "验证", "激活", "授权", 
    "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播", "77.110", "mingming",
    
    # --- 网盘/云盘 (新增过滤) ---
    "网盘", "云盘", "阿里云", "夸克", "UC", "115", "Drive", "Pan", "推送", "存储", "盘搜", 
    "Ali", "Quark", "Yun", "Telegraph"
]

TIMEOUT = 20       
MAX_WORKERS = 30   

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

# ================= 3. 核心处理逻辑 =================

def fetch_and_process(url):
    print(f"    -> 正在抓取: {url}")
    data = get_json(url)
    if not data: 
        return []
    
    extracted_sites = []
    
    def process_site(site):
        # 1. 强制剥离 Jar
        if 'jar' in site:
            del site['jar']
            
        name = site.get('name', '')
        api = str(site.get('api', ''))
        key = str(site.get('key', ''))
        
        # 2. 深度网盘过滤 (API 检查)
        # 很多网盘源名字不带"网盘"，但 API 里有特征
        disk_keywords = ['Ali', 'Quark', 'UC', '115', 'Drive', 'Pan', 'Push']
        if any(k.lower() in api.lower() for k in disk_keywords): return None
        if any(k.lower() in key.lower() for k in disk_keywords): return None
        
        # 3. 关键词黑名单 (名字检查)
        if any(bw in name for bw in BLACKLIST): return None
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): return None
        
        # 4. 标记与美化
        site['name'] = clean_name(name)
        site['searchable'] = 1 
        site['quickSearch'] = 1
        
        if site.get('type') == 3:
            site['name'] = f"🛡️ {site['name']}" # 爬虫
        else:
            site['name'] = f"🚀 {site['name']}" # CMS
            
        return site

    # 提取多仓
    if 'urls' in data and isinstance(data['urls'], list):
        for item in data['urls']:
            if 'url' in item:
                sub_data = get_json(item['url'])
                if sub_data and 'sites' in sub_data:
                    for s in sub_data['sites']:
                        processed = process_site(s)
                        if processed: extracted_sites.append(processed)
    
    # 提取单仓
    if 'sites' in data:
        for s in data['sites']:
            processed = process_site(s)
            if processed: extracted_sites.append(processed)
            
    return extracted_sites

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox v36.0 (代理Jar/去网盘版)")
        
        all_sites = []
        unique_urls = list(set(EXTERNAL_URLS))
        
        # 1. 并发抓取
        print(f">>> [1/2] 正在聚合 {len(unique_urls)} 个源...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(fetch_and_process, url): url for url in unique_urls}
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    sites = future.result()
                    if sites: all_sites.extend(sites)
                except: pass
        
        # 2. 去重与生成
        print(f">>> [2/2] 去重与打包...")
        unique_sites = []
        seen_api = set()
        
        for s in all_sites:
            api = s.get('api', '')
            if api and api not in seen_api:
                unique_sites.append(s)
                seen_api.add(api)
                
        # 3. 截断
        max_sites = 250
        if len(unique_sites) > max_sites:
            unique_sites = unique_sites[:max_sites]
        
        # 4. 生成配置
        config = {
            "spider": GLOBAL_SAFE_JAR, # 你的代理 Jar 地址
            "wallpaper": WALLPAPER_URL,
            "sites": unique_sites,
            "lives": [],
            "parses": [],
            "flags": []
        }
        
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 完成！")
        print(f"📊 聚合接口: {len(unique_sites)} 个")
        print(f"🧹 已清理所有网盘/推送到源")
        print(f"🛡️ 核心 Jar: {GLOBAL_SAFE_JAR}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":GLOBAL_SAFE_JAR, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
