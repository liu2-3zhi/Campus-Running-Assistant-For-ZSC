# Agent 接手说明

本文件用于记录本仓库已经踩过的坑、稳定约定和后续 Agent 必须继续补充的经验。每次完成一个值得复用的修复、排查出真实根因、或用户明确指出同类问题重复出现时，都要更新本文件。

## 基本工作规则

- 开始改动前先看 `git status --short`，确认是否有用户或上一轮 Agent 留下的改动；不要回滚无关改动。
- 一件事完成并验证后就立即 commit，不要把多个已完成任务堆在一起。
- 中文任务使用中文提交信息，提交信息直接说明修复内容。
- 前端可见行为变化必须更新 `version.json`，`version` 使用日期加随机字母数字后缀，例如 `20260728-P4xL8v`；不要用纯时间戳后缀或特殊字符。
- 修改 `version.json` 时同步更新 `build_time` 为当前实际时间。
- 旧版主脚本为 `scripts/main.js`；`Check_for_updates.js` 在 HTML 解析期间读取 `localStorage.siteVersion`，同步插入带 `?version=` 的 `defer` 标签。只有检查更新脚本负责写入该存储项；首次访问或存储不可用时用时间戳防缓存。不要在异步请求返回后才插入主脚本，以免错过 `DOMContentLoaded` 初始化。CDN 缓存键必须包含查询参数。
- 有值得学习的地方就写入本文件，不要只把经验留在对话里。

## 安全要素

- 路径规划诊断统一写现有日志，由 `diagnostic_id` 关联浏览器命令、供应商回调与最终失败；不要另建账号日志或持久化诊断文件。`log_and_notify_frontend` 同时写服务器日志和通知前端，具体原因与前端文案必须分开选择。
- 单账号失败摘要只保存在后台管理器独立内存中，每会话当前批次最多 20 条、每条 JSON 最多 2 KiB；不得附加到会保存的内部任务对象。HTTP 详情按已验证调用者权限过滤，多账号前端详情按目标会话所属系统账号角色过滤；SocketIO 加入房间也要校验现有会话凭证。
- 管理员查看态分开保存来源认证和目标业务会话，连续查看始终保留最早来源。来源上下文须由服务器验证并通过 `admin_view_context` 返回；学校账号登录和业务页面初始化不能清除来源。强制查看不能调用会轮换 Token 的 `/auth/switch_session`；该接口仅允许真实调用者自己的目标会话。
- 后台任务阻塞返回后，写状态、提交生成路线及释放账号执行锁前均须匹配原执行批次，避免旧线程覆盖新任务。真实页面事件监听应安装在浏览器工作线程中，并为队列命令单独传递诊断上下文。

- 不要把用户在对话、日志、截图或本机配置里提供的真实 Key、Token、Cookie、密码、验证码服务器 Key、地图 Key 写入代码、测试、文档、提交信息或 PR 描述；需要示例时使用占位值。
- `configs/`、`.env`、本地运行配置、用户导出的配置、日志和临时调试文件默认按敏感文件处理。提交前必须确认没有把这些文件加入暂存区；除非用户明确要求并确认已脱敏，否则不要提交。
- 不要在生产代码、测试、注释或文档中写入本机绝对路径、用户名、私有目录结构，尤其不要留下“参考某个本地路径里的接口文档”这类注释。需要说明契约时写成通用 API 契约，不暴露本机路径。
- 验证码服务器、地图供应商等第三方服务的服务地址和 Key 只应由后端配置或后端代理使用；浏览器端应访问同源代理接口，不要把后端专用 Key 直接暴露给前端。
- 与验证码服务器兼容时，二验结果应由后端作为最终判定；前端只能提交一次验证结果标识，不能绕过后端二次校验。
- 涉及客户端 IP、代理来源或限流键时，带 Key 的请求不能回退使用连接来源地址；只有明确传入且校验为公网地址的 `clientIp` 才能作为 authenticated 限流键。
- 提交前至少检查暂存内容和敏感字符串：`git status --short`、`git diff --cached --stat`、`git diff --cached --name-only`，并对本次改动文件搜索本机路径、真实 Key 片段、`configs/` 和调试日志痕迹。
- 如果发现敏感信息已经进入 Git 历史，不要只改最新文件；需要先告知用户，清理历史、强制推送前确认范围，并提醒相关 Key 需要轮换。
- 不要保留不必要的 AI 贡献者、协作者署名或生成痕迹；提交作者、commit trailer、文档署名应保持项目原有风格。

## 本地图片验证码测试

- 在已获准执行的本地登录回归测试中，从当前页面验证码 iframe 的 `/api/captcha/html/<captcha_id>` 地址取得本次 `captcha_id`，读取仓库下的 `logs/captchas/<captcha_id>.json`。不要从旧截图、旧 ID 或 `logs/captcha_history/` 猜答案；历史记录中的 `code` 已脱敏为空。
- 将 JSON 作为结构化数据读取，确认文件存在、`id` 与页面当前 ID 一致、`code` 非空且当前 Unix 时间小于 `expires_at`，然后把 `code` 自动填入当前页面的验证码输入框并正常提交登录。PowerShell 可用 `Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json` 读取，`$path` 应由仓库相对路径和当前 ID 构造。
- 本地图片验证码是一次性的，`verify_captcha()` 校验后会删除对应文件；过期或提交失败时刷新页面验证码，重新取得 ID 和文件。行为验证码不使用这个文件，仍按其服务端二验流程处理。
- `logs/captchas/` 含有效验证码，按敏感临时文件处理；不要把实际 `code`、完整 JSON 或本机绝对路径写入对话、测试、文档、日志、提交或 PR，也不要暂存这些文件。本规则仅用于本地测试，不用于线上站点。

## 地图密钥下发与会话密钥生命周期

- 前端只返回当前实际需要的地图供应商密钥；`map_providers` 只能包含脱敏元数据，密钥密文放在 `map_provider_key_bundle` 中，不能一次性下发所有供应商密钥，也不能暴露具体加密算法字段。
- RSA 密钥对只保存在服务进程内存中，服务每次启动都必须生成新的密钥对；私钥不得下发给前端，`/api/map_key_runtime.js?v=<runtime_version>` 只能对当前会话下发禁止缓存的运行时调用壳。
- 前端运行时可以在闭包内生成不可导出的临时密钥对，但模板和下发脚本都不得包含可复用的私钥材料或可离线复原的明文算法片段；实际地图 key 只允许通过 `/api/map_provider_keys/decrypt` 返回给当前会话临时公钥对应的混合密文（RSA 包装 AES 密钥，AES-GCM 包正文），再由前端闭包内解密。
- 运行时脚本下发前必须做服务端随机混淆，不能只压缩空白或去注释；响应正文不能直接出现运行时命名空间、版本号等可读材料。
- 同一认证用户存在活动会话时，新会话复用该用户的运行时密钥对；用户最后一个会话被清理后，必须删除用户映射及无引用的运行时上下文。匿名会话不能在不同认证用户之间共享上下文。
- 运行时密钥接口必须先验证 `X-Session-ID` 对应的活动会话，再校验 `v`；无会话、未知 UUID 或跨会话的运行时版本只能返回不可用结果，不能分配或返回可解密私钥的脚本。
- 不要把 `map_key_runtime.js` 或其模板放在普通 `/scripts/<filename>` 静态资源路径；解密脚本必须走 API，部署层也必须显式拒绝 `/scripts/map_key_runtime.js`，以避免 CDN 或静态缓存返回错误上下文。
- `ENABLE_FRONTEND_JS_ANTI_DEBUG` 默认必须为 `False`；开启后，所有 JS 响应统一去注释、压缩空白、移除 source map 指示并注入轻量反调试守卫。该机制只用于提高浏览器端分析和 Hook 的成本，不能替代服务端鉴权、会话绑定、密文下发或密钥轮换。
- `/api/frontend_config.js` 从 `Referer` 恢复会话时，只能恢复已有内存会话或确有持久化状态的会话；格式合法但未登记的 UUID 不得被创建并长期占用资源。
- Vue 新版 UI 和根目录 `index.html` 使用的老版 UI 都必须完成运行时脚本加载和地图密钥解密。修改新版组件时要同步检查 `scripts/main.js` 的老版入口、初始数据、地图配置保存和登录响应链路。
- 日志、支付操作日志、前端 `appConfigLoaded` 事件和错误信息不得输出原始地图 Key、Token、密码、验证码、签名或完整配置；密码恢复等流程只能记录数量和状态，通用参数日志统一使用递归脱敏函数。

## 地图 iframe 与代理验收经验

- 百度 JS API v4 的地图实例与 `BMap` 构造器必须留在各自 iframe realm；父页面只保存 realm 句柄，销毁时先清覆盖物/事件，再移除 iframe 并清空 `window` 引用，避免 SDK 异步回调污染下一代地图。
- iframe 使用 `srcdoc` 时，`about:srcdoc` 不能作为 `Request` 的 URL 基址；代理重写优先采用继承文档的 HTTP `document.baseURI`，并确认请求不携带父页面路径、会话 UUID 或 Cookie。
- 真实地图验收必须逐轮保留失败记录。供应商上游 `ReadTimeout`、代理 `502`、错误 MIME 与 SDK `pageerror` 不能由后续成功轮次覆盖；连接建立阶段仍受底层 DNS/TCP 超时约束，不应宣称被响应体截止器完全取消。
- 支付订单查询、订单列表和后台订单详情必须通过字段白名单返回；待支付链接只在已鉴权的待支付订单查询中返回，平台原始响应、通知参数、支付参数、主动查询令牌哈希和退款原文不能返回。支付日志读取接口也要在返回前递归脱敏，兼容旧日志文件。

## 地图供应商相关入口

- 非高德地图的真实前端渲染主要在 `scripts/main.js` 的 `initProviderMap()`、`ensureSingleMap()`、`initMap(AMap)` 相关链路，不要只看 `index.html` 的静态容器。
- 地图供应商前端运行时的重点测试是 `tests/map_provider_frontend_runtime.test.mjs`。
- 后端供应商路线规划合同主要看 `tests/test_map_provider_business_execution_contract.py`、`tests/test_map_provider_backend_contract.py`、`tests/test_map_provider_runtime_guards.py`。
- 地图控件、SDK 加载、右键拖动、3D 视角这类问题，自动化测试通过后，尽量再直接加载真实地图验证；用户截图反复指出的问题不能只靠静态代码判断。

## 腾讯地图控件踩坑

- 腾讯左上角视角控件优先使用 SDK 原生 `ROTATION` 控件，初始化时 `showControl` 需要保持为 `true`；右上角缩放仍用应用自绘控件，因此只移除 `TMap.constants.DEFAULT_CONTROL_ID.SCALE` 和 `ZOOM`，不要移除 `ROTATION`。
- 腾讯原生视角控件位置通过 `getControl(DEFAULT_CONTROL_ID.ROTATION).setPosition(TMap.constants.CONTROL_POSITION.TOP_LEFT)` 修正；不要再默认渲染 `provider-3d-view-btn` 自绘左上角控件。
- 应用自绘控件必须挂在外层地图容器上，不能挂在 SDK surface 里，否则会被 SDK 自己的 DOM 层级影响。
- 腾讯自定义 SVG 标记使用 `TMap.MultiMarker` / `MarkerStyle` 时，不要给 `PointGeometry.content` 填文字；否则 SDK 会额外渲染一份原生文字，造成双重标签。需要文字时应放进自定义 SVG 或应用自己的 marker 样式里。
- 腾讯实时位置标记不要在每次轮询时 `setMap(null)` 后重建 `MultiMarker`。多账号位置应复用同一标记对象，使用相同 `PointGeometry.id` 调用 `updateGeometries()` 原位更新；旧 SDK 不支持时再退回 `setGeometries()`。否则高频刷新会触发 SDK 移除图层异常，表现为标记反复消失/出现并刷出 `getSource` 报错。
- 天地图和百度实时位置标记同样不能在每次轮询时删除重建；应分别调用 `T.Marker.setLngLat()` 和 `BMap.Marker.setPosition()` 原位更新。高德当前已有 `setPosition()` 路径，四个供应商的实时位置标记都应保持对象稳定。
- 多账号标记颜色必须按账号稳定缓存，不能在每次位置刷新时递增全局颜色索引；否则即使标记不重建，颜色也会持续变化。相关回归测试见 `tests/map_provider_frontend_runtime.test.mjs`。
- 活动任务路线渲染要传 `showEndpoints:false`，不要让 SDK 或通用渲染层额外加“起点/终点”标记；第一眼可见的标记应该是实际检查点名称。
- 右上角缩放等级不能写死为 `17`。腾讯地图要用 `getZoom()` 读取真实缩放，并监听官方 `zoom` 事件刷新标签。
- 腾讯缩放按钮优先走 `getZoom()` + `setZoom()`，这样按钮点击后能立即同步显示数值；不要只调用 `zoomBy()` 后等待未知的 SDK 状态。
- 自绘左上角 3D/视角控件代码可以保留，但只作历史兜底代码，不要接入腾讯或百度默认初始化路径；如果真实 SDK 原生控件可用，必须优先使用原生控件。

## 百度和天地图控件踩坑

- 百度地图统一使用 JS API v4 的 `BMap` 命名空间与默认 BD09；不要混入 v1、`BMapGL` 或 `coordType: 3`。业务 GCJ-02 只在 SDK 输入、输出边界转换一次，公开折线/标记的 setter 和点击结果也必须经过相同边界。
- 百度左上角视角控件优先使用 v4 原生 `NavigationControl3D`，不要默认叠加 `provider-3d-view-btn` 自绘控件；初始化时如果发现旧自绘 overlay，要清理掉。
- 百度地图的视觉缩放比例和其他供应商不完全一致，默认/复位缩放用 `18.0`；天地图默认/复位缩放用 `17`。不要把所有非高德供应商统一写成同一个整数缩放。
- 百度原生 `NavigationControl3D` 如果用 `BMAP_ANCHOR_TOP_LEFT` 还离左上角太远，检查 `BMap.Size` offset；当前应贴近左上角，使用 `new BMap.Size(12, 12)`。
- 百度和天地图的左上角/右上角缩放数字不会自动跟随 SDK 原生缩放，必须绑定 SDK 缩放事件后再调用 `updateProviderMapZoomLabel()`；百度监听 `zoomend` / `zoom_changed`，天地图监听 `zoomend` / `zoom`。
- 天地图缺少右键拖动时，需要在 SDK surface 上自定义右键拖动并调用 `panBy()`，同时阻止浏览器默认右键菜单。
- 天地图标记点必须显式显示点名称，不能只画图标，否则会和百度、高德表现不一致。
- 任务执行中用户拖动地图、滚轮缩放或调整视角后，应在空闲 2 分钟后自动复位到当前任务路线/默认视角；该逻辑要同时绑定 SDK 拖拽事件和地图容器 DOM 用户输入事件，并在任务停止、完成、错误或手动复位时清理定时器，避免影响下一次打开任务页面。
- 不要把 SDK 的通用 `zoom/move/rotate/pitch` 变化事件直接当成用户操作；路线刷新、自动复位或程序调用 `setZoom()` / `fitBounds()` 也可能触发这些事件，容易导致 2 分钟复位计时被程序行为反复刷新。

## 地图配置生效规则

- 系统配置里修改地图提供方或地图 Key 后，不要立刻 `syncMapProviderConfigFromInitialData()`、`destroySingleMap()` 或重新 `initProviderMap()`；当前页面只应 `queuePendingMapProviderConfig()`，等下一次地图初始化再应用。
- 任务执行中必须避免突然切换地图。后台任务启动时要把当时的 `map_provider` 写入任务状态；`get_initial_data` 只在任务 `running` / `paused` 时返回 `task_status`，前端据此锁定当前地图提供方。
- 浏览器关闭后再打开仍要考虑运行中任务：不能依赖页面内存里的 pending 状态。前端初始化如果看到运行中的 `task_status.map_provider`，应优先使用任务绑定的地图提供方，把最新配置继续留到任务结束后的下一次地图加载。
- `applyPendingMapProviderConfigIfAny()` 应先检查后台轮询、执行视觉态和任务 provider 锁；只有确认没有执行中的地图任务，才允许应用 pending 配置。

## 地图来源与代理验证

- Vue 状态轮询必须请求完成后再间隔调度，单次手动查询不能因回填 `app.isRunning` 意外启循环；此类回归要使用真实 Vue watcher，空 watcher 替身会漏掉响应式联动。状态合并不能等待地图几何，取消旧请求的 finally 也不能清除新请求。
- 百度 SDK 鉴权与路线码分开。仅接收当前百度命令实际捕获的可信鉴权对话框，独立于普通事件上限保存；真实“APP不存在，AK有误”提示附官方控制台链接但没有数字码，不要推测为 220。成功路线和明确路线业务码优先。诊断重复脱敏必须幂等。
- Vue 原生地图使用浅引用，卸载前使代次失效并开始清理；两套前端每代原生宿主 ID 独立，SDK/DOM/按钮回调绑定具体实例。腾讯图层公开 destroy 与 Map 的 destroyed 事件不同：点标记 stopMove/setMap(null)，折线和文字 destroy，Map 最多等待 5 秒；超时隔离旧宿主并阻断复建，不能按已完成处理。高德 loader await 后仍须校验代次，百度回调名须跨组件唯一。
- 严格浏览器验收必须分别保留功能结果和生命周期结果，任一脚本异常、未处理拒绝、错误 MIME、代理失败或非预期直连均阻断通过；失败轮次不能被后来成功覆盖。纯 SDK 对照须对齐实际标签类型及更新调度节奏。合成账号/任务验收和真实地图请求分开，详见 `docs/map-final-fixes-validation.md`，未全绿不能宣称全部完成。
- 地图代理短突发采用有界等待，保持 12 个上游活跃请求、最多额外 24 个等待且最多等 3 秒；异常关闭响应也须释放活跃与准入许可，不能通过无限排队或增大并发掩盖压力失败。
- 腾讯 MultiLabel 在 `geometry_processed` 前仍引用地图字形资源；移除时先隐藏并等待公开事件，再销毁文字和地图。释放超时只结束前端等待，不能取消迟到的实际释放，否则旧地图永远无法清理并重试。
- 天地图仅对指定 `vec/cva` WMTS 瓦片 GET 在总截止时间内最多尝试两次；超时、连接和分块传输中断可重试，脚本、鉴权和路线不套用瓦片重试。验收按同一请求汇总最终结果，同时保留恢复前的失败尝试，不能把恢复成功计为最终 502。
- `backend_page_origin` 只保留 HTTP/HTTPS 协议、主机和端口，按供应商覆盖、全局、当前请求来源依次解析；不能下发到普通初始化或密钥包，也不能携带 UUID 到配置域名导航。后端浏览器来源页由本地 `route.fulfill()` 提供，来源与执行必须位于同一个队列命令。
- 前端代理启用后，SDK、JSONP、瓦片、动态 HTML/CSS 与 Worker 请求都要经过同源白名单代理。不能只验证 SDK 首个脚本；真实验收要检查地图初始化、规划、动态 setter 和是否出现直连。
- 不要用正则改写 SDK 的协议片段：高德实际使用 `protocol + "://restapi.amap.com"`，百度也会单独拼接协议。应保留片段，在浏览器请求入口代理完整 URL；百度根路径查询必须支持 `/` 和多余的根斜杠。
- 高德 JSONP 可能返回 `application/json` 或 `application/octet-stream`。保留 `nosniff`，仅在唯一合法回调、精确回调包裹及严格 JSON 均通过时纠正 MIME；不能把任意 JSON、HTML 或额外脚本提升为 JavaScript。
- 腾讯 `confinfo` 会返回 `callback&&callback(JSON)` 和 `text/plain`；只允许同一个已验证回调的精确守卫包装，不能接受其他表达式。Vue 的 SDK 脚本缓存应使用原始请求 URL，不能拿代理改写后的 `script.src` 比较，否则重建组件会重载高德 Loader。
- 地图容器初始化前保持布局尺寸，可用 `visibility:hidden`，不能以 `display:none` 隐藏后再创建腾讯 GL 地图；天地图 `T.Marker` 没有 `setTitle()`，标题放构造参数并通过 `T.Label` 显示。验收时天地图坐标 getter 自身会舍入，预期值须按同一 SDK getter 规范化，不能修改业务坐标迎合测试。
- 代理凭证须在过期前续签；鉴权失败不能恢复直连。初始化和续签要隔离旧会话响应，成功鉴权只维持真实调用者的内存活跃时间，不新增每瓦片 Token 保存。
- Nginx 必须保留请求 Host 的非默认端口，且包括 HTTP 重定向在内的访问/错误日志不能记录地图代理查询串。Python 的统一脱敏还必须覆盖 `ak`、`tk`、`jscode`、`securityJsCode`，包括 urllib3 DEBUG 记录。
- `tests/browser_map_proxy_smoke.py` 是显式启用的真实后端代理验收，凭据只从环境变量进入内存；不得把真实 Key、Token、原始响应或完整路线写入脚本、配置或验收记录。
- 地图请求代理开关 `Map.frontend_proxy_enabled` 默认关闭，旧版运行时快照和初始化合并都要传递显式 `true/false`，缺字段保留现值；管理员保存后的前端配置读取失败时，回退更新也要保留开关。已执行 SDK/Worker 中的代理 URL 不能靠卸载请求 hooks 逆转，模式切换须在下次加载地图时整页重载，不能复用另一模式的 SDK 缓存。
- 后台任务启动、状态、停止接口都须验证真实调用者及显式管理员来源，再按调用者权限执行；游客同时核对 Token 索引与实体文件且不增加轮询写入。旧版路线快照按会话/执行批次/任务合并进行中的请求，不能因下一次 3 秒轮询到来持续作废慢快照。返回时合并更晚 WebSocket 位置；新批次、路线未就绪、任务切换和停止必须使旧请求失效。相关回归见 `tests/test_background_task_route_auth.py`、`tests/legacy_task_map_restore.test.mjs`。

## 坐标转换踩坑

- `wandergis/coordtransform` 是常见坐标系互转工具，不是高精度增强库；它的 `gcj02towgs84` 是一次近似反推，不应替换当前迭代逆解。
- 高德地图和腾讯地图业务坐标同为 GCJ-02；“高德转腾讯”不应套 WGS84 或 BD09 偏移，前端转换只做数值归一化和无偏移拷贝，避免共享原始对象或未来被误加 datum shift。
- 当前前端 `gcj02ToWgs84()` 使用迭代逆解，目标是让 `WGS84 -> GCJ02` 回环误差进入厘米级。
- 后端天地图路线运行时也要保持同样的 GCJ02 -> WGS84 精确逆解，避免前后端坐标基准不一致。
- 高德官方 `AMap.convertFrom(points, "gps")` 可用于验证或提升 `WGS84/GPS -> GCJ02` 正向转换，但它不提供 `GCJ02 -> WGS84`。
- 如果问题是路径偏离道路，优先使用各供应商自己的步行路线规划返回 path，不要指望坐标转换后直接连线能吸附道路。

## 路线与标记显示规则

- 能用步行路线规划就用步行路线规划。
- Tencent WebService 返回的道路 path 可能缺少原始起点、终点或中间检查点；绘制前要补齐路径显示，但不能修改 `currentRunData.target_points` 或真实执行坐标。
- 标记点为了 UI 美观可以“显示层吸附”到供应商规划路径附近的道路点，但只能影响显示位置；`currentRunData.target_points`、`run_coords`、后端执行路径里的原始检查点坐标都不能被吸附结果覆盖。
- 执行路径必须保留所有原始 waypoint，包括中间检查点；如果供应商 path 里缺失这些点，要自动插入缺失点用于路径连续性和进度推断。
- 进度颜色不能只依赖 `target_sequence` 或 `checked_targets_count`。执行进度可能滞后，应该从 `current_point_index` 或 `current_position` 对 `run_coords` 推断。
- 已完成段用灰色，当前检查点用蓝色，未完成检查点用绿色，剩余路线用活动色；这套语义应对高德、腾讯、百度、天地图保持一致。
- 按执行位置切分路线时，如果当前位置恰好到达序列指定的检查点，必须继续寻找严格位于当前位置之后的检查点；最后一个检查点之后仍以蓝色连接路线终点，到终点后只剩完整灰色段。不能因目标索引等于当前位置就丢掉当前段。回归见 `tests/map_provider_frontend_runtime.test.mjs`。

## 路线规划限流和重试规则

- 地图供应商路线规划存在按秒计算的并发/频率限制时，不要把分段请求一次性并发打满；应采用队列式分段发起：第 1 个请求发起后间隔约 `0.1s` 发第 2 个，再间隔约 `0.1s` 发第 3 个，以此类推。
- 如果一轮分段请求没有任何成功，说明可能是整轮请求被限制或执行器初始化失败；这种情况下最多重试 2 轮，仍无成功就终止，避免无限等待。
- 如果一轮中已有分段成功，但后续分段失败，优先按秒级 API 限流处理：等待约 `0.5s` 后只重试未成功的分段，不要重做已成功分段。
- 连续 2 轮补发都没有任何新的分段成功时终止；只要某轮补发有新成功，就清零连续失败计数并继续补剩余失败分段。
- 这套调度语义应保持供应商无关，高德、腾讯、百度、天地图后端规划执行器都要一致；不要因为腾讯路径需要端点补全而改动真实执行坐标。

## 学校账号任务执行互斥

- 同一学校账号在同一时间只允许一个“任务执行”入口，包括单账号单任务、单账号全部任务、多账号单账号任务、多账号全部任务和后台任务；不能只依赖某个 `Api` 实例里的 `worker_thread` 判断。
- 执行互斥必须使用进程级学校账号执行槽，启动时原子占用并在线程结束时释放。多账号登录后还要把学号别名加入同一执行槽，覆盖“登录名与学号不同”以及“单账号页面与多账号页面同时使用同一学校账号”的情况。
- 单纯添加学校账号、刷新状态、读取通知不占任务执行槽；**添加“新”账号**不受其它账号（甚至同一学校账号的其它入口）正在执行的限制。
- 但对**已存在**账号重复调用 `multi_add_account` 不是“添加”，而是 `already_exists` 无操作，不得借它重建会话——见下面那条 `multi_add_account` 契约。
- 多账号 worker 在任务真正开始执行前必须把 `status_text` 改写成 `正在执行 i/n: <任务名>`（`n` 取本轮任务统计里的可执行数、只增不减且不小于 `i`；未知时退化为 `正在执行: <任务名>`）并重置进度：状态字段原先只在延迟/等待/完成时更新，任务运行期间停留在“延迟 0s”“等待 Ns”这类旧文案上；该字段就是前端列表（含管理员查看他人会话时看到的列表）显示的状态，不改写会让用户以为任务没在跑。进度文案 `运行 i/n: <任务名>` 的分母同样用这个计划任务数（`_run_single_multi_account_task(..., planned_total=...)`），不要退回成恒等于当前序号。相关回归测试见 `tests/test_multi_account_task_reloop.py`。
- 多账号的两种等待必须用可区分的文案，不能退回裸的 `延迟 Ns` / `等待 Ns`：开跑前是 `开始前等待 Ns: 待执行 i/n 个任务`，两个任务之间是 `任务间等待 Ns: 下一个 i/n · <任务名>`。裸文案分不清是“开跑前等”还是“任务之间等”，也看不出后面还有没有任务、下一个是第几个。等待态与执行态必须复用同一份任务名截断逻辑（`_shorten_task_name_for_status`），否则同一任务在两种状态下会显示不同名字。相关回归测试见 `tests/test_multi_account_task_reloop.py::TestWaitStatusTextsBehavior`。
- `multi_add_account` 对**已存在账号**分三档处理，不得退回“无条件从配置重读密码并强制重登”：
  1. **状态正常**（`is_first_login_verified` 为真且 `user_data.id` 非空）且**未给新密码** → 返回 `success=False, reason="already_exists"`，只允许更新 tag/params，**绝不清空 `acc.api_client.session.cookies`、绝不置空 `acc.user_data.id`**；
  2. **状态异常**（首次验证未通过 = 密码错误，或 `user_data.id` 为空 = 会话已失效）→ **允许覆盖**：写入新密码并重建会话。否则“密码填错了想改对”永远无法恢复，只能删掉再加回；
  3. **状态正常但用户显式给了不同密码** → 允许覆盖（用户明确要改密码），但该账号正在执行任务时必须拒绝并返回 `reason="account_running"`，提示先停止任务。
  覆盖前必须用 `_is_multi_account_execution_active()` 确认该账号没有在跑，落盘走共用方法 `_reset_account_session_for_relogin()`。
  批量导入走 `only_if_missing=True`：**不得用文件里的密码覆盖状态正常的账号**（文件密码可能过期或与本地记录不同），异常账号仍会恢复。
  真实事故（2026-10-11 19:07）：任务跑到 250/411 时前端对同一账号又提交了一次 `multi_add_account`，旧代码无条件清空会话，4 秒后下一次提交变成“0 个 Cookie、无 shiroCookie、无 Authorization”的裸请求，被学校服务器拒绝为 400 `userId不能为空`（这是**认证失败**的表象，不是业务字段缺失），重试 10 次后任务中止。相关回归测试见 `tests/test_multi_add_account_running_guard.py`。
- **密码只有在登录成功后才写入配置**，这是硬约束：`_save_config(username, password=None, ...)` 的语义是“保留现有密码”，因此凡是把密码落盘的地方都必须显式传密码。落盘时机只有两处，都在 `_multi_refresh_worker_unlocked` 里：首次登录验证成功的分支，以及已验证账号重新登录成功的分支（后者历史上写成 `_save_config(acc.username)`，导致用户改了密码即使登录成功也**永远写不进去**，已修）。
  改密码走“暂存 → 验证 → 落盘”：`multi_add_account` 对已存在账号用 `_stage_pending_account_password()` 把新密码只放进内存（同时用 `_password_before_change` 记住旧密码）并重建会话；登录成功由 `_commit_pending_account_password()` 落盘，失败由 `_rollback_pending_account_password()` 还原成原密码。这样“输错新密码”永远不会把原本可用的凭据弄丢。新增账号与改参数两条路径同样**不得**提前写未验证的密码（`_save_config(username, password=None, ua=...)` / `_save_config(username)`）。相关回归测试见 `tests/test_password_persistence_timing.py`。
- 缺密码账号补全走四阶段流程，且**缺密码账号不限数量**：任何展示环节都不得截断、不得“只列前 N 个”、不得出现“等 N 个”这类省略，一律用可滚动卡片完整显示。阶段 1 询问“发现以下账号缺少密码，是否要补密码？”并给出「放弃所有无密码账号 / 补全所有账号密码 / 补全部分账号密码」；阶段 2 是勾选表格（第一列勾选框、第二列账号，带全选与“已选 N / 共 M”）；阶段 3 逐个补密码并显示“当前进度 i/N，还有 N-i 个账号待补密码”，第一个账号的放弃按钮显示“放弃所有无密码账号”、后续显示“放弃剩余 N 个账号”；阶段 4 才弹导入结果。**阶段 2 一个都不勾选必须等价于放弃全部并正常收尾**（不得弹密码框、不得卡死）。所有退出路径（补完 / 跳过到队尾 / 放弃剩余 / 放弃所有 / 取消 / 关闭弹窗）必须汇聚到唯一收尾函数 `flushMissingFlowDone()`，否则登记了收尾回调的调用方（导入结果弹窗）会永远等不到、或者重复弹。`#multi-add-user-close`/`#multi-add-user-cancel` 在补密码流程中必须走“跳过当前”而不是直接关闭弹窗。相关回归测试见 `tests/test_missing_password_flow.py`。
- 导入账号的提示必须合并成**一个**弹窗，且汇总成功 / 跳过 / 失败**全部**结果（`【成功导入】`/`【已存在，未重复添加】`/`【缺少密码，已跳过】`/`【执行中，已跳过】`/【文件内重复行】/`【失败】`），为空的段落不渲染，名单同样不截断。弹窗必须等缺密码补全流程结束后才出现。**后端禁止再用 `self.window.evaluate_js("alert(...)")` 弹提示**：那会和前端弹窗形成两套提示，而且历史上只列前 20 个；缺密码提示的唯一出口是阶段 1。`multi_import_accounts` 的返回必须带 `imported_count`/`already_exists_count`/`skipped_count`/`failed`/`accounts_missing_password`/`accounts`，其中 `already_exists` **不得**计入 `imported_count`。`accounts_missing_password` 的键名与 `multi_load_accounts_from_config` 保持一致，便于前端复用同一套队列。相关回归测试见 `tests/test_multi_import_accounts_merged_summary.py`。
- 导入文件解析必须兼容“标题行 + 表头”“只有表头”“没有表头”三类表格，不能把固定列位当唯一格式：先按表头别名（账号/用户名/学号、密码/初始密码、标记/标签/备注）定位列，表头行按**匹配度打分**选取（标题行即使含“账号/密码”二字也不能顶掉真正的表头）；识别不到表头时按数据内容推断学号列（最左、且大多数值为 ≥4 位纯数字），推断不出才退化为第 1/2/3 列。下载模板必须**直接返回** `tests/fixtures/school_accounts_template.xlsx` 的字节（合并标题 + `序号/账号/密码/标记` + 预编排行）；只有该文件缺失/为空时才回退到内置同版式生成，序号列只用于人工对行、导入时忽略。相关回归测试见 `tests/test_multi_import_format_compat.py`。
- 学号必须是**纯数字且至少 4 位**（`main.is_valid_school_username`，`^[0-9]{4,}$`），密码不得包含中文字符（`main.is_valid_school_password`）。`multi_add_account`、`multi_import_accounts`、管理端 `/api/admin/school_account/save|update` 必须在写入前校验；导入汇总单独给出 `invalid_username`/`invalid_password` 分类（旧版弹窗对应 `【学号格式不对，已跳过】`/`【密码包含中文，已跳过】`，Vue 日志显示对应计数）。加载与保存层（`_load_user_school_accounts`、`_save_user_school_accounts`、旧版 INI 扫描、`_save_config`/统计/备份 INI 写入）必须过滤或拒绝非法学号，避免 `1.ini..21.ini`、`序号.ini` 这类坏数据被再次写回。事故背景：名单的“序号/姓名”列曾被当成“账号/密码”导入，产生 22 条 `password=姓名` 的记录。
- 仓库保留两个真实模板 fixture：`tests/fixtures/school_accounts_template.xlsx`（当前模板，带标题与序号列）和 `tests/fixtures/legacy_accounts_template.xlsx`（旧版 `账号/密码/标记`）。测试必须直接读取真实文件，并覆盖空模板、填入行、旧模板、无表头、无表头带序号列、名单误导入、中文密码等场景。
- `_run_single_multi_account_task` 这类“抽出的大方法”里，所有被末尾 `return` 引用的结果标记必须在函数早期无条件初始化（例如 `task_succeeded = False`）。只在 `if submission_successful:` 的 if/else 里赋值，会让“提交失败”这条正常分支抛 `UnboundLocalError` 并让整个 worker 崩溃。判定标准是**真正驱动那条分支**，只断言源码里存在赋值语句抓不到。相关回归测试见 `tests/test_multi_account_submission_failure_path.py`。
- 多账号收尾状态文案固定为“状态词 + (成功/总数)”（`全部完成 (3/3)`、`全部失败 (0/3)`、`部分成功 (1/3)，2个任务失败`、`无任务可执行`）。状态词必须原样保留，因为 `getMultiAccountStatusClass` 按这些词着色；前端匹配必须用 `includes` 而不是整串相等，否则带数量的文案会掉进默认色。相关回归测试见 `tests/test_multi_account_completion_status.py`。
- 「仅执行未完成的任务」开关（`set_multi_run_only_incomplete`）切换时必须立即用各账号已缓存的任务列表重算 `acc.summary`（总数/完成/未开始/可跑/过期）并按新规则刷新状态文案，同时把最新 `accounts` 返回给前端立即重渲染（legacy 走 `renderMultiAccountList`，Vue 写回 `appStore.multiAccounts`）。只改标志不重算会让列表统计停留在旧规则（真实缺陷：完成 6 / 可跑 1 / 过期 5 在勾选/取消后完全不变）。统计口径统一走 `_summarize_multi_account_run_data()`：勾选时已完成任务只计入 completed，不勾选时已完成任务仍按时间状态参与可跑/过期/未开始统计。运行中的账号只刷新统计数字、进度文案不动；已停止/已中止/已取消与错误态不得被开关切换覆盖；还没拉取过任务列表的账号不得被凭空写成“无任务可执行”。相关回归测试见 `tests/test_multi_run_only_incomplete_summary.py`。
- 停止账号任务后状态文案必须停留在“已停止”：`multi_stop_single_account` 的停止看门狗在 worker 线程退出后不得无条件写“待命”，否则会覆盖 worker 收尾写入的“已停止”（真实缺陷：点停止后列表显示“待命”）。看门狗只在 `stop_event` 未置位且当前不是需保留状态时才回落“待命”。相关回归测试见 `tests/test_multi_run_only_incomplete_summary.py::StopStatusTextTests`。
- `_multi_account_worker()` 在 `_select_next_multi_task()` 返回 `None` 且本轮尚未尝试任务时，必须在该分支显式写入“无任务可执行”；不要把此判断放到任务执行之后检查 `attempted_task_keys`，此时集合必非空且分支不可达，最终会被收尾逻辑显示成“待命”。
- `_multi_fetch_and_summarize_tasks()` 只能在整轮任务列表成功拉取后替换 `all_run_data` 和 `summary`；接口失败要返回失败信号并保留上次成功快照，worker 应显示刷新失败而非误报“无任务可执行”。返回成功的空列表才代表确定无任务。相关回归测试见 `tests/test_multi_account_task_reloop.py`。
- `_update_account_status_js()` 必须无条件更新账号对象上的 `status_text`/`progress_*` 字段，socket 推送只是附加通道：多账号列表的轮询接口 `multi_get_all_accounts_status` 读的就是这些字段，缺 `socketio` 或会话 ID 时直接 return 会让状态栏永远停在旧文案。

## 登录和会话提示规则

- 2FA 登录不能只凭“用户名 + 验证码”完成。密码或短信验证通过后，后端必须签发短期、单次使用的 `two_fa_challenge`；前端在新版和旧版 UI 中都必须回传该 challenge。`pyotp` 缺失或用户未启用 2FA 时不得 fail-open。
- 认证用户名必须经过服务端 `USERNAME_PATTERN` 校验；用户级 `school_accounts` 文件名不得直接拼接原始认证用户名，必须使用安全存储键或哈希，避免目录穿越。
- `/api/<method>` 必须使用显式 API 白名单，禁止反射调用任意 `Api` 公开方法；涉及目标用户身份的接口必须从当前会话推导身份，不能信任请求中的 `auth_username`。
- 不提供面向浏览器的 `/execute_js` 路由。服务端 Playwright 脚本只能由后端内部地图规划链路调用，并由会话、操作类型和参数共同约束。
- 支付同步跳转参数 `jump` 只能接受同源 URL 或站内相对路径，并在内联脚本中使用安全 JSON 编码。
- 代理 IP 解析必须从右向左遍历 `X-Forwarded-For`，跳过内网/回环地址和 `trusted_ips.txt` 中的外部可信代理。`trusted_ips.txt` 只记录外部代理，支持单 IP、CIDR、起止区间和 `*`；内网地址内置信任。使用 `*`、文件为空、文件不存在或加载失败并自动全信任时，必须在控制台输出红色警告。
- 用户级会话必须有 `auth_token` 校验。持久化会话恢复、登录装饰器、管理员装饰器都不能只信任 `X-Session-ID`。

- 遇到 `POST /api/get_initial_data 401`、`会话已失效`、刷新后登录页仍弹旧提示、或需要连续登录多次才正常的问题时，先从日志和通用 `/api/<path:method>` 包装层追踪，不要只看 UI 表象。
- `get_initial_data` 属于认证可选初始化链路，后端要允许不可恢复 session 降级到只读初始化上下文；这个临时上下文不能污染后续 session 活动。
- 前端相关链路重点看 `getApiRequestSessionHeaderValue()`、`callPythonAPI()`、`handleAuthLogin()`、`loadInitialData()` 和 `showAuthLogin()`。
- 切回登录页或认证登录页时应清理旧的 `logout-elsewhere-overlay`；当登录页已可见、登录中、或当前没有可用 session 时，应抑制过期会话和多设备登录旧响应，避免未登录状态继续显示倒计时提示。
- 管理员从老版 UI 查看不属于自己的会话时，只能进入“查看态”：前端记录来源会话并随 API 请求发送 `X-Admin-Origin-Session-ID`，后端用来源会话验证管理员身份和权限，但业务 API 仍操作目标会话；切到管理员自己的会话才允许走普通 `/auth/switch_session`。
- 老版 UI 只有 `callPythonAPI`/`callPythonAPI_raw`（都调用 `addAdminViewOriginSessionHeader`）链路会带 `X-Admin-Origin-Session-ID`；裸 `fetch`（例如 `/api/check_overdue`）只带 `X-Session-ID`，必须自己补来源会话头。因此 `login_required`/`admin_required` 和通用 `/api/<path:method>` 都要有“查看态身份兜底”：用 cookie token 反查调用者（`TokenManager.resolve_username_by_token`），要求 token 持有者不是被查看会话的持有者、token 仍有效、且具备 `view_all_sessions`。**能进入他人会话的不一定是超级管理员，禁止把兜底写成“只认 `Admin/super_admin`”**；`admin_required` 再用反查到的真实用户组过管理员组检查。通用 API 的这个兜底不能用 `reason == "token_mismatch"` 当门槛：被查看用户的 token 文件缺失或过期时 reason 是 `no_token_file`/`token_expired`，查看者自己的凭证仍然有效，卡门槛会让正在查看他人会话的管理员 401 掉线。
- 管理员查看态的来源会话必须续期：查看态请求是来源会话仍在使用中的唯一证据，`resolve_admin_origin_session_context()` 校验成功时必须调用 `touch_admin_view_origin_session()` 同步 `session_activity`、`browsing_activity` 和保活窗口。否则管理员进入他人会话后来源会话不再收到 API 流量，会话不活跃监控会在 `session_inactivity_timeout` 后回收它；回收时因为该用户没有其他浏览行为还会删除 token 文件（`TokenManager` 每用户只有一个 token，`verify_token` 不校验 session_id），查看态随后整体 401。保活窗口当前是 `ADMIN_VIEW_ORIGIN_KEEPALIVE_SECONDS`（1800s），窗口过期后还可以用 `is_admin_view_origin_owner_active()`（查看者 token 最近仍被刷新）继续保活，浏览器彻底关闭后来源会话必须能回到普通回收逻辑；会话被显式销毁时要 `clear_admin_view_origin_session()`。保活更新只是辅助状态，内部异常必须吞掉，不能影响鉴权结果。
- 老版 UI 的 `refreshUserList` 30 秒轮询在 socket.io 连接成功后会被清掉，`/auth/check_uuid_type` 也不带会话头，所以查看态页面可能长时间没有携带 `X-Admin-Origin-Session-ID` 的请求；只靠保活窗口会把掉线时间推迟到约 30 分钟。任何 API 请求都要尽量带上来源会话头（`callPythonAPI_raw` 已补），并且来源会话回收时不能连带吊销查看者的 token。
- `localStorage["admin_return_origin"]` 是纯前端记录，来源会话被销毁（例如管理员查看他人会话时关闭浏览器，来源会话被回收）后它不会自动消失，会导致右上角一直显示"返回管理员会话"，点进去跳到已销毁的 UUID。前端必须在三处主动清理：`checkAdminReturnState()` 显示按钮前用 `/auth/check_uuid_type` 确认来源会话仍然存在（返回 `unknown` 就清记录并隐藏按钮，同一来源会话只校验一次并复用请求）、登录成功（含 2FA 验证成功）、`createNewSessionFromPicker()` 创建新会话成功后调用 `clearAdminReturnOriginState()`。回归测试：`node --test tests/admin_return_origin_state.test.mjs`。
- 会话列表中的多账号登录状态不能直接读取 `Api.login_success` 或 `AccountSession.login_success`；必须基于当前 `accounts` 列表实时判断，只要仍存在任意 `is_first_login_verified=True` 的账号才显示已登录。已通过验证的账号从列表移除后，不能继续由旧状态让会话保持已登录；会话恢复时也必须恢复该验证标志。相关回归测试见 `tests/test_auth_session_lifecycle.py`。
- 老版 UI 用模板字符串生成内联 `onclick` 时，不能把 `JSON.stringify()` 的双引号参数直接塞进双引号属性；应对参数字符串做属性转义，并用单引号包裹 `onclick` 属性，否则浏览器会把事件属性截断，表现为按钮没有事件触发器。

## 欠费拦截与绕过欠费权限

- 新增权限 `bypass_overdue`（默认仅 `admin`/`super_admin` 为 True，`guest`/`user` 为 False）：既要写进 `main._create_permissions_json()` 的四个权限组模板，也要写进 `auth_system.BUILTIN_PERMISSION_DEFAULTS`，让已存在的 `permissions.json` 在启动时**只回填缺失键、不覆盖已有值**。管理员可以在用户管理里把它单独授予普通用户，因此“有欠费权限的用户不一定是管理员”，服务端一律用 `auth_system.check_permission(user, "bypass_overdue")` 判定，不能用权限组代替。
- `/api/check_overdue` 必须返回 `can_bypass_overdue`（是否有权限）、`is_admin`（是否管理员/超管，决定警告弹窗是否出现“此次不计费”）、`available_runs`（当前可用执行次数，-1 表示无限）。欠费弹窗在 `can_bypass_overdue` 为真时显示 `强制执行` 按钮；点击后若 `available_runs != -1 且 <= 0`，弹出“执行次数不足”警告：普通用户只看到“继续执行”（仍会生成欠费账单），管理员额外看到“此次不计费”。
- 所有启动入口都必须同时支持 `bypass_overdue`（强制执行意图）与 `waive_charge`（本次不计费）：`start_single_run`、`start_all_runs`、`multi_start_single_account`、`multi_start_all_accounts`、`/api/background_task/start` + `BackgroundTaskManager.start_background_task`。欠费闸门只有在“本次请求强制执行 **且** 用户确有 `bypass_overdue` 权限”时才放行；`waive_charge` 只有在管理员/超级管理员时才生效。多账号“全部开始”在强制放行时不得再把欠费账号从启动列表里剔除（跳过逻辑只服务于 `skip_overdue`）。
- 强制执行照常结算：`_deduct_available_runs_or_increment_overdue()` 优先级不变（先扣系统账号 `available_runs`，不足则给学校账号 `overdue_count + 1` 并生成账单），次数不足同样生成账单；只有 `Api.waive_charge_active` 为 True（管理员选择“此次不计费”）时跳过扣减与账单生成。该标志是一次执行期的会话状态：各启动入口每次都会按本次参数重设，`stop_run`/`multi_stop_all_accounts`/会话销毁会清零。
- 前端（legacy `legacy-payment-user.js` + `main.js` + `legacy-multi-accounts.js`、Vue `usePayment.js` + `MultiAccountView.vue` + `ControlTabs.vue` + `MobileControlPanel.vue`）必须把用户在弹窗里的决策通过 `_consumeOverdueForceOverride()` / `consumeOverdueForceOverride()` 传给上述启动入口；不得只在本地改状态而不带参数，否则后端闸门会继续拦截。相关回归测试见 `tests/test_bypass_overdue_permission.py`。

## 验证清单

- 本次验证码刷新按钮需求先落在旧版 UI：桌面/移动端登录、注册和短信验证弹窗的外层刷新按钮仅服务于本地验证码，必须在 `setCaptchaDisplayBehaviorMode()` 中统一隐藏，切回本地时恢复；后台刷新配置和历史记录不受影响。后续修改同一验证码功能时，应继续核对两套 UI 的行为一致性，并一并修复发现的 Vue 问题。回归测试：`node --test tests/legacy_captcha_refresh_visibility.test.mjs`。

- 修改 `scripts/main.js` 后至少运行 `node --check scripts/main.js`。
- 地图供应商前端改动运行 `node --test tests/map_provider_frontend_runtime.test.mjs`。
- 后端路线规划或供应商配置改动运行：
  - `python -m pytest tests/test_map_provider_business_execution_contract.py`
  - `python -m pytest tests/test_map_provider_backend_contract.py`
  - `python -m pytest tests/test_map_provider_runtime_guards.py`
- 登录、会话恢复或 `get_initial_data` 改动运行：
  - `python -m py_compile main.py`
  - `python -m pytest tests/test_auth_session_lifecycle.py tests/test_auth_login_ui_regressions.py -q`
  - `node --test tests/initial_data_failure_notice.test.mjs`
- 管理员查看态（上帝模式）/会话保活改动运行：
  - `python -m pytest tests/test_admin_view_session_keepalive.py tests/test_session_runtime_cleanup.py tests/test_auth_session_lifecycle.py tests/test_auth_login_ui_regressions.py -q`
  - `node --test tests/initial_data_failure_notice.test.mjs tests/ui_mobile_session_regressions.test.mjs`
- 提交前运行 `git diff --check`。Windows 下 LF/CRLF 提示不是失败，但真正的 whitespace error 不能忽略。
- 提交前确认 `git diff --stat` 和 `git status --short`，只提交当前任务相关文件。
- 前端运行时测试抽取真实函数时，同步装配新增的辅助函数、缓存状态与 Pinia store；登录清理测试应执行完整处理器并断言会话身份、存储和遮罩结果，不能截到函数内首次同名赋值就结束。变更内部折线容器表示时，保留颜色、完整路径等行为断言。回归见 `tests/admin_return_origin_state.test.mjs`、`tests/vue_login_multi_runtime.test.mjs`、`tests/map_provider_frontend_runtime.test.mjs`。
- Python 调用输出中文的 Node 脚本时，`subprocess.run` 必须显式使用 UTF-8，并断言完成标记，避免 Windows 默认 GBK 解码在线程内失败却仍按子进程退出码判定通过。跨平台硬链接测试只替换待测模块自己的 `os` 命名空间，不修改全局 `os.name`，以免影响 `pathlib`；使用真实临时文件验证成功、重名、发布失败及删源回滚。回归见 `tests/test_map_route_progress_segments.py`、`tests/test_log_archiving.py`。

## 会话资源和全局缓存生命周期

- 每个 `Api` 会话实例必须拥有独立的会话停止事件；`AccountRefresh-*` 和多账号监控线程启动时必须捕获该事件对象，不能在 worker 内创建无法从外部触发的局部停止事件。
- `cleanup_inactive_session()`、24 小时清理、用户主动登出、用户删除会话、管理员强制销毁、账号注销六条路径必须统一调用会话销毁逻辑；禁止只执行 `del web_sessions[session_id]`。
- 会话销毁顺序固定为：设置停止事件，停止账号和多账号任务，等待刷新线程退出，关闭 `api_client.session`，关闭该 session 的 Playwright context，释放地图运行时密钥，最后删除活动时间和会话文件锁。
- 会话不活跃监控对多账号会话的“任务执行中”判定必须看账号 worker 线程是否存活（`AccountSession.worker_thread`），不能依赖 `multi_run_stop_flag`：即使该标志已按下一条契约复位，监控也只认“真实还在跑的账号 worker”，避免标志维护失误再次把空闲的多账号会话永久保活。`开始前等待`（启动延迟）和`任务间等待`都发生在 worker 线程内部，worker 存活即代表该账号的任务流程（含两种等待）仍在进行；也不能用 `has_pending_tasks` 判定：它只表示“还有可执行任务”，账号没在跑时同样可能为真。账号 worker 全部结束后会话必须回到普通空闲回收；会话级后台任务（`background_task_manager` 状态为 `running`）仍在执行、或任一账号启用了自动签到（常驻刷新线程）时仍须保活。相关回归测试见 `tests/test_multi_account_session_idle_cleanup.py`。
- `multi_run_stop_flag` 必须真实反映“是否还有多账号任务在跑”：启动账号 worker 时清空，最后一个账号 worker 退出后经 `_mark_multi_account_run_stopped_if_idle()` 恢复置位；启动尝试一个账号都没跑起来（`worker.start()` 失败、`multi_start_all_accounts` 无可启动账号）时同样要恢复置位，不能只在“全部停止”时置位，否则自然跑完的会话会被不活跃监控永久当成“多账号任务执行中”。相关回归测试见 `tests/test_multi_run_stop_flag_lifecycle.py`。
- Playwright 上下文必须按 `session_id` 主动关闭；不能只依赖 24 小时全局清理或 Playwright 工作线程最终退出。
- IP 和手机号缓存必须同时具备 TTL 与最大条目数；短信验证码必须定期删除过期项，并在新增和查询时执行边界清理。
- 验证会话清理不能只看 `web_sessions` 是否为空，还必须验证 `AccountRefresh-*`、`MultiAccountMonitor` 线程已经退出，且重复登录清理后 `Api` 对象可被垃圾回收。
- 内存诊断日志统一使用 `[内存诊断]` 前缀，至少记录 `web_sessions`、后台线程数、Playwright context 数、IP/手机号/短信缓存条目数和 Linux `max_rss_mb`；排查内存增长时优先比较 `cleanup_worker_interval` 与 `session_cleanup:*` 快照趋势。
- 日志轮转按“顺序编号、不搬动历史文件”执行：三个处理器分别使用 `zx-slm-tool` / `zx-slm-tool-WARNING` / `zx-slm-tool-ERROR` 前缀，兼容一位编号，已有历史文件不改名、不覆盖。`Logging.log_backup_count`（默认 10）仅限制近期编号原文数量；当前文件轮转、重新打开并成功写入本条记录后，超额历史必须经 `log_archiving.py` 完成持久化清单、临时 ZIP、成员/CRC/摘要校验、无覆盖发布后才能删除。归档失败保留原文，独立按 2/4/8/16/32/60 秒退避，后续成功写入即检查重试。不要把 FileHandler.emit 正常返回当作写入成功，它会内部吞掉写入异常，必须通过 handleError 记录失败。ZIP 已提交只重试删源；指纹改变时保留新内容并退出旧删除义务。容量清理保留最新 ZIP 和未清理完的批次，0 不限制。回归见 `tests/test_log_rotation_ordering.py`、`tests/test_log_rotation_resilience.py`、`tests/test_log_archiving.py`、`tests/test_log_archiving_integration.py`；流程见 `docs/log-archiving.md`。
- `_read_config_ini()` 返回 `JsonConfigAdapter`，判断配置节必须调用 `has_section()`；不能使用 `"Logging" in config`，适配器没有映射成员协议，否则初始化会吞掉 TypeError 并忽略所有自定义日志设置。日志配置测试必须通过真实 JSON 读取链路，不能用 ConfigParser 替身绕过兼容问题；调用 `setup_logging()` 的验证必须将工作目录、日志、归档和背景目录全部隔离到临时目录，并恢复日志处理器及全局状态，避免真实启动归档副作用。回归见 `tests/test_config_adapter.py`、`tests/test_log_archiving_integration.py`。
- 启动归档必须位于单实例锁之后、日志处理器/背景预热/Web 服务之前；启动日志和背景分别恢复、分别备份，失败不能互相阻塞。背景完整校验后才切换目录并重置用户、游客、旧版会话绑定；暂存目录删不完留待下次启动。运行归档只能选择已关闭的编号日志，不能处理三个当前文件、背景或启动批次。重复 setup_logging 不再重置背景。背景缓存删除只处理缓存图片，先严格读取新旧绑定并保护引用；读取失败跳过删除，不能降级为空绑定。选图、绑定、索引和删除必须使用共享 BACKGROUND_FILES_LOCK 覆盖完整事务，网络锁外、图片临时写入后原子发布，锁内诊断通过 background_files_log 延迟到锁外。预热无图时不持久化全空绑定，后续登录/游客/UUID 可重新初始化，非空绑定继续复用。回归见 `tests/test_background_cache_safety.py`、`tests/test_background_empty_bindings.py`。
- `TokenManager` 是“每用户一个 token”，`verify_token()` 不校验 session_id：清理单个会话时不能只按 `browsing_activity` 判断用户是否还在使用。管理员查看态（上帝模式）和 `/auth/switch_session` 之后，管理员的实际活动会话在 `web_sessions` 里可能登记为别人的会话，`get_user_sessions(管理员)` 里也没有它，直接 `invalidate_token` 会删掉仍在使用的 token 文件，让管理员整个浏览态 401 掉线。失效判定依次为：该用户其他会话有新鲜浏览记录 → 命中管理员查看态保活窗口 → `TokenManager.get_token_last_activity()` 显示 token 最近仍在刷新；三者都不成立才允许删除 token。显式登出、强制登出、账号注销仍各自主动调用 `invalidate_token`，不受该判定影响。
- “必须立刻让旧凭证失效”的路径统一走 `web_server.py` 的 `_purge_user_credentials()`：删除用户、强制重置密码、用户修改自己的密码、强制登出用户。顺序固定为：吊销 token（每用户一个，反查索引同步清理）→ 汇总该用户全部会话（内存 + 用户文件登记 + 调用方补充）→ 逐个 `cleanup_session()` → 按需清空用户文件 `session_ids`；禁止只删 `web_sessions` 或只删会话文件。删除用户前必须先用 `get_user_sessions()` 取出登记的会话 ID，否则只存在于磁盘的会话文件会在下次启动时被重新加载。用户修改自己的密码时用 `keep_session_id` 保留当前会话并 `create_token()` 补发 token 写回 cookie，其他会话/设备全部失效。
- 销毁单个会话（`/auth/admin/destroy_session`、用户删除自己的会话、不活跃回收）不要无条件吊销 token：`cleanup_inactive_session()` 只在“这确实是该用户最后一个会话”时才 `invalidate_token()`，判定用 `_collect_other_user_sessions()`（内存活跃会话 + 确实存在状态文件的持久化会话，历史残留 ID 不算）；例外是 `_is_user_token_in_active_use()` 为真（查看态/切换态下活动会话登记在别人名下）时仍然保留 token，否则管理员查看态会被连带踢下线。`get_user_sessions()` 里残留的旧 ID 不能当作“还有其他会话”，否则 token 永远不失效。
- “退出应用/登出”（`/api/shutdown`、`/auth/logout`）必须先经 `_resolve_logout_target_sessions()` 解析销毁目标：查看态下 X-Session-ID 指向的是**被查看的会话**，必须用 cookie token 反查调用者，只销毁调用者自己的来源会话（请求头来源会话优先，其次 `session_id` Cookie，再退化为该调用者的其他活跃会话），绝不能销毁被查看用户的会话；token 是否吊销同样交给 `cleanup_inactive_session()` 的“最后一个会话”判定。
- 查看态但没有来源会话头的请求（god_mode 兜底）必须在 `g` 上打标记（`admin_view_without_origin` + `viewed_session_id`）：手工校验 token 的命名路由（例如 `/auth/admin/all_sessions`）要识别这种状态，否则会拿被查看会话的 owner 去校验查看者的 token，返回 401 并清空 `auth_token` Cookie，把管理员直接踢成未登录。

## 访客Token与身份级背景绑定

- 注册用户的背景绑定按认证账号身份保存，位置为 `random_background_image/background_state.json` 的 `identity_bindings[user:<username>]`；该账号下所有 UUID 共享同一 PC/MB Bundle。
- `/` 只要 `auth_token` 身份有效且账号已有背景绑定，即使当前没有活动 UUID，也必须返回该身份绑定背景。
- 快捷登录接口只读取会话列表和原有背景绑定，不得创建、替换或消耗 Bundle；缺少绑定时由后续 UUID 初始化按既有规则处理。
- 访客 Token 位于 `tokens/guests/`，每个访客 UUID 对应独立 `auth_token`。访客 Session 活跃时 Token 不得先失效，Token 到期时间必须使用 `max(now + guest_token_ttl_seconds, session_expires_at + guest_token_grace_seconds)`。
- 访客容量按活跃 Session 统计，创建 Session、Token 和背景绑定前必须原子检查 `max_active_guest_sessions`；容量满时返回 `429 guest_limit_reached`，不得产生任何副作用。
- 访客点击“退出应用”只能销毁当前访客 Session、Token 和 `guest_bindings`，不能执行注册用户的全局会话清理。
- 注册用户退出应用、普通登出与会话切换路径必须保持原有语义，不能因为访客逻辑改变注册用户会话生命周期。

## 大文件拆分约定

- `main.py` 必须只保留应用入口、全局装配、路由注册和仍有跨模块状态的兼容函数。
- 已拆分模块包括 `guest_token_store.py`、`theme_background_state.py`、`theme_background_legacy.py`、`payment_crypto.py`、`config_adapter.py`、`auto_attendance_config.py`、`runtime_maintenance.py`、`trusted_ip.py`、`ip_verifier.py`、`frontend_js_hardening.py`、`map_key_runtime.py`、`session_state.py`、`captcha_html.py`、`brute_force_manager.py`、`health_status.py`、`ssl_config.py`、`background_task_manager.py`、`runtime_models.py`、`api_client.py`、`auth_system.py`、`api_runtime.py`、`web_server.py`。
- `scripts/main.js` 必须保留顶层状态、核心 API 和初始化顺序；功能区块拆到 `scripts/legacy-*.js`，地图配置与 SDK 运行时位于 `scripts/legacy-map-runtime.js`，地图坐标转换与路线绘制位于 `scripts/legacy-map-render.js`，应用初始化、WebSocket 和地图交互增强位于 `scripts/legacy-app-runtime.js`，多账号状态与列表渲染位于 `scripts/legacy-multi-accounts.js`。
- 经典脚本必须在 `scripts/Check_for_updates.js` 中按依赖顺序插入，且所有文件都带同一 `version` 查询参数。
- 后续继续拆分时，移动函数后必须同步检查按源码读取 `scripts/main.js` 的测试，测试应组合入口和对应 legacy 模块，而不是放宽断言。
- 从 `main.py` 提取带副作用或可 mock 的函数时，模块内部必须通过 `_main()` 调用跨模块函数、`subprocess` 和运行时会话对象，保证现有 `mock.patch.object(main, ...)` 契约继续生效。
- 拆分类或连续代码块时要同时检查紧邻的非类函数是否被误移；启动路径引用的符号必须继续从 `main.py` 导出，并增加启动符号绑定测试。

## 后续更新方式

当以后又踩到坑时，在对应章节追加：

- 症状：用户看到或测试暴露的问题。
- 根因：最终确认的真实原因。
- 正确做法：以后应该怎么写、怎么验证。
- 相关测试：能防止回归的测试文件或命令。

### 支付回调与支付日志

- 症状：易支付异步通知 URL 未携带 `jump` 时被误判为同步返回，返回 HTML，平台无法收到 `success`。
- 根因：空 `jump` 经 URL 归一化后变成 `/`，提前返回跳转页，跳过验签和通知处理。
- 正确做法：只有非空 `jump` 才进入同步跳转；异步通知继续验签和处理，成功时返回纯文本 `success`。支付日志的 action/status 中文只用于两套 UI 展示，筛选请求和完整 JSON 保留原始值。
- 相关测试：`tests/test_security_hardening_fixes.py`、`tests/test_mobile_admin_payment_logs_ui.py`、`tests/vue_admin_interactions.test.mjs`。

### 主题背景与登录同步

- 症状：认证 Cookie 失效但 UUID 仍有效时登录页背景为空，点击登录还会重复消耗随机背景。
- 根因：公开主题读取路径被重复方法定义覆盖，未应用 UUID 对应 Bundle；登录响应的 `theme_background` 未接管前端状态，后续同步再次进入背景消耗流程。
- 正确做法：公开 GET 只读取已有身份/访客绑定；登录和 2FA 响应统一返回并应用 Bundle，空背景不覆盖当前值，绑定完成后跳过重复消耗。
- 相关测试：`tests/test_identity_bundle_runtime.py`、`tests/theme_background_sync.test.mjs`。
