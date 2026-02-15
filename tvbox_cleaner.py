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

# 【全局配置】
GITHUB_USER = "guru2016"
REPO_NAME = "tvbox-pro"
BRANCH_NAME = "main"
# 全局保底 Jar (你的防毒盾牌)
GLOBAL_SAFE_JAR = f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{REPO_NAME}@{BRANCH_NAME}/spider.jar"

# 【核心：源与Jar的智能匹配表】
# 格式: "订阅地址": "该地址强制使用的Jar"
JAR_MAP = {
    # --- 信任的大厂：保留原配 (兼容性优先) ---
    "http://www.饭太硬.com/tv": "http://www.饭太硬.com/To/jar/3.jar",
    "http://肥猫.com": "http://肥猫.com/肥猫.jar",
    "http://fty.xxooo.cf/tv": "http://www.饭太硬.com/To/jar/3.jar",
    "http://rihou.cc:88/荷城茶秀": "http://rihou.cc:88/jar/荷城茶秀.jar",
    
    # --- ⚠ 需净化的大厂：强制使用你的纯净Jar (去广告优先) ---
    "http://cdn.qiaoji8.com/tvbox.json": GLOBAL_SAFE_JAR,
    "http://tvbox.王二小放牛娃.top": GLOBAL_SAFE_JAR,  # 经常变动，用纯净Jar更稳
}

# 【搜刮列表】(精选40+优质源)
EXTERNAL_URLS = list(JAR_MAP.keys()) + [
    # --- 稳定大厂 ---
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json", # 南风
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",     # 宝盒
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",       # 短剧
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",  # 动力
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",          # 道长
    
    # --- 优质单仓 ---
    "http://ok321.top/tv",
    "https://tv.菜妮丝.top",
    "https://api.hgyx.vip/hgyx.json",
    "https://android.lushunming.qzz.io/json/index.json",
    "http://home.jundie.top:81/top98.json",
    "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://www.252035.xyz/z/FongMi.json",
    "http://52bsj.vip:81/api/v3/file/get/29899/bsj2023.json?sign=3c594b2b985b365bad", # 运输车
    
    # --- 潜力新源 ---
    "https://s2.pub/x",
    "http://tv.nxog.top/m/111.php?ou=公众号欧歌app&mz=all&jar=all&b=欧歌",
    "https://100km.top/0",
    "https://tvbox.cainisi.cf",
    "http://meowtv.cn/tv",
    "https://weixine.net/ysc.json",
    "http://8.210.232.168/xc.json",
    "https://cdn.jsdelivr.net/gh/2hacc/TVBox@main/tvbox.json",
    "https://raw.githubusercontent.com/undCover/PyramidStore/main/pyramid.json",
    "http://dxawi.github.io/0/0.json",
    "https://raw.githubusercontent.com/chengxueli818913/maoTV/main/44.json",
    "https://agit.ai/Yoursmile7/TVBox/raw/branch/master/XC.json"
]

# 【过滤配置】
ALLOWED_TYPES = [0, 1, 3, 4] 
# 广告拦截关键词
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "弹幕", "更新", "公众号", "扫码", "微信", "企鹅", "APP", "下载", 
    "推广", "验证", "激活", "授权", "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播",
    "77.110", "mingming"
]

# 【性能配置】
TIMEOUT = 6        # 单个请求超时时间 (秒)
MAX_WORKERS = 60   # 极速并发数 (GitHub Actions 性能足够支持)

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
    """普通获取，用于拉取配置列表"""
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

# ================= 3. 核心：定向 Jar 注入 =================

def fetch_and_inject_jar(url):
    data = get_json(url)
    if not data: return []
    
    extracted_sites = []
    # 查找是否有预设的 Jar
    target_jar = JAR_MAP.get(url) 
    
    def process_site(site):
        # 只有 Type 3 需要 Jar
        if site.get('type') == 3:
            # 策略 A: 命中 JAR_MAP (如饭太硬或巧技)
            if target_jar:
                site['jar'] = target_jar # 强制使用我们指定的 (原配或纯净)
            
            # 策略 B: 散户源
            elif 'jar' in site:
                # 再次检查 Jar 是否包含毒瘤域名
                jar_url = str(site['jar'])
                if "qiaoji" in jar_url or "mingming" in jar_url:
                    site['jar'] = GLOBAL_SAFE_JAR # 杀毒
                else:
                    pass # 暂时信任原配
            else:
                site['jar'] = GLOBAL_SAFE_JAR # 无Jar则补全
        return site

    # 提取多仓
    if 'urls' in data and isinstance(data['urls'], list):
        for item in data['urls']:
            if 'url' in item:
                sub_data = get_json(item['url'])
                if sub_data and 'sites' in sub_data:
                    for s in sub_data['sites']:
                        extracted_sites.append(process_site(s))
    
    # 提取单仓
    if 'sites' in data:
        for s in data['sites']:
            extracted_sites.append(process_site(s))
            
    return extracted_sites

# ================= 4. 流程函数 =================

def fetch_all_sites_with_jars():
    print(f">>> [1/4] 极速搜刮 (并发: {MAX_WORKERS})...")
    if "guru2016" not in GLOBAL_SAFE_JAR:
        print("!!! 警告：GITHUB_USER 未配置！")
        
    all_sites = []
    # 使用 set 去重 URL，防止重复爬取
    unique_urls = list(set(EXTERNAL_URLS))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(fetch_and_inject_jar, url): url for url in unique_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            try:
                sites = future.result()
                if sites: all_sites.extend(sites)
            except: pass
            
    print(f"    [+] 原始接口数量: {len(all_sites)}")
    return all_sites

def validate_and_filter(sites):
    print(f">>> [2/4] 微创测速 & 深度清洗...")
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
        # 排除 emoji 广告
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): continue

        seen_api.add(api)
        tasks.append(s)

    # ⚡️ 极速检测函数 ⚡️
    def fast_check(site):
        try:
            # 关键优化：stream=True，只读前512字节
            # 只要能建立连接且返回少量数据，就视为存活，极大减少耗时
            with requests.get(site['api'], timeout=TIMEOUT, stream=True, verify=False, proxies=PROXIES) as res:
                if res.status_code == 200:
                    # 尝试读取一点点数据，确保不是空连接
                    chunk = next(res.iter_content(chunk_size=512), None)
                    if chunk:
                        latency = int(res.elapsed.total_seconds() * 1000)
                        site['_latency'] = latency
                        site['name'] = clean_name(site['name'])
                        site['searchable'] = 1 
                        site['quickSearch'] = 1
                        
                        # 图标逻辑
                        site_jar = site.get('jar', '')
                        if site_jar == GLOBAL_SAFE_JAR:
                            site['name'] = f"🛡️ {site['name']}" # 净化过的
                        elif site_jar:
                            site['name'] = f"🧩 {site['name']}" # 原配Jar
                        else:
                            site['name'] = f"🚀 {site['name']}" # CMS/App
                            
                        return site
        except: pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fast_check, s) for s in tasks]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_sites.append(res)
            
    # 排序
    valid_sites.sort(key=lambda x: x['_latency'])
    for s in valid_sites: s.pop('_latency', None)
    
    print(f"    [√] 存活接口: {len(valid_sites)} 个")
    return valid_sites

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox 极速万源版 v24.0")
        
        raw_sites = fetch_all_sites_with_jars()
        final_sites = validate_and_filter(raw_sites)
        
        # 数量限制放宽到 200，因为我们现在有足够多的好源
        max_sites = 200
        if len(final_sites) > max_sites:
            final_sites = final_sites[:max_sites]
        
        config = {
            "spider": GLOBAL_SAFE_JAR,
            "wallpaper": "https://api.kdcc.cn",
            "sites": final_sites,
            "lives": [],
            "parses": [],
            "flags": []
        }
        
        print(f">>> [3/4] 生成配置...")
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 完成！")
        print(f"📊 最终收录: {len(final_sites)} 个")
        print(f"🛡️ 净化源(巧技等): {len([s for s in final_sites if '🛡️' in s['name']])} 个")
        print(f"🧩 原配源(饭/肥等): {len([s for s in final_sites if '🧩' in s['name']])} 个")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":"", "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
