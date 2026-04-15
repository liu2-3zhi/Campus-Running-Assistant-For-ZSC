# Style C 少女向衍生静态预览 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成 Style C 的 3 套少女向衍生静态预览（C1 / C2 / C3），每套包含登录页与后台配置页，并在每个文件中同时展示桌面端、移动端、亮色模式、深色模式，供用户继续筛选方向。

**Architecture:** 继续沿用 `ui-previews/` 下“单文件自包含 HTML”的方式，为 C1 / C2 / C3 各创建登录页和后台页各 1 个文件。每个文件内部使用统一的 2×2 预览布局，明确区分 desktop / mobile 与 light / dark，不接入任何现有业务 JS；同时新增 3 个 `unittest` 文件，分别校验每套预览文件的存在性、主题标记、后台语义和无业务脚本依赖。

**Tech Stack:** HTML5、CSS3、Python `unittest`、本地静态服务器（`python -m http.server`）。

---

## File Structure（实施前锁定）

> 所有命令都从 worktree 根目录执行：`c:/Users/Zelly/Documents/GitHub/python_runing/.worktrees/ui-style-previews`
>
> 本计划刻意不包含 git commit 步骤：当前协作规则要求只有在用户明确要求时才创建提交。

- Create: `ui-previews/style-c1-login.html`
  - Style C1「樱雾奶霜风」登录页；同页展示 desktop-light / desktop-dark / mobile-light / mobile-dark
- Create: `ui-previews/style-c1-admin.html`
  - Style C1「樱雾奶霜风」后台配置页；保留 `admin-config-form` 的分组 + 字段卡片语义
- Create: `ui-previews/style-c2-login.html`
  - Style C2「甜心饰品风」登录页；加入更明显的少女饰品化元素
- Create: `ui-previews/style-c2-admin.html`
  - Style C2「甜心饰品风」后台配置页；在后台语义上承载徽章 / 贴纸 / 星点语言
- Create: `ui-previews/style-c3-login.html`
  - Style C3「夜樱双生风」登录页；突出亮暗双主题的完整世界观
- Create: `ui-previews/style-c3-admin.html`
  - Style C3「夜樱双生风」后台配置页；亮暗双主题都保持强烈产品气质
- Create: `tests/test_ui_previews_style_c1.py`
  - 校验 C1 登录页 / 后台页同时具备 desktop / mobile / light / dark 标记，并保留关键语义
- Create: `tests/test_ui_previews_style_c2.py`
  - 校验 C2 登录页 / 后台页同时具备 desktop / mobile / light / dark 标记，并保留关键语义
- Create: `tests/test_ui_previews_style_c3.py`
  - 校验 C3 登录页 / 后台页同时具备 desktop / mobile / light / dark 标记，并保留关键语义

---

### Task 1: 建立 C1「樱雾奶霜风」静态稿与测试

**Files:**
- Create: `tests/test_ui_previews_style_c1.py`
- Create: `ui-previews/style-c1-login.html`
- Create: `ui-previews/style-c1-admin.html`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_PREVIEWS = ROOT / "ui-previews"


def read_preview(name: str) -> str:
    return (UI_PREVIEWS / name).read_text(encoding="utf-8")


class TestUiPreviewsStyleC1(unittest.TestCase):
    def test_login_preview_has_all_modes(self):
        html = read_preview("style-c1-login.html")
        self.assertIn('data-style="c1"', html)
        self.assertIn('data-page="login"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn('data-theme-preview="light"', html)
        self.assertIn('data-theme-preview="dark"', html)
        self.assertIn("樱雾奶霜风", html)
        self.assertIn("立即登录", html)
        self.assertNotIn("scripts/main.new.js", html)
        self.assertNotIn("fetch(", html)

    def test_admin_preview_keeps_config_semantics(self):
        html = read_preview("style-c1-admin.html")
        self.assertIn('data-style="c1"', html)
        self.assertIn('data-page="admin"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn('data-theme-preview="light"', html)
        self.assertIn('data-theme-preview="dark"', html)
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

Run: `python -m unittest tests.test_ui_previews_style_c1 -v`
Expected: FAIL with `FileNotFoundError` because `ui-previews/style-c1-login.html` and `ui-previews/style-c1-admin.html` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```html
<!-- ui-previews/style-c1-login.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style C1 登录页预览</title>
    <style>
      :root {
        --light-bg: linear-gradient(180deg, #fffafb, #fff2f7 52%, #f9f6ff);
        --light-panel: rgba(255, 255, 255, 0.92);
        --light-line: #f1d8e7;
        --light-text: #5a3e53;
        --light-muted: #8b7286;
        --light-primary: #ef74a8;
        --light-accent: #c084fc;
        --dark-bg: linear-gradient(180deg, #271727, #34203a 54%, #1e1a33);
        --dark-panel: rgba(42, 26, 43, 0.84);
        --dark-line: rgba(255, 199, 229, 0.18);
        --dark-text: #fff1f7;
        --dark-muted: #d4b5cb;
        --dark-primary: #ff89bf;
        --dark-accent: #c7a2ff;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        color: #4b3144;
        background:
          radial-gradient(circle at top left, rgba(255, 183, 213, 0.34), transparent 28%),
          radial-gradient(circle at bottom right, rgba(214, 182, 255, 0.24), transparent 24%),
          #fff8fb;
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 960px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(239, 116, 168, 0.12);
        color: #c03f76;
        font-size: 12px;
        font-weight: 800;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: #8b7286; line-height: 1.7; }
      .preview-grid {
        max-width: 1400px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 20px;
      }
      .preview-card {
        border-radius: 28px;
        padding: 18px;
        border: 1px solid rgba(241, 216, 231, 0.9);
        background: rgba(255, 255, 255, 0.7);
        box-shadow: 0 18px 36px rgba(156, 106, 132, 0.12);
      }
      .preview-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
      }
      .preview-title { font-size: 14px; font-weight: 800; }
      .chip {
        display: inline-flex;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        background: rgba(255, 255, 255, 0.72);
      }
      .scene {
        border-radius: 24px;
        min-height: 560px;
        padding: 26px;
        overflow: hidden;
        position: relative;
      }
      .scene::before {
        content: "";
        position: absolute;
        inset: 0;
        background: radial-gradient(circle at top right, rgba(255,255,255,0.18), transparent 24%);
        pointer-events: none;
      }
      .theme-light .scene {
        background: var(--light-bg);
        color: var(--light-text);
        border: 1px solid #f5dce9;
      }
      .theme-dark .scene {
        background: var(--dark-bg);
        color: var(--dark-text);
        border: 1px solid rgba(255, 199, 229, 0.16);
      }
      .desktop-layout {
        position: relative;
        z-index: 1;
        display: grid;
        grid-template-columns: 1.05fr 360px;
        gap: 28px;
        align-items: center;
      }
      .hero h2 { margin: 14px 0 10px; font-size: 40px; }
      .hero p { margin: 0 0 14px; line-height: 1.8; }
      .badges { display: flex; flex-wrap: wrap; gap: 10px; }
      .badge {
        padding: 8px 12px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 700;
      }
      .theme-light .badge {
        background: #fff7fb;
        color: #c03f76;
        border: 1px solid #f3dce7;
      }
      .theme-dark .badge {
        background: rgba(255, 255, 255, 0.08);
        color: #ffd1e6;
        border: 1px solid rgba(255, 199, 229, 0.18);
      }
      .form-card {
        position: relative;
        z-index: 1;
        padding: 24px;
        border-radius: 26px;
        backdrop-filter: blur(10px);
      }
      .theme-light .form-card {
        background: var(--light-panel);
        border: 1px solid var(--light-line);
        box-shadow: 0 16px 28px rgba(170, 120, 145, 0.12);
      }
      .theme-dark .form-card {
        background: var(--dark-panel);
        border: 1px solid var(--dark-line);
        box-shadow: 0 16px 34px rgba(7, 5, 16, 0.28);
      }
      .logo {
        width: 54px;
        height: 54px;
        display: grid;
        place-items: center;
        border-radius: 18px;
        font-size: 22px;
        font-weight: 800;
        color: #fff;
        background: linear-gradient(135deg, #ef74a8, #c084fc);
      }
      .form-card h3 { margin: 16px 0 8px; font-size: 28px; }
      .form-card p { margin: 0 0 16px; }
      .field { margin-bottom: 12px; }
      .field label { display: block; margin-bottom: 8px; font-size: 13px; font-weight: 700; }
      .field input {
        width: 100%;
        min-height: 46px;
        padding: 0 14px;
        border-radius: 16px;
        outline: none;
      }
      .theme-light .field input {
        border: 1px solid #efd9e7;
        background: #fff;
        color: #5a3e53;
      }
      .theme-dark .field input {
        border: 1px solid rgba(255, 199, 229, 0.18);
        background: rgba(255, 255, 255, 0.06);
        color: #fff1f7;
      }
      .actions { display: grid; gap: 10px; margin-top: 16px; }
      .btn {
        min-height: 44px;
        border-radius: 16px;
        border: none;
        font-size: 14px;
        font-weight: 800;
      }
      .btn-primary {
        color: #fff;
        background: linear-gradient(135deg, #ef74a8, #c084fc);
        box-shadow: 0 14px 24px rgba(239, 116, 168, 0.24);
      }
      .theme-light .btn-secondary {
        background: #fff;
        border: 1px solid #efd9e7;
        color: #6a4860;
      }
      .theme-dark .btn-secondary {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 199, 229, 0.18);
        color: #fff1f7;
      }
      .phone {
        position: relative;
        z-index: 1;
        max-width: 320px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #3f2a3d;
      }
      .phone-screen {
        min-height: 600px;
        border-radius: 26px;
        padding: 18px;
      }
      .theme-light .phone-screen { background: var(--light-bg); }
      .theme-dark .phone-screen { background: var(--dark-bg); }
      .mobile-card {
        margin-top: 18px;
        padding: 18px;
        border-radius: 22px;
      }
      .theme-light .mobile-card {
        background: rgba(255,255,255,0.94);
        border: 1px solid #efd9e7;
      }
      .theme-dark .mobile-card {
        background: rgba(42, 26, 43, 0.88);
        border: 1px solid rgba(255, 199, 229, 0.16);
      }
      .mobile-card h3 { margin: 12px 0 8px; font-size: 24px; }
      .mobile-card p { margin: 0 0 14px; line-height: 1.7; }
      @media (max-width: 1180px) {
        .page { padding: 24px; }
        .preview-grid { grid-template-columns: 1fr; }
        .desktop-layout { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body data-style="c1" data-page="login">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style C1 · 樱雾奶霜风</span>
        <h1>登录页二轮衍生静态预览</h1>
        <p>在原始 Style C 的柔和品牌基底上，继续往奶油粉樱、雾面柔光和甜美梦幻的少女产品界面推进。</p>
      </header>

      <div class="preview-grid">
        <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 亮色模式</span>
            <span class="chip">奶霜樱粉</span>
          </div>
          <div class="scene">
            <div class="desktop-layout">
              <div class="hero">
                <span class="chip">轻甜品牌化</span>
                <h2>跑步助手</h2>
                <p>把登录入口做成像樱花奶霜礼盒一样轻盈柔和，让品牌感和少女气质都更自然地成立。</p>
                <div class="badges">
                  <span class="badge">樱雾背景</span>
                  <span class="badge">奶油卡片</span>
                  <span class="badge">轻珠光按钮</span>
                </div>
              </div>
              <form class="form-card">
                <div class="logo">樱</div>
                <h3>欢迎回来</h3>
                <p>继续进入跑步任务、通知中心与个性化配置。</p>
                <div class="field">
                  <label for="c1-light-desktop-user">账号 / 手机号</label>
                  <input id="c1-light-desktop-user" type="text" value="admin" />
                </div>
                <div class="field">
                  <label for="c1-light-desktop-password">密码</label>
                  <input id="c1-light-desktop-password" type="password" value="admin" />
                </div>
                <div class="actions">
                  <button class="btn btn-primary" type="button">立即登录</button>
                  <button class="btn btn-secondary" type="button">游客试用</button>
                </div>
              </form>
            </div>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 深色模式</span>
            <span class="chip">夜樱梦幻版</span>
          </div>
          <div class="scene">
            <div class="desktop-layout">
              <div class="hero">
                <span class="chip">夜樱雾紫</span>
                <h2>跑步助手</h2>
                <p>用低对比莓紫与暗樱粉发光层，构建柔和但成立的深色少女主题，而不是简单反色。</p>
                <div class="badges">
                  <span class="badge">柔光深底</span>
                  <span class="badge">月雾边框</span>
                  <span class="badge">长看不累</span>
                </div>
              </div>
              <form class="form-card">
                <div class="logo">夜</div>
                <h3>欢迎回来</h3>
                <p>夜晚樱花般安静、柔和，但 CTA 和输入区仍然非常清楚。</p>
                <div class="field">
                  <label for="c1-dark-desktop-user">账号 / 手机号</label>
                  <input id="c1-dark-desktop-user" type="text" value="admin" />
                </div>
                <div class="field">
                  <label for="c1-dark-desktop-password">密码</label>
                  <input id="c1-dark-desktop-password" type="password" value="admin" />
                </div>
                <div class="actions">
                  <button class="btn btn-primary" type="button">立即登录</button>
                  <button class="btn btn-secondary" type="button">游客试用</button>
                </div>
              </form>
            </div>
          </div>
        </section>

        <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">移动端 · 亮色模式</span>
            <span class="chip">奶白粉樱</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-card">
                  <span class="chip">移动端</span>
                  <h3>跑步助手</h3>
                  <p>把樱雾奶霜气质压缩进更轻盈、触达更明确的单列登录结构。</p>
                  <div class="field">
                    <label for="c1-light-mobile-user">账号 / 手机号</label>
                    <input id="c1-light-mobile-user" type="text" placeholder="请输入账号" />
                  </div>
                  <div class="field">
                    <label for="c1-light-mobile-password">密码</label>
                    <input id="c1-light-mobile-password" type="password" placeholder="请输入密码" />
                  </div>
                  <div class="actions">
                    <button class="btn btn-primary" type="button">立即登录</button>
                    <button class="btn btn-secondary" type="button">游客试用</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">移动端 · 深色模式</span>
            <span class="chip">夜樱雾粉</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-card">
                  <span class="chip">移动端</span>
                  <h3>跑步助手</h3>
                  <p>深色模式维持梦幻夜樱气质，同时保证输入、按钮与焦点区域很清楚。</p>
                  <div class="field">
                    <label for="c1-dark-mobile-user">账号 / 手机号</label>
                    <input id="c1-dark-mobile-user" type="text" placeholder="请输入账号" />
                  </div>
                  <div class="field">
                    <label for="c1-dark-mobile-password">密码</label>
                    <input id="c1-dark-mobile-password" type="password" placeholder="请输入密码" />
                  </div>
                  <div class="actions">
                    <button class="btn btn-primary" type="button">立即登录</button>
                    <button class="btn btn-secondary" type="button">游客试用</button>
                  </div>
                </div>
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
<!-- ui-previews/style-c1-admin.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style C1 后台配置页预览</title>
    <style>
      :root {
        --light-bg: linear-gradient(180deg, #fffafb, #fff2f7 52%, #f9f6ff);
        --light-panel: rgba(255,255,255,0.94);
        --light-line: #f1d8e7;
        --light-text: #583e50;
        --light-muted: #8a7084;
        --light-primary: #ef74a8;
        --dark-bg: linear-gradient(180deg, #251825, #33203c 56%, #1e1a34);
        --dark-panel: rgba(43, 26, 45, 0.84);
        --dark-line: rgba(255, 199, 229, 0.16);
        --dark-text: #fff1f7;
        --dark-muted: #d8bdd0;
        --warning-light: #fff3f6;
        --warning-dark: rgba(255, 143, 191, 0.12);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(255, 190, 216, 0.32), transparent 26%),
          radial-gradient(circle at bottom right, rgba(207, 182, 255, 0.22), transparent 24%),
          #fff8fb;
        color: #583e50;
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 960px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(239, 116, 168, 0.12);
        color: #c03f76;
        font-size: 12px;
        font-weight: 800;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: #8a7084; line-height: 1.7; }
      .preview-grid {
        max-width: 1400px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 20px;
      }
      .preview-card {
        border-radius: 28px;
        padding: 18px;
        border: 1px solid rgba(241, 216, 231, 0.9);
        background: rgba(255, 255, 255, 0.7);
        box-shadow: 0 18px 36px rgba(156, 106, 132, 0.12);
      }
      .preview-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
      }
      .preview-title { font-size: 14px; font-weight: 800; }
      .chip {
        display: inline-flex;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        background: rgba(255,255,255,0.72);
      }
      .scene {
        min-height: 620px;
        border-radius: 24px;
        padding: 22px;
      }
      .theme-light .scene {
        background: var(--light-bg);
        color: var(--light-text);
        border: 1px solid #f5dce9;
      }
      .theme-dark .scene {
        background: var(--dark-bg);
        color: var(--dark-text);
        border: 1px solid rgba(255, 199, 229, 0.14);
      }
      .topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 14px;
        margin-bottom: 14px;
      }
      .topbar h2 { margin: 0; font-size: 26px; }
      .topbar p { margin: 6px 0 0; }
      .actions { display: flex; gap: 8px; flex-wrap: wrap; }
      .btn {
        min-height: 40px;
        padding: 0 14px;
        border-radius: 14px;
        font-size: 13px;
        font-weight: 800;
      }
      .theme-light .btn {
        border: 1px solid #efd9e7;
        background: #fff;
        color: #694a5f;
      }
      .theme-dark .btn {
        border: 1px solid rgba(255, 199, 229, 0.18);
        background: rgba(255,255,255,0.06);
        color: #fff1f7;
      }
      .btn-primary {
        color: #fff !important;
        border-color: transparent !important;
        background: linear-gradient(135deg, #ef74a8, #c084fc) !important;
      }
      .warning {
        margin-bottom: 14px;
        padding: 12px 14px;
        border-radius: 16px;
        line-height: 1.7;
      }
      .theme-light .warning {
        background: var(--warning-light);
        border: 1px solid #f6ccde;
      }
      .theme-dark .warning {
        background: var(--warning-dark);
        border: 1px solid rgba(255, 171, 210, 0.18);
      }
      .group { margin-top: 18px; }
      .group-title { margin: 0 0 10px; font-size: 17px; font-weight: 800; }
      .group-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
      }
      .field-card {
        padding: 16px;
        border-radius: 20px;
      }
      .theme-light .field-card {
        background: var(--light-panel);
        border: 1px solid var(--light-line);
      }
      .theme-dark .field-card {
        background: var(--dark-panel);
        border: 1px solid var(--dark-line);
      }
      .field-card strong { display: block; margin-bottom: 8px; }
      .field-card p { margin: 0 0 10px; line-height: 1.6; }
      .mock-input,
      .mock-select {
        min-height: 40px;
        display: flex;
        align-items: center;
        padding: 0 12px;
        border-radius: 14px;
      }
      .theme-light .mock-input,
      .theme-light .mock-select {
        border: 1px solid #efd9e7;
        background: #fff;
      }
      .theme-dark .mock-input,
      .theme-dark .mock-select {
        border: 1px solid rgba(255,199,229,0.18);
        background: rgba(255,255,255,0.06);
      }
      .phone {
        max-width: 320px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #3f2a3d;
      }
      .phone-screen {
        min-height: 620px;
        border-radius: 26px;
        padding: 18px;
      }
      .theme-light .phone-screen { background: var(--light-bg); }
      .theme-dark .phone-screen { background: var(--dark-bg); }
      .mobile-shell {
        padding: 18px;
        border-radius: 22px;
      }
      .theme-light .mobile-shell {
        background: rgba(255,255,255,0.94);
        border: 1px solid #efd9e7;
      }
      .theme-dark .mobile-shell {
        background: rgba(43, 26, 45, 0.88);
        border: 1px solid rgba(255,199,229,0.16);
      }
      .mobile-shell h3 { margin: 0 0 8px; font-size: 24px; }
      .mobile-shell p { margin: 0 0 12px; line-height: 1.7; }
      @media (max-width: 1180px) {
        .page { padding: 24px; }
        .preview-grid { grid-template-columns: 1fr; }
        .group-grid { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body data-style="c1" data-page="admin">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style C1 · 樱雾奶霜风</span>
        <h1>后台配置页二轮衍生静态预览</h1>
        <p>让后台也拥有奶白粉樱、柔光边框和甜点盒卡片感，但仍然保持系统配置界面的明确结构。</p>
      </header>

      <div class="preview-grid">
        <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 亮色模式</span>
            <span class="chip">奶霜后台</span>
          </div>
          <div class="scene">
            <div class="topbar">
              <div>
                <h2>系统配置</h2>
                <p>像轻甜礼盒一样柔和，但仍保留后台操作秩序。</p>
              </div>
              <div class="actions">
                <button class="btn" type="button">刷新</button>
                <button class="btn btn-primary" type="button">保存配置</button>
              </div>
            </div>
            <div class="warning">⚠️ 保存后部分配置需要重启程序才能生效，请确认后再提交。</div>
            <section class="group">
              <h3 class="group-title">游客配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>允许游客登录</strong>
                  <p>用更柔和的标签和容器表达开放策略。</p>
                  <div class="mock-select">启用</div>
                </article>
                <article class="field-card">
                  <strong>显示新手帮助</strong>
                  <p>让后台提示信息也保持温和、亲和的品牌语气。</p>
                  <div class="mock-select">启用</div>
                </article>
              </div>
            </section>
            <section class="group">
              <h3 class="group-title">系统配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>密码存储方式</strong>
                  <p>安全项继续清楚突出，但不再使用冷硬表达。</p>
                  <div class="mock-select">BCrypt (自动加盐)</div>
                </article>
                <article class="field-card">
                  <strong>学校账号目录</strong>
                  <p>目录型字段与整体卡片体系统一。</p>
                  <div class="mock-input">school_accounts</div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 深色模式</span>
            <span class="chip">夜樱后台</span>
          </div>
          <div class="scene">
            <div class="topbar">
              <div>
                <h2>系统配置</h2>
                <p>夜樱雾紫氛围下，卡片、按钮和提示区仍然要一眼看懂。</p>
              </div>
              <div class="actions">
                <button class="btn" type="button">刷新</button>
                <button class="btn btn-primary" type="button">保存配置</button>
              </div>
            </div>
            <div class="warning">⚠️ 夜间模式下依然清楚显示风险提示，不牺牲后台可读性。</div>
            <section class="group">
              <h3 class="group-title">游客配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>允许游客登录</strong>
                  <p>保留柔和发光边线，让状态更容易扫读。</p>
                  <div class="mock-select">启用</div>
                </article>
                <article class="field-card">
                  <strong>显示新手帮助</strong>
                  <p>在夜樱主题下仍然像完整产品后台，而不是普通暗黑页。</p>
                  <div class="mock-select">启用</div>
                </article>
              </div>
            </section>
            <section class="group">
              <h3 class="group-title">系统配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>密码存储方式</strong>
                  <p>深色配置项需要足够清楚，不被装饰感淹没。</p>
                  <div class="mock-select">BCrypt (自动加盐)</div>
                </article>
                <article class="field-card">
                  <strong>学校账号目录</strong>
                  <p>统一卡片、输入框与按钮的夜樱材质语言。</p>
                  <div class="mock-input">school_accounts</div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">移动端 · 亮色模式</span>
            <span class="chip">轻甜单列</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-shell">
                  <h3>系统配置</h3>
                  <p>移动端同样保持奶白粉樱层次，让配置页更亲和。</p>
                  <div class="actions" style="margin-bottom:12px;">
                    <button class="btn" type="button">刷新</button>
                    <button class="btn btn-primary" type="button">保存配置</button>
                  </div>
                  <div class="warning">⚠️ 保存后部分配置需要重启程序。</div>
                  <section class="group">
                    <h4 class="group-title">游客配置</h4>
                    <article class="field-card">
                      <strong>允许游客登录</strong>
                      <p>快速理解游客访问是否开放。</p>
                      <div class="mock-select">启用</div>
                    </article>
                  </section>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">移动端 · 深色模式</span>
            <span class="chip">夜樱单列</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-shell">
                  <h3>系统配置</h3>
                  <p>保持夜樱梦幻感，同时让移动端后台字段依然顺手可扫。</p>
                  <div class="actions" style="margin-bottom:12px;">
                    <button class="btn" type="button">刷新</button>
                    <button class="btn btn-primary" type="button">保存配置</button>
                  </div>
                  <div class="warning">⚠️ 保存后部分配置需要重启程序。</div>
                  <section class="group">
                    <h4 class="group-title">系统配置</h4>
                    <article class="field-card">
                      <strong>密码存储方式</strong>
                      <p>深色后台下仍保证安全字段足够清楚。</p>
                      <div class="mock-select">BCrypt (自动加盐)</div>
                    </article>
                  </section>
                </div>
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

Run: `python -m unittest tests.test_ui_previews_style_c1 -v`
Expected: PASS with 2 tests and 0 failures.

---

### Task 2: 建立 C2「甜心饰品风」静态稿与测试

**Files:**
- Create: `tests/test_ui_previews_style_c2.py`
- Create: `ui-previews/style-c2-login.html`
- Create: `ui-previews/style-c2-admin.html`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_PREVIEWS = ROOT / "ui-previews"


def read_preview(name: str) -> str:
    return (UI_PREVIEWS / name).read_text(encoding="utf-8")


class TestUiPreviewsStyleC2(unittest.TestCase):
    def test_login_preview_has_all_modes(self):
        html = read_preview("style-c2-login.html")
        self.assertIn('data-style="c2"', html)
        self.assertIn('data-page="login"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn('data-theme-preview="light"', html)
        self.assertIn('data-theme-preview="dark"', html)
        self.assertIn("甜心饰品风", html)
        self.assertIn("立即登录", html)
        self.assertNotIn("scripts/main.new.js", html)
        self.assertNotIn("fetch(", html)

    def test_admin_preview_keeps_config_semantics(self):
        html = read_preview("style-c2-admin.html")
        self.assertIn('data-style="c2"', html)
        self.assertIn('data-page="admin"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn('data-theme-preview="light"', html)
        self.assertIn('data-theme-preview="dark"', html)
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

Run: `python -m unittest tests.test_ui_previews_style_c2 -v`
Expected: FAIL with `FileNotFoundError` because `ui-previews/style-c2-login.html` and `ui-previews/style-c2-admin.html` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```html
<!-- ui-previews/style-c2-login.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style C2 登录页预览</title>
    <style>
      :root {
        --light-bg: linear-gradient(180deg, #fff6fb, #ffeaf6 48%, #f8efff);
        --light-panel: rgba(255,255,255,0.94);
        --light-line: #f3cfe5;
        --light-text: #5d3654;
        --light-muted: #8c6b83;
        --dark-bg: linear-gradient(180deg, #231429, #311c38 50%, #1a1731);
        --dark-panel: rgba(44, 24, 49, 0.88);
        --dark-line: rgba(255, 183, 222, 0.2);
        --dark-text: #fff0f8;
        --dark-muted: #d8b6ce;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(255, 174, 210, 0.32), transparent 24%),
          radial-gradient(circle at bottom right, rgba(198, 171, 255, 0.24), transparent 22%),
          #fff8fb;
        color: #5d3654;
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 960px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.72);
        color: #cf3f80;
        font-size: 12px;
        font-weight: 800;
        border: 1px solid #f7d2e7;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: #8c6b83; line-height: 1.7; }
      .preview-grid {
        max-width: 1400px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 20px;
      }
      .preview-card {
        border-radius: 28px;
        padding: 18px;
        border: 1px solid rgba(243, 207, 229, 0.9);
        background: rgba(255,255,255,0.72);
        box-shadow: 0 18px 36px rgba(161, 102, 142, 0.14);
      }
      .preview-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
      }
      .preview-title { font-size: 14px; font-weight: 800; }
      .chip {
        display: inline-flex;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        background: rgba(255,255,255,0.76);
        border: 1px solid rgba(255,255,255,0.82);
      }
      .scene {
        min-height: 560px;
        border-radius: 24px;
        padding: 26px;
        position: relative;
        overflow: hidden;
      }
      .theme-light .scene {
        background: var(--light-bg);
        color: var(--light-text);
        border: 1px solid #f6d8e8;
      }
      .theme-dark .scene {
        background: var(--dark-bg);
        color: var(--dark-text);
        border: 1px solid rgba(255,183,222,0.16);
      }
      .sparkles {
        position: absolute;
        top: 20px;
        right: 20px;
        font-size: 14px;
        letter-spacing: 6px;
      }
      .desktop-layout {
        position: relative;
        z-index: 1;
        display: grid;
        grid-template-columns: 1.02fr 360px;
        gap: 28px;
        align-items: center;
      }
      .hero h2 { margin: 14px 0 10px; font-size: 40px; }
      .hero p { margin: 0 0 16px; line-height: 1.8; }
      .ornaments { display: flex; flex-wrap: wrap; gap: 10px; }
      .ornament {
        padding: 8px 12px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 700;
      }
      .theme-light .ornament {
        background: #fff;
        border: 1px solid #f4d3e6;
        color: #cc4a85;
      }
      .theme-dark .ornament {
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,183,222,0.18);
        color: #ffd0e7;
      }
      .form-card {
        position: relative;
        z-index: 1;
        padding: 24px;
        border-radius: 26px;
      }
      .theme-light .form-card {
        background: var(--light-panel);
        border: 1px solid var(--light-line);
      }
      .theme-dark .form-card {
        background: var(--dark-panel);
        border: 1px solid var(--dark-line);
      }
      .ribbon {
        display: inline-flex;
        margin-bottom: 12px;
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 800;
      }
      .theme-light .ribbon { background: #fff0f7; color: #cf3f80; }
      .theme-dark .ribbon { background: rgba(255,255,255,0.08); color: #ffd0e7; }
      .form-card h3 { margin: 0 0 8px; font-size: 28px; }
      .form-card p { margin: 0 0 16px; }
      .field { margin-bottom: 12px; }
      .field label { display: block; margin-bottom: 8px; font-size: 13px; font-weight: 700; }
      .field input {
        width: 100%;
        min-height: 46px;
        padding: 0 14px;
        border-radius: 18px;
        outline: none;
      }
      .theme-light .field input {
        background: #fff;
        border: 1px solid #f0d2e5;
        color: #5d3654;
      }
      .theme-dark .field input {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,183,222,0.18);
        color: #fff0f8;
      }
      .actions { display: grid; gap: 10px; margin-top: 16px; }
      .btn {
        min-height: 44px;
        border-radius: 18px;
        border: none;
        font-size: 14px;
        font-weight: 800;
      }
      .btn-primary {
        color: #fff;
        background: linear-gradient(135deg, #ff79b7, #ba86ff);
        box-shadow: 0 14px 24px rgba(255, 121, 183, 0.22);
      }
      .theme-light .btn-secondary {
        background: #fff;
        border: 1px dashed #efc6df;
        color: #764764;
      }
      .theme-dark .btn-secondary {
        background: rgba(255,255,255,0.06);
        border: 1px dashed rgba(255,183,222,0.24);
        color: #fff0f8;
      }
      .phone {
        position: relative;
        z-index: 1;
        max-width: 320px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #3d233f;
      }
      .phone-screen {
        min-height: 600px;
        border-radius: 26px;
        padding: 18px;
      }
      .theme-light .phone-screen { background: var(--light-bg); }
      .theme-dark .phone-screen { background: var(--dark-bg); }
      .mobile-card {
        margin-top: 18px;
        padding: 18px;
        border-radius: 22px;
      }
      .theme-light .mobile-card {
        background: rgba(255,255,255,0.94);
        border: 1px solid #f0d2e5;
      }
      .theme-dark .mobile-card {
        background: rgba(44,24,49,0.88);
        border: 1px solid rgba(255,183,222,0.18);
      }
      .mobile-card h3 { margin: 12px 0 8px; font-size: 24px; }
      .mobile-card p { margin: 0 0 14px; line-height: 1.7; }
      @media (max-width: 1180px) {
        .page { padding: 24px; }
        .preview-grid { grid-template-columns: 1fr; }
        .desktop-layout { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body data-style="c2" data-page="login">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style C2 · 甜心饰品风</span>
        <h1>登录页二轮衍生静态预览</h1>
        <p>把 Style C 继续往更明显的二次元饰品化方向推进，让蝴蝶结、星点、徽章与贴纸感进入交互容器。</p>
      </header>

      <div class="preview-grid">
        <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 亮色模式</span>
            <span class="chip">🎀 饰品贴纸版</span>
          </div>
          <div class="scene">
            <div class="sparkles">✦ ✦ ✦</div>
            <div class="desktop-layout">
              <div class="hero">
                <span class="chip">甜心收藏夹</span>
                <h2>跑步助手</h2>
                <p>让按钮像糖果饰品，输入框像贴纸卡槽，把登录入口做成更有“收藏感”的少女产品界面。</p>
                <div class="ornaments">
                  <span class="ornament">🎀 蝴蝶结</span>
                  <span class="ornament">✦ 星点高光</span>
                  <span class="ornament">♡ 贴纸边框</span>
                </div>
              </div>
              <form class="form-card">
                <span class="ribbon">徽章登录</span>
                <h3>欢迎回来</h3>
                <p>继续进入跑步任务、消息中心与个性化配置。</p>
                <div class="field">
                  <label for="c2-light-desktop-user">账号 / 手机号</label>
                  <input id="c2-light-desktop-user" type="text" value="admin" />
                </div>
                <div class="field">
                  <label for="c2-light-desktop-password">密码</label>
                  <input id="c2-light-desktop-password" type="password" value="admin" />
                </div>
                <div class="actions">
                  <button class="btn btn-primary" type="button">立即登录</button>
                  <button class="btn btn-secondary" type="button">游客试用</button>
                </div>
              </form>
            </div>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 深色模式</span>
            <span class="chip">🌙 莓夜饰品版</span>
          </div>
          <div class="scene">
            <div class="sparkles">✦ ✦ ✦</div>
            <div class="desktop-layout">
              <div class="hero">
                <span class="chip">莓夜收藏夹</span>
                <h2>跑步助手</h2>
                <p>在深色模式中继续保留贴纸感和小装饰高光，让二次元辨识度进一步拉高。</p>
                <div class="ornaments">
                  <span class="ornament">🌟 夜空莓蓝</span>
                  <span class="ornament">🎀 暗色蝴蝶结</span>
                  <span class="ornament">♡ 亮边贴纸</span>
                </div>
              </div>
              <form class="form-card">
                <span class="ribbon">夜樱登录</span>
                <h3>欢迎回来</h3>
                <p>深色版重点保留符号感，但不能影响输入、按钮和登录路径识别。</p>
                <div class="field">
                  <label for="c2-dark-desktop-user">账号 / 手机号</label>
                  <input id="c2-dark-desktop-user" type="text" value="admin" />
                </div>
                <div class="field">
                  <label for="c2-dark-desktop-password">密码</label>
                  <input id="c2-dark-desktop-password" type="password" value="admin" />
                </div>
                <div class="actions">
                  <button class="btn btn-primary" type="button">立即登录</button>
                  <button class="btn btn-secondary" type="button">游客试用</button>
                </div>
              </form>
            </div>
          </div>
        </section>

        <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">移动端 · 亮色模式</span>
            <span class="chip">⭐ 贴纸控件</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-card">
                  <span class="ribbon">移动端</span>
                  <h3>跑步助手</h3>
                  <p>在更小的屏幕里保留轻装饰语法，但让 CTA 和输入框依然第一眼可见。</p>
                  <div class="field">
                    <label for="c2-light-mobile-user">账号 / 手机号</label>
                    <input id="c2-light-mobile-user" type="text" placeholder="请输入账号" />
                  </div>
                  <div class="field">
                    <label for="c2-light-mobile-password">密码</label>
                    <input id="c2-light-mobile-password" type="password" placeholder="请输入密码" />
                  </div>
                  <div class="actions">
                    <button class="btn btn-primary" type="button">立即登录</button>
                    <button class="btn btn-secondary" type="button">游客试用</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">移动端 · 深色模式</span>
            <span class="chip">🎀 夜莓星点</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-card">
                  <span class="ribbon">移动端</span>
                  <h3>跑步助手</h3>
                  <p>用莓紫夜空和星点对比维持高辨识度，但不把页面做成杂乱活动页。</p>
                  <div class="field">
                    <label for="c2-dark-mobile-user">账号 / 手机号</label>
                    <input id="c2-dark-mobile-user" type="text" placeholder="请输入账号" />
                  </div>
                  <div class="field">
                    <label for="c2-dark-mobile-password">密码</label>
                    <input id="c2-dark-mobile-password" type="password" placeholder="请输入密码" />
                  </div>
                  <div class="actions">
                    <button class="btn btn-primary" type="button">立即登录</button>
                    <button class="btn btn-secondary" type="button">游客试用</button>
                  </div>
                </div>
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
<!-- ui-previews/style-c2-admin.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style C2 后台配置页预览</title>
    <style>
      :root {
        --light-bg: linear-gradient(180deg, #fff6fb, #ffeaf6 48%, #f8efff);
        --light-panel: rgba(255,255,255,0.94);
        --light-line: #f3cfe5;
        --light-text: #5d3654;
        --light-muted: #8c6b83;
        --dark-bg: linear-gradient(180deg, #231429, #311c38 50%, #1a1731);
        --dark-panel: rgba(44, 24, 49, 0.88);
        --dark-line: rgba(255, 183, 222, 0.2);
        --dark-text: #fff0f8;
        --dark-muted: #d8b6ce;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(255,174,210,0.32), transparent 24%),
          radial-gradient(circle at bottom right, rgba(198,171,255,0.24), transparent 22%),
          #fff8fb;
        color: #5d3654;
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 960px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(255,255,255,0.78);
        color: #cf3f80;
        border: 1px solid #f7d2e7;
        font-size: 12px;
        font-weight: 800;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: #8c6b83; line-height: 1.7; }
      .preview-grid {
        max-width: 1400px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 20px;
      }
      .preview-card {
        border-radius: 28px;
        padding: 18px;
        border: 1px solid rgba(243,207,229,0.9);
        background: rgba(255,255,255,0.72);
        box-shadow: 0 18px 36px rgba(161,102,142,0.14);
      }
      .preview-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
      }
      .preview-title { font-size: 14px; font-weight: 800; }
      .chip {
        display: inline-flex;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        background: rgba(255,255,255,0.76);
      }
      .scene {
        min-height: 620px;
        border-radius: 24px;
        padding: 22px;
      }
      .theme-light .scene {
        background: var(--light-bg);
        color: var(--light-text);
        border: 1px solid #f6d8e8;
      }
      .theme-dark .scene {
        background: var(--dark-bg);
        color: var(--dark-text);
        border: 1px solid rgba(255,183,222,0.16);
      }
      .topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 14px;
        margin-bottom: 14px;
      }
      .topbar h2 { margin: 0; font-size: 26px; }
      .topbar p { margin: 6px 0 0; }
      .actions { display: flex; gap: 8px; flex-wrap: wrap; }
      .btn {
        min-height: 40px;
        padding: 0 14px;
        border-radius: 16px;
        font-size: 13px;
        font-weight: 800;
      }
      .theme-light .btn {
        border: 1px dashed #efc6df;
        background: #fff;
        color: #764764;
      }
      .theme-dark .btn {
        border: 1px dashed rgba(255,183,222,0.24);
        background: rgba(255,255,255,0.06);
        color: #fff0f8;
      }
      .btn-primary {
        border-style: solid !important;
        border-color: transparent !important;
        color: #fff !important;
        background: linear-gradient(135deg, #ff79b7, #ba86ff) !important;
      }
      .warning {
        margin-bottom: 14px;
        padding: 12px 14px;
        border-radius: 16px;
        line-height: 1.7;
      }
      .theme-light .warning {
        background: rgba(255,240,248,0.88);
        border: 1px solid #f7d2e7;
      }
      .theme-dark .warning {
        background: rgba(255,121,183,0.10);
        border: 1px solid rgba(255,183,222,0.18);
      }
      .group { margin-top: 18px; }
      .group-title { margin: 0 0 10px; font-size: 17px; font-weight: 800; }
      .group-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
      }
      .field-card {
        padding: 16px;
        border-radius: 22px;
        position: relative;
      }
      .field-card::before {
        content: "✦";
        position: absolute;
        top: 14px;
        right: 14px;
        font-size: 12px;
        opacity: 0.7;
      }
      .theme-light .field-card {
        background: var(--light-panel);
        border: 1px solid var(--light-line);
      }
      .theme-dark .field-card {
        background: var(--dark-panel);
        border: 1px solid var(--dark-line);
      }
      .field-card strong { display: block; margin-bottom: 8px; }
      .field-card p { margin: 0 0 10px; line-height: 1.6; }
      .mock-input,
      .mock-select {
        min-height: 40px;
        display: flex;
        align-items: center;
        padding: 0 12px;
        border-radius: 16px;
      }
      .theme-light .mock-input,
      .theme-light .mock-select {
        border: 1px solid #efcfe1;
        background: #fff;
      }
      .theme-dark .mock-input,
      .theme-dark .mock-select {
        border: 1px solid rgba(255,183,222,0.18);
        background: rgba(255,255,255,0.06);
      }
      .stack { display: grid; gap: 8px; }
      .sort-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 12px;
        border-radius: 14px;
      }
      .theme-light .sort-item {
        background: #fff;
        border: 1px solid #efcfe1;
      }
      .theme-dark .sort-item {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,183,222,0.18);
      }
      .badge {
        width: 22px;
        height: 22px;
        display: grid;
        place-items: center;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 800;
      }
      .theme-light .badge { background: #fff0f7; color: #cf3f80; }
      .theme-dark .badge { background: rgba(255,255,255,0.08); color: #ffd0e7; }
      .phone {
        max-width: 320px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #3d233f;
      }
      .phone-screen {
        min-height: 620px;
        border-radius: 26px;
        padding: 18px;
      }
      .theme-light .phone-screen { background: var(--light-bg); }
      .theme-dark .phone-screen { background: var(--dark-bg); }
      .mobile-shell {
        padding: 18px;
        border-radius: 22px;
      }
      .theme-light .mobile-shell {
        background: rgba(255,255,255,0.94);
        border: 1px solid #efcfe1;
      }
      .theme-dark .mobile-shell {
        background: rgba(44,24,49,0.88);
        border: 1px solid rgba(255,183,222,0.18);
      }
      .mobile-shell h3 { margin: 0 0 8px; font-size: 24px; }
      .mobile-shell p { margin: 0 0 12px; line-height: 1.7; }
      @media (max-width: 1180px) {
        .page { padding: 24px; }
        .preview-grid { grid-template-columns: 1fr; }
        .group-grid { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body data-style="c2" data-page="admin">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style C2 · 甜心饰品风</span>
        <h1>后台配置页二轮衍生静态预览</h1>
        <p>让后台配置页也拥有明显的徽章、贴纸、蝴蝶结式界面语法，但仍然能快速完成系统设置操作。</p>
      </header>

      <div class="preview-grid">
        <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 亮色模式</span>
            <span class="chip">🎀 收藏式后台</span>
          </div>
          <div class="scene">
            <div class="topbar">
              <div>
                <h2>系统配置</h2>
                <p>像收藏柜一样组织配置组，后台也拥有更明显的少女风记忆点。</p>
              </div>
              <div class="actions">
                <button class="btn" type="button">刷新</button>
                <button class="btn btn-primary" type="button">保存配置</button>
              </div>
            </div>
            <div class="warning">⚠️ 保存后部分配置需要重启程序，饰品感增强但配置语义不变。</div>
            <section class="group">
              <h3 class="group-title">游客配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>允许游客登录</strong>
                  <p>用更有贴纸感的状态卡片表达开关项。</p>
                  <div class="mock-select">启用</div>
                </article>
                <article class="field-card">
                  <strong>显示新手帮助</strong>
                  <p>让说明字段也像收藏徽章的一部分。</p>
                  <div class="mock-select">启用</div>
                </article>
              </div>
            </section>
            <section class="group">
              <h3 class="group-title">系统配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>IP 查询顺序</strong>
                  <p>排序列表也使用甜心贴纸式容器。</p>
                  <div class="stack">
                    <div class="sort-item"><span class="badge">1</span><span>UapiPro</span></div>
                    <div class="sort-item"><span class="badge">2</span><span>高德地图</span></div>
                    <div class="sort-item"><span class="badge">3</span><span>百度开放数据</span></div>
                  </div>
                </article>
                <article class="field-card">
                  <strong>学校账号目录</strong>
                  <p>目录型字段同样保留圆润贴纸边框。</p>
                  <div class="mock-input">school_accounts</div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 深色模式</span>
            <span class="chip">🌙 莓夜收藏柜</span>
          </div>
          <div class="scene">
            <div class="topbar">
              <div>
                <h2>系统配置</h2>
                <p>在莓夜背景里继续保留徽章和贴纸反差，但后台内容仍然足够清楚。</p>
              </div>
              <div class="actions">
                <button class="btn" type="button">刷新</button>
                <button class="btn btn-primary" type="button">保存配置</button>
              </div>
            </div>
            <div class="warning">⚠️ 深色模式下的装饰元素要收敛在边角，不遮挡核心配置路径。</div>
            <section class="group">
              <h3 class="group-title">游客配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>允许游客登录</strong>
                  <p>借助亮边徽章和弱发光强调开关状态。</p>
                  <div class="mock-select">启用</div>
                </article>
                <article class="field-card">
                  <strong>显示新手帮助</strong>
                  <p>在更深的底色里维持卡片层级感。</p>
                  <div class="mock-select">启用</div>
                </article>
              </div>
            </section>
            <section class="group">
              <h3 class="group-title">系统配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>IP 查询顺序</strong>
                  <p>保持排序结构，同时让贴纸视觉在深色中依然成立。</p>
                  <div class="stack">
                    <div class="sort-item"><span class="badge">1</span><span>UapiPro</span></div>
                    <div class="sort-item"><span class="badge">2</span><span>高德地图</span></div>
                    <div class="sort-item"><span class="badge">3</span><span>百度开放数据</span></div>
                  </div>
                </article>
                <article class="field-card">
                  <strong>学校账号目录</strong>
                  <p>保证输入容器可读，避免只剩装饰而失去功能感。</p>
                  <div class="mock-input">school_accounts</div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">移动端 · 亮色模式</span>
            <span class="chip">⭐ 移动徽章栏</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-shell">
                  <h3>系统配置</h3>
                  <p>移动端保留甜心装饰语法，但按钮与列表仍然保持清楚节奏。</p>
                  <div class="actions" style="margin-bottom:12px;">
                    <button class="btn" type="button">刷新</button>
                    <button class="btn btn-primary" type="button">保存配置</button>
                  </div>
                  <section class="group">
                    <h4 class="group-title">游客配置</h4>
                    <article class="field-card">
                      <strong>允许游客登录</strong>
                      <p>快速切换游客访问策略。</p>
                      <div class="mock-select">启用</div>
                    </article>
                  </section>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">移动端 · 深色模式</span>
            <span class="chip">🎀 夜莓卡片</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-shell">
                  <h3>系统配置</h3>
                  <p>把深色饰品风压缩到单列后台里，但不牺牲列表扫读性。</p>
                  <div class="actions" style="margin-bottom:12px;">
                    <button class="btn" type="button">刷新</button>
                    <button class="btn btn-primary" type="button">保存配置</button>
                  </div>
                  <section class="group">
                    <h4 class="group-title">系统配置</h4>
                    <article class="field-card">
                      <strong>IP 查询顺序</strong>
                      <p>深色下仍然保持排序提示感。</p>
                      <div class="stack">
                        <div class="sort-item"><span class="badge">1</span><span>UapiPro</span></div>
                        <div class="sort-item"><span class="badge">2</span><span>高德地图</span></div>
                      </div>
                    </article>
                  </section>
                </div>
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

Run: `python -m unittest tests.test_ui_previews_style_c2 -v`
Expected: PASS with 2 tests and 0 failures.

---

### Task 3: 建立 C3「夜樱双生风」静态稿与测试

**Files:**
- Create: `tests/test_ui_previews_style_c3.py`
- Create: `ui-previews/style-c3-login.html`
- Create: `ui-previews/style-c3-admin.html`

- [ ] **Step 1: Write the failing test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_PREVIEWS = ROOT / "ui-previews"


def read_preview(name: str) -> str:
    return (UI_PREVIEWS / name).read_text(encoding="utf-8")


class TestUiPreviewsStyleC3(unittest.TestCase):
    def test_login_preview_has_all_modes(self):
        html = read_preview("style-c3-login.html")
        self.assertIn('data-style="c3"', html)
        self.assertIn('data-page="login"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn('data-theme-preview="light"', html)
        self.assertIn('data-theme-preview="dark"', html)
        self.assertIn("夜樱双生风", html)
        self.assertIn("立即登录", html)
        self.assertNotIn("scripts/main.new.js", html)
        self.assertNotIn("fetch(", html)

    def test_admin_preview_keeps_config_semantics(self):
        html = read_preview("style-c3-admin.html")
        self.assertIn('data-style="c3"', html)
        self.assertIn('data-page="admin"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn('data-theme-preview="light"', html)
        self.assertIn('data-theme-preview="dark"', html)
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

Run: `python -m unittest tests.test_ui_previews_style_c3 -v`
Expected: FAIL with `FileNotFoundError` because `ui-previews/style-c3-login.html` and `ui-previews/style-c3-admin.html` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```html
<!-- ui-previews/style-c3-login.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style C3 登录页预览</title>
    <style>
      :root {
        --light-bg: linear-gradient(180deg, #fff9fc, #fff1f8 50%, #f6f0ff);
        --light-panel: rgba(255,255,255,0.94);
        --light-line: #f1d7e9;
        --light-text: #5f3954;
        --light-muted: #896f84;
        --dark-bg: linear-gradient(180deg, #160f25, #241738 50%, #120f23);
        --dark-panel: rgba(32, 22, 46, 0.88);
        --dark-line: rgba(255, 168, 214, 0.18);
        --dark-text: #fff2fa;
        --dark-muted: #d6bfd8;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(255, 186, 219, 0.3), transparent 24%),
          radial-gradient(circle at bottom right, rgba(193, 167, 255, 0.24), transparent 24%),
          #fff8fb;
        color: #5f3954;
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 980px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(255,255,255,0.76);
        color: #c73f7f;
        font-size: 12px;
        font-weight: 800;
        border: 1px solid #f3d5e7;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: #896f84; line-height: 1.7; }
      .preview-grid {
        max-width: 1400px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 20px;
      }
      .preview-card {
        border-radius: 28px;
        padding: 18px;
        border: 1px solid rgba(241,215,233,0.9);
        background: rgba(255,255,255,0.72);
        box-shadow: 0 18px 36px rgba(146, 96, 133, 0.14);
      }
      .preview-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
      }
      .preview-title { font-size: 14px; font-weight: 800; }
      .chip {
        display: inline-flex;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        background: rgba(255,255,255,0.78);
      }
      .scene {
        min-height: 560px;
        border-radius: 24px;
        padding: 26px;
        position: relative;
        overflow: hidden;
      }
      .theme-light .scene {
        background: var(--light-bg);
        color: var(--light-text);
        border: 1px solid #f5dce9;
      }
      .theme-dark .scene {
        background: var(--dark-bg);
        color: var(--dark-text);
        border: 1px solid rgba(255,168,214,0.16);
      }
      .theme-light .scene::after,
      .theme-dark .scene::after {
        content: "";
        position: absolute;
        inset: auto auto 0 0;
        width: 180px;
        height: 180px;
        background: radial-gradient(circle, rgba(255,255,255,0.14), transparent 70%);
      }
      .desktop-layout {
        position: relative;
        z-index: 1;
        display: grid;
        grid-template-columns: 1.04fr 360px;
        gap: 28px;
        align-items: center;
      }
      .hero h2 { margin: 14px 0 10px; font-size: 40px; }
      .hero p { margin: 0 0 16px; line-height: 1.8; }
      .duo { display: flex; flex-wrap: wrap; gap: 10px; }
      .duo span {
        padding: 8px 12px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 700;
      }
      .theme-light .duo span {
        background: #fff;
        border: 1px solid #f1d7e9;
        color: #c73f7f;
      }
      .theme-dark .duo span {
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,168,214,0.18);
        color: #ffd0e6;
      }
      .form-card {
        position: relative;
        z-index: 1;
        padding: 24px;
        border-radius: 26px;
      }
      .theme-light .form-card {
        background: var(--light-panel);
        border: 1px solid var(--light-line);
      }
      .theme-dark .form-card {
        background: var(--dark-panel);
        border: 1px solid var(--dark-line);
      }
      .logo {
        width: 56px;
        height: 56px;
        display: grid;
        place-items: center;
        border-radius: 18px;
        font-size: 22px;
        font-weight: 800;
        color: #fff;
        background: linear-gradient(135deg, #ff7fb7, #9b7fff);
      }
      .form-card h3 { margin: 16px 0 8px; font-size: 28px; }
      .form-card p { margin: 0 0 16px; }
      .field { margin-bottom: 12px; }
      .field label { display: block; margin-bottom: 8px; font-size: 13px; font-weight: 700; }
      .field input {
        width: 100%;
        min-height: 46px;
        padding: 0 14px;
        border-radius: 16px;
        outline: none;
      }
      .theme-light .field input {
        background: #fff;
        border: 1px solid #f0d4e5;
        color: #5f3954;
      }
      .theme-dark .field input {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,168,214,0.18);
        color: #fff2fa;
      }
      .actions { display: grid; gap: 10px; margin-top: 16px; }
      .btn {
        min-height: 44px;
        border-radius: 16px;
        border: none;
        font-size: 14px;
        font-weight: 800;
      }
      .btn-primary {
        color: #fff;
        background: linear-gradient(135deg, #ff7fb7, #9b7fff);
        box-shadow: 0 14px 24px rgba(255, 127, 183, 0.24);
      }
      .theme-light .btn-secondary {
        background: #fff;
        border: 1px solid #f0d4e5;
        color: #724a66;
      }
      .theme-dark .btn-secondary {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,168,214,0.18);
        color: #fff2fa;
      }
      .phone {
        position: relative;
        z-index: 1;
        max-width: 320px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #311f40;
      }
      .phone-screen {
        min-height: 600px;
        border-radius: 26px;
        padding: 18px;
      }
      .theme-light .phone-screen { background: var(--light-bg); }
      .theme-dark .phone-screen { background: var(--dark-bg); }
      .mobile-card {
        margin-top: 18px;
        padding: 18px;
        border-radius: 22px;
      }
      .theme-light .mobile-card {
        background: rgba(255,255,255,0.94);
        border: 1px solid #f0d4e5;
      }
      .theme-dark .mobile-card {
        background: rgba(32,22,46,0.88);
        border: 1px solid rgba(255,168,214,0.18);
      }
      .mobile-card h3 { margin: 12px 0 8px; font-size: 24px; }
      .mobile-card p { margin: 0 0 14px; line-height: 1.7; }
      @media (max-width: 1180px) {
        .page { padding: 24px; }
        .preview-grid { grid-template-columns: 1fr; }
        .desktop-layout { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body data-style="c3" data-page="login">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style C3 · 夜樱双生风</span>
        <h1>登录页二轮衍生静态预览</h1>
        <p>把 Style C 拆成一套真正的双生系统：亮色是白昼樱梦，深色是夜樱梦幻版，两者都完整成立。</p>
      </header>

      <div class="preview-grid">
        <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 亮色模式</span>
            <span class="chip">白昼樱梦</span>
          </div>
          <div class="scene">
            <div class="desktop-layout">
              <div class="hero">
                <span class="chip">梦境入口</span>
                <h2>跑步助手</h2>
                <p>亮色模式强调通透、呼吸感和梦境入口气质，让登录页像柔和的白昼樱梦界面。</p>
                <div class="duo">
                  <span>轻盈品牌感</span>
                  <span>白昼花雾</span>
                  <span>通透排版</span>
                </div>
              </div>
              <form class="form-card">
                <div class="logo">昼</div>
                <h3>欢迎回来</h3>
                <p>继续进入跑步任务、通知中心与个性化配置。</p>
                <div class="field">
                  <label for="c3-light-desktop-user">账号 / 手机号</label>
                  <input id="c3-light-desktop-user" type="text" value="admin" />
                </div>
                <div class="field">
                  <label for="c3-light-desktop-password">密码</label>
                  <input id="c3-light-desktop-password" type="password" value="admin" />
                </div>
                <div class="actions">
                  <button class="btn btn-primary" type="button">立即登录</button>
                  <button class="btn btn-secondary" type="button">游客试用</button>
                </div>
              </form>
            </div>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 深色模式</span>
            <span class="chip">夜樱梦幻版</span>
          </div>
          <div class="scene">
            <div class="desktop-layout">
              <div class="hero">
                <span class="chip">月夜花雾</span>
                <h2>跑步助手</h2>
                <p>深色模式作为完整世界观存在：更安静、更梦幻，但按钮、输入框与卡片依旧非常清楚。</p>
                <div class="duo">
                  <span>夜樱辉光</span>
                  <span>月光边框</span>
                  <span>双生主题</span>
                </div>
              </div>
              <form class="form-card">
                <div class="logo">夜</div>
                <h3>欢迎回来</h3>
                <p>不只是暗色版本，而是一整套夜樱产品界面的起点。</p>
                <div class="field">
                  <label for="c3-dark-desktop-user">账号 / 手机号</label>
                  <input id="c3-dark-desktop-user" type="text" value="admin" />
                </div>
                <div class="field">
                  <label for="c3-dark-desktop-password">密码</label>
                  <input id="c3-dark-desktop-password" type="password" value="admin" />
                </div>
                <div class="actions">
                  <button class="btn btn-primary" type="button">立即登录</button>
                  <button class="btn btn-secondary" type="button">游客试用</button>
                </div>
              </form>
            </div>
          </div>
        </section>

        <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">移动端 · 亮色模式</span>
            <span class="chip">白昼单列</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-card">
                  <span class="chip">移动端</span>
                  <h3>跑步助手</h3>
                  <p>移动端亮色版延续通透和呼吸感，让甜美产品气质更完整。</p>
                  <div class="field">
                    <label for="c3-light-mobile-user">账号 / 手机号</label>
                    <input id="c3-light-mobile-user" type="text" placeholder="请输入账号" />
                  </div>
                  <div class="field">
                    <label for="c3-light-mobile-password">密码</label>
                    <input id="c3-light-mobile-password" type="password" placeholder="请输入密码" />
                  </div>
                  <div class="actions">
                    <button class="btn btn-primary" type="button">立即登录</button>
                    <button class="btn btn-secondary" type="button">游客试用</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">移动端 · 深色模式</span>
            <span class="chip">夜樱单列</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-card">
                  <span class="chip">移动端</span>
                  <h3>跑步助手</h3>
                  <p>深色移动端既保留夜樱氛围，也维持清楚的表单、CTA 与输入层级。</p>
                  <div class="field">
                    <label for="c3-dark-mobile-user">账号 / 手机号</label>
                    <input id="c3-dark-mobile-user" type="text" placeholder="请输入账号" />
                  </div>
                  <div class="field">
                    <label for="c3-dark-mobile-password">密码</label>
                    <input id="c3-dark-mobile-password" type="password" placeholder="请输入密码" />
                  </div>
                  <div class="actions">
                    <button class="btn btn-primary" type="button">立即登录</button>
                    <button class="btn btn-secondary" type="button">游客试用</button>
                  </div>
                </div>
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
<!-- ui-previews/style-c3-admin.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style C3 后台配置页预览</title>
    <style>
      :root {
        --light-bg: linear-gradient(180deg, #fff9fc, #fff1f8 50%, #f6f0ff);
        --light-panel: rgba(255,255,255,0.94);
        --light-line: #f1d7e9;
        --light-text: #5f3954;
        --light-muted: #896f84;
        --dark-bg: linear-gradient(180deg, #160f25, #241738 50%, #120f23);
        --dark-panel: rgba(32, 22, 46, 0.88);
        --dark-line: rgba(255,168,214,0.18);
        --dark-text: #fff2fa;
        --dark-muted: #d6bfd8;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(255,186,219,0.3), transparent 24%),
          radial-gradient(circle at bottom right, rgba(193,167,255,0.24), transparent 24%),
          #fff8fb;
        color: #5f3954;
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 980px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(255,255,255,0.76);
        color: #c73f7f;
        border: 1px solid #f3d5e7;
        font-size: 12px;
        font-weight: 800;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; color: #896f84; line-height: 1.7; }
      .preview-grid {
        max-width: 1400px;
        margin: 0 auto;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 20px;
      }
      .preview-card {
        border-radius: 28px;
        padding: 18px;
        border: 1px solid rgba(241,215,233,0.9);
        background: rgba(255,255,255,0.72);
        box-shadow: 0 18px 36px rgba(146,96,133,0.14);
      }
      .preview-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
      }
      .preview-title { font-size: 14px; font-weight: 800; }
      .chip {
        display: inline-flex;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        background: rgba(255,255,255,0.78);
      }
      .scene {
        min-height: 620px;
        border-radius: 24px;
        padding: 22px;
        position: relative;
        overflow: hidden;
      }
      .theme-light .scene {
        background: var(--light-bg);
        color: var(--light-text);
        border: 1px solid #f5dce9;
      }
      .theme-dark .scene {
        background: var(--dark-bg);
        color: var(--dark-text);
        border: 1px solid rgba(255,168,214,0.16);
      }
      .theme-light .scene::after,
      .theme-dark .scene::after {
        content: "";
        position: absolute;
        inset: auto 0 0 auto;
        width: 180px;
        height: 180px;
        background: radial-gradient(circle, rgba(255,255,255,0.12), transparent 70%);
      }
      .topbar {
        position: relative;
        z-index: 1;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 14px;
        margin-bottom: 14px;
      }
      .topbar h2 { margin: 0; font-size: 26px; }
      .topbar p { margin: 6px 0 0; }
      .actions { display: flex; gap: 8px; flex-wrap: wrap; }
      .btn {
        min-height: 40px;
        padding: 0 14px;
        border-radius: 14px;
        font-size: 13px;
        font-weight: 800;
      }
      .theme-light .btn {
        border: 1px solid #f0d4e5;
        background: #fff;
        color: #724a66;
      }
      .theme-dark .btn {
        border: 1px solid rgba(255,168,214,0.18);
        background: rgba(255,255,255,0.06);
        color: #fff2fa;
      }
      .btn-primary {
        border-color: transparent !important;
        color: #fff !important;
        background: linear-gradient(135deg, #ff7fb7, #9b7fff) !important;
      }
      .warning {
        position: relative;
        z-index: 1;
        margin-bottom: 14px;
        padding: 12px 14px;
        border-radius: 16px;
        line-height: 1.7;
      }
      .theme-light .warning {
        background: rgba(255,244,249,0.9);
        border: 1px solid #f4d5e8;
      }
      .theme-dark .warning {
        background: rgba(255,127,183,0.10);
        border: 1px solid rgba(255,168,214,0.18);
      }
      .group { position: relative; z-index: 1; margin-top: 18px; }
      .group-title { margin: 0 0 10px; font-size: 17px; font-weight: 800; }
      .group-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
      }
      .field-card {
        padding: 16px;
        border-radius: 20px;
      }
      .theme-light .field-card {
        background: var(--light-panel);
        border: 1px solid var(--light-line);
      }
      .theme-dark .field-card {
        background: var(--dark-panel);
        border: 1px solid var(--dark-line);
      }
      .field-card strong { display: block; margin-bottom: 8px; }
      .field-card p { margin: 0 0 10px; line-height: 1.6; }
      .mock-input,
      .mock-select {
        min-height: 40px;
        display: flex;
        align-items: center;
        padding: 0 12px;
        border-radius: 14px;
      }
      .theme-light .mock-input,
      .theme-light .mock-select {
        border: 1px solid #f0d4e5;
        background: #fff;
      }
      .theme-dark .mock-input,
      .theme-dark .mock-select {
        border: 1px solid rgba(255,168,214,0.18);
        background: rgba(255,255,255,0.06);
      }
      .phone {
        max-width: 320px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #311f40;
      }
      .phone-screen {
        min-height: 620px;
        border-radius: 26px;
        padding: 18px;
      }
      .theme-light .phone-screen { background: var(--light-bg); }
      .theme-dark .phone-screen { background: var(--dark-bg); }
      .mobile-shell {
        padding: 18px;
        border-radius: 22px;
      }
      .theme-light .mobile-shell {
        background: rgba(255,255,255,0.94);
        border: 1px solid #f0d4e5;
      }
      .theme-dark .mobile-shell {
        background: rgba(32,22,46,0.88);
        border: 1px solid rgba(255,168,214,0.18);
      }
      .mobile-shell h3 { margin: 0 0 8px; font-size: 24px; }
      .mobile-shell p { margin: 0 0 12px; line-height: 1.7; }
      @media (max-width: 1180px) {
        .page { padding: 24px; }
        .preview-grid { grid-template-columns: 1fr; }
        .group-grid { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body data-style="c3" data-page="admin">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style C3 · 夜樱双生风</span>
        <h1>后台配置页二轮衍生静态预览</h1>
        <p>把后台也纳入双生主题：亮色是白昼樱梦管理台，深色则是完整的夜樱梦幻后台。</p>
      </header>

      <div class="preview-grid">
        <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 亮色模式</span>
            <span class="chip">白昼樱梦后台</span>
          </div>
          <div class="scene">
            <div class="topbar">
              <div>
                <h2>系统配置</h2>
                <p>亮色版强调通透层次和梦境入口感，让后台也更像完整产品界面。</p>
              </div>
              <div class="actions">
                <button class="btn" type="button">刷新</button>
                <button class="btn btn-primary" type="button">保存配置</button>
              </div>
            </div>
            <div class="warning">⚠️ 保存后部分配置需要重启程序。亮色版需要温柔，但提示信息仍要明显。</div>
            <section class="group">
              <h3 class="group-title">游客配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>允许游客登录</strong>
                  <p>保持浅色通透感，同时让开关语义清楚。</p>
                  <div class="mock-select">启用</div>
                </article>
                <article class="field-card">
                  <strong>显示新手帮助</strong>
                  <p>让引导信息也融入更完整的品牌语境。</p>
                  <div class="mock-select">启用</div>
                </article>
              </div>
            </section>
            <section class="group">
              <h3 class="group-title">系统配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>会话过期时间 (天)</strong>
                  <p>数值型字段使用更轻盈但清楚的输入壳体。</p>
                  <div class="mock-input">30</div>
                </article>
                <article class="field-card">
                  <strong>密码存储方式</strong>
                  <p>安全项继续清楚凸显，不被主题氛围弱化。</p>
                  <div class="mock-select">BCrypt (自动加盐)</div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 深色模式</span>
            <span class="chip">夜樱梦幻后台</span>
          </div>
          <div class="scene">
            <div class="topbar">
              <div>
                <h2>系统配置</h2>
                <p>深色版是完整夜樱世界观，不是普通暗色管理台的简单换皮。</p>
              </div>
              <div class="actions">
                <button class="btn" type="button">刷新</button>
                <button class="btn btn-primary" type="button">保存配置</button>
              </div>
            </div>
            <div class="warning">⚠️ 深色模式下仍需保证字段、警告和按钮层级第一眼可读。</div>
            <section class="group">
              <h3 class="group-title">游客配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>允许游客登录</strong>
                  <p>借助夜樱高光边线强调配置状态。</p>
                  <div class="mock-select">启用</div>
                </article>
                <article class="field-card">
                  <strong>显示新手帮助</strong>
                  <p>保持梦幻感，但不牺牲管理界面的清楚信息节奏。</p>
                  <div class="mock-select">启用</div>
                </article>
              </div>
            </section>
            <section class="group">
              <h3 class="group-title">系统配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>会话过期时间 (天)</strong>
                  <p>深色数字输入仍要保持高对比与清楚边界。</p>
                  <div class="mock-input">30</div>
                </article>
                <article class="field-card">
                  <strong>密码存储方式</strong>
                  <p>让夜樱风格和后台可用性同时成立。</p>
                  <div class="mock-select">BCrypt (自动加盐)</div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">移动端 · 亮色模式</span>
            <span class="chip">白昼单列后台</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-shell">
                  <h3>系统配置</h3>
                  <p>移动端亮色版重点保留呼吸感和清楚层级。</p>
                  <div class="actions" style="margin-bottom:12px;">
                    <button class="btn" type="button">刷新</button>
                    <button class="btn btn-primary" type="button">保存配置</button>
                  </div>
                  <section class="group">
                    <h4 class="group-title">游客配置</h4>
                    <article class="field-card">
                      <strong>允许游客登录</strong>
                      <p>快速理解游客访问策略。</p>
                      <div class="mock-select">启用</div>
                    </article>
                  </section>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="mobile" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">移动端 · 深色模式</span>
            <span class="chip">夜樱单列后台</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-shell">
                  <h3>系统配置</h3>
                  <p>夜樱移动端继续保留完整世界观，同时保持配置单列顺手可扫。</p>
                  <div class="actions" style="margin-bottom:12px;">
                    <button class="btn" type="button">刷新</button>
                    <button class="btn btn-primary" type="button">保存配置</button>
                  </div>
                  <section class="group">
                    <h4 class="group-title">系统配置</h4>
                    <article class="field-card">
                      <strong>会话过期时间 (天)</strong>
                      <p>在深色单列中仍能一眼识别数值型字段。</p>
                      <div class="mock-input">30</div>
                    </article>
                  </section>
                </div>
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

Run: `python -m unittest tests.test_ui_previews_style_c3 -v`
Expected: PASS with 2 tests and 0 failures.

---

### Task 4: 统一验证 3 套衍生预览并准备给用户挑选

**Files:**
- Test: `tests/test_ui_previews_style_c1.py`
- Test: `tests/test_ui_previews_style_c2.py`
- Test: `tests/test_ui_previews_style_c3.py`
- Review: `ui-previews/style-c1-login.html`
- Review: `ui-previews/style-c1-admin.html`
- Review: `ui-previews/style-c2-login.html`
- Review: `ui-previews/style-c2-admin.html`
- Review: `ui-previews/style-c3-login.html`
- Review: `ui-previews/style-c3-admin.html`

- [ ] **Step 1: Run the new derivative preview tests together**

Run: `python -m unittest tests.test_ui_previews_style_c1 tests.test_ui_previews_style_c2 tests.test_ui_previews_style_c3 -v`
Expected: PASS with 6 tests and 0 failures.

- [ ] **Step 2: Run the full static preview test set to avoid regressions**

Run: `python -m unittest tests.test_ui_previews_style_a tests.test_ui_previews_style_b tests.test_ui_previews_style_c tests.test_ui_previews_style_c1 tests.test_ui_previews_style_c2 tests.test_ui_previews_style_c3 -v`
Expected: PASS with 12 tests and 0 failures.

- [ ] **Step 3: Start a local static server for manual review**

Run: `cd "c:/Users/Zelly/Documents/GitHub/python_runing/.worktrees/ui-style-previews/ui-previews" && python -m http.server 8765 --bind 127.0.0.1`
Expected: server starts successfully and keeps running.

- [ ] **Step 4: Manually inspect all six new pages**

Open and verify:
- `http://127.0.0.1:8765/style-c1-login.html`
- `http://127.0.0.1:8765/style-c1-admin.html`
- `http://127.0.0.1:8765/style-c2-login.html`
- `http://127.0.0.1:8765/style-c2-admin.html`
- `http://127.0.0.1:8765/style-c3-login.html`
- `http://127.0.0.1:8765/style-c3-admin.html`

Manual checklist:
- 每个文件都能清楚看到 desktop / mobile 两种设备预览
- 每个文件都能清楚看到 light / dark 两种主题预览
- C1 明显更奶霜、柔和、耐看
- C2 明显更饰品化、二次元符号更强
- C3 明显更强调亮暗双主题的世界观差异
- 后台页都还能直接映射到 `admin-config-form` 的分组 + 字段卡片结构
- 页面源码内都没有 `scripts/main.new.js` 和 `fetch(`

---

## Self-review

- **Spec coverage:** 已覆盖 6 个 HTML、新增 3 个测试文件、desktop / mobile、light / dark、login / admin、与 `admin-config-form` 的后台语义映射，以及最终本地预览检查。
- **Placeholder scan:** 无 `TODO` / `TBD` / “类似上一步” 之类占位描述；每个代码步骤都给出完整文件内容。
- **Type consistency:** 测试文件和 HTML 内部统一使用 `data-style`、`data-page`、`data-preview-mode`、`data-theme-preview` 四组标记，后续验证命令与这些标记保持一致。
