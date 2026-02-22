import json
import requests
from copy import deepcopy

# ================= 1. 配置区域 =================

# 饭太硬官方底板
BASE_URL = "http://www.饭太硬.com/tv"

# 追加可解析源
EXTRA_SOURCES = [
    "https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json",
    "https://raw.githubusercontent.com/fantaite/TVBox/main/XC.json",
]

TIMEOUT = 10


# ================= 2. 工具函数 =================

def fetch_json(url):
    """安全获取 JSON，空或非 JSON 自动跳过"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        if not r.text.strip():
            print(f"[跳过] 空响应: {url}")
            return None
        return r.json()
    except Exception as e:
        print(f"[跳过] 无法获取: {url} -> {e}")
        return None


def normalize_site(site):
    """格式校验与搜索字段修复"""
    if not isinstance(site, dict):
        return None

    required = ["key", "name", "api", "type"]
    if not all(k in site for k in required):
        return None

    s = deepcopy(site)

    # 补充搜索字段，避免搜索失效
    s.setdefault("searchable", 1)
    s.setdefault("quickSearch", 1)

    # type 转整型
    try:
        s["type"] = int(s["type"])
    except Exception:
        return None

    # api 必须是 HTTP / HTTPS
    if not isinstance(s["api"], str) or not s["api"].startswith("http"):
        return None

    return s


# ================= 3. 核心逻辑 =================

def main():
    print(">>> 拉取饭太硬主配置...")
    base = fetch_json(BASE_URL)
    if not base:
        print("[错误] 饭太硬源不可用，退出")
        return

    result = deepcopy(base)

    # 建立已有 key 集合，用于去重
    base_sites = {s["key"] for s in result.get("sites", []) if "key" in s}
    merged_sites = []

    print(f"饭太硬原始站点数: {len(base_sites)}")

    # 处理附加源
    for src in EXTRA_SOURCES:
        print(f"处理附加源: {src}")
        data = fetch_json(src)
        if not data or "sites" not in data:
            continue

        for site in data["sites"]:
            s = normalize_site(site)
            if not s:
                continue
            # 不覆盖饭太硬原始站点
            if s["key"] in base_sites:
                continue
            merged_sites.append(s)
            base_sites.add(s["key"])

    print(f"成功合并新增站点: {len(merged_sites)}")

    # 合并最终结果
    result["sites"].extend(merged_sites)

    # 确保一些必需字段存在
    result.setdefault("lives", [])
    result.setdefault("parses", [])
    result.setdefault("rules", [])

    # 保存输出文件
    out_file = "tvbox_fty_merged.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 完成生成: {out_file}")
    print(f"📊 最终站点总数: {len(result['sites'])}")


if __name__ == "__main__":
    main()