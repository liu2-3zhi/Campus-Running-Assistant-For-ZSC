"""Opt-in direct SDK control for distinguishing vendor teardown from proxy errors.

Serves only an in-memory test page at the credential's authorized origin using
Playwright route.fulfill. No application page is requested from that domain.
Credentials follow browser_map_proxy_smoke.py's ephemeral environment contract.
"""

import json
import logging
import os
import subprocess
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from browser_map_proxy_smoke import ROOT, browser_step, safe_error


def run(credentials):
    env = {name: value for name, value in os.environ.items() if name != "MAP_SMOKE_CREDENTIALS"}
    compiled = subprocess.run(["node", str(ROOT / "tests" / "map_ui_browser_fixture.mjs")],
                              cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=90, check=True)
    bundle = json.loads(compiled.stdout)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for provider, credential in credentials.items():
                origin = credential["origin"].rstrip("/")
                assert urlsplit(origin).scheme in {"http", "https"}
                context = browser.new_context(service_workers="block")
                try:
                    def serve(route):
                        name = urlsplit(route.request.url).path.lstrip("/")
                        if name == "map-acceptance":
                            body = '<!doctype html><style>html,body,#map-ui,.h-full{height:100%;margin:0}.w-full{width:100%}</style><div id="map-ui"></div><script type="module" src="/map-ui.js"></script>'
                            return route.fulfill(body=body, content_type="text/html")
                        if name in bundle["files"]:
                            return route.fulfill(body=bundle["files"][name], content_type="application/javascript")
                        return route.abort()

                    context.route(origin + "/**", serve)
                    page = context.new_page()
                    errors, console = [], []
                    page.on("pageerror", lambda error: errors.append(safe_error(getattr(error, "stack", None) or error, credentials)))
                    page.on("console", lambda message: console.append(safe_error(message.text, credentials)) if message.type == "error" else None)
                    page.on("dialog", lambda dialog: dialog.dismiss())
                    page.goto(origin + "/map-acceptance", wait_until="domcontentloaded")
                    args = {"provider": provider, "key": credential["key"], "securityJsCode": credential.get("securityJsCode", ""), "sessionId": "control-session", "frontendProxyEnabled": False}
                    browser_step(page, "args => mountMapAcceptance(args)", args)
                    page.wait_for_function("window.mapAcceptance?.ready()", timeout=30000)
                    browser_step(page, "() => mapAcceptance.seed()")
                    browser_step(page, "() => mapAcceptance.progress(2)")
                    browser_step(page, "() => mapAcceptance.progress(4)")
                    browser_step(page, "() => mapAcceptance.finish()")
                    browser_step(page, "() => mapAcceptance.seed(1,1)")
                    browser_step(page, "() => mapAcceptance.destroy()")
                    browser_step(page, "args => mountMapAcceptance(args)", args)
                    page.wait_for_function("window.mapAcceptance?.ready()", timeout=30000)
                    browser_step(page, "() => mapAcceptance.seed(1,2)")
                    page.wait_for_timeout(2000)
                    results.append({"provider": provider, "direct_control": True, "script_errors": len(errors), "script_error_messages": list(dict.fromkeys(errors)), "console_error_messages": list(dict.fromkeys(console))})
                finally:
                    context.close()
        finally:
            browser.close()
    return results


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    credentials = json.loads(os.environ.get("MAP_SMOKE_CREDENTIALS", "{}"))
    try:
        print(json.dumps(run(credentials), ensure_ascii=True, indent=2))
    except Exception as error:
        print(json.dumps({"error": safe_error(error, credentials)}, ensure_ascii=True))
        sys.exit(1)
