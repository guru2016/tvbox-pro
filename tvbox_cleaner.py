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
# 按照你的要求，直接用官方 http 地址，不再走 GitHub
GLOBAL_SAFE_JAR = "http://www.饭太硬.com/To/jar/3.jar"

# 【壁纸】
WALLPAPER_URL = "https://api.kdcc.cn"

# 【亲生宿主列表】
# 这些源里的 Type 3 (爬虫) 接口完美兼容饭太硬 Jar，予以保留
COMPATIBLE_HOSTS = [
    "http://www.饭太硬.com/tv",
    "http://肥猫.com",
    "http://fty.xxooo.cf/tv",
    "http://rihou.cc:88/荷城茶秀"
]

# 【搜刮列表】(只管加，脚本会自动清洗)
EXTERNAL_URLS = COMPATIBLE_HOSTS + [
    # --- 重点大厂 (提取通用资源) ---
    "http://cdn.qiaoji8.com/tvbox.json",               # 巧技 (会被剥离Jar，保留CMS)
    "https://api.hgyx.vip/hgyx.json",                  # 韩国佬
    "https://tv.菜妮丝.top",                           # 菜妮丝
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json", # 南风
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",     # 宝盒
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",       # 短剧
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",  # 动力
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",          # 道长
    "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json", # 高天流云
    "https://www.252035.xyz/z/FongMi.json",            # FongMi
    "http://52bsj.vip:81/api/v3/file/get/29899/bsj2023.json?sign=3c594b2b985b365bad", # 运输车
    
    # --- 优质散户 ---
    "http://ok321.top/tv",
    "http://tvbox.王二小放牛娃.top",
    "https://android.lushunming.qzz.io/json/index.json",
    "http://home.jundie.top:81/top98.json",
    "http://tv.nxog.top/m/111.php?ou=公众号欧歌app&mz=all&jar=all&b=欧歌",
    "https://100km.top/0",
    "http://meowtv.cn/tv"
]

# 【静态过滤黑名单】(包含"摸鱼"等广告词)
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "弹幕", "更新", "公众号", "扫码", "微信", "企鹅", "APP", "下载", 
    "推广", "验证", "激活", "授权", "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播",
    "77.110", "mingming", "摸鱼" 
]

# 【极速配置】
TIMEOUT = 15       # 下载配置的超时时间
MAX_WORKERS = 50   # 满血并发下载

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
        # verify=False 忽略证书错误，增加成功率
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
    只下载，不测速，只做静态清洗
    """
    data = get_json(url)
    if not data: return []
    
    extracted_sites = []
    
    # 判定是否为亲生宿主 (用于判断是否保留Spider接口)
    is_compatible_host = False
    for host in COMPATIBLE_HOSTS:
        if host in url:
            is_compatible_host = True
            break
    
    def process_site(site):
        # 1. 强制剥离 Jar (防止闪退)
        if 'jar' in site:
            del site['jar']
            
        name = site.get('name', '')
        stype = site.get('type', 0)
        
        # 2. 防崩过滤：Type 3 (Spider) 必须来自亲生宿主
        # 如果来自巧技等外部源，因为我们删了它的Jar，它肯定跑不起来，所以直接丢弃
        if stype == 3 and not is_compatible_host:
            return None
            
        # 3. 黑名单清洗 (去广告/去摸鱼)
        if any(bw in name for bw in BLACKLIST): return None
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): return None
        
        # 4. 标记与美化
        site['name'] = clean_name(name)
        site['searchable'] = 1 # 默认开启搜索
        site['quickSearch'] = 1
        
        if stype == 3:
            site['name'] = f"🛡️ {site['name']}" # 兼容饭太硬的Spider
        else:
            site['name'] = f"🚀 {site['name']}" # 通用CMS/App
            
        return site

    # 提取逻辑
    if 'urls' in data and isinstance(data['urls'], list):
        for item in data['urls']:
            if 'url' in item:
                sub_data = get_json(item['url'])
                if sub_data and 'sites' in sub_data:
                    for s in sub_data['sites']:
                        processed = process_site(s)
                        if processed: extracted_sites.append(processed)
    
    if 'sites' in data:
        for s in data['sites']:
            processed = process_site(s)
            if processed: extracted_sites.append(processed)
            
    return extracted_sites

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox 光速聚合版 v31.0")
        
        all_sites = []
        unique_urls = list(set(EXTERNAL_URLS))
        
        # 1. 并发抓取 (只下载配置，不测源)
        print(f">>> [1/2] 正在聚合 {len(unique_urls)} 个订阅源...")
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
                
        # 3. 截断 (保留250个，足够丰富且不卡)
        max_sites = 250
        if len(unique_sites) > max_sites:
            unique_sites = unique_sites[:max_sites]
        
        # 4. 生成配置
        config = {
            "spider": GLOBAL_SAFE_JAR, # 官方直连地址
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
        print(f"🚫 已剔除: 摸鱼/广告/不兼容源")
        print(f"🛡️ 核心 Jar: {GLOBAL_SAFE_JAR}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":GLOBAL_SAFE_JAR, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
