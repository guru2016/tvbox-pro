import requests
import json
import re
import concurrent.futures
import os
import sys
import base64
from urllib.parse import quote, urljoin

# ================= 1. 配置区域 =================

# 【全局唯一 Jar：饭太硬官方直连】
GLOBAL_SAFE_JAR = "http://www.饭太硬.com/To/jar/3.jar"

# 【壁纸】
WALLPAPER_URL = "https://api.kdcc.cn"

# 【搜刮列表】(包含核心 + 镜像 + 散户)
EXTERNAL_URLS = [
    # --- 核心宿主 (注意：GitHub IP可能会连不上这些，导致源少) ---
    "http://www.饭太硬.com/tv",
    "http://肥猫.com",
    
    # --- 镜像/托管源 (GitHub友好，容易抓取) ---
    "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://cdn.jsdelivr.net/gh/2hacc/TVBox@main/tvbox.json",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    
    # --- 优质大厂 ---
    "http://rihou.cc:88/荷城茶秀",
    "https://api.hgyx.vip/hgyx.json",
    "https://tv.菜妮丝.top",
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",
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

# 【黑名单】(只杀广告，不杀源)
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "弹幕", "更新", "公众号", "扫码", "微信", "企鹅", "APP", "下载", 
    "推广", "验证", "激活", "授权", "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播",
    "77.110", "mingming", "摸鱼"
]

TIMEOUT = 10       
MAX_WORKERS = 50   

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
        # 禁用证书验证，提高成功率
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

def fetch_and_process(url):
    data = get_json(url)
    if not data: return []
    
    extracted_sites = []
    
    def process_site(site):
        # 1. 强制剥离 Jar (防止闪退)
        if 'jar' in site:
            del site['jar']
            
        name = site.get('name', '')
        # stype = site.get('type', 0)
        
        # 2. 黑名单清洗
        if any(bw in name for bw in BLACKLIST): return None
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): return None
        
        # 3. 【核心放行】不再检查宿主兼容性，是个Spider就放行！
        # 只要不是黑名单里的，全部保留
        
        # 4. 标记与美化
        site['name'] = clean_name(name)
        site['searchable'] = 1 
        site['quickSearch'] = 1
        
        # 打标：让用户知道哪些是可能不兼容的爬虫
        if site.get('type') == 3:
            site['name'] = f"🛡️ {site['name']}" # 爬虫源
        else:
            site['name'] = f"🚀 {site['name']}" # CMS/App
            
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
        print(">>> 启动 TVBox 广撒网·无脑聚合版 v32.0")
        
        all_sites = []
        unique_urls = list(set(EXTERNAL_URLS))
        
        # 1. 并发抓取
        print(f">>> [1/2] 正在疯狂聚合 {len(unique_urls)} 个订阅源...")
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
                
        # 3. 截断 (放宽到 300)
        max_sites = 300
        if len(unique_sites) > max_sites:
            unique_sites = unique_sites[:max_sites]
        
        # 4. 生成配置
        config = {
            "spider": GLOBAL_SAFE_JAR, # 饭太硬官方直连
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
        print(f"💡 提示: 如果数量依然少，说明GitHub IP被饭太硬等国内源墙了，建议在本地运行脚本。")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":GLOBAL_SAFE_JAR, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
