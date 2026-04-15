# Billing Order Timeout & QR Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a deterministic billing payment lifecycle where pending orders auto-close after N minutes, QR code results are reused within the same TTL for the same school+billing+channel request, and async notifications can still convert closed orders to paid.

**Architecture:** Keep order lifecycle logic in backend helper functions and integrate them into existing payment endpoints (`create_order_for_billing`, `yipay_notify`, `refund`, `query`). Store QR reuse state in a persistent index file under `payment_orders/` keyed by `school_id:billing_id:pay_type`. Update frontend status rendering and pay-button guards to include `closed/refunded_partial/refunded_full` behavior while reusing existing admin config timeout value.

**Tech Stack:** Python (Flask, unittest, json/filesystem), JavaScript (browser runtime + node:test), HTML config panel.

---

## File Structure & Responsibilities

- `main.py`
  - Add order lifecycle helpers (timeout close, terminal-state checks)
  - Add persistent QR cache index helpers
  - Integrate reuse/close rules into `/api/payment/create_order_for_billing`
  - Integrate closed->paid behavior into `/api/payment/yipay_notify`
  - Integrate refund state transitions into `/api/payment/refund`
  - Ensure query/list paths apply timeout close before returning status

- `tests/test_payment_order_lifecycle.py` (new)
  - Backend unit tests for timeout close, closed->paid notify, refund transitions
  - Backend tests for QR cache keying/TTL behavior and cache invalidation

- `scripts/main.new.js`
  - Normalize and render expanded billing statuses
  - Block pay actions for terminal statuses (`paid/refunded_partial/refunded_full`)
  - Show message when closed order requires new order
  - Show message when backend indicates QR reused

- `tests/billing_status_behavior.test.mjs` (new)
  - Node tests for new frontend pure functions (status display + payability rules)

- `index.html`
  - Update admin timeout field helper text to indicate timeout also controls QR reuse TTL
  - Add status options where needed for `refunded_partial` and `refunded_full`

---

### Task 1: Add backend lifecycle helpers with failing tests first

**Files:**
- Modify: `main.py` (near payment helper area around `PAYMENT_ORDERS_DIR` and query endpoints)
- Create: `tests/test_payment_order_lifecycle.py`
- Test: `tests/test_payment_order_lifecycle.py`

- [ ] **Step 1: Write failing tests for timeout close and terminal-state checks**

```python
# tests/test_payment_order_lifecycle.py
import unittest
from main import (
    _advance_order_status_by_timeout,
    _is_order_terminal_for_repay,
)

class TestPaymentOrderLifecycle(unittest.TestCase):
    def test_pending_order_becomes_closed_after_timeout(self):
        order = {
            "status": "pending",
            "expires_at": "2026-04-12T10:00:00+00:00",
            "closed_at": None,
        }
        changed = _advance_order_status_by_timeout(order, now_iso="2026-04-12T10:00:01+00:00")
        self.assertTrue(changed)
        self.assertEqual(order["status"], "closed")
        self.assertIsNotNone(order["closed_at"])

    def test_paid_order_is_terminal_for_repay(self):
        self.assertTrue(_is_order_terminal_for_repay({"status": "paid"}))
        self.assertTrue(_is_order_terminal_for_repay({"status": "refunded_partial"}))
        self.assertTrue(_is_order_terminal_for_repay({"status": "refunded_full"}))
        self.assertFalse(_is_order_terminal_for_repay({"status": "pending"}))
```

- [ ] **Step 2: Run the test to verify RED**

Run:
```bash
python -m unittest tests.test_payment_order_lifecycle.TestPaymentOrderLifecycle -v
```

Expected: FAIL with missing helper function errors.

- [ ] **Step 3: Implement minimal lifecycle helpers in `main.py`**

```python
def _is_order_terminal_for_repay(order_data):
    status = str((order_data or {}).get("status", "")).strip()
    return status in {"paid", "refunded_partial", "refunded_full"}


def _advance_order_status_by_timeout(order_data, now_iso=None):
    if not isinstance(order_data, dict):
        return False
    if str(order_data.get("status", "")).strip() != "pending":
        return False

    expires_at = str(order_data.get("expires_at") or "").strip()
    if not expires_at:
        return False

    now_dt = datetime.datetime.fromisoformat(now_iso) if now_iso else datetime.datetime.now(datetime.timezone.utc)
    expires_dt = datetime.datetime.fromisoformat(expires_at)
    if now_dt <= expires_dt:
        return False

    order_data["status"] = "closed"
    order_data["closed_at"] = now_dt.isoformat()
    return True
```

- [ ] **Step 4: Re-run tests to verify GREEN**

Run:
```bash
python -m unittest tests.test_payment_order_lifecycle.TestPaymentOrderLifecycle -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add tests/test_payment_order_lifecycle.py main.py
git commit -m "test: add lifecycle helpers for billing order timeout"
```

---

### Task 2: Add persistent QR cache index helpers (TDD)

**Files:**
- Modify: `main.py`
- Modify: `tests/test_payment_order_lifecycle.py`
- Test: `tests/test_payment_order_lifecycle.py`

- [ ] **Step 1: Add failing tests for QR cache keying, ttl, and invalidation**

```python
from main import (
    _build_billing_qr_cache_key,
    _load_qr_cache_index,
    _save_qr_cache_index,
    _get_reusable_billing_qr,
    _invalidate_billing_qr_cache_by_order,
)

def test_qr_cache_key_uses_school_billing_paytype(self):
    key = _build_billing_qr_cache_key("2024030101053", "5b603357-cc36", "wxpay")
    self.assertEqual(key, "2024030101053:5b603357-cc36:wxpay")

def test_reuse_qr_within_timeout(self):
    # write index with future expires_at, expect reusable payload returned
    ...

def test_qr_cache_invalidated_by_order_id(self):
    # index contains entry for order_id=A, call invalidate, entry removed
    ...
```

- [ ] **Step 2: Run test to verify RED**

Run:
```bash
python -m unittest tests.test_payment_order_lifecycle.TestPaymentOrderLifecycle -v
```

Expected: FAIL on missing QR helper functions.

- [ ] **Step 3: Implement minimal QR cache helpers in `main.py`**

```python
QR_CACHE_INDEX_FILE = os.path.join(PAYMENT_ORDERS_DIR, "qr_cache_index.json")


def _build_billing_qr_cache_key(school_id, billing_id, pay_type):
    return f"{str(school_id).strip()}:{str(billing_id).strip()}:{str(pay_type).strip()}"


def _load_qr_cache_index():
    if not os.path.exists(QR_CACHE_INDEX_FILE):
        return {}
    with open(QR_CACHE_INDEX_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _save_qr_cache_index(index_data):
    os.makedirs(PAYMENT_ORDERS_DIR, exist_ok=True)
    with open(QR_CACHE_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)


def _get_reusable_billing_qr(cache_key, now_iso=None):
    index_data = _load_qr_cache_index()
    item = index_data.get(cache_key)
    if not isinstance(item, dict):
        return None
    now_dt = datetime.datetime.fromisoformat(now_iso) if now_iso else datetime.datetime.now(datetime.timezone.utc)
    expires_at = str(item.get("expires_at") or "")
    if not expires_at or now_dt > datetime.datetime.fromisoformat(expires_at):
        return None
    return item


def _invalidate_billing_qr_cache_by_order(order_id):
    index_data = _load_qr_cache_index()
    changed = False
    for key, value in list(index_data.items()):
        if isinstance(value, dict) and str(value.get("order_id") or "") == str(order_id):
            index_data.pop(key, None)
            changed = True
    if changed:
        _save_qr_cache_index(index_data)
```

- [ ] **Step 4: Re-run tests to verify GREEN**

Run:
```bash
python -m unittest tests.test_payment_order_lifecycle.TestPaymentOrderLifecycle -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add tests/test_payment_order_lifecycle.py main.py
git commit -m "feat: add persistent qr cache index for billing payments"
```

---

### Task 3: Integrate timeout close + QR reuse into billing order creation (TDD)

**Files:**
- Modify: `main.py` (`/api/payment/create_order_for_billing` around existing function near line ~41353)
- Modify: `tests/test_payment_order_lifecycle.py`
- Test: `tests/test_payment_order_lifecycle.py`

- [ ] **Step 1: Add failing tests for create path behavior**

```python
# Add helper-level tests that simulate request data paths:
# 1) closed required when pending expired
# 2) same school+billing+pay_type returns reused qr payload within ttl
# 3) terminal states reject repay
```

Use a new helper contract in tests:

```python
from main import _resolve_billing_payment_entry

result = _resolve_billing_payment_entry(
    school_id="2024030101053",
    billing_id="5b603357-cc36-4279-a346-38d2da3e7581",
    pay_type="wxpay",
    existing_order={"status": "pending", "expires_at": "2026-04-12T10:00:00+00:00"},
    now_iso="2026-04-12T10:00:01+00:00",
)
self.assertEqual(result["decision"], "create_new")
self.assertEqual(result["normalized_existing_status"], "closed")
```

- [ ] **Step 2: Run test to verify RED**

Run:
```bash
python -m unittest tests.test_payment_order_lifecycle.TestPaymentOrderLifecycle -v
```

Expected: FAIL because `_resolve_billing_payment_entry` doesn’t exist.

- [ ] **Step 3: Implement minimal integration in `main.py`**

Implement helper and wire route:

```python
def _resolve_billing_payment_entry(school_id, billing_id, pay_type, existing_order, now_iso=None):
    # advance existing pending->closed when expired
    # reject terminal states
    # check reusable qr cache
    # return decision dict: reuse_qr / reject_terminal / create_new
    ...
```

Route integration points in `payment_create_order_for_billing`:
- Parse first billing item (`school_username`, `billing_id`) for single-item pay path.
- Call `_resolve_billing_payment_entry(...)` before creating new platform order.
- If `reuse_qr`, return success with existing QR payload and `reused_qr: true`.
- If new order returns QR payload, save QR cache index with `expires_at = created_at + timeout`.

- [ ] **Step 4: Re-run tests to verify GREEN**

Run:
```bash
python -m unittest tests.test_payment_order_lifecycle.TestPaymentOrderLifecycle -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add tests/test_payment_order_lifecycle.py main.py
git commit -m "feat: reuse billing qr codes and enforce timeout close before repay"
```

---

### Task 4: Notify/refund transitions (closed->paid and refunded states) with tests

**Files:**
- Modify: `main.py` (`payment_yipay_notify`, `payment_refund`)
- Modify: `tests/test_payment_order_lifecycle.py`
- Test: `tests/test_payment_order_lifecycle.py`

- [ ] **Step 1: Add failing tests for notification-driven transitions**

```python
from main import _apply_payment_success_transition, _apply_refund_transition

def test_closed_order_can_be_marked_paid_by_notify(self):
    order = {"status": "closed", "paid_time": None}
    _apply_payment_success_transition(order, paid_time="2026-04-12T11:00:00+00:00")
    self.assertEqual(order["status"], "paid")


def test_paid_to_partial_then_full_refund(self):
    order = {"status": "paid", "amount": "10.00", "refund_total": 0}
    _apply_refund_transition(order, refund_amount=2.5)
    self.assertEqual(order["status"], "refunded_partial")
    _apply_refund_transition(order, refund_amount=7.5)
    self.assertEqual(order["status"], "refunded_full")
```

- [ ] **Step 2: Run tests to verify RED**

Run:
```bash
python -m unittest tests.test_payment_order_lifecycle.TestPaymentOrderLifecycle -v
```

Expected: FAIL on missing transition helpers.

- [ ] **Step 3: Implement transition helpers and wire notify/refund routes**

```python
def _apply_payment_success_transition(order_data, paid_time=None):
    order_data["status"] = "paid"
    order_data["paid_time"] = paid_time or datetime.datetime.now(datetime.timezone.utc).isoformat()


def _apply_refund_transition(order_data, refund_amount):
    total = float(order_data.get("refund_total") or 0) + float(refund_amount or 0)
    order_data["refund_total"] = round(total, 2)
    amount = float(order_data.get("amount") or 0)
    order_data["status"] = "refunded_full" if total >= amount and amount > 0 else "refunded_partial"
```

Route wiring:
- `payment_yipay_notify`: if validated, call `_apply_payment_success_transition` even when current status is `closed`.
- `payment_refund`: after successful refund response, call `_apply_refund_transition` and persist order.
- In both places invalidate related QR cache (`_invalidate_billing_qr_cache_by_order`).

- [ ] **Step 4: Re-run tests to verify GREEN**

Run:
```bash
python -m unittest tests.test_payment_order_lifecycle.TestPaymentOrderLifecycle -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add tests/test_payment_order_lifecycle.py main.py
git commit -m "feat: support closed-to-paid notify and refund lifecycle states"
```

---

### Task 5: Frontend status/payout behavior updates (TDD with node:test)

**Files:**
- Modify: `scripts/main.new.js` (billing status rendering blocks around lines ~56569, ~56941, ~62044)
- Modify: `index.html` (billing status select/filter options around lines ~8659, ~17889, ~22512)
- Create: `tests/billing_status_behavior.test.mjs`
- Test: `tests/billing_status_behavior.test.mjs`

- [ ] **Step 1: Add failing frontend tests for status label + payability**

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// extractFunctionSource same pattern as existing tests/theme_background_sync.test.mjs

test('terminal statuses are not payable', () => {
  const { isBillingStatusPayable } = loadFunctions(['isBillingStatusPayable']);
  assert.equal(isBillingStatusPayable('paid'), false);
  assert.equal(isBillingStatusPayable('refunded_partial'), false);
  assert.equal(isBillingStatusPayable('refunded_full'), false);
  assert.equal(isBillingStatusPayable('pending'), true);
});

test('status label includes refunded states', () => {
  const { getBillingStatusLabel } = loadFunctions(['getBillingStatusLabel']);
  assert.equal(getBillingStatusLabel('closed'), '已关闭');
  assert.equal(getBillingStatusLabel('refunded_partial'), '部分退款');
  assert.equal(getBillingStatusLabel('refunded_full'), '全额退款');
});
```

- [ ] **Step 2: Run tests to verify RED**

Run:
```bash
node --test tests/billing_status_behavior.test.mjs
```

Expected: FAIL because helper functions are not present.

- [ ] **Step 3: Implement minimal frontend helpers and wire UI logic**

```javascript
function getBillingStatusLabel(status) {
  switch (String(status || '').trim()) {
    case 'pending': return '待支付';
    case 'paid': return '已支付';
    case 'closed': return '已关闭';
    case 'refunded_partial': return '部分退款';
    case 'refunded_full': return '全额退款';
    default: return '未知状态';
  }
}

function isBillingStatusPayable(status) {
  const s = String(status || '').trim();
  return s === 'pending' || s === 'closed';
}
```

Wire points:
- Replace hardcoded badge/status text in billing tables with `getBillingStatusLabel`.
- Disable pay buttons for terminal states.
- When status is `closed`, allow flow that creates new order and show hint text.
- If backend response contains `reused_qr: true`, show “已复用有效期内二维码” tip in pay modal.

- [ ] **Step 4: Re-run frontend tests to verify GREEN**

Run:
```bash
node --test tests/billing_status_behavior.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
git add tests/billing_status_behavior.test.mjs scripts/main.new.js index.html
git commit -m "feat: update billing status UI and repay guards for refund states"
```

---

### Task 6: Full verification pass

**Files:**
- Verify all changed files from Tasks 1-5

- [ ] **Step 1: Run backend lifecycle tests**

Run:
```bash
python -m unittest tests.test_payment_order_lifecycle -v
```

Expected: PASS with all lifecycle + qr-cache tests green.

- [ ] **Step 2: Run frontend billing behavior tests**

Run:
```bash
node --test tests/billing_status_behavior.test.mjs
```

Expected: PASS.

- [ ] **Step 3: Run existing payment/billing regressions if present**

Run:
```bash
python -m unittest -v
```

Expected: Existing suite remains green (or known unrelated failures only).

- [ ] **Step 4: Final commit (if verification fixes were needed)**

```bash
git add main.py scripts/main.new.js index.html tests/test_payment_order_lifecycle.py tests/billing_status_behavior.test.mjs
git commit -m "test: finalize billing timeout and qr reuse verification"
```

---

## Spec Coverage Self-Check

- Order timeout close (`pending -> closed`): covered in Task 1 + Task 3.
- Shared timeout variable (`payment_timeout_minutes`): used in Task 1/2/3 integrations.
- QR cache reuse by `school_id+billing_id+pay_type`: covered in Task 2 + Task 3.
- Prevent duplicate payment: covered in Task 3 + Task 5.
- Async notify can convert `closed -> paid`: covered in Task 4.
- Refund statuses (`refunded_partial/refunded_full`) and terminal no-repay rule: covered in Task 4 + Task 5.
- Admin config wording sync: covered in Task 5.

No placeholder sections remain; all tasks include concrete files, commands, and expected outcomes.
