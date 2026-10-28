# 离线账单与地图瓦片缓存验证

日期：2026-10-29。仅本地代码、隔离身份和真实地图供应商调用；未提交校园跑步、未部署线上、未更改历史账单。真实凭据只在测试进程内，未保存配置、原始响应或带参数 URL。

## 行为与边界

- 地图快照此前已纳入 API 白名单，继续由 `view_map` 权限控制；没有放开其他内部方法。
- 离线刷新恢复 `is_offline_mode`；离线执行不读取欠费账号或账单。显式空范围、`NULL`、空数组及无效账号返回空结果。管理员查看会话时认证使用来源，欠费和账单范围使用业务目标。读取账单不再补写历史文件；失败在线登录保持离线身份，成功验证后才切换。
- 两套系统配置提供瓦片缓存时间和总大小，默认 20 天、10 GB（十进制），仅开启后端代理时显示。关闭后保留设置；旧配置缺字段自动采用默认值，字段缺省保存不清空已有设置。
- 缓存位于现有 `cache/map_tiles/<provider>/<摘要前两位>/<摘要>.tile`，独立于 CDN。Key、样式、版本、语言、主机、来源及请求头差异均参与摘要，磁盘不保存原始 URL 或凭据；原子替换、重启索引、过期和容量清理不触碰其他缓存目录。
- 命中前先鉴权。同一瓦片并发只有 owner 访问上游，follower 不占上游准入许可；成功、异常和超时均释放等待。响应继续对浏览器 `no-store`，`X-Map-Cache` 为 `HIT/MISS/COALESCED/BYPASS`。
- 缓存服从更短上游有效期；`no-store/no-cache/private`、`Set-Cookie`、未知 Vary、错误内容、非完整响应及大于 4 MiB 的瓦片不落盘。不能为了命中删除上游 Cookie 策略，不能返回过期瓦片掩盖失败。
- 腾讯确认的 batch JSON 严格验证 `datas` 数量和每项非空 base64 `data`，拒绝错误、未知/重复字段及非 JSON 常量。其 JSONP 包装必须与安全 callback 精确匹配、不能夹带脚本；存储 callback 无关 JSON，各请求重新封装并保留 callback 存在性 guard。未知普通腾讯 JSON、百度 JSONP 不套用 batch 结构，继续透传。
- 当前百度 v4 默认 PVD 实测为二进制；按确认端点及特征校验，不能因上游 JavaScript MIME 改写字节。
- 连接复用、有限瓦片重试、总截止时间、有界 DNS 和取消器解绑减少重复连接及队列压力；它们不能保证第三方服务永不超时。

## 真实地图代理复测

使用生产代理及生产规划脚本、隔离认证，通过真实 SDK 验证底图与路线。未使用真实学校任务；以下是最小 SDK 显示和缓存复验，不代替完整校园业务跑步。

| 供应商/轮次 | 规划和显示 | 顺序重复样本 | 4 个并发相同请求 | 错误 |
| --- | --- | --- | --- | --- |
| 腾讯默认 GL | 成功，8 点 | 4 份 batch JSON 均 HIT，第二请求 0 上游 | 1 上游，3 COALESCED | 零代理失败、脚本异常、拒绝或直连 |
| 百度默认 v4 | 成功，14 点 | 4 份 PVD 均 HIT，第二请求 0 上游 | 1 上游，3 COALESCED | 零代理失败、脚本异常、拒绝或直连 |
| 高德无安全密钥 | 成功，10 点 | 4 份 PBF 均 MISS 到 HIT | 1 上游，3 COALESCED | 零最终失败；正常 SDK 302 按严格白名单转发 |
| 高德带安全密钥，第 1 轮 | 失败，SDK 未就绪 | 无样本 | 未执行 | loader 上游 ReadTimeout，代理 502；未回退直连 |
| 高德带安全密钥，第 2 轮 | 成功，10 点 | 4 份 PBF 均 MISS 到 HIT | 1 上游，3 COALESCED | 零最终失败，生产超时未放宽；不覆盖首轮失败 |
| 天地图 | 成功，2 点 | 4 份 WMTS PNG 均因 Set-Cookie 而 BYPASS | 1 上游，3 COALESCED | 零失败；顺序重复仍访问上游，未验证到磁盘 HIT |

腾讯真实结构为 `rt0..3.map.gtimg.com/tile`、`tiles` 批量参数及 `datas/data` 数组。百度真实默认结构为 `apimaponline0..3.bdimg.com/pvd/` 二进制，采样约 376 kB 至 1.34 MB。没有采集到普通 `x/y/z` 腾讯 JSON 或百度 JSONP，因此它们没有真实缓存通过结论。跨 callback JSONP 使用受控端点回归验证，不能写成供应商实测。

## 自动化与隔离浏览器

- `python -m pytest -q --tb=short`：1600 项通过，3 项可选真实 Nginx 部署测试因未配置二进制而跳过（未执行，不能计为通过）。`node --test tests/*.test.mjs`：465 项通过。Vue 生产构建通过，保留现有 Vite 配置、脚本和动态导入提示。缓存、代理和 JSONP 针对性回归覆盖重启命中、错误拒存、凭据/来源隔离、并发合并、过期、损坏、写盘失败、配额清理及鉴权撤销。
- `node tests/browser_map_cache_config_smoke.mjs`：Vue/旧版、桌面/移动共 4 个组合，默认值、开关联动、保存后恢复、离线执行前不查询欠费或账单均通过，零异常及外部请求。
- `node tests/browser_admin_return_smoke.mjs`：桌面和移动覆盖刷新、A 到 B 到 C 到 A、C 属于 A、快速导航、目标失败和来源失效；Cookie、目标任务均不变，零页面异常。
- Node 浏览器脚本需要已安装的 Playwright；可通过当前运行环境的 `NODE_PATH` 使用已有依赖，不向仓库安装临时包。测试关闭自有浏览器、监听与临时缓存，不删除用户现有缓存。

## 复现

```powershell
python -m pytest -q --tb=short
node --test tests/*.test.mjs
npm --prefix frontend run build
node tests/browser_map_cache_config_smoke.mjs
node tests/browser_admin_return_smoke.mjs
```

真实代理测试通过临时 `MAP_SMOKE_CREDENTIALS` 提供每家 `key/origin` 和可选高德 `securityJsCode`，设置 `MAP_SMOKE_TILE_CACHE=1` 后运行 `python tests/browser_map_proxy_smoke.py`。不在此存储真实值；测试结束清理环境变量，保留 Python 退出状态。天地图只在符合上游策略时才落盘，`policy_pass` 不等于磁盘 HIT。
