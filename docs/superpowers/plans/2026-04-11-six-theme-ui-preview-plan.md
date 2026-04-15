# Six Theme UI Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build 6 self-contained theme preview pairs in `ui/`, with `default` converted to Anime Core and five additional themes added, while every page shows desktop/mobile and light/dark variants in a single static HTML file.

**Architecture:** Keep every preview page as a standalone HTML document with inline CSS only, following the existing `ui/default-login.html` and `ui/default-admin.html` pattern. Reuse one semantic markup contract across all 12 files (`data-theme`, `data-page`, `data-preview-mode`, `data-theme-preview`, login/admin business labels), and guard it with one `unittest` module that verifies file presence, required semantics, and the absence of runtime JS or API calls.

**Tech Stack:** HTML5, CSS3, Python 3 `unittest`, local static preview via `python -m http.server`.

---

## File Structure（实施前锁定）

- Modify: `ui/default-login.html`
  - Rewrite from current Style C3 login preview to Anime Core login preview
- Modify: `ui/default-admin.html`
  - Rewrite from current Style C3 admin preview to Anime Core admin preview
- Create: `ui/neo-minimal-login.html`
  - Neo Minimal login preview
- Create: `ui/neo-minimal-admin.html`
  - Neo Minimal admin preview
- Create: `ui/cyber-grid-login.html`
  - Cyber Grid login preview
- Create: `ui/cyber-grid-admin.html`
  - Cyber Grid admin preview
- Create: `ui/eastern-calm-login.html`
  - Eastern Calm login preview
- Create: `ui/eastern-calm-admin.html`
  - Eastern Calm admin preview
- Create: `ui/editorial-magazine-login.html`
  - Editorial Magazine login preview
- Create: `ui/editorial-magazine-admin.html`
  - Editorial Magazine admin preview
- Create: `ui/luxe-noir-login.html`
  - Luxe Noir login preview
- Create: `ui/luxe-noir-admin.html`
  - Luxe Noir admin preview
- Create: `tests/test_ui_theme_previews.py`
  - Shared automated verification for all 12 preview files

## Implementation Phases

1. Create the shared `unittest` harness and convert `default` into Anime Core.
2. Add the remaining five theme pairs one theme at a time, extending the same test file before each implementation.
3. Run full automated verification and manual browser QA across all 12 pages.

## Static Preview Contract（所有 HTML 都必须满足）

### Login pages

Every login preview file must include:

- `body` with `data-theme="<theme-id>"` and `data-page="login"`
- one desktop/light surface: `data-preview-mode="desktop" data-theme-preview="light"`
- one desktop/dark surface: `data-preview-mode="desktop" data-theme-preview="dark"`
- one mobile/light surface: `data-preview-mode="mobile" data-theme-preview="light"`
- one mobile/dark surface: `data-preview-mode="mobile" data-theme-preview="dark"`
- visible labels: `用户名`、`密码`、`立即登录`、`访客入口`
- no `<script` tag, no `fetch(`, no `scripts/main.new.js`

### Admin pages

Every admin preview file must include:

- `body` with `data-theme="<theme-id>"` and `data-page="admin"`
- the same four preview surfaces
- visible labels: `系统配置`、`保存配置`、`允许游客登录`、`会话过期时间 (天)`、`默认主题`
- one warning block
- no `<script` tag, no `fetch(`, no `scripts/main.new.js`

## Reuse Strategy

- Reuse the current self-contained file pattern already present in [ui/default-login.html](ui/default-login.html) and [ui/default-admin.html](ui/default-admin.html): one HTML file, one inline `<style>`, no external dependencies.
- Reuse the same semantic class families across all pages: `page`, `intro`, `preview-grid`, `preview-card`, `scene`, `form-card`, `phone`, `warning`, `group`, `field-card`.
- Do **not** extract a shared CSS file. These are portable comparison previews, so duplication is acceptable and reduces coupling.
- Keep business semantics stable across all themes; only the worldbuilding copy, design tokens, layout ratios, and decorative language should change.
- Keep the automated checks in one file so every new theme extends the same contract instead of creating fragmented test logic.

---

### Task 1: Convert `default` previews to Anime Core

**Files:**
- Create: `tests/test_ui_theme_previews.py`
- Modify: `ui/default-login.html`
- Modify: `ui/default-admin.html`
- Test: `tests/test_ui_theme_previews.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "ui"


def read_html(file_name: str) -> str:
    return (UI_DIR / file_name).read_text(encoding="utf-8")


class TestUiThemePreviews(unittest.TestCase):
    def assert_static_page(self, html: str, *, theme: str, page: str) -> None:
        self.assertIn(f'data-theme="{theme}"', html)
        self.assertIn(f'data-page="{page}"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn('data-theme-preview="light"', html)
        self.assertIn('data-theme-preview="dark"', html)
        self.assertNotIn("<script", html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("scripts/main.new.js", html)

    def assert_login_page(self, file_name: str, *, theme: str, heading: str) -> None:
        html = read_html(file_name)
        self.assert_static_page(html, theme=theme, page="login")
        for text in [heading, "用户名", "密码", "立即登录", "访客入口"]:
            self.assertIn(text, html)

    def assert_admin_page(self, file_name: str, *, theme: str, heading: str) -> None:
        html = read_html(file_name)
        self.assert_static_page(html, theme=theme, page="admin")
        for text in [heading, "系统配置", "保存配置", "允许游客登录", "会话过期时间 (天)", "默认主题"]:
            self.assertIn(text, html)

    def test_anime_core_pages(self) -> None:
        self.assert_login_page("default-login.html", theme="anime-core", heading="Anime Core")
        self.assert_admin_page("default-admin.html", theme="anime-core", heading="Anime Core 控制台")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_anime_core_pages -v`
Expected: FAIL because the current `ui/default-login.html` and `ui/default-admin.html` still describe `Style C3` and do not contain `data-theme="anime-core"`.

- [ ] **Step 3: Rewrite both `default` files as Anime Core**

Overwrite the current files with self-contained HTML that keeps the existing four-surface comparison layout but changes the tokens, headings, and copy to Anime Core.

```html
<!-- ui/default-login.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Anime Core 登录页预览</title>
    <style>
      :root {
        --light-bg: linear-gradient(180deg, #fff8fc, #fff0f7 52%, #eef3ff);
        --light-panel: rgba(255, 255, 255, 0.94);
        --light-line: #f0d7ea;
        --light-text: #5e3a57;
        --light-muted: #8b7188;
        --dark-bg: linear-gradient(180deg, #181126, #25173a 52%, #111020);
        --dark-panel: rgba(35, 24, 51, 0.9);
        --dark-line: rgba(255, 176, 221, 0.2);
        --dark-text: #fff2fa;
        --dark-muted: #d8bfd6;
        --accent: linear-gradient(135deg, #ff7fbd, #9f83ff);
      }
    </style>
  </head>
  <body data-theme="anime-core" data-page="login">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Anime Core · 二次元产品基线</span>
        <h1>梦境入口登录页</h1>
        <p>把 default 改造成二次元风格基线：用樱雾、徽章和月光高光承载真实产品表单。</p>
      </header>
      <div class="preview-grid">
        <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light">
          <div class="scene desktop-layout">
            <div class="hero"><span class="chip">梦境入口</span><h2>Anime Core</h2><p>亮色版像一张樱雾产品卡，少女感明确但仍然是标准登录页。</p></div>
            <form class="form-card"><div class="field"><label>用户名</label><input placeholder="请输入用户名" /></div><div class="field"><label>密码</label><input placeholder="请输入密码" /></div><div class="actions"><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></form>
          </div>
        </section>
        <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark">
          <div class="scene desktop-layout">
            <div class="hero"><span class="chip">月夜模式</span><h2>Anime Core</h2><p>暗色版保持夜莓紫与月光蓝的完整世界观，不做简单反相。</p></div>
            <form class="form-card"><div class="field"><label>用户名</label><input placeholder="请输入用户名" /></div><div class="field"><label>密码</label><input placeholder="请输入密码" /></div><div class="actions"><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></form>
          </div>
        </section>
        <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light">
          <div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><span class="chip">手机亮色</span><h3>Anime Core</h3><p>徽章、糖霜按钮和柔和卡片让移动端也像完整产品主题。</p><div class="field"><label>用户名</label><input placeholder="请输入用户名" /></div><div class="field"><label>密码</label><input placeholder="请输入密码" /></div><div class="actions"><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></div>
        </section>
        <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark">
          <div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><span class="chip">手机暗色</span><h3>Anime Core 夜间版</h3><p>夜间版继续保留缎带、勋章与月光高光的识别度。</p><div class="field"><label>用户名</label><input placeholder="请输入用户名" /></div><div class="field"><label>密码</label><input placeholder="请输入密码" /></div><div class="actions"><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></div>
        </section>
      </div>
    </main>
  </body>
</html>
```

```html
<!-- ui/default-admin.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Anime Core 后台配置页预览</title>
    <style>
      :root {
        --light-bg: linear-gradient(180deg, #fff8fc, #fff0f7 52%, #eef3ff);
        --light-panel: rgba(255, 255, 255, 0.94);
        --light-line: #f0d7ea;
        --light-text: #5e3a57;
        --dark-bg: linear-gradient(180deg, #181126, #25173a 52%, #111020);
        --dark-panel: rgba(35, 24, 51, 0.9);
        --dark-line: rgba(255, 176, 221, 0.2);
        --dark-text: #fff2fa;
        --dark-muted: #d8bfd6;
        --accent: linear-gradient(135deg, #ff7fbd, #9f83ff);
      }
    </style>
  </head>
  <body data-theme="anime-core" data-page="admin">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Anime Core · 二次元产品基线</span>
        <h1>梦境控制台配置页</h1>
        <p>后台继续保留配置语义，但采用缎带标签、柔雾卡片与月光边界。</p>
      </header>
      <div class="preview-grid">
        <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light">
          <div class="scene"><div class="topbar"><div><h2>Anime Core 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">刷新</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">保存配置后，部分梦境资源会在下次刷新时重新载入。</div><section class="group"><h3 class="group-title">游客配置</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">30</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Anime Core</div></article></div></section></div>
        </section>
        <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark">
          <div class="scene"><div class="topbar"><div><h2>Anime Core 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">刷新</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">夜间控制台也要保持提示区清晰，不能因为主题化而失去风险感。</div><section class="group"><h3 class="group-title">游客配置</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">30</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Anime Core</div></article></div></section></div>
        </section>
        <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light">
          <div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Anime Core 控制台</h3><p>系统配置</p><div class="warning">保存配置后，界面会重新渲染。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">30</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Anime Core</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div>
        </section>
        <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark">
          <div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Anime Core 控制台</h3><p>系统配置</p><div class="warning">移动暗色版继续保留封印提示框的清晰层级。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">30</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Anime Core</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div>
        </section>
      </div>
    </main>
  </body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_anime_core_pages -v`
Expected: PASS.

- [ ] **Step 5: Manually inspect Anime Core pages**

Open these files in a browser and verify that all four surfaces render and stay readable:

- `ui/default-login.html`
- `ui/default-admin.html`

Expected: one file shows desktop/mobile and light/dark together; admin page still reads like a configuration console, not a poster page.

- [ ] **Step 6: Commit**

```bash
git add ui/default-login.html ui/default-admin.html tests/test_ui_theme_previews.py
git commit -m "feat: convert default previews to anime core"
```

---

### Task 2: Add Neo Minimal previews

**Files:**
- Modify: `tests/test_ui_theme_previews.py`
- Create: `ui/neo-minimal-login.html`
- Create: `ui/neo-minimal-admin.html`
- Test: `tests/test_ui_theme_previews.py`

- [ ] **Step 1: Extend the failing test**

Append this method to `TestUiThemePreviews` in `tests/test_ui_theme_previews.py`:

```python
    def test_neo_minimal_pages(self) -> None:
        self.assert_login_page("neo-minimal-login.html", theme="neo-minimal", heading="Neo Minimal")
        self.assert_admin_page("neo-minimal-admin.html", theme="neo-minimal", heading="Neo Minimal 控制台")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_neo_minimal_pages -v`
Expected: FAIL with `FileNotFoundError` because the two `neo-minimal` files do not exist yet.

- [ ] **Step 3: Create both Neo Minimal HTML files**

Create both files using the same four-surface contract from Task 1, but with these exact theme identifiers, titles, and tokens.

```html
<!-- ui/neo-minimal-login.html -->
<title>Neo Minimal 登录页预览</title>
<body data-theme="neo-minimal" data-page="login">
  <header class="intro"><span class="eyebrow">Neo Minimal · 新极简秩序</span><h1>秩序入口登录页</h1><p>用大留白、规整描边与克制配色做出最安静的一套产品入口。</p></header>
  <style>:root{--light-bg:linear-gradient(180deg,#f8fafc,#eef2f7 55%,#f8fafc);--light-panel:rgba(255,255,255,.97);--light-line:#d8e0ea;--light-text:#0f172a;--light-muted:#64748b;--dark-bg:linear-gradient(180deg,#0f172a,#111827 55%,#0b1120);--dark-panel:rgba(15,23,42,.9);--dark-line:rgba(148,163,184,.18);--dark-text:#f8fafc;--dark-muted:#cbd5e1;--accent:linear-gradient(135deg,#2563eb,#3b82f6);}.desktop-layout{grid-template-columns:1.2fr 380px;gap:40px}.phone{background:#111827}</style>
  <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light"><div class="scene desktop-layout"><div class="hero"><span class="chip">精简入口</span><h2>Neo Minimal</h2><p>所有强调都来自排版、对齐与留白，不依赖装饰层。</p></div><form class="form-card"><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></form></div></section>
  <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark"><div class="scene desktop-layout"><div class="hero"><span class="chip">夜间秩序</span><h2>Neo Minimal</h2><p>暗色版强调石墨底与冷白字，维持成熟工具感。</p></div><form class="form-card"><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></form></div></section>
  <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><h3>Neo Minimal</h3><p>移动端保持单卡、窄边界和最少文案。</p><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></section>
  <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><h3>Neo Minimal 夜间版</h3><p>夜间移动端继续保留极简秩序。</p><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></section>
</body>
```

```html
<!-- ui/neo-minimal-admin.html -->
<title>Neo Minimal 后台配置页预览</title>
<body data-theme="neo-minimal" data-page="admin">
  <header class="intro"><span class="eyebrow">Neo Minimal · 新极简秩序</span><h1>秩序控制台配置页</h1><p>用窄侧栏思维和规则网格组织系统配置，让后台像一块精密工作台。</p></header>
  <style>:root{--light-bg:linear-gradient(180deg,#f8fafc,#eef2f7 55%,#f8fafc);--light-panel:rgba(255,255,255,.97);--light-line:#d8e0ea;--light-text:#0f172a;--dark-bg:linear-gradient(180deg,#0f172a,#111827 55%,#0b1120);--dark-panel:rgba(15,23,42,.9);--dark-line:rgba(148,163,184,.18);--dark-text:#f8fafc;--accent:linear-gradient(135deg,#2563eb,#3b82f6);}.group-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.phone{background:#111827}</style>
  <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light"><div class="scene"><div class="topbar"><div><h2>Neo Minimal 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">刷新</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">保存配置后，新的缓存窗口会在下一次请求后生效。</div><section class="group"><h3 class="group-title">访问控制</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">14</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Neo Minimal</div></article></div></section></div></section>
  <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark"><div class="scene"><div class="topbar"><div><h2>Neo Minimal 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">刷新</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">暗色版仍只保留必要警告层级，不做额外装饰。</div><section class="group"><h3 class="group-title">访问控制</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">14</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Neo Minimal</div></article></div></section></div></section>
  <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Neo Minimal 控制台</h3><p>系统配置</p><div class="warning">保存配置会刷新当前主题缓存。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">14</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Neo Minimal</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div></section>
  <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Neo Minimal 控制台</h3><p>系统配置</p><div class="warning">夜间版保持石墨底和强对齐。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">14</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Neo Minimal</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div></section>
</body>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_neo_minimal_pages -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui_theme_previews.py ui/neo-minimal-login.html ui/neo-minimal-admin.html
git commit -m "feat: add neo minimal preview theme"
```

---

### Task 3: Add Cyber Grid previews

**Files:**
- Modify: `tests/test_ui_theme_previews.py`
- Create: `ui/cyber-grid-login.html`
- Create: `ui/cyber-grid-admin.html`
- Test: `tests/test_ui_theme_previews.py`

- [ ] **Step 1: Extend the failing test**

Append this method to `TestUiThemePreviews`:

```python
    def test_cyber_grid_pages(self) -> None:
        self.assert_login_page("cyber-grid-login.html", theme="cyber-grid", heading="Cyber Grid")
        self.assert_admin_page("cyber-grid-admin.html", theme="cyber-grid", heading="Cyber Grid 控制台")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_cyber_grid_pages -v`
Expected: FAIL with `FileNotFoundError` because the two `cyber-grid` files do not exist yet.

- [ ] **Step 3: Create both Cyber Grid HTML files**

```html
<!-- ui/cyber-grid-login.html -->
<title>Cyber Grid 登录页预览</title>
<body data-theme="cyber-grid" data-page="login">
  <header class="intro"><span class="eyebrow">Cyber Grid · 赛博网格</span><h1>身份认证终端</h1><p>使用网格、扫描线和高对比描边，把登录页做成未来系统入口。</p></header>
  <style>:root{--light-bg:linear-gradient(180deg,#f3fbff,#e8f7ff 50%,#f6fdff);--light-panel:rgba(255,255,255,.92);--light-line:#b6ecff;--light-text:#083344;--dark-bg:linear-gradient(180deg,#071120,#0c1d38 50%,#060b16);--dark-panel:rgba(8,19,36,.9);--dark-line:rgba(64,224,255,.28);--dark-text:#dff9ff;--accent:linear-gradient(135deg,#00d6ff,#7c3aed);}.scene{box-shadow:inset 0 0 0 1px rgba(0,214,255,.12)}.phone{background:#08111f}</style>
  <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light"><div class="scene desktop-layout"><div class="hero"><span class="chip">终端认证</span><h2>Cyber Grid</h2><p>亮色版像未来实验室，强调浅色网格与冷光描边。</p></div><form class="form-card"><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></form></div></section>
  <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark"><div class="scene desktop-layout"><div class="hero"><span class="chip">夜间矩阵</span><h2>Cyber Grid</h2><p>暗色版是主场，发光边界和终端信息感更强。</p></div><form class="form-card"><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></form></div></section>
  <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><h3>Cyber Grid</h3><p>移动端像掌上控制终端。</p><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></section>
  <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><h3>Cyber Grid 夜间版</h3><p>深色移动端保留霓虹边界和终端文本感。</p><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></section>
</body>
```

```html
<!-- ui/cyber-grid-admin.html -->
<title>Cyber Grid 后台配置页预览</title>
<body data-theme="cyber-grid" data-page="admin">
  <header class="intro"><span class="eyebrow">Cyber Grid · 赛博网格</span><h1>参数控制台</h1><p>让后台更像系统操作台，但仍保留配置分组与字段卡片语义。</p></header>
  <style>:root{--light-bg:linear-gradient(180deg,#f3fbff,#e8f7ff 50%,#f6fdff);--light-panel:rgba(255,255,255,.92);--light-line:#b6ecff;--light-text:#083344;--dark-bg:linear-gradient(180deg,#071120,#0c1d38 50%,#060b16);--dark-panel:rgba(8,19,36,.9);--dark-line:rgba(64,224,255,.28);--dark-text:#dff9ff;--accent:linear-gradient(135deg,#00d6ff,#7c3aed);}.group-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.phone{background:#08111f}</style>
  <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light"><div class="scene"><div class="topbar"><div><h2>Cyber Grid 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">同步</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">参数写入后，矩阵缓存会在下一轮同步后更新。</div><section class="group"><h3 class="group-title">访问控制</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">7</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Cyber Grid</div></article></div></section></div></section>
  <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark"><div class="scene"><div class="topbar"><div><h2>Cyber Grid 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">同步</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">暗色版维持高对比风险提示和强参数边界。</div><section class="group"><h3 class="group-title">访问控制</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">7</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Cyber Grid</div></article></div></section></div></section>
  <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Cyber Grid 控制台</h3><p>系统配置</p><div class="warning">保存后会触发终端刷新。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">7</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Cyber Grid</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div></section>
  <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Cyber Grid 控制台</h3><p>系统配置</p><div class="warning">移动暗色端继续保留高对比状态条。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">7</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Cyber Grid</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div></section>
</body>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_cyber_grid_pages -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui_theme_previews.py ui/cyber-grid-login.html ui/cyber-grid-admin.html
git commit -m "feat: add cyber grid preview theme"
```

---

### Task 4: Add Eastern Calm previews

**Files:**
- Modify: `tests/test_ui_theme_previews.py`
- Create: `ui/eastern-calm-login.html`
- Create: `ui/eastern-calm-admin.html`
- Test: `tests/test_ui_theme_previews.py`

- [ ] **Step 1: Extend the failing test**

Append this method to `TestUiThemePreviews`:

```python
    def test_eastern_calm_pages(self) -> None:
        self.assert_login_page("eastern-calm-login.html", theme="eastern-calm", heading="Eastern Calm")
        self.assert_admin_page("eastern-calm-admin.html", theme="eastern-calm", heading="Eastern Calm 控制台")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_eastern_calm_pages -v`
Expected: FAIL with `FileNotFoundError` because the two `eastern-calm` files do not exist yet.

- [ ] **Step 3: Create both Eastern Calm HTML files**

```html
<!-- ui/eastern-calm-login.html -->
<title>Eastern Calm 登录页预览</title>
<body data-theme="eastern-calm" data-page="login">
  <header class="intro"><span class="eyebrow">Eastern Calm · 东方留白</span><h1>静室入口登录页</h1><p>以宣纸、墨灰和留白构成安静但有风骨的登录入口。</p></header>
  <style>:root{--light-bg:linear-gradient(180deg,#faf7f1,#f2ede4 55%,#f9f6f0);--light-panel:rgba(255,252,247,.95);--light-line:#d8c7ad;--light-text:#2d2418;--dark-bg:linear-gradient(180deg,#16130f,#211b15 55%,#12100d);--dark-panel:rgba(31,25,20,.9);--dark-line:rgba(201,177,133,.2);--dark-text:#f7efe2;--accent:linear-gradient(135deg,#8b1e1e,#c28b36);}.desktop-layout{grid-template-columns:1.25fr 360px;gap:48px}.phone{background:#201812}</style>
  <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light"><div class="scene desktop-layout"><div class="hero"><span class="chip">静室入口</span><h2>Eastern Calm</h2><p>亮色版强调宣纸感、留白和缓慢阅读节奏。</p></div><form class="form-card"><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></form></div></section>
  <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark"><div class="scene desktop-layout"><div class="hero"><span class="chip">夜墨入口</span><h2>Eastern Calm</h2><p>暗色版使用夜墨、暗金灰和深木色建立沉静边界。</p></div><form class="form-card"><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></form></div></section>
  <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><h3>Eastern Calm</h3><p>移动端像一张静室签条，保持极少装饰。</p><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></section>
  <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><h3>Eastern Calm 夜间版</h3><p>夜墨移动端继续保留安静节奏。</p><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></section>
</body>
```

```html
<!-- ui/eastern-calm-admin.html -->
<title>Eastern Calm 后台配置页预览</title>
<body data-theme="eastern-calm" data-page="admin">
  <header class="intro"><span class="eyebrow">Eastern Calm · 东方留白</span><h1>卷轴式配置页</h1><p>把后台分组做成卷轴段落和签条卡片，但保持配置语义清晰。</p></header>
  <style>:root{--light-bg:linear-gradient(180deg,#faf7f1,#f2ede4 55%,#f9f6f0);--light-panel:rgba(255,252,247,.95);--light-line:#d8c7ad;--light-text:#2d2418;--dark-bg:linear-gradient(180deg,#16130f,#211b15 55%,#12100d);--dark-panel:rgba(31,25,20,.9);--dark-line:rgba(201,177,133,.2);--dark-text:#f7efe2;--accent:linear-gradient(135deg,#8b1e1e,#c28b36);}.group-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.phone{background:#201812}</style>
  <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light"><div class="scene"><div class="topbar"><div><h2>Eastern Calm 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">复位</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">保存配置后，新的接待规则会在下一次进入时生效。</div><section class="group"><h3 class="group-title">访客接待</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">21</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Eastern Calm</div></article></div></section></div></section>
  <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark"><div class="scene"><div class="topbar"><div><h2>Eastern Calm 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">复位</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">夜墨版继续保留安静但清晰的风险提示。</div><section class="group"><h3 class="group-title">访客接待</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">21</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Eastern Calm</div></article></div></section></div></section>
  <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Eastern Calm 控制台</h3><p>系统配置</p><div class="warning">保存后会重新应用迎宾界面。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">21</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Eastern Calm</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div></section>
  <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Eastern Calm 控制台</h3><p>系统配置</p><div class="warning">移动暗色端继续保留深木色边界。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">21</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Eastern Calm</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div></section>
</body>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_eastern_calm_pages -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui_theme_previews.py ui/eastern-calm-login.html ui/eastern-calm-admin.html
git commit -m "feat: add eastern calm preview theme"
```

---

### Task 5: Add Editorial Magazine previews

**Files:**
- Modify: `tests/test_ui_theme_previews.py`
- Create: `ui/editorial-magazine-login.html`
- Create: `ui/editorial-magazine-admin.html`
- Test: `tests/test_ui_theme_previews.py`

- [ ] **Step 1: Extend the failing test**

Append this method to `TestUiThemePreviews`:

```python
    def test_editorial_magazine_pages(self) -> None:
        self.assert_login_page("editorial-magazine-login.html", theme="editorial-magazine", heading="Editorial Magazine")
        self.assert_admin_page("editorial-magazine-admin.html", theme="editorial-magazine", heading="Editorial Magazine 控制台")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_editorial_magazine_pages -v`
Expected: FAIL with `FileNotFoundError` because the two `editorial-magazine` files do not exist yet.

- [ ] **Step 3: Create both Editorial Magazine HTML files**

```html
<!-- ui/editorial-magazine-login.html -->
<title>Editorial Magazine 登录页预览</title>
<body data-theme="editorial-magazine" data-page="login">
  <header class="intro"><span class="eyebrow">Editorial Magazine · 杂志编排</span><h1>刊首入口登录页</h1><p>用强标题、非对称分栏和版心结构制造最强排版差异。</p></header>
  <style>:root{--light-bg:linear-gradient(180deg,#f7f5f2,#eeebe6 50%,#faf8f5);--light-panel:rgba(255,255,255,.95);--light-line:#d8d0c6;--light-text:#171717;--dark-bg:linear-gradient(180deg,#141414,#1b1b1b 50%,#0f0f0f);--dark-panel:rgba(24,24,24,.92);--dark-line:rgba(255,255,255,.12);--dark-text:#f7f7f5;--accent:linear-gradient(135deg,#111111,#c2410c);}.desktop-layout{grid-template-columns:1.35fr 340px;gap:28px}.phone{background:#111111}</style>
  <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light"><div class="scene desktop-layout"><div class="hero"><span class="chip">刊首入口</span><h2>Editorial Magazine</h2><p>亮色版靠大标题、栏目分隔与版心节奏制造识别度。</p></div><form class="form-card"><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></form></div></section>
  <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark"><div class="scene desktop-layout"><div class="hero"><span class="chip">夜刊模式</span><h2>Editorial Magazine</h2><p>暗色版继续强调强标题和高反差栏位。</p></div><form class="form-card"><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></form></div></section>
  <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><h3>Editorial Magazine</h3><p>移动端转为海报式单列排版。</p><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></section>
  <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><h3>Editorial Magazine 夜间版</h3><p>夜刊版保持高反差标题系统。</p><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></section>
</body>
```

```html
<!-- ui/editorial-magazine-admin.html -->
<title>Editorial Magazine 后台配置页预览</title>
<body data-theme="editorial-magazine" data-page="admin">
  <header class="intro"><span class="eyebrow">Editorial Magazine · 杂志编排</span><h1>编辑台配置页</h1><p>让后台像一块内容编排台，通过跨栏与层级标题组织配置。</p></header>
  <style>:root{--light-bg:linear-gradient(180deg,#f7f5f2,#eeebe6 50%,#faf8f5);--light-panel:rgba(255,255,255,.95);--light-line:#d8d0c6;--light-text:#171717;--dark-bg:linear-gradient(180deg,#141414,#1b1b1b 50%,#0f0f0f);--dark-panel:rgba(24,24,24,.92);--dark-line:rgba(255,255,255,.12);--dark-text:#f7f7f5;--accent:linear-gradient(135deg,#111111,#c2410c);}.group-grid{grid-template-columns:2fr 1fr 1fr}.phone{background:#111111}</style>
  <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light"><div class="scene"><div class="topbar"><div><h2>Editorial Magazine 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">预览</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">保存配置后，首页栏目与欢迎文案会在下一次载入时刷新。</div><section class="group"><h3 class="group-title">栏目设置</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">10</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Editorial Magazine</div></article></div></section></div></section>
  <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark"><div class="scene"><div class="topbar"><div><h2>Editorial Magazine 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">预览</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">夜刊版继续使用高对比标题和深色版心。</div><section class="group"><h3 class="group-title">栏目设置</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">10</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Editorial Magazine</div></article></div></section></div></section>
  <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Editorial Magazine 控制台</h3><p>系统配置</p><div class="warning">保存后会重新编排首页栏目。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">10</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Editorial Magazine</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div></section>
  <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Editorial Magazine 控制台</h3><p>系统配置</p><div class="warning">移动夜刊版保持版心和标题强度。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">10</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Editorial Magazine</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div></section>
</body>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_editorial_magazine_pages -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui_theme_previews.py ui/editorial-magazine-login.html ui/editorial-magazine-admin.html
git commit -m "feat: add editorial magazine preview theme"
```

---

### Task 6: Add Luxe Noir previews

**Files:**
- Modify: `tests/test_ui_theme_previews.py`
- Create: `ui/luxe-noir-login.html`
- Create: `ui/luxe-noir-admin.html`
- Test: `tests/test_ui_theme_previews.py`

- [ ] **Step 1: Extend the failing test**

Append this method to `TestUiThemePreviews`:

```python
    def test_luxe_noir_pages(self) -> None:
        self.assert_login_page("luxe-noir-login.html", theme="luxe-noir", heading="Luxe Noir")
        self.assert_admin_page("luxe-noir-admin.html", theme="luxe-noir", heading="Luxe Noir 控制台")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_luxe_noir_pages -v`
Expected: FAIL with `FileNotFoundError` because the two `luxe-noir` files do not exist yet.

- [ ] **Step 3: Create both Luxe Noir HTML files**

```html
<!-- ui/luxe-noir-login.html -->
<title>Luxe Noir 登录页预览</title>
<body data-theme="luxe-noir" data-page="login">
  <header class="intro"><span class="eyebrow">Luxe Noir · 轻奢夜宴</span><h1>贵宾入口登录页</h1><p>用黑金、酒红和仪式感边框构成最戏剧化的一套产品入口。</p></header>
  <style>:root{--light-bg:linear-gradient(180deg,#f8f3eb,#efe6da 52%,#fbf7f2);--light-panel:rgba(255,250,244,.94);--light-line:#d6b98b;--light-text:#34241a;--dark-bg:linear-gradient(180deg,#120f12,#1b1418 52%,#0f0d10);--dark-panel:rgba(24,18,22,.92);--dark-line:rgba(212,174,107,.22);--dark-text:#f8ead8;--accent:linear-gradient(135deg,#d4ae6b,#8d2b39);}.desktop-layout{grid-template-columns:1.1fr 380px;gap:34px}.phone{background:#130f13}</style>
  <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light"><div class="scene desktop-layout"><div class="hero"><span class="chip">贵宾入口</span><h2>Luxe Noir</h2><p>亮色版是香槟金与象牙白的高端日间入口。</p></div><form class="form-card"><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></form></div></section>
  <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark"><div class="scene desktop-layout"><div class="hero"><span class="chip">夜宴模式</span><h2>Luxe Noir</h2><p>暗色版以黑金、酒红和暖色高光建立完整戏剧感。</p></div><form class="form-card"><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></form></div></section>
  <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><h3>Luxe Noir</h3><p>移动端仍像高定卡片而不是普通表单。</p><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></section>
  <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-card"><h3>Luxe Noir 夜间版</h3><p>夜宴移动端保留暖金描边和深色底感。</p><label>用户名</label><input placeholder="请输入用户名" /><label>密码</label><input placeholder="请输入密码" /><button class="btn btn-primary">立即登录</button><button class="btn btn-secondary">访客入口</button></div></div></div></div></section>
</body>
```

```html
<!-- ui/luxe-noir-admin.html -->
<title>Luxe Noir 后台配置页预览</title>
<body data-theme="luxe-noir" data-page="admin">
  <header class="intro"><span class="eyebrow">Luxe Noir · 轻奢夜宴</span><h1>总控会客厅配置页</h1><p>后台像品牌运营总控台，保留配置语义并强化仪式感层级。</p></header>
  <style>:root{--light-bg:linear-gradient(180deg,#f8f3eb,#efe6da 52%,#fbf7f2);--light-panel:rgba(255,250,244,.94);--light-line:#d6b98b;--light-text:#34241a;--dark-bg:linear-gradient(180deg,#120f12,#1b1418 52%,#0f0d10);--dark-panel:rgba(24,18,22,.92);--dark-line:rgba(212,174,107,.22);--dark-text:#f8ead8;--accent:linear-gradient(135deg,#d4ae6b,#8d2b39);}.group-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.phone{background:#130f13}</style>
  <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light"><div class="scene"><div class="topbar"><div><h2>Luxe Noir 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">预览</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">保存配置后，贵宾入口与主题资源会在下一次载入时刷新。</div><section class="group"><h3 class="group-title">贵宾接待</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">30</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Luxe Noir</div></article></div></section></div></section>
  <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark"><div class="scene"><div class="topbar"><div><h2>Luxe Noir 控制台</h2><p>系统配置</p></div><div class="actions"><button class="btn">预览</button><button class="btn btn-primary">保存配置</button></div></div><div class="warning">夜宴版提示区必须显眼，不能被戏剧化装饰吞掉。</div><section class="group"><h3 class="group-title">贵宾接待</h3><div class="group-grid"><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">30</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Luxe Noir</div></article></div></section></div></section>
  <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Luxe Noir 控制台</h3><p>系统配置</p><div class="warning">保存后会更新贵宾入口风格。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">30</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Luxe Noir</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div></section>
  <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark"><div class="scene"><div class="phone"><div class="phone-screen"><div class="mobile-shell"><h3>Luxe Noir 控制台</h3><p>系统配置</p><div class="warning">移动夜宴端继续保留黑金层级和风险感。</div><article class="field-card"><strong>允许游客登录</strong><div class="mock-select">启用</div></article><article class="field-card"><strong>会话过期时间 (天)</strong><div class="mock-input">30</div></article><article class="field-card"><strong>默认主题</strong><div class="mock-select">Luxe Noir</div></article><button class="btn btn-primary">保存配置</button></div></div></div></div></section>
</body>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ui_theme_previews.TestUiThemePreviews.test_luxe_noir_pages -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui_theme_previews.py ui/luxe-noir-login.html ui/luxe-noir-admin.html
git commit -m "feat: add luxe noir preview theme"
```

---

### Task 7: Run full verification across all 12 preview files

**Files:**
- Test: `tests/test_ui_theme_previews.py`
- Verify: `ui/default-login.html`
- Verify: `ui/default-admin.html`
- Verify: `ui/neo-minimal-login.html`
- Verify: `ui/neo-minimal-admin.html`
- Verify: `ui/cyber-grid-login.html`
- Verify: `ui/cyber-grid-admin.html`
- Verify: `ui/eastern-calm-login.html`
- Verify: `ui/eastern-calm-admin.html`
- Verify: `ui/editorial-magazine-login.html`
- Verify: `ui/editorial-magazine-admin.html`
- Verify: `ui/luxe-noir-login.html`
- Verify: `ui/luxe-noir-admin.html`

- [ ] **Step 1: Run the full automated suite**

Run: `python -m unittest tests.test_ui_theme_previews -v`
Expected: PASS with 6 test methods:

- `test_anime_core_pages`
- `test_neo_minimal_pages`
- `test_cyber_grid_pages`
- `test_eastern_calm_pages`
- `test_editorial_magazine_pages`
- `test_luxe_noir_pages`

- [ ] **Step 2: Serve the repo locally for browser QA**

Run: `python -m http.server 8765`
Expected: `Serving HTTP on 0.0.0.0 port 8765` (or `127.0.0.1 port 8765`).

- [ ] **Step 3: Open every preview and verify the checklist below**

URLs to open:

- `http://localhost:8765/ui/default-login.html`
- `http://localhost:8765/ui/default-admin.html`
- `http://localhost:8765/ui/neo-minimal-login.html`
- `http://localhost:8765/ui/neo-minimal-admin.html`
- `http://localhost:8765/ui/cyber-grid-login.html`
- `http://localhost:8765/ui/cyber-grid-admin.html`
- `http://localhost:8765/ui/eastern-calm-login.html`
- `http://localhost:8765/ui/eastern-calm-admin.html`
- `http://localhost:8765/ui/editorial-magazine-login.html`
- `http://localhost:8765/ui/editorial-magazine-admin.html`
- `http://localhost:8765/ui/luxe-noir-login.html`
- `http://localhost:8765/ui/luxe-noir-admin.html`

Visual checklist:

- each file shows desktop/light, desktop/dark, mobile/light, mobile/dark together
- login pages always keep `用户名` / `密码` / `立即登录` / `访客入口`
- admin pages always keep `系统配置` / `保存配置` / `允许游客登录` / `会话过期时间 (天)` / `默认主题`
- the six themes are visually distinct at a glance
- `default` is clearly Anime Core, not the previous Style C3 page
- no file looks like an activity poster or game splash page instead of a usable product UI
