"""从 legacy JS 中抽出「缺密码补全流程」源码块，供契约测试与 Node 行为测试复用。

单独放一个模块是为了让两个测试文件共用同一份抽取逻辑，
避免两边各写一份正则解析、边界一改就双双失准。
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_JS = ROOT / "scripts" / "main.js"

#: 流程块起止锚点（改动流程时同步这里）
START_ANCHOR = "// ========== 缺失密码补全流程（四阶段） =========="
END_ANCHOR = "function closeModalElement(id) {"


def extract_missing_flow_source() -> str:
    """返回缺密码四阶段流程的源码块（含 closeModalElement 的完整函数）。"""
    source = MAIN_JS.read_text(encoding="utf-8")
    start = source.index(START_ANCHOR)
    end = source.index(END_ANCHOR, start)

    # closeModalElement 的函数体也要包含进来（花括号配平到结束）
    brace = source.index("{", end)
    depth = 0
    for offset in range(brace, len(source)):
        char = source[offset]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : offset + 1]
    raise AssertionError("未找到 closeModalElement 的结束花括号")


def extract_import_result_source() -> str:
    """返回导入结果弹窗渲染函数的源码块。"""
    source = MAIN_JS.read_text(encoding="utf-8")
    start = source.index("function showImportResultModal(")
    end = source.index("\nfunction ", start + 10)
    return source[start:end]


if __name__ == "__main__":
    block = extract_missing_flow_source()
    print(f"流程块行数: {block.count(chr(10))}")
    print(block[:200])
