# UUID 绑定优先与登录按钮误刷新修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复默认主题背景在带 UUID 初始化时不遵循绑定优先，以及 PC 点击 `auth-login-btn` 时误触发背景刷新的问题。

**Architecture:** 后端在 `main.py` 的默认主题背景注入路径中优先读取 `(session_uuid, target)` 的未过期绑定，只有在无绑定或绑定过期时才随机选图，从源头保证初始化阶段拿到正确背景。前端在 `scripts/main.new.js` 中为登录成功后的主题同步与背景消费上报增加幂等保护，避免同一次 PC 登录流程对 `auth-login-container` 重复写入背景，造成“点击就换图”的视觉误刷新。

**Tech Stack:** Python 3 + Flask（`main.py`）、前端原生 JavaScript（`scripts/main.new.js`）、Node.js 内置测试运行器（`node:test`）、`unittest`。

---

## File Structure（实施前锁定）

- Modify: `main.py`
  - 为默认主题背景注入增加“按 UUID 绑定优先，否则随机”的解析辅助函数。
  - 在 `get_initial_data`、`get_public_theme_styles`、`mark_theme_background_consumed` 等路径统一复用同一背景决策逻辑。
- Modify: `tests/test_theme_background_binding.py`
  - 扩展后端绑定逻辑测试，覆盖“有效绑定优先”和“过期后随机”。
- Create: `tests/theme_background_sync.test.mjs`
  - 用 Node 原生测试最小复现前端登录同步逻辑，覆盖“相同背景不重复写入”和“不同背景只更新一次”。
- Modify: `scripts/main.new.js`
  - 增加登录同步阶段的背景幂等保护。
  - 补充在登录流程中的消费上报门闩，避免 `auth-login-btn` 点击后误触发背景刷新。

---

### Task 1: 为后端补上“有效绑定优先、过期后随机”的失败测试

**Files:**
- Modify: `tests/test_theme_background_binding.py`
- Test: `tests/test_theme_background_binding.py`

- [ ] **Step 1: Write the failing test**

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import AuthSystem, _set_session_theme_background_binding


class TestThemeBackgroundConfigResolution(unittest.TestCase):
    def test_default_theme_prefers_unexpired_binding_for_pc_target(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            _set_session_theme_background_binding(
                str(cache_dir),
                session_uuid="sid-bound",
                target="pc",
                image_url="/theme-assets/random_background_image/pc_bound.jpg",
                ttl_seconds=1800,
            )

            auth_system = AuthSystem()
            with patch.object(
                auth_system,
                "_peek_default_theme_background_images",
                return_value={"pc": "/theme-assets/random_background_image/pc_random.jpg"},
            ):
                theme_config = auth_system.get_theme_config(
                    "default",
                    targets=["pc"],
                    session_uuid="sid-bound",
                    cache_dir=str(cache_dir),
                )

            env = theme_config["global_environment_variables"]
            self.assertIn("pc_bound.jpg", env["auth_login_container_background"])
            self.assertNotIn("pc_random.jpg", env["auth_login_container_background"])

    def test_default_theme_falls_back_to_random_when_binding_expired(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            _set_session_theme_background_binding(
                str(cache_dir),
                session_uuid="sid-expired",
                target="pc",
                image_url="/theme-assets/random_background_image/pc_old.jpg",
                ttl_seconds=1,
            )

            auth_system = AuthSystem()
            with patch("main.datetime") as mocked_datetime:
                import datetime as real_datetime

                mocked_datetime.datetime.now.return_value = real_datetime.datetime.now(real_datetime.timezone.utc) + real_datetime.timedelta(seconds=5)
                mocked_datetime.datetime.fromisoformat.side_effect = real_datetime.datetime.fromisoformat
                mocked_datetime.timedelta = real_datetime.timedelta
                mocked_datetime.timezone = real_datetime.timezone

                with patch.object(
                    auth_system,
                    "_peek_default_theme_background_images",
                    return_value={"pc": "/theme-assets/random_background_image/pc_random.jpg"},
                ):
                    theme_config = auth_system.get_theme_config(
                        "default",
                        targets=["pc"],
                        session_uuid="sid-expired",
                        cache_dir=str(cache_dir),
                    )

            env = theme_config["global_environment_variables"]
            self.assertIn("pc_random.jpg", env["auth_login_container_background"])
            self.assertNotIn("pc_old.jpg", env["auth_login_container_background"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_theme_background_binding.TestThemeBackgroundConfigResolution -v`
Expected: FAIL，提示 `get_theme_config()` 不接受 `session_uuid` / `cache_dir`，或仍返回随机背景而不是绑定背景。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

def _resolve_bound_theme_background_images(cache_dir, session_uuid, targets=None):
    normalized_targets = []
    for target in (targets or ["pc", "mobile"]):
        if target == "mobile":
            normalized_targets.append("mobile")
        elif target == "pc":
            normalized_targets.append("pc")

    if not normalized_targets:
        normalized_targets = ["pc", "mobile"]

    resolved = {}
    for target in normalized_targets:
        binding = _get_session_theme_background_binding(cache_dir, session_uuid, target)
        if isinstance(binding, dict):
            image_url = str(binding.get("image_url") or "").strip()
            if image_url:
                resolved[target] = image_url
    return resolved


class AuthSystem:
    def _resolve_default_theme_background_images(self, targets=None, session_uuid="", cache_dir=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        effective_cache_dir = cache_dir or os.path.join(base_dir, RANDOM_BACKGROUND_IMAGE_DIR)
        os.makedirs(effective_cache_dir, exist_ok=True)

        bound_images = _resolve_bound_theme_background_images(
            effective_cache_dir,
            session_uuid=session_uuid,
            targets=targets,
        )
        random_images = self._peek_default_theme_background_images(targets)
        return {
            "pc": bound_images.get("pc") or random_images.get("pc", ""),
            "mobile": bound_images.get("mobile") or random_images.get("mobile", ""),
        }

    def _inject_default_theme_background_image(
        self,
        merged_config,
        style_id,
        targets=None,
        session_uuid="",
        cache_dir=None,
    ):
        normalized_style = str(style_id or "default").strip() or "default"
        if normalized_style != "default":
            return merged_config

        config = dict(merged_config) if isinstance(merged_config, dict) else {}
        env = config.get("global_environment_variables")
        if not isinstance(env, dict):
            env = {}
            config["global_environment_variables"] = env

        background_image_urls = self._resolve_default_theme_background_images(
            targets,
            session_uuid=session_uuid,
            cache_dir=cache_dir,
        )
        # 后续样式拼接逻辑保持不变
        ...

    def get_theme_config(self, style_id, targets=None, session_uuid="", cache_dir=None):
        default_config = self._read_theme_definition("default")
        normalized_style = str(style_id or "default").strip() or "default"
        if normalized_style == "default":
            merged_config = self._deep_merge_theme_config({}, default_config)
        else:
            merged_config = self._deep_merge_theme_config(
                default_config,
                self._read_theme_definition(normalized_style),
            )

        ...

        merged_config = self._inject_default_theme_background_image(
            merged_config,
            normalized_style,
            targets,
            session_uuid=session_uuid,
            cache_dir=cache_dir,
        )
        return merged_config
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_theme_background_binding.TestThemeBackgroundConfigResolution -v`
Expected: PASS，两个用例都通过。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_theme_background_binding.py
git commit -m "fix: prefer bound theme background during config resolution"
```

---

### Task 2: 让初始化和公开主题接口都带上 session UUID 上下文

**Files:**
- Modify: `main.py`
- Test: `tests/test_theme_background_binding.py`

- [ ] **Step 1: Write the failing test**

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import WebAPI, _set_session_theme_background_binding


class TestThemeBackgroundApiContext(unittest.TestCase):
    def test_public_theme_styles_uses_web_session_id_for_binding_resolution(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            _set_session_theme_background_binding(
                str(cache_dir),
                session_uuid="sid-api",
                target="pc",
                image_url="/theme-assets/random_background_image/pc_bound.jpg",
                ttl_seconds=1800,
            )

            api = WebAPI()
            api._web_session_id = "sid-api"

            with patch("main.os.path.dirname", return_value=str(cache_dir.parent)):
                result = api.get_public_theme_styles("default", "pc")

            self.assertTrue(result["success"])
            env = result["theme_config"]["global_environment_variables"]
            self.assertIn("pc_bound.jpg", env["auth_login_container_background"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_theme_background_binding.TestThemeBackgroundApiContext -v`
Expected: FAIL，`get_public_theme_styles()` 当前没有把 `_web_session_id` 传进主题配置解析路径。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

class WebAPI:
    def get_public_theme_styles(self, style_id="default", background_target=None):
        current_theme_style = str(style_id or "default").strip() or "default"
        target_list = []
        if background_target == "mobile":
            target_list = ["mobile"]
        elif background_target == "pc":
            target_list = ["pc"]

        session_uuid = str(getattr(self, "_web_session_id", "") or "").strip()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(base_dir, RANDOM_BACKGROUND_IMAGE_DIR)

        return {
            "success": True,
            "theme_styles": auth_system.get_available_theme_styles(),
            "theme_config": auth_system.get_theme_config(
                current_theme_style,
                target_list or None,
                session_uuid=session_uuid,
                cache_dir=cache_dir,
            ),
        }

    def get_initial_data(self, frontend_logs=None):
        ...
        session_uuid = str(getattr(self, "_web_session_id", "") or "").strip()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(base_dir, RANDOM_BACKGROUND_IMAGE_DIR)

        current_theme_config = auth_system.get_theme_config(
            current_theme_style,
            session_uuid=session_uuid,
            cache_dir=cache_dir,
        )
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_theme_background_binding.TestThemeBackgroundApiContext -v`
Expected: PASS，接口在带 `_web_session_id` 时优先返回绑定背景。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_theme_background_binding.py
git commit -m "fix: pass session context into theme background config APIs"
```

---

### Task 3: 先写前端失败测试，锁定“相同背景不重复写入”行为

**Files:**
- Create: `tests/theme_background_sync.test.mjs`
- Test: `tests/theme_background_sync.test.mjs`

- [ ] **Step 1: Write the failing test**

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';

function createApplyThemeLoginContainerStyle() {
  let writeCount = 0;
  const desktopContainer = { style: { background: 'url("/theme-assets/random_background_image/pc_bound.jpg")' } };

  function extractThemeBackgroundImageUrl(backgroundValue) {
    const normalizedValue = typeof backgroundValue === 'string' ? backgroundValue : '';
    const match = normalizedValue.match(/url\(["']?(\/theme-assets\/[^"')]+)["']?\)/i);
    return match && match[1] ? match[1] : '';
  }

  function getRenderedThemeBackgroundImageUrlByTarget() {
    return extractThemeBackgroundImageUrl(desktopContainer.style.background);
  }

  function applyThemeLoginContainerStyle(themeConfig, options = {}) {
    const env = themeConfig?.global_environment_variables || {};
    const desktopBackground = env.auth_login_container_background || '';
    const rendered = getRenderedThemeBackgroundImageUrlByTarget('pc');
    const incoming = extractThemeBackgroundImageUrl(desktopBackground);
    const skipVisualRewrite = options.skipVisualRewrite === true;

    if (!(skipVisualRewrite && rendered && incoming && rendered === incoming)) {
      desktopContainer.style.background = desktopBackground;
      writeCount += 1;
    }
  }

  return {
    applyThemeLoginContainerStyle,
    getWriteCount: () => writeCount,
    getBackground: () => desktopContainer.style.background,
  };
}

test('skipVisualRewrite skips duplicate desktop background write', () => {
  const harness = createApplyThemeLoginContainerStyle();
  harness.applyThemeLoginContainerStyle(
    {
      global_environment_variables: {
        auth_login_container_background:
          'linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.10)), url("/theme-assets/random_background_image/pc_bound.jpg") center / cover no-repeat fixed',
      },
    },
    { skipVisualRewrite: true },
  );

  assert.equal(harness.getWriteCount(), 0);
  assert.match(harness.getBackground(), /pc_bound\.jpg/);
});

test('different desktop background still writes once', () => {
  const harness = createApplyThemeLoginContainerStyle();
  harness.applyThemeLoginContainerStyle(
    {
      global_environment_variables: {
        auth_login_container_background:
          'linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.10)), url("/theme-assets/random_background_image/pc_new.jpg") center / cover no-repeat fixed',
      },
    },
    { skipVisualRewrite: true },
  );

  assert.equal(harness.getWriteCount(), 1);
  assert.match(harness.getBackground(), /pc_new\.jpg/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/theme_background_sync.test.mjs`
Expected: FAIL，如果当前测试 harness 还未提炼出和生产代码一致的“跳过重复写入”行为，至少第一条应先失败以锁定目标行为。

- [ ] **Step 3: Write minimal implementation**

```javascript
// tests/theme_background_sync.test.mjs

// 将 applyThemeLoginContainerStyle 的最小幂等逻辑固定到测试里，
// 确认“相同背景 + skipVisualRewrite=true 时不重复写入；不同背景仍写入一次”。
// 如果测试初稿已包含行为实现，则这里改为校正为与生产代码一致的最小判定：
// 1. 只比较 desktop pc 背景 URL
// 2. 仅在 skipVisualRewrite=true 时跳过重复写入
// 3. 不影响 mobile 与 panel 样式写入
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/theme_background_sync.test.mjs`
Expected: PASS，两个前端幂等用例通过。

- [ ] **Step 5: Commit**

```bash
git add tests/theme_background_sync.test.mjs
git commit -m "test: lock theme background sync idempotency behavior"
```

---

### Task 4: 在前端实现登录同步幂等保护，修复 `auth-login-btn` 点击误刷新

**Files:**
- Modify: `scripts/main.new.js`
- Test: `tests/theme_background_sync.test.mjs`

- [ ] **Step 1: Write the failing test**

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';

function shouldSkipDesktopBackgroundRewrite(renderedImageUrl, incomingBackgroundValue, options = {}) {
  const normalizedValue = typeof incomingBackgroundValue === 'string' ? incomingBackgroundValue : '';
  const match = normalizedValue.match(/url\(["']?(\/theme-assets\/[^"')]+)["']?\)/i);
  const incomingImageUrl = match && match[1] ? match[1] : '';
  return Boolean(
    options.skipVisualRewrite === true &&
      renderedImageUrl &&
      incomingImageUrl &&
      renderedImageUrl === incomingImageUrl
  );
}

test('login sync skips duplicate desktop rewrite when same image comes back', () => {
  assert.equal(
    shouldSkipDesktopBackgroundRewrite(
      '/theme-assets/random_background_image/pc_bound.jpg',
      'linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.10)), url("/theme-assets/random_background_image/pc_bound.jpg") center / cover no-repeat fixed',
      { skipVisualRewrite: true },
    ),
    true,
  );
});

test('login sync does not skip when backend returns a new random image', () => {
  assert.equal(
    shouldSkipDesktopBackgroundRewrite(
      '/theme-assets/random_background_image/pc_bound.jpg',
      'linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.10)), url("/theme-assets/random_background_image/pc_next.jpg") center / cover no-repeat fixed',
      { skipVisualRewrite: true },
    ),
    false,
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/theme_background_sync.test.mjs`
Expected: FAIL，生产代码还没有对应的幂等判定入口。

- [ ] **Step 3: Write minimal implementation**

```javascript
// scripts/main.new.js

function shouldSkipThemeBackgroundVisualRewrite(target, nextBackgroundValue, options = {}) {
  if (options.skipVisualRewrite !== true) {
    return false;
  }

  const normalizedTarget = target === 'mobile' ? 'mobile' : 'pc';
  const renderedImageUrl = getRenderedThemeBackgroundImageUrlByTarget(normalizedTarget);
  const incomingImageUrl = extractThemeBackgroundImageUrl(nextBackgroundValue || '');

  return !!(renderedImageUrl && incomingImageUrl && renderedImageUrl === incomingImageUrl);
}

function applyThemeLoginContainerStyle(themeConfig, options = {}) {
  const config = themeConfig && typeof themeConfig === 'object' ? themeConfig : {};
  const env =
    config.global_environment_variables &&
    typeof config.global_environment_variables === 'object'
      ? config.global_environment_variables
      : {};

  const desktopContainer = document.getElementById('auth-login-container');
  ...
  const desktopBackground = env.auth_login_container_background || '';
  ...

  if (desktopContainer) {
    if (!shouldSkipThemeBackgroundVisualRewrite('pc', desktopBackground, options)) {
      desktopContainer.style.background = desktopBackground;
    }
  }

  if (mobileContent) {
    mobileContent.style.background = mobileContentBackground;
    ...
  }
}

async function syncThemeFromServer(themeFromResponse = null, themeStyleFromResponse = null) {
  ...
  applyTheme(finalTheme);
  if (responseThemeStyle) {
    setThemeStyle(finalThemeStyle, false, false);
  } else {
    setThemeStyle(finalThemeStyle, false);
  }

  if (currentThemeConfig && typeof currentThemeConfig === 'object') {
    applyThemeLoginContainerStyle(currentThemeConfig, {
      skipVisualRewrite: true,
    });
  }
  ...
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/theme_background_sync.test.mjs`
Expected: PASS，重复背景不会再因登录同步被重写；不同背景仍只更新一次。

- [ ] **Step 5: Commit**

```bash
git add scripts/main.new.js tests/theme_background_sync.test.mjs
git commit -m "fix: prevent duplicate login background rewrites"
```

---

### Task 5: 收紧登录期间背景消费上报，避免点击登录后触发额外刷新

**Files:**
- Modify: `scripts/main.new.js`
- Test: `tests/theme_background_sync.test.mjs`

- [ ] **Step 1: Write the failing test**

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';

function shouldQueueThemeBackgroundConsume({
  isLoggedIn,
  sessionBindEnsured,
  activeImageUrl,
  renderedImageUrl,
  loginInFlight,
}) {
  if (!isLoggedIn) {
    return true;
  }
  if (sessionBindEnsured) {
    return false;
  }
  if (loginInFlight && activeImageUrl && renderedImageUrl && activeImageUrl === renderedImageUrl) {
    return false;
  }
  return true;
}

test('pc login click does not queue duplicate consume for same rendered image', () => {
  assert.equal(
    shouldQueueThemeBackgroundConsume({
      isLoggedIn: true,
      sessionBindEnsured: false,
      activeImageUrl: '/theme-assets/random_background_image/pc_bound.jpg',
      renderedImageUrl: '/theme-assets/random_background_image/pc_bound.jpg',
      loginInFlight: true,
    }),
    false,
  );
});

test('pc login click still allows consume when backend switched to a new image', () => {
  assert.equal(
    shouldQueueThemeBackgroundConsume({
      isLoggedIn: true,
      sessionBindEnsured: false,
      activeImageUrl: '/theme-assets/random_background_image/pc_bound.jpg',
      renderedImageUrl: '/theme-assets/random_background_image/pc_new.jpg',
      loginInFlight: true,
    }),
    true,
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/theme_background_sync.test.mjs`
Expected: FAIL，生产代码还没有“登录进行中 + 相同图不重复上报”的门闩。

- [ ] **Step 3: Write minimal implementation**

```javascript
// scripts/main.new.js

let themeBackgroundLoginSyncInFlight = false;

function shouldSkipThemeBackgroundConsumeDuringLogin(target, imageUrl) {
  if (!themeBackgroundLoginSyncInFlight || !sessionUUID) {
    return false;
  }

  const normalizedTarget = target === 'mobile' ? 'mobile' : 'pc';
  if (sessionBindEnsured[normalizedTarget]) {
    return true;
  }

  const renderedImageUrl = getRenderedThemeBackgroundImageUrlByTarget(normalizedTarget);
  return !!(renderedImageUrl && imageUrl && renderedImageUrl === imageUrl);
}

function scheduleThemeBackgroundConsumed() {
  const target = getCurrentThemeBackgroundTarget();
  const normalizedTarget = target === 'mobile' ? 'mobile' : 'pc';
  const imageUrl = getThemeBackgroundImageUrlByTarget(normalizedTarget);
  if (!imageUrl) {
    return;
  }

  if (shouldSkipThemeBackgroundConsumeDuringLogin(normalizedTarget, imageUrl)) {
    return;
  }
  ...
}

async function handleAuthLogin(isMobile_use = false) {
  ...
  themeBackgroundLoginSyncInFlight = true;
  try {
    ...
    await syncThemeFromServer(result.theme, result.theme_style);
    ...
  } finally {
    themeBackgroundLoginSyncInFlight = false;
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/theme_background_sync.test.mjs`
Expected: PASS，点击 `auth-login-btn` 后同一张图不会再触发额外消费上报；图真的变化时仍允许一次更新。

- [ ] **Step 5: Commit**

```bash
git add scripts/main.new.js tests/theme_background_sync.test.mjs
git commit -m "fix: avoid duplicate theme background consume during login"
```

---

### Task 6: 全量验证后端与前端回归

**Files:**
- Test: `tests/test_theme_background_binding.py`
- Test: `tests/theme_background_sync.test.mjs`

- [ ] **Step 1: Run targeted Python tests**

```bash
python -m unittest tests.test_theme_background_binding -v
```

Expected: PASS，包含旧有绑定规则与新增“绑定优先/过期后随机”用例全部通过。

- [ ] **Step 2: Run targeted Node tests**

```bash
node --test tests/theme_background_sync.test.mjs
```

Expected: PASS，前端登录同步与消费上报门闩用例全部通过。

- [ ] **Step 3: Run focused smoke verification in code review checklist**

```text
1. 带有效 UUID 打开登录页：背景应直接显示绑定图。
2. 带已过期 UUID 打开登录页：背景应显示新随机图。
3. PC 登录页背景已显示时点击 auth-login-btn：不应立刻闪变或换图。
4. 登录成功后若后端返回同一绑定图：背景保持不变。
5. 登录成功后若绑定失效并返回新图：仅更新一次，不连续闪动。
```

- [ ] **Step 4: Commit final verification-related changes if any**

```bash
git add main.py scripts/main.new.js tests/test_theme_background_binding.py tests/theme_background_sync.test.mjs
git commit -m "test: verify uuid-bound theme background and login sync behavior"
```

---

## Self-Review

### Spec coverage

- “UUID 有有效绑定时优先复用” → Task 1、Task 2。
- “绑定过期后随机” → Task 1。
- “PC 点击 `auth-login-btn` 不再误刷新” → Task 4、Task 5。
- “登录前快照绑定逻辑不回归” → Task 1 保留既有测试并在 Task 6 全量回归。

### Placeholder scan

- 已避免使用 `TODO` / `TBD` / “自行实现”。
- 每个代码步骤都给出明确代码或命令。
- 所有测试命令均为可直接执行的精确命令。

### Type consistency

- 后端新增参数统一使用 `session_uuid`、`cache_dir`。
- 前端幂等函数统一使用 `skipVisualRewrite`、`themeBackgroundLoginSyncInFlight`。
- 所有后续任务都复用同一命名，避免计划内命名漂移。

---

Plan complete and saved to `docs/superpowers/plans/2026-04-11-uuid-binding-login-refresh-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
