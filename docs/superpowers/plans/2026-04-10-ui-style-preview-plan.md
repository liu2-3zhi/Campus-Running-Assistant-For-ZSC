# UI 静态风格稿 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成 3 套纯静态 HTML 风格稿，覆盖前台登录页与后台配置页，并在每个文件中同时展示桌面端与移动端效果，供用户进行 UI 方向选择。

**Architecture:** 直接在 `ui-previews/` 下创建 6 个自包含 HTML 文件，每个文件只用内联 CSS 呈现一个页面主题，不接入任何现有业务 JS。用 3 个轻量 `unittest` 文件分别校验 A/B/C 三套静态稿是否存在、是否同时包含桌面端与移动端预览、是否保留登录页/配置页的关键语义，并确保没有误接入 `scripts/main.new.js` 或 `fetch`。

**Tech Stack:** HTML5、CSS3、Python `unittest`、本地静态服务器（`python -m http.server`）。

---

## File Structure（实施前锁定）

- Create: `ui-previews/style-a-login.html`
  - 极简专业风登录页预览；同页展示桌面端与移动端
- Create: `ui-previews/style-a-admin.html`
  - 极简专业风后台配置页预览；映射 `admin-config-form` 的分组 + 字段卡片语义
- Create: `ui-previews/style-b-login.html`
  - 玻璃科技风登录页预览；同页展示桌面端与移动端
- Create: `ui-previews/style-b-admin.html`
  - 玻璃科技风后台配置页预览
- Create: `ui-previews/style-c-login.html`
  - 品牌化柔和风登录页预览；同页展示桌面端与移动端
- Create: `ui-previews/style-c-admin.html`
  - 品牌化柔和风后台配置页预览
- Create: `tests/test_ui_previews_style_a.py`
  - 校验 A 套文件存在、语义完整、无业务脚本依赖
- Create: `tests/test_ui_previews_style_b.py`
  - 校验 B 套文件存在、语义完整、无业务脚本依赖
- Create: `tests/test_ui_previews_style_c.py`
  - 校验 C 套文件存在、语义完整、无业务脚本依赖

---

### Task 1: 建立 Style A（极简专业风）静态稿与校验测试

**Files:**
- Create: `ui-previews/style-a-login.html`
- Create: `ui-previews/style-a-admin.html`
- Create: `tests/test_ui_previews_style_a.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_PREVIEWS = ROOT / "ui-previews"


def read_preview(name: str) -> str:
    return (UI_PREVIEWS / name).read_text(encoding="utf-8")


class TestUiPreviewsStyleA(unittest.TestCase):
    def test_login_preview_has_desktop_and_mobile_sections(self):
        html = read_preview("style-a-login.html")
        self.assertIn('data-style="a"', html)
        self.assertIn('data-page="login"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn("跑步助手", html)
        self.assertIn("立即登录", html)
        self.assertNotIn("scripts/main.new.js", html)
        self.assertNotIn("fetch(", html)

    def test_admin_preview_maps_to_config_page_semantics(self):
        html = read_preview("style-a-admin.html")
        self.assertIn('data-style="a"', html)
        self.assertIn('data-page="admin"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn("系统配置", html)
        self.assertIn("保存配置", html)
        self.assertIn("允许游客登录", html)
        self.assertIn("会话过期时间 (天)", html)
        self.assertNotIn("scripts/main.new.js", html)
        self.assertNotIn("fetch(", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ui_previews_style_a -v`
Expected: FAIL with `FileNotFoundError` because `ui-previews/style-a-login.html` and `ui-previews/style-a-admin.html` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```html
<!-- ui-previews/style-a-login.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style A 登录页预览</title>
    <style>
      :root {
        --bg: #f5f8fd;
        --panel: rgba(255, 255, 255, 0.92);
        --line: #dbe4f0;
        --text: #0f172a;
        --muted: #64748b;
        --primary: #2563eb;
        --primary-soft: #dbeafe;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--text);
        background: linear-gradient(180deg, #f8fbff 0%, #eef4ff 55%, #f8fbff 100%);
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 860px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: #eff6ff;
        color: #1d4ed8;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.04em;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: var(--muted); line-height: 1.7; }
      .grid {
        max-width: 1320px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: minmax(0, 1.4fr) minmax(320px, 420px);
        gap: 24px;
        align-items: start;
      }
      .preview {
        border: 1px solid rgba(219, 228, 240, 0.9);
        border-radius: 28px;
        background: rgba(255, 255, 255, 0.72);
        box-shadow: 0 24px 50px rgba(15, 23, 42, 0.08);
        padding: 22px;
      }
      .preview-tag {
        display: inline-flex;
        margin-bottom: 14px;
        padding: 5px 10px;
        border-radius: 999px;
        background: #e2e8f0;
        color: #334155;
        font-size: 12px;
        font-weight: 700;
      }
      .desktop-scene {
        min-height: 680px;
        border-radius: 24px;
        background: linear-gradient(135deg, #ffffff 0%, #f2f7ff 100%);
        border: 1px solid #e5edf8;
        padding: 48px;
        display: grid;
        grid-template-columns: 1.1fr 420px;
        gap: 40px;
        align-items: center;
      }
      .hero h2 { margin: 14px 0 12px; font-size: 44px; }
      .hero p { margin: 0 0 18px; color: var(--muted); line-height: 1.8; }
      .hero ul { margin: 0; padding-left: 18px; color: #334155; line-height: 1.8; }
      .pill {
        display: inline-flex;
        padding: 7px 12px;
        border-radius: 999px;
        background: var(--primary-soft);
        color: #1d4ed8;
        font-weight: 700;
        font-size: 13px;
      }
      .card {
        background: var(--panel);
        border: 1px solid #e2e8f0;
        border-radius: 24px;
        padding: 26px;
        box-shadow: 0 18px 30px rgba(15, 23, 42, 0.06);
      }
      .logo {
        width: 52px;
        height: 52px;
        display: grid;
        place-items: center;
        border-radius: 16px;
        background: linear-gradient(135deg, #2563eb, #60a5fa);
        color: #fff;
        font-weight: 800;
        font-size: 22px;
      }
      .card h3 { margin: 16px 0 8px; font-size: 28px; }
      .card p { margin: 0 0 18px; color: var(--muted); }
      .field { margin-bottom: 14px; }
      .field label {
        display: block;
        margin-bottom: 8px;
        color: #334155;
        font-size: 14px;
        font-weight: 700;
      }
      .field input {
        width: 100%;
        padding: 13px 14px;
        border-radius: 16px;
        border: 1px solid var(--line);
        background: #fff;
        font-size: 14px;
        color: var(--text);
        outline: none;
      }
      .field input:focus {
        border-color: #60a5fa;
        box-shadow: 0 0 0 4px rgba(96, 165, 250, 0.18);
      }
      .actions { display: grid; gap: 12px; margin-top: 18px; }
      .btn {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        min-height: 46px;
        border-radius: 16px;
        border: none;
        font-size: 15px;
        font-weight: 700;
        cursor: pointer;
      }
      .btn-primary {
        background: linear-gradient(135deg, #2563eb, #3b82f6);
        color: #fff;
        box-shadow: 0 14px 24px rgba(37, 99, 235, 0.22);
      }
      .btn-secondary {
        background: #fff;
        color: #1e293b;
        border: 1px solid #dbe4f0;
      }
      .helper { margin-top: 12px; font-size: 13px; color: var(--muted); text-align: center; }
      .phone {
        width: 100%;
        max-width: 360px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #0f172a;
        box-shadow: 0 24px 50px rgba(15, 23, 42, 0.22);
      }
      .phone-screen {
        min-height: 720px;
        border-radius: 26px;
        background: linear-gradient(180deg, #f8fbff, #edf4ff);
        padding: 22px;
      }
      .mobile-top { margin-bottom: 20px; }
      .mobile-top h2 { margin: 10px 0 6px; font-size: 30px; }
      .mobile-top p { margin: 0; color: var(--muted); line-height: 1.7; }
      .mobile-card {
        margin-top: 18px;
        background: rgba(255, 255, 255, 0.94);
        border: 1px solid #e2e8f0;
        border-radius: 24px;
        padding: 20px;
        box-shadow: 0 14px 24px rgba(15, 23, 42, 0.08);
      }
      @media (max-width: 1120px) {
        .page { padding: 24px; }
        .grid { grid-template-columns: 1fr; }
        .desktop-scene { grid-template-columns: 1fr; padding: 28px; }
      }
    </style>
  </head>
  <body data-style="a" data-page="login">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style A · 极简专业风</span>
        <h1>前台登录页静态预览</h1>
        <p>用清晰留白、稳定层级和克制的蓝色点缀，验证“更耐看、更易落地”的整体 UI 方向。</p>
      </header>

      <div class="grid">
        <section class="preview" data-preview-mode="desktop">
          <span class="preview-tag">桌面端预览</span>
          <div class="desktop-scene">
            <div class="hero">
              <span class="pill">校园跑管理</span>
              <h2>跑步助手</h2>
              <p>在更整洁的登录体验中完成身份进入、查看公告信息，并快速进入任务中心与管理模块。</p>
              <ul>
                <li>更清楚的标题层级与辅助说明</li>
                <li>更稳的表单边框、焦点态与按钮层次</li>
                <li>适合后续统一到前台与后台的基础组件语言</li>
              </ul>
            </div>

            <form class="card">
              <div class="logo">跑</div>
              <h3>欢迎回来</h3>
              <p>登录后可继续查看任务、通知与个人配置。</p>

              <div class="field">
                <label for="desktop-user">账号 / 手机号</label>
                <input id="desktop-user" type="text" value="admin" />
              </div>
              <div class="field">
                <label for="desktop-password">密码</label>
                <input id="desktop-password" type="password" value="admin" />
              </div>

              <div class="actions">
                <button class="btn btn-primary" type="button">立即登录</button>
                <button class="btn btn-secondary" type="button">游客试用</button>
              </div>
              <div class="helper">默认展示为纯静态示意，不接入真实登录逻辑。</div>
            </form>
          </div>
        </section>

        <section class="preview" data-preview-mode="mobile">
          <span class="preview-tag">移动端预览</span>
          <div class="phone">
            <div class="phone-screen">
              <div class="mobile-top">
                <span class="pill">移动端</span>
                <h2>跑步助手</h2>
                <p>保持同一视觉语言，把桌面端的整洁感延续到移动端登录流程。</p>
              </div>

              <div class="mobile-card">
                <div class="field">
                  <label for="mobile-user">账号 / 手机号</label>
                  <input id="mobile-user" type="text" placeholder="请输入账号" />
                </div>
                <div class="field">
                  <label for="mobile-password">密码</label>
                  <input id="mobile-password" type="password" placeholder="请输入密码" />
                </div>
                <div class="actions">
                  <button class="btn btn-primary" type="button">立即登录</button>
                  <button class="btn btn-secondary" type="button">游客试用</button>
                </div>
                <div class="helper">简化装饰，保证输入区和 CTA 最醒目。</div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </body>
</html>
```

```html
<!-- ui-previews/style-a-admin.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style A 后台配置页预览</title>
    <style>
      :root {
        --bg: #f5f8fd;
        --panel: rgba(255, 255, 255, 0.94);
        --line: #dde7f3;
        --text: #0f172a;
        --muted: #64748b;
        --primary: #2563eb;
        --primary-soft: #eff6ff;
        --warning-bg: #fff7ed;
        --warning-line: #fdba74;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--text);
        background: linear-gradient(180deg, #f8fbff 0%, #eef4ff 52%, #f8fbff 100%);
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 900px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: #eff6ff;
        color: #1d4ed8;
        font-weight: 700;
        font-size: 12px;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: var(--muted); line-height: 1.7; }
      .grid {
        max-width: 1380px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: minmax(0, 1.4fr) minmax(320px, 430px);
        gap: 24px;
        align-items: start;
      }
      .preview {
        border-radius: 28px;
        border: 1px solid rgba(221, 231, 243, 0.95);
        background: rgba(255, 255, 255, 0.72);
        box-shadow: 0 24px 50px rgba(15, 23, 42, 0.08);
        padding: 22px;
      }
      .preview-tag {
        display: inline-flex;
        margin-bottom: 14px;
        padding: 5px 10px;
        border-radius: 999px;
        background: #e2e8f0;
        color: #334155;
        font-size: 12px;
        font-weight: 700;
      }
      .desktop-scene {
        min-height: 760px;
        border-radius: 24px;
        background: linear-gradient(135deg, #ffffff 0%, #f3f7ff 100%);
        border: 1px solid #e5edf8;
        padding: 28px;
      }
      .topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        margin-bottom: 18px;
      }
      .topbar h2 { margin: 0; font-size: 28px; }
      .topbar p { margin: 6px 0 0; color: var(--muted); }
      .actions { display: flex; gap: 10px; flex-wrap: wrap; }
      .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 42px;
        padding: 0 16px;
        border-radius: 14px;
        border: 1px solid var(--line);
        background: #fff;
        font-weight: 700;
        color: #1e293b;
      }
      .btn-primary {
        background: linear-gradient(135deg, #2563eb, #3b82f6);
        border-color: transparent;
        color: #fff;
        box-shadow: 0 14px 24px rgba(37, 99, 235, 0.22);
      }
      .warning {
        margin-bottom: 18px;
        padding: 14px 16px;
        border-radius: 18px;
        border: 1px solid var(--warning-line);
        background: var(--warning-bg);
        color: #9a3412;
        line-height: 1.7;
      }
      .group { margin-top: 22px; }
      .group-title {
        margin: 0 0 12px;
        font-size: 18px;
        font-weight: 800;
      }
      .group-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
      }
      .field-card {
        padding: 18px;
        border-radius: 20px;
        border: 1px solid #e2e8f0;
        background: rgba(255, 255, 255, 0.98);
        box-shadow: 0 12px 20px rgba(15, 23, 42, 0.05);
      }
      .field-card strong { display: block; margin-bottom: 8px; font-size: 15px; }
      .field-card p { margin: 0 0 10px; color: var(--muted); font-size: 13px; line-height: 1.6; }
      .mock-input,
      .mock-select {
        display: flex;
        align-items: center;
        min-height: 42px;
        padding: 0 14px;
        border-radius: 14px;
        border: 1px solid var(--line);
        background: #fff;
        color: #334155;
        font-size: 14px;
      }
      .stack { display: grid; gap: 8px; }
      .sort-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        border-radius: 14px;
        background: #fff;
        border: 1px solid var(--line);
      }
      .badge {
        width: 22px;
        height: 22px;
        display: grid;
        place-items: center;
        border-radius: 999px;
        background: var(--primary-soft);
        color: #1d4ed8;
        font-size: 12px;
        font-weight: 800;
      }
      .phone {
        width: 100%;
        max-width: 370px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #0f172a;
        box-shadow: 0 24px 50px rgba(15, 23, 42, 0.22);
      }
      .phone-screen {
        min-height: 780px;
        border-radius: 26px;
        background: linear-gradient(180deg, #f8fbff, #edf4ff);
        padding: 18px;
      }
      .mobile-shell {
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid #e2e8f0;
        border-radius: 24px;
        padding: 18px;
      }
      .mobile-title { margin: 0 0 6px; font-size: 24px; }
      .mobile-subtitle { margin: 0 0 14px; color: var(--muted); line-height: 1.6; }
      .mobile-actions { display: flex; gap: 8px; margin-bottom: 12px; }
      .mobile-actions .btn { flex: 1; min-height: 40px; padding: 0 10px; font-size: 13px; }
      @media (max-width: 1140px) {
        .page { padding: 24px; }
        .grid { grid-template-columns: 1fr; }
        .group-grid { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body data-style="a" data-page="admin">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style A · 极简专业风</span>
        <h1>后台配置页静态预览</h1>
        <p>把当前 `admin-config-form` 的“分组 + 字段卡片”语义重组成更清晰、更现代的管理面板。</p>
      </header>

      <div class="grid">
        <section class="preview" data-preview-mode="desktop">
          <span class="preview-tag">桌面端预览</span>
          <div class="desktop-scene">
            <div class="topbar">
              <div>
                <h2>系统配置</h2>
                <p>统一展示后台配置卡片、说明文案与操作按钮层级。</p>
              </div>
              <div class="actions">
                <button class="btn" type="button">刷新</button>
                <button class="btn btn-primary" type="button">保存配置</button>
              </div>
            </div>

            <div class="warning">⚠️ 修改这些配置可能影响系统稳定性。保存后，部分配置需要重启程序才能生效。</div>

            <section class="group">
              <h3 class="group-title">游客配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>允许游客登录</strong>
                  <p>是否允许未注册用户以游客身份使用系统。</p>
                  <div class="mock-select">启用</div>
                </article>
                <article class="field-card">
                  <strong>显示新手帮助</strong>
                  <p>是否展示新手帮助入口与说明。</p>
                  <div class="mock-select">启用</div>
                </article>
              </div>
            </section>

            <section class="group">
              <h3 class="group-title">系统配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>会话过期时间 (天)</strong>
                  <p>超过该时间未访问的会话将被自动清理。</p>
                  <div class="mock-input">30</div>
                </article>
                <article class="field-card">
                  <strong>密码存储方式</strong>
                  <p>决定后台账号密码的持久化策略。</p>
                  <div class="mock-select">BCrypt (自动加盐)</div>
                </article>
                <article class="field-card">
                  <strong>学校账号目录</strong>
                  <p>存储 `school_accounts/*.ini` 文件的目录。</p>
                  <div class="mock-input">school_accounts</div>
                </article>
                <article class="field-card">
                  <strong>IP 查询顺序</strong>
                  <p>拖拽排序，按优先级依次查询 IP 归属地。</p>
                  <div class="stack">
                    <div class="sort-item"><span class="badge">1</span><span>UapiPro</span></div>
                    <div class="sort-item"><span class="badge">2</span><span>高德地图</span></div>
                    <div class="sort-item"><span class="badge">3</span><span>百度开放数据</span></div>
                  </div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="preview" data-preview-mode="mobile">
          <span class="preview-tag">移动端预览</span>
          <div class="phone">
            <div class="phone-screen">
              <div class="mobile-shell">
                <h2 class="mobile-title">系统配置</h2>
                <p class="mobile-subtitle">移动端保留后台配置语义，但把卡片、按钮和警告条重新压缩成更适合单列浏览的层级。</p>
                <div class="mobile-actions">
                  <button class="btn" type="button">刷新</button>
                  <button class="btn btn-primary" type="button">保存配置</button>
                </div>
                <div class="warning">⚠️ 修改系统配置后，部分选项需要重启程序。</div>
                <section class="group">
                  <h3 class="group-title">游客配置</h3>
                  <div class="field-card">
                    <strong>允许游客登录</strong>
                    <p>未注册用户可直接进入系统。</p>
                    <div class="mock-select">启用</div>
                  </div>
                </section>
                <section class="group">
                  <h3 class="group-title">系统配置</h3>
                  <div class="field-card">
                    <strong>会话过期时间 (天)</strong>
                    <p>自动清理未访问会话。</p>
                    <div class="mock-input">30</div>
                  </div>
                  <div class="field-card" style="margin-top: 12px;">
                    <strong>密码存储方式</strong>
                    <p>统一显示常用安全选项。</p>
                    <div class="mock-select">BCrypt (自动加盐)</div>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ui_previews_style_a -v`
Expected: PASS with 2 tests passing.

- [ ] **Step 5: Commit**

```bash
git add ui-previews/style-a-login.html ui-previews/style-a-admin.html tests/test_ui_previews_style_a.py
git commit -m "feat: add minimal professional UI previews"
```

---

### Task 2: 建立 Style B（玻璃科技风）静态稿与校验测试

**Files:**
- Create: `ui-previews/style-b-login.html`
- Create: `ui-previews/style-b-admin.html`
- Create: `tests/test_ui_previews_style_b.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_PREVIEWS = ROOT / "ui-previews"


def read_preview(name: str) -> str:
    return (UI_PREVIEWS / name).read_text(encoding="utf-8")


class TestUiPreviewsStyleB(unittest.TestCase):
    def test_login_preview_has_glass_theme_markers(self):
        html = read_preview("style-b-login.html")
        self.assertIn('data-style="b"', html)
        self.assertIn('data-page="login"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn("Style B · 玻璃科技风", html)
        self.assertIn("跑步助手", html)
        self.assertIn("立即登录", html)
        self.assertNotIn("scripts/main.new.js", html)
        self.assertNotIn("fetch(", html)

    def test_admin_preview_has_admin_config_semantics(self):
        html = read_preview("style-b-admin.html")
        self.assertIn('data-style="b"', html)
        self.assertIn('data-page="admin"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn("系统配置", html)
        self.assertIn("保存配置", html)
        self.assertIn("允许游客登录", html)
        self.assertIn("IP 查询顺序", html)
        self.assertNotIn("scripts/main.new.js", html)
        self.assertNotIn("fetch(", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ui_previews_style_b -v`
Expected: FAIL with `FileNotFoundError` because the two Style B preview files do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```html
<!-- ui-previews/style-b-login.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style B 登录页预览</title>
    <style>
      :root {
        --bg-1: #07111f;
        --bg-2: #111c36;
        --panel: rgba(12, 22, 44, 0.58);
        --line: rgba(148, 163, 184, 0.28);
        --text: #e2e8f0;
        --muted: #94a3b8;
        --primary: #38bdf8;
        --accent: #8b5cf6;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--text);
        background:
          radial-gradient(circle at top left, rgba(56, 189, 248, 0.22), transparent 28%),
          radial-gradient(circle at bottom right, rgba(139, 92, 246, 0.22), transparent 30%),
          linear-gradient(180deg, var(--bg-1), var(--bg-2));
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 880px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(56, 189, 248, 0.14);
        border: 1px solid rgba(56, 189, 248, 0.24);
        color: #7dd3fc;
        font-size: 12px;
        font-weight: 700;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: var(--muted); line-height: 1.7; }
      .grid {
        max-width: 1320px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: minmax(0, 1.4fr) minmax(320px, 420px);
        gap: 24px;
        align-items: start;
      }
      .preview {
        border-radius: 30px;
        padding: 22px;
        background: rgba(7, 17, 31, 0.36);
        border: 1px solid rgba(148, 163, 184, 0.18);
        box-shadow: 0 24px 60px rgba(2, 8, 23, 0.45);
        backdrop-filter: blur(16px);
      }
      .preview-tag {
        display: inline-flex;
        margin-bottom: 14px;
        padding: 5px 10px;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.56);
        color: #cbd5e1;
        border: 1px solid rgba(148, 163, 184, 0.18);
        font-size: 12px;
        font-weight: 700;
      }
      .desktop-scene {
        min-height: 680px;
        border-radius: 26px;
        padding: 42px;
        display: grid;
        grid-template-columns: 1.05fr 420px;
        gap: 36px;
        align-items: center;
        background:
          radial-gradient(circle at top right, rgba(56, 189, 248, 0.12), transparent 24%),
          linear-gradient(180deg, rgba(15, 23, 42, 0.78), rgba(15, 23, 42, 0.52));
        border: 1px solid rgba(148, 163, 184, 0.16);
      }
      .hero h2 { margin: 16px 0 12px; font-size: 46px; }
      .hero p { margin: 0 0 18px; color: #cbd5e1; line-height: 1.8; }
      .metrics {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin-top: 20px;
      }
      .metric {
        padding: 16px;
        border-radius: 18px;
        background: rgba(15, 23, 42, 0.52);
        border: 1px solid rgba(148, 163, 184, 0.14);
      }
      .metric strong { display: block; font-size: 22px; margin-bottom: 4px; }
      .metric span { color: var(--muted); font-size: 13px; }
      .card {
        padding: 26px;
        border-radius: 26px;
        background: var(--panel);
        border: 1px solid rgba(148, 163, 184, 0.16);
        backdrop-filter: blur(18px);
        box-shadow: 0 24px 40px rgba(2, 8, 23, 0.34);
      }
      .logo {
        width: 54px;
        height: 54px;
        display: grid;
        place-items: center;
        border-radius: 18px;
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.9), rgba(139, 92, 246, 0.9));
        color: #fff;
        font-size: 22px;
        font-weight: 800;
        box-shadow: 0 0 24px rgba(56, 189, 248, 0.4);
      }
      .card h3 { margin: 16px 0 8px; font-size: 28px; }
      .card p { margin: 0 0 18px; color: #cbd5e1; }
      .field { margin-bottom: 14px; }
      .field label { display: block; margin-bottom: 8px; color: #cbd5e1; font-size: 14px; font-weight: 700; }
      .field input {
        width: 100%;
        min-height: 48px;
        padding: 0 14px;
        border-radius: 16px;
        border: 1px solid rgba(148, 163, 184, 0.22);
        background: rgba(15, 23, 42, 0.56);
        color: #e2e8f0;
        outline: none;
      }
      .field input:focus {
        border-color: rgba(56, 189, 248, 0.72);
        box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.16);
      }
      .actions { display: grid; gap: 12px; margin-top: 18px; }
      .btn {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        min-height: 46px;
        border-radius: 16px;
        border: 1px solid rgba(148, 163, 184, 0.22);
        background: rgba(15, 23, 42, 0.54);
        color: #e2e8f0;
        font-size: 15px;
        font-weight: 700;
      }
      .btn-primary {
        background: linear-gradient(135deg, #38bdf8, #6366f1);
        border-color: transparent;
        box-shadow: 0 0 28px rgba(56, 189, 248, 0.3);
      }
      .helper { margin-top: 12px; text-align: center; font-size: 13px; color: var(--muted); }
      .phone {
        width: 100%;
        max-width: 360px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: linear-gradient(180deg, #0f172a, #020617);
        box-shadow: 0 28px 60px rgba(2, 8, 23, 0.55);
      }
      .phone-screen {
        min-height: 720px;
        border-radius: 26px;
        padding: 22px;
        background:
          radial-gradient(circle at top, rgba(56, 189, 248, 0.2), transparent 24%),
          linear-gradient(180deg, rgba(8, 15, 32, 0.98), rgba(15, 23, 42, 0.98));
      }
      .mobile-shell {
        margin-top: 18px;
        padding: 18px;
        border-radius: 24px;
        background: rgba(12, 22, 44, 0.66);
        border: 1px solid rgba(148, 163, 184, 0.16);
        backdrop-filter: blur(18px);
      }
      .mobile-shell h2 { margin: 12px 0 6px; font-size: 30px; }
      .mobile-shell p { margin: 0; color: #cbd5e1; line-height: 1.7; }
      @media (max-width: 1120px) {
        .page { padding: 24px; }
        .grid { grid-template-columns: 1fr; }
        .desktop-scene { grid-template-columns: 1fr; padding: 28px; }
        .metrics { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body data-style="b" data-page="login">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style B · 玻璃科技风</span>
        <h1>前台登录页静态预览</h1>
        <p>通过暗色背景、玻璃模糊与局部霓虹高光，验证更强科技感、更强记忆点的视觉方向。</p>
      </header>

      <div class="grid">
        <section class="preview" data-preview-mode="desktop">
          <span class="preview-tag">桌面端预览</span>
          <div class="desktop-scene">
            <div class="hero">
              <span class="eyebrow">实时监控 · 任务入口</span>
              <h2>跑步助手</h2>
              <p>把登录入口做成更有产品感的展示界面，让前台不只像工具页，也更像完整应用的起始屏。</p>
              <div class="metrics">
                <div class="metric"><strong>3 套</strong><span>风格稿并行对比</span></div>
                <div class="metric"><strong>双端</strong><span>桌面与移动同页查看</span></div>
                <div class="metric"><strong>零接入</strong><span>不调用真实业务脚本</span></div>
              </div>
            </div>

            <form class="card">
              <div class="logo">跑</div>
              <h3>连接会话</h3>
              <p>安全连接校园跑服务，继续进入公告、任务与账户管理。</p>
              <div class="field">
                <label for="glass-user">账号 / 手机号</label>
                <input id="glass-user" type="text" value="admin" />
              </div>
              <div class="field">
                <label for="glass-password">密码</label>
                <input id="glass-password" type="password" value="admin" />
              </div>
              <div class="actions">
                <button class="btn btn-primary" type="button">立即登录</button>
                <button class="btn" type="button">游客试用</button>
              </div>
              <div class="helper">视觉重点集中在模糊卡片、发光 CTA 与暗色氛围层。</div>
            </form>
          </div>
        </section>

        <section class="preview" data-preview-mode="mobile">
          <span class="preview-tag">移动端预览</span>
          <div class="phone">
            <div class="phone-screen">
              <div class="mobile-shell">
                <span class="eyebrow">移动端</span>
                <h2>跑步助手</h2>
                <p>保持玻璃层与霓虹按钮，但把可读性放在更高优先级，避免移动端过度花哨。</p>
                <div class="field" style="margin-top: 18px;">
                  <label for="glass-mobile-user">账号 / 手机号</label>
                  <input id="glass-mobile-user" type="text" placeholder="输入账号" />
                </div>
                <div class="field">
                  <label for="glass-mobile-password">密码</label>
                  <input id="glass-mobile-password" type="password" placeholder="输入密码" />
                </div>
                <div class="actions">
                  <button class="btn btn-primary" type="button">立即登录</button>
                  <button class="btn" type="button">游客试用</button>
                </div>
                <div class="helper">移动端用更强对比让表单区不会淹没在背景特效里。</div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </body>
</html>
```

```html
<!-- ui-previews/style-b-admin.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style B 后台配置页预览</title>
    <style>
      :root {
        --bg-1: #07111f;
        --bg-2: #111c36;
        --panel: rgba(12, 22, 44, 0.62);
        --line: rgba(148, 163, 184, 0.24);
        --text: #e2e8f0;
        --muted: #94a3b8;
        --primary: #38bdf8;
        --accent: #8b5cf6;
        --warning-bg: rgba(124, 45, 18, 0.24);
        --warning-line: rgba(251, 146, 60, 0.4);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--text);
        background:
          radial-gradient(circle at top left, rgba(56, 189, 248, 0.2), transparent 24%),
          radial-gradient(circle at bottom right, rgba(139, 92, 246, 0.2), transparent 30%),
          linear-gradient(180deg, var(--bg-1), var(--bg-2));
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 920px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(56, 189, 248, 0.14);
        border: 1px solid rgba(56, 189, 248, 0.24);
        color: #7dd3fc;
        font-weight: 700;
        font-size: 12px;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: var(--muted); line-height: 1.7; }
      .grid {
        max-width: 1380px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: minmax(0, 1.4fr) minmax(320px, 430px);
        gap: 24px;
        align-items: start;
      }
      .preview {
        padding: 22px;
        border-radius: 30px;
        background: rgba(7, 17, 31, 0.36);
        border: 1px solid rgba(148, 163, 184, 0.18);
        box-shadow: 0 24px 60px rgba(2, 8, 23, 0.45);
        backdrop-filter: blur(16px);
      }
      .preview-tag {
        display: inline-flex;
        margin-bottom: 14px;
        padding: 5px 10px;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.56);
        color: #cbd5e1;
        border: 1px solid rgba(148, 163, 184, 0.18);
        font-size: 12px;
        font-weight: 700;
      }
      .desktop-scene {
        min-height: 780px;
        border-radius: 26px;
        padding: 26px;
        background:
          radial-gradient(circle at top right, rgba(56, 189, 248, 0.1), transparent 22%),
          linear-gradient(180deg, rgba(8, 15, 32, 0.98), rgba(15, 23, 42, 0.9));
        border: 1px solid rgba(148, 163, 184, 0.16);
      }
      .topbar {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: center;
        margin-bottom: 18px;
      }
      .topbar h2 { margin: 0; font-size: 28px; }
      .topbar p { margin: 6px 0 0; color: var(--muted); }
      .actions { display: flex; gap: 10px; flex-wrap: wrap; }
      .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 42px;
        padding: 0 16px;
        border-radius: 14px;
        border: 1px solid rgba(148, 163, 184, 0.2);
        background: rgba(15, 23, 42, 0.58);
        color: #e2e8f0;
        font-weight: 700;
      }
      .btn-primary {
        background: linear-gradient(135deg, #38bdf8, #6366f1);
        border-color: transparent;
        box-shadow: 0 0 28px rgba(56, 189, 248, 0.28);
      }
      .warning {
        margin-bottom: 18px;
        padding: 14px 16px;
        border-radius: 18px;
        background: var(--warning-bg);
        border: 1px solid var(--warning-line);
        color: #fdba74;
        line-height: 1.7;
      }
      .group { margin-top: 22px; }
      .group-title {
        margin: 0 0 12px;
        font-size: 18px;
        font-weight: 800;
        color: #f8fafc;
      }
      .group-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
      }
      .field-card {
        padding: 18px;
        border-radius: 20px;
        background: var(--panel);
        border: 1px solid rgba(148, 163, 184, 0.16);
        backdrop-filter: blur(18px);
      }
      .field-card strong { display: block; margin-bottom: 8px; font-size: 15px; }
      .field-card p { margin: 0 0 10px; color: #cbd5e1; font-size: 13px; line-height: 1.6; }
      .mock-input,
      .mock-select {
        display: flex;
        align-items: center;
        min-height: 42px;
        padding: 0 14px;
        border-radius: 14px;
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: rgba(15, 23, 42, 0.56);
        color: #e2e8f0;
      }
      .stack { display: grid; gap: 8px; }
      .sort-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        border-radius: 14px;
        background: rgba(15, 23, 42, 0.62);
        border: 1px solid rgba(148, 163, 184, 0.18);
      }
      .badge {
        width: 22px;
        height: 22px;
        display: grid;
        place-items: center;
        border-radius: 999px;
        background: rgba(56, 189, 248, 0.16);
        color: #7dd3fc;
        font-size: 12px;
        font-weight: 800;
      }
      .phone {
        width: 100%;
        max-width: 370px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: linear-gradient(180deg, #0f172a, #020617);
        box-shadow: 0 28px 60px rgba(2, 8, 23, 0.55);
      }
      .phone-screen {
        min-height: 800px;
        border-radius: 26px;
        padding: 18px;
        background:
          radial-gradient(circle at top, rgba(56, 189, 248, 0.16), transparent 24%),
          linear-gradient(180deg, rgba(8, 15, 32, 1), rgba(15, 23, 42, 0.98));
      }
      .mobile-shell {
        padding: 18px;
        border-radius: 24px;
        background: rgba(12, 22, 44, 0.68);
        border: 1px solid rgba(148, 163, 184, 0.16);
        backdrop-filter: blur(18px);
      }
      .mobile-title { margin: 0 0 6px; font-size: 24px; }
      .mobile-subtitle { margin: 0 0 14px; color: #cbd5e1; line-height: 1.6; }
      .mobile-actions { display: flex; gap: 8px; margin-bottom: 12px; }
      .mobile-actions .btn { flex: 1; min-height: 40px; padding: 0 10px; font-size: 13px; }
      @media (max-width: 1140px) {
        .page { padding: 24px; }
        .grid { grid-template-columns: 1fr; }
        .group-grid { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body data-style="b" data-page="admin">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style B · 玻璃科技风</span>
        <h1>后台配置页静态预览</h1>
        <p>把管理台变成更有产品展示感的控制中心，同时仍保留配置分组和字段卡片的操作语义。</p>
      </header>

      <div class="grid">
        <section class="preview" data-preview-mode="desktop">
          <span class="preview-tag">桌面端预览</span>
          <div class="desktop-scene">
            <div class="topbar">
              <div>
                <h2>系统配置</h2>
                <p>高对比标题、玻璃容器和发光主按钮，让后台也具备更明显的品牌辨识度。</p>
              </div>
              <div class="actions">
                <button class="btn" type="button">刷新</button>
                <button class="btn btn-primary" type="button">保存配置</button>
              </div>
            </div>

            <div class="warning">⚠️ 修改这些配置可能影响系统稳定性。保存后，部分配置需要重启程序才能生效。</div>

            <section class="group">
              <h3 class="group-title">游客配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>允许游客登录</strong>
                  <p>保持配置语义不变，但用暗色玻璃卡片提升识别度。</p>
                  <div class="mock-select">启用</div>
                </article>
                <article class="field-card">
                  <strong>显示新手帮助</strong>
                  <p>用更明显的卡片边界表现说明信息。</p>
                  <div class="mock-select">启用</div>
                </article>
              </div>
            </section>

            <section class="group">
              <h3 class="group-title">系统配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>会话过期时间 (天)</strong>
                  <p>使用高对比输入框，增强焦点态想象空间。</p>
                  <div class="mock-input">30</div>
                </article>
                <article class="field-card">
                  <strong>密码存储方式</strong>
                  <p>把安全项作为高价值信息突出呈现。</p>
                  <div class="mock-select">BCrypt (自动加盐)</div>
                </article>
                <article class="field-card">
                  <strong>学校账号目录</strong>
                  <p>目录型设置采用统一暗色输入面板。</p>
                  <div class="mock-input">school_accounts</div>
                </article>
                <article class="field-card">
                  <strong>IP 查询顺序</strong>
                  <p>拖拽列表保留层级感与发光焦点语言。</p>
                  <div class="stack">
                    <div class="sort-item"><span class="badge">1</span><span>UapiPro</span></div>
                    <div class="sort-item"><span class="badge">2</span><span>高德地图</span></div>
                    <div class="sort-item"><span class="badge">3</span><span>百度开放数据</span></div>
                  </div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="preview" data-preview-mode="mobile">
          <span class="preview-tag">移动端预览</span>
          <div class="phone">
            <div class="phone-screen">
              <div class="mobile-shell">
                <h2 class="mobile-title">系统配置</h2>
                <p class="mobile-subtitle">移动端保留暗色玻璃气质，但让按钮、警告条和配置卡片更易扫读。</p>
                <div class="mobile-actions">
                  <button class="btn" type="button">刷新</button>
                  <button class="btn btn-primary" type="button">保存配置</button>
                </div>
                <div class="warning">⚠️ 保存后部分配置需要重启程序。</div>
                <section class="group">
                  <h3 class="group-title">游客配置</h3>
                  <div class="field-card">
                    <strong>允许游客登录</strong>
                    <p>快速切换游客访问权限。</p>
                    <div class="mock-select">启用</div>
                  </div>
                </section>
                <section class="group">
                  <h3 class="group-title">系统配置</h3>
                  <div class="field-card">
                    <strong>IP 查询顺序</strong>
                    <p>保留拖拽场景的视觉暗示。</p>
                    <div class="stack">
                      <div class="sort-item"><span class="badge">1</span><span>UapiPro</span></div>
                      <div class="sort-item"><span class="badge">2</span><span>高德地图</span></div>
                    </div>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ui_previews_style_b -v`
Expected: PASS with 2 tests passing.

- [ ] **Step 5: Commit**

```bash
git add ui-previews/style-b-login.html ui-previews/style-b-admin.html tests/test_ui_previews_style_b.py
git commit -m "feat: add glass technology UI previews"
```

---

### Task 3: 建立 Style C（品牌化柔和风）静态稿与校验测试

**Files:**
- Create: `ui-previews/style-c-login.html`
- Create: `ui-previews/style-c-admin.html`
- Create: `tests/test_ui_previews_style_c.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_PREVIEWS = ROOT / "ui-previews"


def read_preview(name: str) -> str:
    return (UI_PREVIEWS / name).read_text(encoding="utf-8")


class TestUiPreviewsStyleC(unittest.TestCase):
    def test_login_preview_has_soft_brand_markers(self):
        html = read_preview("style-c-login.html")
        self.assertIn('data-style="c"', html)
        self.assertIn('data-page="login"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn("Style C · 品牌化柔和风", html)
        self.assertIn("跑步助手", html)
        self.assertIn("立即登录", html)
        self.assertNotIn("scripts/main.new.js", html)
        self.assertNotIn("fetch(", html)

    def test_admin_preview_keeps_config_groups(self):
        html = read_preview("style-c-admin.html")
        self.assertIn('data-style="c"', html)
        self.assertIn('data-page="admin"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn("系统配置", html)
        self.assertIn("保存配置", html)
        self.assertIn("允许游客登录", html)
        self.assertIn("密码存储方式", html)
        self.assertNotIn("scripts/main.new.js", html)
        self.assertNotIn("fetch(", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ui_previews_style_c -v`
Expected: FAIL with `FileNotFoundError` because the two Style C preview files do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```html
<!-- ui-previews/style-c-login.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style C 登录页预览</title>
    <style>
      :root {
        --bg-top: #fff8fb;
        --bg-bottom: #eef6ff;
        --panel: rgba(255, 255, 255, 0.92);
        --line: #eed8e6;
        --text: #3a2941;
        --muted: #7f6b88;
        --primary: #ec4899;
        --secondary: #8b5cf6;
        --soft: #fff0f6;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--text);
        background:
          radial-gradient(circle at top left, rgba(236, 72, 153, 0.14), transparent 28%),
          radial-gradient(circle at bottom right, rgba(59, 130, 246, 0.14), transparent 24%),
          linear-gradient(180deg, var(--bg-top), var(--bg-bottom));
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 860px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(236, 72, 153, 0.1);
        color: #be185d;
        font-size: 12px;
        font-weight: 700;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: var(--muted); line-height: 1.7; }
      .grid {
        max-width: 1320px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: minmax(0, 1.4fr) minmax(320px, 420px);
        gap: 24px;
        align-items: start;
      }
      .preview {
        border-radius: 30px;
        padding: 22px;
        background: rgba(255, 255, 255, 0.62);
        border: 1px solid rgba(238, 216, 230, 0.9);
        box-shadow: 0 24px 50px rgba(125, 93, 129, 0.12);
        backdrop-filter: blur(8px);
      }
      .preview-tag {
        display: inline-flex;
        margin-bottom: 14px;
        padding: 5px 10px;
        border-radius: 999px;
        background: #fff3f8;
        color: #9d174d;
        font-size: 12px;
        font-weight: 700;
      }
      .desktop-scene {
        min-height: 680px;
        border-radius: 28px;
        padding: 42px;
        display: grid;
        grid-template-columns: 1.08fr 420px;
        gap: 36px;
        align-items: center;
        background:
          radial-gradient(circle at top right, rgba(236, 72, 153, 0.08), transparent 26%),
          linear-gradient(180deg, #fff9fc, #f8fbff);
        border: 1px solid #f1dfeb;
      }
      .hero h2 { margin: 16px 0 12px; font-size: 44px; }
      .hero p { margin: 0 0 18px; color: var(--muted); line-height: 1.8; }
      .chips { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 18px; }
      .chip {
        padding: 8px 12px;
        border-radius: 999px;
        background: #fff;
        border: 1px solid #efdce8;
        color: #7c3aed;
        font-size: 13px;
        font-weight: 700;
      }
      .card {
        padding: 26px;
        border-radius: 28px;
        background: var(--panel);
        border: 1px solid #efdce8;
        box-shadow: 0 18px 30px rgba(125, 93, 129, 0.1);
      }
      .logo {
        width: 54px;
        height: 54px;
        display: grid;
        place-items: center;
        border-radius: 20px;
        background: linear-gradient(135deg, #ec4899, #8b5cf6);
        color: #fff;
        font-size: 22px;
        font-weight: 800;
      }
      .card h3 { margin: 16px 0 8px; font-size: 28px; }
      .card p { margin: 0 0 18px; color: var(--muted); }
      .field { margin-bottom: 14px; }
      .field label { display: block; margin-bottom: 8px; color: #5b445f; font-size: 14px; font-weight: 700; }
      .field input {
        width: 100%;
        min-height: 48px;
        padding: 0 14px;
        border-radius: 18px;
        border: 1px solid #efdce8;
        background: #fff;
        color: var(--text);
        outline: none;
      }
      .field input:focus {
        border-color: rgba(236, 72, 153, 0.6);
        box-shadow: 0 0 0 4px rgba(236, 72, 153, 0.14);
      }
      .actions { display: grid; gap: 12px; margin-top: 18px; }
      .btn {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        min-height: 46px;
        border-radius: 18px;
        border: 1px solid #efdce8;
        background: #fff;
        color: var(--text);
        font-size: 15px;
        font-weight: 700;
      }
      .btn-primary {
        background: linear-gradient(135deg, #ec4899, #8b5cf6);
        border-color: transparent;
        color: #fff;
        box-shadow: 0 16px 24px rgba(236, 72, 153, 0.18);
      }
      .helper { margin-top: 12px; text-align: center; font-size: 13px; color: var(--muted); }
      .phone {
        width: 100%;
        max-width: 360px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #3a2941;
        box-shadow: 0 28px 54px rgba(125, 93, 129, 0.24);
      }
      .phone-screen {
        min-height: 720px;
        border-radius: 26px;
        padding: 22px;
        background: linear-gradient(180deg, #fff8fb, #f3f8ff);
      }
      .mobile-shell {
        margin-top: 18px;
        padding: 18px;
        border-radius: 24px;
        background: rgba(255, 255, 255, 0.94);
        border: 1px solid #efdce8;
      }
      .mobile-shell h2 { margin: 12px 0 6px; font-size: 30px; }
      .mobile-shell p { margin: 0; color: var(--muted); line-height: 1.7; }
      @media (max-width: 1120px) {
        .page { padding: 24px; }
        .grid { grid-template-columns: 1fr; }
        .desktop-scene { grid-template-columns: 1fr; padding: 28px; }
      }
    </style>
  </head>
  <body data-style="c" data-page="login">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style C · 品牌化柔和风</span>
        <h1>前台登录页静态预览</h1>
        <p>用更柔和的品牌色、圆润卡片和亲和排版，让前台首页既有产品感又适合长期使用。</p>
      </header>

      <div class="grid">
        <section class="preview" data-preview-mode="desktop">
          <span class="preview-tag">桌面端预览</span>
          <div class="desktop-scene">
            <div class="hero">
              <span class="eyebrow">轻品牌化 · 柔和层次</span>
              <h2>跑步助手</h2>
              <p>通过更圆润的按钮、更柔和的粉紫蓝渐变与更有温度的说明文案，建立统一的品牌型体验。</p>
              <div class="chips">
                <span class="chip">更亲和</span>
                <span class="chip">更圆润</span>
                <span class="chip">更适合长期使用</span>
              </div>
            </div>

            <form class="card">
              <div class="logo">跑</div>
              <h3>欢迎回来</h3>
              <p>继续进入跑步任务、通知中心与个性化配置。</p>
              <div class="field">
                <label for="soft-user">账号 / 手机号</label>
                <input id="soft-user" type="text" value="admin" />
              </div>
              <div class="field">
                <label for="soft-password">密码</label>
                <input id="soft-password" type="password" value="admin" />
              </div>
              <div class="actions">
                <button class="btn btn-primary" type="button">立即登录</button>
                <button class="btn" type="button">游客试用</button>
              </div>
              <div class="helper">更适合前后台统一到同一产品品牌语言下。</div>
            </form>
          </div>
        </section>

        <section class="preview" data-preview-mode="mobile">
          <span class="preview-tag">移动端预览</span>
          <div class="phone">
            <div class="phone-screen">
              <div class="mobile-shell">
                <span class="eyebrow">移动端</span>
                <h2>跑步助手</h2>
                <p>延续柔和品牌风格，保持表单和按钮触达区域清晰、友好。</p>
                <div class="field" style="margin-top: 18px;">
                  <label for="soft-mobile-user">账号 / 手机号</label>
                  <input id="soft-mobile-user" type="text" placeholder="请输入账号" />
                </div>
                <div class="field">
                  <label for="soft-mobile-password">密码</label>
                  <input id="soft-mobile-password" type="password" placeholder="请输入密码" />
                </div>
                <div class="actions">
                  <button class="btn btn-primary" type="button">立即登录</button>
                  <button class="btn" type="button">游客试用</button>
                </div>
                <div class="helper">移动端重点是温和，但仍保持 CTA 明确。</div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </body>
</html>
```

```html
<!-- ui-previews/style-c-admin.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style C 后台配置页预览</title>
    <style>
      :root {
        --bg-top: #fff8fb;
        --bg-bottom: #eef6ff;
        --panel: rgba(255, 255, 255, 0.94);
        --line: #efdce8;
        --text: #3a2941;
        --muted: #7f6b88;
        --primary: #ec4899;
        --secondary: #8b5cf6;
        --warning-bg: #fff1e8;
        --warning-line: #fdba74;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--text);
        background:
          radial-gradient(circle at top left, rgba(236, 72, 153, 0.12), transparent 28%),
          radial-gradient(circle at bottom right, rgba(59, 130, 246, 0.12), transparent 24%),
          linear-gradient(180deg, var(--bg-top), var(--bg-bottom));
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 920px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(236, 72, 153, 0.1);
        color: #be185d;
        font-size: 12px;
        font-weight: 700;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: var(--muted); line-height: 1.7; }
      .grid {
        max-width: 1380px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: minmax(0, 1.4fr) minmax(320px, 430px);
        gap: 24px;
        align-items: start;
      }
      .preview {
        padding: 22px;
        border-radius: 30px;
        background: rgba(255, 255, 255, 0.64);
        border: 1px solid rgba(239, 220, 232, 0.9);
        box-shadow: 0 24px 50px rgba(125, 93, 129, 0.12);
        backdrop-filter: blur(8px);
      }
      .preview-tag {
        display: inline-flex;
        margin-bottom: 14px;
        padding: 5px 10px;
        border-radius: 999px;
        background: #fff3f8;
        color: #9d174d;
        font-size: 12px;
        font-weight: 700;
      }
      .desktop-scene {
        min-height: 780px;
        border-radius: 28px;
        padding: 26px;
        background:
          radial-gradient(circle at top right, rgba(236, 72, 153, 0.08), transparent 24%),
          linear-gradient(180deg, #fff9fc, #f8fbff);
        border: 1px solid #f1dfeb;
      }
      .topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        margin-bottom: 18px;
      }
      .topbar h2 { margin: 0; font-size: 28px; }
      .topbar p { margin: 6px 0 0; color: var(--muted); }
      .actions { display: flex; gap: 10px; flex-wrap: wrap; }
      .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 42px;
        padding: 0 16px;
        border-radius: 16px;
        border: 1px solid #efdce8;
        background: #fff;
        color: var(--text);
        font-weight: 700;
      }
      .btn-primary {
        background: linear-gradient(135deg, #ec4899, #8b5cf6);
        border-color: transparent;
        color: #fff;
        box-shadow: 0 16px 24px rgba(236, 72, 153, 0.18);
      }
      .warning {
        margin-bottom: 18px;
        padding: 14px 16px;
        border-radius: 18px;
        background: var(--warning-bg);
        border: 1px solid var(--warning-line);
        color: #9a3412;
        line-height: 1.7;
      }
      .group { margin-top: 22px; }
      .group-title {
        margin: 0 0 12px;
        font-size: 18px;
        font-weight: 800;
      }
      .group-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
      }
      .field-card {
        padding: 18px;
        border-radius: 22px;
        background: var(--panel);
        border: 1px solid #efdce8;
        box-shadow: 0 12px 20px rgba(125, 93, 129, 0.08);
      }
      .field-card strong { display: block; margin-bottom: 8px; font-size: 15px; }
      .field-card p { margin: 0 0 10px; color: var(--muted); font-size: 13px; line-height: 1.6; }
      .mock-input,
      .mock-select {
        display: flex;
        align-items: center;
        min-height: 42px;
        padding: 0 14px;
        border-radius: 16px;
        border: 1px solid #efdce8;
        background: #fff;
        color: var(--text);
      }
      .stack { display: grid; gap: 8px; }
      .sort-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        border-radius: 16px;
        background: #fff;
        border: 1px solid #efdce8;
      }
      .badge {
        width: 22px;
        height: 22px;
        display: grid;
        place-items: center;
        border-radius: 999px;
        background: #fff0f6;
        color: #be185d;
        font-size: 12px;
        font-weight: 800;
      }
      .phone {
        width: 100%;
        max-width: 370px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #3a2941;
        box-shadow: 0 28px 54px rgba(125, 93, 129, 0.24);
      }
      .phone-screen {
        min-height: 800px;
        border-radius: 26px;
        padding: 18px;
        background: linear-gradient(180deg, #fff8fb, #f3f8ff);
      }
      .mobile-shell {
        padding: 18px;
        border-radius: 24px;
        background: rgba(255, 255, 255, 0.94);
        border: 1px solid #efdce8;
      }
      .mobile-title { margin: 0 0 6px; font-size: 24px; }
      .mobile-subtitle { margin: 0 0 14px; color: var(--muted); line-height: 1.6; }
      .mobile-actions { display: flex; gap: 8px; margin-bottom: 12px; }
      .mobile-actions .btn { flex: 1; min-height: 40px; padding: 0 10px; font-size: 13px; }
      @media (max-width: 1140px) {
        .page { padding: 24px; }
        .grid { grid-template-columns: 1fr; }
        .group-grid { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body data-style="c" data-page="admin">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style C · 品牌化柔和风</span>
        <h1>后台配置页静态预览</h1>
        <p>让后台配置界面保留管理秩序，同时拥有更完整的品牌语言、更温和的颜色和更圆润的卡片体系。</p>
      </header>

      <div class="grid">
        <section class="preview" data-preview-mode="desktop">
          <span class="preview-tag">桌面端预览</span>
          <div class="desktop-scene">
            <div class="topbar">
              <div>
                <h2>系统配置</h2>
                <p>适合把后台也纳入统一产品视觉体系，而不是单独做成冷冰冰的管理工具。</p>
              </div>
              <div class="actions">
                <button class="btn" type="button">刷新</button>
                <button class="btn btn-primary" type="button">保存配置</button>
              </div>
            </div>

            <div class="warning">⚠️ 修改这些配置可能影响系统稳定性。保存后，部分配置需要重启程序才能生效。</div>

            <section class="group">
              <h3 class="group-title">游客配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>允许游客登录</strong>
                  <p>以更友好的说明方式表达系统边界与权限。</p>
                  <div class="mock-select">启用</div>
                </article>
                <article class="field-card">
                  <strong>显示新手帮助</strong>
                  <p>把引导型配置融入同一品牌语义中。</p>
                  <div class="mock-select">启用</div>
                </article>
              </div>
            </section>

            <section class="group">
              <h3 class="group-title">系统配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>会话过期时间 (天)</strong>
                  <p>让数值输入型配置保持轻量又清晰。</p>
                  <div class="mock-input">30</div>
                </article>
                <article class="field-card">
                  <strong>密码存储方式</strong>
                  <p>安全设置仍作为重点信息呈现。</p>
                  <div class="mock-select">BCrypt (自动加盐)</div>
                </article>
                <article class="field-card">
                  <strong>学校账号目录</strong>
                  <p>目录型字段和说明文案保持统一卡片表达。</p>
                  <div class="mock-input">school_accounts</div>
                </article>
                <article class="field-card">
                  <strong>IP 查询顺序</strong>
                  <p>拖拽排序场景用更柔和的层级关系表达。</p>
                  <div class="stack">
                    <div class="sort-item"><span class="badge">1</span><span>UapiPro</span></div>
                    <div class="sort-item"><span class="badge">2</span><span>高德地图</span></div>
                    <div class="sort-item"><span class="badge">3</span><span>百度开放数据</span></div>
                  </div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="preview" data-preview-mode="mobile">
          <span class="preview-tag">移动端预览</span>
          <div class="phone">
            <div class="phone-screen">
              <div class="mobile-shell">
                <h2 class="mobile-title">系统配置</h2>
                <p class="mobile-subtitle">移动端保持温和品牌气质，同时把操作按钮、卡片和说明整理成更顺手的单列信息流。</p>
                <div class="mobile-actions">
                  <button class="btn" type="button">刷新</button>
                  <button class="btn btn-primary" type="button">保存配置</button>
                </div>
                <div class="warning">⚠️ 保存后部分配置需要重启程序。</div>
                <section class="group">
                  <h3 class="group-title">游客配置</h3>
                  <div class="field-card">
                    <strong>允许游客登录</strong>
                    <p>快速理解该项是否开放游客使用。</p>
                    <div class="mock-select">启用</div>
                  </div>
                </section>
                <section class="group">
                  <h3 class="group-title">系统配置</h3>
                  <div class="field-card">
                    <strong>密码存储方式</strong>
                    <p>在移动端仍清楚表达安全项的重要性。</p>
                    <div class="mock-select">BCrypt (自动加盐)</div>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ui_previews_style_c -v`
Expected: PASS with 2 tests passing.

- [ ] **Step 5: Commit**

```bash
git add ui-previews/style-c-login.html ui-previews/style-c-admin.html tests/test_ui_previews_style_c.py
git commit -m "feat: add soft brand UI previews"
```

---

### Task 4: 做最终验证，确保 6 个静态稿都可直接比较

**Files:**
- Test: `tests/test_ui_previews_style_a.py`
- Test: `tests/test_ui_previews_style_b.py`
- Test: `tests/test_ui_previews_style_c.py`
- Verify: `ui-previews/style-a-login.html`
- Verify: `ui-previews/style-a-admin.html`
- Verify: `ui-previews/style-b-login.html`
- Verify: `ui-previews/style-b-admin.html`
- Verify: `ui-previews/style-c-login.html`
- Verify: `ui-previews/style-c-admin.html`

- [ ] **Step 1: Run the full preview test suite**

Run: `python -m unittest tests.test_ui_previews_style_a tests.test_ui_previews_style_b tests.test_ui_previews_style_c -v`
Expected: PASS with 6 tests passing.

- [ ] **Step 2: Serve the preview directory locally**

Run: `python -m http.server 8765 --directory ui-previews`
Expected: terminal prints `Serving HTTP on 0.0.0.0 port 8765` or similar.

- [ ] **Step 3: Open all 6 preview URLs and perform the visual checklist**

Open:
- `http://127.0.0.1:8765/style-a-login.html`
- `http://127.0.0.1:8765/style-a-admin.html`
- `http://127.0.0.1:8765/style-b-login.html`
- `http://127.0.0.1:8765/style-b-admin.html`
- `http://127.0.0.1:8765/style-c-login.html`
- `http://127.0.0.1:8765/style-c-admin.html`

Expected checklist:
1. 每个页面都能同时看到桌面端和移动端预览区。
2. Style A 明显更克制、更专业、更接近现代 SaaS 管理台。
3. Style B 明显更暗色、更玻璃、更强调科技感和发光重点。
4. Style C 明显更柔和、更圆润、更有统一品牌气质。
5. 三套后台页都包含“系统配置 / 刷新 / 保存配置 / 警告条 / 分组标题 / 字段卡片”语义。
6. 三套登录页都包含“跑步助手 / 输入框 / 主按钮 / 次按钮”核心元素。

- [ ] **Step 4: Stop the local server after verification**

Run: `Ctrl+C`
Expected: HTTP server exits cleanly and returns to the shell prompt.

- [ ] **Step 5: Confirm the working tree is clean after the three feature commits**

Run: `git status --short`
Expected: no output.

---

## Self-Review

### Spec coverage

- 3 套完全不同方向：Task 1 / Task 2 / Task 3 分别实现 A、B、C。
- 每套包含前台登录页和后台配置页：每个任务都创建 2 个 HTML 文件。
- 每个文件同时展示桌面端和移动端：三个测试文件与 HTML 代码都强制包含 `data-preview-mode="desktop"` 和 `data-preview-mode="mobile"`。
- 输出到 `ui-previews/`：所有创建文件都位于该目录。
- 不接入现有业务 JS：三个测试文件都校验不包含 `scripts/main.new.js` 和 `fetch(`。
- 后台页映射 `admin-config-form` 语义：三个后台静态稿都覆盖 `系统配置`、`保存配置`、`允许游客登录`、`会话过期时间 (天)`、`密码存储方式`、`IP 查询顺序` 等典型内容。

### Placeholder scan

- 已检查全文，无 `TBD`、`TODO`、`implement later`、`similar to Task N` 之类占位描述。
- 所有代码步骤都提供了具体文件内容或具体测试内容。
- 所有验证步骤都提供了具体命令与预期结果。

### Type consistency

- 所有测试均使用与 HTML 对应的 `data-style`、`data-page`、`data-preview-mode` 标记。
- 三套后台页均统一使用 `系统配置` / `保存配置` / `允许游客登录` 等语义文本，便于测试与人工比对保持一致。
- 三套登录页均统一保留 `跑步助手` 与 `立即登录` 核心文本，避免测试断裂。
