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

# 【核心安全锁】
# 强制使用你自己的纯净 Jar，这是杜绝广告的根本
GITHUB_USER = "guru2016"
REPO_NAME = "tvbox-pro"
BRANCH_NAME = "main"
SAFE_JAR_URL = f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{REPO_NAME}@{BRANCH_NAME}/spider.jar"

# 【宿主配置】(只用饭太硬做骨架，最稳)
HOST_URLS = [
    "http://www.饭太硬.com/tv",       
    "http://肥猫.com",
    "http://fty.xxooo.cf/tv"
]

# 【搜刮列表】(这里放你想“吸”的源，包括巧技)
EXTERNAL_URLS = [
    # --- 重点吸血对象 ---
    "http://cdn.qiaoji8.com/tvbox.json",  # 巧技 (只吸通用接口)
    "http://tv.nxog.top/m/111.php?ou=公众号欧歌app&mz=all&jar=all&b=欧歌", # 欧歌
    "https://api.hgyx.vip/hgyx.json",     # 韩国佬
    "https://tv.菜妮丝.top",              # 菜妮丝
    
    # --- 新增优质大厂 ---
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json", # 道长
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json", # 南风
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json", # 宝盒
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",   # 短剧
    "http://tvbox.王二小放牛娃.top",
    "http://ok321.top/tv",
    "http://52bsj.vip:81/api/v3/file/get/29899/bsj2023.json?sign=3c594b2b985b365bad", # 运输车
    
    # --- 备用池 ---
    "https://www.252035.xyz/z/FongMi.json",
    "http://www.meowtv.vip/tvbox.json",
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",
    "https://android.lushunming.qzz.io/json/index.json"
]

# 【过滤配置】(严防死守)
# 只允许 0(xml), 1(json), 4(app/parse)
# 绝对不要 3(spider)，因为我们不用他们的Jar
ALLOWED_TYPES = [0, 1, 4] 

# 【杀毒黑名单】
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "弹幕", "更新", "饭太硬", "公众号", "扫码", "微信", "企鹅", "APP", "下载", 
    "蓝光", "互助", "推广", "验证", "激活", "授权", "雷鲸", "小脑斧", "玩偶", "助手", 
    "专线", "剧白白", "剧荒", "腾云", "彩蛋", "神马", "悦享"
]

TIMEOUT = 5
MAX_WORKERS = 15

# ================= 2. 工具函数 =================

def decode_content(content):
    if not content: return None
    try:
        return json.loads(content)
    except:
        pass
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

# ================= 3. 核心逻辑 =================

def fetch_base_config_fail_safe():
    print(f">>> [1/5] 正在连接宿主 (饭太硬/肥猫)...")
    
    # 检查用户是否配置了 GITHUB_USER
    if "guru2016" not in SAFE_JAR_URL:
        print("!!! 警告：请在脚本头部填写正确的 GITHUB_USER，否则 Jar 包无法加载！")

    for url in HOST_URLS:
        print(f"    - 尝试: {url}")
        base = get_json(url)
        if base and isinstance(base, dict) and 'sites' in base:
            print(f"    [√] 成功锁定宿主: {url}")
            base_host = url.rsplit('/', 1)[0] + '/'
            
            # 【核心策略】强制覆盖 Jar，不论宿主是谁
            print(f"    [🛡️] 注入纯净防毒 Jar: {SAFE_JAR_URL}")
            base['spider'] = SAFE_JAR_URL

            if 'wallpaper' in base and isinstance(base['wallpaper'], str) and base['wallpaper'].startswith('./'):
                base['wallpaper'] = urljoin(base_host, base['wallpaper'])
                
            return base
    
    print("!!! 宿主连接全部失败，启用本地保底骨架。")
    return {
        "spider": SAFE_JAR_URL,
        "wallpaper": "https://api.kdcc.cn",
        "sites": [], "lives": [], "parses": [], "flags": []
    }

def fetch_external_candidates():
    print(f">>> [2/5] 正在全网收割优质接口...")
    all_urls = EXTERNAL_URLS.copy()
    candidates_sites = []
    
    def process_url(url):
        data = get_json(url)
        if not data: return []
        
        extracted = []
        # 提取多仓
        if 'urls' in data and isinstance(data['urls'], list):
            for item in data['urls']:
                if 'url' in item:
                    sub_data = get_json(item['url'])
                    if sub_data and 'sites' in sub_data:
                        extracted.extend(sub_data['sites'])
        # 提取单仓
        if 'sites' in data:
            extracted.extend(data['sites'])
            
        return extracted

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_url, url): url for url in all_urls}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: candidates_sites.extend(res)
            
    print(f"    [+] 共收集到 {len(candidates_sites)} 个潜在接口")
    return candidates_sites

def validate_and_filter(sites):
    print(f">>> [3/5] 正在进行 安全清洗 & 深度测速...")
    
    valid_sites = []
    seen_api = set()
    tasks = []
    
    for s in sites:
        name = s.get('name', '')
        api = s.get('api', '')
        stype = s.get('type', 0)
        
        # 1. 【核心过滤】坚决不要 Type 3 (Spider)
        # 这是防止巧技等源弹窗、闪退的根本！
        if stype not in ALLOWED_TYPES: continue
        
        # 2. 去重
        if api in seen_api: continue
        
        # 3. 关键词黑名单
        if any(bw in name for bw in BLACKLIST): continue
        
        # 4. 排除 emoji 广告 (名字太花哨的一般都是广)
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']):
            continue

        seen_api.add(api)
        tasks.append(s)

    # 深度测速
    def check(site):
        try:
            # 必须是真实的 JSON 接口，不能是网页
            res = requests.get(site['api'], timeout=TIMEOUT, verify=False, proxies=PROXIES)
            if res.status_code == 200:
                # 简单验证内容，防止空壳
                content = res.text.strip()
                if content.startswith('{') or content.startswith('['):
                    # 只要能通，且是JSON，就认为是好源
                    latency = int(res.elapsed.total_seconds() * 1000)
                    site['_latency'] = latency
                    site['name'] = f"🚀 {clean_name(site['name'])}"
                    return site
        except: pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check, s) for s in tasks]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_sites.append(res)
            
    # 按速度排序，越快越前
    valid_sites.sort(key=lambda x: x['_latency'])
    for s in valid_sites: s.pop('_latency', None)
    
    print(f"    [√] 清洗完毕，剩余 {len(valid_sites)} 个纯净通用源")
    return valid_sites

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox 吸星大法 v18.0")
        
        # 1. 搞定宿主 (带防毒Jar)
        base_config = fetch_base_config_fail_safe()
        
        # 2. 全网收割
        raw_external = fetch_external_candidates()
        verified_external = validate_and_filter(raw_external)
        
        print(f">>> [4/5] 融合配置...")
        host_sites = base_config.get('sites', [])
        
        # 处理宿主源名字
        # 注意：宿主(饭太硬)里的 Type 3 源可以保留，因为我们的纯净 Jar 大概率兼容他的源
        # 但如果发现宿主里的源也有弹窗，可以在这里加逻辑过滤
        safe_host_sites = []
        for s in host_sites:
            s['name'] = f"★ {clean_name(s['name'])}"
            safe_host_sites.append(s)
            
        # 拼接：宿主在前，收割的极速源在后
        # 限制外部源数量，防止列表太长
        max_add = 60 
        if len(verified_external) > max_add:
            verified_external = verified_external[:max_add]
            
        final_sites = safe_host_sites + verified_external
        base_config['sites'] = final_sites
        
        print(f">>> [5/5] 保存...")
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(base_config, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 运行成功！")
        print(f"📊 宿主源: {len(safe_host_sites)} 个")
        print(f"🚀 收割源: {len(verified_external)} 个 (已剔除毒Jar)")
        print(f"🛡️ 当前防御塔(Jar): {base_config['spider']}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":"", "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
