# Style C2 Night Sakura Refine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Style C2 新增一组“夜樱轻奢”精修静态预览：登录页与后台配置页各 1 个 HTML，并用 1 个 `unittest` 文件覆盖亮色/深色、桌面端/移动端、关键语义与无业务脚本约束。

**Architecture:** 继续沿用当前 `ui-previews/` 的纯静态预览模式：每个页面都是自包含 HTML、内联 CSS、无业务 JS，并在单页中用 2×2 布局同时展示 `desktop/mobile + light/dark`。测试沿用现有 `tests/test_ui_previews_style_c2.py` 的结构，先为 login 写失败测试再补页面，再扩展 admin 测试并补后台页面，最后跑完整 Style C 预览回归并做一次本地视觉验收。

**Tech Stack:** Python `unittest`、纯静态 HTML、内联 CSS、`python -m http.server`

---

## File Structure

**Create:**
- `tests/test_ui_previews_style_c2_refine.py` — 只负责校验 `c2-refine` 的 login/admin 预览是否存在、是否包含 2×2 模式标记、关键语义文案与无业务脚本约束
- `ui-previews/style-c2-refine-login.html` — 夜樱轻奢登录页静态预览，单文件展示 desktop/mobile + light/dark
- `ui-previews/style-c2-refine-admin.html` — 夜樱轻奢后台配置页静态预览，单文件展示 desktop/mobile + light/dark，并保留真实配置语义

**Reference only (do not modify):**
- `ui-previews/style-c2-login.html` — 当前 C2 登录页结构与 2×2 布局参考
- `ui-previews/style-c2-admin.html` — 当前 C2 后台结构与字段语义参考
- `tests/test_ui_previews_style_c2.py` — 现有 C2 测试写法参考

**Execution note:**
- 所有命令都在 worktree 根目录 `c:/Users/Zelly/Documents/GitHub/python_runing/.worktrees/ui-style-previews` 运行
- 针对单文件测试，统一使用 `python -m unittest discover -s tests -p "..." -v`

### Task 1: Create the refined login preview

**Files:**
- Create: `tests/test_ui_previews_style_c2_refine.py`
- Create: `ui-previews/style-c2-refine-login.html`
- Reference: `ui-previews/style-c2-login.html`

- [ ] **Step 1: Write the failing login test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_PREVIEWS = ROOT / "ui-previews"


def read_preview(name: str) -> str:
    return (UI_PREVIEWS / name).read_text(encoding="utf-8")


class TestUiPreviewsStyleC2Refine(unittest.TestCase):
    def test_login_preview_has_night_sakura_all_modes(self):
        html = read_preview("style-c2-refine-login.html")
        self.assertIn('data-style="c2-refine"', html)
        self.assertIn('data-page="login"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn('data-theme-preview="light"', html)
        self.assertIn('data-theme-preview="dark"', html)
        self.assertIn("夜樱轻奢", html)
        self.assertIn("晨樱珠雾", html)
        self.assertIn("夜樱月下", html)
        self.assertIn("立即登录", html)
        self.assertNotIn("scripts/main.new.js", html)
        self.assertNotIn("fetch(", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the login test to verify it fails**

Run:

```bash
python -m unittest discover -s tests -p "test_ui_previews_style_c2_refine.py" -v
```

Expected:
- `test_login_preview_has_night_sakura_all_modes` FAIL
- Failure reason is `FileNotFoundError` for `ui-previews/style-c2-refine-login.html`

- [ ] **Step 3: Write the minimal login preview implementation**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style C2 夜樱轻奢登录页预览</title>
    <style>
      :root {
        --light-bg: linear-gradient(180deg, #fff8fc, #fff1f8 52%, #f4efff);
        --light-panel: rgba(255,255,255,0.92);
        --light-line: rgba(232,191,220,0.92);
        --light-text: #5b3650;
        --light-muted: #86667f;
        --dark-bg: linear-gradient(180deg, #170f24, #241633 48%, #100d1d);
        --dark-panel: rgba(31, 22, 43, 0.9);
        --dark-line: rgba(255, 202, 231, 0.18);
        --dark-text: #fff4fb;
        --dark-muted: #d8c1d9;
        --accent: linear-gradient(135deg, #ff8ebe, #c08bff 58%, #7f8fff);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(255, 204, 231, 0.28), transparent 24%),
          radial-gradient(circle at bottom right, rgba(180, 170, 255, 0.22), transparent 24%),
          #fff8fb;
        color: #5b3650;
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 980px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        border: 1px solid #f1d7e7;
        background: rgba(255,255,255,0.74);
        color: #cb4f86;
        font-size: 12px;
        font-weight: 800;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; line-height: 1.7; color: #86667f; }
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
        border: 1px solid rgba(238, 208, 228, 0.92);
        background: rgba(255,255,255,0.72);
        box-shadow: 0 18px 40px rgba(131, 85, 125, 0.14);
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
        align-items: center;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        background: rgba(255,255,255,0.8);
      }
      .scene {
        min-height: 580px;
        padding: 26px;
        border-radius: 24px;
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
        border: 1px solid rgba(255, 202, 231, 0.16);
      }
      .moon-arc {
        position: absolute;
        top: -18px;
        right: -28px;
        width: 220px;
        height: 220px;
        border-radius: 50%;
        border: 1px solid rgba(255,255,255,0.22);
        box-shadow: inset 0 0 0 18px rgba(255,255,255,0.04);
      }
      .petals {
        position: absolute;
        top: 26px;
        left: 26px;
        font-size: 12px;
        letter-spacing: 6px;
        opacity: 0.8;
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
      .hero p { margin: 0 0 16px; line-height: 1.8; }
      .hero-tags { display: flex; flex-wrap: wrap; gap: 10px; }
      .hero-tags span {
        padding: 8px 12px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 700;
      }
      .theme-light .hero-tags span {
        background: rgba(255,255,255,0.88);
        border: 1px solid #efd6e5;
        color: #c74f85;
      }
      .theme-dark .hero-tags span {
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255, 202, 231, 0.18);
        color: #ffd5ea;
      }
      .form-card {
        position: relative;
        z-index: 1;
        padding: 24px;
        border-radius: 28px;
        backdrop-filter: blur(18px);
      }
      .theme-light .form-card {
        background: var(--light-panel);
        border: 1px solid var(--light-line);
        box-shadow: 0 18px 34px rgba(205, 163, 187, 0.22);
      }
      .theme-dark .form-card {
        background: var(--dark-panel);
        border: 1px solid var(--dark-line);
        box-shadow: 0 18px 34px rgba(12, 10, 23, 0.34);
      }
      .crest {
        width: 58px;
        height: 58px;
        display: grid;
        place-items: center;
        border-radius: 18px;
        color: #fff;
        font-size: 24px;
        font-weight: 800;
        background: var(--accent);
        box-shadow: 0 14px 24px rgba(255, 142, 190, 0.26);
      }
      .form-card h3 { margin: 16px 0 8px; font-size: 28px; }
      .form-card p { margin: 0 0 16px; line-height: 1.7; }
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
        border: 1px solid #edd2e2;
        background: rgba(255,255,255,0.96);
        color: var(--light-text);
      }
      .theme-dark .field input {
        border: 1px solid rgba(255, 202, 231, 0.18);
        background: rgba(255,255,255,0.06);
        color: var(--dark-text);
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
        background: var(--accent);
        box-shadow: 0 14px 26px rgba(255, 142, 190, 0.26);
      }
      .theme-light .btn-secondary {
        background: rgba(255,255,255,0.92);
        border: 1px solid #edd6e6;
        color: #744f66;
      }
      .theme-dark .btn-secondary {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255, 202, 231, 0.18);
        color: #fff4fb;
      }
      .phone {
        max-width: 320px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #2e203d;
      }
      .phone-screen {
        min-height: 620px;
        border-radius: 26px;
        padding: 18px;
      }
      .theme-light .phone-screen { background: var(--light-bg); }
      .theme-dark .phone-screen { background: var(--dark-bg); }
      .mobile-card {
        margin-top: 18px;
        padding: 18px;
        border-radius: 24px;
        backdrop-filter: blur(16px);
      }
      .theme-light .mobile-card {
        background: rgba(255,255,255,0.94);
        border: 1px solid #edd6e6;
      }
      .theme-dark .mobile-card {
        background: rgba(31, 22, 43, 0.9);
        border: 1px solid rgba(255, 202, 231, 0.18);
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
  <body data-style="c2-refine" data-page="login">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style C2 Refine · 夜樱轻奢</span>
        <h1>登录页精修静态预览</h1>
        <p>把当前 C2 收敛成更完整的夜樱轻奢世界观：亮色是晨樱珠雾，深色是夜樱月下，移动端与桌面端都保持统一的少女系产品气质。</p>
      </header>

      <div class="preview-grid">
        <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 亮色模式</span>
            <span class="chip">晨樱珠雾</span>
          </div>
          <div class="scene">
            <div class="moon-arc"></div>
            <div class="petals">✦ 花瓣 ✦ 月光 ✦</div>
            <div class="desktop-layout">
              <div class="hero">
                <span class="chip">夜樱轻奢</span>
                <h2>跑步助手</h2>
                <p>用晨樱珠雾与月光描边重做登录入口，让它像一款正式少女产品的世界观首页，而不是甜品贴纸海报。</p>
                <div class="hero-tags">
                  <span>樱雾月光</span>
                  <span>珠光描边</span>
                  <span>轻奢少女</span>
                </div>
              </div>
              <form class="form-card">
                <div class="crest">樱</div>
                <h3>欢迎回来</h3>
                <p>继续进入任务、通知与个性化设置，回到更完整的夜樱世界。</p>
                <div class="field">
                  <label for="c2-refine-light-desktop-user">账号 / 手机号</label>
                  <input id="c2-refine-light-desktop-user" type="text" value="admin" />
                </div>
                <div class="field">
                  <label for="c2-refine-light-desktop-password">密码</label>
                  <input id="c2-refine-light-desktop-password" type="password" value="admin" />
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
            <span class="chip">夜樱月下</span>
          </div>
          <div class="scene">
            <div class="moon-arc"></div>
            <div class="petals">✦ 花瓣 ✦ 月弧 ✦</div>
            <div class="desktop-layout">
              <div class="hero">
                <span class="chip">月下花雾</span>
                <h2>跑步助手</h2>
                <p>深色版不再只是暗色换皮，而是完整的夜樱月下入口，保持珠光轮廓、柔辉光与清楚的登录节奏。</p>
                <div class="hero-tags">
                  <span>夜樱辉光</span>
                  <span>月下描边</span>
                  <span>完整世界观</span>
                </div>
              </div>
              <form class="form-card">
                <div class="crest">夜</div>
                <h3>欢迎回来</h3>
                <p>让深色版像真正的主视觉产品界面，而不是普通暗色表单。</p>
                <div class="field">
                  <label for="c2-refine-dark-desktop-user">账号 / 手机号</label>
                  <input id="c2-refine-dark-desktop-user" type="text" value="admin" />
                </div>
                <div class="field">
                  <label for="c2-refine-dark-desktop-password">密码</label>
                  <input id="c2-refine-dark-desktop-password" type="password" value="admin" />
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
            <span class="chip">晨樱单列</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-card">
                  <span class="chip">晨樱珠雾</span>
                  <h3>跑步助手</h3>
                  <p>移动端亮色继续保留珠光半透和樱雾层次，让夜樱轻奢感在单列界面里也成立。</p>
                  <div class="field">
                    <label for="c2-refine-light-mobile-user">账号 / 手机号</label>
                    <input id="c2-refine-light-mobile-user" type="text" placeholder="请输入账号" />
                  </div>
                  <div class="field">
                    <label for="c2-refine-light-mobile-password">密码</label>
                    <input id="c2-refine-light-mobile-password" type="password" placeholder="请输入密码" />
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
                  <span class="chip">夜樱月下</span>
                  <h3>跑步助手</h3>
                  <p>把月下花雾、珠光边线与克制高光压缩到单列移动端里，同时保证 CTA 和输入层级第一眼可见。</p>
                  <div class="field">
                    <label for="c2-refine-dark-mobile-user">账号 / 手机号</label>
                    <input id="c2-refine-dark-mobile-user" type="text" placeholder="请输入账号" />
                  </div>
                  <div class="field">
                    <label for="c2-refine-dark-mobile-password">密码</label>
                    <input id="c2-refine-dark-mobile-password" type="password" placeholder="请输入密码" />
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

- [ ] **Step 4: Run the login test to verify it passes**

Run:

```bash
python -m unittest discover -s tests -p "test_ui_previews_style_c2_refine.py" -v
```

Expected:
- `test_login_preview_has_night_sakura_all_modes` PASS
- No additional failures

- [ ] **Step 5: Commit the login preview**

Run:

```bash
git add tests/test_ui_previews_style_c2_refine.py ui-previews/style-c2-refine-login.html
git commit -m "feat: add refined C2 login preview"
```

Expected:
- A new commit is created containing the login test and login preview HTML

### Task 2: Add the refined admin preview

**Files:**
- Modify: `tests/test_ui_previews_style_c2_refine.py`
- Create: `ui-previews/style-c2-refine-admin.html`
- Reference: `ui-previews/style-c2-admin.html`

- [ ] **Step 1: Extend the test file with a failing admin test**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_PREVIEWS = ROOT / "ui-previews"


def read_preview(name: str) -> str:
    return (UI_PREVIEWS / name).read_text(encoding="utf-8")


class TestUiPreviewsStyleC2Refine(unittest.TestCase):
    def test_login_preview_has_night_sakura_all_modes(self):
        html = read_preview("style-c2-refine-login.html")
        self.assertIn('data-style="c2-refine"', html)
        self.assertIn('data-page="login"', html)
        self.assertIn('data-preview-mode="desktop"', html)
        self.assertIn('data-preview-mode="mobile"', html)
        self.assertIn('data-theme-preview="light"', html)
        self.assertIn('data-theme-preview="dark"', html)
        self.assertIn("夜樱轻奢", html)
        self.assertIn("晨樱珠雾", html)
        self.assertIn("夜樱月下", html)
        self.assertIn("立即登录", html)
        self.assertNotIn("scripts/main.new.js", html)
        self.assertNotIn("fetch(", html)

    def test_admin_preview_keeps_config_semantics_in_refine_theme(self):
        html = read_preview("style-c2-refine-admin.html")
        self.assertIn('data-style="c2-refine"', html)
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

- [ ] **Step 2: Run the refine test file to verify the new admin test fails**

Run:

```bash
python -m unittest discover -s tests -p "test_ui_previews_style_c2_refine.py" -v
```

Expected:
- `test_login_preview_has_night_sakura_all_modes` PASS
- `test_admin_preview_keeps_config_semantics_in_refine_theme` FAIL
- Failure reason is `FileNotFoundError` for `ui-previews/style-c2-refine-admin.html`

- [ ] **Step 3: Write the minimal admin preview implementation**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Style C2 夜樱轻奢后台配置页预览</title>
    <style>
      :root {
        --light-bg: linear-gradient(180deg, #fff8fc, #fff0f7 50%, #f4efff);
        --light-panel: rgba(255,255,255,0.94);
        --light-line: rgba(233, 194, 221, 0.92);
        --light-text: #59364f;
        --light-muted: #856b80;
        --dark-bg: linear-gradient(180deg, #150f21, #22152f 50%, #100d1c);
        --dark-panel: rgba(31, 22, 43, 0.9);
        --dark-line: rgba(255, 204, 233, 0.18);
        --dark-text: #fff3fa;
        --dark-muted: #d6c0d8;
        --accent: linear-gradient(135deg, #ff8cbe, #c190ff 56%, #8d92ff);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(255, 203, 230, 0.28), transparent 24%),
          radial-gradient(circle at bottom right, rgba(176, 168, 255, 0.22), transparent 24%),
          #fff8fb;
        color: #59364f;
      }
      .page { min-height: 100vh; padding: 32px; }
      .intro { max-width: 980px; margin: 0 auto 24px; }
      .eyebrow {
        display: inline-flex;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(255,255,255,0.76);
        border: 1px solid #f0d7e7;
        color: #cc4e86;
        font-size: 12px;
        font-weight: 800;
      }
      .intro h1 { margin: 14px 0 8px; font-size: 34px; }
      .intro p { margin: 0; line-height: 1.7; color: #856b80; }
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
        border: 1px solid rgba(238, 208, 228, 0.92);
        background: rgba(255,255,255,0.72);
        box-shadow: 0 18px 40px rgba(133, 92, 126, 0.14);
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
        background: rgba(255,255,255,0.8);
      }
      .scene {
        min-height: 640px;
        padding: 22px;
        border-radius: 24px;
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
        border: 1px solid rgba(255, 204, 233, 0.16);
      }
      .moon-arc {
        position: absolute;
        inset: -40px -20px auto auto;
        width: 220px;
        height: 220px;
        border-radius: 50%;
        border: 1px solid rgba(255,255,255,0.22);
        box-shadow: inset 0 0 0 18px rgba(255,255,255,0.04);
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
      .topbar p { margin: 6px 0 0; line-height: 1.7; }
      .actions { display: flex; gap: 8px; flex-wrap: wrap; }
      .btn {
        min-height: 40px;
        padding: 0 14px;
        border-radius: 16px;
        font-size: 13px;
        font-weight: 800;
      }
      .theme-light .btn {
        border: 1px solid #efd5e6;
        background: rgba(255,255,255,0.92);
        color: #704d65;
      }
      .theme-dark .btn {
        border: 1px solid rgba(255, 204, 233, 0.18);
        background: rgba(255,255,255,0.06);
        color: #fff3fa;
      }
      .btn-primary {
        border-color: transparent !important;
        color: #fff !important;
        background: var(--accent) !important;
        box-shadow: 0 14px 24px rgba(255, 140, 190, 0.24);
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
        background: rgba(255,244,249,0.92);
        border: 1px solid #f1d6e7;
      }
      .theme-dark .warning {
        background: rgba(255, 140, 190, 0.1);
        border: 1px solid rgba(255, 204, 233, 0.18);
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
        border-radius: 22px;
        backdrop-filter: blur(16px);
      }
      .theme-light .field-card {
        background: var(--light-panel);
        border: 1px solid var(--light-line);
        box-shadow: 0 14px 28px rgba(206, 164, 188, 0.2);
      }
      .theme-dark .field-card {
        background: var(--dark-panel);
        border: 1px solid var(--dark-line);
        box-shadow: 0 14px 28px rgba(12, 10, 23, 0.28);
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
        border: 1px solid #edd3e3;
        background: rgba(255,255,255,0.96);
      }
      .theme-dark .mock-input,
      .theme-dark .mock-select {
        border: 1px solid rgba(255, 204, 233, 0.18);
        background: rgba(255,255,255,0.06);
      }
      .phone {
        max-width: 320px;
        margin: 0 auto;
        border-radius: 34px;
        padding: 14px;
        background: #2d203c;
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
        border-radius: 24px;
        backdrop-filter: blur(16px);
      }
      .theme-light .mobile-shell {
        background: rgba(255,255,255,0.94);
        border: 1px solid #edd3e3;
      }
      .theme-dark .mobile-shell {
        background: rgba(31, 22, 43, 0.9);
        border: 1px solid rgba(255, 204, 233, 0.18);
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
  <body data-style="c2-refine" data-page="admin">
    <main class="page">
      <header class="intro">
        <span class="eyebrow">Style C2 Refine · 夜樱轻奢</span>
        <h1>后台配置页精修静态预览</h1>
        <p>让后台也进入夜樱轻奢世界观：亮色像晨樱珠雾管理台，深色像夜樱月下后台，同时保留真实字段语义与配置节奏。</p>
      </header>

      <div class="preview-grid">
        <section class="preview-card theme-light" data-preview-mode="desktop" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 亮色模式</span>
            <span class="chip">晨樱珠雾后台</span>
          </div>
          <div class="scene">
            <div class="moon-arc"></div>
            <div class="topbar">
              <div>
                <h2>系统配置</h2>
                <p>用珠光模块卡与轻月描边重做后台，让它像同一套少女产品中的正式配置界面。</p>
              </div>
              <div class="actions">
                <button class="btn" type="button">刷新</button>
                <button class="btn btn-primary" type="button">保存配置</button>
              </div>
            </div>
            <div class="warning">⚠️ 保存后部分配置需要重启程序。提示信息仍然明确，但整体语气更融入夜樱轻奢主题。</div>
            <section class="group">
              <h3 class="group-title">游客配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>允许游客登录</strong>
                  <p>保持字段语义清楚，同时让卡片更像珠光配置匣。</p>
                  <div class="mock-select">启用</div>
                </article>
                <article class="field-card">
                  <strong>显示新手帮助</strong>
                  <p>说明文案更轻、更柔和，但不影响扫读。</p>
                  <div class="mock-select">启用</div>
                </article>
              </div>
            </section>
            <section class="group">
              <h3 class="group-title">系统配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>会话过期时间 (天)</strong>
                  <p>输入壳体升级为更细致的品牌化控件。</p>
                  <div class="mock-input">30</div>
                </article>
                <article class="field-card">
                  <strong>密码存储方式</strong>
                  <p>在更高级的视觉里保持安全项的清晰权重。</p>
                  <div class="mock-select">BCrypt (自动加盐)</div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="preview-card theme-dark" data-preview-mode="desktop" data-theme-preview="dark">
          <div class="preview-head">
            <span class="preview-title">桌面端 · 深色模式</span>
            <span class="chip">夜樱月下后台</span>
          </div>
          <div class="scene">
            <div class="moon-arc"></div>
            <div class="topbar">
              <div>
                <h2>系统配置</h2>
                <p>深色版作为完整夜樱月下后台存在，让花雾辉光与真正的产品可用性同时成立。</p>
              </div>
              <div class="actions">
                <button class="btn" type="button">刷新</button>
                <button class="btn btn-primary" type="button">保存配置</button>
              </div>
            </div>
            <div class="warning">⚠️ 深色模式下仍要保证字段、按钮、警告与分组的层级第一眼可读。</div>
            <section class="group">
              <h3 class="group-title">游客配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>允许游客登录</strong>
                  <p>用月下描边强调状态，但不把界面做成装饰海报。</p>
                  <div class="mock-select">启用</div>
                </article>
                <article class="field-card">
                  <strong>显示新手帮助</strong>
                  <p>深色说明区维持柔和节奏与清楚信息密度。</p>
                  <div class="mock-select">启用</div>
                </article>
              </div>
            </section>
            <section class="group">
              <h3 class="group-title">系统配置</h3>
              <div class="group-grid">
                <article class="field-card">
                  <strong>会话过期时间 (天)</strong>
                  <p>数字字段在夜樱深色中仍有清楚边界和高对比。</p>
                  <div class="mock-input">30</div>
                </article>
                <article class="field-card">
                  <strong>密码存储方式</strong>
                  <p>把珠光与辉光收敛在容器轮廓，不干扰实际配置阅读。</p>
                  <div class="mock-select">BCrypt (自动加盐)</div>
                </article>
              </div>
            </section>
          </div>
        </section>

        <section class="preview-card theme-light" data-preview-mode="mobile" data-theme-preview="light">
          <div class="preview-head">
            <span class="preview-title">移动端 · 亮色模式</span>
            <span class="chip">晨樱单列后台</span>
          </div>
          <div class="scene">
            <div class="phone">
              <div class="phone-screen">
                <div class="mobile-shell">
                  <h3>系统配置</h3>
                  <p>移动端亮色继续保留珠光模块感，同时让后台操作路径一眼可扫。</p>
                  <div class="actions" style="margin-bottom:12px;">
                    <button class="btn" type="button">刷新</button>
                    <button class="btn btn-primary" type="button">保存配置</button>
                  </div>
                  <section class="group">
                    <h4 class="group-title">游客配置</h4>
                    <article class="field-card">
                      <strong>允许游客登录</strong>
                      <p>在移动单列里快速理解游客访问策略。</p>
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
                  <p>夜樱移动端在保留完整世界观的同时，继续维持单列配置界面的顺手节奏。</p>
                  <div class="actions" style="margin-bottom:12px;">
                    <button class="btn" type="button">刷新</button>
                    <button class="btn btn-primary" type="button">保存配置</button>
                  </div>
                  <section class="group">
                    <h4 class="group-title">系统配置</h4>
                    <article class="field-card">
                      <strong>会话过期时间 (天)</strong>
                      <p>在深色单列中仍能一眼识别数值字段与操作边界。</p>
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

- [ ] **Step 4: Run the refine test file to verify both tests pass**

Run:

```bash
python -m unittest discover -s tests -p "test_ui_previews_style_c2_refine.py" -v
```

Expected:
- `test_login_preview_has_night_sakura_all_modes` PASS
- `test_admin_preview_keeps_config_semantics_in_refine_theme` PASS

- [ ] **Step 5: Commit the admin preview**

Run:

```bash
git add tests/test_ui_previews_style_c2_refine.py ui-previews/style-c2-refine-admin.html
git commit -m "feat: add refined C2 admin preview"
```

Expected:
- A new commit is created containing the admin preview test update and admin preview HTML

### Task 3: Run regression and perform visual verification

**Files:**
- Verify: `tests/test_ui_previews_style_c.py`
- Verify: `tests/test_ui_previews_style_c1.py`
- Verify: `tests/test_ui_previews_style_c2.py`
- Verify: `tests/test_ui_previews_style_c3.py`
- Verify: `tests/test_ui_previews_style_c2_refine.py`
- Verify: `ui-previews/style-c2-refine-login.html`
- Verify: `ui-previews/style-c2-refine-admin.html`

- [ ] **Step 1: Run the full Style C preview regression suite**

Run:

```bash
python -m unittest discover -s tests -p "test_ui_previews_style_c*.py" -v
```

Expected:
- Existing `style-c`, `style-c1`, `style-c2`, `style-c3` tests PASS
- New `style-c2-refine` tests PASS
- No `FileNotFoundError`, no import failures, no extra regressions

- [ ] **Step 2: Start a local preview server from the worktree root**

Run:

```bash
python -m http.server 8767
```

Expected:
- Terminal shows `Serving HTTP on 0.0.0.0 port 8767`
- Keep this running while you manually inspect both pages in a browser

- [ ] **Step 3: Open the refine previews and perform the visual acceptance check**

Open:

```text
http://127.0.0.1:8767/ui-previews/style-c2-refine-login.html
http://127.0.0.1:8767/ui-previews/style-c2-refine-admin.html
```

Check all of the following:
- 登录页亮色第一眼是“晨樱珠雾”，不是糖果贴纸
- 登录页深色第一眼是“夜樱月下”，不是普通暗色换皮
- 四个状态都能明显看出同一套夜樱轻奢世界观
- 后台仍然保留标题、刷新、保存配置、警告、分组、字段卡片的清楚结构
- 后台字段 `允许游客登录` 与 `会话过期时间 (天)` 在四个状态里都能快速识别

- [ ] **Step 4: Stop the local preview server after manual review**

Run:

```text
Ctrl+C
```

Expected:
- The server exits cleanly and you return to the shell prompt
