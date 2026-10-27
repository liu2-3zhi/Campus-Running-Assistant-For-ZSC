"""Opt-in production browser-pool origin checks. Credentials come only from env.

MAP_SMOKE_CREDENTIALS is a JSON object keyed by provider, with key, origin and
optional securityJsCode. This script never starts the application or saves data.
"""

from __future__ import annotations

import ast
import json
import logging
import os
from pathlib import Path
import queue
import re
import sys
import threading
import time
from types import MethodType
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from background_task_manager import ChromeBrowserPool
from map_error_catalog import map_error_retry_policy
from map_runtime_origin import MAP_RUNTIME_MARKER, normalize_backend_page_origin


def production_planner(provider):
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    name = f"_plan_route_path_with_{provider}_runtime"
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "execute_js":
            return ast.literal_eval(node.args[1])
    raise AssertionError(f"{provider}: production planner not found")


def safe_error(value, credentials):
    text = str(value)
    for credential in credentials.values():
        for field in ("key", "securityJsCode"):
            if credential.get(field):
                text = text.replace(credential[field], "<redacted>")
    return re.sub(r"https?://[^\s]+", "<url>", text)[:400]


def minimal_pool():
    """Use the actual queue/worker/context/execute paths without full app setup."""
    pool = ChromeBrowserPool.__new__(ChromeBrowserPool)
    pool.headless = True
    pool.max_instances = 4
    pool._native_threading = threading
    pool._native_queue = queue
    pool._request_queue = queue.Queue()
    pool._stop_flag = threading.Event()
    pool._playwright = None
    pool._browser = None
    pool._contexts = {}
    pool._initialized = False
    pool.origin_audits = {}

    def initialize(self):
        if not self._initialized:
            self._playwright = sync_playwright().start()
            browser_path = os.environ.get("MAP_SMOKE_BROWSER_PATH")
            self._browser = self._playwright.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"],
                **({"executable_path": browser_path} if browser_path else {}),
            )
            self._initialized = True
        return {"success": True}

    def get_context(self, session_id):
        result = ChromeBrowserPool._do_get_context(self, session_id)
        if not result.get("success"):
            return result
        entry = self._contexts[session_id]
        context, page = entry["context"], entry["page"]
        if session_id not in self.origin_audits:
            audit = {"external_document_attempts": 0, "local_documents": [], "initial_cookies": len(context.cookies())}
            self.origin_audits[session_id] = audit

            def guard(route):
                parsed = urlsplit(route.request.url)
                if route.request.is_navigation_request() and parsed.path == "/map-runtime":
                    # A correctly fulfilled page route prevents reaching this guard.
                    audit["external_document_attempts"] += 1
                    route.abort()
                else:
                    route.continue_()

            def response_received(response):
                parsed = urlsplit(response.url)
                if response.request.is_navigation_request() and parsed.path == "/map-runtime":
                    audit["local_documents"].append({
                        "origin": f"{parsed.scheme}://{parsed.netloc}",
                        "server_address": response.server_addr(),
                        "cache_control": response.headers.get("cache-control"),
                        "referrer_policy": response.headers.get("referrer-policy"),
                    })

            context.route("**/*", guard)
            page.on("response", response_received)
        result["audit"] = {
            **self.origin_audits[session_id], "cookies": len(context.cookies()),
            "cookie_metadata": [{"domain": item["domain"], "name": item["name"]} for item in context.cookies()],
            "service_workers": len(context.service_workers),
        }
        return result

    pool._do_initialize = MethodType(initialize, pool)
    pool._do_get_context = MethodType(get_context, pool)
    pool._worker_thread = threading.Thread(target=pool._worker_loop, name="MapOriginSmokeWorker")
    pool._worker_thread.start()
    return pool


INSPECT = """async () => {
    await new Promise(resolve => setTimeout(resolve, 250));
    return {origin:location.origin, url:location.href, cookie:document.cookie,
        marker:document.querySelector('meta[name="zx-map-runtime"]')?.content,
        serviceWorkers:navigator.serviceWorker ? (await navigator.serviceWorker.getRegistrations()).length : 0};
}"""


def run(credentials):
    assert credentials and set(credentials) <= {"amap", "tencent", "baidu", "tianditu"}, "Explicit provider credentials required"
    assert all(item.get("key") and item.get("origin") for item in credentials.values()), "Key and authorized origin required"
    pool = minimal_pool()
    results = []
    checks = {}
    try:
        for provider, credential in credentials.items():
            origin = normalize_backend_page_origin(credential["origin"])
            session_id = f"origin-smoke-{provider}"
            deadline = time.time() * 1000 + 45000
            params = {
                "api_retries": 0, "api_fallback_line": False, "api_retry_delay_s": 0,
                "api_queue_interval_s": 0, "_deadline_epoch_ms": deadline,
                "_map_error_retry_policy": map_error_retry_policy(provider),
            }
            args = [[[116.397128, 39.916527], [116.398128, 39.916527]], credential["key"], params]
            args += [["AMap.Walking"], "walking", credential.get("securityJsCode", "")] if provider == "amap" else ["walking"]
            started = time.monotonic()
            diagnostic = {"diagnostic_id": f"origin-smoke-{provider}", "provider": provider,
                          "sensitive_values": [credential["key"], credential.get("securityJsCode", "")]}
            route = pool.execute_js(session_id, production_planner(provider), *args,
                                    diagnostic_context=diagnostic, runtime_page_origin=origin, deadline_epoch_ms=deadline)
            inspected = pool.execute_js(session_id, INSPECT, diagnostic_context=diagnostic,
                                        deadline_epoch_ms=time.time() * 1000 + 5000)
            audit = pool._send_request("get_context", {"session_id": session_id})["audit"]
            local = audit["local_documents"]
            cookie_metadata = audit["cookie_metadata"]
            application_cookies = [item for item in cookie_metadata
                                   if item["domain"].lstrip(".") == urlsplit(origin).hostname
                                   or item["name"].lower() in {"auth_token", "session"}]
            isolated = (
                inspected.get("origin") == origin and inspected.get("marker") == MAP_RUNTIME_MARKER
                and not inspected.get("serviceWorkers") and not application_cookies
                and audit["initial_cookies"] == 0 and audit["service_workers"] == 0
                and audit["external_document_attempts"] == 0 and len(local) == 1
                and local[0]["origin"] == origin and local[0]["server_address"] is None
                and local[0]["cache_control"] == "no-store" and local[0]["referrer_policy"] == "strict-origin"
                and inspected.get("url") == origin + "/map-runtime"
            )
            path = route.get("path") if isinstance(route, dict) else None
            result = {
                "provider": provider, "origin": origin, "route_points": len(path or []),
                "origin_isolation_passed": isolated, "external_document_attempts": audit["external_document_attempts"],
                "initial_cookies": audit["initial_cookies"], "application_cookies": len(application_cookies),
                "cookie_metadata": cookie_metadata, "service_workers": audit["service_workers"],
                "elapsed_s": round(time.monotonic() - started, 2),
            }
            if not path or route.get("error") or not isolated:
                result["error"] = safe_error(route.get("error") or "Runtime origin isolation check failed", credentials)
            results.append(result)
            pool.close_context(session_id)
            result["context_closed"] = session_id not in pool._contexts

        expired = pool.execute_js("origin-smoke-expired", "() => 1", diagnostic_context={"diagnostic_id": "expired"},
                                  runtime_page_origin=origin, deadline_epoch_ms=time.time() * 1000 - 10)
        checks["expired_before_context"] = bool(expired.get("error")) and "origin-smoke-expired" not in pool._contexts
        deadline_result = pool.execute_js("origin-smoke-timeout", "() => new Promise(() => {})",
                                         diagnostic_context={"diagnostic_id": "timeout"}, runtime_page_origin=origin,
                                         deadline_epoch_ms=time.time() * 1000 + 600)
        after_timeout = pool.execute_js("origin-smoke-timeout", "() => location.href", deadline_epoch_ms=time.time() * 1000 + 3000)
        checks["deadline_cancelled_to_blank"] = bool(deadline_result.get("error")) and after_timeout == "about:blank"
    finally:
        pool.shutdown()
        checks["worker_closed"] = not pool._worker_thread.is_alive()
        checks["contexts_closed"] = not pool._contexts
    return {"providers": results, "checks": checks}


if __name__ == "__main__":
    logging.basicConfig(level=logging.CRITICAL)
    raw_credentials = os.environ.pop("MAP_SMOKE_CREDENTIALS", "")
    if not raw_credentials:
        raise SystemExit("Set MAP_SMOKE_CREDENTIALS explicitly; no stored credentials are read")
    credentials = json.loads(raw_credentials)
    try:
        outcome = run(credentials)
        print(json.dumps(outcome, ensure_ascii=False))
        raise SystemExit(0 if all(item["route_points"] and item["origin_isolation_passed"] and item["context_closed"] and not item.get("error")
                                 for item in outcome["providers"]) and all(outcome["checks"].values()) else 1)
    except Exception as error:
        print(json.dumps({"error": safe_error(error, credentials)}, ensure_ascii=False))
        raise SystemExit(1)
