"""Opt-in production UI lifecycle control at an authorized, fulfilled origin.

No page is fetched from that domain. Vendor SDK requests remain direct. The
credential environment contract and acceptance gates match the proxy runner.
"""

import json
import logging
import os
import subprocess
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from browser_map_proxy_smoke import (
    ROOT, PROXY_HOSTS, browser_step, evaluate_acceptance, exercise_map_lifecycle,
    production_planner, safe_error, smoke_results_passed,
)


def run(credentials, *, render_legacy=False):
    assert credentials and set(credentials) <= PROXY_HOSTS.keys()
    bundle = None
    if not render_legacy:
        env = {name: value for name, value in os.environ.items() if name != "MAP_SMOKE_CREDENTIALS"}
        compiled = subprocess.run(["node", str(ROOT / "tests" / "map_ui_browser_fixture.mjs")],
                                  cwd=ROOT, env=env, capture_output=True, text=True,
                                  encoding="utf-8", timeout=90, check=True)
        bundle = json.loads(compiled.stdout)
    results = []
    with sync_playwright() as playwright:
        browser_path = os.environ.get("MAP_SMOKE_BROWSER_PATH")
        browser = playwright.chromium.launch(headless=True, **({"executable_path": browser_path} if browser_path else {}))
        try:
            for provider, credential in credentials.items():
                parsed = urlsplit(credential["origin"])
                assert parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username
                origin = f"{parsed.scheme}://{parsed.netloc}"
                context = browser.new_context(service_workers="block")
                try:
                    def serve(route):
                        name = urlsplit(route.request.url).path.lstrip("/")
                        if name == "map-acceptance":
                            script = '<script type="module" src="/map-ui.js"></script>' if bundle else ""
                            return route.fulfill(body='<!doctype html><style>html,body,#map-ui,.h-full{height:100%;margin:0}.w-full{width:100%}</style><div id="map-ui"></div><div id="map"></div>' + script, content_type="text/html")
                        if bundle and name in bundle["files"]:
                            return route.fulfill(body=bundle["files"][name], content_type="application/javascript")
                        if name == "legacy-fixture.js":
                            return route.fulfill(body=(ROOT / "tests" / "legacy_map_browser_fixture.js").read_text(encoding="utf-8"), content_type="application/javascript")
                        if name in {"legacy-scripts/legacy-map-runtime.js", "legacy-scripts/legacy-map-render.js"}:
                            return route.fulfill(body=(ROOT / "scripts" / name.split("/")[-1]).read_text(encoding="utf-8"), content_type="application/javascript")
                        return route.fulfill(status=404, body="Not found", content_type="text/plain")

                    context.route(origin + "/**", serve)
                    page = context.new_page()
                    errors, console, rejections, direct, failures = [], [], [], [], []
                    page.expose_function("recordSmokeRejection", lambda value: rejections.append(safe_error(value, credentials)))
                    page.add_init_script("addEventListener('unhandledrejection', event => { window.recordSmokeRejection(String(event.reason?.stack || event.reason || 'unhandled rejection')); });")
                    page.on("pageerror", lambda error: errors.append(safe_error(getattr(error, "stack", None) or error, credentials)))
                    page.on("console", lambda message: console.append(safe_error(message.text, credentials)) if message.type == "error" else None)
                    page.on("dialog", lambda dialog: dialog.dismiss())
                    page.on("request", lambda req: direct.append({"host": urlsplit(req.url).hostname, "type": req.resource_type}) if urlsplit(req.url).hostname in PROXY_HOSTS[provider] else None)

                    def response_received(response):
                        parsed_response = urlsplit(response.url)
                        if response.status >= 400 or (response.request.resource_type == "script" and "javascript" not in response.headers.get("content-type", "")):
                            failures.append({"host": parsed_response.hostname, "status": response.status, "path": safe_error(parsed_response.path, credentials)})

                    page.on("response", response_received)
                    page.goto(origin + "/map-acceptance", wait_until="domcontentloaded")
                    args = [[[116.397128, 39.916527], [116.398128, 39.916527]], credential["key"],
                            {"api_retries": 0, "api_fallback_line": False, "api_retry_delay_s": 0, "api_queue_interval_s": 0}]
                    args += [["AMap.Walking"], "walking", credential.get("securityJsCode", "")] if provider == "amap" else ["walking"]
                    route = {}
                    rounds = []
                    try:
                        route = browser_step(page, "async ({source,args}) => (0,eval)('('+source+')')(args)", {"source": production_planner(provider), "args": args}, timeout_ms=60000)
                        if render_legacy:
                            page.evaluate("() => document.getElementById('map')?.remove()")
                            page.add_script_tag(url=origin + "/legacy-fixture.js")
                        else:
                            page.goto(origin + "/map-acceptance", wait_until="domcontentloaded")
                        rounds = exercise_map_lifecycle(page, provider, credential, session_id="control-session",
                                                       render_ui=not render_legacy, errors=errors,
                                                       rejections=rejections, console=console, proxy_enabled=False,
                                                       script_base=origin + "/legacy-scripts/")
                    except Exception as error:
                        route["map_error"] = safe_error(error, credentials)
                    page.wait_for_timeout(2000)
                    results.append(evaluate_acceptance({
                        "provider": provider, "direct_control": True, "proxy_enabled": False,
                        "route_success": bool(route) and not route.get("error"),
                        "route_points": len(route.get("path", [])), "map_ready": bool(rounds) and all(row["functional_pass"] for row in rounds),
                        "map_error": route.get("map_error"), "error": safe_error(route.get("error", ""), credentials),
                        "rounds": rounds, "direct_requests": direct, "upstream_failures": failures,
                        "script_errors": len(errors), "script_error_messages": list(dict.fromkeys(errors)),
                        "unhandled_rejections": len(rejections), "unhandled_rejection_messages": list(dict.fromkeys(rejections)),
                        "console_error_messages": list(dict.fromkeys(console)),
                    }))
                finally:
                    context.close()
        finally:
            browser.close()
    return results


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    credentials = json.loads(os.environ.get("MAP_SMOKE_CREDENTIALS", "{}"))
    try:
        results = run(credentials, render_legacy=os.environ.get("MAP_SMOKE_RENDER_LEGACY") == "1")
    except Exception as error:
        print(json.dumps({"error": safe_error(error, credentials)}, ensure_ascii=True))
        raise SystemExit(1) from None
    print(json.dumps(results, ensure_ascii=True, indent=2))
    raise SystemExit(0 if smoke_results_passed(results) else 1)
