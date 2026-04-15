# CDN Require 递归离线缓存升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级现有 CDN 缓存系统，自动递归拉取 `require(...)`（相对依赖 + 包依赖），改写为本地 `require` 路径，并在本地缓存缺失时自动回源拉取。

**Architecture:** 在 `main.py` 现有 CDN 缓存模块内新增一组“依赖解析 + URL 解析 + 文件重命名 + 元数据索引 + 回源兜底”函数。`update_single_cdn_file` 对 JS 资源改为“入口 + 递归依赖”的缓存流程，CSS/字体逻辑保持不变。新增元数据文件 `<entry>.meta.json` 用于 `url_to_local`/`local_to_url` 映射，支持本地失败自动回源并补写缓存。

**Tech Stack:** Python 3（`re`, `json`, `os`, `urllib.parse`, `hashlib`, `threading`, `unittest`, `unittest.mock`）、Flask 现有 API。

---

## File Structure（实施前锁定）

- Modify: `main.py`
  - 现有 CDN 区域（`JS_CACHE_DIR`, `CDN_FILES`, `fetch_cdn_file`, `load_cached_file`, `save_cached_file`, `update_single_cdn_file`, `init_cdn_cache`, `get_cdn_cached_file`）
  - 新增职责：
    1) `require(...)` 解析与改写
    2) 相对/包依赖 URL 解析
    3) 依赖文件命名（包名_路径）
    4) 元数据持久化（`<entry>.meta.json`）
    5) 本地失败自动回源
- Create: `tests/test_cdn_require_parser.py`
- Create: `tests/test_cdn_dependency_resolver.py`
- Create: `tests/test_cdn_meta_fallback.py`

---

### Task 1: 建立 require 解析与重命名基础（TDD）

**Files:**
- Modify: `main.py`（CDN 缓存函数区）
- Test: `tests/test_cdn_require_parser.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from main import _extract_commonjs_requires, _build_dep_storage_name


class TestCdnRequireParser(unittest.TestCase):
    def test_extract_commonjs_requires(self):
        source = """
        require('./src/flowchart.shim');
        var parse = require('./src/flowchart.parse');
        require('jquery');
        require('lodash/fp');
        """
        requires = _extract_commonjs_requires(source)
        self.assertEqual(
            requires,
            ['./src/flowchart.shim', './src/flowchart.parse', 'jquery', 'lodash/fp'],
        )

    def test_build_dep_storage_name(self):
        self.assertEqual(
            _build_dep_storage_name('flowchart', './src/flowchart.shim', '.js'),
            'flowchart_src_flowchart.shim.js',
        )
        self.assertEqual(
            _build_dep_storage_name('flowchart', 'lodash/fp', '.js'),
            'lodash_fp.js',
        )


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cdn_require_parser -v`
Expected: FAIL with `ImportError` 或 `AttributeError`（函数尚未实现）。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

RE_REQUIRE = re.compile(r"(?<![\w$])require\(\s*['\"]([^'\"]+)['\"]\s*\)")


def _extract_commonjs_requires(source_text: str) -> list[str]:
    if not isinstance(source_text, str):
        return []
    return [m.group(1).strip() for m in RE_REQUIRE.finditer(source_text)]


def _sanitize_dep_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", (name or "").strip())
    return cleaned.strip("_") or "dep"


def _build_dep_storage_name(entry_pkg: str, require_spec: str, default_ext: str = ".js") -> str:
    spec = (require_spec or "").strip()
    if spec.startswith("./") or spec.startswith("../"):
        spec = spec.lstrip("./")
        base = f"{entry_pkg}_{spec}"
    else:
        base = spec.replace("/", "_")
    base = _sanitize_dep_name(base)
    root, ext = os.path.splitext(base)
    if ext:
        return base
    return f"{base}{default_ext}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cdn_require_parser -v`
Expected: PASS (`test_extract_commonjs_requires`, `test_build_dep_storage_name`)。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cdn_require_parser.py
git commit -m "test+feat: add require parser and dependency naming helpers"
```

---

### Task 2: 增加元数据索引（url_to_local / local_to_url）

**Files:**
- Modify: `main.py`
- Test: `tests/test_cdn_meta_fallback.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import os
import tempfile
import unittest

from main import _load_cdn_meta, _save_cdn_meta, _meta_set_mapping


class TestCdnMeta(unittest.TestCase):
    def test_meta_roundtrip_and_mapping(self):
        with tempfile.TemporaryDirectory() as d:
            meta_path = os.path.join(d, 'flowchart.meta.json')
            meta = _load_cdn_meta(meta_path)
            self.assertEqual(meta['url_to_local'], {})
            self.assertEqual(meta['local_to_url'], {})

            _meta_set_mapping(meta, 'https://cdn.jsdelivr.net/npm/flowchart.js/index.js', 'flowchart.js')
            _save_cdn_meta(meta_path, meta)

            saved = _load_cdn_meta(meta_path)
            self.assertEqual(saved['url_to_local']['https://cdn.jsdelivr.net/npm/flowchart.js/index.js'], 'flowchart.js')
            self.assertEqual(saved['local_to_url']['flowchart.js'], 'https://cdn.jsdelivr.net/npm/flowchart.js/index.js')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cdn_meta_fallback -v`
Expected: FAIL（元数据函数未定义）。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

def _default_cdn_meta(entry_url: str = "", entry_file: str = "", deps_dir: str = "") -> dict:
    return {
        "entry_url": entry_url,
        "entry_file": entry_file,
        "deps_dir": deps_dir,
        "url_to_local": {},
        "local_to_url": {},
        "status": "partial",
        "failed": [],
    }


def _load_cdn_meta(meta_path: str) -> dict:
    if not os.path.exists(meta_path):
        return _default_cdn_meta()
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default_cdn_meta()
        data.setdefault("url_to_local", {})
        data.setdefault("local_to_url", {})
        data.setdefault("failed", [])
        data.setdefault("status", "partial")
        return data
    except Exception:
        return _default_cdn_meta()


def _save_cdn_meta(meta_path: str, meta: dict) -> bool:
    tmp = f"{meta_path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        os.replace(tmp, meta_path)
        return True
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _meta_set_mapping(meta: dict, remote_url: str, local_rel_path: str):
    meta.setdefault("url_to_local", {})[remote_url] = local_rel_path
    meta.setdefault("local_to_url", {})[local_rel_path] = remote_url
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cdn_meta_fallback -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cdn_meta_fallback.py
git commit -m "feat: add per-entry CDN metadata mapping store"
```

---

### Task 3: 实现依赖 URL 解析（相对路径 + 包依赖）

**Files:**
- Modify: `main.py`
- Test: `tests/test_cdn_dependency_resolver.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from main import _resolve_relative_require_url, _split_package_require


class TestCdnDependencyResolver(unittest.TestCase):
    def test_resolve_relative(self):
        base = 'https://cdn.jsdelivr.net/npm/flowchart.js/index.js'
        self.assertEqual(
            _resolve_relative_require_url(base, './src/flowchart.shim'),
            'https://cdn.jsdelivr.net/npm/flowchart.js/src/flowchart.shim.js',
        )

    def test_split_package_require(self):
        self.assertEqual(_split_package_require('jquery'), ('jquery', ''))
        self.assertEqual(_split_package_require('lodash/fp'), ('lodash', 'fp'))
        self.assertEqual(_split_package_require('@scope/pkg/subpath'), ('@scope/pkg', 'subpath'))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cdn_dependency_resolver -v`
Expected: FAIL（解析函数未定义）。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

def _ensure_js_like_path(path_value: str) -> str:
    p = (path_value or "").strip()
    if not p:
        return "index.js"
    if p.endswith(".js") or p.endswith(".json"):
        return p
    if p.endswith("/"):
        return p + "index.js"
    return p + ".js"


def _resolve_relative_require_url(current_file_url: str, require_spec: str) -> str:
    raw = _ensure_js_like_path(require_spec)
    return urllib.parse.urljoin(current_file_url, raw)


def _split_package_require(require_spec: str) -> tuple[str, str]:
    spec = (require_spec or "").strip()
    if spec.startswith("@"):
        parts = spec.split("/")
        if len(parts) <= 2:
            return spec, ""
        return "/".join(parts[:2]), "/".join(parts[2:])
    parts = spec.split("/", 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cdn_dependency_resolver -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cdn_dependency_resolver.py
git commit -m "feat: add CDN dependency URL resolver helpers"
```

---

### Task 4: 实现递归缓存与 require 改写主流程

**Files:**
- Modify: `main.py`
- Test: `tests/test_cdn_require_parser.py`（扩展场景）

- [ ] **Step 1: Write the failing test**

```python
import unittest

from main import _rewrite_requires_to_local


class TestRewriteRequires(unittest.TestCase):
    def test_rewrite_to_local(self):
        source = """
        require('./src/flowchart.shim');
        var parse = require('./src/flowchart.parse');
        require('jquery');
        """
        mapping = {
            './src/flowchart.shim': './flowchart/flowchart_src_flowchart.shim.js',
            './src/flowchart.parse': './flowchart/flowchart_src_flowchart.parse.js',
            'jquery': './flowchart/jquery_index.js',
        }
        out = _rewrite_requires_to_local(source, mapping)
        self.assertIn("require('./flowchart/flowchart_src_flowchart.shim.js')", out)
        self.assertIn("require('./flowchart/flowchart_src_flowchart.parse.js')", out)
        self.assertIn("require('./flowchart/jquery_index.js')", out)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cdn_require_parser -v`
Expected: FAIL（改写函数未定义）。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

def _rewrite_requires_to_local(source_text: str, require_to_local: dict[str, str]) -> str:
    if not isinstance(source_text, str) or not require_to_local:
        return source_text

    def _replace(match):
        spec = match.group(1).strip()
        local_path = require_to_local.get(spec)
        if not local_path:
            return match.group(0)
        return f"require('{local_path}')"

    return RE_REQUIRE.sub(_replace, source_text)


def _cache_js_entry_with_dependencies(entry_key: str, entry_url: str, entry_filename: str) -> bool:
    entry_pkg = (entry_filename or entry_key or "entry").rsplit('.', 1)[0]
    deps_dir = entry_pkg
    meta_path = os.path.join(JS_CACHE_DIR, f"{entry_pkg}.meta.json")
    meta = _load_cdn_meta(meta_path)
    meta["entry_url"] = entry_url
    meta["entry_file"] = entry_filename
    meta["deps_dir"] = deps_dir

    visited = set()
    queued = [(entry_url, entry_filename, True)]

    def _resolve_package_url(require_spec: str) -> str | None:
        pkg, subpath = _split_package_require(require_spec)
        pkg_root = f"https://cdn.jsdelivr.net/npm/{pkg}"
        pkg_json_url = f"{pkg_root}/package.json"
        pkg_json_text = fetch_cdn_file(pkg_json_url)
        if not pkg_json_text:
            return None
        try:
            pkg_json = json.loads(pkg_json_text)
        except Exception:
            return None

        if subpath:
            candidate = _ensure_js_like_path(subpath)
            return f"{pkg_root}/{candidate}"

        entry_path = ""
        exports_value = pkg_json.get("exports")
        if isinstance(exports_value, str):
            entry_path = exports_value
        elif isinstance(exports_value, dict):
            dot_value = exports_value.get(".")
            if isinstance(dot_value, str):
                entry_path = dot_value
            elif isinstance(dot_value, dict):
                entry_path = dot_value.get("require") or dot_value.get("default") or ""

        if not entry_path:
            entry_path = pkg_json.get("module") or pkg_json.get("main") or "index.js"

        entry_path = _ensure_js_like_path(str(entry_path).lstrip("./"))
        return f"{pkg_root}/{entry_path}"

    while queued:
        remote_url, local_name, is_entry = queued.pop(0)
        if remote_url in visited:
            continue
        visited.add(remote_url)

        text = fetch_cdn_file(remote_url)
        if text is None:
            meta.setdefault("failed", []).append({"url": remote_url, "error": "fetch_failed"})
            continue

        requires = _extract_commonjs_requires(text)
        rewrite_map = {}

        for spec in requires:
            if spec.startswith("./") or spec.startswith("../"):
                dep_url = _resolve_relative_require_url(remote_url, spec)
            else:
                dep_url = _resolve_package_url(spec)

            if not dep_url:
                meta.setdefault("failed", []).append({"url": remote_url, "require": spec, "error": "resolve_failed"})
                continue

            dep_filename = _build_dep_storage_name(entry_pkg, spec, ".js")
            dep_rel_path = f"{deps_dir}/{dep_filename}"
            rewrite_map[spec] = f"./{dep_rel_path}"
            _meta_set_mapping(meta, dep_url, dep_rel_path)
            queued.append((dep_url, dep_rel_path, False))

        rewritten = _rewrite_requires_to_local(text, rewrite_map)
        target_name = entry_filename if is_entry else local_name
        if not save_cached_file(target_name, rewritten):
            meta.setdefault("failed", []).append({"url": remote_url, "file": target_name, "error": "save_failed"})
            continue

        _meta_set_mapping(meta, remote_url, target_name)

    meta["status"] = "complete" if not meta.get("failed") else "partial"
    _save_cdn_meta(meta_path, meta)
    return meta["status"] == "complete"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cdn_require_parser -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cdn_require_parser.py
git commit -m "feat: implement recursive JS dependency cache and require rewrite"
```

---

### Task 5: 集成到现有 CDN 更新流程（含本地失败自动回源）

**Files:**
- Modify: `main.py`（`update_single_cdn_file`, `load_cached_file`, `get_cdn_cached_file`）
- Test: `tests/test_cdn_meta_fallback.py`（扩展回源测试）

- [ ] **Step 1: Write the failing test**

```python
import unittest
from unittest.mock import patch

from main import _load_or_refetch_cached_file


class TestLocalFallback(unittest.TestCase):
    @patch('main.fetch_cdn_file')
    def test_refetch_when_local_missing(self, mock_fetch):
        mock_fetch.return_value = 'module.exports = {}'
        meta = {
            'local_to_url': {'flowchart/flowchart_src_flowchart.shim.js': 'https://cdn.jsdelivr.net/npm/flowchart.js/src/flowchart.shim.js'}
        }
        content = _load_or_refetch_cached_file('flowchart/flowchart_src_flowchart.shim.js', meta)
        self.assertEqual(content, 'module.exports = {}')
        mock_fetch.assert_called_once()


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cdn_meta_fallback -v`
Expected: FAIL（兜底函数未定义）。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

def _load_or_refetch_cached_file(local_rel_path: str, meta: dict, binary: bool = False):
    cached = load_cached_file(local_rel_path, binary=binary)
    if cached is not None:
        return cached

    remote_url = (meta or {}).get('local_to_url', {}).get(local_rel_path)
    if not remote_url:
        return None

    content = fetch_cdn_file(remote_url, binary=binary)
    if content is None:
        return None

    save_cached_file(local_rel_path, content, binary=binary)
    return content


# update_single_cdn_file 集成点：
# - file_type == 'js' 时，调用 _cache_js_entry_with_dependencies
# - file_type != 'js' 时，保留原路径

# get_cdn_cached_file 集成点：
# - 未命中 js_cache_storage 时，尝试读取本地缓存
# - 本地失败时触发单文件回源更新（update_single_cdn_file）再返回
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cdn_meta_fallback -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cdn_meta_fallback.py
git commit -m "feat: add local-cache-miss fallback to remote CDN and persist back"
```

---

### Task 6: 全量回归验证与文档同步

**Files:**
- Modify: `docs/superpowers/specs/2026-04-09-cdn-offline-cache-design.md`（仅在实现偏差时更新）
- Test: `tests/test_cdn_require_parser.py`, `tests/test_cdn_dependency_resolver.py`, `tests/test_cdn_meta_fallback.py`

- [ ] **Step 1: Add integration-level failing test case for flowchart scenario**

```python
# tests/test_cdn_dependency_resolver.py 中增加
# - 模拟入口 flowchart.js
# - 断言依赖文件名规则为 flowchart/*.js
# - 断言 rewritten require 指向 ./flowchart/<renamed>.js
```

- [ ] **Step 2: Run full test suite**

Run: `python -m unittest -v tests.test_cdn_require_parser tests.test_cdn_dependency_resolver tests.test_cdn_meta_fallback`
Expected: ALL PASS。

- [ ] **Step 3: Manual verification commands**

Run:
```bash
python -c "import main; print('main import ok')"
```
Expected: `main import ok`

Run:
```bash
python -c "import os; p=os.path.join('cache','cdn'); print('cache dir exists:', os.path.isdir(p))"
```
Expected: `cache dir exists: True`

- [ ] **Step 4: Validate acceptance criteria checklist**

```text
[ ] flowchart.js 缓存为 <cache>/flowchart.js
[ ] 依赖缓存为 <cache>/flowchart/*
[ ] require 改写为 ./flowchart/<pkg_path_renamed>.js
[ ] 本地依赖删除后可自动回源并补回
[ ] 元数据文件 <entry>.meta.json 含双向映射
```

- [ ] **Step 5: Commit**

```bash
git add main.py tests/*.py docs/superpowers/specs/2026-04-09-cdn-offline-cache-design.md
git commit -m "test+feat: complete CDN recursive require offline caching with fallback"
```

---

## Self-Review（against spec）

1. **Spec coverage**
- 目录与命名规范（`<entry>.js + <entry_dir>/...` + 包名_路径）：Task 1, Task 4, Task 6
- 解析与递归流程（相对 + 包依赖）：Task 3, Task 4
- 元数据索引（url/local 双向映射）：Task 2
- 本地失败自动回源：Task 5
- 验收与回归：Task 6

2. **Placeholder scan**
- 所有任务包含具体文件、命令、测试入口。
- 注意：Task 4 Step 3 的 `...` 在执行时必须替换为完整实现（不得提交占位符）。

3. **Type consistency**
- 函数命名统一：`_extract_commonjs_requires`, `_build_dep_storage_name`, `_split_package_require`, `_rewrite_requires_to_local`, `_load_or_refetch_cached_file`。
- 测试文件调用与函数名一致。
