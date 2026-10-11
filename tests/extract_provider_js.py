"""从 main.py 抽取各 provider 的路径规划 JS（供 Node 真实执行）。"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(os.environ.get("TEMP", "/tmp"), "jsprobe")

# (名字, 函数起点, 函数终点)
PAIRS = [
    ("amap", "def _plan_route_path_with_amap_runtime", "def _plan_route_path_with_tencent_runtime"),
    ("tencent", "def _plan_route_path_with_tencent_runtime", "def _plan_route_path_with_tianditu_runtime"),
    ("tianditu", "def _plan_route_path_with_tianditu_runtime", "def _plan_route_path_with_baidu_runtime"),
    ("baidu", "def _plan_route_path_with_baidu_runtime", "def _plan_route_path_with_provider_runtime"),
]


def extract_js(body: str) -> str:
    """抓取 execute_js(session_id, <字符串字面量> 里的 JS。"""
    idx = body.index("execute_js(")
    tail = body[idx:]
    # 跳过 execute_js(session_id, 之后的内容
    after = tail[tail.index(",") + 1 :]
    # 定位第一个三引号或单/双引号字符串
    triple = re.search(r'"""(.*?)"""', after, re.S)
    if triple:
        return triple.group(1)
    single = re.search(r"'''(.*?)'''", after, re.S)
    if single:
        return single.group(1)
    # 退化为 inline 拼接：取出直到最后的 ) 之前
    raise AssertionError("未找到 JS 字符串字面量")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    failed = 0
    for name, start_marker, end_marker in PAIRS:
        body = src[src.index(start_marker) : src.index(end_marker)]
        try:
            js = extract_js(body)
        except AssertionError as exc:
            print("%s: 抽取失败 %s" % (name, exc))
            failed += 1
            continue
        path = os.path.join(OUT_DIR, name + ".js")
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(js)
        print("%s: 抽取 %d 字符 -> %s" % (name, len(js), path))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
