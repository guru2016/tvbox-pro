import json
import requests
from copy import deepcopy

# ================= 配置 =================

BASE_URL = "http://www.饭太硬.com/tv"
OUTPUT_FILE = "my_tvbox.json"
TIMEOUT = 12

HEADERS = {
    "User-Agent": "Mozilla/5.0 (TVBox CI)"
}

# ================= 工具函数 =================

def fetch_json(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        if not r.text.strip():
            print(f"[跳过] 空响应: {url}")
            return None
        return r.json()
    except Exception as e:
        print(f"[失败] {url} -> {e}")
        return None


def fix_search_fields(site):
    """
    不破坏饭太硬逻辑，仅修复搜索缺失字段
    """
    if not isinstance(site, dict):
        return site

    site.setdefault("searchable", 1)
    site.setdefault("quickSearch", 1)
    return site


# ================= 主逻辑 =================

def main():
    print(">>> 拉取饭太硬主配置")
    base = fetch_json(BASE_URL)

    if not base or not isinstance(base, dict):
        print("[警告] 饭太硬源不可用，生成最小兜底配置")
        base = {
            "sites": [],
            "parses": [],
            "rules": [],
            "lives": []
        }

    result = deepcopy(base)

    # 确保字段存在
    result.setdefault("sites", [])
    result.setdefault("parses", [])
    result.setdefault("rules", [])
    result.setdefault("lives", [])

    print(f"饭太硬原始站点数: {len(result['sites'])}")

    # 只修复搜索字段，不做任何过滤
    fixed_sites = []
    for s in result["sites"]:
        fixed_sites.append(fix_search_fields(s))

    result["sites"] = fixed_sites

    # ===== 最终兜底保障 =====
    if not result["sites"]:
        print("[警告] sites 为空，仍生成文件防止 CI 失败")

    # 保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 已生成 {OUTPUT_FILE}")
    print(f"📊 最终站点数: {len(result['sites'])}")


if __name__ == "__main__":
    main()