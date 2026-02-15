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

# 【核心配置】
GITHUB_USER = "guru2016"
REPO_NAME = "tvbox-pro"
BRANCH_NAME = "main"

# 【全局唯一 Jar】
# 为了兼容性最好，建议使用 FongMi 或 Yoursmile 的全能 Jar
# 也可以用你自己仓库里的，前提是你仓库里的这个 Jar 足够全能
GLOBAL_SAFE_JAR = f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{REPO_NAME}@{BRANCH_NAME}/spider.jar"
# 备用推荐 (如果你的spider.jar不够强，可以用下面这个):
# GLOBAL_SAFE_JAR = "https://cdn.jsdelivr.net/gh/yoursmile66/TVBox@main/Yoursmile.jar"

# 【搜刮列表】(只管加，脚本会统一处理)
EXTERNAL_URLS = [
    # --- 宿主级大厂 ---
    "http://www.饭太硬.com/tv",       
    "http://肥猫.com",
    "http://fty.xxooo.cf/tv",
    "http://rihou.cc:88/荷城茶秀",
    
    # --- 需净化的资源 ---
    "http://cdn.qiaoji8.com/tvbox.json",
    "http://tvbox.王二小放牛娃.top",
    "http://tv.nxog.top/m/111.php?ou=公众号欧歌app&mz=all&jar=all&b=欧歌",
    
    # --- 优质散户 ---
    "https://api.hgyx.vip/hgyx.json",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",
    "https://android.lushunming.qzz.io/json/index.json",
    "http://home.jundie.top:81/top98.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://www.252035.xyz/z/FongMi.json",
    "http://52bsj.vip:81/api/v3/file/get/29899/bsj2023.json?sign=3c594b2b985b365bad",
    "http://ok321.top/tv",
    "https://tv.菜妮丝.top",
]

# 【过滤配置】
ALLOWED_TYPES = [0, 1, 3, 4] 
# 广告关键词拦截
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "弹幕", "更新", "公众号", "扫码", "微信", "企鹅", "APP", "下载", 
    "推广", "验证", "激活", "授权", "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播",
    "77.110", "mingming"
]

TIMEOUT = 6        
MAX_WORKERS = 60   

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

# ================= 3. 核心：强制剥离 Jar =================

def process_and_strip_jar(url):
    """
    抓取并剥离所有接口的 jar 字段
    """
    data = get_json(url)
    if not data: return []
    
    extracted_sites = []
    
    def process_site(site):
        # 【核心修改】
        # 无论它原来有没有 jar，无论它原来用谁的 jar
        # 统统删掉！让它强制继承我们 JSON 根目录下的 spider
        if 'jar' in site:
            del site['jar']
            
        # 顺便处理一下分类，如果是纯 CMS，保留
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

def fetch_all_sites_stripped():
    print(f">>> [1/4] 极速搜刮 & 剥离Jar...")
    if "guru2016" not in GLOBAL_SAFE_JAR:
        print("!!! 警告：GITHUB_USER 未配置！")
        
    all_sites = []
    unique_urls = list(set(EXTERNAL_URLS))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(process_and_strip_jar, url): url for url in unique_urls}
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
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): continue

        seen_api.add(api)
        tasks.append(s)

    def fast_check(site):
        try:
            # 极速检测：只读前 512 字节
            with requests.get(site['api'], timeout=TIMEOUT, stream=True, verify=False, proxies=PROXIES) as res:
                if res.status_code == 200:
                    chunk = next(res.iter_content(chunk_size=512), None)
                    if chunk:
                        latency = int(res.elapsed.total_seconds() * 1000)
                        site['_latency'] = latency
                        site['name'] = clean_name(site['name'])
                        
                        # 统一开启搜索
                        site['searchable'] = 1 
                        site['quickSearch'] = 1
                        
                        # 图标逻辑：现在只有两种
                        if site.get('type') == 3:
                            site['name'] = f"🛡️ {site['name']}" # Spider (使用全局Jar)
                        else:
                            site['name'] = f"🚀 {site['name']}" # CMS/App (无Jar)
                            
                        return site
        except: pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fast_check, s) for s in tasks]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_sites.append(res)
            
    valid_sites.sort(key=lambda x: x['_latency'])
    for s in valid_sites: s.pop('_latency', None)
    
    print(f"    [√] 存活接口: {len(valid_sites)} 个")
    return valid_sites

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox 单Jar极速稳定版 v25.0")
        
        # 1. 抓取并剥离
        raw_sites = fetch_all_sites_stripped()
        
        # 2. 清洗
        final_sites = validate_and_filter(raw_sites)
        
        # 3. 截断 (防止内存溢出)
        max_sites = 150
        if len(final_sites) > max_sites:
            final_sites = final_sites[:max_sites]
        
        # 4. 生成配置
        # 关键：根目录只有这一个 spider，sites 列表里没有任何 jar 字段
        # 电视盒子只会加载这一个 Jar，极其稳定
        config = {
            "spider": GLOBAL_SAFE_JAR,
            "wallpaper": "https://api.kdcc.cn",
            "sites": final_sites,
            "lives": [],
            "parses": [],
            "flags": []
        }
        
        print(f">>> [3/4] 保存配置...")
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 成功！已强制所有源使用统一Jar。")
        print(f"📊 最终源数: {len(final_sites)} 个")
        print(f"🛡️ 全局核心: {GLOBAL_SAFE_JAR}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":"", "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
