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

# 【宿主配置】
# 我们以这个源为基础，只往里面添加东西，不改动它原有的核心
BASE_URL = "http://www.饭太硬.com/tv"
BASE_HOST = "http://www.饭太硬.com/"

# 【搜刮列表】(只从中提取通用 CMS/APP 接口)
EXTERNAL_URLS = [
    "http://肥猫.com",
    "http://fty.xxooo.cf/tv",
    "https://毒盒.com/tv/",
    "http://我不是.摸鱼儿.com",
    "http://ok321.top/tv",
    "http://ok321.top/ok",
    "http://tvbox.王二小放牛娃.top",
    "https://www.yingm.cc/dm/dm.json",
    "http://home.jundie.top:81/top98.json",
    "http://cdn.qiaoji8.com/tvbox.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    "https://gitee.com/free-kingdom/dc/raw/main/T4.json",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://tv.菜妮丝.top",
    "https://api.hgyx.vip/hgyx.json",
    "https://dxawi.github.io/0/0.json",
    "http://www.mitvbox.xyz/小米/DEMO.json",
    "http://xhztv.top/xhz",
    "http://xhztv.top/4k.json",
    "https://9877.kstore.space/AnotherD/api.json",
    "https://raw.githubusercontent.com/xyq254245/xyqonlinerule/main/XYQTVBox.json",
    "https://bitbucket.org/xduo/duoapi/raw/master/xpg.json",
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",
    "http://tv.nxog.top/m/111.php?ou=公众号欧歌app&mz=all&jar=all&b=欧歌",
    "https://哪吒.live/",
    "https://www.252035.xyz/z/FongMi.json",
    "http://www.meowtv.vip/tvbox.json",
    "http://fmys.top/fmys.json",
    "https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://gitee.com/yiwu369/6758/raw/master/%E9%9D%92%E9%BE%99/1.json",
    "https://raw.githubusercontent.com/maoystv/6/main/000.json",
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",
    "https://cnb.cool/aooooowuuuuu/FreeSpider/-/git/raw/main/config",
    "https://android.lushunming.qzz.io/json/index.json",
    "https://www.iyouhun.com/tv/dc",
    "https://www.iyouhun.com/tv/yh",
    "https://9877.kstore.space/AnotherDS/api.json",
    "http://xhztv.top/dc/",
    "http://xhztv.top/DC.txt",
    "https://bitbucket.org/xduo/cool/raw/main/room.json",
    "https://qixing.myhkw.com/DC.txt",
    "http://xmbjm.fh4u.org/dc.txt"
]

# 【过滤配置】
# 严禁引入 Spider(Type 3)，因为会和饭太硬的 Jar 冲突导致闪退
ALLOWED_TYPES = [0, 1, 4] 
BLACKLIST = ["失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", "引流", "弹幕", "更新", "饭太硬"] # 饭太硬自己不用重复加
TIMEOUT = 5
MAX_WORKERS = 20

# ================= 2. 工具函数 =================

def decode_content(content):
    if not content: return None
    try:
        return json.loads(content)
    except:
        pass
    try:
        # 处理简单的 Base64 或 干扰字符
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
        res = requests.get(url, headers=headers, timeout=8, verify=False, proxies=PROXIES)
        res.encoding = 'utf-8'
        if res.status_code == 200:
            return decode_content(res.text)
    except: pass
    return None

def clean_name(name):
    return re.sub(r'【.*?】|\[.*?\]|\(.*?\)', '', str(name)).replace("聚合", "").replace("蓝光", "").strip()

# ================= 3. 核心逻辑 =================

def fetch_base_config():
    """获取饭太硬原始配置，并修复路径"""
    print(f">>> [1/5] 正在拉取宿主配置 (饭太硬): {BASE_URL} ...")
    base = get_json(BASE_URL)
    if not base:
        print("!!! 无法获取饭太硬配置，脚本终止。")
        sys.exit(1)
    
    # 修复 Spider Jar 路径 (转为绝对路径)
    if 'spider' in base:
        spider = base['spider']
        if spider.startswith('./'):
            base['spider'] = urljoin(BASE_HOST, spider)
            print(f"    [√] 修复 Jar 路径: {base['spider']}")
    
    # 修复 Wallpaper 路径
    if 'wallpaper' in base:
        wp = base['wallpaper']
        if wp.startswith('./'):
            base['wallpaper'] = urljoin(BASE_HOST, wp)

    return base

def fetch_external_candidates():
    """获取外部所有源列表"""
    print(f">>> [2/5] 正在搜刮外部候选源...")
    all_urls = EXTERNAL_URLS.copy()
    
    # 简单的官网抓取
    try:
        res = requests.get(BASE_HOST, timeout=10, verify=False, proxies=PROXIES)
        matches = re.findall(r'(https?://[^\s"<>]+)', res.text)
        for u in matches:
            if '.json' in u and u not in all_urls: all_urls.append(u)
    except: pass

    # 展开多仓
    candidates_sites = []
    
    def process_url(url):
        data = get_json(url)
        if not data: return []
        
        # 如果是多仓，提取子链接
        if 'urls' in data and isinstance(data['urls'], list):
            sub_sites = []
            for item in data['urls']:
                if 'url' in item:
                    sub_data = get_json(item['url'])
                    if sub_data and 'sites' in sub_data:
                        sub_sites.extend(sub_data['sites'])
            return sub_sites
            
        # 如果是单仓，提取 sites
        if 'sites' in data:
            return data['sites']
        return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_url, url): url for url in all_urls}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: candidates_sites.extend(res)
            
    print(f"    [+] 搜集到 {len(candidates_sites)} 个潜在接口")
    return candidates_sites

def validate_and_filter(sites):
    """筛选：只留通用接口，且必须能连通"""
    print(f">>> [3/5] 正在进行兼容性筛选与测速...")
    
    valid_sites = []
    seen_api = set()
    
    # 预处理：先去重，且只保留 Type 0/1/4
    tasks = []
    for s in sites:
        name = s.get('name', '')
        api = s.get('api', '')
        stype = s.get('type', 0)
        
        # 1. 类型过滤 (拒绝 Type 3 Spider，防止冲突)
        if stype not in ALLOWED_TYPES: continue
        
        # 2. 关键词过滤
        if any(bw in name for bw in BLACKLIST): continue
        
        # 3. 去重
        if api in seen_api: continue
        seen_api.add(api)
        
        tasks.append(s)

    # 并发测速
    def check(site):
        try:
            # 深度检测：尝试获取 JSON
            res = requests.get(site['api'], timeout=TIMEOUT, verify=False, proxies=PROXIES)
            if res.status_code == 200:
                # 简单验证是否为有效 JSON (防止 HTML 伪装)
                if res.text.strip().startswith('{') or res.text.strip().startswith('['):
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
            
    # 按速度排序
    valid_sites.sort(key=lambda x: x['_latency'])
    # 清理临时字段
    for s in valid_sites: s.pop('_latency', None)
    
    print(f"    [√] 筛选出 {len(valid_sites)} 个优质通用源")
    return valid_sites

def main():
    requests.packages.urllib3.disable_warnings()
    print(">>> 启动 TVBox 寄生模式优化脚本 v15.0")
    
    # 1. 获取宿主 (饭太硬)
    base_config = fetch_base_config()
    
    # 2. 获取并清洗外部源
    raw_external = fetch_external_candidates()
    verified_external = validate_and_filter(raw_external)
    
    # 3. 融合 (Grafting)
    print(f">>> [4/5] 正在进行配置融合...")
    
    # 保留宿主原本的所有 site，但给它们加上标记
    host_sites = base_config.get('sites', [])
    for s in host_sites:
        # 给饭太硬原版加个星星，排在最前
        if "饭太硬" not in s['name']:
            s['name'] = f"★ {s['name']}"
            
    # 将外部优质源追加到后面
    # 截取前 50 个最快的外部源，防止列表过长导致内存溢出
    max_add = 50
    if len(verified_external) > max_add:
        verified_external = verified_external[:max_add]
        
    final_sites = host_sites + verified_external
    base_config['sites'] = final_sites
    
    # 4. 保存
    print(f">>> [5/5] 保存配置...")
    with open("my_tvbox.json", 'w', encoding='utf-8') as f:
        json.dump(base_config, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ 成功！")
    print(f"📊 宿主源: {len(host_sites)} 个")
    print(f"🚀 挂载源: {len(verified_external)} 个 (已剔除不兼容的Jar源)")
    print(f"📂 核心 Jar: {base_config.get('spider')}")

if __name__ == "__main__":
    main()
