# Original 前端结构总览（Structure Map）

> 本目录用于对 **original 前端**（根目录 `index.html` + `scripts/main.new.js` + `styles/style.css` + 辅助脚本）进行逐行完整解析，作为 Vue 版复刻的权威依据。
> 生成时间：2026-07-14

## 1. 文件规模

| 文件 | 行数 / 大小 | 角色 |
|---|---|---|
| `index.html` | 22894 行 (987 KB) | 页面结构 / 模板 / 内联样式片段 |
| `scripts/main.new.js` | 66131 行 (2.5 MB) | 主应用逻辑（由原内联脚本块拼接而成，12 个 script block） |
| `styles/style.css` | 56 KB | 全局样式 |
| `scripts/ie_detect.js` | 294 行 | IE 浏览器检测 |
| `scripts/load_amap_watermark.js` | 281 行 | 高德地图水印加载控制 |
| `scripts/Remove_watermark_from_Amap_Map.js` | 138 行 | 高德地图去水印 |
| `scripts/Check_for_updates.js` | 106 行 | 版本更新检查 |

## 2. index.html 顶层结构

外部依赖（`<head>`）：SweetAlert2、qrcode、cropperjs@1.6.2、TailwindCSS 3.4.17、socket.io、jquery、sortablejs、editor.md。均通过 `/api/cdn/*` 代理加载，带 `onerror` 回退到 jsdelivr。

两大容器体系 + 顶层模态框：

| 行号 | id / 容器 | 说明 |
|---|---|---|
| 565 | `#newbie-help-modal` | 新手帮助模态框 |
| 866 | `#guest_warning` | 游客警告 |
| 906 | `#newUserModal` | 新建用户模态框（含 `#newUserSmsGroup` 短信验证） |
| 1041 | `#multi-add-user-modal` | 移动端批量添加用户模态框 |
| 1121 | `#school-accounts-modal` | 校园账号模态框 |
| 2000 | `#auth-2fa-form` | 2FA 验证表单 |
| **2162** | **`#desktop-container`** | **PC 端主容器** |
| **3577** | **`#mobile-container`** | **移动端主容器** |
| 3623 | `#mobile-auth-login-container` | 移动端认证登录容器 |
| 4067 | `#mobile-login-container` | 移动端会话登录容器 |
| 4566 | `#mobile-main-app` | 移动端主应用 |
| 10482 | `#mobile-multi-account-app` | 移动端多账号应用 |
| 13020 | `#mobile-sidebar-multi-account` | 移动端多账号侧边栏 |
| 19524 | `#admin-pricing-panel_modal` | 管理员定价面板模态框 |
| 21347 | `#sms-test-result` | 短信测试结果 |
| 21486 | `#sms-reply-logs-list` | 短信回复记录列表 |
| 21565 | `#captcha-detail-content` | 验证码详情内容 |
| 22461 | `#modify-phone-modal` | 修改手机号模态框 |
| 22586 | `#payment-modal` | 支付模态框 |
| 22697 | `#orders-modal` | 订单列表模态框 |

## 3. main.new.js 脚本块边界（`// --- Next Script Block ---`）

| Block | 起始行 | 主要内容 |
|---|---|---|
| 1 | 1 | 安全配置常量、支付日志面板、事件监听绑定 |
| 2 | 1187 | 全局状态管理对象、核心功能函数 |
| 3 | 2386 | 支付设置面板（标签切换 / 支付方式配置 / 订单查询 / 退款 / 测试支付） |
| 4 | 6340 | Tab 切换、订单查询、订单列表管理、易支付配置（PC+移动） |
| 5 | 10701 | 注册提示、个人资料 available_runs、价格配置管理、支付方式、高德水印控制 |
| 6 | 11857 | （续）支付方式动态加载 |
| 7 | 13941 | （极小） |
| 8 | 13960 | （小） |
| 9 | **14139** | **主应用逻辑**（移动端检测、管理面板、日志、健康、个人信息、密码修改、用户管理、强制登出、IP封禁、短信、会话选择器、移动端创建用户）— 巨大，14139~43148 |
| 10 | 43148 | CDN缓存、密码恢复、定时提醒、移动端管理面板初始化、移动端多账号 |
| 11 | 49751 | 移动端多账号管理面板全套功能 |
| 12 | 58399 | 密码恢复任务、彩虹易支付前端+管理员、欠费检查、欠费查询、退款金额填充、账单函数 |

## 4. main.new.js 功能区目录（banner 标题）

见 `01-JS-功能区目录.md`（逐段详解拆分到 JS-*.md）。

## 5. 解析进度追踪（全部完成）

| 文档 | 覆盖范围 | 状态 |
|---|---|---|
| 10-HTML-head-modals.md | index.html 1–2162 | ✅ |
| 11-HTML-desktop.md | index.html 2162–3577 | ✅ |
| 12-HTML-mobile-main.md | index.html 3577–10482 | ✅ |
| 13-HTML-mobile-multiaccount.md | index.html 10482–19524 | ✅ |
| 14-HTML-modals-tail.md | index.html 19524–22894 | ✅ |
| 20-JS-支付与核心.md | main.new.js 1–14139 | ✅ |
| 21-JS-主应用A.md | main.new.js 14139–26329 | ✅ |
| 22-JS-主应用B.md | main.new.js 26329–43148 | ✅ |
| 23-JS-移动端与多账号.md | main.new.js 43148–58399 | ✅ |
| 24-JS-易支付与账单.md | main.new.js 58399–66131 | ✅ |
| 30-CSS-与辅助脚本.md | style.css + 4 个辅助脚本 | ✅ |
| 40-API与Socket对照.md | API/Socket 端点对照 | ✅ |
| 90-Vue版差异与复刻计划.md | Vue 版 gap 分析与计划 | ✅（随修改推进更新） |

## 6. 完整性核验结论（反复核验）

- **行覆盖**：HTML 1–22894、JS 1–66131 均由分段文档**连续无缝覆盖**（边界共享，无空洞）。
- **id 交叉核验**：index.html 共 **1262 个 distinct id**，逐一比对 HTML 文档，仅 4 个子容器 id 未字面出现（`auth-login-captcha-container_display`@1687、`mobile-multi-admin-captcha-list`@7714、`mobile-multi-admin-pricing-content`@9955、`mobile-captcha-history-modal-content`@11929），均落在已覆盖范围内且被父面板描述涵盖 → **字面命中 99.7%，范围命中 100%**。
- **banner 区块核验**：main.new.js 全部功能区 banner（约 90 个）已在 JS 文档目录中体现。
- **Socket 事件核验**：14 个 `socket.on` + `heartbeat`/`join` 全部记录，且 Vue 版已复刻。
- 结论：**original 前端解析无实质遗漏，可进入 Vue 复刻修改阶段。**
