# Agent 接手说明

本文件用于记录本仓库已经踩过的坑、稳定约定和后续 Agent 必须继续补充的经验。每次完成一个值得复用的修复、排查出真实根因、或用户明确指出同类问题重复出现时，都要更新本文件。

## 基本工作规则

- 开始改动前先看 `git status --short`，确认是否有用户或上一轮 Agent 留下的改动；不要回滚无关改动。
- 一件事完成并验证后就立即 commit，不要把多个已完成任务堆在一起。
- 中文任务使用中文提交信息，提交信息直接说明修复内容。
- 前端可见行为变化必须更新 `version.json`，`version` 使用日期加随机字母数字后缀，例如 `20260728-P4xL8v`；不要用纯时间戳后缀或特殊字符。
- 修改 `version.json` 时同步更新 `build_time` 为当前实际时间。
- 有值得学习的地方就写入本文件，不要只把经验留在对话里。

## 安全要素

- 不要把用户在对话、日志、截图或本机配置里提供的真实 Key、Token、Cookie、密码、验证码服务器 Key、地图 Key 写入代码、测试、文档、提交信息或 PR 描述；需要示例时使用占位值。
- `configs/`、`.env`、本地运行配置、用户导出的配置、日志和临时调试文件默认按敏感文件处理。提交前必须确认没有把这些文件加入暂存区；除非用户明确要求并确认已脱敏，否则不要提交。
- 不要在生产代码、测试、注释或文档中写入本机绝对路径、用户名、私有目录结构，尤其不要留下“参考某个本地路径里的接口文档”这类注释。需要说明契约时写成通用 API 契约，不暴露本机路径。
- 验证码服务器、地图供应商等第三方服务的服务地址和 Key 只应由后端配置或后端代理使用；浏览器端应访问同源代理接口，不要把后端专用 Key 直接暴露给前端。
- 与验证码服务器兼容时，二验结果应由后端作为最终判定；前端只能提交一次验证结果标识，不能绕过后端二次校验。
- 涉及客户端 IP、代理来源或限流键时，带 Key 的请求不能回退使用连接来源地址；只有明确传入且校验为公网地址的 `clientIp` 才能作为 authenticated 限流键。
- 提交前至少检查暂存内容和敏感字符串：`git status --short`、`git diff --cached --stat`、`git diff --cached --name-only`，并对本次改动文件搜索本机路径、真实 Key 片段、`configs/` 和调试日志痕迹。
- 如果发现敏感信息已经进入 Git 历史，不要只改最新文件；需要先告知用户，清理历史、强制推送前确认范围，并提醒相关 Key 需要轮换。
- 不要保留不必要的 AI 贡献者、协作者署名或生成痕迹；提交作者、commit trailer、文档署名应保持项目原有风格。

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
- Vue 新版 UI 和根目录 `index.html` 使用的老版 UI 都必须完成运行时脚本加载和地图密钥解密。修改新版组件时要同步检查 `scripts/main.new.js` 的老版入口、初始数据、地图配置保存和登录响应链路。
- 日志、支付操作日志、前端 `appConfigLoaded` 事件和错误信息不得输出原始地图 Key、Token、密码、验证码、签名或完整配置；密码恢复等流程只能记录数量和状态，通用参数日志统一使用递归脱敏函数。
- 支付订单查询、订单列表和后台订单详情必须通过字段白名单返回；待支付链接只在已鉴权的待支付订单查询中返回，平台原始响应、通知参数、支付参数、主动查询令牌哈希和退款原文不能返回。支付日志读取接口也要在返回前递归脱敏，兼容旧日志文件。

## 地图供应商相关入口

- 非高德地图的真实前端渲染主要在 `scripts/main.new.js` 的 `initProviderMap()`、`ensureSingleMap()`、`initMap(AMap)` 相关链路，不要只看 `index.html` 的静态容器。
- 地图供应商前端运行时的重点测试是 `tests/map_provider_frontend_runtime.test.mjs`。
- 后端供应商路线规划合同主要看 `tests/test_map_provider_business_execution_contract.py`、`tests/test_map_provider_backend_contract.py`、`tests/test_map_provider_runtime_guards.py`。
- 地图控件、SDK 加载、右键拖动、3D 视角这类问题，自动化测试通过后，尽量再直接加载真实地图验证；用户截图反复指出的问题不能只靠静态代码判断。

## 腾讯地图控件踩坑

- 腾讯左上角视角控件优先使用 SDK 原生 `ROTATION` 控件，初始化时 `showControl` 需要保持为 `true`；右上角缩放仍用应用自绘控件，因此只移除 `TMap.constants.DEFAULT_CONTROL_ID.SCALE` 和 `ZOOM`，不要移除 `ROTATION`。
- 腾讯原生视角控件位置通过 `getControl(DEFAULT_CONTROL_ID.ROTATION).setPosition(TMap.constants.CONTROL_POSITION.TOP_LEFT)` 修正；不要再默认渲染 `provider-3d-view-btn` 自绘左上角控件。
- 应用自绘控件必须挂在外层地图容器上，不能挂在 SDK surface 里，否则会被 SDK 自己的 DOM 层级影响。
- 腾讯自定义 SVG 标记使用 `TMap.MultiMarker` / `MarkerStyle` 时，不要给 `PointGeometry.content` 填文字；否则 SDK 会额外渲染一份原生文字，造成双重标签。需要文字时应放进自定义 SVG 或应用自己的 marker 样式里。
- 活动任务路线渲染要传 `showEndpoints:false`，不要让 SDK 或通用渲染层额外加“起点/终点”标记；第一眼可见的标记应该是实际检查点名称。
- 右上角缩放等级不能写死为 `17`。腾讯地图要用 `getZoom()` 读取真实缩放，并监听官方 `zoom` 事件刷新标签。
- 腾讯缩放按钮优先走 `getZoom()` + `setZoom()`，这样按钮点击后能立即同步显示数值；不要只调用 `zoomBy()` 后等待未知的 SDK 状态。
- 自绘左上角 3D/视角控件代码可以保留，但只作历史兜底代码，不要接入腾讯或百度默认初始化路径；如果真实 SDK 原生控件可用，必须优先使用原生控件。

## 百度和天地图控件踩坑

- 百度地图必须使用 BMapGL/WebGL 版本，加载 URL 要带 WebGL 类型，初始化时保留 3D 能力。
- 百度左上角视角控件优先使用 BMapGL 原生 `NavigationControl3D`，不要默认叠加 `provider-3d-view-btn` 自绘控件；初始化时如果发现旧自绘 overlay，要清理掉。
- 百度地图的视觉缩放比例和其他供应商不完全一致，默认/复位缩放用 `18.0`；天地图默认/复位缩放用 `17`。不要把所有非高德供应商统一写成同一个整数缩放。
- 百度原生 `NavigationControl3D` 如果用 `BMAP_ANCHOR_TOP_LEFT` 还离左上角太远，检查 `BMapGL.Size` offset；当前应贴近左上角，使用 `new BMapGL.Size(12, 12)`。
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

## 路线规划限流和重试规则

- 地图供应商路线规划存在按秒计算的并发/频率限制时，不要把分段请求一次性并发打满；应采用队列式分段发起：第 1 个请求发起后间隔约 `0.1s` 发第 2 个，再间隔约 `0.1s` 发第 3 个，以此类推。
- 如果一轮分段请求没有任何成功，说明可能是整轮请求被限制或执行器初始化失败；这种情况下最多重试 2 轮，仍无成功就终止，避免无限等待。
- 如果一轮中已有分段成功，但后续分段失败，优先按秒级 API 限流处理：等待约 `0.5s` 后只重试未成功的分段，不要重做已成功分段。
- 连续 2 轮补发都没有任何新的分段成功时终止；只要某轮补发有新成功，就清零连续失败计数并继续补剩余失败分段。
- 这套调度语义应保持供应商无关，高德、腾讯、百度、天地图后端规划执行器都要一致；不要因为腾讯路径需要端点补全而改动真实执行坐标。

## 登录和会话提示规则

- 遇到 `POST /api/get_initial_data 401`、`会话已失效`、刷新后登录页仍弹旧提示、或需要连续登录多次才正常的问题时，先从日志和通用 `/api/<path:method>` 包装层追踪，不要只看 UI 表象。
- `get_initial_data` 属于认证可选初始化链路，后端要允许不可恢复 session 降级到只读初始化上下文；这个临时上下文不能污染后续 session 活动。
- 前端相关链路重点看 `getApiRequestSessionHeaderValue()`、`callPythonAPI()`、`handleAuthLogin()`、`loadInitialData()` 和 `showAuthLogin()`。
- 切回登录页或认证登录页时应清理旧的 `logout-elsewhere-overlay`；当登录页已可见、登录中、或当前没有可用 session 时，应抑制过期会话和多设备登录旧响应，避免未登录状态继续显示倒计时提示。
- 管理员从老版 UI 查看不属于自己的会话时，只能进入“查看态”：前端记录来源会话并随 API 请求发送 `X-Admin-Origin-Session-ID`，后端用来源会话验证管理员身份和权限，但业务 API 仍操作目标会话；切到管理员自己的会话才允许走普通 `/auth/switch_session`。
- 老版 UI 用模板字符串生成内联 `onclick` 时，不能把 `JSON.stringify()` 的双引号参数直接塞进双引号属性；应对参数字符串做属性转义，并用单引号包裹 `onclick` 属性，否则浏览器会把事件属性截断，表现为按钮没有事件触发器。

## 验证清单

- 修改 `scripts/main.new.js` 后至少运行 `node --check scripts/main.new.js`。
- 地图供应商前端改动运行 `node --test tests/map_provider_frontend_runtime.test.mjs`。
- 后端路线规划或供应商配置改动运行：
  - `python -m pytest tests/test_map_provider_business_execution_contract.py`
  - `python -m pytest tests/test_map_provider_backend_contract.py`
  - `python -m pytest tests/test_map_provider_runtime_guards.py`
- 登录、会话恢复或 `get_initial_data` 改动运行：
  - `python -m py_compile main.py`
  - `python -m pytest tests/test_auth_session_lifecycle.py tests/test_auth_login_ui_regressions.py -q`
  - `node --test tests/initial_data_failure_notice.test.mjs`
- 提交前运行 `git diff --check`。Windows 下 LF/CRLF 提示不是失败，但真正的 whitespace error 不能忽略。
- 提交前确认 `git diff --stat` 和 `git status --short`，只提交当前任务相关文件。

## 会话资源和全局缓存生命周期

- 每个 `Api` 会话实例必须拥有独立的会话停止事件；`AccountRefresh-*` 和多账号监控线程启动时必须捕获该事件对象，不能在 worker 内创建无法从外部触发的局部停止事件。
- `cleanup_inactive_session()`、24 小时清理、用户主动登出、用户删除会话、管理员强制销毁、账号注销六条路径必须统一调用会话销毁逻辑；禁止只执行 `del web_sessions[session_id]`。
- 会话销毁顺序固定为：设置停止事件，停止账号和多账号任务，等待刷新线程退出，关闭 `api_client.session`，关闭该 session 的 Playwright context，释放地图运行时密钥，最后删除活动时间和会话文件锁。
- Playwright 上下文必须按 `session_id` 主动关闭；不能只依赖 24 小时全局清理或 Playwright 工作线程最终退出。
- IP 和手机号缓存必须同时具备 TTL 与最大条目数；短信验证码必须定期删除过期项，并在新增和查询时执行边界清理。
- 验证会话清理不能只看 `web_sessions` 是否为空，还必须验证 `AccountRefresh-*`、`MultiAccountMonitor` 线程已经退出，且重复登录清理后 `Api` 对象可被垃圾回收。
- 内存诊断日志统一使用 `[内存诊断]` 前缀，至少记录 `web_sessions`、后台线程数、Playwright context 数、IP/手机号/短信缓存条目数和 Linux `max_rss_mb`；排查内存增长时优先比较 `cleanup_worker_interval` 与 `session_cleanup:*` 快照趋势。

## 后续更新方式

当以后又踩到坑时，在对应章节追加：

- 症状：用户看到或测试暴露的问题。
- 根因：最终确认的真实原因。
- 正确做法：以后应该怎么写、怎么验证。
- 相关测试：能防止回归的测试文件或命令。
