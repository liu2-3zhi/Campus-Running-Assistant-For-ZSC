#!/usr/bin/env python3
"""Capture matching legacy and Vue UI screenshots for visual comparison."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


MOBILE_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Mobile Safari/537.36"
)


def build_context(browser, width: int, height: int, mobile: bool):
    options = {
        "viewport": {"width": width, "height": height},
        "device_scale_factor": 1,
    }
    if mobile:
        options.update(
            {
                "screen": {"width": width, "height": height},
                "is_mobile": True,
                "has_touch": True,
                "user_agent": MOBILE_USER_AGENT,
            }
        )
    return browser.new_context(**options)


def capture_pair(
    browser,
    legacy_url: str,
    vue_url: str,
    output_dir: Path,
    label: str,
    width: int,
    height: int,
    mobile: bool,
) -> None:
    context = build_context(browser, width, height, mobile)
    try:
        for name, url in (("legacy", legacy_url), ("vue", vue_url)):
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(4_000)
            page.screenshot(
                path=str(output_dir / f"{name}-{label}.png"),
                full_page=True,
            )
            page.close()
    finally:
        context.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--legacy-url",
        default=os.getenv("LEGACY_URL", "http://127.0.0.1:5000/"),
    )
    parser.add_argument(
        "--vue-url",
        default=os.getenv("VUE_URL", "http://127.0.0.1:5173/"),
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("OUTPUT_DIR", "output/ui-parity"),
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            capture_pair(
                browser,
                args.legacy_url,
                args.vue_url,
                output_dir,
                "desktop",
                1440,
                900,
                False,
            )
            capture_pair(
                browser,
                args.legacy_url,
                args.vue_url,
                output_dir,
                "mobile",
                390,
                844,
                True,
            )
        finally:
            browser.close()

    print(f"UI screenshots written to {output_dir.resolve()}")


if __name__ == "__main__":
    main()
