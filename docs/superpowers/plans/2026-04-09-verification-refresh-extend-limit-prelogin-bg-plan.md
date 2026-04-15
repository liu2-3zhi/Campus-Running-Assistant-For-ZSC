# Verification Refresh, Extend Limit, and Pre-login Background Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make verification-code modals auto-refresh via WebSocket with 30s polling fallback, enforce one-time SMS extension per `phone+code`, and bind login background using the snapshot captured at login click.

**Architecture:** Keep the existing architecture and patch in-place: add small backend helpers around `/api/sms/extend_code`, add a frontend verification-refresh scheduler that reacts to socket health, and add a pre-login background snapshot state consumed by existing background-binding flow. Avoid new framework/module layers and keep compatibility with current routes and event names.

**Tech Stack:** Python (Flask), JavaScript (browser + Socket.IO client), unittest

---

## File Structure Map

- **Modify** `main.py` (around `29435+`, `32023+`, `8583+`, `14144+`, `47890+`)
  - Add SMS extend-once helper state + functions.
  - Extend `/api/sms/extend_code` response with deterministic fields for countdown UI.
- **Modify** `scripts/main.new.js` (around `16783+`, `18162+`, `18596+`, `30125+`, `30423+`, `32782+`)
  - Add verification modal refresh scheduler (socket-driven + polling fallback).
  - Add dynamic countdown inside “信息已自动填充” Swal.
  - Capture pre-login background snapshot at login click and consume it during bind.
- **Create** `tests/test_sms_extend_once.py`
  - Unit-test backend extend-once helpers (`phone+code` single extension).
- **Modify** `tests/test_theme_background_binding.py`
  - Add test that confirms fallback behavior still uses current background when candidate is empty.

---

### Task 1: Backend one-time extend enforcement (`phone+code`)

**Files:**
- Modify: `main.py:22923-22940`, `main.py:32023-32071`
- Test: `tests/test_sms_extend_once.py`

- [ ] **Step 1: Write the failing tests (new file)**

```python
# tests/test_sms_extend_once.py
import unittest

from main import (
    _build_sms_extend_once_key,
    _is_sms_extend_allowed_once,
    _mark_sms_extend_used_once,
    _reset_sms_extend_once_for_phone,
    sms_extended_once_keys,
)


class TestSmsExtendOnce(unittest.TestCase):
    def setUp(self):
        sms_extended_once_keys.clear()

    def test_extend_once_allows_first_and_blocks_second(self):
        phone = "13800138000"
        code = "123456"

        self.assertTrue(_is_sms_extend_allowed_once(phone, code))
        _mark_sms_extend_used_once(phone, code)
        self.assertFalse(_is_sms_extend_allowed_once(phone, code))

    def test_different_code_on_same_phone_is_independent(self):
        phone = "13800138000"
        _mark_sms_extend_used_once(phone, "111111")
        self.assertTrue(_is_sms_extend_allowed_once(phone, "222222"))

    def test_reset_by_phone_clears_previous_marks(self):
        phone = "13800138000"
        _mark_sms_extend_used_once(phone, "111111")
        _reset_sms_extend_once_for_phone(phone)
        self.assertTrue(_is_sms_extend_allowed_once(phone, "111111"))

    def test_key_is_stable(self):
        self.assertEqual(
            _build_sms_extend_once_key("13800138000", "123456"),
            "13800138000:123456",
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH="c:/Users/Zelly/Documents/GitHub/python_runing" python -m unittest tests.test_sms_extend_once -v
```

Expected: FAIL with `ImportError` / missing helper symbols.

- [ ] **Step 3: Write minimal implementation in `main.py`**

```python
# near sms_verification_codes = {}
sms_verification_codes = {}
sms_extended_once_keys = set()


def _build_sms_extend_once_key(phone, code):
    normalized_phone = str(phone or "").strip()
    normalized_code = str(code or "").strip()
    return f"{normalized_phone}:{normalized_code}" if normalized_phone and normalized_code else ""


def _is_sms_extend_allowed_once(phone, code):
    key = _build_sms_extend_once_key(phone, code)
    if not key:
        return False
    return key not in sms_extended_once_keys


def _mark_sms_extend_used_once(phone, code):
    key = _build_sms_extend_once_key(phone, code)
    if key:
        sms_extended_once_keys.add(key)


def _reset_sms_extend_once_for_phone(phone):
    normalized_phone = str(phone or "").strip()
    if not normalized_phone:
        return
    stale_keys = [k for k in sms_extended_once_keys if k.startswith(f"{normalized_phone}:")]
    for k in stale_keys:
        sms_extended_once_keys.discard(k)
```

And update `/api/sms/send_code` and `/api/admin/sms/add_manual_code` after setting `sms_verification_codes[phone] = (...)`:

```python
_reset_sms_extend_once_for_phone(phone)
```

And update `/api/sms/extend_code` core branch:

```python
code, expire_time = sms_verification_codes[phone]

if not _is_sms_extend_allowed_once(phone, code):
    remaining_seconds = max(0, int(expire_time - current_time))
    return jsonify({
        "success": False,
        "error_code": "EXTEND_LIMIT_REACHED",
        "message": "该验证码已延期过一次，请直接完成注册",
        "expires_at": int(expire_time),
        "remaining_seconds": remaining_seconds,
    })

extend_minutes = 5
extend_seconds = extend_minutes * 60
new_expire_time = current_time + extend_seconds
sms_verification_codes[phone] = (code, new_expire_time)
_mark_sms_extend_used_once(phone, code)

return jsonify({
    "success": True,
    "message": f"验证码有效期已延长{extend_minutes}分钟",
    "extend_minutes": extend_minutes,
    "expires_at": int(new_expire_time),
    "remaining_seconds": int(extend_seconds),
})
```

- [ ] **Step 4: Run tests to verify pass**

Run:
```bash
PYTHONPATH="c:/Users/Zelly/Documents/GitHub/python_runing" python -m unittest tests.test_sms_extend_once -v
```

Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_sms_extend_once.py
git commit -m "feat: enforce one-time sms extension per phone and code"
```

---

### Task 2: Verification modal auto refresh (WebSocket + 30s fallback polling)

**Files:**
- Modify: `scripts/main.new.js:30125-30132`, `scripts/main.new.js:30423-30510`, `scripts/main.new.js:32782-32927`

- [ ] **Step 1: Write the failing verification checklist (manual RED)**

Create this checklist in your working notes and execute before changes:

```text
[RED] Manual failing checks before code changes:
1) Open PC verification modal, then break websocket connection: list does not auto-refresh every 30s (expected fail now).
2) Open mobile verification modal, break websocket: list does not auto-refresh every 30s (expected fail now).
3) Restore websocket: polling does not stop automatically (expected fail now).
```

- [ ] **Step 2: Verify RED manually**

Run app and reproduce:
```bash
python "c:/Users/Zelly/Documents/GitHub/python_runing/main.py"
```

Expected: checklist items fail as described above.

- [ ] **Step 3: Implement minimal scheduler in `scripts/main.new.js`**

Add state and helpers near verification modal section:

```javascript
let verificationCodesPollingTimer = null;
const VERIFICATION_CODES_POLLING_MS = 30000;
let verificationCodesSocketHealthy = false;

function isVerificationCodesModalOpen() {
  const modal = $("verification-codes-modal");
  return !!modal && !modal.classList.contains("hidden");
}

function isMobileVerificationCodesModalOpen() {
  const modal = document.getElementById("mobile-verification-codes-modal");
  return !!modal && !modal.classList.contains("hidden");
}

function refreshOpenVerificationCodeModals() {
  if (isVerificationCodesModalOpen()) {
    loadVerificationCodes();
  }
  if (isMobileVerificationCodesModalOpen()) {
    loadMobileVerificationCodes();
  }
}

function startVerificationCodesPollingFallback() {
  if (verificationCodesPollingTimer) return;
  verificationCodesPollingTimer = setInterval(() => {
    if (!verificationCodesSocketHealthy) {
      refreshOpenVerificationCodeModals();
    }
  }, VERIFICATION_CODES_POLLING_MS);
}

function stopVerificationCodesPollingFallback() {
  if (!verificationCodesPollingTimer) return;
  clearInterval(verificationCodesPollingTimer);
  verificationCodesPollingTimer = null;
}
```

Update `openVerificationCodesModal`, `closeVerificationCodesModal`, `openMobileVerificationCodesModal`, `closeMobileVerificationCodesModal` to start/stop polling based on socket health + whether any modal remains open.

Update socket handlers in `connectWebSocket()`:

```javascript
socket.on("connect", () => {
  verificationCodesSocketHealthy = true;
  stopVerificationCodesPollingFallback();
  // existing code...
});

socket.on("disconnect", (reason) => {
  verificationCodesSocketHealthy = false;
  if (isVerificationCodesModalOpen() || isMobileVerificationCodesModalOpen()) {
    startVerificationCodesPollingFallback();
  }
  // existing code...
});

socket.on("connect_error", (error) => {
  verificationCodesSocketHealthy = false;
  if (isVerificationCodesModalOpen() || isMobileVerificationCodesModalOpen()) {
    startVerificationCodesPollingFallback();
  }
  // existing code...
});

socket.on("verification_codes_updated", () => {
  refreshOpenVerificationCodeModals();
});
```

- [ ] **Step 4: Verify GREEN manually**

Run app:
```bash
python "c:/Users/Zelly/Documents/GitHub/python_runing/main.py"
```

Expected:
```text
PASS-MANUAL:
- PC modal: websocket push refresh works.
- Mobile modal: websocket push refresh works.
- On disconnect: polling refresh every ~30s.
- On reconnect: polling stops.
```

- [ ] **Step 5: Commit**

```bash
git add scripts/main.new.js
git commit -m "feat: add websocket-first verification refresh with polling fallback"
```

---

### Task 3: Non-blocking extend feedback + dynamic countdown in auto-fill Swal

**Files:**
- Modify: `scripts/main.new.js:18596-18710`

- [ ] **Step 1: Write failing manual RED checks**

```text
[RED] Manual failing checks before code changes:
1) Trigger phone-not-registered redirect twice with same phone+code:
   second time UI shows generic success text claiming extension happened (expected fail now).
2) Keep auto-fill swal open for 30+ seconds:
   remaining validity does not update every second (expected fail now).
```

- [ ] **Step 2: Verify RED manually**

Run app:
```bash
python "c:/Users/Zelly/Documents/GitHub/python_runing/main.py"
```

Expected: both checks fail.

- [ ] **Step 3: Implement minimal behavior in `handlePhoneNotRegisteredRedirect`**

Use response fields from backend (`expires_at`, `remaining_seconds`, `error_code`) and dynamic interval:

```javascript
let extendStatusText = "延期状态未知，请尽快完成注册。";
let effectiveExpireAt = null;

try {
  const response = await fetch("/api/sms/extend_code", { ... });
  const data = await response.json();
  if (data.success) {
    extendStatusText = "验证码已延期一次。";
    effectiveExpireAt = Number(data.expires_at || 0);
  } else if (data.error_code === "EXTEND_LIMIT_REACHED") {
    extendStatusText = "该验证码已达延期上限，本次未再次延期，请尽快完成注册。";
    effectiveExpireAt = Number(data.expires_at || 0);
  } else {
    extendStatusText = data.message || "延期状态获取失败，请尽快完成注册。";
  }
} catch (_) {
  extendStatusText = "延期状态获取失败，请尽快完成注册。";
}

let countdownTimer = null;
fireVerificationCodesModalSwal({
  icon: "success",
  title: "信息已自动填充",
  html: `
    <div class="text-left">
      <p class="mb-2 text-green-600">✅ 手机号和验证码已自动填充</p>
      <p id="reg-sms-expire-countdown" class="text-sm text-slate-600">验证码剩余有效时间：计算中...</p>
      <p class="text-sm text-slate-600 mt-2">${escapeHtml(extendStatusText)}</p>
      <p class="text-sm text-slate-600 mt-2">请设置用户名和密码完成注册。</p>
    </div>
  `,
  confirmButtonText: "我知道了",
  allowOutsideClick: false,
  didOpen: () => {
    const el = document.getElementById("reg-sms-expire-countdown");
    const update = () => {
      if (!el) return;
      const now = Math.floor(Date.now() / 1000);
      const remain = effectiveExpireAt ? Math.max(0, effectiveExpireAt - now) : 0;
      if (remain <= 0) {
        el.textContent = "验证码可能已过期，请重新获取。";
        return;
      }
      const m = Math.floor(remain / 60);
      const s = remain % 60;
      el.textContent = `验证码剩余有效时间：${m}分${s}秒`;
    };
    update();
    countdownTimer = setInterval(update, 1000);
  },
  willClose: () => {
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  },
});
```

- [ ] **Step 4: Verify GREEN manually**

Run app:
```bash
python "c:/Users/Zelly/Documents/GitHub/python_runing/main.py"
```

Expected:
```text
PASS-MANUAL:
- Extend rejected path still keeps user in register flow.
- Auto-fill swal shows live countdown that updates every second.
- Closing swal stops countdown timer.
```

- [ ] **Step 5: Commit**

```bash
git add scripts/main.new.js
git commit -m "fix: make extend rejection non-blocking with live expiry countdown"
```

---

### Task 4: Capture pre-login background snapshot and bind with login-context candidate

**Files:**
- Modify: `scripts/main.new.js:16783-16980`, `scripts/main.new.js:18162-18320`
- Test: `tests/test_theme_background_binding.py`

- [ ] **Step 1: Write failing test for binding fallback consistency**

Add this test in `tests/test_theme_background_binding.py`:

```python
def test_login_context_without_candidate_falls_back_to_current_image(self):
    with tempfile.TemporaryDirectory() as d:
        cache_dir = Path(d)
        result = _resolve_theme_background_binding_decision(
            cache_dir=str(cache_dir),
            session_uuid="sid-fallback",
            target="pc",
            current_image_url="/theme-assets/random_background_image/pc_current.jpg",
            login_context=True,
            candidate_image_url="",
            ttl_seconds=1800,
        )
        self.assertEqual(result["action"], "bind_new")
        self.assertEqual(
            result["selected_image_url"],
            "/theme-assets/random_background_image/pc_current.jpg",
        )
```

- [ ] **Step 2: Run test to verify RED**

Run:
```bash
PYTHONPATH="c:/Users/Zelly/Documents/GitHub/python_runing" python -m unittest tests.test_theme_background_binding -v
```

Expected: FAIL only if current behavior diverges from required fallback.

- [ ] **Step 3: Implement minimal snapshot capture + candidate consumption**

In `scripts/main.new.js`, add state and helpers near theme background state:

```javascript
const preLoginBackgroundSnapshot = { pc: "", mobile: "" };

function capturePreLoginBackgroundSnapshot() {
  const target = getCurrentThemeBackgroundTarget();
  const normalizedTarget = target === "mobile" ? "mobile" : "pc";
  const imageUrl = getThemeBackgroundImageUrlByTarget(normalizedTarget);
  if (imageUrl) {
    preLoginBackgroundSnapshot[normalizedTarget] = imageUrl;
  }
}
```

Call this at the very start of `handleAuthLogin(...)` before async request.

In `notifyThemeBackgroundConsumed(...)`, when `sessionUUID` and `login_context` are true:

```javascript
const snapshotCandidate = preLoginBackgroundSnapshot[normalizedTarget];
const candidateImage = snapshotCandidate || anonConsumedBackgroundByTarget[normalizedTarget];
if (payload.login_context && candidateImage) {
  payload.candidate_image_url = candidateImage;
}
```

After successful bind in login context:

```javascript
if (sessionUUID && sessionBindEnsured[normalizedTarget]) {
  preLoginBackgroundSnapshot[normalizedTarget] = "";
}
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:
```bash
PYTHONPATH="c:/Users/Zelly/Documents/GitHub/python_runing" python -m unittest tests.test_theme_background_binding -v
```

Expected: PASS (all tests green including new fallback test).

- [ ] **Step 5: Commit**

```bash
git add scripts/main.new.js tests/test_theme_background_binding.py
git commit -m "feat: bind theme background from pre-login snapshot"
```

---

## Final Verification Task

**Files:**
- Modify: none
- Test: `tests/test_sms_extend_once.py`, `tests/test_theme_background_binding.py`

- [ ] **Step 1: Run backend test suite subset**

```bash
PYTHONPATH="c:/Users/Zelly/Documents/GitHub/python_runing" python -m unittest tests.test_sms_extend_once tests.test_theme_background_binding -v
```

Expected:
```text
Ran X tests
OK
```

- [ ] **Step 2: Run manual integration checks**

```text
Checklist:
1) Open PC verification modal; disconnect socket; confirm 30s polling refresh.
2) Open mobile verification modal; disconnect socket; confirm 30s polling refresh.
3) Reconnect socket; confirm polling stops.
4) Trigger unregistered-phone redirect twice with same phone+code:
   first extend success, second EXTEND_LIMIT_REACHED; both keep register flow.
5) Keep “信息已自动填充” swal open for >20s and verify countdown updates.
6) Click login with visible background A, then complete login and verify bind uses A.
```

Expected: all checks pass.

- [ ] **Step 3: Commit final integration changes (if any)**

```bash
git add main.py scripts/main.new.js tests/test_sms_extend_once.py tests/test_theme_background_binding.py
git commit -m "feat: complete verification refresh fallback and login background binding flow"
```

---

## Plan Self-Review

### Spec coverage

- WebSocket + 30s polling fallback for PC/mobile verification modal: **covered in Task 2**.
- Extend once per `phone+code` + non-blocking frontend handling: **covered in Task 1 + Task 3**.
- Auto-fill popup shows dynamic expiry countdown even without confirm click: **covered in Task 3**.
- Pre-login background snapshot used for login binding; fallback to current background: **covered in Task 4**.

### Placeholder scan

- No `TODO`/`TBD` placeholders.
- Each coding step includes concrete code blocks.
- Each verification step includes concrete commands + expected outcome.

### Type/signature consistency

- Extend-limit helpers consistently named:
  - `_build_sms_extend_once_key`
  - `_is_sms_extend_allowed_once`
  - `_mark_sms_extend_used_once`
  - `_reset_sms_extend_once_for_phone`
- Frontend snapshot state consistently named `preLoginBackgroundSnapshot`.

