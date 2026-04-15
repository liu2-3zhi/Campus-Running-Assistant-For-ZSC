# 默认主题随机背景图绑定与重复登录修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复默认主题随机背景图的重复消耗与登录后复用问题，实现 `(sessionUUID, target)` 30 分钟绑定、匿名重登覆盖绑定，以及重复登录 cookie 轮换且不误报多端登录。

**Architecture:** 后端在 `random_background_image/index.json` 中新增 `session_bindings`，由 `main.py` 在主题背景选择与“已使用背景”上报路径中统一执行绑定/续期/覆盖。前端在 `scripts/main.new.js` 引入“未登录首稳态一次消耗 + 登录后按 target ensure-bind 一次”的状态门闩，避免加载期间重复请求。登录流程统一使用认证结果中的标准用户名，避免手机号登录路径导致会话清理与告警误判。

**Tech Stack:** Python 3 + Flask（`main.py`）、前端原生 JavaScript（`scripts/main.new.js`）、`unittest`。

---

## File Structure（实施前锁定）

- Modify: `main.py`
  - 扩展随机背景索引读写结构（`session_bindings`）
  - 新增/调整默认主题背景绑定解析函数
  - 升级 `mark_theme_background_consumed` 语义为 ensure-bind + login_context 覆盖
  - 修复 `/auth/login` 中登录用户名归一化与多端提示判定
- Modify: `scripts/main.new.js`
  - 新增背景消耗门闩状态（匿名首稳态 / 登录 ensure-bind）
  - 调整 `scheduleThemeBackgroundConsumed` / `notifyThemeBackgroundConsumed`
  - 登录成功后携带 `login_context` + `candidate_image_url` 触发覆盖绑定
- Create: `tests/test_theme_background_binding.py`
  - 覆盖索引结构兼容、绑定 TTL、覆盖绑定与过期切换
- Create: `tests/test_auth_login_helpers.py`
  - 覆盖登录用户名归一化与多端提示判定辅助函数

---

### Task 1: 为随机背景索引增加 `session_bindings` 与 TTL 绑定辅助函数（TDD）

**Files:**
- Modify: `main.py`（`_load_random_background_index`、`_save_random_background_index` 附近）
- Test: `tests/test_theme_background_binding.py`

- [ ] **Step 1: Write the failing test**

```python
import tempfile
import unittest
from pathlib import Path

from main import (
    _load_random_background_index,
    _save_random_background_index,
    _set_session_theme_background_binding,
    _get_session_theme_background_binding,
)


class TestThemeBackgroundBinding(unittest.TestCase):
    def test_index_backward_compatible_with_session_bindings(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            index = _load_random_background_index(str(cache_dir))
            self.assertIn("files", index)
            self.assertIn("feedback", index)
            self.assertIn("session_bindings", index)

            index["session_bindings"]["sid-1"] = {
                "pc": {
                    "image_url": "/theme-assets/random_background_image/pc_a.jpg",
                    "bound_at": "2026-04-09T10:00:00+08:00",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                }
            }
            _save_random_background_index(str(cache_dir), index)
            reloaded = _load_random_background_index(str(cache_dir))
            self.assertIn("sid-1", reloaded["session_bindings"])

    def test_set_and_get_binding(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            _set_session_theme_background_binding(
                str(cache_dir),
                session_uuid="sid-2",
                target="pc",
                image_url="/theme-assets/random_background_image/pc_b.jpg",
                ttl_seconds=1800,
            )
            binding = _get_session_theme_background_binding(
                str(cache_dir), "sid-2", "pc"
            )
            self.assertIsNotNone(binding)
            self.assertEqual(
                binding["image_url"],
                "/theme-assets/random_background_image/pc_b.jpg",
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_theme_background_binding -v`
Expected: FAIL with `ImportError` / `AttributeError`（新函数尚未实现）。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

def _load_random_background_index(cache_dir):
    index_path = os.path.join(cache_dir, "index.json")
    default_index = {"files": {}, "feedback": {}, "session_bindings": {}}
    try:
        if not os.path.exists(index_path):
            return default_index
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default_index
        files = data.get("files") if isinstance(data.get("files"), dict) else {}
        feedback = data.get("feedback") if isinstance(data.get("feedback"), dict) else {}
        session_bindings = (
            data.get("session_bindings")
            if isinstance(data.get("session_bindings"), dict)
            else {}
        )
        return {
            "files": files,
            "feedback": feedback,
            "session_bindings": session_bindings,
        }
    except Exception:
        return default_index


def _save_random_background_index(cache_dir, index_data):
    index_path = os.path.join(cache_dir, "index.json")
    safe_index = {
        "files": index_data.get("files", {}) if isinstance(index_data, dict) else {},
        "feedback": index_data.get("feedback", {}) if isinstance(index_data, dict) else {},
        "session_bindings": (
            index_data.get("session_bindings", {}) if isinstance(index_data, dict) else {}
        ),
    }
    tmp = f"{index_path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(safe_index, f, indent=2, ensure_ascii=False)
    os.replace(tmp, index_path)


def _set_session_theme_background_binding(cache_dir, session_uuid, target, image_url, ttl_seconds=1800):
    sid = str(session_uuid or "").strip()
    if not sid:
        return None
    normalized_target = "mobile" if str(target).lower() == "mobile" else "pc"
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(seconds=max(int(ttl_seconds or 0), 1))

    index = _load_random_background_index(cache_dir)
    bindings = index.setdefault("session_bindings", {})
    sid_entry = bindings.setdefault(sid, {})
    sid_entry[normalized_target] = {
        "image_url": str(image_url or "").strip(),
        "bound_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    _save_random_background_index(cache_dir, index)
    return sid_entry[normalized_target]


def _get_session_theme_background_binding(cache_dir, session_uuid, target):
    sid = str(session_uuid or "").strip()
    if not sid:
        return None
    normalized_target = "mobile" if str(target).lower() == "mobile" else "pc"
    index = _load_random_background_index(cache_dir)
    bindings = index.get("session_bindings", {})
    sid_entry = bindings.get(sid, {}) if isinstance(bindings, dict) else {}
    entry = sid_entry.get(normalized_target) if isinstance(sid_entry, dict) else None
    if not isinstance(entry, dict):
        return None

    expires_at = entry.get("expires_at")
    if not expires_at:
        return None
    try:
        expire_dt = datetime.datetime.fromisoformat(str(expires_at))
    except Exception:
        return None
    if expire_dt <= datetime.datetime.now(datetime.timezone.utc):
        sid_entry.pop(normalized_target, None)
        if not sid_entry:
            bindings.pop(sid, None)
        _save_random_background_index(cache_dir, index)
        return None
    return entry
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_theme_background_binding -v`
Expected: PASS（上述两个用例通过）。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_theme_background_binding.py
git commit -m "feat: add session-based theme background binding storage"
```

---

### Task 2: 实现 ensure-bind 核心规则（命中复用、过期换图、login_context 覆盖）

**Files:**
- Modify: `main.py`（`mark_theme_background_consumed` 与默认主题背景选择逻辑）
- Test: `tests/test_theme_background_binding.py`

- [ ] **Step 1: Write the failing test**

```python
import tempfile
import unittest
from pathlib import Path

from main import _resolve_theme_background_binding_decision


class TestThemeBindingDecision(unittest.TestCase):
    def test_reuse_unexpired_binding(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            result = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-reuse",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_1.jpg",
                login_context=False,
                candidate_image_url="",
                ttl_seconds=1800,
            )
            self.assertEqual(result["action"], "bind_new")

            result2 = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-reuse",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_2.jpg",
                login_context=False,
                candidate_image_url="",
                ttl_seconds=1800,
            )
            self.assertEqual(result2["action"], "reuse_existing")
            self.assertEqual(result2["selected_image_url"], "/theme-assets/random_background_image/pc_1.jpg")

    def test_login_context_overrides_unexpired_binding(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-override",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_old.jpg",
                login_context=False,
                candidate_image_url="",
                ttl_seconds=1800,
            )
            result = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-override",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_old.jpg",
                login_context=True,
                candidate_image_url="/theme-assets/random_background_image/pc_new.jpg",
                ttl_seconds=1800,
            )
            self.assertEqual(result["action"], "override_binding")
            self.assertEqual(result["selected_image_url"], "/theme-assets/random_background_image/pc_new.jpg")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_theme_background_binding.TestThemeBindingDecision -v`
Expected: FAIL（决策函数尚未实现）。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

def _resolve_theme_background_binding_decision(
    cache_dir,
    session_uuid,
    target,
    current_image_url,
    login_context=False,
    candidate_image_url="",
    ttl_seconds=1800,
):
    existing = _get_session_theme_background_binding(cache_dir, session_uuid, target)
    normalized_candidate = str(candidate_image_url or "").strip()

    if login_context and normalized_candidate:
        _set_session_theme_background_binding(
            cache_dir,
            session_uuid=session_uuid,
            target=target,
            image_url=normalized_candidate,
            ttl_seconds=ttl_seconds,
        )
        return {"action": "override_binding", "selected_image_url": normalized_candidate}

    if existing and existing.get("image_url"):
        return {"action": "reuse_existing", "selected_image_url": str(existing.get("image_url"))}

    selected = str(current_image_url or "").strip()
    if selected:
        _set_session_theme_background_binding(
            cache_dir,
            session_uuid=session_uuid,
            target=target,
            image_url=selected,
            ttl_seconds=ttl_seconds,
        )
        return {"action": "bind_new", "selected_image_url": selected}

    return {"action": "noop", "selected_image_url": ""}
```

并在 `mark_theme_background_consumed` 中接入：

```python
# main.py (inside mark_theme_background_consumed)

def mark_theme_background_consumed(self, target="pc", image_url="", login_context=False, candidate_image_url=""):
    normalized_target = "mobile" if str(target or "").strip().lower() == "mobile" else "pc"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(base_dir, RANDOM_BACKGROUND_IMAGE_DIR)
    os.makedirs(cache_dir, exist_ok=True)

    session_uuid = str(getattr(self, "_web_session_id", "") or "").strip()
    decision = _resolve_theme_background_binding_decision(
        cache_dir=cache_dir,
        session_uuid=session_uuid,
        target=normalized_target,
        current_image_url=str(image_url or "").strip(),
        login_context=bool(login_context),
        candidate_image_url=str(candidate_image_url or "").strip(),
        ttl_seconds=1800,
    )

    next_theme_config = auth_system.get_theme_config("default", [normalized_target])
    return {
        "success": True,
        "theme_config": next_theme_config,
        "binding_action": decision.get("action", "noop"),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_theme_background_binding -v`
Expected: PASS（新增决策用例通过）。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_theme_background_binding.py
git commit -m "feat: implement ensure-bind and login-context override for theme backgrounds"
```

---

### Task 3: 前端消耗状态机改造（首稳态一次 + 登录 ensure-bind）

**Files:**
- Modify: `scripts/main.new.js`
- Test: 手工验证（浏览器）

- [ ] **Step 1: Add failing behavioral checks (manual checklist)**

```text
Case A: 未登录打开 / ，观察 Network：
- /api/public/theme_background/consume 只应成功触发 1 次。

Case B: 未登录打开 / 后触发多次主题应用（切换主题、窗口 resize）：
- 不应新增 consume 请求。

Case C: 未登录拿到图后登录：
- 登录请求后会触发 ensure-bind；返回主题图在 30 分钟内稳定。
```

- [ ] **Step 2: Verify current behavior fails checklist**

Run manually in browser DevTools Network.
Expected: 现状会出现重复 consume 或登录后不稳定复用。

- [ ] **Step 3: Write minimal implementation**

```javascript
// scripts/main.new.js
let initialConsumeDone = { pc: false, mobile: false };
let sessionBindEnsured = { pc: false, mobile: false };
let anonConsumedBackgroundByTarget = { pc: "", mobile: "" };

function resetThemeBackgroundConsumeStateAfterLogin() {
  sessionBindEnsured = { pc: false, mobile: false };
}

function shouldSendThemeBackgroundConsume(target) {
  const normalizedTarget = target === "mobile" ? "mobile" : "pc";
  if (sessionUUID) {
    return !sessionBindEnsured[normalizedTarget];
  }
  return !initialConsumeDone[normalizedTarget];
}

async function notifyThemeBackgroundConsumed(target, imageUrlOverride = null, options = {}) {
  const normalizedTarget = target === "mobile" ? "mobile" : "pc";
  const imageUrl =
    typeof imageUrlOverride === "string" && imageUrlOverride
      ? imageUrlOverride
      : getThemeBackgroundImageUrlByTarget(normalizedTarget);

  if (!imageUrl || !shouldSendThemeBackgroundConsume(normalizedTarget)) return;

  const payload = {
    target: normalizedTarget,
    image_url: imageUrl,
    login_context: !!options.loginContext,
    candidate_image_url: options.candidateImageUrl || "",
  };

  if (sessionUUID) {
    const result = await callPythonAPI("mark_theme_background_consumed", payload);
    if (result && result.success) {
      sessionBindEnsured[normalizedTarget] = true;
      if (result.theme_config) {
        currentThemeConfig = result.theme_config;
        applyThemeLoginContainerStyle(currentThemeConfig);
      }
    }
    return;
  }

  const response = await fetch("/api/public/theme_background/consume", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`HTTP错误: ${response.status}`);
  initialConsumeDone[normalizedTarget] = true;
  anonConsumedBackgroundByTarget[normalizedTarget] = imageUrl;
}
```

并在登录成功后调用：

```javascript
// scripts/main.new.js (inside login success branch)
resetThemeBackgroundConsumeStateAfterLogin();
const loginTarget = getCurrentThemeBackgroundTarget();
await notifyThemeBackgroundConsumed(
  loginTarget,
  null,
  {
    loginContext: true,
    candidateImageUrl: anonConsumedBackgroundByTarget[loginTarget] || "",
  }
);
```

- [ ] **Step 4: Re-run manual checklist to verify pass**

Run manually in browser DevTools Network.
Expected:
- 未登录阶段单次页面加载仅一次 consume。
- 登录后触发 ensure-bind，并稳定复用 30 分钟。
- 同会话切换 target 时仅首次 ensure。

- [ ] **Step 5: Commit**

```bash
git add scripts/main.new.js
git commit -m "fix: debounce and gate theme background consumption across login states"
```

---

### Task 4: 修复登录流程用户名归一化与多端登录误报

**Files:**
- Modify: `main.py`（`/auth/login`）
- Test: `tests/test_auth_login_helpers.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from main import _normalize_login_username_for_session_ops, _should_emit_multi_device_warning


class TestAuthLoginHelpers(unittest.TestCase):
    def test_normalize_login_username(self):
        auth_result = {"auth_username": "real_user"}
        self.assertEqual(
            _normalize_login_username_for_session_ops(auth_result, ""),
            "real_user",
        )

    def test_should_emit_multi_device_warning(self):
        self.assertFalse(_should_emit_multi_device_warning([], same_browser_relogin=True))
        self.assertFalse(_should_emit_multi_device_warning(["sid1"], same_browser_relogin=True))
        self.assertTrue(_should_emit_multi_device_warning(["sid1"], same_browser_relogin=False))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_auth_login_helpers -v`
Expected: FAIL（辅助函数未实现）。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

def _normalize_login_username_for_session_ops(auth_result, fallback_username=""):
    if isinstance(auth_result, dict):
        resolved = str(auth_result.get("auth_username") or "").strip()
        if resolved:
            return resolved
    return str(fallback_username or "").strip()


def _should_emit_multi_device_warning(kicked_sessions, same_browser_relogin=False):
    valid = [s for s in (kicked_sessions or []) if str(s or "").strip()]
    return bool(valid) and not bool(same_browser_relogin)
```

并在 `/auth/login` 中替换变量使用：

```python
# main.py (inside auth_login)
normalized_auth_username = _normalize_login_username_for_session_ops(auth_result, auth_username)

# 用 normalized_auth_username 执行：
# - check_single_session_enforcement
# - link_session_to_user
# - token_manager.create_token
# - token_manager.detect_multi_device_login

same_browser_relogin = bool(request.cookies.get("auth_token"))
if _should_emit_multi_device_warning(kicked_sessions, same_browser_relogin=same_browser_relogin):
    response_data["multi_device_warning"] = (
        f"检测到该账号在其他 {len(kicked_sessions)} 个设备上登录，已自动登出旧设备"
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m unittest tests.test_auth_login_helpers -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_auth_login_helpers.py
git commit -m "fix: normalize login username and suppress same-browser relogin warning"
```

---

### Task 5: 端到端回归验证与收尾

**Files:**
- Modify: `docs/superpowers/specs/2026-04-09-default-theme-random-background-design.md`（仅在实现与 spec 不一致时更新）

- [ ] **Step 1: Run backend unit tests**

Run:
- `python -m unittest tests.test_theme_background_binding -v`
- `python -m unittest tests.test_auth_login_helpers -v`

Expected: 全部 PASS。

- [ ] **Step 2: Execute end-to-end manual scenarios**

Run manually in browser:

1. `/` 未登录加载：仅一次 consume。
2. `/uuid=<sid>` 登录后 30 分钟内刷新：同 target 同图。
3. 已绑定后访问 `/` 再登录：新匿名图覆盖旧绑定并重置 30 分钟。
4. PC 绑定后切移动端登录：移动端建立独立绑定，PC 不受影响。
5. 同浏览器重复登录：响应有新 cookie，不出现 `multi_device_warning`。

Expected: 全部符合 spec。

- [ ] **Step 3: Final diff review**

Run: `git diff -- main.py scripts/main.new.js tests/test_theme_background_binding.py tests/test_auth_login_helpers.py`
Expected: 仅包含本计划范围内改动，无额外重构。

- [ ] **Step 4: Commit verification result**

```bash
git add main.py scripts/main.new.js tests/test_theme_background_binding.py tests/test_auth_login_helpers.py
git commit -m "test: validate theme binding flow and relogin session behavior"
```

---

## Self-Review（against spec）

1. **Spec coverage check**
- 加载过程重复请求 → Task 3（前端门闩）
- 登录后 `(sessionUUID,target)` 绑定 30 分钟 → Task 1 + Task 2
- 无 UUID 重进后再登录覆盖绑定并重置 TTL → Task 2 + Task 3
- PC/Mobile 独立绑定 → Task 1 + Task 2 + Task 3
- 重复登录 cookie 轮换与多端提示修正 → Task 4

2. **Placeholder scan**
- 无 `TODO/TBD/implement later`。
- 每个代码步骤包含明确代码块。
- 每个验证步骤包含具体命令或明确手工检查项。

3. **Type/signature consistency**
- 绑定相关函数统一使用：
  - `_set_session_theme_background_binding(...)`
  - `_get_session_theme_background_binding(...)`
  - `_resolve_theme_background_binding_decision(...)`
- 登录辅助函数统一使用：
  - `_normalize_login_username_for_session_ops(...)`
  - `_should_emit_multi_device_warning(...)`

---

Plan complete and saved to `docs/superpowers/plans/2026-04-09-default-theme-background-binding-plan.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
