import requests
import json
import re
import base64
from copy import deepcopy

# ================= 配置 =================

BASE_URL = "http://www.饭太硬.com/tv"
EXTRA_SOURCES = [
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json",
]

OUTPUT_FILE = "my_tvbox.json"
TIMEOUT = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (TVBox Fusion)"
}

# ================= 解码（关键） =================

def decode_content(text: str):
    if not text:
        return None
    text = text.strip()

    # 1. 直接 JSON
    try:
        return json.loads(text)
    except:
        pass

    # 2. Base64 JSON
    try:
        cleaned = re.sub(r'[^A-Za-z0-9+/=]', '', text)
        decoded = base64.b64decode(cleaned).decode("utf-8")
        return json.loads(decoded)
    except:
        pass

    # 3. 正则提取
    try:
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            return json.loads(m.group())
    except:
        pass

    return None


def fetch_json(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = decode_content(r.text)
        if not data:
            print(f"[跳过] 无法解析: {url}")
            return None
        return data
    except Exception as e:
        print(f"[跳过] 请求失败: {url} -> {e}")
        return None


# ================= 校验与修复 =================

def is_valid_site(site):
    if not isinstance(site, dict):
        return False
    for k in ("key", "name", "api", "type"):
        if k not in site:
            return False
    if not isinstance(site["api"], str):
        return False
    if not site["api"].startswith("http"):
        return False
    return True


def fix_search(site):
    site.setdefault("searchable", 1)
    site.setdefault("quickSearch", 1)
    return site


# ================= 主逻辑 =================

def main():
    print(">>> 拉取饭太硬底板")
    base = fetch_json(BASE_URL)

    if not base or not isinstance(base, dict):
        print("[致命] 饭太硬不可解析，生成兜底文件")
        base = {
            "sites": [],
            "parses": [],
            "rules": [],
            "lives": []
        }

    result = deepcopy(base)
    result.setdefault("sites", [])
    result.setdefault("parses", [])
    result.setdefault("rules", [])
    result.setdefault("lives", [])

    print(f"✔ 饭太硬站点数: {len(result['sites'])}")

    # 记录已有 key（只用于附加源去重）
    existing_keys = {s.get("key") for s in result["sites"] if isinstance(s, dict)}

    # 修复饭太硬搜索字段（不破坏）
    result["sites"] = [fix_search(s) for s in result["sites"]]

    added = 0

    print(">>> 开始融合附加源")
    for src in EXTRA_SOURCES:
        print(f"  -> {src}")
        data = fetch_json(src)
        if not data or "sites" not in data:
            continue

        for site in data["sites"]:
            if not is_valid_site(site):
                continue
            if site["key"] in existing_keys:
                continue

            result["sites"].append(fix_search(site))
            existing_keys.add(site["key"])
            added += 1

    print(f"✔ 新增融合站点: {added}")
    print(f"📊 最终站点总数: {len(result['sites'])}")

    # 一定写文件，保证 CI
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 输出完成: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()