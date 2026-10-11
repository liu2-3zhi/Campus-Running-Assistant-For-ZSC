"""未绑定名字的静态检测（无第三方依赖，基于标准库 symtable）。

存在的原因:
    把一个大方法拆成多个方法时，很容易把原方法里的局部变量一起带过去，
    留下"看起来正常、实际未定义"的名字。这类问题：
      - 语法检查（ast.parse / py_compile）发现不了；
      - 只做字符串断言的契约测试发现不了；
      - 只有真正执行到那一行才抛 NameError。

    真实事故：从 _multi_account_worker 抽出 _run_single_multi_account_task 时，
    进度文案里残留了调用方的 attempted_task_keys。该名字在模块里不存在，
    于是被解析为全局查找，运行到"把进度更新为 100%"时抛
    NameError: name 'attempted_task_keys' is not defined，多账号 worker 整体崩溃。

检测思路:
    Python 对"函数内引用、但该函数内没有绑定、也没有 global 声明"的名字，
    一律按全局查找处理。因此只要该名字在模块顶层从未绑定，运行到那一行
    必然 NameError。本模块据此做高置信度检测。
"""

from __future__ import annotations

import ast
import builtins
import symtable
from typing import Iterable


def _module_bound_names(top: symtable.SymbolTable) -> set[str]:
    """模块顶层真正绑定过的名字（赋值/import/def/class/全局声明）。"""
    bound: set[str] = set()
    for symbol in top.get_symbols():
        if (
            symbol.is_assigned()
            or symbol.is_imported()
            or symbol.is_namespace()
            or symbol.is_declared_global()
        ):
            bound.add(symbol.get_name())
    return bound


def _name_line_index(source: str) -> dict[tuple[str, str], list[int]]:
    """(限定作用域名, 名字) -> 行号列表。

    必须按作用域分别记录：同一个名字可能在一个函数里是参数、在另一个函数里
    才是未绑定的引用。若只按名字做全局索引，会把行号错配到无关位置，
    从而产生误报。
    """
    index: dict[tuple[str, str], list[int]] = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return index

    def visit(node, scope: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            child_scope = f"{scope}.{node.name}" if scope else node.name
            for child in ast.iter_child_nodes(node):
                visit(child, child_scope)
            return
        if isinstance(node, ast.Name):
            index.setdefault((scope, node.id), []).append(node.lineno)
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    for child in ast.iter_child_nodes(tree):
        visit(child, "")
    return index


def _scope_bound_names(table: symtable.SymbolTable) -> set[str]:
    """某个作用域内绑定过的名字（赋值/import/def/class/参数/全局声明）。"""
    bound: set[str] = set()
    for symbol in table.get_symbols():
        if (
            symbol.is_assigned()
            or symbol.is_imported()
            or symbol.is_namespace()
            or symbol.is_parameter()
            or symbol.is_declared_global()
        ):
            bound.add(symbol.get_name())
    return bound


def find_unbound_names(source: str, filename: str = "<string>") -> list[dict]:
    """
    返回"运行时必然 NameError"的名字引用列表。

    每个元素:
        {"function": 限定名, "name": 名字, "line": 行号}

    判定规则:
        - 该名字在当前作用域被引用；
        - 当前作用域内没有绑定它（非局部、非参数、非 import、非赋值目标）；
        - 它不是自由变量（闭包变量）；
        - **该名字在模块顶层以及所有外层作用域里都没有绑定**；
        - 不在 builtins 中。

    为什么"外层作用域的绑定"也算可见:
        函数体内引用一个名字时，若本作用域没绑定，Python 会按 LEGB 逐层向外
        查找，最终落到模块全局。因此只要任何外层作用域绑定过它，运行时就能
        取到值，不构成缺陷。

        真实案例：sms_send_code 里用到 cache，而 cache 是在 main.py 模块顶层
        赋值的全局变量。本作用域内没绑定它，但运行时完全正常——若不做这个
        判断就会误报。

        反过来，真实事故里的 attempted_task_keys 只在**兄弟函数**里被赋值过，
        任何外层作用域都没有它，运行时必然 NameError，会被正确报出。

    刻意不覆盖（避免误报）:
        - 通过 globals()/exec 动态注入的名字；
        - 单文件无法看到的跨模块注入。
    """
    top = symtable.symtable(source, filename, "exec")
    # builtins 之外，解释器还会注入一批模块级 dunder（如 __file__/__name__），
    # 它们不体现在 symtable 里，必须显式排除，否则全是误报。
    builtin_names = set(dir(builtins)) | {
        "__file__",
        "__name__",
        "__doc__",
        "__package__",
        "__loader__",
        "__spec__",
        "__builtins__",
        "__debug__",
        "__annotations__",
    }
    line_index = _name_line_index(source)
    findings: list[dict] = []

    def walk(table: symtable.SymbolTable, prefix: str, visible: set[str]) -> None:
        """visible: 当前作用域可见的外层绑定（LEGB 的外层部分）。"""
        qualname = f"{prefix}.{table.get_name()}" if prefix else table.get_name()
        # symtable 的顶层表名固定为 "top"，而 AST 侧用的是 ""。
        # 去重时统一剥掉这个前缀，否则按作用域查行号会整片查不到。
        lookup_name = qualname[4:] if qualname.startswith("top.") else qualname

        if table.get_type() == "function":
            for symbol in table.get_symbols():
                name = symbol.get_name()

                if not symbol.is_referenced():
                    continue
                if name in builtin_names or name in visible:
                    continue
                # 解析规则：
                #   - 局部/参数/import/赋值目标 -> 已在当前作用域绑定
                #   - free -> 闭包变量，由外层作用域提供
                # 剩下的情况 Python 会按全局查找；如果外层作用域（含模块顶层）
                # 也没绑定过，运行时必然 NameError。
                if (
                    symbol.is_local()
                    or symbol.is_parameter()
                    or symbol.is_imported()
                    or symbol.is_assigned()
                    or symbol.is_free()
                ):
                    continue

                findings.append(
                    {
                        "function": qualname,
                        "name": name,
                        "line": (
                            line_index.get((lookup_name, name))
                            or line_index.get(("", name))
                            or [None]
                        )[0],
                        "all_lines": line_index.get((lookup_name, name), []),
                    }
                )

        # 进入子作用域前，把本作用域的绑定并入可见集合
        nested_visible = visible | _scope_bound_names(table)
        for child in table.get_children():
            walk(child, qualname, nested_visible)

    walk(top, "", set())
    return findings


def format_findings(findings: Iterable[dict]) -> str:
    return "\n".join(
        f"{item['function']}: 引用未绑定的名字 {item['name']!r} (行 {item['line']})"
        for item in findings
    )
