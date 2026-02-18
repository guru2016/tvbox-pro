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
# 注意：国内网络直接访问此链接可能会慢或失败，但在 TVBox 内部通常能自动处理 302 跳转
GLOBAL_SAFE_JAR = "https://github.com/guru2016/tvbox-pro/raw/refs/heads/main/custom_spider.jar"

# 【壁纸】(替换道长不稳定的壁纸)
WALLPAPER_URL = "https://api.kdcc.cn"

# 【底板来源：道长 dr_py 官方配置】
# 我们将以这个文件的结构（parses, rules, flags）为基础进行修改
BASE_CONFIG_URL = "https://raw.githubusercontent.com/hjdhnx/dr_py/main/tvbox.json"

# 【追加搜刮列表】
# 在道长的基础上，添加这些优质源
ADDITIONAL_URLS = [
    "http://www.饭太硬.com/tv",
    "http://肥猫.com",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",      # 南风
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",          # 宝盒
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",       # 动力
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",              # 道长镜像
    "https://api.hgyx.vip/hgyx.json",
    "https://tv.菜妮丝.top"
]

# 【过滤配置】
ALLOWED_TYPES = [0, 1, 3, 4] 

# 【通用黑名单】
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "更新", "扫码", "微信", "企鹅", "APP", "下载", "推广", "验证", "激活", "授权", 
    "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播", "77.110", "mingming", "摸鱼"
]

# 【网盘特征词】(用于清洗道长原来的网盘接口)
# 遇到这些词，直接杀掉
DISK_KEYWORDS = [
    "阿里云", "夸克", "UC网盘", "115", "网盘", "云盘", "推送", "存储", 
    "Drive", "Ali", "Quark", "Alist", "1359527.xyz" # 屏蔽道长私有服务器
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
        # verify=False 忽略证书错误
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
    """
    清洗单个 Site 对象
    """
    # 1. 强制剥离 Jar
    if 'jar' in site:
        del site['jar']
        
    name = site.get('name', '')
    api = str(site.get('api', ''))
    
    # 2. 网盘 & Alist 过滤
    is_disk = False
    if any(k in name for k in DISK_KEYWORDS): is_disk = True
    if not is_disk:
        api_lower = api.lower()
        if any(k.lower() in api_lower for k in DISK_KEYWORDS): is_disk = True
        
    if is_disk:
        return None

    # 3. 广告过滤
    if any(bw in name for bw in BLACKLIST): return None
    
    # 4. 标记与美化
    site['name'] = clean_name(name)
    site['searchable'] = 1 
    site['quickSearch'] = 1
    
    # 5. 特殊处理：如果 Type 3 接口的 API 看起来是需要道长私有服务器的(比如 drpy.min.js)，
    # 因为我们换了 Jar，这些大概率会崩。建议保留标准 CMS (Type 0/1) 和兼容性好的 Type 3。
    # 这里我们只保留名字里带 "drpy" 但 API 也是 http 的，或者标准的 CSP。
    
    if site.get('type') == 3:
        site['name'] = f"🛡️ {site['name']}" 
    else:
        site['name'] = f"🚀 {site['name']}" 
        
    return site

def fetch_sites_from_url(url):
    """
    从指定 URL 抓取并清洗 sites
    """
    print(f"    -> 抓取扩展源: {url}")
    data = get_json(url)
    if not data: return []
    
    extracted = []
    
    # 处理多仓
    if 'urls' in data and isinstance(data['urls'], list):
        for item in data['urls']:
            if 'url' in item:
                sub = get_json(item['url'])
                if sub and 'sites' in sub:
                    for s in sub['sites']:
                        p = process_site(s)
                        if p: extracted.append(p)
    
    # 处理单仓
    if 'sites' in data:
        for s in data['sites']:
            p = process_site(s)
            if p: extracted.append(p)
            
    return extracted

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox v41.0 (道长底板+私有Jar+融合版)")
        
        # 1. 获取道长底板配置
        print(f">>> [1/3] 下载道长底板配置: {BASE_CONFIG_URL}")
        base_config = get_json(BASE_CONFIG_URL)
        
        if not base_config:
            print("!!! 无法下载底板，将使用空模板")
            base_config = {"spider": "", "sites": [], "parses": [], "flags": [], "rules": []}
            
        # 2. 修改底板核心参数
        base_config['spider'] = GLOBAL_SAFE_JAR   # 替换 Jar
        base_config['wallpaper'] = WALLPAPER_URL  # 替换壁纸
        base_config['drives'] = []                # 清空网盘挂载 (核心去网盘步骤)
        
        # 3. 清洗道长原有的 Sites
        # 道长的源里混合了大量网盘，需要清洗
        print(">>> [2/3] 清洗道长原有接口...")
        clean_base_sites = []
        if 'sites' in base_config:
            for s in base_config['sites']:
                processed = process_site(s)
                if processed:
                    clean_base_sites.append(processed)
        
        # 4. 并发抓取追加源
        print(f">>> [3/3] 融合其他 {len(ADDITIONAL_URLS)} 个大厂源...")
        additional_sites = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(fetch_sites_from_url, url): url for url in ADDITIONAL_URLS}
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    sites = future.result()
                    if sites: additional_sites.extend(sites)
                except: pass
        
        # 5. 合并与去重
        # 顺序：道长清洗后的源 + 追加的大厂源
        all_sites = clean_base_sites + additional_sites
        unique_sites = []
        seen_api = set()
        
        for s in all_sites:
            api = s.get('api', '')
            if api and api not in seen_api:
                unique_sites.append(s)
                seen_api.add(api)
        
        # 截断
        if len(unique_sites) > 350:
            unique_sites = unique_sites[:350]
            
        base_config['sites'] = unique_sites
        
        # 6. 保存
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(base_config, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 完成！")
        print(f"📊 最终接口: {len(unique_sites)} 个")
        print(f"🧬 继承: 道长 Parses/Rules/Flags")
        print(f"🧹 剔除: 道长 Drives (网盘挂载)")
        print(f"🛡️ 核心 Jar: {GLOBAL_SAFE_JAR}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":GLOBAL_SAFE_JAR, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
