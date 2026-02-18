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
# 兼容性之王，能驱动绝大多数接口
GLOBAL_SAFE_JAR = "http://www.饭太硬.com/To/jar/3.jar"

# 【壁纸】
WALLPAPER_URL = "https://api.kdcc.cn"

# 【亲生宿主列表】
# 优先抓取，且保留其 Spider 接口
COMPATIBLE_HOSTS = [
    "http://www.饭太硬.com/tv",
    "http://肥猫.com",
    "http://fty.xxooo.cf/tv",
    "http://rihou.cc:88/荷城茶秀"
]

# 【搜刮列表】(新增道长官方源)
EXTERNAL_URLS = COMPATIBLE_HOSTS + [
    # --- 道长 dr_py 官方源 (你刚才发的代码的源头) ---
    "https://raw.githubusercontent.com/hjdhnx/dr_py/main/tvbox.json",
    
    # --- 其他优质大厂 ---
    "https://api.hgyx.vip/hgyx.json",                  # 韩国佬
    "https://tv.菜妮丝.top",                           # 菜妮丝
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json", # 南风
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",     # 宝盒
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",       # 短剧
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",  # 动力
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",          # 道长镜像
    "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json", # 高天流云
    "https://www.252035.xyz/z/FongMi.json",            # FongMi
    "http://52bsj.vip:81/api/v3/file/get/29899/bsj2023.json?sign=3c594b2b985b365bad", # 运输车
    
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

# 【广告/垃圾 黑名单】
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "更新", "扫码", "微信", "企鹅", "APP", "下载", "推广", "验证", "激活", "授权", 
    "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播", "77.110", "mingming", "摸鱼"
]

# 【网盘/Alist 特征词】(精准剔除你不需要的网盘)
# 只要 API 或 名字 里包含这些，直接杀掉
DISK_KEYWORDS = [
    "阿里云", "夸克", "UC网盘", "115", "网盘", "云盘", "推送", "存储", 
    "Drive", "Ali", "Quark", "Alist", "1359527.xyz" # 屏蔽道长的私有服务器(不稳定)
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
        # 1. 强制剥离 Jar (防止闪退，统一用饭太硬核心)
        if 'jar' in site:
            del site['jar']
            
        name = site.get('name', '')
        api = str(site.get('api', ''))
        stype = site.get('type', 0)
        
        # 2. 【核心】网盘 & Alist 过滤
        # 道长的配置里有很多 "Alist(xx)" 和 "http://.../alist.min.js"
        # 这里统一查杀
        is_disk = False
        # 查名字
        if any(k in name for k in DISK_KEYWORDS): is_disk = True
        # 查API链接 (不区分大小写)
        if not is_disk:
            api_lower = api.lower()
            if any(k.lower() in api_lower for k in DISK_KEYWORDS): is_disk = True
            
        if is_disk:
            # print(f"       [x] 剔除网盘/Alist: {name}")
            return None

        # 3. 广告过滤
        if any(bw in name for bw in BLACKLIST): return None
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): return None
        
        # 4. 防崩过滤
        # 如果是外部源的 Spider (Type 3)，且不是来自亲生宿主
        # 为了防止不兼容，建议过滤。但如果你想赌它能用，可以注释掉下面两行。
        # (道长的 drpy 很多需要他的私有服务器，这里为了稳定，如果不兼容就丢弃)
        if stype == 3 and not is_compatible_host:
             # 但是，为了不错过好资源，我们放宽一点：
             # 如果是 drpy 类型的，且用了外部 JS，可能不兼容。
             # 这里我们采取“试探性保留”，不强制杀掉，看看饭太硬 Jar 能不能扛住。
             pass 
        
        # 5. 标记与美化
        site['name'] = clean_name(name)
        site['searchable'] = 1 
        site['quickSearch'] = 1
        
        if stype == 3:
            site['name'] = f"🛡️ {site['name']}" # Spider
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
        print(">>> 启动 TVBox v39.0 (去Alist/吸纳道长/饭太硬核心)")
        
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
                
        # 3. 截断 (保留300个)
        max_sites = 300
        if len(unique_sites) > max_sites:
            unique_sites = unique_sites[:max_sites]
        
        # 4. 生成配置
        config = {
            "spider": GLOBAL_SAFE_JAR, # 饭太硬官方 HTTP Jar
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
        print(f"🧹 已剔除: Alist/网盘/道长私有服务器接口")
        print(f"🛡️ 核心 Jar: {GLOBAL_SAFE_JAR}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":GLOBAL_SAFE_JAR, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
