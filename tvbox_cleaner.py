import requests
import json
import re
import concurrent.futures
import os
import sys
from urllib.parse import quote, urljoin

# ================= 1. 配置区域 =================

MY_GITHUB_TOKEN = "" 
PROXIES = None 

# 【个人基础配置】
GITHUB_USER = "guru2016"
REPO_NAME = "tvbox-pro"
BRANCH_NAME = "main"
# 全局保底 Jar (当找不到特定 Jar 时用这个)
GLOBAL_SAFE_JAR = f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{REPO_NAME}@{BRANCH_NAME}/spider.jar"

# 【智能 Jar 匹配表】(核心修改)
# 格式: "API关键词": "对应的专用Jar地址"
# 遇到这些 API 时，脚本会自动给它分配专属 Jar，确保能用且无广告
SPECIFIC_JARS = {
    "csp_Xpg": "https://cdn.jsdelivr.net/gh/yoursmile66/TVBox@main/jar/xpg.jar", # 小苹果专用
    "csp_Wogg": "https://cdn.jsdelivr.net/gh/yoursmile66/TVBox@main/jar/wogg.jar", # 玩偶专用
    "csp_Nmys": "https://cdn.jsdelivr.net/gh/yoursmile66/TVBox@main/jar/nmys.jar", # 农民/糯米专用
    "csp_Panda": "https://cdn.jsdelivr.net/gh/yoursmile66/TVBox@main/jar/panda.jar",
    "csp_Jianpian": "https://cdn.jsdelivr.net/gh/2hacc/TVBox@main/jar/jp.jar" # 荐片专用
}

# 【Jar 包域名白名单】
# 只有这些域名下的 Jar 允许被保留，其他的杂牌 Jar 一律替换为 GLOBAL_SAFE_JAR
SAFE_JAR_DOMAINS = [
    "cdn.jsdelivr.net",
    "raw.githubusercontent.com",
    "ghproxy.com",
    "ghproxy.net",
    "fastly.jsdelivr.net",
    "cdn.qiaoji8.com", # 巧技的Jar技术上是没毒的，配置有毒
    "gitlab.com"
]

# 【宿主列表】
HOST_URLS = [
    "http://www.饭太硬.com/tv",       
    "http://肥猫.com",
    "http://fty.xxooo.cf/tv"
]

# 【搜刮列表】
EXTERNAL_URLS = [
    # 聚合大厂
    "http://ok321.top/tv",
    "http://tvbox.王二小放牛娃.top",
    "https://tv.菜妮丝.top",
    "https://api.hgyx.vip/hgyx.json",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",
    "https://android.lushunming.qzz.io/json/index.json",
    "http://home.jundie.top:81/top98.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    # 优质单仓
    "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://www.252035.xyz/z/FongMi.json"
]

# 【过滤配置】
ALLOWED_TYPES = [0, 1, 3, 4] # 全面放开 Type 3
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "弹幕", "更新", "公众号", "扫码", "微信", "企鹅", "APP", "下载", 
    "推广", "验证", "激活", "授权", "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播"
]

TIMEOUT = 8 
MAX_WORKERS = 20

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

# ================= 3. 核心：Jar 智能处理 =================

def process_site_jar(site):
    """
    智能分配 Jar 包：
    1. 如果 API 在 SPECIFIC_JARS 里，强制赋予专用 Jar。
    2. 如果源自带 Jar，检查域名是否在白名单。
       - 在白名单：保留。
       - 不在白名单：剔除 Jar (使用全局 Jar)。
    3. 如果没有 Jar，保持原样 (使用全局 Jar)。
    """
    api = site.get('api', '')
    original_jar = site.get('jar', '')
    
    # 策略 1: 精准匹配 (优先级最高)
    for key, specific_jar in SPECIFIC_JARS.items():
        if key in api:
            site['jar'] = specific_jar
            # print(f"    [🔧] 自动适配 Jar: {site['name']} -> {specific_jar}")
            return site

    # 策略 2: 现有 Jar 安全性检查
    if original_jar:
        is_safe = False
        for domain in SAFE_JAR_DOMAINS:
            if domain in original_jar:
                is_safe = True
                break
        
        if not is_safe:
            # print(f"    [🛡️] 拦截可疑 Jar: {site['name']} -> {original_jar}")
            del site['jar'] # 删除毒 Jar，回退到全局 Jar
    
    return site

# ================= 4. 流程函数 =================

def fetch_base_config_fail_safe():
    print(f">>> [1/5] 连接宿主...")
    if "guru2016" not in GLOBAL_SAFE_JAR:
        print("!!! 警告：GITHUB_USER 未配置！")

    for url in HOST_URLS:
        print(f"    - 尝试: {url}")
        base = get_json(url)
        if base and isinstance(base, dict) and 'sites' in base:
            print(f"    [√] 锁定宿主: {url}")
            base_host = url.rsplit('/', 1)[0] + '/'
            
            # 宿主默认使用全局安全 Jar
            base['spider'] = GLOBAL_SAFE_JAR
            
            if 'wallpaper' in base and isinstance(base['wallpaper'], str) and base['wallpaper'].startswith('./'):
                base['wallpaper'] = urljoin(base_host, base['wallpaper'])
                
            return base
    
    return {
        "spider": GLOBAL_SAFE_JAR,
        "wallpaper": "https://api.kdcc.cn",
        "sites": [], "lives": [], "parses": [], "flags": []
    }

def fetch_external_candidates():
    print(f">>> [2/5] 全网搜刮...")
    all_urls = EXTERNAL_URLS.copy()
    candidates_sites = []
    
    def process_url(url):
        data = get_json(url)
        if not data: return []
        extracted = []
        if 'urls' in data and isinstance(data['urls'], list):
            for item in data['urls']:
                if 'url' in item:
                    sub_data = get_json(item['url'])
                    if sub_data and 'sites' in sub_data:
                        extracted.extend(sub_data['sites'])
        if 'sites' in data:
            extracted.extend(data['sites'])
        return extracted

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_url, url): url for url in all_urls}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: candidates_sites.extend(res)
            
    print(f"    [+] 搜集到 {len(candidates_sites)} 个接口")
    return candidates_sites

def validate_and_filter(sites):
    print(f">>> [3/5] 智能清洗 & 匹配Jar...")
    
    valid_sites = []
    seen_api = set()
    tasks = []
    
    for s in sites:
        name = s.get('name', '')
        api = s.get('api', '')
        stype = s.get('type', 0)
        
        if stype not in ALLOWED_TYPES: continue
        if any(bw in name for bw in BLACKLIST): continue
        if api in seen_api: continue
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): continue

        # 【核心步骤】处理 Jar 包
        s = process_site_jar(s)

        seen_api.add(api)
        tasks.append(s)

    def check(site):
        try:
            # 只要能通就行，不强求 JSON，因为有些 Type 3 是加密数据
            res = requests.get(site['api'], timeout=TIMEOUT, verify=False, proxies=PROXIES)
            if res.status_code == 200 and len(res.content) > 10:
                latency = int(res.elapsed.total_seconds() * 1000)
                site['_latency'] = latency
                site['name'] = clean_name(site['name'])
                
                # 开启搜索
                site['searchable'] = 1 
                site['quickSearch'] = 1
                
                # 标记：如果这个源有独立 Jar，给个特殊图标
                if 'jar' in site:
                    site['name'] = f"🧩 {site['name']}"
                else:
                    site['name'] = f"🚀 {site['name']}"
                    
                return site
        except: pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check, s) for s in tasks]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_sites.append(res)
            
    valid_sites.sort(key=lambda x: x['_latency'])
    for s in valid_sites: s.pop('_latency', None)
    
    print(f"    [√] 清洗完毕，剩余 {len(valid_sites)} 个有效源")
    return valid_sites

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox 智能多Jar版 v20.0")
        
        base_config = fetch_base_config_fail_safe()
        
        raw_external = fetch_external_candidates()
        verified_external = validate_and_filter(raw_external)
        
        print(f">>> [4/5] 融合配置...")
        host_sites = base_config.get('sites', [])
        
        safe_host_sites = []
        for s in host_sites:
            s['name'] = f"★ {clean_name(s['name'])}"
            s['searchable'] = 1
            # 宿主里的源也需要过一遍 Jar 检查，防止宿主自带毒
            s = process_site_jar(s)
            safe_host_sites.append(s)
            
        max_add = 100 # 增加到 100 个，因为现在有很多 Type 3 了
        if len(verified_external) > max_add:
            verified_external = verified_external[:max_add]
            
        final_sites = safe_host_sites + verified_external
        base_config['sites'] = final_sites
        
        print(f">>> [5/5] 保存...")
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(base_config, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 成功！")
        print(f"📊 总计源: {len(final_sites)} 个")
        print(f"🧩 独立Jar源: {len([s for s in final_sites if '🧩' in s['name']])} 个")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":"", "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
