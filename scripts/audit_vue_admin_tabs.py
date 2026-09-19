#!/usr/bin/env python3
"""Open every Vue admin tab and fail on missing, empty, or crashing panels."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import uuid
from dataclasses import dataclass

from playwright.sync_api import sync_playwright


TAB_LABELS = [
    "用户管理",
    "权限组",
    "日志查看",
    "会话管理",
    "系统状态",
    "个人信息",
    "留言板",
    "IP封禁",
    "短信配置",
    "系统配置",
    "验证码",
    "定时提醒",
    "HTTPS",
    "CDN",
    "暴力破解",
    "支付日志",
    "支付设置",
    "定价管理",
    "水印管理",
    "账单管理",
    "账单日志",
    "恢复账号",
]

PERMISSION_KEYS = [
    "manage_users",
    "manage_groups",
    "view_logs",
    "manage_sessions",
    "manage_sms",
    "manage_config",
    "manage_captcha",
    "manage_reminders",
    "manage_ssl",
    "manage_cdn",
    "manage_security",
    "view_payment_logs",
    "manage_payment",
    "manage_pricing",
    "manage_watermark",
    "manage_billing",
    "view_billing_logs",
    "restore_accounts",
]


@dataclass
class TabResult:
    label: str
    status: str
    text_length: int
    preview: str


def create_guest_session(backend_url: str) -> str:
    session_id = str(uuid.uuid4())
    request = urllib.request.Request(
        f"{backend_url.rstrip('/')}/auth/guest_login",
        data=b"{}",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Session-ID": session_id,
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("success"):
        raise RuntimeError(f"guest login failed: {payload}")
    return session_id


def audit_tabs(vue_url: str, session_id: str, minimum_text: int) -> list[TabResult]:
    permissions = {key: True for key in PERMISSION_KEYS}
    results: list[TabResult] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.add_init_script(
            f"sessionStorage.setItem('session_uuid', {json.dumps(session_id)})"
        )
        page = context.new_page()
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        page.goto(f"{vue_url.rstrip('/')}/app", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        page.evaluate(
            """(permissions) => {
              const pinia = document.querySelector('#app').__vue_app__
                .config.globalProperties.$pinia
              const auth = pinia._s.get('auth')
              auth.isAdmin = true
              auth.permissions = permissions
            }""",
            permissions,
        )
        page.wait_for_timeout(200)
        page.get_by_role("button", name="管理", exact=True).click()
        modal = page.locator("#admin-panel-modal")
        modal.wait_for(state="visible")

        for label in TAB_LABELS:
            found = modal.locator("button").evaluate_all(
                """(buttons, label) => {
                  const button = buttons.find(
                    (item) => item.textContent.trim() === label
                  )
                  if (!button) return false
                  button.click()
                  return true
                }""",
                label,
            )
            page.wait_for_timeout(700)
            content = modal.locator(".min-h-0.flex-1").inner_text().strip()
            status = "ok"
            if not found:
                status = "missing"
            elif len(content) <= minimum_text:
                status = "empty"
            results.append(
                TabResult(
                    label=label,
                    status=status,
                    text_length=len(content),
                    preview=content[:100].replace("\n", " "),
                )
            )

        if page_errors:
            for error in page_errors:
                results.append(
                    TabResult(
                        label="<page-error>",
                        status="error",
                        text_length=0,
                        preview=error,
                    )
                )

        context.close()
        browser.close()

    return results


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-url", default="http://127.0.0.1:5000")
    parser.add_argument("--vue-url", default="http://127.0.0.1:5173")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--minimum-text", type=int, default=8)
    args = parser.parse_args()

    session_id = args.session_id or create_guest_session(args.backend_url)
    results = audit_tabs(args.vue_url, session_id, args.minimum_text)

    for result in results:
        print(
            f"{result.label}\t{result.status}\t"
            f"{result.text_length}\t{result.preview}"
        )

    failed = [result for result in results if result.status != "ok"]
    if failed:
        print(f"\n{len(failed)} admin tabs failed", file=sys.stderr)
        return 1

    print(f"\nAll {len(results)} admin tabs rendered successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
