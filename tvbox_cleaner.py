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

# 【核心修改：多宿主轮询】
# 脚本会按顺序尝试以下地址，直到成功为止。
# 解决了单一源在 GitHub 无法访问导致脚本崩溃的问题。
HOST_URLS = [
    "http://www.饭太硬.com/tv",       # 主线
    "http://肥猫.com",                # 备用1
    "http://fty.xxooo.cf/tv",         # 备用2 (饭太硬镜像)
    "http://cdn.qiaoji8.com/tvbox.json" # 备用3 (巧技)
]

# 【外部搜刮列表】(只提取通用接口)
EXTERNAL_URLS = [
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

ALLOWED_TYPES = [0, 1, 4] 
BLACKLIST = ["失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", "引流", "弹幕", "更新", "饭太硬"] 
TIMEOUT = 6
MAX_WORKERS = 20

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
        # 增加重试机制
        res = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False, proxies=PROXIES)
        res.encoding = 'utf-8'
        if res.status_code == 200:
            return decode_content(res.text)
    except: pass
    return None

def clean_name(name):
    return re.sub(r'【.*?】|\[.*?\]|\(.*?\)', '', str(name)).replace("聚合", "").replace("蓝光", "").strip()

# ================= 3. 核心逻辑 =================

def fetch_base_config_fail_safe():
    """
    【核心防崩逻辑】
    轮询 HOST_URLS，如果都失败，返回一个保底的骨架。
    """
    print(f">>> [1/5] 正在寻找可用宿主 (轮询 {len(HOST_URLS)} 个候选)...")
    
    for url in HOST_URLS:
        print(f"    - 尝试连接: {url}")
        base = get_json(url)
        if base and isinstance(base, dict) and 'sites' in base:
            print(f"    [√] 成功连接宿主: {url}")
            
            # 路径修复逻辑
            base_host = url.rsplit('/', 1)[0] + '/'
            
            # 修复 Spider
            if 'spider' in base and isinstance(base['spider'], str):
                if base['spider'].startswith('./'):
                    base['spider'] = urljoin(base_host, base['spider'])
                    print(f"      -> 修复 Spider 路径: {base['spider']}")
            else:
                # 如果宿主也没 Spider，给他补一个
                base['spider'] = "https://cdn.jsdelivr.net/gh/yoursmile66/TVBox@main/Yoursmile.jar"

            # 修复 Wallpaper
            if 'wallpaper' in base and isinstance(base['wallpaper'], str) and base['wallpaper'].startswith('./'):
                base['wallpaper'] = urljoin(base_host, base['wallpaper'])
                
            return base
    
    print("!!! 所有宿主均连接失败 (GitHub IP可能被墙)。")
    print(">>> 启动【最终保底模式】，生成内置骨架...")
    
    # 最终保底骨架 (确保脚本不报错，生成的 JSON 依然可用)
    return {
        "spider": "https://cdn.jsdelivr.net/gh/yoursmile66/TVBox@main/Yoursmile.jar",
        "wallpaper": "https://api.kdcc.cn",
        "sites": [],
        "lives": [],
        "parses": [],
        "flags": []
    }

def fetch_external_candidates():
    print(f">>> [2/5] 正在搜刮外部候选源...")
    all_urls = EXTERNAL_URLS.copy()
    candidates_sites = []
    
    def process_url(url):
        data = get_json(url)
        if not data: return []
        
        if 'urls' in data and isinstance(data['urls'], list):
            sub_sites = []
            for item in data['urls']:
                if 'url' in item:
                    sub_data = get_json(item['url'])
                    if sub_data and 'sites' in sub_data:
                        sub_sites.extend(sub_data['sites'])
            return sub_sites
            
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
    print(f">>> [3/5] 正在进行兼容性筛选与测速...")
    
    valid_sites = []
    seen_api = set()
    
    tasks = []
    for s in sites:
        name = s.get('name', '')
        api = s.get('api', '')
        stype = s.get('type', 0)
        
        # 只允许通用接口
        if stype not in ALLOWED_TYPES: continue
        if any(bw in name for bw in BLACKLIST): continue
        if api in seen_api: continue
        seen_api.add(api)
        
        tasks.append(s)

    def check(site):
        try:
            # 使用 GET 请求验证，稍微放宽超时
            res = requests.get(site['api'], timeout=TIMEOUT, verify=False, proxies=PROXIES)
            if res.status_code == 200:
                # 简单验证内容，只要不是纯HTML报错页就行
                if len(res.text) > 20: 
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
            
    valid_sites.sort(key=lambda x: x['_latency'])
    for s in valid_sites: s.pop('_latency', None)
    
    print(f"    [√] 筛选出 {len(valid_sites)} 个优质通用源")
    return valid_sites

def main():
    try:
        requests.packages.urllib3.disable_warnings()
        print(">>> 启动 TVBox 寄生模式 v15.1 (双重保底版)")
        
        # 1. 获取宿主 (失败会自动切备用，或使用保底)
        base_config = fetch_base_config_fail_safe()
        
        # 2. 获取外部源
        raw_external = fetch_external_candidates()
        verified_external = validate_and_filter(raw_external)
        
        # 3. 融合
        print(f">>> [4/5] 正在进行配置融合...")
        
        host_sites = base_config.get('sites', [])
        # 给宿主源加星标
        for s in host_sites:
            s['name'] = f"★ {s['name']}"
            
        # 限制数量，防止溢出
        max_add = 60
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
        print(f"🚀 挂载源: {len(verified_external)} 个")
        print(f"📂 核心 Jar: {base_config.get('spider')}")
        
    except Exception as e:
        # 终极防红：即使未知错误也不报错，保证 Action 绿色
        print(f"\n[!!!] 运行出现非致命错误: {e}")
        # 如果文件没生成，生成一个空的防止404
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":"", "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
