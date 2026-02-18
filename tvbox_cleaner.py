import requests
import json
import re
import concurrent.futures
import os
import sys
import base64
from urllib.parse import quote, urljoin

# ================= 1. 配置区域 =================

# 【全局唯一 Jar：你仓库里的 custom_spider.jar】
# 使用 jsDelivr 加速你的 GitHub 文件，国内访问速度极快，且极其稳定
GLOBAL_SAFE_JAR = "https://cdn.jsdelivr.net/gh/guru2016/tvbox-pro@main/custom_spider.jar"

# 【壁纸】
WALLPAPER_URL = "https://api.kdcc.cn"

# 【亲生宿主列表】(优先抓取)
COMPATIBLE_HOSTS = [
    "http://www.饭太硬.com/tv",
    "http://肥猫.com",
    "http://fty.xxooo.cf/tv",
    "http://rihou.cc:88/荷城茶秀"
]

# 【搜刮列表】(包含道长、饭太硬及各大厂)
EXTERNAL_URLS = COMPATIBLE_HOSTS + [
    # --- 道长 dr_py 官方源 ---
    "https://raw.githubusercontent.com/hjdhnx/dr_py/main/tvbox.json",
    
    # --- 优质大厂 (GitHub 镜像) ---
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",      # 南风
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",          # 宝盒
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",       # 动力
    "https://raw.githubusercontent.com/2hacc/TVBox/main/tvbox.json",         # 二哈
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",              # 道长镜像
    
    # --- 备用源 ---
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://www.252035.xyz/z/FongMi.json",
    "https://api.hgyx.vip/hgyx.json",
    "https://tv.菜妮丝.top",
    "http://ok321.top/tv",
    "http://tvbox.王二小放牛娃.top",
    "http://cdn.qiaoji8.com/tvbox.json" 
]

# 【过滤配置】
ALLOWED_TYPES = [0, 1, 3, 4] 

# 【通用黑名单】(去广告)
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "更新", "扫码", "微信", "企鹅", "APP", "下载", "推广", "验证", "激活", "授权", 
    "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播", "77.110", "mingming", "摸鱼"
]

# 【网盘/Alist 特征词】(精准剔除)
# 遇到这些词，直接杀掉
DISK_KEYWORDS = [
    "阿里云", "夸克", "UC网盘", "115", "网盘", "云盘", "推送", "存储", 
    "Drive", "Ali", "Quark", "Alist", "1359527.xyz"
]

TIMEOUT = 15       
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
    
    # 判定是否为亲生宿主
    is_compatible_host = False
    for host in COMPATIBLE_HOSTS:
        if host in url:
            is_compatible_host = True
            break
    
    def process_site(site):
        # 1. 强制剥离 Jar (确保所有源都使用你上传的 custom_spider.jar)
        if 'jar' in site:
            del site['jar']
            
        name = site.get('name', '')
        api = str(site.get('api', ''))
        stype = site.get('type', 0)
        
        # 2. 网盘 & Alist 过滤
        is_disk = False
        # 查名字
        if any(k in name for k in DISK_KEYWORDS): is_disk = True
        # 查API链接
        if not is_disk:
            api_lower = api.lower()
            if any(k.lower() in api_lower for k in DISK_KEYWORDS): is_disk = True
            
        if is_disk:
            # print(f"       [x] 剔除网盘: {name}")
            return None

        # 3. 广告过滤
        if any(bw in name for bw in BLACKLIST): return None
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): return None
        
        # 4. 防崩逻辑 (Type 3 Spider)
        # 如果是外部源的 Spider，且不是饭太硬/肥猫本家的
        # 既然你用了自定义 Jar，我们尽量保留这些 Spider 试试看
        # 但如果道长的 drpy 依赖他的私有服务器，不兼容时可能会报错
        
        # 5. 标记与美化
        site['name'] = clean_name(name)
        site['searchable'] = 1 
        site['quickSearch'] = 1
        
        if stype == 3:
            site['name'] = f"🛡️ {site['name']}" 
        else:
            site['name'] = f"🚀 {site['name']}" 
            
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
        print(">>> 启动 TVBox v40.0 (私有Jar直连/去网盘)")
        
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
        max_sites = 300
        if len(unique_sites) > max_sites:
            unique_sites = unique_sites[:max_sites]
        
        # 4. 生成配置
        config = {
            "spider": GLOBAL_SAFE_JAR, # 指向你的 GitHub 文件
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
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":GLOBAL_SAFE_JAR, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
