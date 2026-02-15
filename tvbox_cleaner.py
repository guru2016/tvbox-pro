import requests
import json
import re
import concurrent.futures
import os
import sys
import base64
from urllib.parse import quote, urljoin

# ================= 1. 配置区域 =================

# 【核心主源：饭太硬镜像站】
# 脚本会优先读取这个地址，提取它的 Spider(Jar) 和 Wallpaper 作为全局标准
PRIME_SOURCE = "https://fty.xxooo.cf/tv"

# 【备用默认值】
# 万一主源连不上，使用这些兜底（均为非 jsdelivr 地址）
DEFAULT_JAR = "http://www.饭太硬.com/To/jar/3.jar"
DEFAULT_WALLPAPER = "https://api.kdcc.cn"

# 【搜刮列表】
# 包含主源 + 其他优质大厂 (脚本会自动去重和清洗)
EXTERNAL_URLS = [
    PRIME_SOURCE, # 必须放在第一个
    
    # --- 优质大厂 ---
    "http://www.饭太硬.com/tv",
    "http://肥猫.com",
    "http://rihou.cc:88/荷城茶秀",
    "https://api.hgyx.vip/hgyx.json",
    "https://tv.菜妮丝.top",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://www.252035.xyz/z/FongMi.json",
    "http://52bsj.vip:81/api/v3/file/get/29899/bsj2023.json?sign=3c594b2b985b365bad",
    
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

# 【静态过滤配置】
ALLOWED_TYPES = [0, 1, 3, 4] 
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色", 
    "引流", "弹幕", "更新", "公众号", "扫码", "微信", "企鹅", "APP", "下载", 
    "推广", "验证", "激活", "授权", "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播",
    "77.110", "mingming", "摸鱼" 
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
        # verify=False 解决部分 HTTPS 证书问题
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

def fetch_prime_config():
    """优先抓取主源，提取全局 Spider 和 Wallpaper"""
    print(f">>> [1/4] 正在解析主源: {PRIME_SOURCE}")
    data = get_json(PRIME_SOURCE)
    
    global_jar = DEFAULT_JAR
    global_wp = DEFAULT_WALLPAPER
    
    if data:
        # 提取 Jar
        if 'spider' in data:
            candidate = data['spider']
            # 如果是相对路径，转换为绝对路径
            if candidate.startswith('./'):
                base_host = PRIME_SOURCE.rsplit('/', 1)[0] + '/'
                global_jar = urljoin(base_host, candidate)
            elif candidate.startswith('http'):
                global_jar = candidate
                
        # 提取 Wallpaper
        if 'wallpaper' in data:
            candidate = data['wallpaper']
            if candidate.startswith('http'):
                global_wp = candidate
                
        print(f"    [√] 成功提取核心 Jar: {global_jar}")
    else:
        print(f"    [!] 主源连接失败，使用默认 Jar: {global_jar}")
        
    return global_jar, global_wp

def fetch_and_process(url):
    data = get_json(url)
    if not data: return []
    
    extracted_sites = []
    
    # 判定是否为主源 (主源的 Spider 接口最稳，优先保留)
    is_prime = (url == PRIME_SOURCE)
    
    def process_site(site):
        # 1. 强制剥离 Jar (核心防崩逻辑)
        if 'jar' in site:
            del site['jar']
            
        name = site.get('name', '')
        stype = site.get('type', 0)
        
        # 2. 防崩过滤：Type 3 (Spider)
        # 如果不是主源的 Spider，为了防止不兼容饭太硬的 Jar，建议丢弃
        # 但如果你想碰运气，可以注释掉下面两行
        if stype == 3 and not is_prime and "饭太硬" not in url and "肥猫" not in url:
             return None
            
        # 3. 黑名单清洗
        if any(bw in name for bw in BLACKLIST): return None
        if any(char in name for char in ['💰', '👗', '👠', '✨', '⚡', '🔥', '免费', '送', '加V']): return None
        
        # 4. 标记与美化
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
        print(">>> 启动 TVBox 镜像直连版 v34.0")
        
        # 1. 获取核心配置
        final_jar, final_wp = fetch_prime_config()
        
        # 2. 并发抓取
        all_sites = []
        unique_urls = list(set(EXTERNAL_URLS))
        print(f">>> [2/4] 正在聚合 {len(unique_urls)} 个订阅源...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(fetch_and_process, url): url for url in unique_urls}
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    sites = future.result()
                    if sites: all_sites.extend(sites)
                except: pass
        
        # 3. 去重与生成
        print(f">>> [3/4] 去重与打包...")
        unique_sites = []
        seen_api = set()
        
        # 让主源的接口排在最前面
        # 简单的排序逻辑：包含"饭太硬"或"肥猫"的优先
        all_sites.sort(key=lambda x: 0 if "🛡️" in x['name'] else 1)

        for s in all_sites:
            api = s.get('api', '')
            if api and api not in seen_api:
                unique_sites.append(s)
                seen_api.add(api)
                
        # 截断
        max_sites = 250
        if len(unique_sites) > max_sites:
            unique_sites = unique_sites[:max_sites]
        
        # 4. 生成配置
        config = {
            "spider": final_jar, # 动态获取的 Jar
            "wallpaper": final_wp,
            "sites": unique_sites,
            "lives": [],
            "parses": [],
            "flags": []
        }
        
        with open("my_tvbox.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 完成！")
        print(f"📊 聚合接口: {len(unique_sites)} 个")
        print(f"🛡️ 核心 Jar: {final_jar}")
        
    except Exception as e:
        print(f"\n[!!!] 错误: {e}")
        # 保底生成
        if not os.path.exists("my_tvbox.json"):
            with open("my_tvbox.json", 'w', encoding='utf-8') as f:
                json.dump({"spider":DEFAULT_JAR, "sites":[]}, f)
        sys.exit(0)

if __name__ == "__main__":
    main()
