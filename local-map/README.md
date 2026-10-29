# 电子科技大学中山学院离线地图

独立的校园地图、步行路线规划 API 和 Web 测试台。使用真实 OpenStreetMap
数据，路线引擎复用 Valhalla，默认使用准备阶段缓存的高德图片瓦片，Web
基于 Valhalla 官方 Web App 适配。所有代码和数据均限定在本目录，未接入主程序。

## 启动

本机环境准备并完成地图构建后，直接运行：

```powershell
Set-Location C:\Users\Zelly\Documents\GitHub\python_runing\local-map
.\start.ps1
```

启动后按终端中的 `Map` 和 `API docs` 地址访问地图及交互文档。
默认只监听本机，优先使用 `127.0.0.1:8765`；若端口已被占用，则由系统自动
分配可用端口并输出实际地址。按 Ctrl+C 停止。
关闭时最多等待现有连接 10 秒，让地图瓦片等正常响应有时间完成；超过上限的卡住连接会被强制结束，避免 Windows 的底层 TCP 关闭等待一直挂起。
运行时不需要 Docker、Node 服务或任何在线地图密钥。

`start.ps1` 和 `setup.ps1` 都按自身位置识别项目目录。搬迁或复制后会检测旧虚拟环境，
将其完整保留到 `.runtime/venv-backups`，再使用当前目录的 Python 重建；不会修改地图数据。
启动脚本无需手动激活环境，环境正常时不重新安装依赖。激活环境后，`python main.py`
也会直接启动 Web，等同于 `python main.py serve`。
需要固定端口时，运行 `.\start.ps1 --port 8766` 或
`python main.py serve --port 8766`。显式指定的端口被占用时会明确报错，
不会自动切换；`--port 0` 则始终由系统分配可用端口。

在新机器首次准备环境时，需要 Windows x64、Node.js 24、uv，以及 Microsoft
Visual C++ Redistributable。Python 3.12 放在本目录的 `.runtime`，不替换系统 Python。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
.venv\Scripts\python.exe main.py prepare
.venv\Scripts\python.exe main.py build
.venv\Scripts\python.exe main.py validate
.venv\Scripts\python.exe main.py serve
```

首次安装和 `prepare` 可以联网；数据准备完毕后的 `build`、`validate`、`serve`
均使用本地资源。`prepare` 使用高德官方 Web 服务把原始 OSM 节点正向转换为
GCJ-02，并缓存校园范围的高德 14–18 级瓦片。网页可继续放大至 20 级；19、20
级使用 18 级图片放大，避免该来源返回的空白图。构建产物、虚拟环境、密钥和依赖
目录不进入 Git，原始 WGS84 源数据和版本信息保留。

准备数据前，将 Web 服务 Key 设置为 `AMAP_WEB_KEY` 环境变量，或写入本地
`.local-config.json` 的 `amap_web_key` 字段。该文件已被 Git 忽略；日常启动
不读取或向浏览器公开 Key，也不加载在线 JS SDK。
所有高德请求都显式设置 `Referer: https://zslf.zsc.edu.cn/` 和
`Origin: https://zslf.zsc.edu.cn`。API 的真实数据来源 URL 与请求来源分开记录。

高德栅格使用已实测的 `webrd01.is.autonavi.com/appmaptile`，它不是有版本保障的
公开 Web 服务接口。其服务条款及来源保存在清单中；后续接口变化可能导致重新准备
失败，此时保留旧版本。需要独立本地渲染时可使用
`prepare --tile-provider osm --maxzoom 20` 与 `build --maxzoom 20`，TileServer GL
会从同一份 GCJ-02 GeoJSON 生成底图，不把 WGS84 图片混入 GCJ-02 版本。

导入已有 OSM 数据时使用：

```powershell
.venv\Scripts\python.exe main.py prepare --source .\campus.osm
.venv\Scripts\python.exe main.py build
```

若要把任务文件中的参考点周边小路一并归档，准备阶段传入 `--footpaths`：

```powershell
.venv\Scripts\python.exe main.py prepare `
  --source .\data\source\a0595348040142196da0.osm `
  --footpaths C:\Users\Zelly\Downloads\task_d2c2c8671877d322b51efaac344e84f1_1793097445.json
.venv\Scripts\python.exe main.py build
```

该选项使用高德官方步行接口保存真实 polyline，再并入 GCJ-02 的 Valhalla 图和
`footpaths` GeoJSON 图层；不会按端点绘制直线。当前参考文件得到 83 条补充路段，
3 对高德没有连续步行路径的组合会保留在 `skipped_pairs` 中。高德栅格实测原生
细节到 z18，z19/z20 只是本地放大 z18 图片；因此放大底图本身不能补出小路，
补充步行几何才是离线小路来源。

各命令均支持 `--data-dir`；`serve` 另支持 `--host` 和 `--port`。
修改本地道路可使用 JOSM 编辑 OSM 文件，再导入重建。准备或构建失败不会替换
已发布的数据版本；`data/current.json` 指向校验通过的完整版本。

## Web 使用

- 点击地图或输入经纬度设置起点、终点、途经点，可拖动位置、调整顺序及清空。
- 使用校园示例按钮，可在不位于校园的设备上立即测试。
- 点击设备定位后由浏览器请求权限；允许后显示当前位置，拒绝或定位超时仍可手动选点。
- 查看路线、距离、时间及吸附位置，在调试面板检查实际请求、响应和耗时，导出 GeoJSON。

界面操作使用中文；详细转向指令保留当前原生引擎的 `en-US` 文本。

设备定位取决于系统、设备、浏览器权限与安全上下文，不能保证桌面或断网设备能
获得 GPS。完全离线保证针对本应用的地图、页面资源和 API；测试中的模拟定位
不能替代真实设备定位验收。

## API

地图、任务输入、GeoJSON、路线、吸附点和原生 polyline6 均采用 **GCJ-02（火星
坐标）**，数组顺序固定为 `[经度, 纬度]`。手输和任务文件中的 GCJ-02 坐标原样
进入离线路网，不在请求时做 GCJ-02→WGS84 的逆向转换。Valhalla 路网也由已转换
的 GCJ-02 OSM 节点构建；旧 WGS84 版本会明确拒绝加载，必须重新 prepare/build。

唯一的 WGS84 输入边界是设备 GPS。校园内使用准备阶段保存的高德官方转换网格
在本地插值，离线可用；范围外使用本地近似正向算法，响应中的 `method` 明确区分。
这解决坐标基准混用，不修正 OSM 自身的测绘误差或缺失道路；道路吸附仍不代表入口。

| 方法与路径 | 说明 |
| --- | --- |
| `GET /healthz` | 服务和当前地图数据状态 |
| `GET /api/v1/map` | 范围、图层、来源、覆盖诊断及示例 |
| `GET /api/v1/map-style` | 根据当前数据生成的本地 GCJ-02 MapLibre 样式 |
| `POST /api/v1/coordinates/gps` | 将设备 WGS84 GPS 点离线换算到 GCJ-02 |
| `GET /api/v1/features/{layer}` | 指定图层的 GeoJSON |
| `GET /api/v1/tiles/{z}/{x}/{y}.png` | 256px 本地 XYZ 图片瓦片 |
| `POST /api/v1/routes` | 统一步行规划接口 |
| `GET /valhalla/route?json=...` | 官方 Web 使用的 Valhalla 原生兼容接口 |
| `GET /openapi.json`、`GET /docs` | 接口契约和本地交互文档 |

规划请求：

```json
{
  "start": [113.389, 22.527],
  "end": [113.390, 22.528],
  "waypoints": []
}
```

该片段用于说明格式；可运行的真实路线坐标请从 `/api/v1/map` 的 `examples`
读取，或在 Web 点击示例。最多支持 20 个有序途经点；返回 `route.geometry`、
`distance_m`、`duration_s`、`legs`、`snapped_points`。使用步行最短距离策略，
步速设置为 5.04km/h；时间是引擎估计值。输入点到路段的吸附偏移不作为真实道路。
吸附超过 50 米、数据范围之外或路网不连通时明确失败，不使用直线伪造路线。

## 数据与适用范围

原始 OSM 的 WGS84 抓取范围为 `[113.3798, 22.5255, 113.3901, 22.5355]`；
运行时的 GCJ-02 范围以 `/api/v1/map` 的 `bounds` 为准，约为
`[113.385275, 22.522802, 113.395582, 22.532810]`。包含主校园、北侧校园地块与
周边连接道路；路线可能经过覆盖范围内的校外连接路。

公开 OSM 记录了部分校园主道路及建筑，内部步道、楼梯和建筑入口并未完整收录。
当前版本按“真实数据先交付”提供覆盖诊断，不承诺所有建筑入口可达，不代表实地
通行核验结果。请勿将最近道路吸附点理解为建筑入口。

路网数据许可为 ODbL，地图注明 OpenStreetMap contributors；高德底图与转换服务
的来源和条款单独记录，不把其图片标为 OSM 或开源数据。上游组件与许可见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，构建及测试记录见
[VALIDATION.md](VALIDATION.md)。主要上游提交和发布版本见 `UPSTREAM_LOCK.json`。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe main.py validate
.venv\Scripts\python.exe scripts/verify_offline.py
```

浏览器验收需要先构建地图和 Web。Puppeteer 测试依赖固定在本模块的 Web 依赖中，
不依赖父项目；若本机没有对应的测试浏览器，先联网运行一次
`npm exec --prefix web -- puppeteer browsers install chrome`。
该脚本会新启 Python 服务，拒绝 Python 的非本机 socket 连接，在浏览器中阻断
外部 HTTP 请求，执行真实数据和浏览器测试后自动关闭服务。它没有修改系统防火墙；
Python audit hook 不覆盖 C++ 直接联网，因此另检查 Valhalla 无远程瓦片配置。
具体执行命令与结果以 `VALIDATION.md` 为准。
