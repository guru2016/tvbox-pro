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
# 不再使用 GitHub 转发，直接用官方地址
GLOBAL_SAFE_JAR = "http://www.饭太硬.com/To/jar/3.jar"

# 【壁纸】
WALLPAPER_URL = "https://api.kdcc.cn"

# 【搜刮列表】(包含核心 + 优质大厂 + 散户)
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

# 【静态过滤配置】(只过滤名字，不测网速)
ALLOWED_TYPES = [0, 1, 3, 4] 
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "弹幕", "更新", "公众号", "扫码", "微信", "企鹅", "APP", "下载", 
    "推广", "验证", "激活", "授权", "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播",
    "77.110", "mingming"
]

TIMEOUT = 15       # 下载配置的超时时间
MAX_WORKERS = 30   # 并发下载数

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
        # 增加 verify=False 防止证书报错
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
    """
    抓取配置 -> 提取接口 -> 剥离Jar -> 静态过滤
    """
    data = get_json(url)
    if not data: return []
    
    extracted_sites = []
    
    def process_site(site):
        # 1. 强制剥离 Jar (防止闪退)
        if 'jar' in site:
            del site['jar']
            
        # 2. 静态清洗
        name = site.get('name', '')
        # stype = site.get('type', 0) # 暂时不卡死类型，宽进
        
        # 关键词过滤
        if any(bw in name for bw in BLACKLIST): return None
        # Emoji 广告过滤
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): return None
        
        # 美化名字
        site['name'] = clean_name(name)
        
        # 统一开启搜索
        site['searchable'] = 1
        site['quickSearch'] = 1
        
        # 打标
        if site.get('type') == 3:
            site['name'] = f"🛡️ {site['name']}" # 饭太硬内核 Spider
        else:
            site['name'] = f"🚀 {site['name']}" # CMS/App
            
        return site

    # 提取多仓 urls
    if 'urls' in data and isinstance(data['urls'], list):
        for item in data['urls']:
            if 'url' in item:
                sub_data = get_json(item['url'])
                if sub_data and 'sites' in sub_data:
                    for s in sub_data['sites']:
                        processed = process_site(s)
                        if processed: extracted_sites.append(processed)
    
    # 提取单仓 sites
    if 'sites' in data:
        for s in data['sites']:
            processed = process_site(s)
            if processed: extracted_sites.append(processed)
            
    return extracted_sites

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox 极速聚合版 v28.0 (不测速/直连饭太硬)")
        
        all_sites = []
        unique_urls = list(set(EXTERNAL_URLS))
        
        # 1. 并发抓取
        print(f">>> [1/2] 正在聚合 {len(unique_urls)} 个订阅源...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(fetch_and_process, url): url for url in unique_urls}
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    sites = future.result()
                    if sites: all_sites.extend(sites)
                except: pass
        
        # 2. 去重 (API地址相同则去重)
        print(f">>> [2/2] 去重与生成...")
        unique_sites = []
        seen_api = set()
        
        # 优先保留排在前面的源 (通常大厂在前面)
        for s in all_sites:
            api = s.get('api', '')
            if api and api not in seen_api:
                unique_sites.append(s)
                seen_api.add(api)
                
        # 3. 截断 (虽然不测速，但太多了盒子加载也会慢，限制一下)
        max_sites = 255 # 255 是很多固件的列表上限建议值
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
        print(f"🛡️ 核心 Jar: {GLOBAL_SAFE_JAR}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        # 保底生成空文件，防止 Actions 报错
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":GLOBAL_SAFE_JAR, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
