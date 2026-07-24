# 11 - 原始 HTML 解析：PC 端主容器 `#desktop-container`

> **覆盖范围**：`index.html` 第 **2162 – 3577** 行。
> 本文档逐区块编目"跑步助手"原始单文件前端的 **PC 端主容器 `#desktop-container`** 全部 UI 结构、交互元素、事件绑定、data-* 属性、可见性逻辑与关键文案，作为 Vue 重构版的完整复刻依据。
>
> **边界说明**：
> - `#desktop-container` 开始于第 **2162** 行，结束（闭合 `</div>`）于第 **3572** 行。
> - 第 3574 行起为注释块，第 **3577** 行是 `#mobile-container` 的开始标签（移动端容器，超出本文覆盖范围，仅标注边界）。
>
> **说明**：本段内绝大多数按钮/输入框**没有内联事件**，仅通过 `id` 供外部 JS（addEventListener）绑定；下文"事件"列中，凡标注"内联"的才是写在 HTML 里的 `onclick`/`onchange` 等；其余需在 JS 层按 id 绑定。

---

## 顶层结构总览

| 行号 | 元素 | id | 初始可见性 | 说明 |
|---|---|---|---|---|
| 2162 | `<div>` | `desktop-container` | 可见（由外层 CSS 控制 PC/移动端切换） | PC 端根容器 |
| 2164–2595 | `<main>` | `login-container` | 可见（无 hidden） | 登录/认证界面（三栏栅格） |
| 2597–3042 | `<main>` | `main-app` | **hidden** | 单账号主应用（任务+地图） |
| 3044–3301 | `<main>` | `multi-account-app` | **hidden** | 多账号控制台 |
| 3303–3349 | `<div>` | `amap-key-modal` | **hidden** | 地图 API Key 弹窗 |
| 3351–3416 | `<div>` | `auto-gen-modal` | **hidden** | 自动生成路线配置弹窗 |
| 3417–3442 | `<div>` | `user-details-modal` | **hidden** | 用户详情弹窗 |
| 3443–3468 | `<div>` | `task-details-modal` | **hidden** | 任务详情弹窗 |
| 3494–3571 | `<div>` | `pc-beian-footer` | **始终可见**（无 hidden） | PC 端备案 footer（所有 PC 页面共享） |
| 3572 | `</div>` | — | — | `#desktop-container` 闭合 |

栅格切换逻辑：三个 `<main>` 互斥显示，`login-container` 无 `hidden`，`main-app` 与 `multi-account-app` 带 `hidden` 类，通过 JS 切换 `hidden` 类实现页面互换。

---

## 一、登录界面 `#login-container`（2164–2595）

- **容器**：`<main id="login-container" class="h-screen w-screen grid grid-cols-1 lg:grid-cols-3">`（行 2164–2167）
- **初始可见性**：可见（无 hidden）。
- **布局**：单列（移动断点）/ `lg` 断点三列栅格。三栏分别为：多账号引导、单账号登录、会话管理。

### 1.1 第一栏 · 多账号引导面板（2168–2233）

- 外层：装饰性渐变背景 `bg-gradient-to-br from-purple-50 ...`（行 2168–2176 含两个模糊光晕装饰 div）。
- 内层 panel（行 2178–2232）：`panel rounded-3xl ... bg-white/60 backdrop-blur-xl`。
- 顶部图标：紫色 SVG 人群图标（行 2181–2196，带 `animate-pulse` 光晕）。
- **标题**（行 2198–2202）：`掌上莲峰<br />多账号模式`（渐变文字 `card-title`）。
- **说明文案**（行 2204–2210）：
  - `✨ 支持批量导入账号`
  - `🎯 统一管理所有任务`
  - `⚡ 一键执行全部流程`
- **按钮**：

| id | 行号 | 文案 | class | 事件 | 备注 |
|---|---|---|---|---|---|
| `multi-account-btn` | 2212–2231 | `进入多账号控制台`（含右箭头 SVG） | `btn btn-secondary w-full py-3.5 ...` | 需 JS 绑定（无内联） | `title="多账号"` `aria-label="多账号"`；点击进入多账号控制台 |

### 1.2 第二栏 · 单账号登录面板（2235–2468）

- 外层：`bg-gradient-to-br from-white via-sky-50/30 ...`（含两个光晕装饰）。
- 内层 panel（行 2245–2467）：`panel rounded-3xl w-full max-w-md ...`，**id = `desktop-container-single-login-panel-wrapper`**（行 2247）。
- 标题区（行 2249–2273）：人像 SVG + `<h2>单账号登录</h2>`（行 2267），副标题 `掌上莲峰跑步助手`（行 2272）。
- **表单字段**（行 2275–2361）：

| 元素 | id | 行号 | 类型 | 标签/占位 | 属性 |
|---|---|---|---|---|---|
| `<select>` | `user-combo` | 2296–2301 | 下拉 | 标签"选择账号" | `title="选择已保存的账号或创建新账号"` `aria-label="选择账号"`，内容空（由 JS 填充） |
| `<input>` | `username-entry` | 2324–2330 | text | 标签"用户名"，占位 `请输入学号或工号` | `autocomplete="username"` |
| `<input>` | `password-entry` | 2353–2359 | password | 标签"密码"，占位 `请输入密码，一般为身份证后六位` | `autocomplete="current-password"` |

- **按钮与操作**：

| id | 行号 | 文案 | class | 事件 | 备注 |
|---|---|---|---|---|---|
| `login-button` | 2363–2382 | `立即登录`（含右箭头 SVG） | `btn btn-primary w-full py-3.5 ...` | JS 绑定 | `title="登录"` |
| — 分割线 — | 2384–2390 | `或者` | — | — | 视觉分隔 |
| `import-button` | 2392–2413 | `导入离线文件`（含上传 SVG） | `btn btn-success w-full py-3 ...` | JS 绑定 | `title="导入"` |

- **User-Agent 区块**（行 2415–2466）：
  - 标签：`User-Agent 标识`（含 info SVG，行 2434）。
  - 按钮 `random-ua-btn`（行 2437–2457）：文案 `随机`（含刷新 SVG），`class="btn btn-ghost !py-1.5 !px-3 text-xs ..."`，`title="随机生成新的User-Agent，用于模拟不同设备和浏览器"`，JS 绑定。
  - 显示区 `<p id="ua-label">`（行 2460–2465）：初始文本 `(未加载)`，`break-all`，用于展示当前 UA。

### 1.3 第三栏 · 会话管理面板（2470–2594）

- 外层容器 `<div ... id="admin-panel-modal-Inline">`（行 2470–2473），渐变背景 + 光晕装饰。
- 内层 panel（行 2481–2484）：`max-height: calc(100vh - 12rem)`。
- 标题（行 2485–2505）：人群 SVG + `<h3>会话管理</h3>`（行 2502–2504）。
- **会话面板** `<div id="admin-sessions-panel">`（行 2507–2592）：
  - 子标题 `<h4>会话列表</h4>`（行 2514）。
  - **上帝模式开关**（行 2517–2532）：
    - `<label id="god-mode-toggle" ... style="display: none">`（行 2517–2520，**初始隐藏**）。
    - `<input type="checkbox" id="god-mode-checkbox" class="... accent-red-600 ...">`（行 2522–2528），`aria-label`/`title="god mode checkbox"`。
    - 文案：`⚠️ 上帝模式`（红色，行 2529–2531）。
  - **会话计数显示** `<div id="admin-session-count-display-inline">`（行 2534–2537）：空，由 JS 填充。
  - **刷新会话按钮** `<button id="admin-refresh-sessions-inline">`（行 2539–2560）：文案 `刷新`（含刷新 SVG），`class="btn btn-ghost !py-1.5 !px-3 ..."`，`title="刷新会话"`，JS 绑定。
  - **会话列表容器** `<div id="admin-sessions-list-inline" class="space-y-3 max-h-[50vh] overflow-y-auto ...">`（行 2564–2591）：初始占位为加载动画 SVG + 文案 `正在加载会话数据...`（行 2589）。
- `</main>` 闭合于行 2595。

---

## 二、单账号主应用 `#main-app`（2597–3042）

- **容器**：`<main id="main-app" class="hidden h-screen w-screen grid grid-cols-1 lg:grid-cols-3 xl:grid-cols-4 gap-4 p-4">`（行 2597–2600）。
- **初始可见性**：**hidden**（登录后由 JS 移除）。
- **布局**：左侧栏 1 列（`lg:col-span-1 xl:col-span-1`）+ 右侧 2/3 列（地图与状态）。

### 2.1 左侧栏 `#user-info-section-desktop-inline`（2601–2937）

容器：`<div class="lg:col-span-1 ..." id="user-info-section-desktop-inline">`（行 2601–2603）。含三块 panel：用户信息栏、任务列表、标签页控制区。

#### 2.1.1 用户信息栏（2604–2647）

- panel：`rounded-xl p-4 flex items-center gap-4`。
- 姓名标签 `<p id="user-name-label">`（行 2606–2608）：初始 `姓名: NULL`。
- 学号标签 `<p id="user-id-label">`（行 2609–2611）：初始 `学号: NULL`。
- **按钮组**：

| id | 行号 | 文案 | class | 可见性 | 备注 |
|---|---|---|---|---|---|
| `show-notifications-btn` | 2614–2625 | `通知` | `btn btn-ghost !py-2 !px-3 relative` | 可见 | `title="查看通知"`；内含徽标 span |
| `notification-badge` | 2620–2623 | 初始 `0` | `hidden absolute ... bg-red-500 ...` | **hidden** | 未读数徽标，JS 控制显示 |
| `show-user-details` | 2626–2632 | `详情` | `btn btn-ghost !py-2 !px-3` | 可见 | `title="查看用户详情"` |
| `show-admin-panel` | 2633–2639 | `管理` | `btn btn-ghost !py-2 !px-3 hidden` | **hidden** | `title="管理面板"`，仅管理员可见 |
| `logout-button` | 2640–2646 | `退出` | `btn btn-ghost !py-2 !px-3 !text-red-600` | 可见 | `title="注销"` |

#### 2.1.2 任务列表面板 `#task-panel-desktop-inline`（2648–2674）

- panel：`rounded-xl p-4 flex-grow flex flex-col min-h-0`。
- 标题 `<h2>任务列表</h2>`（行 2650）。
- 按钮：
  - `show-task-details`（行 2652–2659）：文案 `任务详情`，`title/aria-label="查看任务详情"`，JS 绑定。
  - `refresh-button`（行 2660–2667）：文案 `刷新`，`title/aria-label="刷新"`，JS 绑定。
- 列表容器 `<div id="task-list" class="flex-grow overflow-y-auto -mr-2 pr-2">`（行 2670–2673）：空，由 JS 渲染任务项。

#### 2.1.3 标签页控制区 `#task-section-desktop-inline`（2675–2936）

- panel：`rounded-xl p-4`。
- **Tab 按钮条**（行 2676–2701）：`<div class="flex border-b ...">`，全部为**内联 onclick**，调用 `showTab(tabName, this)`：

| Tab 按钮文案 | 行号 | onclick | 对应内容面板 id | 初始 active |
|---|---|---|---|---|
| `执行` | 2677–2682 | `showTab('run-control', this)` | `run-control-tab` | ✅ `active` |
| `路径` | 2683–2685 | `showTab('path-tools', this)` | `path-tools-tab` | — |
| `打卡点` | 2686–2688 | `showTab('checkpoints', this)` | `checkpoints-tab` | — |
| `签到` | 2689–2691 | `showTab('attendance', this)` | `attendance-tab` | — |
| `历史` | 2692–2694 | `showTab('history', this)` | `history-tab` | — |
| `参数` | 2695–2697 | `showTab('params', this)` | `params-tab` | — |
| `日志` | 2698–2700 | `showTab('log', this)` | `log-tab` | — |

- Tab 内容外框：`<div class="h-56 overflow-y-auto">`（行 2702）。

##### (a) 执行 Tab `#run-control-tab`（2703–2777，可见）

- **统计块** `#run-stats-block`（行 2704–2715）：
  - 标题 `已选任务总览`（行 2708）。
  - `<p id="run-stats-label">`（行 2709–2714）：初始 `-- km / --:--`。
- **单任务进度块** `#single-progress-block`（行 2717–2734）：
  - 进度条填充 `<div id="single-progress-fill" style="width: 0%">`（行 2719–2723）。
  - 进度文本 `<span id="single-progress-text">`（行 2726–2728）：初始 `未开始`。
  - 附加信息 `<span id="single-progress-extra">`（行 2729–2732）：空。
- **执行按钮组**（行 2736–2753）：

| id | 行号 | 文案 | class | 备注 |
|---|---|---|---|---|
| `start-run-button` | 2737–2744 | `开始执行` | `btn btn-primary` | `title/aria-label="开始运行"` |
| `start-all-button` | 2745–2752 | `执行所有` | `btn btn-secondary` | `title/aria-label="全部开始"` |

- **复选框组**（行 2755–2776）：
  - `<input type="checkbox" id="run-completed-check" class="... accent-sky-600 ...">`（行 2758–2764）+ 文案 `忽略已完成状态`。
  - `<input type="checkbox" id="auto-gen-all-check" ...>`（行 2768–2774）+ 文案 `自动生成路径`。

##### (b) 路径 Tab `#path-tools-tab`（2778–2824，**hidden**）

- 第一组 2×2 按钮（行 2779–2812）：

| id | 行号 | 文案 | class |
|---|---|---|---|
| `record-button` | 2780–2787 | `录制路径` | `btn btn-success`，`title/aria-label="记录"` |
| `auto-gen-button` | 2788–2795 | `自动生成` | `btn btn-secondary`，`title/aria-label="自动生成"` |
| `process-button` | 2796–2803 | `处理路径` | `btn btn-primary`，`title/aria-label="处理"` |
| `clear-button` | 2804–2811 | `清除路径` | `btn btn-warning`，`title/aria-label="清除"` |

- 第二组（行 2813–2823）：`export-button`（行 2814–2821）文案 `导出`，`btn btn-ghost border border-slate-300 col-span-1`，`title/aria-label="导出"`；右侧空占位 div。

##### (c) 打卡点 Tab `#checkpoints-tab`（2825–2827，**hidden**）

- 容器 `<div id="target-points-text" class="h-48 overflow-y-auto">`（行 2826）：空，由 JS 填充目标点列表。

##### (d) 签到 Tab `#attendance-tab`（2829–2907，**hidden**）

- 容器：`class="hidden pt-2 space-y-2 h-56 flex flex-col"`。
- **自动签到设置区**（行 2833–2886）：
  - 开关 `<input type="checkbox" id="param-auto_attendance_enabled" data-key="auto_attendance_enabled">`（行 2838–2845）+ 文案 `开启自动签到`；label `title="开启后，将在后台自动刷新通知并尝试签到"`。
  - 提示：`⏱ 自动签到启用后将在 120 分钟内自动关闭。`（行 2850–2852）。
  - 数字输入 `刷新间隔(秒)`：`<input type="number" step="5" min="10" id="param-auto_attendance_refresh_s" data-key="auto_attendance_refresh_s">`（行 2859–2867），`title="自动刷新通知的间隔时间（秒），最小10秒"`。
  - 数字输入 `随机半径(米)`：`<input type="number" step="1" id="param-attendance_user_radius_m" data-key="attendance_user_radius_m">`（行 2874–2881），`title="自动签到时，在服务器允许范围内的最大随机偏移半径。设为0为精确签到。"`。
  - 提示：`⚠ 若随机半径超过签到允许的最大范围，将自动缩减至该上限。`（行 2883–2885）。
- **签到任务列表区**（行 2887–2906）：
  - 子标题 `签到任务列表`（行 2890–2892）。
  - **刷新按钮** `<button id="refresh-attendance-list-btn" onclick="refreshNotificationsUI(true, true)">`（行 2893–2899，**内联 onclick**）：文案 `刷新`。
  - 列表容器 `<div id="attendance-list" class="flex-grow pr-1">`（行 2902–2906）：初始占位文案 `点击"刷新"按钮查看签到任务`。

##### (e) 历史 Tab `#history-tab`（2909–2919，**hidden**）

- 容器 `#history-list-container`（行 2910–2918）：
  - 占位 `<p id="history-placeholder">选择任务后显示历史记录</p>`（行 2911–2916）。
  - 列表 `<div id="history-list">`（行 2917）：空。

##### (f) 参数 Tab `#params-tab`（2920–2922，**hidden**）

- 容器 `<div id="params-container">`（行 2921）：空，由 JS 动态渲染参数表单。

##### (g) 日志 Tab `#log-tab`（2923–2934，**hidden**）

- `<textarea id="log-text" readonly>`（行 2925–2932）：只读日志文本框，`aria-label/title/placeholder="log text"`。

### 2.2 右侧区（地图 + 状态）（2939–3041）

容器：`<div class="lg:col-span-2 xl:col-span-3 flex flex-col gap-4 ...">`（行 2939–2941）。

#### 2.2.1 地图容器 `#map-container`（2942–2978）

- `<div id="map-container" class="flex-grow bg-slate-200 rounded-xl relative overflow-hidden ...">`（行 2942–2945）。
- **地图控制条**（行 2946–2977，右上角悬浮）：

| id | 行号 | 文案 | 备注 |
|---|---|---|---|
| `zoom-in` | 2949–2956 | `+` | `title/aria-label="放大"` |
| `zoom-level` | 2957–2961 | 初始 `17` | 缩放级别显示（span） |
| `zoom-out` | 2962–2969 | `-` | `title/aria-label="缩小"` |
| `reset-view-btn` | 2970–2976 | `🎯` | `title="复位视角"` |

#### 2.2.2 状态面板 `#status-panels`（2979–3040）

- 容器 `<div class="grid grid-cols-1 gap-4" id="status-panels">`（行 2979）。
- panel `实时状态`（行 2980–3039）：
  - 标题 `<h3>实时状态</h3>`（行 2982）。
  - 当前坐标 `<p id="current-location-label">`（行 2983–2988）：初始 `当前位置GPS坐标: --, --`。
  - **5 列指标网格**（行 2990–3038）：

| 指标标签 | 值元素 id | 行号 | 初始值 |
|---|---|---|---|
| 已跑距离 | `live-dist-label` | 2995–3000 | `0.00 km` |
| 总距离 | `total-dist-label` | 3004–3009 | `0.00 km` |
| 已用时间 | `live-time-label` | 3013–3018 | `00:00` |
| 预计时间 | `total-time-label` | 3022–3027 | `00:00` |
| 预估剩余时间 | `remaining-time-label` | 3031–3036 | `00:00` |

- `</main>` 闭合于行 3042。

---

## 三、多账号控制台 `#multi-account-app`（3044–3301）

- **容器**：`<main id="multi-account-app" class="hidden h-screen w-screen grid grid-cols-1 lg:grid-cols-[530px,1fr] xl:grid-cols-[530px,1fr] gap-4 p-4">`（行 3044–3047）。
- **初始可见性**：**hidden**。
- **布局**：左固定 530px 控制列 + 右自适应（地图+全局日志）。

### 3.1 左列（3048–3254）

#### 3.1.1 控制台头部 panel（3049–3128）

- 标题 `<h2 ... card-title>多账号控制台</h2>`（行 3051–3053）。
- 头部按钮：
  - `show-admin-panel-multi`（行 3055–3061）：文案 `管理面板`，`title="管理面板"`。
  - `exit-multi-mode-btn`（行 3062–3067）：文案 `返回登录页`。
- **主控按钮组**（行 3070–3077）：
  - `multi-start-all-btn`（行 3071–3073）：文案 `全部开始`，`btn btn-primary`。
  - `multi-stop-all-btn`（行 3074–3076）：文案 `全部停止`，`btn btn-danger`。
- **选项区**（行 3078–3127）：
  - 复选框 `<input type="checkbox" id="multi-use-delay-check" checked>`（行 3082–3089，**默认勾选**）+ 文案 `启用随机启动延迟`。
    - 数字输入 `multi-min-delay-input`（行 3092–3100，value=`0`）。
    - 数字输入 `multi-max-delay-input`（行 3102–3110，value=`300`）。
    - 后缀 `秒`。
  - 复选框 `<input type="checkbox" id="multi-run-only-incomplete-check" checked>`（行 3117–3124，**默认勾选**）+ 文案 `仅执行未完成的任务`。

#### 3.1.2 账号列表 panel（3129–3246）

- 头部（行 3130–3166）：
  - 标题 `账号列表 (<span id="multi-account-count">0</span>)`（行 3132–3134）。
  - 全选复选框 `<input type="checkbox" id="multi-select-all-check" ... style="display: none">`（行 3135–3141，**初始隐藏**），`title="全选/取消全选"`。
  - 右侧按钮组：
    - `multi-import-excel-btn`（行 3144–3150）：文案 `导入`，`title="从文件导入"`。
    - `multi-export-excel-btn`（行 3151–3157）：文案 `导出`，`title="导出汇总"`。
    - `multi-download-template-btn`（行 3158–3164）：文案 `下载模板`，`title="下载导入模板"`。
- **操作条**（行 3168–3218，三组）：

| 分组 | id | 行号 | 文案 | 颜色 class |
|---|---|---|---|---|
| 刷新 | `multi-refresh-selected-btn` | 3173–3178 | `刷新选中` | `text-blue-600` |
| 刷新 | `multi-refresh-all-btn` | 3179–3184 | `刷新全部` | `text-blue-600` |
| 控制 | `multi-start-selected-btn` | 3189–3194 | `开始选中` | `text-green-600` |
| 控制 | `multi-stop-selected-btn` | 3195–3200 | `停止选中` | `text-green-600` |
| 移除 | `multi-remove-selected-btn` | 3205–3210 | `移除选中` | `text-red-600` |
| 移除 | `multi-remove-all-btn` | 3211–3216 | `移除全部` | `text-red-600` |

- **账号列表容器** `<div id="multi-account-list" class="flex-grow overflow-y-auto ..." style="max-height: 42vh">`（行 3220–3226）：初始占位 `请先添加或导入账号`。
- **配置添加区**（行 3227–3245）：
  - 下拉 `<select id="multi-config-user-select" ...>`（行 3228–3232），`aria-label="从配置添加用户"`，空（JS 填充）。
  - `multi-add-from-config-btn`（行 3233–3238）：文案 `添加`。
  - `multi-load-all-from-config-btn`（行 3239–3244）：文案 `添加全部`。

#### 3.1.3 全局参数 panel（3247–3253）

- 标题 `<h3>全局参数</h3>`（行 3248）。
- 容器 `<div id="multi-global-params-container" class="h-40 overflow-y-auto pr-1">`（行 3249–3252）：空，JS 渲染。

### 3.2 右列（3255–3300）

#### 3.2.1 多账号地图 `#multi-map-container`（3256–3288）

- `<div id="multi-map-container" ...>`（行 3256–3259）。
- 地图控制条（行 3260–3287）：

| id | 行号 | 文案 | 备注 |
|---|---|---|---|
| `multi-zoom-in` | 3263–3268 | `+` | — |
| `multi-zoom-level` | 3269–3273 | 初始 `17` | 缩放级别 span |
| `multi-zoom-out` | 3274–3279 | `-` | — |
| `multi-reset-view-btn` | 3280–3286 | `🎯` | `title="复位视角"` |

#### 3.2.2 全局日志 panel（3289–3299）

- 标题 `<h3>全局日志</h3>`（行 3290）。
- `<textarea id="multi-log-text" readonly>`（行 3291–3298）：只读，`aria-label/title/placeholder="multi log text"`。
- `</main>` 闭合于行 3301。

---

## 四、弹窗组（Modals，均 `fixed inset-0 ... hidden z-50`）

### 4.1 地图 API Key 弹窗 `#amap-key-modal`（3303–3349，hidden）

- 遮罩 `bg-black/60`（行 3307）。
- 标题 `<h3 id="map-provider-key-modal-title">缺少地图 API Key</h3>`（行 3309–3314）。
- 描述 `<p id="map-provider-key-modal-description">`（行 3315–3329）：含链接 `<a id="map-provider-key-modal-link" href="#" target="_blank">地图开放平台</a>` 与尾句 `<span id="map-provider-key-modal-extra">申请并粘贴到下方。</span>`。
- 标签 `<label id="map-provider-key-input-label">API Key:</label>`（行 3331–3335）。
- 输入 `<input id="amap-key-input" type="text" placeholder="请在此处粘贴当前地图提供方的 API Key">`（行 3336–3341）。
- 按钮 `confirm-amap-key-btn`（行 3344–3346）：文案 `确认并保存`，`btn btn-primary`。

### 4.2 自动生成路线配置弹窗 `#auto-gen-modal`（3351–3416，hidden）

- 遮罩 `bg-black/40`（行 3355）。
- 标题 `<h3>自动生成路线配置</h3>`（行 3357–3359）。
- 输入项（行 3360–3403）：

| 标签 | id | 行号 | 默认值 |
|---|---|---|---|
| 最短时间(分钟) | `min-time-input` | 3365–3373 | `20` |
| 最长时间(分钟) | `max-time-input` | 3379–3387 | `30` |
| 最短距离(米) | `min-dist-input` | 3393–3401 | `2000` |

- 按钮（行 3404–3414）：
  - `cancel-gen-button`（行 3405–3410）：文案 `取消`，`btn btn-ghost border ...`。
  - `confirm-gen-button`（行 3411–3413）：文案 `生成`，`btn btn-primary`。

### 4.3 用户详情弹窗 `#user-details-modal`（3417–3442，hidden）

- 遮罩 div（行 3421–3424）：**内联 `onclick="toggleUserDetails(false)"`**。
- 标题 `<h3>用户详情</h3>`（行 3427）。
- 内容容器 `<div id="user-details-content" class="text-sm space-y-1 max-h-[70vh] overflow-y-auto">`（行 3429–3432）：空，JS 填充。
- 关闭按钮（行 3434–3439）：文案 `关闭`，**内联 `onclick="toggleUserDetails(false)"`**。

### 4.4 任务详情弹窗 `#task-details-modal`（3443–3468，hidden）

- 遮罩 div（行 3447–3450）：**内联 `onclick="toggleTaskDetails(false)"`**。
- 标题 `<h3>任务详情</h3>`（行 3453）。
- 内容容器 `<div id="task-details-content" ...>`（行 3455–3458）：空，JS 填充。
- 关闭按钮（行 3460–3465）：文案 `关闭`，**内联 `onclick="toggleTaskDetails(false)"`**。

---

## 五、PC 端备案 Footer `#pc-beian-footer`（3470–3571）

- 由大段注释（行 3470–3493）说明：**该容器始终可见**（无 hidden/display:none），无备案信息时显示为空白占位，防止布局跳动；内部链接由 `updateBeianSection("pc-")` 控制显隐。
- 容器 `<div id="pc-beian-footer" class="border-t border-slate-200 flex flex-col ...">`（行 3494–3497）。
- 内层 flex-wrap 容器（行 3499）。
- **ICP 备案链接**（行 3509–3534）：
  - `<a id="pc-icp-beian-link" href="https://beian.miit.gov.cn" target="_blank" rel="noopener noreferrer" style="display: none">`（**初始隐藏**）。
  - 显示条件：后端 `show_icp=true` 且提供 `icp_number`。
  - 文本容器 `<span id="pc-icp-beian-text">`（行 3533）：空，JS 填充。
- **公安备案链接**（行 3544–3569）：
  - `<a id="pc-police-beian-link" href="https://beian.mps.gov.cn" target="_blank" rel="noopener noreferrer" style="display: none">`（**初始隐藏**）。
  - 显示条件：后端 `show_police=true` 且提供 `police_number`。
  - 文本容器 `<span id="pc-police-beian-text">`（行 3568）：空，JS 填充。
- `#desktop-container` 闭合 `</div>` 于行 **3572**。

---

## 六、内联事件与关键 JS 函数索引（本段全量）

| 函数名 | 参数 | 出现位置（行号） | 触发元素 |
|---|---|---|---|
| `showTab` | `('run-control', this)` | 2679 | 执行 tab 按钮 |
| `showTab` | `('path-tools', this)` | 2683 | 路径 tab 按钮 |
| `showTab` | `('checkpoints', this)` | 2686 | 打卡点 tab 按钮 |
| `showTab` | `('attendance', this)` | 2689 | 签到 tab 按钮 |
| `showTab` | `('history', this)` | 2692 | 历史 tab 按钮 |
| `showTab` | `('params', this)` | 2695 | 参数 tab 按钮 |
| `showTab` | `('log', this)` | 2698 | 日志 tab 按钮 |
| `refreshNotificationsUI` | `(true, true)` | 2896 | `refresh-attendance-list-btn` |
| `toggleUserDetails` | `(false)` | 3423, 3436 | 用户详情弹窗遮罩/关闭按钮 |
| `toggleTaskDetails` | `(false)` | 3449, 3462 | 任务详情弹窗遮罩/关闭按钮 |

> 其余交互元素（`multi-account-btn`、`login-button`、`import-button`、`random-ua-btn`、会话/任务/多账号各按钮、缩放按钮、复选框、下拉框等）**无内联事件**，需在 JS 中按 `id` 用 `addEventListener` 绑定，复刻时须同步保留这些 id。

## 七、data-* 属性索引（本段全量）

| 元素 id | data-key | 行号 |
|---|---|---|
| `param-auto_attendance_enabled` | `auto_attendance_enabled` | 2841 |
| `param-auto_attendance_refresh_s` | `auto_attendance_refresh_s` | 2864 |
| `param-attendance_user_radius_m` | `attendance_user_radius_m` | 2878 |

## 八、初始可见性/隐藏元素清单（复刻关键）

| 元素 id | 隐藏方式 | 行号 | 说明 |
|---|---|---|---|
| `main-app` | `hidden` 类 | 2597 | 登录后显示 |
| `multi-account-app` | `hidden` 类 | 3044 | 进入多账号后显示 |
| `god-mode-toggle` | `style="display:none"` | 2520 | 上帝模式开关，条件显示 |
| `notification-badge` | `hidden` 类 | 2622 | 有未读通知时显示 |
| `show-admin-panel` | `hidden` 类 | 2635 | 仅管理员显示 |
| `path-tools-tab` / `checkpoints-tab` / `attendance-tab` / `history-tab` / `params-tab` / `log-tab` | `hidden` 类 | 2778/2825/2831/2909/2920/2923 | 非激活 tab 面板 |
| `multi-select-all-check` | `style="display:none"` | 3140 | 有账号时显示 |
| `amap-key-modal` / `auto-gen-modal` / `user-details-modal` / `task-details-modal` | `hidden` 类 | 3305/3353/3419/3445 | 弹窗，按需弹出 |
| `pc-icp-beian-link` / `pc-police-beian-link` | `style="display:none"` | 3515/3550 | 备案链接，配置启用后显示 |
| `run-control-tab` | 无（默认可见） | 2703 | 默认激活 tab |
| `pc-beian-footer` | 无（始终可见） | 3494 | 空白占位保持布局稳定 |
