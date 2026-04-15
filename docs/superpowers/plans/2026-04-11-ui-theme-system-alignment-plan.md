# UI Theme System Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the runtime UI/theme system with `ui/`, rebuild the six runtime theme definitions, and extend default random background reuse from the login surface to the authenticated app/admin surfaces without changing the existing `session + target` binding model.

**Architecture:** Keep `ui/` as the source of truth for theme identity and visual direction, but continue to render the live product from `index.html`, `styles/style.css`, `scripts/main.new.js`, and `main.py`. `theme/*.json` becomes the runtime metadata + token layer, `main.py` merges and injects the correct env vars, and the frontend applies those env vars to desktop/mobile auth/app/admin shells while preserving the current background-consumption flow.

**Tech Stack:** Python 3 + Flask (`main.py`), vanilla JavaScript (`scripts/main.new.js`), HTML (`index.html`), CSS (`styles/style.css`), Python `unittest`.

---

**Execution context:** Per user instruction, execute directly in the project root (no worktree) and isolate each completed task with a normal git commit.

## Scope check

This stays as one implementation plan because the catalog sync, runtime theme metadata, backend config injection, frontend theme application, and page-shell markup are tightly coupled. Splitting them into separate plans would create churn around the same four files (`main.py`, `scripts/main.new.js`, `index.html`, `styles/style.css`) and make it harder to preserve the background-binding behavior end to end.

## File structure（实施前锁定）

- Modify: `theme/default.json`
  - Rewrite metadata and default theme runtime tokens so `default` becomes the `Anime Core` runtime theme.
- Create: `theme/neo-minimal.json`
  - Runtime metadata + env vars for Neo Minimal.
- Create: `theme/cyber-grid.json`
  - Runtime metadata + env vars for Cyber Grid.
- Create: `theme/eastern-calm.json`
  - Runtime metadata + env vars for Eastern Calm.
- Create: `theme/editorial-magazine.json`
  - Runtime metadata + env vars for Editorial Magazine.
- Create: `theme/luxe-noir.json`
  - Runtime metadata + env vars for Luxe Noir.
- Delete: `theme/anime.json`, `theme/minimalist.json`, `theme/corporate.json`, `theme/creative.json`, `theme/futuristic.json`, `theme/retro.json`
  - Remove runtime themes that are not backed by `ui/`.
- Modify: `main.py:6587-6707,14097-14180`
  - Keep the existing loader shape, fan out default random backgrounds to auth/app/admin env vars, and continue exposing theme metadata to the frontend.
- Modify: `scripts/main.new.js:16754-17121,17237-17357`
  - Apply runtime env vars to desktop/mobile auth/app/admin surfaces and stamp the active runtime theme ID onto `document.body`.
- Modify: `index.html:1569-1814,2187-2625,3591-4270,6269,11995`
  - Add stable theme surface hooks around the existing desktop/mobile auth/app/admin sections without breaking JS IDs.
- Modify: `styles/style.css:10-24,162-168,491-627,793-1036,1166-1307,1869-1944`
  - Add reusable shell styling plus six runtime theme variants for desktop and mobile.
- Create: `tests/test_runtime_theme_catalog.py`
  - Validate that runtime themes now match `ui/` and that all metadata fields are rewritten.
- Modify: `tests/test_theme_background_binding.py`
  - Validate that default background injection fans out to auth/app/admin while preserving the `pc/mobile` binding contract.
- Create: `tests/test_theme_shell_contract.py`
  - Static contract tests for the new HTML hooks, CSS selectors, and JS runtime theme/application tokens.
- Reuse: `tests/test_ui_theme_previews.py`
  - Keep the existing preview contract as the guardrail for the `ui/` source-of-truth set.

## Task ordering

1. Lock the runtime theme catalog to the `ui/`-backed six-theme set.
2. Extend backend default-theme background injection without changing session-binding semantics.
3. Extend the frontend runtime theme application chain to auth/app/admin surfaces.
4. Add desktop shell hooks and desktop theme structure/styling.
5. Add mobile shell hooks and mobile theme structure/styling.
6. Run the full verification set and do a final integration pass.

---

### Task 1: Rebuild the runtime theme catalog from `ui/`

**Files:**
- Create: `tests/test_runtime_theme_catalog.py`
- Modify: `theme/default.json`
- Create: `theme/neo-minimal.json`
- Create: `theme/cyber-grid.json`
- Create: `theme/eastern-calm.json`
- Create: `theme/editorial-magazine.json`
- Create: `theme/luxe-noir.json`
- Delete: `theme/anime.json`
- Delete: `theme/minimalist.json`
- Delete: `theme/corporate.json`
- Delete: `theme/creative.json`
- Delete: `theme/futuristic.json`
- Delete: `theme/retro.json`
- Test: `tests/test_runtime_theme_catalog.py`

- [ ] **Step 1: Write the failing runtime catalog test**

```python
import json
import unittest
from pathlib import Path

from main import auth_system

ROOT = Path(__file__).resolve().parents[1]
THEME_DIR = ROOT / "theme"

EXPECTED_THEME_FILES = {
    "default.json",
    "neo-minimal.json",
    "cyber-grid.json",
    "eastern-calm.json",
    "editorial-magazine.json",
    "luxe-noir.json",
}
EXPECTED_THEME_IDS = {
    "default",
    "theme-neo-minimal",
    "theme-cyber-grid",
    "theme-eastern-calm",
    "theme-editorial-magazine",
    "theme-luxe-noir",
}
EXPECTED_LABELS = {
    "default": "Anime Core",
    "theme-neo-minimal": "Neo Minimal",
    "theme-cyber-grid": "Cyber Grid",
    "theme-eastern-calm": "Eastern Calm",
    "theme-editorial-magazine": "Editorial Magazine",
    "theme-luxe-noir": "Luxe Noir",
}
RETIRED_THEME_IDS = {
    "theme-anime",
    "theme-minimalist",
    "theme-corporate",
    "theme-creative",
    "theme-futuristic",
    "theme-retro",
}


class TestRuntimeThemeCatalog(unittest.TestCase):
    def test_theme_directory_matches_ui_backed_set(self):
        theme_files = {path.name for path in THEME_DIR.glob("*.json")}
        self.assertEqual(theme_files, EXPECTED_THEME_FILES)

    def test_available_theme_styles_only_exposes_ui_backed_themes(self):
        styles = auth_system.get_available_theme_styles()
        ids = {style["id"] for style in styles}
        self.assertEqual(ids, EXPECTED_THEME_IDS)
        self.assertTrue(RETIRED_THEME_IDS.isdisjoint(ids))

        labels = {style["id"]: style["label"] for style in styles}
        self.assertEqual(labels, EXPECTED_LABELS)

        for style in styles:
            self.assertTrue(style["description"].strip())
            self.assertIn("<svg", style["svg"])
            self.assertIn("global_environment_variables", style)

    def test_theme_files_rewrite_basic_information(self):
        for file_name in EXPECTED_THEME_FILES:
            data = json.loads((THEME_DIR / file_name).read_text(encoding="utf-8"))
            basic = data["basic_information"]
            self.assertTrue(basic["id"].strip())
            self.assertTrue(basic["label"].strip())
            self.assertTrue(basic["description"].strip())
            self.assertIn("<svg", basic["svg"])
            self.assertIn("global_environment_variables", data)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the catalog test to verify it fails**

Run: `python -m unittest tests.test_runtime_theme_catalog -v`
Expected: FAIL because `theme/` still contains retired files (`anime.json`, `retro.json`, etc.) and `theme/default.json` still reports the old “默认主题” metadata.

- [ ] **Step 3: Rewrite `theme/default.json` as Anime Core**

Replace `theme/default.json` with:

```json
{
  "basic_information": {
    "id": "default",
    "label": "Anime Core",
    "description": "樱雾、月光和徽章卡片构成的二次元产品基线主题。",
    "svg": "<svg width=\"320\" height=\"200\" viewBox=\"0 0 320 200\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"><rect width=\"320\" height=\"200\" rx=\"24\" fill=\"#FFF7FB\"/><rect x=\"20\" y=\"20\" width=\"280\" height=\"160\" rx=\"24\" fill=\"#FFFFFF\" stroke=\"#F5C8E3\"/><circle cx=\"84\" cy=\"78\" r=\"28\" fill=\"#FFB4D9\" fill-opacity=\"0.9\"/><circle cx=\"112\" cy=\"106\" r=\"18\" fill=\"#C6B8FF\" fill-opacity=\"0.85\"/><rect x=\"156\" y=\"52\" width=\"102\" height=\"14\" rx=\"7\" fill=\"#FF7FBD\" fill-opacity=\"0.9\"/><rect x=\"156\" y=\"82\" width=\"118\" height=\"10\" rx=\"5\" fill=\"#D9CCFF\"/><rect x=\"156\" y=\"106\" width=\"92\" height=\"10\" rx=\"5\" fill=\"#EEDCFF\"/><rect x=\"52\" y=\"126\" width=\"216\" height=\"30\" rx=\"15\" fill=\"#FFF0F7\" stroke=\"#F5C8E3\"/></svg>"
  },
  "global_environment_variables": {
    "auth_login_container_background": "radial-gradient(circle at top left, rgba(255, 180, 217, 0.34), transparent 28%), radial-gradient(circle at bottom right, rgba(179, 177, 255, 0.26), transparent 24%), linear-gradient(180deg, #fff8fc 0%, #fff0f7 52%, #eef3ff 100%)",
    "auth_login_panel_background": "rgba(255,255,255,0.88)",
    "auth_login_panel_shadow": "0 24px 64px rgba(191, 99, 160, 0.18)",
    "auth_login_panel_border": "rgba(245,200,227,0.92)",
    "mobile_auth_login_content_background": "linear-gradient(180deg, rgba(255,248,252,0.98), rgba(255,240,247,0.96) 52%, rgba(238,243,255,0.98))",
    "mobile_auth_login_card_background": "rgba(255,255,255,0.9)",
    "mobile_auth_login_card_shadow": "0 18px 48px rgba(191, 99, 160, 0.18)",
    "app_shell_background": "linear-gradient(180deg, rgba(255,248,252,0.98), rgba(252,243,255,0.96) 52%, rgba(238,243,255,0.98))",
    "mobile_app_shell_background": "linear-gradient(180deg, rgba(255,248,252,0.98), rgba(252,243,255,0.96) 52%, rgba(238,243,255,0.98))",
    "app_panel_background": "rgba(255,255,255,0.84)",
    "admin_shell_background": "linear-gradient(180deg, rgba(255,248,252,0.98), rgba(255,240,247,0.96) 52%, rgba(238,243,255,0.98))",
    "mobile_admin_shell_background": "linear-gradient(180deg, rgba(255,248,252,0.98), rgba(255,240,247,0.96) 52%, rgba(238,243,255,0.98))",
    "admin_panel_background": "rgba(255,255,255,0.88)",
    "admin_panel_border": "rgba(245,200,227,0.88)",
    "admin_panel_shadow": "0 24px 64px rgba(191, 99, 160, 0.18)"
  }
}
```

- [ ] **Step 4: Create the five non-default runtime theme files and remove retired runtime themes**

Create `theme/neo-minimal.json`:

```json
{
  "basic_information": {
    "id": "theme-neo-minimal",
    "label": "Neo Minimal",
    "description": "留白、秩序与低噪声面板构成的新极简工具界面。",
    "svg": "<svg width=\"320\" height=\"200\" viewBox=\"0 0 320 200\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"><rect width=\"320\" height=\"200\" rx=\"24\" fill=\"#F6F8FB\"/><rect x=\"28\" y=\"22\" width=\"264\" height=\"156\" rx=\"24\" fill=\"#FFFFFF\" stroke=\"#D8DFEA\"/><rect x=\"52\" y=\"46\" width=\"84\" height=\"10\" rx=\"5\" fill=\"#1F2937\"/><rect x=\"52\" y=\"72\" width=\"144\" height=\"8\" rx=\"4\" fill=\"#B6C0CF\"/><rect x=\"52\" y=\"102\" width=\"216\" height=\"18\" rx=\"9\" fill=\"#F3F6FA\" stroke=\"#D8DFEA\"/><rect x=\"52\" y=\"132\" width=\"96\" height=\"18\" rx=\"9\" fill=\"#DCE6F7\"/></svg>"
  },
  "global_environment_variables": {
    "auth_login_container_background": "linear-gradient(180deg, #f7f9fc 0%, #f0f4f8 48%, #eef2f7 100%)",
    "auth_login_panel_background": "rgba(255,255,255,0.9)",
    "auth_login_panel_shadow": "0 20px 48px rgba(15,23,42,0.08)",
    "auth_login_panel_border": "rgba(210,218,229,0.88)",
    "mobile_auth_login_content_background": "linear-gradient(180deg, #f7f9fc 0%, #f1f5f9 100%)",
    "mobile_auth_login_card_background": "rgba(255,255,255,0.92)",
    "mobile_auth_login_card_shadow": "0 14px 36px rgba(15,23,42,0.08)",
    "app_shell_background": "linear-gradient(180deg, #fbfcfe 0%, #f5f7fa 100%)",
    "mobile_app_shell_background": "linear-gradient(180deg, #fbfcfe 0%, #f5f7fa 100%)",
    "app_panel_background": "rgba(255,255,255,0.92)",
    "admin_shell_background": "linear-gradient(180deg, #fbfcfe 0%, #f4f7fb 100%)",
    "mobile_admin_shell_background": "linear-gradient(180deg, #fbfcfe 0%, #f4f7fb 100%)",
    "admin_panel_background": "rgba(255,255,255,0.94)",
    "admin_panel_border": "rgba(210,218,229,0.92)",
    "admin_panel_shadow": "0 18px 42px rgba(15,23,42,0.08)"
  }
}
```

Create `theme/cyber-grid.json`:

```json
{
  "basic_information": {
    "id": "theme-cyber-grid",
    "label": "Cyber Grid",
    "description": "荧光栅格、扫描线与终端面板构成的赛博控制主题。",
    "svg": "<svg width=\"320\" height=\"200\" viewBox=\"0 0 320 200\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"><rect width=\"320\" height=\"200\" rx=\"24\" fill=\"#0B1020\"/><rect x=\"20\" y=\"20\" width=\"280\" height=\"160\" rx=\"24\" fill=\"#11182B\" stroke=\"#2CE6FF\" stroke-opacity=\"0.7\"/><path d=\"M36 52H284\" stroke=\"#2CE6FF\" stroke-opacity=\"0.3\"/><path d=\"M36 82H284\" stroke=\"#2CE6FF\" stroke-opacity=\"0.2\"/><path d=\"M36 112H284\" stroke=\"#2CE6FF\" stroke-opacity=\"0.2\"/><rect x=\"48\" y=\"44\" width=\"98\" height=\"12\" rx=\"6\" fill=\"#2CE6FF\" fill-opacity=\"0.85\"/><rect x=\"182\" y=\"44\" width=\"74\" height=\"12\" rx=\"6\" fill=\"#FF4FD8\" fill-opacity=\"0.85\"/><rect x=\"48\" y=\"132\" width=\"224\" height=\"20\" rx=\"10\" fill=\"#18233E\" stroke=\"#2CE6FF\" stroke-opacity=\"0.55\"/></svg>"
  },
  "global_environment_variables": {
    "auth_login_container_background": "linear-gradient(180deg, rgba(8,12,24,0.98) 0%, rgba(14,24,42,0.98) 100%), repeating-linear-gradient(90deg, rgba(44,230,255,0.08) 0, rgba(44,230,255,0.08) 1px, transparent 1px, transparent 32px)",
    "auth_login_panel_background": "rgba(12,20,36,0.84)",
    "auth_login_panel_shadow": "0 24px 72px rgba(0,0,0,0.45)",
    "auth_login_panel_border": "rgba(44,230,255,0.45)",
    "mobile_auth_login_content_background": "linear-gradient(180deg, rgba(8,12,24,0.98) 0%, rgba(14,24,42,0.98) 100%)",
    "mobile_auth_login_card_background": "rgba(12,20,36,0.9)",
    "mobile_auth_login_card_shadow": "0 20px 56px rgba(0,0,0,0.45)",
    "app_shell_background": "linear-gradient(180deg, rgba(8,12,24,0.98) 0%, rgba(12,20,36,0.98) 100%)",
    "mobile_app_shell_background": "linear-gradient(180deg, rgba(8,12,24,0.98) 0%, rgba(12,20,36,0.98) 100%)",
    "app_panel_background": "rgba(12,20,36,0.84)",
    "admin_shell_background": "linear-gradient(180deg, rgba(8,12,24,0.98) 0%, rgba(12,20,36,0.98) 100%)",
    "mobile_admin_shell_background": "linear-gradient(180deg, rgba(8,12,24,0.98) 0%, rgba(12,20,36,0.98) 100%)",
    "admin_panel_background": "rgba(12,20,36,0.88)",
    "admin_panel_border": "rgba(44,230,255,0.45)",
    "admin_panel_shadow": "0 24px 72px rgba(0,0,0,0.5)"
  }
}
```

Create `theme/eastern-calm.json`:

```json
{
  "basic_information": {
    "id": "theme-eastern-calm",
    "label": "Eastern Calm",
    "description": "东方留白、纸感和静谧层次构成的沉静主题。",
    "svg": "<svg width=\"320\" height=\"200\" viewBox=\"0 0 320 200\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"><rect width=\"320\" height=\"200\" rx=\"24\" fill=\"#F7F4ED\"/><rect x=\"24\" y=\"24\" width=\"272\" height=\"152\" rx=\"24\" fill=\"#FFFDF8\" stroke=\"#DDD2C1\"/><path d=\"M72 46V154\" stroke=\"#C49B6C\" stroke-opacity=\"0.65\"/><rect x=\"96\" y=\"46\" width=\"76\" height=\"12\" rx=\"6\" fill=\"#5C5045\" fill-opacity=\"0.86\"/><rect x=\"96\" y=\"74\" width=\"112\" height=\"8\" rx=\"4\" fill=\"#B7AA9A\"/><rect x=\"96\" y=\"116\" width=\"160\" height=\"18\" rx=\"9\" fill=\"#F6F1E7\" stroke=\"#DDD2C1\"/><circle cx=\"248\" cy=\"66\" r=\"14\" fill=\"#B65A3A\" fill-opacity=\"0.78\"/></svg>"
  },
  "global_environment_variables": {
    "auth_login_container_background": "linear-gradient(180deg, #f7f4ed 0%, #f3eee3 52%, #ede7db 100%)",
    "auth_login_panel_background": "rgba(255,253,248,0.92)",
    "auth_login_panel_shadow": "0 22px 56px rgba(92,80,69,0.12)",
    "auth_login_panel_border": "rgba(221,210,193,0.92)",
    "mobile_auth_login_content_background": "linear-gradient(180deg, #f7f4ed 0%, #efe8da 100%)",
    "mobile_auth_login_card_background": "rgba(255,253,248,0.94)",
    "mobile_auth_login_card_shadow": "0 16px 40px rgba(92,80,69,0.12)",
    "app_shell_background": "linear-gradient(180deg, #fbf8f1 0%, #f2ecdf 100%)",
    "mobile_app_shell_background": "linear-gradient(180deg, #fbf8f1 0%, #f2ecdf 100%)",
    "app_panel_background": "rgba(255,253,248,0.9)",
    "admin_shell_background": "linear-gradient(180deg, #faf6ee 0%, #efe8da 100%)",
    "mobile_admin_shell_background": "linear-gradient(180deg, #faf6ee 0%, #efe8da 100%)",
    "admin_panel_background": "rgba(255,253,248,0.92)",
    "admin_panel_border": "rgba(221,210,193,0.92)",
    "admin_panel_shadow": "0 20px 48px rgba(92,80,69,0.12)"
  }
}
```

Create `theme/editorial-magazine.json`:

```json
{
  "basic_information": {
    "id": "theme-editorial-magazine",
    "label": "Editorial Magazine",
    "description": "栏目化、强标题和分栏信息密度构成的杂志编排主题。",
    "svg": "<svg width=\"320\" height=\"200\" viewBox=\"0 0 320 200\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"><rect width=\"320\" height=\"200\" rx=\"24\" fill=\"#FAF7F2\"/><rect x=\"18\" y=\"18\" width=\"284\" height=\"164\" rx=\"20\" fill=\"#FFFDF8\" stroke=\"#DCCBB4\"/><rect x=\"40\" y=\"38\" width=\"86\" height=\"88\" rx=\"14\" fill=\"#D8C1A6\" fill-opacity=\"0.72\"/><rect x=\"144\" y=\"42\" width=\"112\" height=\"16\" rx=\"8\" fill=\"#202020\"/><rect x=\"144\" y=\"70\" width=\"112\" height=\"8\" rx=\"4\" fill=\"#86807A\"/><rect x=\"144\" y=\"88\" width=\"104\" height=\"8\" rx=\"4\" fill=\"#B8B1AA\"/><rect x=\"40\" y=\"142\" width=\"216\" height=\"16\" rx=\"8\" fill=\"#EFE7DA\" stroke=\"#DCCBB4\"/></svg>"
  },
  "global_environment_variables": {
    "auth_login_container_background": "linear-gradient(180deg, #faf7f2 0%, #f3ece1 52%, #eee5d8 100%)",
    "auth_login_panel_background": "rgba(255,253,248,0.9)",
    "auth_login_panel_shadow": "0 22px 60px rgba(52,42,33,0.14)",
    "auth_login_panel_border": "rgba(220,203,180,0.92)",
    "mobile_auth_login_content_background": "linear-gradient(180deg, #faf7f2 0%, #f0e6d8 100%)",
    "mobile_auth_login_card_background": "rgba(255,253,248,0.92)",
    "mobile_auth_login_card_shadow": "0 16px 42px rgba(52,42,33,0.14)",
    "app_shell_background": "linear-gradient(180deg, #fdfaf4 0%, #f4ede1 100%)",
    "mobile_app_shell_background": "linear-gradient(180deg, #fdfaf4 0%, #f4ede1 100%)",
    "app_panel_background": "rgba(255,253,248,0.9)",
    "admin_shell_background": "linear-gradient(180deg, #fdfaf4 0%, #efe5d7 100%)",
    "mobile_admin_shell_background": "linear-gradient(180deg, #fdfaf4 0%, #efe5d7 100%)",
    "admin_panel_background": "rgba(255,253,248,0.92)",
    "admin_panel_border": "rgba(220,203,180,0.92)",
    "admin_panel_shadow": "0 20px 52px rgba(52,42,33,0.14)"
  }
}
```

Create `theme/luxe-noir.json`:

```json
{
  "basic_information": {
    "id": "theme-luxe-noir",
    "label": "Luxe Noir",
    "description": "夜色、金属边界和高对比材质构成的暗奢主题。",
    "svg": "<svg width=\"320\" height=\"200\" viewBox=\"0 0 320 200\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"><rect width=\"320\" height=\"200\" rx=\"24\" fill=\"#0F1014\"/><rect x=\"20\" y=\"20\" width=\"280\" height=\"160\" rx=\"24\" fill=\"#181A21\" stroke=\"#CFA95B\" stroke-opacity=\"0.65\"/><rect x=\"42\" y=\"42\" width=\"110\" height=\"12\" rx=\"6\" fill=\"#F2E1B3\" fill-opacity=\"0.85\"/><rect x=\"42\" y=\"72\" width=\"146\" height=\"8\" rx=\"4\" fill=\"#7F7461\"/><rect x=\"42\" y=\"130\" width=\"236\" height=\"20\" rx=\"10\" fill=\"#101319\" stroke=\"#CFA95B\" stroke-opacity=\"0.45\"/><circle cx=\"246\" cy=\"68\" r=\"18\" fill=\"#CFA95B\" fill-opacity=\"0.22\"/></svg>"
  },
  "global_environment_variables": {
    "auth_login_container_background": "linear-gradient(180deg, #0f1014 0%, #14161c 48%, #1a1d24 100%)",
    "auth_login_panel_background": "rgba(18,20,26,0.86)",
    "auth_login_panel_shadow": "0 26px 78px rgba(0,0,0,0.5)",
    "auth_login_panel_border": "rgba(207,169,91,0.34)",
    "mobile_auth_login_content_background": "linear-gradient(180deg, #0f1014 0%, #161820 100%)",
    "mobile_auth_login_card_background": "rgba(18,20,26,0.9)",
    "mobile_auth_login_card_shadow": "0 18px 52px rgba(0,0,0,0.5)",
    "app_shell_background": "linear-gradient(180deg, #0f1014 0%, #161920 100%)",
    "mobile_app_shell_background": "linear-gradient(180deg, #0f1014 0%, #161920 100%)",
    "app_panel_background": "rgba(18,20,26,0.88)",
    "admin_shell_background": "linear-gradient(180deg, #101216 0%, #171a21 100%)",
    "mobile_admin_shell_background": "linear-gradient(180deg, #101216 0%, #171a21 100%)",
    "admin_panel_background": "rgba(18,20,26,0.9)",
    "admin_panel_border": "rgba(207,169,91,0.34)",
    "admin_panel_shadow": "0 24px 72px rgba(0,0,0,0.52)"
  }
}
```

Then run:

```bash
git rm theme/anime.json theme/minimalist.json theme/corporate.json theme/creative.json theme/futuristic.json theme/retro.json
```

- [ ] **Step 5: Run the runtime catalog test to verify it passes**

Run: `python -m unittest tests.test_runtime_theme_catalog -v`
Expected: PASS with 3 passing tests and no retired runtime theme IDs.

- [ ] **Step 6: Commit the catalog rewrite**

Run:

```bash
git add tests/test_runtime_theme_catalog.py theme/default.json theme/neo-minimal.json theme/cyber-grid.json theme/eastern-calm.json theme/editorial-magazine.json theme/luxe-noir.json
git commit -m "$(cat <<'EOF'
refactor: rebuild runtime theme catalog from ui previews
EOF
)"
```

---

### Task 2: Fan out default random backgrounds to auth/app/admin in `main.py`

**Files:**
- Modify: `tests/test_theme_background_binding.py`
- Modify: `main.py:6587-6660`
- Test: `tests/test_theme_background_binding.py`

- [ ] **Step 1: Add a failing test for default background fan-out**

Append this test to `tests/test_theme_background_binding.py`:

```python
from unittest.mock import patch

from main import auth_system


class TestThemeBackgroundBinding(unittest.TestCase):
    @patch.object(
        auth_system,
        "_resolve_default_theme_background_images",
        return_value={
            "pc": "/theme-assets/random_background_image/pc_bound.jpg",
            "mobile": "/theme-assets/random_background_image/mb_bound.jpg",
        },
    )
    def test_default_theme_background_fans_out_to_auth_app_and_admin(self, _mock_backgrounds):
        config = auth_system.get_theme_config("default", ["pc", "mobile"])
        env = config["global_environment_variables"]

        self.assertIn("pc_bound.jpg", env["auth_login_container_background"])
        self.assertEqual(env["app_shell_background"], env["admin_shell_background"])
        self.assertIn("pc_bound.jpg", env["app_shell_background"])
        self.assertIn("mb_bound.jpg", env["mobile_auth_login_content_background"])
        self.assertEqual(
            env["mobile_app_shell_background"],
            env["mobile_admin_shell_background"],
        )
        self.assertIn("mb_bound.jpg", env["mobile_app_shell_background"])
```

- [ ] **Step 2: Run the binding test to verify it fails**

Run: `python -m unittest tests.test_theme_background_binding.TestThemeBackgroundBinding.test_default_theme_background_fans_out_to_auth_app_and_admin -v`
Expected: FAIL with `KeyError` or missing `app_shell_background` / `mobile_app_shell_background` keys because `main.py` currently only injects the login surfaces.

- [ ] **Step 3: Extend `_inject_default_theme_background_image` to write auth/app/admin backgrounds from the same bound URLs**

Update `main.py` around `AuthSystem._inject_default_theme_background_image` to this shape:

```python
def _inject_default_theme_background_image(self, merged_config, style_id, targets=None):
    normalized_style = str(style_id or "default").strip() or "default"
    if normalized_style != "default":
        return merged_config

    config = dict(merged_config) if isinstance(merged_config, dict) else {}
    env = config.get("global_environment_variables")
    if not isinstance(env, dict):
        env = {}
        config["global_environment_variables"] = env

    background_image_urls = self._resolve_default_theme_background_images(targets)
    pc_background_image_url = background_image_urls.get("pc", "")
    mobile_background_image_url = background_image_urls.get("mobile", "")
    if not pc_background_image_url and not mobile_background_image_url:
        return config

    if pc_background_image_url:
        desktop_background_value = (
            "linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.10)), "
            f'url("{pc_background_image_url}") center / cover no-repeat fixed'
        )
        env["auth_login_container_background"] = desktop_background_value
        env["app_shell_background"] = desktop_background_value
        env["admin_shell_background"] = desktop_background_value

    if mobile_background_image_url:
        mobile_background_value = (
            "linear-gradient(rgba(255,255,255,0.12), rgba(255,255,255,0.12)), "
            f'url("{mobile_background_image_url}") center / cover no-repeat'
        )
        env["mobile_auth_login_content_background"] = mobile_background_value
        env["mobile_app_shell_background"] = mobile_background_value
        env["mobile_admin_shell_background"] = mobile_background_value
    else:
        env.setdefault("mobile_auth_login_content_background", "")
        env.setdefault("mobile_app_shell_background", "")
        env.setdefault("mobile_admin_shell_background", "")

    env.setdefault("mobile_auth_login_card_background", "rgba(255,255,255,0.58)")
    env.setdefault("auth_login_panel_background", "rgba(255,255,255,0.52)")
    env.setdefault("auth_login_panel_shadow", "0 20px 60px rgba(15,23,42,0.12)")
    env.setdefault("auth_login_panel_border", "rgba(255,255,255,0.24)")
    env.setdefault("mobile_auth_login_card_shadow", "0 18px 48px rgba(15,23,42,0.12)")
    env.setdefault("app_panel_background", env.get("auth_login_panel_background", "rgba(255,255,255,0.52)"))
    env.setdefault("admin_panel_background", env.get("auth_login_panel_background", "rgba(255,255,255,0.52)"))
    env.setdefault("admin_panel_border", env.get("auth_login_panel_border", "rgba(255,255,255,0.24)"))
    env.setdefault("admin_panel_shadow", env.get("auth_login_panel_shadow", "0 20px 60px rgba(15,23,42,0.12)"))
    return config
```

- [ ] **Step 4: Re-run the binding test and the existing binding suite**

Run: `python -m unittest tests.test_theme_background_binding -v`
Expected: PASS, including the new fan-out test and the existing `session + target` binding tests.

- [ ] **Step 5: Commit the backend background fan-out change**

Run:

```bash
git add main.py tests/test_theme_background_binding.py
git commit -m "$(cat <<'EOF'
feat: fan out default theme backgrounds to app and admin shells
EOF
)"
```

---

### Task 3: Extend the frontend runtime theme application chain

**Files:**
- Create: `tests/test_theme_shell_contract.py`
- Modify: `scripts/main.new.js:16754-17121,17237-17357`
- Test: `tests/test_theme_shell_contract.py`

- [ ] **Step 1: Write the failing JS contract test**

Create `tests/test_theme_shell_contract.py` with:

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "scripts" / "main.new.js").read_text(encoding="utf-8")


class TestThemeShellContract(unittest.TestCase):
    def test_runtime_script_knows_new_shell_background_keys(self):
        for token in [
            "app_shell_background",
            "mobile_app_shell_background",
            "admin_shell_background",
            "mobile_admin_shell_background",
            'document.body.dataset.themeStyleRuntime',
            'document.getElementById("main-app")',
            'document.getElementById("admin-panel-modal-Inline")',
            'document.getElementById("mobile-login-container")',
            'document.getElementById("mobile-session-panel-card")',
            'document.getElementById("mobile-admin-panel-content")',
            'document.getElementById("mobile-multi-admin-content-panel")',
        ]:
            self.assertIn(token, SCRIPT)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the JS contract test to verify it fails**

Run: `python -m unittest tests.test_theme_shell_contract.TestThemeShellContract.test_runtime_script_knows_new_shell_background_keys -v`
Expected: FAIL because `scripts/main.new.js` currently only applies login-surface env vars and does not stamp the active runtime theme ID onto `document.body`.

- [ ] **Step 3: Expand `applyThemeGlobalEnvironmentVariables` and `applyThemeLoginContainerStyle`**

Update `scripts/main.new.js` with these concrete changes:

```javascript
function applySurfaceBackground(element, backgroundValue) {
  if (!element) return;
  element.style.background = backgroundValue || "";
  element.style.backgroundSize = backgroundValue ? "cover" : "";
  element.style.backgroundPosition = backgroundValue ? "center" : "";
  element.style.backgroundRepeat = backgroundValue ? "no-repeat" : "";
}

function applyPanelSurface(element, background, shadow, borderColor) {
  if (!element) return;
  if (background) element.style.background = background;
  if (shadow) element.style.boxShadow = shadow;
  if (borderColor) element.style.borderColor = borderColor;
}

function applyThemeGlobalEnvironmentVariables(themeConfig) {
  const config = themeConfig && typeof themeConfig === "object" ? themeConfig : {};
  const env =
    config.global_environment_variables &&
    typeof config.global_environment_variables === "object"
      ? config.global_environment_variables
      : {};

  currentThemeConfig = config;
  window.themeConfig = config;
  window.themeGlobalEnvironmentVariables = env;

  const runtimeThemeId =
    config.basic_information && config.basic_information.id
      ? config.basic_information.id
      : normalizeThemeStyle(getCachedThemeStyle());
  document.body.dataset.themeStyleRuntime = runtimeThemeId;

  Object.keys(window).forEach((key) => {
    if (key.startsWith("themeEnv_")) {
      try {
        delete window[key];
      } catch (_) {}
    }
  });

  Object.entries(env).forEach(([key, value]) => {
    if (!/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key)) return;
    window[`themeEnv_${key}`] = value;
  });

  applyThemeLoginContainerStyle(config);
  scheduleThemeBackgroundConsumed();
}

function applyThemeLoginContainerStyle(themeConfig) {
  const config = themeConfig && typeof themeConfig === "object" ? themeConfig : {};
  const env =
    config.global_environment_variables &&
    typeof config.global_environment_variables === "object"
      ? config.global_environment_variables
      : {};

  const desktopAuthContainer = document.getElementById("auth-login-container");
  const desktopAuthPanel = document.getElementById("auth-login-container_panel");
  const desktopAppShell = document.getElementById("main-app");
  const desktopAdminShell = document.getElementById("admin-panel-modal-Inline");
  const desktopSingleLoginPanel = document.getElementById("desktop-container-single-login-panel-wrapper");

  const mobileContent = document.getElementById("mobile-content");
  const mobileAuthCard = document.getElementById("mobile-auth-login-container-card");
  const mobileAppShell = document.getElementById("mobile-login-container");
  const mobileSessionPanel = document.getElementById("mobile-session-panel-card");
  const mobileAdminShell = document.getElementById("mobile-admin-panel-content");
  const mobileMultiAdminShell = document.getElementById("mobile-multi-admin-content-panel");

  const desktopBackground = env.auth_login_container_background || "";
  const mobileBackground = env.mobile_auth_login_content_background || "";
  const appShellBackground = env.app_shell_background || desktopBackground;
  const mobileAppShellBackground = env.mobile_app_shell_background || mobileBackground;
  const adminShellBackground = env.admin_shell_background || appShellBackground;
  const mobileAdminShellBackground = env.mobile_admin_shell_background || mobileAppShellBackground;

  const authPanelBackground = env.auth_login_panel_background || "";
  const authPanelShadow = env.auth_login_panel_shadow || "";
  const authPanelBorder = env.auth_login_panel_border || "";
  const mobileAuthCardBackground = env.mobile_auth_login_card_background || "";
  const mobileAuthCardShadow = env.mobile_auth_login_card_shadow || "";
  const appPanelBackground = env.app_panel_background || authPanelBackground;
  const adminPanelBackground = env.admin_panel_background || authPanelBackground;
  const adminPanelBorder = env.admin_panel_border || authPanelBorder;
  const adminPanelShadow = env.admin_panel_shadow || authPanelShadow;

  applySurfaceBackground(desktopAuthContainer, desktopBackground);
  applyPanelSurface(desktopAuthPanel, authPanelBackground, authPanelShadow, authPanelBorder);
  applySurfaceBackground(desktopAppShell, appShellBackground);
  applyPanelSurface(desktopSingleLoginPanel, appPanelBackground, authPanelShadow, authPanelBorder);
  applySurfaceBackground(desktopAdminShell, adminShellBackground);
  applyPanelSurface(desktopAdminShell?.querySelector(".panel"), adminPanelBackground, adminPanelShadow, adminPanelBorder);

  applySurfaceBackground(mobileContent, mobileBackground);
  applyPanelSurface(mobileAuthCard, mobileAuthCardBackground, mobileAuthCardShadow, authPanelBorder);
  applySurfaceBackground(mobileAppShell, mobileAppShellBackground);
  applyPanelSurface(mobileSessionPanel, adminPanelBackground, adminPanelShadow, adminPanelBorder);
  applySurfaceBackground(mobileAdminShell, mobileAdminShellBackground);
  applySurfaceBackground(mobileMultiAdminShell, mobileAdminShellBackground);
}
```

- [ ] **Step 4: Re-run the JS contract test**

Run: `python -m unittest tests.test_theme_shell_contract.TestThemeShellContract.test_runtime_script_knows_new_shell_background_keys -v`
Expected: PASS.

- [ ] **Step 5: Commit the frontend theme-application update**

Run:

```bash
git add scripts/main.new.js tests/test_theme_shell_contract.py
git commit -m "$(cat <<'EOF'
feat: apply runtime theme tokens to auth app and admin shells
EOF
)"
```

---

### Task 4: Add desktop theme shell hooks and desktop-specific styling

**Files:**
- Modify: `tests/test_theme_shell_contract.py`
- Modify: `index.html:1569-1814,2187-2625`
- Modify: `styles/style.css:10-24,162-168,491-627,793-1036,1869-1944`
- Test: `tests/test_theme_shell_contract.py`

- [ ] **Step 1: Extend the contract test with desktop HTML/CSS expectations**

Append these tests to `tests/test_theme_shell_contract.py`:

```python
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "styles" / "style.css").read_text(encoding="utf-8")


class TestThemeShellContract(unittest.TestCase):
    def test_desktop_index_exposes_theme_surface_hooks(self):
        for token in [
            'id="auth-login-container"',
            'id="login-container" data-theme-surface="auth"',
            'id="desktop-container-single-login-panel-wrapper" data-theme-panel="app"',
            'id="main-app" data-theme-surface="app"',
            'id="admin-panel-modal-Inline" data-theme-surface="admin"',
        ]:
            self.assertIn(token, HTML)

    def test_styles_define_desktop_theme_variants(self):
        for token in [
            '[data-theme-surface="auth"]',
            '[data-theme-surface="app"]',
            '[data-theme-surface="admin"]',
            'body[data-theme-style-runtime="default"] #login-container',
            'body[data-theme-style-runtime="theme-neo-minimal"] #login-container',
            'body[data-theme-style-runtime="theme-cyber-grid"] #login-container',
            'body[data-theme-style-runtime="theme-eastern-calm"] #login-container',
            'body[data-theme-style-runtime="theme-editorial-magazine"] #login-container',
            'body[data-theme-style-runtime="theme-luxe-noir"] #login-container',
            'body[data-theme-style-runtime="theme-luxe-noir"] #main-app .panel',
        ]:
            self.assertIn(token, CSS)
```

- [ ] **Step 2: Run the desktop contract tests to verify they fail**

Run: `python -m unittest tests.test_theme_shell_contract.TestThemeShellContract.test_desktop_index_exposes_theme_surface_hooks tests.test_theme_shell_contract.TestThemeShellContract.test_styles_define_desktop_theme_variants -v`
Expected: FAIL because the desktop shells do not yet expose the new `data-theme-surface` / `data-theme-panel` hooks and the CSS has no runtime-theme selectors.

- [ ] **Step 3: Add desktop shell hooks to `index.html`**

Update the desktop markup to preserve the existing IDs while adding explicit theme hooks:

```html
<main
  id="login-container"
  data-theme-surface="auth"
  class="h-screen w-screen grid grid-cols-1 lg:grid-cols-3 theme-shell-desktop"
>
  ...
  <div
    class="relative panel rounded-3xl w-full max-w-md p-10 space-y-4 shadow-2xl border border-white/60 hover:shadow-sky-200/40 transition-all duration-300 overflow-y-auto max-h-full"
    id="desktop-container-single-login-panel-wrapper"
    data-theme-panel="app"
  >
    ...
  </div>
</main>

<div
  class="flex flex-col items-center justify-center p-6 md:p-10 lg:p-12 bg-gradient-to-br from-sky-50 via-white to-cyan-50 relative overflow-hidden"
  id="admin-panel-modal-Inline"
  data-theme-surface="admin"
>
  ...
</div>

<main
  id="main-app"
  data-theme-surface="app"
  class="hidden h-screen w-screen grid grid-cols-1 lg:grid-cols-3 xl:grid-cols-4 gap-4 p-4"
>
```

- [ ] **Step 4: Add reusable shell styling and six desktop runtime-theme variants to `styles/style.css`**

Add these concrete CSS blocks near the existing panel/button/input rules:

```css
[data-theme-surface="auth"],
[data-theme-surface="app"],
[data-theme-surface="admin"] {
  transition:
    background 0.25s ease,
    box-shadow 0.25s ease,
    border-color 0.25s ease,
    color 0.25s ease;
}

[data-theme-panel="app"],
[data-theme-panel="admin"] {
  transition:
    background 0.25s ease,
    box-shadow 0.25s ease,
    border-color 0.25s ease;
}

body[data-theme-style-runtime="default"] #login-container {
  grid-template-columns: minmax(0, 1.15fr) minmax(360px, 0.95fr) minmax(0, 0.9fr);
}

body[data-theme-style-runtime="theme-neo-minimal"] #login-container {
  grid-template-columns: minmax(0, 0.88fr) minmax(420px, 1.05fr) minmax(0, 0.85fr);
}

body[data-theme-style-runtime="theme-cyber-grid"] #login-container {
  background-image:
    linear-gradient(rgba(44, 230, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(44, 230, 255, 0.06) 1px, transparent 1px);
  background-size: 32px 32px;
}

body[data-theme-style-runtime="theme-eastern-calm"] #login-container {
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.9fr) minmax(0, 0.85fr);
}

body[data-theme-style-runtime="theme-editorial-magazine"] #login-container {
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.9fr) minmax(0, 0.78fr);
}

body[data-theme-style-runtime="theme-luxe-noir"] #login-container {
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.95fr) minmax(0, 0.95fr);
}

body[data-theme-style-runtime="default"] #main-app .panel,
body[data-theme-style-runtime="default"] #admin-panel-modal-Inline .panel {
  border-radius: 28px;
}

body[data-theme-style-runtime="theme-neo-minimal"] #main-app .panel,
body[data-theme-style-runtime="theme-neo-minimal"] #admin-panel-modal-Inline .panel {
  border-radius: 22px;
  border-width: 1px;
}

body[data-theme-style-runtime="theme-cyber-grid"] #main-app .panel,
body[data-theme-style-runtime="theme-cyber-grid"] #admin-panel-modal-Inline .panel {
  border-radius: 20px;
  border-color: rgba(44, 230, 255, 0.35);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.38);
}

body[data-theme-style-runtime="theme-eastern-calm"] #main-app .panel,
body[data-theme-style-runtime="theme-eastern-calm"] #admin-panel-modal-Inline .panel {
  border-radius: 24px;
  border-color: rgba(196, 155, 108, 0.22);
}

body[data-theme-style-runtime="theme-editorial-magazine"] #main-app .panel,
body[data-theme-style-runtime="theme-editorial-magazine"] #admin-panel-modal-Inline .panel {
  border-radius: 20px;
  box-shadow: 0 20px 52px rgba(52, 42, 33, 0.14);
}

body[data-theme-style-runtime="theme-luxe-noir"] #main-app .panel,
body[data-theme-style-runtime="theme-luxe-noir"] #admin-panel-modal-Inline .panel {
  border-radius: 28px;
  border-color: rgba(207, 169, 91, 0.24);
  box-shadow: 0 24px 72px rgba(5, 6, 12, 0.45);
}
```

- [ ] **Step 5: Re-run the desktop contract tests**

Run: `python -m unittest tests.test_theme_shell_contract.TestThemeShellContract.test_desktop_index_exposes_theme_surface_hooks tests.test_theme_shell_contract.TestThemeShellContract.test_styles_define_desktop_theme_variants -v`
Expected: PASS.

- [ ] **Step 6: Commit the desktop shell update**

Run:

```bash
git add index.html styles/style.css tests/test_theme_shell_contract.py
git commit -m "$(cat <<'EOF'
feat: add desktop theme shell hooks and runtime theme layouts
EOF
)"
```

---

### Task 5: Add mobile theme shell hooks and mobile-specific styling

**Files:**
- Modify: `tests/test_theme_shell_contract.py`
- Modify: `index.html:3591-4270,6269,11995`
- Modify: `styles/style.css:1166-1307,1621-1653,1840-1944`
- Test: `tests/test_theme_shell_contract.py`

- [ ] **Step 1: Extend the contract test with mobile HTML/CSS expectations**

Append these tests to `tests/test_theme_shell_contract.py`:

```python
class TestThemeShellContract(unittest.TestCase):
    def test_mobile_index_exposes_theme_surface_hooks(self):
        for token in [
            'id="mobile-content" data-theme-surface="auth"',
            'id="mobile-auth-login-container-card" data-theme-panel="auth"',
            'id="mobile-login-container" data-theme-surface="app"',
            'id="mobile-session-panel-card" data-theme-panel="admin"',
            'id="mobile-admin-panel-content" data-theme-surface="admin"',
            'id="mobile-multi-admin-content-panel" data-theme-surface="admin"',
        ]:
            self.assertIn(token, HTML)

    def test_styles_define_mobile_theme_variants(self):
        for token in [
            'body.mobile-mode[data-theme-style-runtime="default"] #mobile-content',
            'body.mobile-mode[data-theme-style-runtime="theme-neo-minimal"] #mobile-content',
            'body.mobile-mode[data-theme-style-runtime="theme-cyber-grid"] #mobile-content',
            'body.mobile-mode[data-theme-style-runtime="theme-eastern-calm"] #mobile-content',
            'body.mobile-mode[data-theme-style-runtime="theme-editorial-magazine"] #mobile-content',
            'body.mobile-mode[data-theme-style-runtime="theme-luxe-noir"] #mobile-content',
            'body.mobile-mode [data-theme-panel="auth"]',
            'body.mobile-mode [data-theme-panel="admin"]',
        ]:
            self.assertIn(token, CSS)
```

- [ ] **Step 2: Run the mobile contract tests to verify they fail**

Run: `python -m unittest tests.test_theme_shell_contract.TestThemeShellContract.test_mobile_index_exposes_theme_surface_hooks tests.test_theme_shell_contract.TestThemeShellContract.test_styles_define_mobile_theme_variants -v`
Expected: FAIL because the mobile containers do not yet expose the new theme-surface attributes or mobile runtime-theme selectors.

- [ ] **Step 3: Add mobile theme-surface hooks in `index.html`**

Update the mobile markup to preserve existing IDs while exposing theme-surface hooks:

```html
<main class="mobile-content" id="mobile-content" data-theme-surface="auth">
  <div id="mobile-auth-login-container" class="space-y-4">
    <div class="mobile-card" id="mobile-auth-login-container-card" data-theme-panel="auth">
      ...
    </div>
  </div>

  <div id="mobile-login-container" data-theme-surface="app" class="space-y-4 hidden">
    ...
    <div class="mobile-card relative overflow-hidden !p-5" id="mobile-session-panel-card" data-theme-panel="admin">
      ...
    </div>
  </div>

  <div id="mobile-admin-panel-content" data-theme-surface="admin">
    ...
  </div>

  <div id="mobile-multi-admin-content-panel" data-theme-surface="admin">
    ...
  </div>
</main>
```

- [ ] **Step 4: Add mobile runtime-theme selectors to `styles/style.css`**

Add these concrete mobile rules:

```css
body.mobile-mode [data-theme-panel="auth"],
body.mobile-mode [data-theme-panel="admin"] {
  transition:
    background 0.25s ease,
    box-shadow 0.25s ease,
    border-color 0.25s ease;
}

body.mobile-mode[data-theme-style-runtime="default"] #mobile-content {
  padding: 16px 14px 28px;
}

body.mobile-mode[data-theme-style-runtime="theme-neo-minimal"] #mobile-content {
  padding: 20px 16px 28px;
}

body.mobile-mode[data-theme-style-runtime="theme-cyber-grid"] #mobile-content {
  padding: 18px 14px 30px;
  background-image:
    linear-gradient(rgba(44, 230, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(44, 230, 255, 0.06) 1px, transparent 1px);
  background-size: 24px 24px;
}

body.mobile-mode[data-theme-style-runtime="theme-eastern-calm"] #mobile-content {
  padding: 18px 16px 30px;
}

body.mobile-mode[data-theme-style-runtime="theme-editorial-magazine"] #mobile-content {
  padding: 20px 14px 30px;
}

body.mobile-mode[data-theme-style-runtime="theme-luxe-noir"] #mobile-content {
  padding: 18px 14px 30px;
}

body.mobile-mode[data-theme-style-runtime="default"] [data-theme-panel="auth"],
body.mobile-mode[data-theme-style-runtime="default"] [data-theme-panel="admin"] {
  border-radius: 28px;
}

body.mobile-mode[data-theme-style-runtime="theme-neo-minimal"] [data-theme-panel="auth"],
body.mobile-mode[data-theme-style-runtime="theme-neo-minimal"] [data-theme-panel="admin"] {
  border-radius: 22px;
}

body.mobile-mode[data-theme-style-runtime="theme-cyber-grid"] [data-theme-panel="auth"],
body.mobile-mode[data-theme-style-runtime="theme-cyber-grid"] [data-theme-panel="admin"] {
  border-radius: 20px;
  border-color: rgba(44, 230, 255, 0.32);
}

body.mobile-mode[data-theme-style-runtime="theme-eastern-calm"] [data-theme-panel="auth"],
body.mobile-mode[data-theme-style-runtime="theme-eastern-calm"] [data-theme-panel="admin"] {
  border-radius: 24px;
}

body.mobile-mode[data-theme-style-runtime="theme-editorial-magazine"] [data-theme-panel="auth"],
body.mobile-mode[data-theme-style-runtime="theme-editorial-magazine"] [data-theme-panel="admin"] {
  border-radius: 20px;
}

body.mobile-mode[data-theme-style-runtime="theme-luxe-noir"] [data-theme-panel="auth"],
body.mobile-mode[data-theme-style-runtime="theme-luxe-noir"] [data-theme-panel="admin"] {
  border-radius: 26px;
  border-color: rgba(207, 169, 91, 0.26);
}
```

- [ ] **Step 5: Re-run the mobile contract tests**

Run: `python -m unittest tests.test_theme_shell_contract.TestThemeShellContract.test_mobile_index_exposes_theme_surface_hooks tests.test_theme_shell_contract.TestThemeShellContract.test_styles_define_mobile_theme_variants -v`
Expected: PASS.

- [ ] **Step 6: Commit the mobile shell update**

Run:

```bash
git add index.html styles/style.css tests/test_theme_shell_contract.py
git commit -m "$(cat <<'EOF'
feat: add mobile theme shell hooks and runtime theme layouts
EOF
)"
```

---

### Task 6: Run the full verification set and do the final integration pass

**Files:**
- Test: `tests/test_runtime_theme_catalog.py`
- Test: `tests/test_theme_background_binding.py`
- Test: `tests/test_theme_shell_contract.py`
- Test: `tests/test_ui_theme_previews.py`
- Manual QA: `index.html`, `scripts/main.new.js`, `styles/style.css`, `main.py`

- [ ] **Step 1: Run the full Python verification suite**

Run: `python -m unittest tests.test_runtime_theme_catalog tests.test_theme_background_binding tests.test_theme_shell_contract tests.test_ui_theme_previews -v`
Expected: PASS for all tests.

- [ ] **Step 2: Run a manual static preview check for the six `ui/` source files**

Run: `python -m http.server 8000`
Expected: local preview server starts at `http://localhost:8000/`.

Manual checklist:
- Open `/ui/default-login.html`, `/ui/default-admin.html`, `/ui/neo-minimal-login.html`, `/ui/neo-minimal-admin.html`, `/ui/cyber-grid-login.html`, `/ui/cyber-grid-admin.html`, `/ui/eastern-calm-login.html`, `/ui/eastern-calm-admin.html`, `/ui/editorial-magazine-login.html`, `/ui/editorial-magazine-admin.html`, `/ui/luxe-noir-login.html`, `/ui/luxe-noir-admin.html`.
- Confirm every file still exposes desktop/mobile + light/dark preview surfaces.
- Confirm `ui/default-*` reads as `Anime Core`, not “默认主题”.

- [ ] **Step 3: Run an integration smoke check against the live app in repo root**

Run: `python main.py`
Expected: the Flask app starts successfully with no theme-loading exceptions.

Manual checklist against the running app:
- Open the unauthenticated desktop view and confirm the current runtime theme list only exposes six themes.
- Switch between all six themes and verify the login surface, authenticated desktop app surface, and desktop admin surface all change style.
- Switch to mobile mode and confirm the same six themes update the mobile auth/app/admin shells.
- With the default theme selected, verify the same `pc` background image is reused across desktop auth / app / admin and the same `mobile` background image is reused across mobile auth / app / admin.
- Verify a non-default theme never shows `/theme-assets/random_background_image/...` in its computed background values.

- [ ] **Step 4: Inspect git status before the final commit**

Run: `git status --short`
Expected: only the planned files are modified/added/removed.

- [ ] **Step 5: Commit the verified end-to-end implementation**

Run:

```bash
git add main.py scripts/main.new.js index.html styles/style.css tests/test_runtime_theme_catalog.py tests/test_theme_background_binding.py tests/test_theme_shell_contract.py tests/test_ui_theme_previews.py theme/default.json theme/neo-minimal.json theme/cyber-grid.json theme/eastern-calm.json theme/editorial-magazine.json theme/luxe-noir.json
git commit -m "$(cat <<'EOF'
feat: align runtime theme system with ui source of truth
EOF
)"
```

---

## Spec coverage cross-check

- `ui/` as唯一主题来源 → Task 1.
- `theme/` 只保留六个与 `ui/` 对齐的主题 → Task 1.
- `id/label/description/svg` 全部重写 → Task 1.
- 默认主题随机背景继续按 `session + target` 绑定 → Task 2.
- 默认主题背景扩展到登录 / 前台 / 后台 → Task 2 + Task 3.
- 重构 `main.py` / `scripts/main.new.js` / `index.html` / `styles/style.css` 主题链路 → Task 2, 3, 4, 5.
- 桌面端和移动端一起适配 → Task 4 + Task 5.
- 保持 `ui` 预览基线不变 → Task 6 (`tests/test_ui_theme_previews.py`).

## Placeholder scan

No `TODO`, `TBD`, “implement later”, or “similar to task N” markers remain in this plan.

## Type / naming consistency

This plan consistently uses:

- runtime theme IDs: `default`, `theme-neo-minimal`, `theme-cyber-grid`, `theme-eastern-calm`, `theme-editorial-magazine`, `theme-luxe-noir`
- env var names: `app_shell_background`, `mobile_app_shell_background`, `admin_shell_background`, `mobile_admin_shell_background`, `app_panel_background`, `admin_panel_background`, `admin_panel_border`, `admin_panel_shadow`
- HTML hooks: `data-theme-surface`, `data-theme-panel`, `document.body.dataset.themeStyleRuntime`

If any later edit changes those names, update the tests in Tasks 2-5 at the same time.
