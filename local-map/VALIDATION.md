# 验证记录

验证环境：Windows x64，Python 3.12.16，Node.js 24.12.0，2026-10-29。
首轮验收在原 `chaoxing_plus` 的独立分支 `codex/campus-offline-map` 完成，
没有接入主程序或推送。以下保留原始验收记录；迁移后的复测单列在文末。

## 真实数据与开源引擎

- 当前发布：`20261029T094426Z-fd8979d8`。
- 真实 OSM 快照：`data/source/a0595348040142196da0.osm`，1,029,591 字节。
- 源文件 SHA256：`a0595348040142196da0abaa9b823d0b03f06d3c6cdce4eb739382529e5e25a3`。
- 来源为 Overpass XML 查询，原始文件、查询、时间、ODbL 信息保存在相邻 provenance JSON。
- 官方 Windows Valhalla 构建了 5 个 `.gph`；完整 TileServer GL 实际生成
  缩放 14 至 20 的 1416 张 256px PNG；官方 Font Maker 实际生成 61 个字形区段。
- 最终发布包含 1499 个被校验的文件，目录总计 22,058,867 字节。字形缓存后的
  最后一轮完整构建约 11 秒。构建已停止其自有 TileServer GL 进程。
- `main.py validate` 对源于 manifest 的 SHA256、路网及完整瓦片集合检查通过。

三组示例经实际统一 API 验证，距离分别约 928、1037、927 米；第三组有一个途经点，
返回两个独立分段。最大道路吸附偏移约 0.047 米。示例路线各几何点均位于瓦片范围内。

真实覆盖不足：主校区收录道路 12 条、建筑 33 栋，北校区道路 0 条、建筑 1 栋；
两个地块均没有收录入口标记和专门步道。没有推测或补画缺失道路，北校区内部规划
能力因此有限。以上是 OSM 数据统计，不是实地测绘或通行核验。

## 已执行检查

| 检查 | 结果 |
| --- | --- |
| `python -m pytest -q` | 54 通过，1 个 Starlette/httpx 测试客户端弃用提示 |
| `main.py validate` | 当前版本 1499 文件通过 |
| `setup.ps1 -SkipWebBuild` | Python 精确依赖同步和原生地图工具安装成功 |
| Postman 本机真实 GET `/healthz` | 200，离线状态和发布版本断言通过 |
| Postman 本机真实 POST `/api/v1/routes` | 200，GeoJSON、途经点两段及 50 米吸附断言通过 |
| 主仓库 82 个 Node 测试文件 | 745 通过、102 跳过、0 失败（847 项） |
| 主仓库 TypeScript `tsc --noEmit` | 退出码 0 |
| Web `npm test -- --run` | 57 个文件、815 项全部通过，0 跳过 |
| Web `npm run typecheck`、`npm run build` | 均退出码 0 |
| `scripts/verify_offline.py` | 真实 HTTP、24 并发及 8 项浏览器测试通过，端口释放 |
| 独立应用内浏览器复核 | 中文底图、三点两段路线、请求响应调试显示正常 |
| `git diff --check` | 通过；下载的固定资源保留原始字节 |

Python 测试使用真实 Valhalla 合成图验证步行最短路、台阶捷径、`foot=no`、断路、
同路段吸附、50 米距离限制、重复点、22 个不同位置、途经点顺序、线程锁与路径重定位。
另覆盖输入验证、错误响应、OpenAPI 契约、文件损坏、静态路径边界、发布失败保留旧版。

主仓库回归采用 PowerShell 实际展开 `scripts/*.test.mjs` 文件列表后运行
`node --test --test-concurrency=4 @testFiles`，没有依赖 Windows 的命令行通配符展开。
未修改主程序运行入口，因此未重建扩展的 `dist`。

## 离线与浏览器复测

```powershell
.venv\Scripts\python.exe scripts/verify_offline.py
```

该脚本使用新 Python 进程冷启动 API，Python audit hook 拒绝非 loopback 的
socket 解析和连接，并确认 Valhalla 没有远程瓦片 URL。测试读取本地页面、文档、
六个 GeoJSON 图层、全部七级缩放的抽样瓦片，调用三组真实路线及 24 次并发请求。
浏览器拦截所有外部 HTTP 请求，并断言没有尝试访问外部资源或已禁用的接口。
脚本结束会关闭自有浏览器、Python 服务及其 Windows 子进程，并确认端口释放。

这里没有更改系统防火墙，也没有拔网线。Python audit hook 不拦截 C++ 直接联网；
对应边界由 Valhalla 的空远程瓦片配置及只读本地数据保证。浏览器设备定位使用
成功、拒绝、超时模拟，未在真实校园设备上测试 GPS 精度或离线卫星定位。

JSON 结果与日志位于 `evidence/`；浏览器截图位于 `.runtime/screenshots/`。
实际覆盖桌面及 320、768、1024 像素布局、手机地图视图、地图点击与标记拖动、
列表顺序调整、手工坐标、导出 JSON/GeoJSON、错误恢复、请求响应调试与本地文档。
这里的手机检查为浏览器视口模拟，没有把它记为真实手机或实地 GPS 验收。

已排除测试采集干扰：按住鼠标时的 fullPage 截图会取消 dnd-kit 拖放，
软件 WebGL 在 fullPage 采集时也可能得到空白画布。最终截图在手势完成后采集
视口，等候地图 idle，并检查非白像素比例；独立应用内浏览器也确认地图正常。
`iab-desktop.png` 与 `iab-debug.png` 为独立浏览器截图。

## 依赖与遗留项

依赖锁定与源码提交见 `requirements.lock.txt`、两个 npm lockfile 和
`UPSTREAM_LOCK.json`。保留上游许可证及适配说明。

安装时 `npm audit` 对固定的 TileServer GL 5.7.0 构建依赖树报告 7 项：2 low、
4 high、1 critical，主要来自 sqlite3/node-gyp 的 tar 安装工具链。
`npm audit fix --dry-run` 没有给出可直接应用的变更。本次保留批准的版本组合；
此 Node 工具仅在构建期监听回环地址，日常服务仅使用 Python。该审计结果不代表
这些依赖已经修复，后续升级构建工具时需要重新验证原生渲染。

自动审批拒绝了两个字体构建临时目录的递归清理，返回原因仅为 `blocked by policy`。
这些目录保留在 Git 忽略的 `.runtime` 内。临时测试服务已清理，离线验收脚本
确认其端口释放；收尾确认默认端口 8765 没有监听，自有 Python/TileServer 进程无残留。

Vite 的大体积 chunk 提示及软件 WebGL ReadPixels 性能提示没有导致测试失败。
详细转向指令当前仍是原生 Valhalla 的英文文本，界面控制及 Web 错误提示已中文化，
调试面板保留原始 API 响应。已通过先失败再通过的回归测试修正地图 GPS 超时
被误判为权限拒绝的问题；判断依据为错误码与常量比较。

## 迁移后的环境自适应复测

当前目录为 `C:\Users\Zelly\Documents\GitHub\python_runing\local-map`。
原 `.venv/pyvenv.cfg` 仍引用旧项目的绝对 Python 路径，导致安装和启动前即失败。
本地 Python 3.12.16 本身正常，数据、路网和瓦片不需要重建。

安装及启动脚本现在按自身目录选择并探测 Python，检查虚拟环境的版本、
`prefix`、`base_prefix` 和目录标记。失效或复制过来的旧环境整体保留在
`.runtime/venv-backups`，之后重建并同步固定依赖；健康环境可以重复使用。
原失效环境已备份，重复安装后仍只有这一份恢复备份。

- 完整 `setup.ps1` 在当前目录成功同步 Python、Node 工具并构建 Web。
- 首次 Web `npm ci` 遇到临时 EBUSY 文件占用；后续安装和完整脚本复跑成功。
- 当前 Python 测试为 59 项通过。迁移回归覆盖 PowerShell 5/7、StrictMode、
  空格目录、旧运行时仍可用的复制环境、失效环境文件保留及重复执行。
- 从父目录通过 Windows PowerShell 5 调用 `start.ps1 --port 18765` 成功，
  无需激活环境；`python main.py` 无参在默认端口 8765 启动成功。
- 三组真实路线分别为 928、1037、927 米，分段数为 1、1、2；首页、本地文档、
  OpenAPI 和 PNG 瓦片请求成功。1499 个发布文件校验通过，数据版本保持不变。
- 用户要求后已结束占用 8765 的 VS Code MCP Hub 运行进程，保留 VS Code 主程序。
  本轮临时地图服务随后关闭，8765 和 18765 已确认释放。

迁移时还发现浏览器验收脚本从旧父项目解析 Puppeteer。现将此前实际使用的
`puppeteer@25.14.0` 精确固定为本模块的 Web 开发依赖，并从本地 Web 解析。
修正后独立执行 `scripts/verify_offline.py` 通过：真实接口、24 次并发、七级瓦片
及 8 项浏览器测试全部通过，报告确认自有服务端口释放。Web 类型检查及构建通过。

本轮 Web 依赖安装另报告 27 项 npm audit 问题（1 low、6 moderate、15 high、
5 critical）；未在环境迁移修复中批量升级上游依赖，完整审计修复不在本轮范围内。

## Windows 关闭等待修正

用户报告 Ctrl+C 后日志停留在 `Shutting down`。检查时已没有残留的地图进程，
8765 也没有监听，因此未取得该次卡住的现场堆栈。实际在 Windows 控制台完成三组
路线及七级瓦片请求后发送 Ctrl+C，可以正常结束并释放端口。

代码中确认 Uvicorn 的关闭等待未设置超时，默认会无限等待连接、请求或底层
`server.wait_closed()`。现设置 `timeout_graceful_shutdown=3`，复用 Uvicorn
现成的超时取消机制。回归测试模拟底层 TCP 关闭永不返回，修复前在 5 秒测试上限
失败，修复后能取消该等待并继续执行应用关闭流程。

实际 Windows PTY 测试还同时保持 HTTP keep-alive 连接及只发送部分请求体的
POST 请求。按一次 Ctrl+C 后触发 3 秒上限，未完成请求被取消，应用关闭及进程
结束日志完整出现，客户端连接关闭，8765/18765 均无监听。该刻意取消的半包请求
会产生 Uvicorn 的 CancelledError/500 关闭日志，不是成功路线的返回结果。
最终 Python 全量测试为 60 项通过，保留一个现有 Starlette/httpx 弃用提示。

## 默认端口冲突自适应

用户再次启动时出现 WinError 10048。现场确认 8765 被 VS Code MCP Hub
进程 PID 81684 占用，属于再次出现的外部服务监听，不是残留的地图进程。

未指定 `--port` 时现在优先绑定 8765，遇到端口不可用就直接绑定端口 0，
由系统分配空闲端口。Windows 使用 `SO_EXCLUSIVEADDRUSE`，成功绑定后即开始
监听，并将同一个 socket 交给 Uvicorn，避免检测后释放再绑定的竞争。
终端显示实际地图和文档地址；通配监听地址在访问链接中显示为对应的 loopback。
显式指定 `--port` 保持严格模式，冲突时返回 `PORT_IN_USE` 和退出码 1。
DNS、非法监听地址等其他错误不会被默认端口回退掩盖。

实际保留 8765 的外部占用进程，直接运行 `python main.py`，成功回退到 20219。
三组真实路线距离为 928、1037、927 米，首页、文档、OpenAPI 和七级 PNG 瓦片
均请求成功。完成请求后一次 Ctrl+C 正常退出，自有测试进程结束。
回归检查还覆盖首选端口空闲、显式冲突、非法端口和 host、IPv6、通配地址 URL、
独占绑定、启动异常后的 socket 清理，以及此前的 3 秒关闭超时。

本轮再次用真实 Windows 进程复核：8765 仍由 PID 81684 的 VS Code MCP Hub
监听，未终止该进程。直接运行 `python main.py` 自动绑定到 33542；健康检查、
地图页、文档及一条 928 米真实路线均返回成功。按 Ctrl+C 后应用关闭和进程结束
日志完整出现。离线验收脚本通过，24 次并发路线、七级瓦片、三组示例路线及 8 项
浏览器测试通过，并确认验收服务端口已释放。全量 Python 测试 69 项通过，数据
完整性校验 1499 个文件通过。

## 2026-10-30 高德放大小路补充复测

用户提供的 8 个 GCJ-02 参考点通过高德官方步行接口逐对准备，共请求 28 对：
25 对新获取、3 对复用缓存，生成 83 条连续 polyline 步行分段；3 对没有连续有效
步行路径，原始响应和 `skipped_pairs` 均保留，未用直线代替。补充路段以 GCJ-02
写入 OSM/Valhalla 图，并直接发布到 `features/footpaths.geojson`，网页以橙色线显示。
构图时实际验证 8 点按原顺序得到 7 段离线路线，总长约 2.341 km。

最新发布为 `20261029T171725Z-59b5ff5e`：道路图层 592 条，其中补充小路 83 条，
地图清单校验 167 个文件通过。高德栅格仍只准备 z14–18 共 101 张 PNG；z19/z20
接口实测为空白图，因此网页的更高缩放是 z18 本地图片放大，不能依靠栅格放大恢复
缺失的小路。小路来源是上述官方步行 polyline，覆盖范围限于参考点路线周边。

本轮验证结果：

- `python -m pytest -q`: 169 passed，1 个既有 Starlette/httpx 弃用提示。
- `npm run typecheck`、`npm run build`: 均通过。
- `python main.py validate`: 167 个发布文件通过。
- `scripts/verify_offline.py`: 阻断外网后健康检查、83 条小路图层、PNG 瓦片、24 并发路线、浏览器页面和端口释放均通过。
- 直接 POST `/api/v1/routes` 使用 8 个原始点和 6 个途经点返回 7 个分段，坐标仍为原始 GCJ-02 `[经度, 纬度]`。

修正验收脚本期间曾有一次端口释放检查误报：单次 `connect_ex` 将 TCP 关闭过程中的
暂态结果当作仍在监听。初次失败原始记录保留在
`evidence/offline-port-release-first-failure.json` 和 `.log`；检查现已改为最多等待
3 秒确认，最终报告 `evidence/offline-report.json` 状态为通过且
`server_port_released` 为 true。该误报不代表地图服务仍持有监听端口。

## 2026-10-30 GCJ-02 与高德底图

已发布数据版本 `20261029T160131Z-1a08c115`，保留此前数据目录。原始 OSM
存档的 SHA-256 不变；3821 个节点通过高德官方 Web 服务正向转换，新的 XML、
PBF、GeoJSON、Valhalla 图、示例、路线与吸附点统一采用 GCJ-02，运行时不再做
GCJ-02→WGS84 逆向转换。旧坐标系的数据、浏览器缓存和未标注坐标系的旧链接
被隔离，瓦片 URL 包含当前数据版本。

高德请求明确发送 `Referer: https://zslf.zsc.edu.cn/` 和
`Origin: https://zslf.zsc.edu.cn`。官方批量转换实测成功；栅格接口在校园 z18
返回有效 PNG，z19/20 返回相同的空白 PNG，因此实际准备并校验 z14–18 共
101 张图，在网页中放大至20级显示。接口属于未提供版本保障的栅格来源；真实
URL、条款和请求来源分别记录在 manifest。密钥仅保存于被 Git 忽略的本地配置。
数据清单及 115 个文件通过完整性校验。

GPS 校准数据为高德官方转换结果组成的17×17网格。25个不在网格顶点的独立
样本与官方服务比较，最大差值 `0.06798m`，平均 `0.03036m`。这是本次样本的
坐标换算差值，不能视为底图、OSM 道路或设备定位的实地测绘精度。范围外的 GPS
响应明确标记为本地近似转换。

原任务 JSON 的8个 GCJ-02 目标点均以原值落入地图范围。7点能找到50米内的
OSM可步行路段；第3点 `[113.393379,22.529166]` 在50米内没有可吸附路段，
返回路网不可达，不扩大吸附范围或伪造连线。首两点通过浏览器手动输入，实际
请求坐标与原始 JSON 完全相同，成功规划约202米路线。记录见
`evidence/gcj02-report.json`，截图见 `.runtime/screenshots/original-task-gcj02.png`。

验证完成：Python 全量测试、14个相关前端测试文件的168条用例、Web类型检查与
生产构建通过。断网验收在独立进程中阻断Python外网并拦截浏览器外部HTTP请求，
三组示例、24次并发、五级瓦片、本地Swagger、GPS成功/拒绝/超时、原任务输入、
选点拖动、途经点排序、导出、桌面与移动布局共9项浏览器检查全部通过。
浏览器的地图拖动测试曾在缩放动画未结束时操作屏幕外标记，已改为等待标记在
视口中稳定后再拖动，最终全部通过。临时服务退出且端口释放。

另外，服务的优雅关停上限现为10秒（此前记录中的3秒为历史配置）；仍保留
连接卡住时的有界取消。现有Starlette/httpx弃用提示不影响本轮结果。
