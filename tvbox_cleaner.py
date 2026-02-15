import requests
import json
import re
import concurrent.futures
import os
import sys
import base64
from urllib.parse import quote, urljoin

# ================= 配置区域 =================
MY_GITHUB_TOKEN = ""
PROXIES = None

GITHUB_USER = "guru2016"
REPO_NAME = "tvbox-pro"
BRANCH_NAME = "main"

GLOBAL_SAFE_JAR = f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{REPO_NAME}@{BRANCH_NAME}/spider.jar"

EXTERNAL_URLS = [
    "http://www.饭太硬.com/tv",
    "http://肥猫.com",
    "http://fty.xxooo.cf/tv",
    "http://rihou.cc:88/荷城茶秀",
    "https://api.hgyx.vip/hgyx.json",
    "https://tv.菜妮丝.top",
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",
    "https://cnb.cool/fish2018/duanju/-/git/raw/main/tvbox.json",
    "https://raw.githubusercontent.com/chitue/dongliTV/main/api.json",
    "https://cdn.gitmirror.com/bb/xduo/libs/master/index.json",
    "http://ok321.top/tv",
    "http://tvbox.王二小放牛娃.top",
    "https://android.lushunming.qzz.io/json/index.json",
    "http://home.jundie.top:81/top98.json",
    "https://ghproxy.net/https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json",
    "https://www.252035.xyz/z/FongMi.json",
    "http://52bsj.vip:81/api/v3/file/get/29899/bsj2023.json?sign=3c594b2b985b365bad",
    "https://s2.pub/x",
    "http://tv.nxog.top/m/111.php?ou=公众号欧歌app&mz=all&jar=all&b=欧歌",
    "https://100km.top/0",
    "http://meowtv.cn/tv",
    "http://cdn.qiaoji8.com/tvbox.json"
]

ALLOWED_TYPES = [0, 1, 3, 4]
BLACKLIST = [
    "失效", "测试", "广告", "收费", "群", "加V", "挂壁", "Q群", "伦理", "福利", "成人", "情色",
    "引流", "弹幕", "更新", "公众号", "扫码", "微信", "企鹅", "APP", "下载",
    "推广", "验证", "激活", "授权", "雷鲸", "玩偶哥哥", "助手", "专线", "彩蛋", "直播",
    "77.110", "mingming"
]

TIMEOUT = 6
MAX_WORKERS = 60
OUTPUT_FILE = "my_tvbox.json"

# ================= 工具函数 =================
def decode_content(content):
    if not content:
        return None
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
            if match:
                return json.loads(match.group())
        except:
            pass
    return None

def get_json(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False, proxies=PROXIES)
        res.encoding = 'utf-8'
        if res.status_code == 200:
            return decode_content(res.text)
    except:
        pass
    return None

def clean_name(name):
    name = str(name)
    name = re.sub(r'【.*?】|\[.*?\]|\(.*?\)|（.*?）', '', name)
    name = name.replace("聚合", "").replace("蓝光", "").replace("专线", "").strip()
    return name

def fetch_and_strip(url):
    data = get_json(url)
    if not data:
        return []
    extracted_sites = []

    def process_site(s):
        if 'jar' in s:
            del s['jar']
        return s

    if 'urls' in data and isinstance(data['urls'], list):
        for item in data['urls']:
            if 'url' in item:
                sub_data = get_json(item['url'])
                if sub_data and 'sites' in sub_data:
                    for s in sub_data['sites']:
                        extracted_sites.append(process_site(s))
    if 'sites' in data:
        for s in data['sites']:
            extracted_sites.append(process_site(s))
    return extracted_sites

def fetch_all_sites_stripped():
    all_sites = []
    unique_urls = list(set(EXTERNAL_URLS))
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(fetch_and_strip, url): url for url in unique_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            try:
                sites = future.result()
                if sites:
                    all_sites.extend(sites)
            except:
                pass
    return all_sites

# ================= 【关键】去掉测速，只清洗 =================
def only_clean_no_speed_test(sites):
    valid_sites = []
    seen_api = set()

    for s in sites:
        name = s.get('name', '')
        api = s.get('api', '')
        stype = s.get('type', 0)

        if stype not in ALLOWED_TYPES:
            continue
        if any(bw in name for bw in BLACKLIST):
            continue
        if api in seen_api:
            continue

        seen_api.add(api)

        # 只清理名字，不开通测速
        s['name'] = clean_name(name)
        s['searchable'] = 1
        s['quickSearch'] = 1

        if s.get('type') == 3:
            s['name'] = f"🛡️ {s['name']}"
        else:
            s['name'] = f"🚀 {s['name']}"

        valid_sites.append(s)

    return valid_sites

def main():
    requests.packages.urllib3.disable_warnings()
    print(">>> 开始自动更新 TVBox 配置（无测速，超多源）...")

    raw_sites = fetch_all_sites_stripped()
    final_sites = only_clean_no_speed_test(raw_sites)

    if len(final_sites) > 300:
        final_sites = final_sites[:300]

    lives = [
        {"name": "📺 央视卫视", "type": 0, "url": "https://tv.iill.top/m3u/iptv-org.m3u", "ua": "okhttp/3.12.13"},
        {"name": "📺 高清直播", "type": 0, "url": "https://raw.githubusercontent.com/sszlxx/IPTV4TVBox/main/live.txt", "ua": "okhttp/3.12.13"}
    ]

    parses = [
        {"name": "⚡ 极速解析1", "url": "https://jx.qqmi.cc/jx/player.php?url="},
        {"name": "⚡ 极速解析2", "url": "https://jx.777jiexi.com:666/?url="},
        {"name": "⚡ 通用解析", "url": "https://www.8090zz.cc/?url="}
    ]

    config = {
        "spider": GLOBAL_SAFE_JAR,
        "wallpaper": "https://api.kdcc.cn",
        "sites": final_sites,
        "lives": lives,
        "parses": parses,
        "flags": []
    }

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"✅ 生成完成：{OUTPUT_FILE}，有效源：{len(final_sites)}")
    except Exception as e:
        print(f"❌ 写入失败：{e}")

if __name__ == "__main__":
    main()
