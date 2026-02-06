import requests
import json
import base64
import re
import concurrent.futures
import os
import time
from urllib.parse import quote, urlparse

# ================= 1. 配置区域 =================

# 【Token 设置】本地运行可填，GitHub Actions 留空
MY_GITHUB_TOKEN = "" 

# 【代理设置】Mac 本地建议填 None 或具体的 Clash 地址
PROXIES = None 
# PROXIES = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

# 【源列表】包含单仓和多仓，脚本会自动识别处理
SOURCE_URLS = [
    # --- 单仓 ---
    "http://www.饭太硬.com/tv",
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
    
    # --- 多仓 (脚本会自动展开) ---
    "https://www.iyouhun.com/tv/dc",
    "https://www.iyouhun.com/tv/yh",
    "https://9877.kstore.space/AnotherDS/api.json",
    "http://xhztv.top/dc/",
    "http://xhztv.top/DC.txt",
    "https://bitbucket.org/xduo/cool/raw/main/room.json",
    "https://qixing.myhkw.com/DC.txt",
    "http://xmbjm.fh4u.org/dc.txt"
]

# 优化配置
ENABLE_GITHUB_SEARCH = True   # 开启自动搜寻
MAX_GITHUB_RESULTS = 5
TIMEOUT = 4                   # 适度放宽超时，保证抓取率
BLACKLIST = ["失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人"]

# ================= 2. 基础工具函数 =================

def decode_content(content):
    """解密 TVBox 各种奇葩格式"""
    if not content: return None
    content = content.strip()
    try:
        return json.loads(content)
    except:
        pass
    try:
        # 简单处理干扰字符和Base64
        clean_content = content.replace('**', '').replace('o', '').strip() if content.startswith('**') else content
        decoded = base64.b64decode(clean_content).decode('utf-8')
        return json.loads(decoded)
    except:
        pass
    try:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    return None

def get_json(url):
    """带重试的网络请求"""
    safe_url = quote(url, safe=':/?&=')
    headers = {"User-Agent": "Mozilla/5.0", "Referer": safe_url}
    try:
        res = requests.get(url, headers=headers, timeout=6, verify=False, proxies=PROXIES)
        res.encoding = 'utf-8'
        if res.status_code == 200:
            return decode_content(res.text)
    except:
        pass
    return None

def fetch_github_sources():
    """GitHub 自动搜寻"""
    print(">>> [1/5] 正在连接 GitHub 探索新源...")
    token = os.getenv("GH_TOKEN") or MY_GITHUB_TOKEN
    
    if "ghp_" not in token:
        print("    [!] 未配置有效 Token，跳过 GitHub 搜索。")
        return []
        
    urls = []
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    api = "https://api.github.com/search/code?q=filename:json+spider+sites+tvbox&sort=indexed&order=desc"
    
    try:
        r = requests.get(api, headers=headers, timeout=10, verify=False, proxies=PROXIES)
        if r.status_code == 200:
            items = r.json().get('items', [])
            print(f"    [+] GitHub 发现 {len(items)} 个潜在源文件")
            for item in items[:MAX_GITHUB_RESULTS]:
                raw = item.get('html_url', '').replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
                if raw: urls.append(raw)
    except Exception as e:
        print(f"    [!] GitHub 搜索出错: {e}")
    return urls

# ================= 3. 核心逻辑：多仓展开与融合 =================

def clean_name(name):
    """名称清洗"""
    name = re.sub(r'【.*?】|\[.*?\]|\(.*?\)', '', name)
    name = name.replace("聚合", "").replace("蓝光", "").replace("专线", "").replace("API", "").strip()
    return name if name else "未命名接口"

def expand_multirepo(urls):
    """【新功能】递归展开多仓列表"""
    print(f"\n>>> [2/5] 正在解析 {len(urls)} 个初始地址 (智能识别单仓/多仓)...")
    
    final_single_repos = []
    
    def check_url(url):
        data = get_json(url)
        if not data: return None
        
        # 情况A: 是多仓 (包含 urls 列表)
        if 'urls' in data and isinstance(data['urls'], list):
            print(f"    [+] 发现多仓: {url} -> 包含 {len(data['urls'])} 个子源")
            sub_urls = []
            for item in data['urls']:
                if isinstance(item, dict) and 'url' in item:
                    sub_urls.append(item['url'])
            return ("MULTI", sub_urls)
            
        # 情况B: 是单仓 (包含 sites 列表)
        elif 'sites' in data:
            # print(f"    [.] 确认单仓: {url}")
            return ("SINGLE", url)
            
        return None

    # 并发预检查
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(check_url, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            res = future.result()
            if res:
                rtype, content = res
                if rtype == "SINGLE":
                    final_single_repos.append(content)
                elif rtype == "MULTI":
                    # 将多仓里的子链接直接加入待处理列表
                    final_single_repos.extend(content)

    # 去重
    final_single_repos = list(set(final_single_repos))
    print(f"    -> 最终解析出 {len(final_single_repos)} 个有效的单仓配置地址。")
    return final_single_repos

def test_site_latency(site):
    """测速 + 验证"""
    name = site.get('name', '')
    api = site.get('api', '')
    
    for kw in BLACKLIST:
        if kw in name: return None
        
    # 只取通用 CMS (0/1) 和 APP (4)
    if site.get('type') not in [0, 1, 4]:
        return None

    headers = {"User-Agent": "Mozilla/5.0"}
    start_time = time.time()
    
    try:
        r = requests.get(api, headers=headers, timeout=TIMEOUT, stream=True, verify=False, proxies=PROXIES)
        if r.status_code < 400:
            latency = (time.time() - start_time) * 1000
            site['_latency'] = int(latency)
            site['name'] = clean_name(name)
            
            if latency < 800: site['name'] = f"🚀 {site['name']}"
            elif latency < 1500: site['name'] = f"🟢 {site['name']}"
            else: site['name'] = f"🟡 {site['name']}"
            
            # print(f"    [√] {int(latency)}ms | {site['name']}")
            return site
    except:
        pass
    return None

def main():
    requests.packages.urllib3.disable_warnings()
    print(">>> 启动 TVBox 全网融合脚本 v6.0 (多仓版)")
    
    # 1. 准备初始列表
    initial_urls = SOURCE_URLS.copy()
    if ENABLE_GITHUB_SEARCH:
        initial_urls.extend(fetch_github_sources())
        
    # 2. 展开多仓，获取所有单仓地址
    all_config_urls = expand_multirepo(initial_urls)
    
    # 3. 扫描提取接口
    print(f"\n>>> [3/5] 正在深度扫描 {len(all_config_urls)} 个配置...")
    
    skeleton_config = None
    raw_sites = []
    
    # 这里不需要太高并发，以免被源站封IP
    for i, url in enumerate(all_config_urls):
        # 简单的进度显示
        # print(f"    处理 ({i+1}/{len(all_config_urls)}): {url}")
        data = get_json(url)
        if not data: continue
        
        # 抓取骨架 (优先找带 jar 的)
        if not skeleton_config and data.get('spider'):
            skeleton_config = {
                "spider": data.get('spider'),
                "wallpaper": data.get('wallpaper'),
                "lives": data.get('lives', []), 
                "parses": data.get('parses', []),
                "flags": data.get('flags', [])
            }
            # 保留主源的 Spider 接口
            for s in data.get('sites', []):
                if s.get('type') == 3:
                    s['name'] = f"★ {clean_name(s['name'])}"
                    s['_latency'] = 0
                    raw_sites.append(s)

        # 提取 CMS 接口
        for s in data.get('sites', []):
            if s.get('type') in [0, 1, 4]:
                raw_sites.append(s)

    if not skeleton_config:
        print("\n[!!!] 悲剧：所有源里都没找到一个可用的 Spider/Jar，无法生成有效配置。")
        # 紧急保底（防止空文件）：随便造一个骨架
        skeleton_config = {"spider": "", "sites": [], "lives": []}

    # 4. 去重与测速
    print(f"\n>>> [4/5] 正在竞速清洗 (原始接口: {len(raw_sites)} 个)...")
    
    unique_sites = {}
    tasks = []
    
    for s in raw_sites:
        api = s.get('api')
        if api:
            if s.get('type') == 3:
                unique_sites[api] = s # Spider接口直接保留
            elif api not in unique_sites: # 避免重复测同一个API
                tasks.append(s) 

    valid_sites = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor: # 提高并发加速测速
        futures = [executor.submit(test_site_latency, site) for site in tasks]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                if res['api'] not in unique_sites:
                    unique_sites[res['api']] = res
                    valid_sites.append(res)

    # 5. 排序与输出
    print(f"\n>>> [5/5] 正在生成最终列表...")
    
    vip_sites = [s for s in unique_sites.values() if s.get('_latency') == 0]
    common_sites = sorted(valid_sites, key=lambda x: x['_latency']) # 按延迟排序
    
    final_sites = vip_sites + common_sites
    
    # 清理内部字段
    for s in final_sites:
        s.pop('_latency', None)

    skeleton_config['sites'] = final_sites
    
    with open("my_tvbox.json", 'w', encoding='utf-8') as f:
        json.dump(skeleton_config, f, ensure_ascii=False, indent=2)

    print(f"\n" + "="*40)
    print(f"✅ 全网融合完成！")
    print(f"📊 统计：")
    print(f"   - 初始地址数: {len(initial_urls)}")
    print(f"   - 解析单仓数: {len(all_config_urls)} (含自动裂变)")
    print(f"   - 原始接口池: {len(raw_sites)}")
    print(f"   - 最终有效源: {len(final_sites)}")
    print(f"   - 🚀 极速源:   {len([s for s in valid_sites if '🚀' in s['name']])} 个")
    print(f"📂 文件路径: {os.path.abspath('my_tvbox.json')}")
    print(f"="*40)

if __name__ == "__main__":
    main()