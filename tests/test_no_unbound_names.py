"""全局回归：生产代码不得存在"引用未绑定名字"（必然 NameError）。

为什么需要这个测试:
    把一个大方法拆成多个方法时，很容易把原方法里的局部变量一起带过去。
    这类问题：
      - ast.parse / py_compile 发现不了（语法合法）；
      - 只做字符串断言的契约测试发现不了；
      - mock 掉被抽出的方法时也发现不了；
      - 只有真正执行到那一行才抛 NameError。

    真实事故：从 _multi_account_worker 抽出 _run_single_multi_account_task 时，
    进度文案里残留了调用方的 attempted_task_keys。该名字从未定义，
    于是"任务已完成、准备把进度更新为 100%"时抛
    NameError: name 'attempted_task_keys' is not defined。
    后果：多账号 worker 整体崩溃 —— 22 个账号各崩一次，任务卡在
    "已提交但未确认"状态（不结算、不计完成数、不清理线程）。

    同一检查还发现了两个既有缺陷：captcha_html.py 缺 import math、
    main.py 的短信路由缺模块级 cache。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unbound_local_check import find_unbound_names  # noqa: E402


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 生产代码范围（不含 tests/ 与 tools/ 等辅助脚本）
PRODUCTION_GLOBS = ("*.py", "runtime/*.py")
EXCLUDED_FILES = {"main_runtime.py"}


def _iter_production_files():
    import glob

    paths = []
    for pattern in PRODUCTION_GLOBS:
        paths.extend(glob.glob(os.path.join(PROJECT_ROOT, pattern)))
    for path in sorted(paths):
        name = os.path.relpath(path, PROJECT_ROOT)
        if name in EXCLUDED_FILES:
            continue
        yield name, path


class TestDetectorSelfCheck(unittest.TestCase):
    """先证明检测器本身有效，否则"无命中"可能只是检测器失灵。"""

    def test_detects_the_real_regression_shape(self):
        """复现真实事故的形态：变量只在兄弟函数里赋值。"""
        source = (
            "def caller():\n"
            "    attempted_task_keys = set()\n"
            "    return helper()\n"
            "\n"
            "def helper():\n"
            "    return f'count={len(attempted_task_keys)}'\n"
        )

        findings = find_unbound_names(source, "sample.py")

        self.assertEqual(
            [item["name"] for item in findings],
            ["attempted_task_keys"],
            "检测器未能发现兄弟函数作用域泄漏",
        )

    def test_does_not_flag_valid_global_and_closure_references(self):
        source = (
            "import os\n"
            "MODULE_LIMIT = 5\n"
            "GLOBAL_CACHE = {}\n"
            "\n"
            "def outer():\n"
            "    captured = 1\n"
            "    def inner():\n"
            "        return captured + MODULE_LIMIT + len(os.sep)\n"
            "    return inner\n"
            "\n"
            "def uses_global():\n"
            "    return GLOBAL_CACHE.get(1)\n"
        )

        self.assertEqual(find_unbound_names(source, "good.py"), [])

    def test_does_not_flag_module_dunders(self):
        source = "def where():\n    return __file__\n"

        self.assertEqual(find_unbound_names(source, "dunder.py"), [])

    def test_reports_useful_line_number(self):
        source = (
            "def caller():\n"
            "    leak = 1\n"
            "    return helper()\n"
            "\n"
            "def helper():\n"
            "    return leak\n"
        )

        findings = find_unbound_names(source, "line.py")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 6)


class TestProductionCodeHasNoUnboundNames(unittest.TestCase):
    def test_no_unbound_names_in_production_modules(self):
        offenders = []
        scanned = 0

        for name, path in _iter_production_files():
            try:
                source = open(path, encoding="utf-8").read()
            except Exception as exc:  # pragma: no cover - 读取失败要显式暴露
                self.fail(f"读取 {name} 失败: {exc}")

            try:
                findings = find_unbound_names(source, name)
            except SyntaxError as exc:
                self.fail(f"{name} 语法错误: {exc}")

            scanned += 1
            for item in findings:
                offenders.append(
                    f"{name}:{item['line']} {item['function']} 引用未绑定的名字 "
                    f"{item['name']!r}"
                )

        # 防止 glob 失效导致"零文件也算通过"
        self.assertGreater(scanned, 20, "生产模块扫描数量异常，检查 glob 配置")

        self.assertEqual(
            offenders,
            [],
            "以下位置引用了未绑定的名字，运行到该行必然 NameError：\n"
            + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
