# 30 · CSS 与辅助脚本解析（复刻依据）

> 解析对象：`styles/style.css`（约 57 KB）+ 4 个辅助脚本。
> 目的：为 Vue 重构版提供逐项复刻依据。凡样式类名、CSS 变量、动画、辅助脚本全局函数均已收录，不得遗漏。
> 生成时间：2026-07-14

---

## 一、`styles/style.css` 全局样式

### 1. CSS 自定义属性（CSS Variables）

全部定义在 `:root` 中（style.css L460-468）。这是主题色体系的唯一来源，Vue 版应原样保留：

| 变量名 | 默认值 | 用途 |
|---|---|---|
| `--base-color` | `#7dd3fc`（sky-300） | 主题基础色（浅蓝），用于 `.btn-primary` 渐变起点 |
| `--base-color-600` | `#0891b2`（cyan-600） | 主题深色，用于按钮渐变终点、聚焦边框、`.badge`、`.tab-button.active`、选中态左边框 |
| `--base-color-500` | `#22d3ee`（cyan-500） | 主题中间色（当前 CSS 内未直接引用，预留供 JS 主题切换） |
| `--base-color-300` | `#a5f3fc`（cyan-200/300） | 主题浅色（预留） |
| `--card-bg` | `rgba(255, 255, 255, 0.85)` | 玻璃拟态卡片 `.panel` 的背景色 |
| `--glass` | `rgba(255, 255, 255, 0.65)` | 玻璃背景（预留，未直接引用） |
| `--ink` | `#0f172a`（slate-900） | 主文字色（预留，未直接引用；`.input-field` 用同值硬编码） |

> 注意：`--base-color` / `--base-color-600` 会被主题切换逻辑（JS 中的 `.theme-dot` 交互）动态改写，复刻时须保证 CSS 变量可被 JS 运行时覆盖。

### 2. 全局基础样式

| 选择器 | 关键属性 | 说明 |
|---|---|---|
| `body` | `background: linear-gradient(180deg, #f5faff→#ebf5ff(40%)→#faf0ff)`；`background-attachment: fixed` | 页面浅蓝到浅紫的固定渐变背景（**定义了两次**，L1-9 与 L475-483 内容一致） |
| `html, body` | `height: 100%` | |
| `.bg-anime` | `background-image: url("")`；`cover`；`center` | 预留的动漫背景图容器（图片 URL 为空，运行时注入） |
| `.hero-overlay` | 白色半透明自上而下渐变 | 顶部 Hero 遮罩 |

### 3. 玻璃拟态面板 `.panel`

- `.panel`（L11/L491）：`backdrop-filter: blur(16px)`，背景 `var(--card-bg)`，半透明白边框，柔和投影。核心毛玻璃卡片。

### 4. 按钮体系 `.btn` 系列

| 类名 | 背景 / 颜色 | 说明 |
|---|---|---|
| `.btn` | 圆角 `999px`（胶囊）、`font-weight:700`、`inline-flex` 居中、青色投影 | 按钮基类；`:hover` 加深投影（无位移），`:disabled` 半透明不可点 |
| `.btn-primary` | `linear-gradient(135deg, var(--base-color), var(--base-color-600))`，白字 | 主按钮（随主题变色） |
| `.btn-secondary` | `linear-gradient(135deg, #a855f7, #7c3aed)`，白字 | 紫色次按钮 |
| `.btn-danger` | `linear-gradient(135deg, #ef4444, #b91c1c)`，白字 | 危险红 |
| `.btn-warning` | `linear-gradient(135deg, #f59e0b, #d97706)`，白字 | 警告橙 |
| `.btn-success` | `linear-gradient(135deg, #10b981, #059669)`，白字 | 成功绿 |
| `.btn-ghost` | `rgba(255,255,255,0.7)` 背景 + 灰边框，`#334155` 字 | 幽灵按钮 |
| `.btn-loading` | `pointer-events:none`、`opacity:0.85`，`::after` 旋转 spinner | 加载态；spinner 用 `@keyframes cr-spin` |

### 5. 表单输入体系

| 类名 | 说明 |
|---|---|
| `.input-field` / `.select-field` | 圆角 `14px`，白色垂直渐变背景，内外双层阴影，聚焦时边框变 `--base-color-600` 且外发光 `rgba(34,211,238,.25)` |
| `select.select-field` | 覆写 `padding: 0.45rem 0.6rem` |
| `.phone-input-wrapper` | 手机号输入容器（flex 横排），`:focus-within` 时整体外发光；内部 `.input-field` 去边框透明 |
| `.phone-prefix` | 手机号前缀（如 +86），`user-select:none`、灰色、不换行 |
| `.phone-input-wrapper.prefix-hidden .input-field` | 前缀隐藏时恢复左内边距 |
| `#multi-config-user-select` | 多配置用户下拉：`white-space:nowrap`、横向滚动、`max-width:100%`；`option` 溢出省略号 |

### 6. 其他 UI 组件

| 类名 / id | 说明 |
|---|---|
| `.badge` | 胶囊标签，`rgba(34,211,238,0.18)` 底 + `--base-color-600` 字 |
| `.card-title` | 卡片标题，`font-family:"Zilla Slab", serif`，字距 0.5px |
| `.tab-button` / `.tab-button.active` | 标签页按钮，激活态变主题色 + 底部 3px 边框 |
| `#task-list > div.selected` | 任务列表选中项：淡青底 + 左侧 4px 主题色边框 |
| `.theme-dot` / `:hover` | 20px 圆形主题色选择点，hover 放大 1.05 |
| `.pulsing-marker` | 地图脉冲标记，应用 `@keyframes pulse` |
| `#map-container.drawing .amap-*` | 绘制模式下禁用高德覆盖物指针事件 |
| `#admin-modal-close-btn:hover` | `transform: translateY(-50%)` |

### 7. 模态框体系 `.modal` / `.modal-content`

| 选择器 | 说明 |
|---|---|
| `.modal` | 全屏遮罩：`display:none` 默认隐藏、`position:fixed`、`z-index:1000`、`rgba(0,0,0,0.4)` 半透明底、flex 居中 |
| `.modal-content` | 弹窗主体：白色渐变底、圆角 16px、宽 360px、双层阴影 + 蓝色外发光、入场动画 `fadeIn + scaleIn`；字体 `"Segoe UI","Microsoft YaHei"` |
| `.modal-content h3` | 居中标题，20px，`#3a4a7a`，字距 1px |
| `.close` / `:hover` | 右上角 × 关闭按钮，hover 变粉 `#ff5c8a` |
| `.form-group` / `label` / `input` / `input:focus` | 弹窗内表单组：label 定宽 70px 加粗，input 定宽 230px、聚焦蓝边外发光 |
| `.modal-actions` / `button` | 弹窗底部按钮区，右对齐 |
| `#newUserCancel` / `:hover` | 新建用户取消按钮（浅灰） |
| `#newUserConfirm` / `:hover` | 新建用户确认按钮（蓝紫渐变 + 投影） |

#### 拟态（Neumorphism）风格弹窗

- `.modal-content.neumorphic` 与 `.neumorphic-modal .modal-content`（两种写法等价）：`#e8ecf4` 底 + 双向 12px 拟态阴影、圆角 20px。
- 其内部 `input/select/textarea`：内凹阴影；`:focus` 加深内凹。
- 其内部 `button`：外凸阴影；`:hover` 上浮 2px、`:active` 内凹；`button.btn-primary` 用蓝色渐变 `#7aa3ff→#6b8ee6`。

### 8. 关键帧动画 `@keyframes`

| 动画名 | 效果 | 使用者 |
|---|---|---|
| `fadeIn` | `opacity 0→1` | `.modal-content`、`#mobile-status-indicator` |
| `scaleIn` | `scale(0.9)→1` | `.modal-content` |
| `pulse` | 缩放 0.98↔1 + 外扩投影环 `rgba(2,132,199,…)` | `.pulsing-marker`、移动端地图占位 SVG |
| `cr-spin` | `rotate(360deg)` | `.btn-loading::after` 加载圈 |

### 9. 深色模式（`body.dark-mode`）

深色模式通过 `body.dark-mode` 类前缀切换（**非** `prefers-color-scheme`，PC 端由 JS 手动切换）。覆写范围（L19-231）：

- **面板/输入/按钮**：`.panel`、各类 input/select/textarea、`.btn` 及其 primary/success/warning 变体。
- **模态框**：`.modal-content`（深灰渐变）、`.modal-content h3`、以及深色版拟态弹窗（`#2d3748` 底 + 深色拟态阴影）。
- **表格**：`table` / `th` / `td` / `tr:hover`。
- **Tailwind 工具类覆写**：`.bg-slate-50`、`.border-slate-200`、`.text-slate-700/600/400`、`.bg-red-50/green-50/blue-50/yellow-50`、`.border-red-200/green-200/blue-200/yellow-200`（把浅色 Tailwind 语义色改成深色半透明版）。
- **链接**：`a` → `#60a5fa`，`:hover` → `#93c5fd`。
- **滚动条**：`::-webkit-scrollbar` 系列深色化。
- **登录容器渐变**：`#login-container .bg-gradient-to-br` 深色渐变。

> 复刻要点：深色模式主要靠「覆写 Tailwind 语义类 + 自定义类」实现，Vue 版若继续用 Tailwind，需保留这批同名覆写。

### 10. 浅色默认滚动条

`::-webkit-scrollbar`（10px）、`-track`（`rgba(226,232,240,0.6)`）、`-thumb`（灰色圆角带边框）、`-thumb:hover`（加深）。

### 11. 地图水印隐藏逻辑（重要）

L738-772 一大段选择器：当特定模态框（`#amap-key-modal`、`#user-details-modal`、`#task-details-modal`、`#account-params-modal`）显示（`:not(.hidden)`）或 `body.modal-visible` 时，用 `display:none !important; z-index:-1 !important` 隐藏高德/天地图/百度地图的 logo、版权、`.smnoprint`、`.tdt-control-container`、`.BMap_cpyCtrl`、`.anchorBL` 等水印元素；同时 `body.modal-visible` 下把各地图容器（`#map-container`、`#multi-map-container`、`#mobile-map-container` 等）设为 `isolation:isolate; pointer-events:none`。

### 12. SweetAlert2（swal2）相关

| 选择器 | 说明 |
|---|---|
| `html.swal2-shown` / `body.swal2-shown:not(.swal2-toast-shown)` | 修复弹窗时 `padding-right:0`、保留滚动条，防登录框位移（"问题4"） |
| `.swal2-container` | `z-index:2147483647 !important`（最高层级） |
| `body.swal2-shown #auth-login-container / #mobile-auth-login-container` | 消除滚动条补偿导致的登录容器偏移（"任务11"） |
| `.swal2-popup` | 圆角 16px |
| `.swal2-neumorphism-popup/-title/-confirm/-cancel`（含 hover/active） | 拟态风格弹窗整套：渐变底 + 拟态阴影 + 立体按钮 |
| `.swal-flat-popup` / `.swal-flat-button`（含 hover） | 扁平无阴影弹窗风格，蓝色扁平按钮 |
| `.swal2-clean-popup/-title/-btn:focus` | 干净风格：柔和阴影、去按钮发光 |
| `.swal2-confirm:focus` / `.swal2-cancel:focus` | 彻底去除默认按钮 glow |

### 13. 通用模态框层级修复

- `#sms-history-modal`、`#verification-codes-modal`、`#sms-test-modal`：`z-index:20002`（移动端可见性修复"问题1"）。
- `#admin-payment-logs-panel_modal`、`#admin-billing-panel_modal`、`#admin-watermark-control-panel_modal`、`#admin-payment-settings-panel_modal`：`margin-top:0`。

### 14. 支付系统占位样式

- `.orders-filter-btn` / `.orders-filter-btn.active`：订单筛选按钮，实际样式由 Tailwind 类 + JS 动态添加（`bg-sky-500`、`text-white`），CSS 中仅占位注释。

### 15. 响应式断点

| 断点 | 主要规则 |
|---|---|
| `@media (max-width: 768px)` | 弹窗/面板宽 90%；按钮与输入 `min-height:44px`、`font-size:16px`（触控友好、防 iOS 缩放）；`.flex.gap-3/4` 改纵向；`admin-tab` 加大；`grid-cols-2/3/4` 全部改单列 |
| `@media (max-width: 480px)` | 弹窗/面板宽 95%；`h1/.text-xl→20px`、`h2/.text-lg→18px`、`h3/.text-base→16px`；`.flex.gap-1/2` 改纵向且按钮全宽 |
| `@media (orientation: landscape) and (max-height: 500px)` | 横屏矮屏：压缩移动端 header(48px)/bottom-nav(56px)/card、地图高 200px、列表 `max-height:30vh`；侧边栏内边距压缩 |
| `@media (prefers-color-scheme: dark)` | 移动端系统深色：`#mobile-container` 深色渐变、mobile-card/header/nav/title/subtitle/input 深色化；侧边栏深色化 |

### 16. 桌面强制模式 `body.desktop-forced-mode`（L895-1045）

手机浏览器选择"查看桌面网站"时触发。强制恢复 PC 双列/多列布局，避免地图掉到下方：

- `#main-app` 强制 `grid-template-columns: minmax(400px,44%) minmax(0,56%)`；重排 `#user-info-section-desktop-inline`、`#task-panel/section-desktop-inline`、`#map-container`、`#status-panels`。
- `#multi-account-app` 强制 `530px minmax(0,1fr)`；`#multi-account-list` 可滚动；一批 `#multi-*-btn` 加 `white-space:nowrap`。
- `#login-container` 强制三列；`.flex.gap-3/4` 恢复横排。
- 全局 `min-width:1280px`、`overflow-x:auto`，`#desktop-container/#login-container/#main-app/#multi-account-app` 均设 `min-width:1280px`。
- `grid-cols-2/3/4` 用 `revert` 恢复默认多列。

### 17. 移动端专用容器与组件（`body.mobile-mode` / `#mobile-container`）

移动端是**独立的 DOM 容器体系**，通过 `body.mobile-mode` 前缀激活。核心结构：

| 类名 / id | 说明 |
|---|---|
| `#mobile-container` | 移动端根容器，`display:none` 默认、`position:fixed`、100vh、`z-index:10000`、渐变背景 |
| `#desktop-container` | PC 根容器（后段 L1873 重定义为 `display:flex; flex-direction:column`，配合备案 footer） |
| `body.mobile-mode` | 16px 字号、禁横向滚动、`touch-action:pan-y`、去点击高亮 |
| `body.mobile-mode #desktop-container / #auth-login-container / #login-container / #main-app / #multi-account-app` | 移动端下强制隐藏 PC 容器（`display:none;visibility:hidden;pointer-events:none;z-index:-1`） |

移动端组件类（`.mobile-mode` 前缀）：

- **布局**：`.mobile-header`（固定顶栏 56px 毛玻璃）、`.mobile-content`（上下留白避开顶/底栏）、`.mobile-bottom-nav`（底部导航 64px，**后段 L1812 被 `display:none` 关闭**改用侧边栏）、`.mobile-nav-btn` / `.active` / `svg`。
- **卡片/表单**：`.mobile-card`、`.mobile-card-fullscreen`（全屏卡片 `height:calc(100vh - 60px)`）、`.mobile-form-group`、`.mobile-form-label`。
- **按钮**：`.mobile-primary-btn`（蓝渐变全宽 50px）、`.mobile-secondary-btn`（白底蓝边）、通用 `.btn/button`（`min-height/width:44px`、`:active` 缩放 0.95）。
- **列表/分隔**：`.mobile-list-item`（`:active` 缩放）、`.mobile-divider`、`.mobile-title`、`.mobile-subtitle`、`.mobile-empty-state`、`.mobile-loading`。
- **控件**：`.mobile-switch` / `.active` / `::after`（自定义开关，圆钮左右滑）。
- **底部弹窗**：`.mobile-modal`（`z-index:20000`、底部对齐、`.show` 淡入）、`.mobile-modal-content`（从底部上滑 `translateY(100%)→0`、圆角顶、`env(safe-area-inset-bottom)` 适配）。
- **输入**：`.mobile-mode input/select/textarea`（44px、16px、圆角、`:focus` 蓝边 + `scale(1.02)`）；移动版 `.phone-input-wrapper` / `.phone-prefix` 重定义。

移动端具体容器专项样式（`.mobile-mode #xxx`）：

- 通知列表 `#mobile-all-notifications-list` / `#mobile-attendance-notifications-list`：list-item 左边框状态色（未读蓝、`.opacity-60` 无边框）。
- 任务面板 `#mobile-task-panel .mobile-list-item`：绿色左边框。
- 地图 `#mobile-map-container`：`touch-action:pan-x pan-y`；占位 SVG 用 `pulse` 动画。
- 控制面板 `#mobile-control-panel button:disabled`：灰化。
- **状态指示器** `#mobile-status-indicator`：`.status-idle`（灰）/`.status-running`（绿）/`.status-paused`（黄）/`.status-error`（红）。
- 进度条 `#mobile-progress-bar`：`transition: width 0.5s`。
- 多账号 `#mobile-multi-account-list`：list-item 左内边距 48px 放复选框（绝对定位居中）。
- **账号状态徽章** `.account-status-badge` + `.account-status-running`（绿）/`-stopped`（灰）/`-error`（红）。
- 一批列表在窄屏/滚动区强制 `padding-bottom`（`#mobile-task-list`、`#mobile-*-notifications-list`、`#mobile-multi-account-list`、`#mobile-admin-panel-content` 等）。

### 18. 移动端侧边栏导航（L1698-1851）

替代底部导航的抽屉式侧边栏：

- `.mobile-sidebar-backdrop` / `.show`：半透明遮罩，淡入淡出。
- `.mobile-sidebar` / `.show`：宽 280px，从左 `translateX(-100%)→0` 滑入，`z-index:9999`，毛玻璃。
- `.mobile-sidebar-header`（蓝渐变头 + `.sidebar-title` + svg）、`.mobile-sidebar-menu`、`.mobile-sidebar-item`（`:hover`/`:active` 反馈 + 左边框）、`.mobile-sidebar-item.danger`（红色危险项）。
- 深色模式与横屏矮屏各有覆写。

### 19. 备案 Footer

- PC：`#pc-beian-footer`（`position:fixed` 底部、毛玻璃、`z-index:50`）；`#auth-login-container/#main-app/#multi-account-app` 加 `padding-bottom:20px` 留位。
- 移动：`#mobile-beian-footer`（`padding-bottom:calc(120px + env(safe-area-inset-bottom,20px))` 避开导航/工具栏与刘海屏）。

### 20. 移动端日志文本框

`#mobile-log-text` / `#mobile-multi-log-text`：`min-height:400px`、`height:auto`（随内容增长）、`overflow:visible`（不裁剪）。

### 21. 被注释掉的样式（复刻时可忽略，但需知晓）

文件末尾 L2183-2362 一整段（`.mobile-reminder-markdown-content` 与 `.pc-reminder-markdown-content` 系列，用于 editor.md 渲染 Markdown 的紧凑排版）被包在 `/* ... */` 块注释内，**当前未生效**。若 Vue 版提醒列表需渲染 Markdown，可参考这段（含 p/ul/ol/li/code/pre/h1-6/blockquote/img/a/table 的字号与间距覆写）。

---

## 二、辅助脚本（4 个）

4 个脚本均在 `index.html <head>` 顶部**同步加载**（无 async/defer），加载顺序见下：

```html
<!--[if lt IE 9]> ... window.location.href="/ie_basic.html" <![endif]-->  <!-- 条件注释：IE<9 -->
<!--[if (IE 9)]> ... window.location.href="/ie.html" <![endif]-->         <!-- 条件注释：IE9 -->
<script src="/scripts/ie_detect.js"></script>            <!-- 15 -->
<script src="/scripts/Check_for_updates.js"></script>    <!-- 16 -->
<script src="/scripts/load_amap_watermark.js"></script>  <!-- 17 -->
<!-- <script src="/scripts/Remove_watermark_from_Amap_Map.js"></script> --> <!-- 18：已注释，改由 17 动态注入 -->
```

> 关键：`Remove_watermark_from_Amap_Map.js` **不由 HTML 直接引入**，而是由 `load_amap_watermark.js` 在鉴权通过后动态创建 `<script>` 注入。IE6-9 由 HTML 条件注释先行拦截，IE10-11 及其他旧浏览器由 `ie_detect.js` 拦截。

### 1. `scripts/ie_detect.js`（294 行）——浏览器兼容性检测拦截

- **职责**：在页面渲染前同步执行，检测不兼容浏览器并 `window.location.href = '/ie.html'` 重定向到升级提示页。
- **实现形式**：IIFE，**全程 ES5 语法**（`var`/`function`、`indexOf`/正则，不用 `includes`/`startsWith`），确保在老旧浏览器自身可解析执行。
- **全局导出**：无（IIFE 封闭，不污染全局）。内部仅 `block()` 跳转函数 + `var ua = navigator.userAgent`。
- **检测顺序（14 项，命中即 `return block()` 提前退出）**：
  1. IE10/IE11 —— `document.documentMode` 为真。
  2. 旧版 Edge（EdgeHTML）—— `/\bEdge\/\d+/`（注意 Chromium Edge 是 `Edg/`，放行）。
  3. 国产双核浏览器兼容模式 —— `/Trident\//` 且 UA 含 `360EE|360SE|QIHU|Sogou|MetaSr|QQBrowser|TheWorld|Maxthon|2345Explorer`。
  4. 旧版 Opera（Presto）—— `/Opera\//` 且不含 `/OPR\//`。
  5. Opera Mini —— `/Opera Mini/i`。
  6. UC 浏览器 —— `/UCBrowser\//i`。
  7. 百度浏览器 —— `/BIDUBrowser|baidubrowser/i`。
  8. Samsung Internet < 10 —— `SamsungBrowser/(\d+)` 解析版本号。
  9. Firefox < 68 —— `Firefox/(\d+)`。
  10. Chrome/Chromium < 70 —— `\bChrome\/(\d+)`，排除 `Edg/` 与 `SamsungBrowser/`。
  11. Safari < 12 —— `Version/(\d+).*Safari`，排除含 `Chrome/`、`Android`。
  12. Android 内置浏览器（≤4.x）—— `Android [1-4]\.\d` + `Version/` + 非 `Chrome/`。
  13. 特性兜底检测 —— 遍历 `['Promise','fetch','Symbol','Map','Set']`，任一在 `window` 上 `undefined` 即拦截。
  14.（通过全部检测则不做任何事，继续正常加载页面。）
- **复刻要点**：Vue 版通常保留此文件原样引入即可（属纯静态防御脚本）；重定向目标 `/ie.html` 与 `/ie_basic.html` 需一并保留。

### 2. `scripts/load_amap_watermark.js`（281 行）——高德地图加载器（带去水印鉴权）

- **职责**：加载高德地图前，先请求后端确认当前用户是否有"去水印"权限；有权限→注入去水印脚本，无权限/出错→加载普通高德脚本。
- **实现形式**：IIFE，进入时立即调用 `checkWatermarkPermission()`。
- **内部函数（均封闭在 IIFE，不导出到全局作用域）**：
  - `getUUIDFromURL()`：按优先级取 session UUID —— ① `window.sessionUUID` ② `localStorage.getItem("sessionUUID")` ③ `sessionStorage.getItem("sessionUUID")` ④ cookie `session_id_cookie` ⑤ URL 路径 `/uuid=<UUIDv4>`；取不到返回 `null`。
  - `installAmapNativeDialogGuard()`：在 AMap 加载期间**劫持** `window.alert/confirm/prompt`（分别返回 `undefined`/`false`/`null` 并打警告日志），防止原生弹窗中断执行。进入 IIFE 后立即调用一次。
  - `loadWatermarkRemovalScript()`：动态创建 `<script src="/scripts/Remove_watermark_from_Amap_Map.js" data-amap-watermark-removal="1" async=false>` 注入 `<head>`；`onerror` 回退调用 `loadAmapScript()`；带防重复注入判断。
  - `loadAmapScript()`：动态创建 `<script src="/api/cdn/amap-loader" data-amap-loader="1">`，`onerror` 回退到 `https://webapi.amap.com/loader.js`；带防重复注入判断。
  - `checkWatermarkPermission()`：`fetch("/api/amap/watermark_control", {method:GET, headers:{Content-Type, X-Session-ID}})` → 解析 `{allowed:boolean}`：`allowed===true` 调 `loadWatermarkRemovalScript()`，否则（含格式错误、HTTP 错误、网络异常）调 `loadAmapScript()`。**保守策略：任何异常都回退到不带去水印的普通加载**。
- **暴露到 `window` 的全局标记**（供跨脚本协作/幂等）：
  - `window.__amapNativeDialogGuardInstalled`（布尔，防重复安装弹窗守卫）。
  - `window.__amapNativeDialogGuardRestore`（函数，恢复原生 alert/confirm/prompt）——**去水印脚本执行完后应调用它还原**。
- **依赖的全局变量（读取）**：`window.sessionUUID`（由主脚本 `main.new.js` 维护）。
- **后端接口**：`GET /api/amap/watermark_control`（返回 `{allowed}`）、`GET /api/cdn/amap-loader`。

### 3. `scripts/Remove_watermark_from_Amap_Map.js`（138 行）——高德地图去水印拦截

- **职责**：拦截高德地图主库/统计脚本的网络请求，替换掉"未获得高德地图商用授权"水印关键词后再执行；处理完成后加载高德。
- **加载方式**：**不由 index.html 直接引入**（HTML 中该行被注释），由 `load_amap_watermark.js` 在鉴权通过后动态注入。
- **全局导出**：`function loadAmapScript()`（此处是**全局函数声明**，非 IIFE 内，会挂到 `window.loadAmapScript`；与 load_amap_watermark 内部同名函数逻辑一致但作用域不同）。
- **模块级常量/变量**（模块作用域，`const`/顶层）：
  - `CONFIG`：`{ targetMatch:["webapi.amap.com/maps","webapi.amap.com/count"], replaceRules:[{pattern:/未获得高德地图商用授权/g, replacement:""},{pattern:/\\u672a...\\u6388\\u6743(Unicode 转义版)/g, replacement:""}], timeout:5000 }`。
  - `requestCache = new Map()`：按 src 缓存处理结果（Promise），避免重复处理。
  - `originalCreateElement = document.createElement`：保存原始方法。
  - `originalSrcDescriptor`：`HTMLScriptElement.prototype` 上 `src` 属性的原始描述符。
- **关键逻辑**：
  - `fetchWithTimeout(url, timeout)`：`Promise.race([fetch, 超时reject])`，5s 超时放行原链接。
  - `interceptAndModify(src)`：命中缓存则返回；否则 fetch 脚本文本→按 `replaceRules` 剔除水印词→`new Blob([...],{type:"text/javascript"})` 生成 `URL.createObjectURL` blob URL；失败则回退原始 `src`。
  - **核心注入**：**重写 `document.createElement`**——对 `script` 标签用 `Object.defineProperty` 覆盖其 `src` setter：命中 `CONFIG.targetMatch` 时先异步 `interceptAndModify` 再用原始 setter 写入 blob URL（先阻止原赋值），未命中则原样放行。
  - 末尾调用 `loadAmapScript()` 启动高德加载（此时 createElement 已被劫持，高德 loader 内部创建的脚本会被自动净化）。
- **复刻要点**：这是运行时 monkey-patch，Vue 版若保留去水印功能须原样保留此脚本与注入时机（在高德 loader 之前劫持 `document.createElement`）。

### 4. `scripts/Check_for_updates.js`（106 行）——版本更新检查

- **职责**：对比本地缓存版本与后端 `version.json`，检测到版本变更时清缓存 + 注销 Service Worker + 强制刷新，实现无感更新。
- **实现形式**：IIFE，进入时立即 `checkVersion()`。
- **内部函数（不导出全局）**：
  - `getSessionId()`：读全局 `sessionUUID`（try/catch 容错），取不到返回 `""`。
  - `sendUpdateLog(level, message, extra)`：`fetch POST /api/log_frontend`（带 `X-Session-ID`、`keepalive:true`）上报前端日志，`source:"check_for_updates.js"`；同时 `console.log`。
  - `forceReloadWithBustTag()`：给当前 URL 加 `?__cache_bust=<Date.now()>` 后 `window.location.replace`（缓存击穿刷新）。
  - `checkVersion()`：`fetch("/api/version.json",{cache:"no-store"})` → 取 `data.version` 作 `latestVersion`，与 `localStorage.getItem("siteVersion")` 作 `currentVersion` 比较：
    - 若 `currentVersion` 存在且与 `latestVersion` 不同 → 写入新版本号 → 清 Cache API（`caches.keys()`+`caches.delete`）→ 注销全部 Service Worker（`getRegistrations()`+`unregister()`）→ `forceReloadWithBustTag()` 强刷。
    - 否则写入 `latestVersion`，记 DEBUG 日志，不刷新。
- **依赖/接口**：读全局 `sessionUUID`；后端 `GET /api/version.json`、`POST /api/log_frontend`；`localStorage` 键 `siteVersion`。
- **复刻要点**：Vue 版构建后版本号来源（`version.json`）与 `siteVersion` 存储键需保持一致，否则会触发无限刷新或不更新。

---

## 三、复刻检查清单（速查）

- [ ] `:root` 7 个 CSS 变量原样保留，且允许 JS 运行时覆盖 `--base-color` / `--base-color-600`。
- [ ] `.btn` 全系列（primary/secondary/danger/warning/success/ghost/loading）+ `.panel` + `.input-field`/`.select-field`/`.phone-input-wrapper`。
- [ ] `.modal` / `.modal-content` 及 `.neumorphic` 拟态变体；4 个 `@keyframes`（fadeIn/scaleIn/pulse/cr-spin）。
- [ ] `body.dark-mode` 全套覆写（含对 Tailwind 语义类的覆写）。
- [ ] 移动端 `body.mobile-mode` / `#mobile-container` 整套组件类 + 侧边栏 + 底部弹窗 + 状态徽章。
- [ ] `body.desktop-forced-mode`「查看桌面网站」强制布局。
- [ ] 地图水印隐藏选择器（`body.modal-visible` + 各 modal `:not(.hidden)`）。
- [ ] swal2 四套风格类（neumorphism / flat / clean / 去 glow）。
- [ ] 3 个响应式断点（768 / 480 / landscape 500）+ `prefers-color-scheme: dark`。
- [ ] 4 个辅助脚本按 `ie_detect → Check_for_updates → load_amap_watermark`（后者动态注入 Remove_watermark）顺序同步加载；保留全局标记 `window.__amapNativeDialogGuardInstalled` / `__amapNativeDialogGuardRestore` 与全局 `window.loadAmapScript`。
