# app-service.js 接口契约分析（2026-11-23）

本分析对照用户提供的 `www/app-service.js` 与本轮修改前的 `api_client.py`，追踪请求配置、拦截器、业务方法及页面调用方。其目的在于确认本项目已使用接口的实际参数位置和传输方式，并为修复保留可复核证据。

- 源文件：`www/app-service.js`，1,749,666 字节，共 45,178 行。
- 源文件 SHA256：`66d73fe73ca9fe21149a5f2522e22696fa63a302f3defe657e3b3b8a2f94a02b`。
- Python 对照基线：提交 `35b98c7` 中的 `api_client.py`；下文列出的 Python 行号属于该基线。
- 文中的 JavaScript 行号只适用于上述摘要对应的产物；重新格式化或换版后应按方法和路径重新定位。

## 请求层与鉴权

该产物使用 luch-request 3.1.0（5530–5531 行）。请求适配器先将 `params` 序列化并附加到 URL，再把 `data`、`method`、`timeout` 等传给 `uni.request`（3466–3528 行）。这意味着 POST 方法并不意味着参数必须进入请求体。

| 项目 | 静态证据 | 契约及含义 |
| --- | --- | --- |
| 主服务地址 | 3725–3730、5534 行 | `https://zslf.zsc.edu.cn`，普通业务路径使用 `/app` 前缀。 |
| 跑步和签到服务地址 | 5558–5561 行 | 请求路径含 `/run/` 时切换为同域根地址，不加 `/app`，没有在此配置独立端口。 |
| 绝对 URL | 5561 行 | `http://` 或 `https://` 开头的 URL 不再拼接 baseURL，匹配不区分大小写。 |
| 请求方式默认值 | 5535–5536 行 | 共用实例默认 GET，超时 8000 ms；业务方法显式覆盖时以业务配置为准。 |
| 请求体类型 | 5537–5540 行 | 默认 `Content-Type: application/json;charset=UTF-8`。对象形式的 `data` 应保持 JSON 对象语义。 |
| Accept | 5578 行 | 虽然初始配置是 `text/json`，请求拦截器最终覆盖为 `*/*`。 |
| platform | 5418–5419、5579 行 | 来自 `uni.getSystemInfoSync().osName`。 |
| appVersion | 5418–5419、5580 行 | 来自 `uni.getSystemInfoSync().appVersion`，是请求头字段。 |
| Authorization | 5575–5577、5687 行 | 从存储的 `token` 取值后原样写入，无 `Bearer ` 前缀。 |
| TLS 配置 | 5541 行 | 此 App 配置 `sslVerify: false`；这只是源行为记录，不构成本项目关闭证书验证的理由。 |

登录调用的表单只有 `username` 与 `password`（6077–6087 行），业务方法通过 POST 的 `params` 传入（5689–5699 行）。响应拦截器从 `data.accessToken` 与 `data.refreshToken` 保存令牌（5593–5600 行）；用户存储将其分别写入 `token`、`refresh-token`（5196–5205 行）。后续主 API 请求使用 accessToken，不把 refreshToken 作为 Authorization。

在本分析追踪的主服务请求链 `_i → Ci.middleware → 请求拦截器 → uni.request` 中，没有额外的签名、密码加密或请求体加密处理。登录参数和业务参数在 HTTPS 之内按 query/JSON 发送。产物还包含 uniCloud、广告等第三方 SDK；其他 SDK 中的签名与 token 代码不属于上述主 API 契约，不能据此为主 API 添加签名步骤，也不能据此断言整个产物都没有加密功能。

## 已覆盖的接口

下表路径是最终 HTTP 路径。`query` 对应源代码的 `params`，`JSON body` 对应源代码的 `data`。8 秒表示继承共用请求实例的超时；版本查询直接使用 `uni.request`，没有在该调用内设置超时。

| 方法 | 最终路径 | 参数位置和字段 | 超时 | JavaScript 行号 |
| --- | --- | --- | --- | --- |
| POST | `/app/login` | query：`username`、`password` | 8 秒 | 5689–5699、6077–6087 |
| GET | `/app/checkVersion` | 无 query/body 字段 | 未显式指定 | 7835–7879 |
| POST | `/run/errand/getErrandList` | query：`userId`、`offset`、`limit`、`isFinish` | 8 秒 | 25271–25277、25483–25488 |
| POST | `/run/errand/getErrandDetail` | query：`errandId`、`userId`、`errandScheduleId` | 8 秒 | 25278–25284、28791–28795 |
| POST | `/run/errand/addErrandTrackByData` | JSON body：轨迹 form | 30 秒 | 25285–25292 |
| POST | `/run/errand/syncSportData` | JSON body：同一轨迹 form | 30 秒 | 25293–25300、26800–26802 |
| POST | `/run/errand/reportLocation` | JSON body：同一轨迹 form | 30 秒 | 25301–25308、26800–26802 |
| POST | `/run/errand/quickSave` | JSON body：简化的轨迹记录 | 15 秒 | 25309–25316、27617–27630 |
| POST | `/run/errand/punch` | query：`longitude1`、`latitude1`、`longitude2`、`latitude2` | 8 秒 | 25317–25323、27821–27826 |
| POST | `/run/errand/getUserErrandTrackRecord` | query：`errandScheduleId`、`userId`、`offset`、`limit` | 8 秒 | 25324–25330、28921–28926 |
| POST | `/run/errand/getTrackRecordByTrid` | query：`trid` | 8 秒 | 25331–25337 |
| POST | `/run/errand/getTrackByTrid` | query：`trid` | 8 秒 | 25338–25344 |
| POST | `/app/appNotice/unreadNumber` | 无业务参数 | 8 秒 | 8490–8496、8511–8516 |
| POST | `/app/appNotice/noticeListByType` | query：`offset`、`limit`、`typeId` | 8 秒 | 8497–8503、38289 |
| POST | `/app/announcement/announcementList` | query：`offset`、`limit` | 8 秒 | 8504–8510、38291 |
| POST | `/app/appNotice/updateNoticeMutuaById` | query：`noticeId` | 8 秒 | 8517–8523 |
| POST | `/app/appNotice/updateNoticeIsRead` | query：`noticeId` | 8 秒 | 8524–8530 |
| POST | `/run/attendanceRecord/getAttendanceByRollCallId` | query：`id`、`userId` | 8 秒 | 43161–43167、43241 |
| POST | `/run/attendanceRecord/addAttendance` | query：签到 form，字段见下文 | 8 秒 | 43168–43174、43274–43289 |
| POST | `/app/appFind/getDictTips` | query：`code`、`num`；签到半径取 `attendanceRadius`、`1` | 8 秒 | 10266–10271、43228 |
| POST | `/app/mobileLogReport/addLog` | JSON body：失败诊断记录 | 8 秒 | 27302–27321 |

此表包括已有 Python 方法和为理解相邻流程而追踪的接口；某接口没有 Python 包装方法，本身不等于现有功能有缺陷，也不要求自动新增该功能。表中 query/JSON 结论仅适用于已追踪接口。不能推广成“整个 bundle 除四个轨迹接口外都使用 query”：例如失败诊断接口同样使用 `data`（27317–27319 行）。

query 序列化还具有以下规则：忽略 null/undefined，数组键加 `[]` 后逐项序列化，对象元素 JSON.stringify，日期转 ISO 字符串（3423–3448 行）。当前 Python 包装方法主要使用标量字段；未来接入数组或对象参数时应单独验证，不能仅把 Python 容器交给默认 urlencode。

## 跑步提交的数据形状

轨迹 form 的初始字段包括 `scheduleId`、`userId`、`userName`、`runLength`、`runTime`、`startPoint`、`endPoint`、`imgUrl`、`startTime`、`endTime`、`trid`、`sid`、`tid`、`speed`、`finishType`、`coordinate`、`batchId`（26724–26742 行）。

页面在提交前把轨迹点数组 `JSON.stringify` 到 `coordinate` 字段，再将完整 form 作为外层 JSON 对象提交（27337–27346、27455–27477 行）。因此 coordinate 是 JSON 字符串字段，外层 body 仍是 JSON 对象。已编码的外层 JSON 字符串可以直接作为请求体，但不能再对该字符串整体 JSON 编码一次，也不能把对象转成表单。

新页面维护主接口、syncSportData、reportLocation 三种提交入口（26800–26802 行）。轻量保存的字段为 `trid`、`batchId`、`scheduleId`、`userId`、`userName`、`imgUrl`、`runLength`、`runTime`、`finishType`、`startTime`、`endTime`（27617–27630 行）。这些证据说明传输方式和字段来源，不证明这些接口线上必定互为等价备份，也不证明可任意补造或省略业务字段。

## 签到字段与坐标顺序

签到 form 包含 `id`、`userId`、`name`、`rollCallId`、`coordinate`、`distance`、`status`、`reason`、`signCode`（43194–43204、43445–43454 行）。定位签到的提交过程如下：

1. 用页面携带的活动标识与用户标识调用 `getAttendanceByRollCallId`（43241 行）。
2. 将返回的 `rollCallInfo.id` 赋给提交 form.id（43253 行）。
3. 将页面携带的活动标识赋给 form.rollCallId（43288 行）。
4. name/userId 来自用户资料，signCode 来自设备 deviceId（43281–43283 行）。
5. coordinate 按 `latitude + ',' + longitude` 构造，即“纬度,经度”（43284–43287 行）。

二维码签到也将 `rollCallInfo.id` 与原始活动参数分别赋给 id 和 rollCallId（43694–43699、43715–43722 行）。静态产物不能证明这两个 ID 永远相等；客户端不应把缺失的 id 自动解释成 rollCallId。

这与轨迹点中的独立经纬度字段、地图模块使用的坐标数组是不同的接口边界。不能对所有名为 coordinate 的字段一概交换顺序。

## 版本来源与响应语义

App 的 appVersion 请求头来自设备运行时版本（5418–5419、5580 行）。`checkVersion` 是单独的 GET 调用，用服务端返回的 version 与运行时属性 version 比较，并结合平台决定是否展示更新（7835–7879 行）；它没有把返回值赋给共用请求层的 `ki.appVersion`。

本项目同步服务端最新版本、只升不降并复用缓存，是为了兼容服务端版本检查的项目策略。不能由该静态产物证明“服务端最低允许版本永远等于商店最新版”，也不能从文件中证明任意具体版本号在当前线上一定成功。本轮未重新验证旧注释中关于 1.0.84/1.0.85 的线上实测描述。

共用响应拦截器把 HTTP 2xx 的响应体交给业务方，并检查业务 code 是否为 200（5590–5619 行）。HTTP 非 2xx 会进入错误路径，包装成包含 code/success/message/errMsg/statusCode 的对象（5622–5683 行）。因此 HTTP 成功和业务成功必须分开判断。Python 保留非重试 4xx 的 JSON 错误正文，是本项目诊断策略，与 App 的错误包装方式不同，但不应将 401 的业务信息丢成无响应或反复重试。

## 本轮修改前已正确的部分

基线 `api_client.py` 已正确实现普通接口的 `/app` 前缀与 `/run/*` 根路径（90–96 行），登录 POST/query（463–480 行），accessToken 原样 Authorization（149–158、485–502 行），历史轨迹使用 POST/query（566–577 行），通知、签到与字典配置的 POST/query（609–645、708–759 行），以及预编码轨迹 JSON 字符串直接发送（579–591 行）。这些行为无需因本轮比对改回旧路径、表单登录或 GET 历史轨迹。

Cookie 中 shiroCookie 的兜底、网络重试、取消机制和版本同步均属于本项目扩展策略，不能冒充产物中的原始行为。Cookie 兜底也不能掩盖 accessToken 生命周期错误。

## 本轮发现的修复依据

以下记录针对修改前基线，供本轮修复与回归验收使用；不表示完成文档写入就已经完成代码修复。

| 差异 | 修改前 Python 位置 | 修复及验收方向 |
| --- | --- | --- |
| 版本查询误用 POST | `sync_app_version` 193–199 行 | 改为 GET，验证最终 URL 和无请求体。 |
| 上传未使用 30 秒超时 | `submit_run_track` 585–591、`_request` 317 行 | 为轨迹提交保留独立读取超时，避免 10 秒即超时并重传；不要仅扩大所有请求的全局超时。 |
| 对象 data 被表单编码 | `_request` 289–303 行 | JSON 类型对应 JSON 序列化，保留预编码 JSON 字符串语义；显式表单仍按表单处理，不能覆写调用方指定的内容类型。 |
| Accept 与最终拦截器值不同 | `_get_headers` 142 行 | 与最终 `*/*` 对齐；不能把初始 `text/json` 当作最终头。 |
| 相等版本缓存不命中 | `sync_app_version` 178–186 行 | 有效缓存版本等于当前版本时也应复用，验证多实例不会重复检查。 |
| 异常版本响应阻断登录 | `sync_app_version` 202–215、login 470 行 | data 非对象、无有效版本等情况保留当前版本，不抛出异常中断登录；失败不能永久标记同步成功。 |
| 签到 id 被凭空补齐 | `submit_attendance` 727–732 行 | 使用调用方经查询取得的正确 id；不要假设 id 与 rollCallId 相等。 |
| 签到调用方缺 name 且坐标颠倒 | `api_runtime.py` 11484–11503 行 | 在构建 payload 的边界按 App 来源补 name、id，并明确纬度,经度；不在通用网络层猜测和交换字符串。 |
| 重登只清 Cookie | `api_runtime.py` 8057–8062 行 | Cookie 清理与 accessToken/refreshToken 清理须保持同一会话生命周期，避免复用旧认证头。 |

## 本轮验证边界

本分析使用本地产物静态阅读、关键字定位和调用链追踪，已核对主请求层以及本表列出的业务方法与参数构造位置。SHA256 用于固定证据版本。没有在本轮运行原始移动 App、使用真实账号登录、发起线上签到/跑步提交或重放第三方 SDK 请求。

后续受控单元测试可以验证客户端最终构造的 URL、query、body、headers、timeout、缓存和取消行为；这类测试不能代替服务器实际接受请求的证明，也不能证明签到/成绩判定等业务已在线上成功。未追踪的整个 bundle 其余业务接口不在此分析覆盖范围内。

## 修复与回归结果

本轮已落实上述客户端及直接调用点修正：版本查询改为 GET，版本缓存相等命中、异常响应可重试同步；JSON 对象与预编码字符串正确发送，轨迹提交单独使用 30 秒读取超时；对齐 Accept，恢复响应头和原始响应诊断日志；签到使用响应中的记录 ID、用户姓名和纬度在前的坐标；登录、注销和多账号重登清除旧认证状态。

新增契约测试通过真实 requests 序列化构造 PreparedRequest，仅在传输适配器处截获请求，不连接线上服务器。新增用例先复现失败，再验证修复；网络日志测试改为正常执行客户端构造器，避免跳过认证和版本状态初始化。

- 相关调用链回归：118 项通过。
- 全量 Python 回归：`python -m pytest -q --tb=short`，1935 项通过、3 项跳过；存在原有 Eventlet 弃用警告。
- 独立代码审查未发现阻断项，Python 编译检查与 Git 差异格式检查通过。
- 上述结果只证明本地契约和回归行为，未执行真实账号登录、签到或跑步成绩验收。
