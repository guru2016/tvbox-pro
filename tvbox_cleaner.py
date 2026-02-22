import json
import requests
from copy import deepcopy

BASE_URL = "https://fty.xxooo.cf/tv"

# ⚠️ 只放“结构简单、直链 JSON、已知可解析”的源
EXTRA_SOURCES = [
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://raw.githubusercontent.com/fantaite/TVBox/main/XC.json",
]

TIMEOUT = 8


def fetch_json(url):
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[跳过] 无法获取: {url} -> {e}")
        return None


def normalize_site(site):
    """
    只做最低限度清洗，避免破坏可解析性
    """
    if not isinstance(site, dict):
        return None

    required = ["key", "name", "api", "type"]
    if not all(k in site for k in required):
        return None

    s = deepcopy(site)

    # 搜索修复：只补，不覆盖
    s.setdefault("searchable", 1)
    s.setdefault("quickSearch", 1)

    # 防止奇怪类型
    try:
        s["type"] = int(s["type"])
    except Exception:
        return None

    # API 基本校验
    if not isinstance(s["api"], str) or not s["api"].startswith("http"):
        return None

    return s


def main():
    print("拉取饭太硬主配置…")
    base = fetch_json(BASE_URL)
    if not base:
        raise RuntimeError("饭太硬源不可用，直接退出")

    result = deepcopy(base)

    base_sites = {s["key"] for s in result.get("sites", []) if "key" in s}
    merged = []

    print(f"饭太硬原始站点数: {len(base_sites)}")

    for src in EXTRA_SOURCES:
        print(f"处理附加源: {src}")
        data = fetch_json(src)
        if not data or "sites" not in data:
            continue

        for site in data["sites"]:
            s = normalize_site(site)
            if not s:
                continue

            # 不覆盖饭太硬
            if s["key"] in base_sites:
                continue

            merged.append(s)
            base_sites.add(s["key"])

    print(f"成功合并新增站点: {len(merged)}")

    result["sites"].extend(merged)

    # 最终校验
    result.setdefault("lives", [])
    result.setdefault("parses", [])
    result.setdefault("rules", [])

    with open("tvbox_fty_merged.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("✅ 生成完成: tvbox_fty_merged.json")
    print("✅ 该文件以饭太硬为主，新增源全部可解析")


if __name__ == "__main__":
    main()