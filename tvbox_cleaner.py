import requests
import json
import re
import concurrent.futures
import os
import sys
import base64
from urllib.parse import quote, urljoin

# ================= 1. 配置区域 =================

# 【全局唯一 Jar：使用 GitHub 托管的稳定版】
# 既然在 GitHub 跑，就用 GitHub 的资源，速度最快
GLOBAL_SAFE_JAR = "https://raw.githubusercontent.com/yoursmile66/TVBox/main/jar/fan.jar"

# 【壁纸】
WALLPAPER_URL = "https://api.kdcc.cn"

# 【搜刮列表：全员 GitHub 化】
# 这些全是托管在 GitHub/GitLab 上的地址，美国 IP 访问秒开！
# 彻底解决了“国内源连不上”的问题
EXTERNAL_URLS = [
    # --- 核心大厂 (GitHub 镜像) ---
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",      # 南风 (极稳)
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",          # 宝盒 (极稳)
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",       # 动力 (极稳)
    "https://raw.githubusercontent.com/2hacc/TVBox/main/tvbox.json",         # 二哈 (极稳)
    "https://raw.githubusercontent.com/chengxueli818913/maoTV/main/44.json", # 摸鱼镜像(去广后可用)
    
    # --- 优质聚合 (GitHub 托管) ---
    "https://cdn.jsdelivr.net/gh/2hacc/TVBox@main/tvbox.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    "https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://raw.githubusercontent.com/1000y/ip/main/tvbox.json",
    
    # --- 备用 CDN 加速源 (这些通常对海外友好) ---
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://www.252035.xyz/z/FongMi.json",
    "https://api.hgyx.vip/hgyx.json",
    "https://tv.菜妮丝.top",
    
    # --- 饭太硬 / 肥猫 (尝试使用 CF 加速域名，赌它能连上) ---
    "https://fty.xxooo.cf/tv",
    "http://我不是.摸鱼儿.com" # 它的CF域名
]

# 【代理配置 (如果你有稳定的代理，填在这里)】
# 格式: {"http": "http://ip:port", "https": "http://ip:port"}
# 如果留空，脚本会自动使用 GitHub 直连模式
PROXIES = None  
# 示例 (不要直接用，肯定挂了): 
# PROXIES = {"http": "http://112.113.114.115:8888", "https": "http://112.113.114.115:8888"}

# 【过滤配置】
ALLOWED_TYPES = [0, 1, 3, 4] 

# 【黑名单】(稍微放宽了一点，先抓下来再说)
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "更新", "扫码", "微信", "企鹅", "APP", "下载", 
    "推广", "验证", "激活", "授权", "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播",
    "77.110", "mingming"
]

TIMEOUT = 20       # GitHub 有时候握手慢，给足时间
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
        # 如果是 GitHub 的链接，不需要代理，速度飞快
        # 如果是国内链接，尝试直连
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
        print(f"       [!] 失败 (可能是IP被墙): {url}")
        return []
    
    print(f"       [√] 成功! 解析中...")
    extracted_sites = []
    
    def process_site(site):
        # 1. 强制剥离 Jar
        if 'jar' in site:
            del site['jar']
            
        name = site.get('name', '')
        stype = site.get('type', 0)
        
        # 2. 黑名单清洗
        if any(bw in name for bw in BLACKLIST): return None
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): return None
        
        # 3. 标记与美化
        site['name'] = clean_name(name)
        site['searchable'] = 1 
        site['quickSearch'] = 1
        
        if stype == 3:
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
        print(">>> 启动 TVBox GitHub 专供版 v35.0")
        
        all_sites = []
        unique_urls = list(set(EXTERNAL_URLS))
        
        # 1. 并发抓取
        print(f">>> [1/2] 正在聚合 {len(unique_urls)} 个 GitHub 友好源...")
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
        
        # 优先保留排在前面的源
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
            "spider": GLOBAL_SAFE_JAR, 
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
        print(f"🛡️ 核心 Jar: GitHub 镜像直连")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":GLOBAL_SAFE_JAR, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
