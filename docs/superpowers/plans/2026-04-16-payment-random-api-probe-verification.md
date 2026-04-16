# 支付随机 API 探针校验 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将支付 `app_host` 验证切换为“一次性随机 `/api` 路径 + 随机 challenge 文本 + 本机内存消费成功”的唯一主链路，并把 `return_url` 调整为“仅允许本站任意路径、禁止跨站跳转”。

**Architecture:** 在 `main.py` 中新增支付 probe 内存管理 helper、随机 probe 路由和 `return_url` 同源校验 helper；`IPVerifier.check_app_host()`、`/api/payment/verify_host` 与 `RainbowYiPay.create_order()` 统一复用这套 probe 机制。旧固定 `/api/payment/verify_challenge` 和基于公网 IP 的支付自检主流程被移除，避免 CDN/反代场景误判。

**Tech Stack:** Python 3、Flask（`main.py`）、`unittest` + `unittest.mock`、现有 requests/urllib 依赖。

---

## File Structure（实施前锁定）

- Modify: `main.py`
  - 新增支付 probe 生命周期管理 helper。
  - 新增 `/api/payment/verify_probe/<token>` 路由。
  - 改造 `IPVerifier.check_app_host()` 为随机 probe 校验。
  - 改造 `/api/payment/verify_host` 复用同一校验链路。
  - 改造 `payment_create_order()` / `RainbowYiPay.create_order()` 的 `return_url` 处理。
  - 删除旧固定 challenge 路由与旧全局状态。
- Modify: `tests/test_payment_order_lifecycle.py`
  - 增加 probe helper、随机路径、消费状态、跨站 `return_url` 的回归测试。
- Modify: `docs/superpowers/specs/2026-04-16-payment-random-api-probe-verification-design.md`
  - 仅在实现与 spec 发现轻微命名偏差时同步修正（默认不改）。

---

### Task 1: 为支付 probe 生命周期写失败测试

**Files:**
- Modify: `tests/test_payment_order_lifecycle.py`
- Test: `tests/test_payment_order_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
import time
import unittest

import main as main_module
from main import (
    _cleanup_expired_payment_verify_probes,
    _consume_payment_verify_probe,
    _create_payment_verify_probe,
    _is_payment_verify_probe_consumed,
)


class TestPaymentVerifyProbeLifecycle(unittest.TestCase):
    def setUp(self):
        main_module.payment_verify_probes = {}

    def test_probe_roundtrip_consumes_once(self):
        token, challenge = _create_payment_verify_probe(ttl_seconds=15)

        self.assertFalse(_is_payment_verify_probe_consumed(token))
        self.assertTrue(_consume_payment_verify_probe(token, challenge))
        self.assertTrue(_is_payment_verify_probe_consumed(token))
        self.assertFalse(_consume_payment_verify_probe(token, challenge))

    def test_probe_rejects_wrong_challenge(self):
        token, challenge = _create_payment_verify_probe(ttl_seconds=15)

        self.assertFalse(_consume_payment_verify_probe(token, challenge + "-wrong"))
        self.assertFalse(_is_payment_verify_probe_consumed(token))

    def test_cleanup_drops_expired_probe(self):
        token, challenge = _create_payment_verify_probe(ttl_seconds=0)
        time.sleep(0.01)

        _cleanup_expired_payment_verify_probes()

        self.assertFalse(_consume_payment_verify_probe(token, challenge))
        self.assertNotIn(token, main_module.payment_verify_probes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_payment_order_lifecycle.TestPaymentVerifyProbeLifecycle -v`
Expected: FAIL，提示 `_create_payment_verify_probe` / `_consume_payment_verify_probe` / `_cleanup_expired_payment_verify_probes` / `_is_payment_verify_probe_consumed` 未定义。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py
payment_verify_probes = {}
payment_verify_probes_lock = threading.Lock()


def _cleanup_expired_payment_verify_probes(now_ts=None):
    current_ts = float(now_ts if now_ts is not None else time.time())
    with payment_verify_probes_lock:
        expired_tokens = [
            token
            for token, probe in payment_verify_probes.items()
            if float(probe.get("expires_at", 0) or 0) <= current_ts
        ]
        for token in expired_tokens:
            payment_verify_probes.pop(token, None)


def _create_payment_verify_probe(ttl_seconds=15):
    _cleanup_expired_payment_verify_probes()
    token = secrets.token_urlsafe(24)
    challenge = secrets.token_urlsafe(32)
    now_ts = time.time()
    with payment_verify_probes_lock:
        payment_verify_probes[token] = {
            "token": token,
            "challenge": challenge,
            "created_at": now_ts,
            "expires_at": now_ts + float(ttl_seconds),
            "consumed": False,
        }
    return token, challenge


def _consume_payment_verify_probe(token, challenge, now_ts=None):
    _cleanup_expired_payment_verify_probes(now_ts=now_ts)
    with payment_verify_probes_lock:
        probe = payment_verify_probes.get(str(token or ""))
        if not isinstance(probe, dict):
            return False
        if probe.get("consumed"):
            return False
        if str(probe.get("challenge") or "") != str(challenge or ""):
            return False
        probe["consumed"] = True
        return True


def _is_payment_verify_probe_consumed(token):
    with payment_verify_probes_lock:
        probe = payment_verify_probes.get(str(token or ""))
        return bool(isinstance(probe, dict) and probe.get("consumed"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_payment_order_lifecycle.TestPaymentVerifyProbeLifecycle -v`
Expected: PASS，三个用例通过。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_payment_order_lifecycle.py
git commit -m "feat: add payment verify probe lifecycle helpers"
```

---

### Task 2: 为随机 probe URL 和无缓存响应写失败测试

**Files:**
- Modify: `tests/test_payment_order_lifecycle.py`
- Modify: `main.py`
- Test: `tests/test_payment_order_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from flask import Flask

import main as main_module
from main import _build_payment_verify_probe_url, _register_payment_verify_probe_route


class TestPaymentVerifyProbeRoute(unittest.TestCase):
    def setUp(self):
        main_module.payment_verify_probes = {}

    def test_build_probe_url_uses_random_api_path(self):
        url = _build_payment_verify_probe_url("https://example.com/", "token-123")
        self.assertEqual(url, "https://example.com/api/payment/verify_probe/token-123")

    def test_probe_route_consumes_probe_and_sets_no_cache_headers(self):
        app = Flask(__name__)
        _register_payment_verify_probe_route(app)
        token, challenge = main_module._create_payment_verify_probe(ttl_seconds=15)

        with app.test_client() as client:
            response = client.post(
                f"/api/payment/verify_probe/{token}",
                json={"challenge": challenge},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(response.headers["Expires"], "0")
        self.assertTrue(main_module._is_payment_verify_probe_consumed(token))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_payment_order_lifecycle.TestPaymentVerifyProbeRoute -v`
Expected: FAIL，提示 `_build_payment_verify_probe_url` / `_register_payment_verify_probe_route` 未定义，或 probe 路由未注册。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

def _build_payment_verify_probe_url(base_url, token):
    normalized_base = str(base_url or "").rstrip("/")
    return f"{normalized_base}/api/payment/verify_probe/{token}"


def _apply_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _register_payment_verify_probe_route(app):
    @app.route("/api/payment/verify_probe/<token>", methods=["POST"])
    def payment_verify_probe(token):
        data = request.get_json(silent=True) or {}
        challenge = data.get("challenge", "")
        if not _consume_payment_verify_probe(token, challenge):
            response = jsonify({"success": False})
            return _apply_no_cache_headers(response), 404
        response = jsonify({"success": True})
        return _apply_no_cache_headers(response)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_payment_order_lifecycle.TestPaymentVerifyProbeRoute -v`
Expected: PASS，两个用例通过。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_payment_order_lifecycle.py
git commit -m "feat: add random payment verify probe route"
```

---

### Task 3: 为 `check_app_host()` 的“本机消费成功才算通过”写失败测试

**Files:**
- Modify: `tests/test_payment_order_lifecycle.py`
- Modify: `main.py`
- Test: `tests/test_payment_order_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from unittest import mock

import main as main_module


class TestCheckAppHostProbeValidation(unittest.TestCase):
    def test_check_app_host_posts_to_random_probe_url(self):
        verifier = main_module.IPVerifier()
        response_mock = mock.Mock()
        response_mock.status_code = 200
        response_mock.json.return_value = {"success": True}

        with mock.patch.object(main_module, "urllib", __import__("urllib"), create=True), \
             mock.patch.object(main_module, "requests", mock.Mock(post=mock.Mock(return_value=response_mock)), create=True), \
             mock.patch.object(main_module, "_create_payment_verify_probe", return_value=("token-123", "challenge-abc")), \
             mock.patch.object(main_module, "_is_payment_verify_probe_consumed", return_value=True):
            ok = verifier.check_app_host("https://pay.example.com")

        self.assertTrue(ok)
        main_module.requests.post.assert_called_once_with(
            "https://pay.example.com/api/payment/verify_probe/token-123",
            json={"challenge": "challenge-abc"},
            timeout=5,
        )

    def test_check_app_host_rejects_fake_success_when_probe_not_consumed(self):
        verifier = main_module.IPVerifier()
        response_mock = mock.Mock()
        response_mock.status_code = 200
        response_mock.json.return_value = {"success": True}

        with mock.patch.object(main_module, "urllib", __import__("urllib"), create=True), \
             mock.patch.object(main_module, "requests", mock.Mock(post=mock.Mock(return_value=response_mock)), create=True), \
             mock.patch.object(main_module, "_create_payment_verify_probe", return_value=("token-123", "challenge-abc")), \
             mock.patch.object(main_module, "_is_payment_verify_probe_consumed", return_value=False):
            ok = verifier.check_app_host("https://pay.example.com")

        self.assertFalse(ok)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_payment_order_lifecycle.TestCheckAppHostProbeValidation -v`
Expected: FAIL，仍请求旧 `/api/payment/verify_challenge`，或仅凭远端 JSON 成功就返回 True。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py
class IPVerifier:
    def check_app_host(self, client_app_host: str) -> bool:
        parsed = self.parse_host_input(client_app_host)
        if not parsed["ip"]:
            logging.warning(f"[本机验证] 无法解析host: {client_app_host}")
            return False

        base_url = parsed["full_url"]
        if not base_url:
            logging.warning(f"[本机验证] 无法构建请求URL: {client_app_host}")
            return False

        token, challenge = _create_payment_verify_probe(ttl_seconds=15)
        verify_url = _build_payment_verify_probe_url(base_url, token)
        token_preview = f"{token[:8]}..." if len(token) > 8 else token
        logging.info(f"[本机验证] 创建随机 probe: {token_preview} -> {verify_url}")

        try:
            response = requests.post(
                verify_url,
                json={"challenge": challenge},
                timeout=5,
            )
            if response.status_code != 200:
                logging.warning(f"[本机验证] HTTP请求失败 - 状态码: {response.status_code}")
                return False

            response_data = response.json()
            if not response_data.get("success"):
                logging.warning("[本机验证] probe 接口返回失败")
                return False

            if not _is_payment_verify_probe_consumed(token):
                logging.warning(f"[本机验证] probe 未在本机消费成功: {token_preview}")
                return False
            return True
        except requests.exceptions.Timeout:
            logging.warning(f"[本机验证] 请求超时 - {verify_url}")
            return False
        except requests.exceptions.ConnectionError:
            logging.warning(f"[本机验证] 连接失败 - {verify_url}")
            return False
        except Exception as e:
            logging.error(f"[本机验证] 验证过程异常: {str(e)}")
            return False
        finally:
            _cleanup_expired_payment_verify_probes()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_payment_order_lifecycle.TestCheckAppHostProbeValidation -v`
Expected: PASS，两个用例通过。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_payment_order_lifecycle.py
git commit -m "fix: validate app host with consumed random probe"
```

---

### Task 4: 为 `/api/payment/verify_host` 复用 probe 链路写失败测试

**Files:**
- Modify: `tests/test_payment_order_lifecycle.py`
- Modify: `main.py`
- Test: `tests/test_payment_order_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from flask import Flask, jsonify, request

import main as main_module


class TestVerifyHostEndpoint(unittest.TestCase):
    def test_verify_host_endpoint_uses_ipverifier_check_app_host(self):
        app = Flask(__name__)

        def login_required(func):
            return func

        verifier_calls = []

        @app.route("/api/payment/verify_host", methods=["POST"])
        def _placeholder():
            return jsonify({"success": False}), 500

        main_module._register_payment_verify_host_route_for_tests(
            app,
            login_required=login_required,
            verifier_factory=lambda: type(
                "VerifierStub",
                (),
                {"check_app_host": lambda self, host: verifier_calls.append(host) or True},
            )(),
        )

        with app.test_client() as client:
            response = client.post("/api/payment/verify_host", json={"app_host": "https://pay.example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(verifier_calls, ["https://pay.example.com"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_payment_order_lifecycle.TestVerifyHostEndpoint -v`
Expected: FAIL，当前实现仍内嵌旧 challenge 逻辑，无法用 `IPVerifier.check_app_host()` 统一复用。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

def _register_payment_verify_host_route_for_tests(app, login_required, verifier_factory=None):
    verifier_factory = verifier_factory or IPVerifier

    @app.route("/api/payment/verify_host", methods=["POST"])
    @login_required
    def payment_verify_host():
        data = request.get_json() or {}
        app_host = str(data.get("app_host", "")).strip()
        if not app_host:
            return jsonify({"success": False, "message": "app_host参数不能为空", "verified": False})
        if not (app_host.startswith("http://") or app_host.startswith("https://")):
            return jsonify({"success": False, "message": "app_host格式不正确，必须以http://或https://开头", "verified": False})

        verifier = verifier_factory()
        verified = verifier.check_app_host(app_host.rstrip("/"))
        if verified:
            return jsonify({"success": True, "message": "验证通过，这是本服务器", "verified": True})
        return jsonify({"success": False, "message": "验证失败：目标地址未命中本机随机探针", "verified": False})
```

将生产路由替换为：

```python
_register_payment_verify_host_route_for_tests(app, login_required)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_payment_order_lifecycle.TestVerifyHostEndpoint -v`
Expected: PASS，用例通过，且 endpoint 已统一复用 `IPVerifier.check_app_host()`。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_payment_order_lifecycle.py
git commit -m "refactor: reuse app host probe validation in verify endpoint"
```

---

### Task 5: 为 `return_url` 的“本站任意路径，禁止跨站”写失败测试

**Files:**
- Modify: `tests/test_payment_order_lifecycle.py`
- Modify: `main.py`
- Test: `tests/test_payment_order_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from main import _normalize_payment_return_url


class TestPaymentReturnUrlValidation(unittest.TestCase):
    def test_same_origin_return_url_is_preserved(self):
        result = _normalize_payment_return_url(
            "https://pay.example.com/orders/result?order=1",
            app_host="https://pay.example.com",
            notify_url="https://pay.example.com/api/payment/yipay_notify",
        )
        self.assertEqual(result, "https://pay.example.com/orders/result?order=1")

    def test_cross_origin_return_url_is_rejected(self):
        result = _normalize_payment_return_url(
            "https://evil.example.com/phish",
            app_host="https://pay.example.com",
            notify_url="https://pay.example.com/api/payment/yipay_notify",
        )
        self.assertIsNone(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_payment_order_lifecycle.TestPaymentReturnUrlValidation -v`
Expected: FAIL，提示 `_normalize_payment_return_url` 未定义，或当前逻辑会把任意 `return_url` 包进 `?jump=`。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py

def _is_same_origin_url(candidate_url, base_url):
    try:
        candidate = urllib.parse.urlparse(str(candidate_url or "").strip())
        base = urllib.parse.urlparse(str(base_url or "").strip())
    except Exception:
        return False
    if not candidate.scheme or not candidate.netloc:
        return False
    return (
        candidate.scheme.lower(),
        candidate.hostname.lower() if candidate.hostname else "",
        candidate.port or (443 if candidate.scheme.lower() == "https" else 80),
    ) == (
        base.scheme.lower(),
        base.hostname.lower() if base.hostname else "",
        base.port or (443 if base.scheme.lower() == "https" else 80),
    )


def _normalize_payment_return_url(return_url, app_host, notify_url):
    normalized_return_url = str(return_url or "").strip()
    if not normalized_return_url or normalized_return_url in {"null", "NULL", "None", "none", "undefined", "undefind"}:
        return None
    if not _is_same_origin_url(normalized_return_url, app_host):
        return None
    return normalized_return_url
```

并在 `payment_create_order()` / `RainbowYiPay.create_order()` 中替换旧逻辑：

```python
return_url = _normalize_payment_return_url(
    return_url,
    app_host=app_host,
    notify_url=notify_url,
)
if return_url is None:
    return_url = notify_url
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_payment_order_lifecycle.TestPaymentReturnUrlValidation -v`
Expected: PASS，同站 URL 保留，跨站 URL 返回 None。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_payment_order_lifecycle.py
git commit -m "fix: restrict payment return url to same origin"
```

---

### Task 6: 删除旧 challenge 主流程并补完整回归验证

**Files:**
- Modify: `main.py`
- Modify: `tests/test_payment_order_lifecycle.py`
- Test: `tests/test_payment_order_lifecycle.py`

- [ ] **Step 1: Write the failing regression test**

```python
import unittest

import main as main_module


class TestLegacyPaymentChallengeRemoval(unittest.TestCase):
    def test_legacy_payment_challenge_globals_are_not_required(self):
        self.assertFalse(hasattr(main_module, "payment_verify_challenge_get"))

    def test_legacy_self_check_flag_is_not_required(self):
        self.assertFalse(hasattr(main_module, "PAYMENT_APP_HOST_SELF_CHECK_ENABLED"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_payment_order_lifecycle.TestLegacyPaymentChallengeRemoval -v`
Expected: FAIL，这两个旧兼容状态仍存在。

- [ ] **Step 3: Write minimal implementation**

```python
# main.py
# 删除：
# - PAYMENT_APP_HOST_SELF_CHECK_ENABLED
# - payment_verify_challenge_get
# - /api/payment/verify_challenge 路由
# - check_app_host() / verify_host() / create_order() 中对旧变量和旧接口的引用
```

并把 `tests/test_payment_order_lifecycle.py` 中旧测试：

```python
def test_check_app_host_skips_network_when_self_check_disabled(self):
    ...
```

替换为：

```python
def test_check_app_host_requires_probe_roundtrip(self):
    verifier = main_module.IPVerifier()
    response_mock = mock.Mock(status_code=200)
    response_mock.json.return_value = {"success": True}

    with mock.patch.object(main_module, "urllib", __import__("urllib"), create=True), \
         mock.patch.object(main_module, "requests", mock.Mock(post=mock.Mock(return_value=response_mock)), create=True), \
         mock.patch.object(main_module, "_create_payment_verify_probe", return_value=("token-123", "challenge-abc")), \
         mock.patch.object(main_module, "_is_payment_verify_probe_consumed", return_value=False):
        self.assertFalse(verifier.check_app_host("https://example.com"))
```

- [ ] **Step 4: Run full targeted regression suite**

Run: `python -m unittest tests.test_theme_background_binding tests.test_payment_order_lifecycle -v`
Expected: PASS，所有支付相关与既有主题测试都通过；不再出现 `js_cache_lock` / 旧 challenge 路径相关失败。

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_payment_order_lifecycle.py
git commit -m "refactor: remove legacy payment challenge verification"
```

---

## Spec coverage self-check

- “只采用随机路径 + 随机文本” → Task 1 / Task 2 / Task 3 / Task 4 覆盖。
- “路径必须以 `/api` 开头，防止缓存” → Task 2 覆盖 URL 与 no-cache 头。
- “成功条件必须包含本机 probe 已消费” → Task 3 覆盖。
- “`return_url` 仅允许本站任意路径，禁止跨站” → Task 5 覆盖。
- “旧固定 challenge 主流程退出主链路” → Task 6 覆盖。
- “前端 `/api/payment/verify_host` 入口保持兼容” → Task 4 覆盖 endpoint 复用，不改前端入口。

无缺口；如实现中发现 spec 与现有路径名不一致，仅允许同步修正命名，不扩展范围。

---

## Placeholder / consistency self-check

- 没有 `TODO` / `TBD` / “类似 Task N”。
- 每个任务都给了确切文件、测试命令、期望结果。
- helper 命名在各任务中保持一致：
  - `_create_payment_verify_probe`
  - `_consume_payment_verify_probe`
  - `_cleanup_expired_payment_verify_probes`
  - `_is_payment_verify_probe_consumed`
  - `_build_payment_verify_probe_url`
  - `_normalize_payment_return_url`
- 若实现时发现 Flask 路由重复注册问题，可把 `Task 4` 的 `_register_payment_verify_host_route_for_tests` 保留为测试友好的注册 helper，生产路径直接复用它，不新增第二套逻辑。

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-16-payment-random-api-probe-verification.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
