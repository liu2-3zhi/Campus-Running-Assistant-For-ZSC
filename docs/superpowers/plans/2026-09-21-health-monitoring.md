# Health Monitoring And Legacy Panel Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/health` report live uptime and administrator-only memory diagnostics, and preserve scroll position across refreshes in both old PC and mobile health panels.

**Architecture:** Keep the existing health status aggregation and administrator token/group check. Add monotonic uptime and a pure runtime-diagnostic collector in `main.py`, return diagnostics only after the existing admin check, and add no-store response headers. In `scripts/main.new.js`, capture all relevant scroll containers before replacing health HTML, render shared diagnostic cards, and restore scroll positions after PC, single-account mobile copy, and multi-account mobile refreshes.

**Tech Stack:** Python, Flask, unittest/mock, browser Fetch API, vanilla JavaScript, Node `node:test`, existing Tailwind utility classes.

---

### Task 1: Record and verify the backend contract

**Files:**
- Modify: `tests/test_health_monitoring_tiered_visibility.py`

- [ ] **Step 1: Add failing backend tests**

Add tests for the desired contract:

```python
    def test_health_route_uses_monotonic_uptime_and_no_store_headers(self):
        app = Flask(__name__)
        component_results = [
            {"name": "running_core", "critical": True, "status": "ok", "message": "ok", "checks": {}},
            {"name": "payment_system", "critical": False, "status": "ok", "message": "ok", "checks": {}},
            {"name": "sms_system", "critical": False, "status": "ok", "message": "ok", "checks": {}},
        ]

        with mock.patch.object(main_module, "server_start_time", 1000, create=True), \
             mock.patch.object(main_module, "server_start_monotonic", 10, create=True), \
             mock.patch.object(main_module.time, "time", side_effect=[2000, 2000, 2000]), \
             mock.patch.object(main_module.time, "monotonic", return_value=301), \
             mock.patch.object(main_module, "request", flask_request, create=True), \
             mock.patch.object(main_module, "jsonify", jsonify, create=True), \
             mock.patch.object(main_module, "_check_running_core_health", return_value=component_results[0]), \
             mock.patch.object(main_module, "_check_payment_system_health", return_value=component_results[1]), \
             mock.patch.object(main_module, "_check_sms_system_health", return_value=component_results[2]):
            main_module._register_health_route(app)

            with app.test_client() as client:
                response = client.get("/health")

        self.assertEqual(response.get_json()["uptime_seconds"], 291)
        self.assertEqual(response.get_json()["uptime_formatted"], "4分钟51秒")
        self.assertEqual(response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(response.headers["Expires"], "0")

    def test_health_route_exposes_memory_diagnostics_only_to_admin(self):
        app = Flask(__name__)
        component_results = [
            {"name": "running_core", "critical": True, "status": "ok", "message": "ok", "checks": {}},
            {"name": "payment_system", "critical": False, "status": "ok", "message": "ok", "checks": {}},
            {"name": "sms_system", "critical": False, "status": "ok", "message": "ok", "checks": {}},
        ]
        diagnostics = {"process_id": 123, "rss_mb": 42.5, "active_threads": 7, "gc_counts": [1, 2, 3]}

        with mock.patch.object(main_module, "server_start_time", 0, create=True), \
             mock.patch.object(main_module, "server_start_monotonic", 0, create=True), \
             mock.patch.object(main_module, "request", flask_request, create=True), \
             mock.patch.object(main_module, "jsonify", jsonify, create=True), \
             mock.patch.object(main_module, "_collect_runtime_memory_diagnostics", return_value=diagnostics), \
             mock.patch.object(main_module, "_is_admin_health_view_from_token", side_effect=[False, True]), \
             mock.patch.object(main_module, "_check_running_core_health", return_value=component_results[0]), \
             mock.patch.object(main_module, "_check_payment_system_health", return_value=component_results[1]), \
             mock.patch.object(main_module, "_check_sms_system_health", return_value=component_results[2]):
            main_module._register_health_route(app)

            with app.test_client() as client:
                public_payload = client.get("/health").get_json()
                admin_payload = client.get("/health").get_json()

        self.assertNotIn("memory_diagnostics", public_payload)
        self.assertEqual(admin_payload["memory_diagnostics"], diagnostics)
```

- [ ] **Step 2: Run the focused tests and confirm the expected failure**

Run:

```powershell
python -m pytest tests/test_health_monitoring_tiered_visibility.py -q
```

Expected: FAIL because the monotonic uptime helper, cache headers, and `memory_diagnostics` response do not exist yet.

### Task 2: Implement live uptime and administrator memory diagnostics

**Files:**
- Modify: `main.py:23060-23135`
- Modify: `main.py:27859-27995`
- Modify: `main.py:28218-28235`

- [ ] **Step 1: Add minimal runtime helpers**

Implement `_get_health_uptime_seconds()` using `time.monotonic()` and a non-negative wall-clock fallback. Implement `_collect_runtime_memory_diagnostics()` with safe `globals().get()` access for sessions and caches, current thread counts, browser contexts, RSS values, process ID, server start timestamp, and `gc.get_count()`. Refactor `_log_runtime_memory_diagnostics()` to log values from the collector without changing its existing log prefix or field meanings.

- [ ] **Step 2: Record monotonic server start**

In `start_web_server()`, assign `server_start_monotonic = time.monotonic()` immediately after the existing `server_start_time = time.time()` assignment.

- [ ] **Step 3: Update `/health`**

Use `_get_health_uptime_seconds()` instead of subtracting the wall clock directly. After the existing administrator check, add `memory_diagnostics` only for administrators. Return a Flask response object with status code `http_status` and these headers:

```python
response = jsonify(payload)
response.status_code = http_status
response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
response.headers["Pragma"] = "no-cache"
response.headers["Expires"] = "0"
return response
```

- [ ] **Step 4: Run the focused backend tests**

Run:

```powershell
python -m pytest tests/test_health_monitoring_tiered_visibility.py -q
```

Expected: all health visibility, uptime, cache-header, and memory-diagnostic tests pass.

### Task 3: Add failing legacy UI refresh and diagnostic rendering tests

**Files:**
- Modify: `tests/health_status_ui_behavior.test.mjs`

- [ ] **Step 1: Add pure scroll-helper behavior coverage**

Load `captureHealthScrollPositions` and `restoreHealthScrollPositions` from `scripts/main.new.js` with a minimal fake `window`/`document` environment, then assert that a saved element scroll position is restored after the element value is changed.

- [ ] **Step 2: Add source contract assertions**

Assert that both `loadHealthStatus` and `loadMobileMultiHealthStatus` contain `captureHealthScrollPositions`, `restoreHealthScrollPositions`, `memory_diagnostics`, and `cache: "no-store"`. Assert that `copyAdminContentToPanelVersion` also captures and restores the health mobile container position.

- [ ] **Step 3: Run the focused Node tests and confirm the expected failure**

Run:

```powershell
node --test tests/health_status_ui_behavior.test.mjs
```

Expected: FAIL because the scroll helpers, diagnostic rendering, and no-store fetch options are not present.

### Task 4: Implement old PC and mobile health refresh behavior

**Files:**
- Modify: `scripts/main.new.js:24780-25000`
- Modify: `scripts/main.new.js:53978-54150`
- Modify: `scripts/main.new.js:55674-55800`

- [ ] **Step 1: Add shared scroll helpers**

Add `getHealthScrollableElements`, `captureHealthScrollPositions`, and `restoreHealthScrollPositions`. Capture the content element, scrollable ancestors, `document.scrollingElement`, and window coordinates. Restore element coordinates in `requestAnimationFrame` with a `setTimeout` fallback, guarding browser globals.

- [ ] **Step 2: Add shared diagnostic rendering**

Add a renderer that reads `result.memory_diagnostics`, escapes values with existing `escapeHtml`, displays process/start/RSS/thread/cache/GC fields, and returns an empty string when the administrator-only field is absent. Use the renderer in both desktop and multi-account mobile health HTML.

- [ ] **Step 3: Make PC and multi-account mobile refresh non-destructive**

At the beginning of each health loader, capture scroll positions and only display the loading placeholder when the content has not previously loaded. Fetch `/health` with `cache: "no-store"` and `credentials: "include"`. After success or failure, restore the captured positions. On refresh failure after a previous successful render, keep the existing content instead of replacing it with an error placeholder.

- [ ] **Step 4: Preserve single-account mobile copy position**

In `copyAdminContentToPanelVersion`, when `tabType === "health"`, capture the mobile health content position before copying PC HTML and restore it after the copy. Keep the existing compact button, heading, and form-control styling.

- [ ] **Step 5: Run focused frontend tests and syntax validation**

Run:

```powershell
node --test tests/health_status_ui_behavior.test.mjs
node --check scripts/main.new.js
```

Expected: all health UI behavior tests pass and Node reports no syntax errors.

### Task 5: Update visible-build metadata and run full verification

**Files:**
- Modify: `version.json`
- Modify: `agent.md` only if this task reveals a reusable health-panel rule

- [ ] **Step 1: Update `version.json`**

Set `version` to `20260921-<random-alphanumeric-suffix>` and `build_time` to the actual current local timestamp, preserving the existing JSON structure and author.

- [ ] **Step 2: Run required verification**

Run:

```powershell
python -m pytest tests/test_health_monitoring_tiered_visibility.py -q
node --test tests/health_status_ui_behavior.test.mjs
python -m py_compile main.py
node --check scripts/main.new.js
git diff --check
git status --short
```

Expected: all focused tests and syntax/whitespace checks pass. If the broader Vue parity test command still reports the previously observed unrelated legacy parity failures, report them separately without changing Vue code.

- [ ] **Step 3: Inspect staged content and commit on `main`**

Run:

```powershell
git diff --stat
git diff --cached --stat
git diff --cached --name-only
```

Confirm only health backend/UI/tests/docs/version files are staged and no sensitive file is included, then commit:

```powershell
git add main.py scripts/main.new.js tests/test_health_monitoring_tiered_visibility.py tests/health_status_ui_behavior.test.mjs version.json docs/superpowers/specs/2026-09-21-health-monitoring-design.md docs/superpowers/plans/2026-09-21-health-monitoring.md
git commit -m "修复健康检查与旧版面板刷新"
```
