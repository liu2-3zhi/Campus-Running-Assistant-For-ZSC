# 10 · index.html 逐行解析（`<head>` 与顶层模态框）

> **覆盖范围：`index.html` 第 1 行 – 第 2162 行**（含 `<head>` 全部外部依赖 + `<body>` 内所有顶层浮层 / 模态框 / 认证登录容器，止于 `#desktop-container` 起始行 2162）。
> 本文件是 Vue 复刻的权威依据，逐元素记录 id / class / 行号 / 可见性 / 内联事件绑定 / 文案，力求无遗漏。
> 生成时间：2026-07-14

---

## 目录（按出现顺序）

| # | 行号 | 容器 | 说明 |
|---|---|---|---|
| A | 1–521 | `<head>` | 外部依赖、meta、PWA、内联样式 |
| B | 523–538 | `#admin-return-overlay` | 「返回管理员会话」悬浮按钮 |
| C | 540–563 | `#newbie-help-btn` | 新手帮助悬浮按钮 |
| D | 565–629 | `#newbie-help-modal` | 新手帮助模态框 |
| E | 631–754 | `<script>` | 新手帮助模态框行为脚本（内联 IIFE） |
| F | 756–775 | `#exit-app-btn` | 退出应用悬浮按钮 |
| G | 777–834 | `#cdn-error-overlay` | CDN 资源加载失败全屏遮罩 |
| H | 836–905 | `#guest_warning_overlay` + `#guest-warning-toast`（内含 `#guest_warning`） | 游客模式警告浮层 |
| I | 906–1039 | `#newUserModal`（内含 `#newUserSmsGroup`） | 新建用户模态框 |
| J | 1041–1119 | `#multi-add-user-modal` | 移动端批量添加用户 · 单条录入模态框 |
| K | 1121–1170 | `#school-accounts-modal` | 校园账号管理模态框 |
| L | 1172–1381 | `#edit-school-account-modal` | 编辑校园账号模态框 |
| M | 1383–1389 | `#loading-overlay` | 资源加载遮罩 |
| N | 1391–1539 | `#captcha-verification-modal` | 图形验证码 / 安全验证模态框 |
| O | 1541–2157 | `#auth-login-container` | 认证登录容器（登录表单 + 注册表单 + `#auth-2fa-form` + 备案 footer） |
| — | 2162 | `#desktop-container` | 下一区块起点（不在本文覆盖内） |

> 说明：本段中**绝大多数按钮的 id 存在，但点击事件在 `scripts/main.new.js` 中通过 `addEventListener` 绑定**（非内联）。凡是写在 HTML 里的内联事件（`onclick`/`oninput`/`onerror` 等）在下文用「内联」标注；仅有 id、需在 JS 中查绑定的用「JS 绑定」标注。

---

## A. `<head>`（第 1–521 行）

### A.1 IE 检测与顶层同步脚本（1–19）

| 行 | 内容 | 说明 |
|---|---|---|
| 4–8 | `<!--[if lt IE 9]>` 条件注释 | IE < 9 跳转 `/ie_basic.html` |
| 9–13 | `<!--[if (IE 9)]>` 条件注释 | IE 9 跳转 `/ie.html` |
| 15 | `<script src="/scripts/ie_detect.js">` | IE 检测（同步加载，渲染前完成） |
| 16 | `<script src="/scripts/Check_for_updates.js">` | 版本更新检查 |
| 17 | `<script src="/scripts/load_amap_watermark.js">` | 高德地图水印加载控制 |
| 18 | （注释）`Remove_watermark_from_Amap_Map.js` | 已注释停用 |
| 19 | `<script src="/api/frontend_config.js">` | 后端下发前端配置（生成 `window.APP_CONFIG`） |

### A.2 meta / PWA / 图标（20–31）

| 行 | 标签 | 值 |
|---|---|---|
| 20 | `<meta charset>` | `UTF-8` |
| 21 | `<title>` | **跑步助手** |
| 22 | `<link rel="icon">` | `/favicon.ico` |
| 24 | `<link rel="manifest">` | `/manifest.json`（PWA） |
| 25 | `theme-color` | `#2563eb` |
| 26 | `mobile-web-app-capable` | `yes` |
| 27 | `apple-mobile-web-app-capable` | `yes` |
| 28 | `apple-mobile-web-app-status-bar-style` | `default` |
| 29 | `apple-mobile-web-app-title` | `跑步助手` |
| 30 | `apple-touch-icon` | `/icon-192x192.png` |
| 31 | `viewport` | `width=device-width, initial-scale=1` |

### A.3 外部依赖（CDN）——统一 `/api/cdn/*` 代理 + `onerror` 回退到 jsdelivr

**加载模式说明：** 每个资源 `src`/`href` 指向本地代理 `/api/cdn/<name>`；`onerror` 内联切换到公网 CDN（`https://cdn.jsdelivr.net/...` 等）。JS 用 `this.src=...`，CSS 用 `this.href=...`。

#### 通用第三方库（32–75）

| 行 | 资源 | 代理路径 | onerror 回退 |
|---|---|---|---|
| 33–37 | SweetAlert2 CSS | `/api/cdn/sweetalert2-css` | `.../sweetalert2/dist/sweetalert2.min.css` |
| 38–41 | SweetAlert2 JS | `/api/cdn/sweetalert2` | `.../sweetalert2/dist/sweetalert2.all.min.js` |
| 44 | qrcode（二维码） | `/api/cdn/qrcode` | `.../qrcode/build/qrcode.min.js`（注释注明**不可换成** jsdelivr 的 qrcode.min.js） |
| 47 | cropperjs CSS | `/api/cdn/cropperjs-css` | `cropperjs@1.6.2/dist/cropper.min.css`（锁 1.6.2，2.x API 变动） |
| 48 | cropperjs JS | `/api/cdn/cropperjs` | `cropperjs@1.6.2/dist/cropper.min.js` |
| 52 | TailwindCSS | `/api/cdn/tailwindcss` | `https://cdn.tailwindcss.com`（锁 3.4.17，4.x API 变动） |
| 54 | socket.io | `/api/cdn/socketio` | `.../socket.io/client-dist/socket.io.min.js` |
| 62 | Zilla Slab 字体 | `/api/cdn/zilla-slab` | `@fontsource/zilla-slab@5/index.min.css` |
| 63 | Noto Sans SC 字体 | `/api/cdn/noto-sans-sc` | `@fontsource-variable/noto-sans-sc/index.min.css`（注释：计划改思源雅黑 TODO） |
| 70 | jQuery | `/api/cdn/jquery` | `.../jquery/dist/jquery.min.js` |
| 72 | sortablejs（拖拽排序） | `/api/cdn/sortable` | `.../sortablejs/Sortable.min.js` |

> 注释中已停用项：56–57 preconnect、61 google-fonts 合并链接、67–68 amap-loader（改由 `load_amap_watermark.js` 引入）。

#### 本地资源（74–76）

| 行 | 资源 |
|---|---|
| 74 | `styles/style.css`（全局样式） |
| 75 | `scripts/main.new.js`（`defer`，主应用逻辑） |
| 76 | `/editor.md/css/editormd.css` |

#### 内联 `<style>`（77–216）

针对 `#newbie-help-btn` 与 `#newbie-help-modal` 的样式，以及 `.btn-neo`（`.confirm`/`.cancel`）按钮样式。关键规则：
- `@media (max-width:768px)` 时 `#newbie-help-btn { display:none !important }`（78–82）
- `#newbie-help-btn`：flex、`min-width:64px`、`height:48px`、`touch-action:none`、禁止选中（84–103）
- `#newbie-help-modal`：`position:fixed; inset:0; display:none;`（**初始隐藏**）`z-index:10001`（104–111）；`.modal-backdrop` 半透明模糊；`.modal-card` 白蓝渐变卡片、有进出场 transform 过渡；`.show .modal-card` 触发显示动画（134–136）
- `body.mobile-mode #newbie-help-btn { display:flex !important }`（213–215）——移动模式强制显示帮助按钮

#### CodeMirror 全家桶（218–398）

编辑器核心 + 语法高亮 + 增强插件，均 `/api/cdn/codemirror-*` + onerror 回退到 `cdn.jsdelivr.net/npm/codemirror/...`：

- **核心**（226–253）：`codemirror-js`、`codemirror-css`、`codemirror-dialog-css`、`codemirror-matchesonscrollbar-css`、`codemirror-foldgutter-css`
- **语言高亮**（260–318）：`meta-js`、`markdown-js`、`xml-js`、`javascript-js`、`css-js`、`htmlmixed-js`、`gfm-js`、`python-js`、`clike-js`、`shell-js`、`sql-js`、`yaml-js`
- **编辑增强**（325–398）：`matchbrackets-js`、`closebrackets-js`、`closetag-js`、`foldcode-js`、`foldgutter-js`、`brace-fold-js`、`xml-fold-js`、`markdown-fold-js`、`overlay-js`、`active-line-js`、`search-js`、`searchcursor-js`、`match-highlighter-js`、`dialog-js`、`placeholder-js`

#### KaTeX 数学公式（400–414）

`/api/cdn/katex-js`（回退 `.../katex/dist/katex.js`）+ `/api/cdn/katex-css`（回退 `.../katex/dist/katex.css`）。

#### 流程图 / 时序图（416–483）

| 行 | 资源 | 回退 |
|---|---|---|
| 421 | raphael-js | `.../raphael/raphael.js` |
| 426 | underscore-js | `.../underscore/underscore.js` |
| 431 | flowchart-js | `.../flowchart.js/release/flowchart.js` |
| 436–457 | **内联脚本** `window.__maybeLoadJqueryFlowchart` | 惰性加载 jquery.flowchart，等待 `jQuery.widget` 就绪 + `document.readyState==="complete"`，否则监听 `load` 事件后再加载 `/api/cdn/jquery-flowchart-js`（回退 `.../jquery.flowchart/jquery.flowchart.js`） |
| 458–462 | jquery-ui-js | `onload="window.__maybeLoadJqueryFlowchart()"`；回退 `.../jquery-ui-dist/jquery-ui.min.js` |
| 463–467 | jquery-ui-widget-js | `onload="window.__maybeLoadJqueryFlowchart()"`；回退 `.../jquery-ui/ui/widget.js` |
| 468 | jquery-flowchart-css | `.../jquery.flowchart/jquery.flowchart.css` |
| 475 | sequence-diagram-js | `@rokt33r/js-sequence-diagrams/dist/sequence-diagram-min.js` |
| 479 | sequence-diagram-css | `@rokt33r/js-sequence-diagrams/dist/sequence-diagram-min.css` |

#### Markdown 解析与代码高亮（485–498）

- 490 `marked-js` → `.../marked/lib/marked.umd.min.js`
- 495 `prettify-js` → `.../gh/google/code-prettify@master/loader/run_prettify.js`

#### Editor.md 与 PWA SW 注册（500–520）

- 501 `<script src="/editor.md/editormd.js">`
- 504–520 **内联脚本**：`if ("serviceWorker" in navigator)` → `window.load` 时 `navigator.serviceWorker.register("/sw.js", { scope:"/" })`，成功/失败均 console 输出。

`</head>` 于 521 行，`<body class="text-slate-800 font-sans h-screen overflow-hidden antialiased">` 于 523 行。

---

## B. `#admin-return-overlay` — 返回管理员会话浮层（523–538）

- 容器 `div#admin-return-overlay`，class `fixed top-4 left-4 z-[10000] hidden`（**初始 hidden**），内联 `style="touch-action:none; user-select:none"`（支持拖拽）。
- 内部按钮 `button#admin-return-btn`，class 含 `cursor-move`（可拖动），文案 **「返回管理员会话」**（536）。
- 事件：**JS 绑定**（main.new.js）。SVG 图标被注释（533–535）。

---

## C. `#newbie-help-btn` — 新手帮助悬浮按钮（540–563）

- `button#newbie-help-btn`，`title="新手帮助"`，`aria-label="新手帮助"`。
- 内联 `style="top:100px; right:1rem; bottom:auto; left:auto"`；class `fixed ... z-[10001] ... touch-none select-none`（可拖拽、悬浮）。
- 内含问号 SVG 图标 + `<span>帮助</span>`（562）。
- 可见性：默认 CSS 控制（移动端 `display:none`，`body.mobile-mode` 或配置启用时 `display:flex`）；点击事件在下方内联脚本 E 中绑定（`openNewbieModal`）。

---

## D. `#newbie-help-modal` — 新手帮助模态框（565–629）

- 容器 `div#newbie-help-modal`，`aria-hidden="true"`；**初始 `display:none`**（由 `<style>` 控制，脚本 E 通过 `style.display="flex"`/`"none"` 切换）。
- 结构：
  - `.modal-backdrop`（566）——**内联** `onclick="closeNewbieModal()"`
  - `.modal-card`（`role="dialog" aria-modal="true" aria-labelledby="newbie-help-title"`）
    - header：信息 SVG + `<h3 id="newbie-help-title">即将前往新手帮助</h3>`（593）
    - `div#newbie-help-url` → `.url-row`：
      - `a#newbie-help-link`（`href="#" target="_blank" rel="noopener noreferrer"`，文本占位 `--`）
      - `button#newbie-help-copy.btn-copy`（`title="复制链接"`，文案「复制」）
    - `.modal-actions`：
      - `button#newbie-help-cancel.btn-neo.cancel`（「取消」）
      - `button#newbie-help-confirm.btn-neo.confirm`（「前往」）
    - `button.modal-close`（`aria-label="关闭弹窗"`，**内联** `onclick="closeNewbieModal()"`，符号 `×`）
- 文案要点：标题「即将前往新手帮助」，确认按钮「前往」。

---

## E. 新手帮助行为脚本（内联 IIFE，631–754）

一个立即执行函数，负责整个新手帮助功能的行为逻辑：

- **`applyConfig()`**（633–657）：读 `window.APP_CONFIG`；若 `conf.show_newbie_help` 为真 → 按钮 `display:flex`，把 `conf.newbie_help_url` 写入 `#newbie-help-link` 的文本与 `href`，复制按钮按 URL 有无显隐；否则按钮 `display:none`。
- **`openNewbieModal()`**（659–661）：`#newbie-help-modal` `style.display="flex"`。
- **`window.closeNewbieModal()`**（662–664）：`display="none"`（全局暴露，供 D 中内联 `onclick` 调用）。
- **`DOMContentLoaded`**（666–752）：
  - 调 `applyConfig()`；若配置启用且存在 `makeDraggable`（**外部函数，main.new.js**）则 `makeDraggable("newbie-help-btn")` 使按钮可拖拽（673）。
  - 按钮 click：若 `btn._hasMoved()` 为真（发生拖动）则阻止；否则 `openNewbieModal()`。
  - `#newbie-help-cancel` → `closeNewbieModal`。
  - `#newbie-help-copy` → 复制 `APP_CONFIG.newbie_help_url`（优先 `navigator.clipboard.writeText`，回退 `textarea + execCommand('copy')`），成功后文案变「已复制」1.5s 复原。
  - `#newbie-help-confirm` → `window.open(url,"_blank")`（置 `opener=null`；异常回退 `location.href=url`），随后关闭模态框。
  - 全局 `keydown`：`Escape` → `closeNewbieModal()`。

> **复刻关键函数名：`closeNewbieModal`、`openNewbieModal`、`applyConfig`、`makeDraggable`（外部）、`_hasMoved`（拖拽标记）。**

---

## F. `#exit-app-btn` — 退出应用按钮（756–775）

- `button#exit-app-btn`，`title="退出应用"`；class `fixed bottom-[170px] right-4 z-[9999] ... touch-none select-none`（可拖拽悬浮）。
- 内含退出 SVG + 文案 **「退出应用」**。
- 事件：**JS 绑定**。

---

## G. `#cdn-error-overlay` — CDN 资源加载失败遮罩（777–834）

- 容器 `div#cdn-error-overlay`，class `fixed inset-0 z-9999 hidden flex-col items-center justify-center bg-[#f8fafc] ...`（**初始 hidden**，出错时由 JS 显示）。
- 文案（纯展示、无交互元素）：
  - 标题 `<h1>` **「界面资源加载失败」**（红色 #be123c）
  - 说明段：应用无法连接 CDN 下载界面文件（样式、地图库）。
  - `<h2>`「可能的原因及解决方法：」+ `<ul>` 三条：**检查网络连接** / **检查防火墙或代理** / **网络环境问题**。
  - 结尾提示：请检查网络后完全关闭并重启程序。
- 无按钮/输入。

---

## H. 游客模式警告（836–905）

### H.1 `#guest_warning_overlay`（836–839）
- `div#guest_warning_overlay`，class `fixed inset-0 bg-black bg-opacity-50 z-[20000] hidden`（**初始 hidden**，背景遮罩）。

### H.2 `#guest-warning-toast`（841–905）
- 容器 `div#guest-warning-toast`，class 含 `fixed top-1/2 left-1/2 ... z-[20001] rounded-2xl hidden shadow-2xl ... border-4 border-red-500`（**初始 hidden**），内联渐变背景 `linear-gradient(135deg,#fef3c7,#fde68a)`。
- 关闭按钮 `button#guest-warning-close-btn`（`title="关闭提示"`、`aria-label="关闭提示"`，×形 SVG），**JS 绑定**。
- 内层 `div.flex.items-start id="guest_warning"`（866）——即任务点名的 `#guest_warning`：
  - 左侧警告三角 SVG（`animate-pulse`）。
  - 右侧内容：
    - `<h3>` **「⚠️ 游客模式重要提示」**
    - 段落一（红字加粗）：**「⚠️ 请立即保存当前网址！」** 丢失 URL 将无法恢复数据。
    - 段落二：**「功能限制：」** 无法标记通知已读、无法使用签到功能、无法执行多账号任务。
    - 段落三（琥珀色）：**「⏰ 自动清理：」** 5 分钟不活跃会话将被自动清理。
    - 段落四：建议「请注册账号以获得完整功能和永久数据保存」。
  - 无输入元素，仅关闭按钮交互。

---

## I. `#newUserModal` — 新建用户模态框（906–1039）

- 容器 `div#newUserModal.modal`（`.modal` 类默认隐藏，由 JS 加 `.active`/切换显隐）。
- 面板 `.panel.rounded-2xl.max-w-md`。
- 关闭按钮 `button#newUserClose`（`title="关闭"`，×SVG，**JS 绑定**）。
- 标题 `<h3>` **「添加新用户」**。
- 表单字段（无 `<form>` 包裹，纯 div+input）：

| 行 | label | input id | type | placeholder | 其他属性 |
|---|---|---|---|---|---|
| 934–946 | 账号 | `newUsername` | text | 请输入账号（3-20字符，不含中文） | `class="input-field mt-1"` |
| 948–963 | 手机号（可选） | `newUserPhone` | tel | 请输入手机号 | `inputmode="numeric" pattern="[0-9]*" maxlength="11"` |
| 965–990 | 验证码（可选）**`#newUserSmsGroup`** | `newUserSmsCode` | text | 请输入验证码 | `maxlength="6" inputmode="numeric" pattern="[0-9]{6}"` |
| 992–1004 | 昵称 | `newUserNickname` | text | 请输入昵称（可含中文） | |
| 1006–1018 | 密码 | `newPassword` | password | 请输入密码（至少6字符） | |
| 1020–1032 | 确认密码 | `newPasswordConfirm` | password | 请再次输入密码 | |

- **`#newUserSmsGroup`**（965）：外层 `div style="display:none"`（**初始隐藏**，有手机号时才显示）；内含 `#newUserSmsCode` 输入 + `button#newUserSendCode.btn.btn-primary`（文案「发送验证码」，`min-height:44px`，**JS 绑定**）。
- 底部按钮：`button#newUserCancel.btn.btn-ghost`（「取消」）、`button#newUserConfirm.btn.btn-primary`（「确认」）——均 **JS 绑定**。

---

## J. `#multi-add-user-modal` — 批量添加用户 · 单条录入模态框（1041–1119）

- 容器 `div#multi-add-user-modal.modal`（默认隐藏）。
- 关闭按钮 `button#multi-add-user-close`（×SVG，`title/aria-label="关闭"`，**JS 绑定**）。
- 标题 `<h3>` **「添加新账号」**。
- 字段：

| 行 | label | input id | type | placeholder |
|---|---|---|---|---|
| 1068–1080 | 账号 (必填) | `multi-add-username` | text | 请输入账号（例如学号） |
| 1081–1093 | 密码 (必填) | `multi-add-password` | password | 请输入密码 (至少6字符) |
| 1094–1106 | 标记 (可选) | `multi-add-tag` | text | 可选，用于分组 (例如: 'A组') |

- 底部：`button#multi-add-user-cancel.btn.btn-ghost`（「取消」）、`button#multi-add-user-confirm.btn.btn-primary`（`title/aria-label="确认添加"`，文案「确认添加」）——**JS 绑定**。

---

## K. `#school-accounts-modal` — 校园账号管理模态框（1121–1170）

- 容器 `div#school-accounts-modal.modal`（默认隐藏），面板 `max-w-4xl`。
- 关闭按钮 `button#school-accounts-close`（×SVG，**JS 绑定**）。
- 标题 `<h3>` **「School Accounts 管理」**；副标题「查看所有认证用户的学校账户密码」。
- 内容区 `div#school-accounts-content`（class `space-y-4 max-h-[60vh] overflow-y-auto`）——初始占位 `<p>加载中...</p>`，列表由 JS 动态填充。
- 底部：`button#school-accounts-refresh.btn.btn-ghost`（`title/aria-label="刷新学校账号列表"`，「刷新」）、`button#school-accounts-ok.btn.btn-primary`（「确定」）——**JS 绑定**。

---

## L. `#edit-school-account-modal` — 编辑校园账号模态框（1172–1381）

- 容器 `div#edit-school-account-modal`，class `fixed inset-0 hidden z-[20001] flex items-center justify-center p-4`（**初始 hidden**），内联半透明模糊背景。
- 内层卡片 `onclick="event.stopPropagation()"`（内联，阻止冒泡关闭）。
- 头部：编辑图标 + `<h3 id="edit-school-account-modal-title">编辑 School Account</h3>`；关闭按钮 **内联** `onclick="closeEditSchoolAccountModal()"`（×SVG）。
- 表单 `form#edit-school-account-form`：

| 行 | label | 字段 id | name | 类型/属性 | placeholder |
|---|---|---|---|---|---|
| 1243–1259 | 认证用户 (Auth Username) | `edit-school-account-auth-username` | `auth_username` | text · `readonly` | 认证用户名 |
| 1261–1278 | 学校账号用户名 (School Username) `*` | `edit-school-account-school-username` | `school_username` | text · `required` | 请输入学校账号用户名 |
| 1280–1296 | 密码 (Password) `*` | `edit-school-account-password` | `password` | text · `required` · font-mono | 请输入密码 |
| 1298–1341 | User Agent (UA) | `edit-school-account-ua` | `ua` | `<textarea rows="3">` | （可选）请输入 User Agent |
| 1343–1350 | （隐藏） | `edit-school-account-original-username` | `original_username` | `type="hidden"` | — |

- UA 区域右上「随机UA」按钮：**内联** `onclick="generateRandomUAForSchoolAccount()"`（1308），带刷新 SVG。其下提示：不填则用系统默认 UA，可点「随机UA」生成。
- 底部按钮：
  - 取消：**内联** `onclick="closeEditSchoolAccountModal()"`（1357）
  - 保存：**内联** `onclick="submitSchoolAccount()"`（1369）

> **复刻关键函数名：`closeEditSchoolAccountModal`、`generateRandomUAForSchoolAccount`、`submitSchoolAccount`。**

---

## M. `#loading-overlay` — 资源加载遮罩（1383–1389）

- `div#loading-overlay`，class `absolute inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-white/80`（**默认显示**，加载完成后由 JS 隐藏）。
- 内含 `.loader`（CSS 动画）+ `<p>` **「正在加载资源中...」**。

---

## N. `#captcha-verification-modal` — 图形验证码 / 安全验证模态框（1391–1539）

- 容器 `div#captcha-verification-modal`，class `fixed inset-0 hidden z-[10001] flex items-center justify-center p-4`（**初始 hidden**），半透明模糊背景。
- 内层卡片 `id="send_sms_code_modal_content_wrapper"`，**内联** `onclick="event.stopPropagation()"`。
- 头部：盾牌 SVG + `<h3>安全验证</h3>`；关闭按钮 **内联** `onclick="closeCaptchaModal()"`（1434）。
- 正文提示：「为保护您的账号安全，请完成以下验证」。
- 图形验证码区：
  - label「图形验证码」
  - 容器 `div#send_sms_code_captcha_container`
  - 显示框 `div#captcha-modal-display`——**内联** `onclick="refreshCaptchaModal()"`（1472，`title="点击刷新验证码"`，占位「加载中...」）
  - 刷新按钮 `button#modal-login-captcha-refresh`——**内联** `onclick="refreshCaptchaModal()"`（1483，刷新 SVG）
- 输入：`input#captcha-modal-input`（text，`maxlength="6" autocomplete="off"`，placeholder「请输入图形验证码」）。
- 底部按钮：
  - 取消：**内联** `onclick="closeCaptchaModal()"`（1519，`title/aria-label="取消"`）
  - `button#captcha-modal-confirm-btn`——**内联** `onclick="confirmCaptchaAndSendSMS()"`（1529，文案「确认发送」）

> **复刻关键函数名：`closeCaptchaModal`、`refreshCaptchaModal`、`confirmCaptchaAndSendSMS`。**

---

## O. `#auth-login-container` — 认证登录容器（1541–2157）

- 容器 `div#auth-login-container`，class `hidden h-screen w-screen flex items-center justify-center`（**初始 hidden**）。
- 面板 `div.panel id="auth-login-container_panel"`。
- 头部：`<h2>跑步助手</h2>` + `<p>请登录或注册以继续使用</p>`。

### O.1 登录/注册 Tab（1556–1573）
- `button#auth-tab-login`（「登录」，激活态高亮，`title/aria-label="切换到登录"`）
- `button#auth-tab-register`（「注册」，`title/aria-label="切换到注册"`）
- 事件 **JS 绑定**（切换下方两个表单显隐）。

### O.2 登录表单 `#auth-login-form`（1575–1782）
- `form#auth-login-form`，**内联** `onsubmit="return false;"`，`autocomplete="on"`，`class="... overflow-y-auto max-h-[60vh]"`。
- **登录方式切换** `div#auth-login-type-toggle`（1581–1603）：
  - `button#auth-login-username-btn`（「用户名登录」，默认激活）
  - `button#auth-login-phone-btn`（「手机号登录」）——**JS 绑定**。
- **账号输入**（1605–1621）：`label#auth-login-label`（默认「用户名」，随方式切换）；容器 `div#auth-username-container` → `input#auth-username name="username"`（placeholder「请输入用户名」，`autocomplete="username"`）。
- **密码区** `div#auth-password-section`（1623–1645）：label「密码」+ `button#auth-switch-to-sms`（「使用验证码登录」，默认 `hidden`）；`input#auth-password name="password"`（`autocomplete="current-password"`，placeholder「请输入密码」）。
- **短信验证码区** `div#auth-sms-section`（1647–1680，**初始 `hidden`**）：label「验证码」+ `button#auth-switch-to-password`（「使用密码登录」）；`input#auth-sms-code`（`maxlength=6 inputmode=numeric pattern=[0-9]{6}`）+ `button#auth-send-login-code.btn.btn-primary`（「发送验证码」）。
- **图形验证码区**（1682–1731）：
  - 显示框 `div#auth-login-captcha-display`（`title="点击刷新验证码"`，占位「加载中...」）
  - 刷新按钮 `button#auth-login-captcha-refresh`（刷新 SVG）
  - 输入 `input#auth-login-captcha`（`maxlength=6 autocomplete=off`，placeholder「请输入验证码」）
- **登录按钮** `button#auth-login-btn.btn.btn-primary.w-full`（「登录」，`title/aria-label="登录"`）。
- **游客登录区** `div#guest-login-section`（1742–1781，**初始 `hidden`**）：分隔线「或」；`button#auth-guest-btn.btn.btn-ghost`（「以游客身份继续」）；琥珀色提示卡：⚠️ 游客模式提示——UUID 恢复状态需保存地址 / 丢失 URL 无法恢复 / 5 分钟不活跃清理 / 建议注册。
- 上述按钮事件均 **JS 绑定**。

### O.3 注册表单 `#auth-register-form`（1784–1998）
- `form#auth-register-form`，class `hidden ...`（**初始 hidden**），**内联** `onsubmit="return false;"`。
- 字段：

| 行 | label | 字段 id | 属性 | placeholder |
|---|---|---|---|---|
| 1790–1802 | 用户名 | `auth-reg-username`（name=username） | `autocomplete="username"` | 请输入用户名（3-20字符，不含中文） |
| 1804–1821 | 手机号（`#auth-reg-phone-wrapper`） | `auth-reg-phone` | tel · `inputmode=numeric pattern=[0-9]* maxlength=11`，前缀 `+86` | 请输入手机号 |
| 1823–1847 | 验证码（`#auth-reg-sms-wrapper`） | `auth-reg-sms-code` + `button#auth-reg-send-code-btn`（「发送验证码」） | `maxlength=6 inputmode=numeric pattern=[0-9]{6}` | 请输入验证码 |
| 1849–1859 | 昵称 | `auth-reg-nickname` | | 请输入昵称（可含中文） |
| 1861–1904 | 头像 | `img#auth-reg-avatar-preview`（src `/static/default_avatar.png`）+ `input#auth-reg-avatar type=file accept=image/*`（`hidden`）+ 上传按钮 | 上传按钮 **内联** `onclick="document.getElementById('auth-reg-avatar').click(); return false;"` | — |
| 1906–1918 | 密码 | `auth-reg-password`（name=new-password） | `autocomplete="new-password"` | 请输入密码（至少6字符） |
| 1919–1931 | 确认密码 | `auth-reg-password-confirm`（name=new-password-confirm） | `autocomplete="new-password"` | 请再次输入密码 |
| 1933–1977 | 图形验证码 | 显示框 `div#auth-register-captcha-display` + 刷新 `button#auth-register-captcha-refresh` + 输入 `input#auth-register-captcha`（`maxlength=6`） | | 请输入验证码 |

- **注册赠送提示** `div#auth-register-available-runs-hint`（1979–1987，**初始 hidden**）：🎁 + `<span id="auth-register-runs-text">`（JS 填充）。
- **注册按钮** `button#auth-register-btn.btn.btn-success.w-full`（「注册」，`title/aria-label="注册"`）。
- 事件均 **JS 绑定**。

### O.4 `#auth-2fa-form` — 双因素认证表单（2000–2039）
- `div#auth-2fa-form`，class `hidden space-y-4`（**初始 hidden**）。
- 头部：`<h3>双因素认证</h3>` + `<p>请输入您的验证器应用中的6位验证码</p>`。
- `div#auth-2fa-code-wrapper`（注释说明：为避免与 SMS 冲突而重命名）：label「验证码」+ `input#auth-2fa-code`（`maxlength=6 inputmode=numeric pattern=[0-9]{6} autocomplete=one-time-code`，placeholder「输入6位验证码」）。
- 按钮：`button#auth-2fa-verify-btn.btn.btn-primary`（「验证」，`title/aria-label="验证二次认证"`）、`button#auth-2fa-back-btn.btn.btn-ghost`（「返回登录」，`title/aria-label="返回"`）。
- 事件 **JS 绑定**。

### O.5 认证结果提示（2041–2048）
- `div#auth-error-msg`（`hidden ... bg-red-50 text-red-600`，JS 填充错误文案）。
- `div#auth-success-msg`（`hidden ... bg-green-50 text-green-600`，JS 填充成功文案）。

### O.6 备案 footer `#auth-beian-footer`（2050–2155）
- 容器 `div#auth-beian-footer`（**始终可见**，无 hidden——保持布局稳定，注释详述设计意图）。
- 内层 flex 容器包两条链接（**默认 `style="display:none"`**，由 JS `updateBeianSection` 依后端配置显隐）：
  - ICP 备案 `a#auth-icp-beian-link`（`href="https://beian.miit.gov.cn" target="_blank" rel="noopener noreferrer"`）+ 文档 SVG + `<span id="auth-icp-beian-text">`（JS 填充备案号）。显示条件：`show_icp=true && icp_number`。
  - 公安备案 `a#auth-police-beian-link`（`href="https://beian.mps.gov.cn"` 同上属性）+ 盾牌 SVG + `<span id="auth-police-beian-text">`。显示条件：`show_police=true && police_number`。

> **复刻关键函数名：`updateBeianSection`（备案显隐控制）。**

`#auth-login-container` 于 2157 行结束；随后 2159–2161 为注释，**2162 行 `<div id="desktop-container">` 起始**（本文覆盖终点）。

---

## 复刻要点 · 引用的关键 JS 函数名汇总

| 函数 / 全局标识 | 出处 | 用途 |
|---|---|---|
| `closeNewbieModal` / `openNewbieModal` / `applyConfig` | 内联脚本 E | 新手帮助模态框显隐与配置 |
| `makeDraggable` | E（外部，main.new.js） | 悬浮按钮拖拽（`newbie-help-btn` 等） |
| `_hasMoved` | E | 拖拽后抑制点击 |
| `window.__maybeLoadJqueryFlowchart` | head 436–467 | 惰性加载 jquery.flowchart |
| `closeEditSchoolAccountModal` / `generateRandomUAForSchoolAccount` / `submitSchoolAccount` | L | 编辑校园账号 |
| `closeCaptchaModal` / `refreshCaptchaModal` / `confirmCaptchaAndSendSMS` | N | 图形验证码 / 发送短信 |
| `updateBeianSection` | O.6（注释引用） | 备案链接显隐 |
| `event.stopPropagation()` | L/N 内层卡片 | 阻止点击背景冒泡关闭 |

**全局配置依赖：** `window.APP_CONFIG`（来自 `/api/frontend_config.js`），字段含 `show_newbie_help`、`newbie_help_url`，以及备案相关 `show_icp`/`icp_number`/`show_police`/`police_number`。

**`.modal` 类约定：** `#newUserModal`/`#multi-add-user-modal`/`#school-accounts-modal` 使用统一 `.modal` 类（默认隐藏，JS 切换 active）；其余模态框用 `hidden` + `style.display` 控制。
