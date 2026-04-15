# Product Name Generator Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an extensible industry mode switch to `product_name_generator.py`, including a new `travel_service` mode and startup-time mode validation in `main.py`.

**Architecture:** Keep `LoMeiGenerator` as the compatibility entry point, but move industry-specific data into a single mode configuration table keyed by mode name. Add shared validator helpers inside `product_name_generator.py`, then call that validator from a small startup-check helper in `main.py` before the Flask/SocketIO app continues booting.

**Tech Stack:** Python 3, `unittest`, `unittest.mock`, existing Flask startup flow in `main.py`

---

## File structure and responsibilities

- `product_name_generator.py`
  - Remains the single source of truth for product-name generation.
  - Owns the global mode constant, the supported-mode registry, the validation helpers, and both mode-specific generation strategies.
  - Must keep the current `LoMeiGenerator()` call shape working for existing callers.

- `main.py`
  - Continues to import `LoMeiGenerator` inside `main()`.
  - Adds one startup-only helper that validates `PRODUCT_NAME_GENERATOR_MODE` immediately after importing from `product_name_generator.py` and exits early on invalid config.

- `tests/test_product_name_generator.py`
  - New focused unit tests for the generator module itself.
  - Covers supported modes, invalid mode errors, `lomei` compatibility, `travel_service` fixed quantifiers, and invalid quantity handling.

- `tests/test_product_name_generator_startup.py`
  - New focused startup validation tests for `main.py`.
  - Covers the success path and the invalid-config exit path without trying to boot the full server.

## Implementation notes to preserve scope

- Do **not** rename `LoMeiGenerator` in this change.
- Do **not** introduce environment variables, admin-panel configuration, or a new module hierarchy.
- Do **not** scatter `if mode == ...` branches across unrelated methods; keep supported modes centralized in one config table.
- Keep `generate()` as the public entry point for callers such as `_generate_payment_product_name_by_amount()`.

### Task 1: Add generator-mode tests and implement the extensible mode registry

**Files:**
- Create: `tests/test_product_name_generator.py`
- Modify: `product_name_generator.py:1-222`

- [ ] **Step 1: Write the failing generator tests**

Create `tests/test_product_name_generator.py` with the following content:

```python
import unittest
from unittest import mock

import product_name_generator as png


class TestProductNameGeneratorModes(unittest.TestCase):
    def test_supported_modes_include_lomei_and_travel_service(self):
        self.assertEqual(
            png.get_supported_product_name_generator_modes(),
            ("lomei", "travel_service"),
        )

    def test_invalid_mode_raises_clear_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            png.validate_product_name_generator_mode("bad_mode")

        message = str(ctx.exception)
        self.assertIn("PRODUCT_NAME_GENERATOR_MODE", message)
        self.assertIn("bad_mode", message)
        self.assertIn("lomei", message)
        self.assertIn("travel_service", message)

    def test_lomei_mode_keeps_existing_single_item_style(self):
        with mock.patch.object(png, "PRODUCT_NAME_GENERATOR_MODE", "lomei"):
            generator = png.LoMeiGenerator()
            with mock.patch.object(
                png.random,
                "choice",
                side_effect=["鸭脖", "串", "快乐的", "麻辣", "一串快乐的麻辣鸭脖"],
            ):
                result = generator.generate(1)

        self.assertEqual(result, "一串快乐的麻辣鸭脖")

    def test_travel_service_mode_uses_fixed_item_quantifier(self):
        with mock.patch.object(png, "PRODUCT_NAME_GENERATOR_MODE", "travel_service"):
            generator = png.LoMeiGenerator()
            with mock.patch.object(
                png.random,
                "choice",
                return_value={"name": "短信费", "quantifier": "次"},
            ):
                result = generator.generate(2)

        self.assertEqual(result, "二次短信费")

    def test_invalid_quantity_returns_none(self):
        with mock.patch.object(png, "PRODUCT_NAME_GENERATOR_MODE", "travel_service"):
            generator = png.LoMeiGenerator()
        self.assertIsNone(generator.generate(0))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test file and verify it fails**

Run:

```bash
python -m unittest tests.test_product_name_generator -v
```

Expected:
- FAIL because `product_name_generator.py` does not yet expose `get_supported_product_name_generator_modes()`.
- FAIL because `validate_product_name_generator_mode()` does not exist yet.
- FAIL because `travel_service` mode and fixed quantifier output do not exist yet.

- [ ] **Step 3: Implement the mode registry, validation helpers, comments, and `travel_service` generation**

Update `product_name_generator.py` so the top of the file becomes mode-aware and extensible. Use this structure as the implementation target:

```python
# -*- coding: utf-8 -*-
"""
多行业商品名生成器模块。

默认保留现卤现捞商品名生成能力，并支持通过顶部模式常量切换到其他行业。
"""

import random  # nosec B311 - 仅用于生成展示型商品名的随机文案，不用于安全场景

# ==============================
# 商品名生成器行业模式开关
# - 这是全局行业模式配置，请勿随意切换。
# - 修改前请先确认当前站点业务场景。
# - 只能填写 PRODUCT_NAME_GENERATOR_MODE_CONFIGS 中已注册的模式值。
# - 若要新增行业，请先补充模式配置，再修改本常量。
# ==============================
PRODUCT_NAME_GENERATOR_MODE = "lomei"

PRODUCT_NAME_GENERATOR_MODE_CONFIGS = {
    "lomei": {
        "display_name": "现卤现捞",
        "fallback_template": "{count}份现捞小吃",
        "foods": [
            "鸭脖", "鸭翅", "鸭掌", "鸭舌", "鸭头", "锁骨",
            "鱼豆腐", "豆皮", "海带结", "藕片", "烤肠", "波波肠",
            "鸡尖", "鹌鹑蛋", "腐竹", "魔芋爽", "大鸡腿", "兰花干",
        ],
        "quantifiers": ["根", "串", "块", "份", "个", "只", "大把", "口"],
        "adj_flavor": [
            "秘制", "麻辣", "五香", "甜辣", "变态辣", "爆辣",
            "酱香", "卤味", "满口香", "红油", "脆皮", "多汁",
            "Q弹", "入味", "鲜嫩", "吮指", "藤椒",
        ],
        "adj_emotion": [
            "寂寞的", "快乐的", "治愈的", "灵魂", "让室友流泪的",
            "高贵的", "卑微的", "暴躁的", "佛系养生的", "充满希望的",
            "绝望的", "初恋般的", "热血的", "深夜的", "独自享用的",
            "令人发指的", "不仅防饿还能防脱发的", "吃完就通过考试的",
            "甚至想再来一份的", "老板含泪推荐的", "也就是个", "减肥路上的绊脚石",
        ],
        "connectors": ["搭配", "配上", "以及", "还有", "加上", "和"],
    },
    "travel_service": {
        "display_name": "旅游服务",
        "fallback_template": "{count}项旅游服务费",
        "items": [
            {"name": "资料打印费", "quantifier": "份"},
            {"name": "短信费", "quantifier": "次"},
        ],
    },
}


def get_supported_product_name_generator_modes():
    return tuple(PRODUCT_NAME_GENERATOR_MODE_CONFIGS.keys())


def validate_product_name_generator_mode(mode=None):
    selected_mode = str(mode if mode is not None else PRODUCT_NAME_GENERATOR_MODE).strip()
    if selected_mode not in PRODUCT_NAME_GENERATOR_MODE_CONFIGS:
        supported = ", ".join(get_supported_product_name_generator_modes())
        raise ValueError(
            f"PRODUCT_NAME_GENERATOR_MODE 配置无效: {selected_mode!r}。"
            f" 允许值: {supported}。"
            " 如需新增行业模式，请先在 PRODUCT_NAME_GENERATOR_MODE_CONFIGS 中注册。"
        )
    return selected_mode
```

Then update `LoMeiGenerator` to load mode-specific config in `__init__()` and keep shared helpers reusable:

```python
class LoMeiGenerator:
    def __init__(self):
        self.mode = validate_product_name_generator_mode()
        self.mode_config = PRODUCT_NAME_GENERATOR_MODE_CONFIGS[self.mode]

        self.foods = self.mode_config.get("foods", [])
        self.quantifiers = self.mode_config.get("quantifiers", [])
        self.adj_flavor = self.mode_config.get("adj_flavor", [])
        self.adj_emotion = self.mode_config.get("adj_emotion", [])
        self.connectors = self.mode_config.get("connectors", [])
        self.travel_service_items = self.mode_config.get("items", [])
        self.fallback_template = self.mode_config["fallback_template"]

        self.zh_nums = list("零一二三四五六七八九")
        self.zh_units = ["", "十", "百", "千", "万"]

    def _build_travel_service_desc(self, count):
        item = random.choice(self.travel_service_items)
        count_str = self._int_to_chinese(count)
        return f"{count_str}{item['quantifier']}{item['name']}"

    def _try_generate_lomei_strategy(self, n):
        # 把当前 _try_generate_strategy() 里的现卤现捞逻辑整体搬到这里
        ...

    def _try_generate_strategy(self, n):
        if self.mode == "travel_service":
            return self._build_travel_service_desc(n)
        return self._try_generate_lomei_strategy(n)

    def generate(self, n):
        if not isinstance(n, int) or n <= 0:
            return None

        max_bytes = 127
        for _ in range(15):
            result = self._try_generate_strategy(n)
            if self._get_byte_len(result) <= max_bytes:
                return result

        return self.fallback_template.format(count=self._int_to_chinese(n))
```

Finish the refactor by updating the module docstring and the export comments at the bottom so they mention multiple modes instead of only “现卤现捞”. Do **not** change the public constructor call shape.

- [ ] **Step 4: Run the generator tests again and verify they pass**

Run:

```bash
python -m unittest tests.test_product_name_generator -v
```

Expected:
- All 5 tests pass.
- Output ends with `OK`.

- [ ] **Step 5: Commit the generator-mode change**

Run:

```bash
git add product_name_generator.py tests/test_product_name_generator.py
git commit -m "$(cat <<'EOF'
feat: add extensible product name generator modes

Add a central mode registry to product_name_generator.py so the existing
lomei flow stays compatible while a new travel_service mode can generate
fixed-quantifier service charge names.
EOF
)"
```

### Task 2: Add startup validation in `main.py` and cover it with focused tests

**Files:**
- Create: `tests/test_product_name_generator_startup.py`
- Modify: `main.py:49497-49518`

- [ ] **Step 1: Write the failing startup-validation tests**

Create `tests/test_product_name_generator_startup.py` with the following content:

```python
import unittest
from unittest import mock

import main as main_module


class TestProductNameGeneratorStartupValidation(unittest.TestCase):
    def test_startup_validation_accepts_registered_mode(self):
        with mock.patch.object(main_module, "PRODUCT_NAME_GENERATOR_MODE", "travel_service", create=True), \
             mock.patch.object(main_module, "validate_product_name_generator_mode") as validate_mode, \
             mock.patch.object(main_module, "logging") as fake_logging:
            main_module._validate_product_name_generator_startup_config()

        validate_mode.assert_called_once_with("travel_service")
        fake_logging.info.assert_called()

    def test_startup_validation_exits_on_invalid_mode(self):
        with mock.patch.object(main_module, "PRODUCT_NAME_GENERATOR_MODE", "broken_mode", create=True), \
             mock.patch.object(
                 main_module,
                 "validate_product_name_generator_mode",
                 side_effect=ValueError("PRODUCT_NAME_GENERATOR_MODE 配置无效: 'broken_mode'"),
             ), \
             mock.patch.object(main_module, "logging") as fake_logging, \
             mock.patch("builtins.print") as fake_print:
            with self.assertRaises(SystemExit) as ctx:
                main_module._validate_product_name_generator_startup_config()

        self.assertEqual(ctx.exception.code, 1)
        fake_print.assert_called_once()
        fake_logging.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the startup-validation test file and verify it fails**

Run:

```bash
python -m unittest tests.test_product_name_generator_startup -v
```

Expected:
- FAIL with `AttributeError` because `_validate_product_name_generator_startup_config()` does not exist yet.

- [ ] **Step 3: Implement the startup validator and call it before app boot continues**

Add a helper near the `main()` entry path in `main.py`:

```python
def _validate_product_name_generator_startup_config():
    try:
        validate_product_name_generator_mode(PRODUCT_NAME_GENERATOR_MODE)
        logging.info(
            "[启动校验] 商品名生成器行业模式配置有效: %s",
            PRODUCT_NAME_GENERATOR_MODE,
        )
    except ValueError as exc:
        message = f"[启动校验] 商品名生成器行业模式配置无效: {exc}"
        print(message)
        logging.error(message)
        raise SystemExit(1) from exc
```

Then update the import block inside `main()` from:

```python
global LoMeiGenerator
if os.path.exists("product_name_generator.py"):
    from product_name_generator import LoMeiGenerator
else:
    raise ImportError("缺少 product_name_generator.py 文件，无法继续运行。")
```

To:

```python
global LoMeiGenerator, PRODUCT_NAME_GENERATOR_MODE, validate_product_name_generator_mode
if os.path.exists("product_name_generator.py"):
    from product_name_generator import (
        LoMeiGenerator,
        PRODUCT_NAME_GENERATOR_MODE,
        validate_product_name_generator_mode,
    )
    _validate_product_name_generator_startup_config()
else:
    raise ImportError("缺少 product_name_generator.py 文件，无法继续运行。")
```

This keeps validation close to the actual startup path and ensures invalid mode values stop the process before the server continues initializing.

- [ ] **Step 4: Run the startup-validation tests again and verify they pass**

Run:

```bash
python -m unittest tests.test_product_name_generator_startup -v
```

Expected:
- Both tests pass.
- Output ends with `OK`.

- [ ] **Step 5: Commit the startup-validation change**

Run:

```bash
git add main.py tests/test_product_name_generator_startup.py
git commit -m "$(cat <<'EOF'
fix: validate product name generator mode at startup

Check the configured product name generator mode during startup so invalid
industry-mode values fail fast before the web server continues booting.
EOF
)"
```

### Task 3: Run regression checks and do a two-mode smoke test

**Files:**
- Modify: none expected
- Test: `tests/test_product_name_generator.py`
- Test: `tests/test_product_name_generator_startup.py`
- Test: `tests/test_payment_order_lifecycle.py`

- [ ] **Step 1: Run the focused regression suite**

Run:

```bash
python -m unittest tests.test_product_name_generator tests.test_product_name_generator_startup tests.test_payment_order_lifecycle -v
```

Expected:
- Existing payment-order tests still pass.
- New generator and startup validation tests pass.
- Output ends with `OK`.

- [ ] **Step 2: Run a direct smoke check for both modes**

Run:

```bash
python - <<'PY'
import product_name_generator as png
from unittest import mock

with mock.patch.object(png, "PRODUCT_NAME_GENERATOR_MODE", "lomei"):
    with mock.patch.object(
        png.random,
        "choice",
        side_effect=["鸭脖", "串", "快乐的", "麻辣", "一串快乐的麻辣鸭脖"],
    ):
        print(png.LoMeiGenerator().generate(1))

with mock.patch.object(png, "PRODUCT_NAME_GENERATOR_MODE", "travel_service"):
    with mock.patch.object(
        png.random,
        "choice",
        return_value={"name": "短信费", "quantifier": "次"},
    ):
        print(png.LoMeiGenerator().generate(2))
PY
```

Expected stdout:

```text
一串快乐的麻辣鸭脖
二次短信费
```

- [ ] **Step 3: Check for a clean working tree before finishing**

Run:

```bash
git status --short
```

Expected:
- No unexpected unstaged files.
- If there are documentation or formatting edits from implementation, review them before deciding whether another commit is needed.
- Do **not** create an empty commit if there are no new changes.

## Self-review checklist completed

- **Spec coverage:**
  - Mode constant with warning comments: Task 1, Step 3
  - Extensible central config table: Task 1, Step 3
  - `travel_service` with fixed item quantifiers: Task 1, Steps 1 and 3
  - Keep `lomei` behavior compatible: Task 1, Steps 1 and 3
  - Startup validation in `main.py`: Task 2, Step 3
  - Fast failure on invalid config: Task 2, Steps 1 and 3
  - Regression confidence: Task 3

- **Placeholder scan:**
  - No `TODO`, `TBD`, or “similar to above” instructions remain.
  - All commands, file paths, and test snippets are concrete.

- **Type and naming consistency:**
  - `PRODUCT_NAME_GENERATOR_MODE`
  - `PRODUCT_NAME_GENERATOR_MODE_CONFIGS`
  - `get_supported_product_name_generator_modes()`
  - `validate_product_name_generator_mode()`
  - `_validate_product_name_generator_startup_config()`

Plan complete and saved to `docs/superpowers/plans/2026-04-15-product-name-generator-modes-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
