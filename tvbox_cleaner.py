import requests
import json
import re
import concurrent.futures
import os
import sys
import base64
from urllib.parse import quote, urljoin

# ================= 1. 配置区域 =================

# 【核心配置】
# 最终生成的 JSON 里，Spider 指向饭太硬官方 Jar (最稳定，不搞代理了)
FINAL_SPIDER_URL = "http://www.饭太硬.com/To/jar/3.jar"
FINAL_WALLPAPER = "https://api.kdcc.cn"

# 【抓取专用地址】
# GitHub 抓不到 www.饭太硬.com，必须用 fty.xxooo.cf 这个镜像来抓
PRIME_SOURCE_URL = "http://fty.xxooo.cf/tv"

# 【补充源列表】(只抓取通用接口，并去网盘)
EXTERNAL_URLS = [
    # 优质大厂 (GitHub 镜像，速度快)
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",
    "https://raw.githubusercontent.com/2hacc/TVBox/main/tvbox.json",
    
    # 优质聚合
    "https://cdn.jsdelivr.net/gh/2hacc/TVBox@main/tvbox.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    "https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    
    # 备用
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://tv.菜妮丝.top",
    "https://api.hgyx.vip/hgyx.json"
]

# 【过滤配置】
ALLOWED_TYPES = [0, 1, 3, 4] 

# 【黑名单】(广告/垃圾)
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "更新", "扫码", "微信", "企鹅", "APP", "下载", "推广", "验证", "激活", "授权", 
    "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播", "77.110", "mingming"
]

# 【网盘特征】(用于过滤外部源的网盘)
DISK_KEYWORDS = ["阿里云", "夸克", "UC网盘", "115", "网盘", "云盘", "推送", "存储", "Drive", "Ali", "Quark"]

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

def fetch_and_process(url, is_prime=False):
    print(f"    -> 正在抓取: {url} ({'宿主' if is_prime else '扩展'})")
    data = get_json(url)
    if not data: 
        print(f"       [!] 失败: {url}")
        return []
    
    extracted_sites = []
    
    def process_site(site):
        # 1. 强制剥离 Jar (核心防崩)
        if 'jar' in site:
            del site['jar']
            
        name = site.get('name', '')
        api = str(site.get('api', ''))
        
        # 2. 如果是宿主 (饭太硬)，无条件保留 (除了明显的广告)
        if is_prime:
            if "失效" in name or "测试" in name: return None
            site['name'] = clean_name(name) # 仅美化名字
            site['searchable'] = 1
            site['quickSearch'] = 1
            # 给宿主打标
            if site.get('type') == 3:
                site['name'] = f"🛡️ {site['name']}"
            else:
                site['name'] = f"☘️ {site['name']}"
            return site

        # 3. 如果是外部源，执行严格过滤
        # 3.1 广告过滤
        if any(bw in name for bw in BLACKLIST): return None
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): return None
        
        # 3.2 网盘过滤 (外部源不要网盘)
        is_disk = False
        if any(k in name for k in ["阿里云", "夸克", "UC网盘", "115", "网盘", "推送"]): is_disk = True
        if not is_disk:
            api_lower = api.lower()
            if "ali" in api_lower or "quark" in api_lower or "ucpan" in api_lower or "115.com" in api_lower or "drive" in api_lower:
                is_disk = True
        if is_disk: return None
        
        # 3.3 美化
        site['name'] = f"🚀 {clean_name(name)}"
        site['searchable'] = 1 
        site['quickSearch'] = 1
        
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
        print(">>> 启动 TVBox v38.0 (饭太硬全收录+扩展去网盘)")
        
        all_sites = []
        
        # 1. 优先抓取宿主 (饭太硬)
        # 必须单独抓，确保它一定在
        print(">>> [1/3] 抓取宿主 (饭太硬)...")
        prime_sites = fetch_and_process(PRIME_SOURCE_URL, is_prime=True)
        if prime_sites:
            print(f"    [√] 成功获取饭太硬接口: {len(prime_sites)} 个")
            all_sites.extend(prime_sites)
        else:
            print("    [!] 警告：无法连接饭太硬镜像，尝试连接官方...")
            # 备用尝试
            prime_sites = fetch_and_process("http://www.饭太硬.com/tv", is_prime=True)
            if prime_sites: all_sites.extend(prime_sites)

        # 2. 并发抓取扩展源
        print(f">>> [2/3] 抓取扩展源 ({len(EXTERNAL_URLS)}个)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(fetch_and_process, url, False): url for url in EXTERNAL_URLS}
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    sites = future.result()
                    if sites: all_sites.extend(sites)
                except: pass
        
        # 3. 去重与生成
        print(f">>> [3/3] 去重与打包...")
        unique_sites = []
        seen_api = set()
        
        # 此时 all_sites 里饭太硬已经在最前面了
        for s in all_sites:
            api = s.get('api', '')
            if api and api not in seen_api:
                unique_sites.append(s)
                seen_api.add(api)
                
        # 截断
        if len(unique_sites) > 300:
            unique_sites = unique_sites[:300]
        
        # 生成配置
        config = {
            "spider": FINAL_SPIDER_URL, # 官方Jar
            "wallpaper": WALLPAPER_URL,
            "sites": unique_sites,
            "lives": [],
            "parses": [],
            "flags": []
        }
        
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 完成！")
        print(f"📊 总计接口: {len(unique_sites)} 个")
        print(f"🛡️ 核心 Jar: {FINAL_SPIDER_URL}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":FINAL_SPIDER_URL, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
