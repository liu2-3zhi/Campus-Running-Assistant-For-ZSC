# Vue UI 视觉一致性基础与登录页实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 先将旧版的全局视觉基础与登录/注册链路完整对齐到 Vue 版，并建立可重复运行的视觉回归入口。

**Architecture:** 保持现有 Vue 路由、Pinia 和 API 调用不变，只迁移旧版 `styles/style.css` 的视觉规则，并重排 `LoginView.vue` 与 `AuthPanel.vue` 的 DOM 层级。自动化测试使用 Node 静态契约测试与 Playwright 截图捕获，业务逻辑不改。

**Tech Stack:** Vue 3、Vite 8、Tailwind CSS 4、Node test runner、Python Playwright、Pillow。

---

## 文件结构

- `frontend/src/assets/style.css`：全局视觉 token、面板、按钮、输入框、弹窗、深色模式与页面背景。
- `frontend/src/views/LoginView.vue`：认证页外壳、卡片、帮助入口和响应式布局。
- `frontend/src/components/login/AuthPanel.vue`：登录/注册/2FA 表单与验证码布局。
- `frontend/src/components/common/BeianFooter.vue`：认证卡片底部备案信息。
- `tests/vue_ui_parity_login.test.mjs`：认证页结构与全局视觉契约测试。
- `scripts/capture_ui_parity.py`：旧版/Vue 版同视口截图捕获脚本。

### Task 1: 建立认证页视觉契约测试

**Files:**
- Create: `tests/vue_ui_parity_login.test.mjs`
- Test: `tests/vue_ui_parity_login.test.mjs`

- [ ] **Step 1: 写入失败测试**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('global styles retain legacy page and surface tokens', () => {
  const css = read('frontend/src/assets/style.css')
  assert.match(css, /linear-gradient\(\s*180deg,\s*rgba\(245,\s*250,\s*255,\s*1\)/)
  assert.match(css, /box-shadow:\s*0 10px 24px rgba\(16,\s*24,\s*40,\s*0\.12\)/)
  assert.match(css, /body\.dark-mode \.panel/)
})

test('auth screens expose legacy semantic anchors', () => {
  const loginView = read('frontend/src/views/LoginView.vue')
  const authPanel = read('frontend/src/components/login/AuthPanel.vue')
  assert.match(loginView, /id="auth-login-container"/)
  assert.match(loginView, /id="auth-login-container_panel"/)
  assert.match(authPanel, /id="auth-login-form"/)
  assert.match(authPanel, /id="auth-login-captcha-display"/)
  assert.match(authPanel, /id="guest-login-section"/)
  assert.match(authPanel, /id="auth-beian-footer"/)
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --test tests/vue_ui_parity_login.test.mjs`

Expected: FAIL，提示旧版渐变、面板阴影或认证页语义 id 缺失。

- [ ] **Step 3: 提交测试**

```bash
git add tests/vue_ui_parity_login.test.mjs
git commit -m "test: 添加 Vue 登录页视觉契约"
```

### Task 2: 迁移旧版全局视觉基础

**Files:**
- Modify: `frontend/src/assets/style.css`
- Test: `tests/vue_ui_parity_login.test.mjs`

- [ ] **Step 1: 用旧版规则替换全局页面前提**

在 `:root` 后增加旧版页面渐变，并让面板、输入框、按钮、模态框继续引用同一组 CSS 变量：

```css
body {
  background:
    linear-gradient(
      180deg,
      rgba(245, 250, 255, 1) 0%,
      rgba(235, 245, 255, 1) 40%,
      rgba(250, 240, 255, 1) 100%
    );
  background-attachment: fixed;
}

.panel {
  -webkit-backdrop-filter: blur(16px);
  backdrop-filter: blur(16px);
  background-color: var(--card-bg);
  border: 1px solid rgba(255, 255, 255, 0.45);
  box-shadow: 0 10px 24px rgba(16, 24, 40, 0.12);
}

body.dark-mode .panel {
  background-color: rgba(31, 41, 55, 0.8);
  border: 1px solid rgba(75, 85, 99, 0.5);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.4);
}
```

同时迁移旧版的 `body.dark-mode .btn*`、输入控件、表格和滚动条覆盖规则，避免新增渐变被深色模式覆盖。

- [ ] **Step 2: 运行契约测试**

Run: `node --test tests/vue_ui_parity_login.test.mjs`

Expected: 第一条测试 PASS，第二条仍可能 FAIL。

- [ ] **Step 3: 运行构建**

Run: `npm run build`

Working directory: `frontend`

Expected: 输出包含 `built in` 且退出码为 0。

- [ ] **Step 4: 提交全局视觉修改**

```bash
git add frontend/src/assets/style.css
git commit -m "style: 对齐旧版全局视觉基础"
```

### Task 3: 重排认证卡片与登录表单

**Files:**
- Modify: `frontend/src/views/LoginView.vue`
- Modify: `frontend/src/components/login/AuthPanel.vue`
- Modify: `frontend/src/components/common/BeianFooter.vue`
- Test: `tests/vue_ui_parity_login.test.mjs`

- [ ] **Step 1: 给认证页补回旧版语义锚点**

`LoginView.vue` 的认证分支改为旧版容器与面板 id：

```vue
<div
  v-else-if="viewMode === 'auth'"
  id="auth-login-container"
  class="flex h-screen w-screen items-center justify-center p-4"
>
  <div
    id="auth-login-container_panel"
    class="panel auth-panel w-full max-w-[600px]"
  >
    <div class="auth-panel__header">
      <h1>跑步助手</h1>
      <p>请登录或注册以继续使用</p>
    </div>
    <AuthPanel @login-success="onAuthSuccess" />
  </div>
</div>
```

- [ ] **Step 2: 对齐登录表单的旧版顺序**

在 `AuthPanel.vue` 中为表单和关键区域补 id，并将验证码恢复成旧版顺序：显示框、刷新按钮、输入框。

```vue
<form id="auth-login-form" class="auth-form" @submit.prevent="handleLogin">
  <div id="auth-login-type-toggle" class="auth-mode-toggle">
    <button type="button" @click="loginMode = 'username'; passwordMode = 'password'">
      用户名登录
    </button>
    <button type="button" @click="loginMode = 'phone'">
      手机号登录
    </button>
  </div>
  <div id="auth-username-container" v-if="loginMode === 'username'">
    <label>用户名</label>
    <input v-model="loginForm.username" class="input-field" placeholder="请输入用户名" />
  </div>
  <div id="auth-password-section" v-if="passwordMode === 'password'">
    <label>密码</label>
    <input
      v-model="loginForm.password"
      type="password"
      class="input-field"
      placeholder="请输入密码"
      autocomplete="current-password"
    />
  </div>
  <div id="auth-sms-section" v-if="passwordMode === 'sms'">
    <label>验证码</label>
    <div class="flex gap-2">
      <input v-model="loginForm.smsCode" class="input-field" maxlength="6" />
      <button type="button" class="btn btn-primary" @click="sendLoginSmsCode">
        发送验证码
      </button>
    </div>
  </div>
  <div class="auth-captcha-block">
    <div id="auth-login-captcha-display" @click="loadCaptcha('login')">
      <iframe v-if="loginCaptchaIframeSrc" :src="loginCaptchaIframeSrc" />
      <span v-else>加载中...</span>
    </div>
    <button id="auth-login-captcha-refresh" type="button" @click="loadCaptcha('login')">
      刷新验证码
    </button>
    <input
      id="auth-login-captcha"
      v-model="loginForm.captchaCode"
      class="input-field"
      placeholder="请输入验证码"
      maxlength="6"
    />
  </div>
  <button id="auth-login-btn" class="btn btn-primary w-full" type="submit">登录</button>
  <div id="guest-login-section" v-if="guestLoginEnabled">
    <span>或</span>
    <button type="button" class="btn btn-ghost w-full" @click="handleGuestLogin">
      以游客身份继续
    </button>
  </div>
</form>
```

- [ ] **Step 3: 恢复旧版页脚**

在认证面板内部加入 `BeianFooter`，页面级别不再重复输出：

```vue
<div id="auth-beian-footer" class="auth-beian-footer">
  <BeianFooter />
</div>
```

- [ ] **Step 4: 运行契约测试与构建**

Run: `node --test tests/vue_ui_parity_login.test.mjs`

Expected: PASS。

Run: `npm run build`

Working directory: `frontend`

Expected: 构建成功，无 Vue 模板错误。

- [ ] **Step 5: 提交认证页修改**

```bash
git add frontend/src/views/LoginView.vue frontend/src/components/login/AuthPanel.vue frontend/src/components/common/BeianFooter.vue
git commit -m "style: 对齐旧版登录页布局"
```

### Task 4: 捕获并检查同视口截图

**Files:**
- Create: `scripts/capture_ui_parity.py`
- Output: `output/ui-parity/legacy-*.png`
- Output: `output/ui-parity/vue-*.png`

- [ ] **Step 1: 创建截图捕获脚本**

脚本使用 `LEGACY_URL`、`VUE_URL`、`OUTPUT_DIR` 环境变量，默认旧版为 `http://127.0.0.1:5000/`，Vue 为 `http://127.0.0.1:5173/`。桌面使用 `1440x900`，移动端使用真实移动 UA、触控和设备上下文 `390x844`。

- [ ] **Step 2: 启动服务**

Run: `python main.py --host 127.0.0.1 --port 5000 --log-level error`

Run: `npm run dev -- --host 127.0.0.1 --port 5173`

Working directory: `frontend`

- [ ] **Step 3: 运行截图**

Run: `python scripts/capture_ui_parity.py`

Expected: `output/ui-parity/` 下生成四张认证页截图。

- [ ] **Step 4: 人工检查关键几何**

检查 `#auth-login-container_panel` 的桌面宽度、标题、页签、验证码顺序、帮助入口、备案页脚和移动端滚动边界。记录与旧版仍不一致的元素，作为下一批修正输入。

- [ ] **Step 5: 提交截图工具**

```bash
git add scripts/capture_ui_parity.py
git commit -m "test: 添加 UI 同视口截图工具"
```

## 后续计划

登录链路完成后，分别创建主应用/弹窗计划和管理后台计划；每个计划都必须以旧版截图与固定 fixture 为验收基础。
