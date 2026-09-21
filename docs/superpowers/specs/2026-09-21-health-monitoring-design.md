# Health Monitoring And Legacy Panel Refresh Design

## Goal

修正 `/health` 运行时长被固定或缓存导致的陈旧结果，增加仅管理员可见的运行时内存诊断信息，并修复根目录 `index.html` 旧版 UI 的健康面板刷新后滚动位置丢失。

## Scope

- `/health` 保持现有公开字段和状态码语义。
- 运行时长使用单调时钟计算，避免系统时间调整导致数值倒退或固定。
- 健康响应发送禁止缓存头，避免浏览器、代理或中间层复用旧 JSON。
- 只有现有管理员验证通过后才返回详细组件、汇总和内存诊断。
- 管理员诊断包含进程标识、启动时间、RSS、RSS 峰值、活动线程、账号刷新线程、多账号监控线程、Playwright 上下文和缓存条目等可用于多次采样比较的指标。
- 旧版 PC 健康面板、单账号移动端从 PC 复制的健康面板、多账号移动端专用健康面板都必须在刷新后恢复原滚动位置。
- 只修改健康检查和旧版 UI；不修改权限组、权限配置、`permissions.json` 或 Vue 版 UI。

## Root Cause

后端当前通过 `time.time() - server_start_time` 计算运行时长，且 `/health` 没有禁止缓存响应头。服务启动时间只在启动路径设置，响应本身缺少进程启动标识，无法区分服务重启与缓存复用。

旧版 UI 的健康加载函数在请求开始时立即用加载占位符覆盖内容，成功后再次替换整个 `innerHTML`。移动端单账号还会异步把 PC 内容复制到移动容器，两个替换点都会让滚动容器回到顶部。

## Design

### Backend

在 `main.py` 中增加小型、可测试的运行时辅助函数：

- `_get_health_uptime_seconds()` 优先使用服务启动时保存的 `time.monotonic()` 值；没有该值时兼容旧环境回退到墙上时钟。
- `_collect_runtime_memory_diagnostics()` 只读取现有运行时状态，不返回 token、cookie、配置密钥或用户内容。
- `_log_runtime_memory_diagnostics()` 复用采集结果，保持现有 `[内存诊断]` 日志格式。

`start_web_server()` 同步记录 `server_start_monotonic`。健康路由计算响应后构造 Flask response，设置 `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`、`Pragma: no-cache` 和 `Expires: 0`。

管理员响应新增顶层 `memory_diagnostics`。匿名和普通用户响应不包含该字段，现有基于 `auth_token` 的管理员组验证不变。

### Legacy UI

在 `scripts/main.new.js` 中增加通用健康刷新辅助函数：

- 捕获内容元素及其可滚动祖先、文档滚动位置。
- 内容替换后通过 `requestAnimationFrame` 恢复所有保存的 `scrollTop`/`scrollLeft`。
- 已经渲染过内容时，刷新请求期间不清空旧内容，避免滚动高度瞬间塌陷。
- 请求使用 `cache: "no-store"`，并保留同源 cookie。

健康诊断用一个共享渲染函数生成 PC 和移动端卡片。PC loader、移动端多账号 loader 都调用相同的滚动保存/恢复逻辑。单账号移动端的 `copyAdminContentToPanelVersion("health")` 在复制 PC HTML 前后保存和恢复移动容器滚动位置。

不改变现有健康状态中文文案、权限组或 Vue 组件。

## Error Handling

- 诊断采集任一运行时对象失败时使用 `None` 或 `-1`，不影响 `/health` 主状态聚合。
- 管理员诊断渲染字段为空时显示 `--`，原始 JSON 仍保留完整诊断值。
- 首次加载失败时显示现有错误提示；已有内容刷新失败时保留旧内容并恢复滚动位置。
- `/health` 继续使用现有组件状态和 200/503 状态码规则。

## Verification

- Python 单元测试验证单调时钟、禁止缓存头、管理员诊断可见性和非管理员隔离。
- Node 静态行为测试验证 PC、多账号移动端 loader 都使用滚动快照、禁止缓存和内存诊断渲染；验证通用滚动辅助函数能恢复保存位置。
- 运行 `node --check scripts/main.new.js`、`python -m py_compile main.py` 和 `git diff --check`。
- 运行健康相关 Python/Node 测试，并记录与本任务无关的既有 Vue parity 测试失败。
