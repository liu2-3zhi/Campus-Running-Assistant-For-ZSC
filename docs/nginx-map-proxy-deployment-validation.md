# Nginx 地图代理部署验证

验证日期：2026-10-28。本记录验证本地隔离的真实 Nginx；未操作线上部署、现有服务或真实账号任务。

## 环境与依据

本机 Docker CLI 为 29.5.3，当前 context 为 `desktop-linux`。执行 `docker version`、`docker image ls` 均因 `dockerDesktopLinuxEngine` 管道不存在而失败，未启动 Docker daemon，无法检查镜像或运行 Linux 容器。

在标准命令路径、下载目录及常用工具目录未找到 Nginx 后，从 [Nginx 官方下载页](https://nginx.org/en/download.html) 获取 [nginx/Windows 1.31.8 ZIP](https://nginx.org/download/nginx-1.31.8.zip)，仅解压到 OS 临时目录。未安装系统服务。

本次 ZIP 的 SHA256：`FBB1501009BE34655CC238D460714CF20391B639013F4C73859813D7938783FD`。

## 配置与隔离

集成测试直接提取 `docker/docker-entrypoint.sh` 的 `NGINX_MAP_EOF`、`LOCATIONS_EOF`、`HTTP_ONLY_EOF`、`HEAD_EOF`、`EOF_80_NORMAL`、`EOF_80_REDIRECT`、`EOF_443`，组合实际三种部署配置。保留代理路径、Host/forwarded headers、访问日志条件和重定向规则。

为在 Windows 临时目录独立运行，仅做以下适配：

- 将 `/app`、`/etc/nginx`、日志/PID 路径改为当前测试的临时目录；复制官方包的 `mime.types`。
- 将上游 `127.0.0.1:5000` 替换为临时 Flask 的随机端口，Nginx 仅监听 loopback 的测试端口。
- 将 `/dev/null` 替换为 Windows `NUL`，保持错误日志丢弃语义；Windows worker 数量设为 1。
- 为 HTTPS 生成仅有效一小时的临时自签证书，客户端校验证书；不读取仓库或线上证书。

Flask 使用生产 `register_map_proxy_routes` 和严格 Origin 校验。仅登录、权限与上游传输为隔离夹具；地图 Key、系统 Token、域名均为明确的虚构测试值，不访问真实供应商。此测试验收代理部署链路，真实供应商结果另见 [地图代理验证记录](map-proxy-validation.md)。

## 实测结果

最终指定 HTTP `:8080`、HTTPS `:8443` 重新运行，3 项集成测试通过，耗时 19.004 秒。

| 场景 | 配置检查 | 转发与权限 | 日志检查 |
| --- | --- | --- | --- |
| HTTP-only | 实际 `nginx -t` 通过 | `http://127.0.0.1:8080` 保留 Host 端口与协议；同源初始化 200、错误端口 403；地图代理 200 | 地图请求及其 Key 不进入两类访问日志；普通 API 仍正常记录 |
| HTTP + HTTPS | 实际 `nginx -t` 通过 | HTTP `:8080`、HTTPS `:8443` 均保留 Host 端口、协议和代理链；各自同源 200、错误端口 403、地图代理 200 | 两类访问日志不含地图请求；普通 API 日志保留 |
| HTTPS-only + HTTP redirect | 实际 `nginx -t` 通过 | HTTPS 代理正常；HTTP 地图请求返回 301 | HTTP server 级重定向也不记录地图请求或查询串 |

另外停止隔离 Flask 上游，向地图代理发送带虚构 Key 的请求，真实 Nginx 返回 502；检查 `access.log`、`access_json.log`、`error.log`，均无该 Key 或 `/map-proxy/` 资源请求。验证了异常分支的 Nginx 错误日志隔离，而不只是成功请求的日志过滤。

隔离上游还断言 Key 与 JSONP callback 原样到达供应商传输层；发送给供应商的 `Origin` 使用配置的授权来源。后端 Origin 检查保持严格，未为测试放宽来源或端口比较。

## 复现

先准备独立 Nginx 二进制，测试不会自行联网下载或启动 Docker。Windows 官方 ZIP 应保留旁边的 `conf/mime.types`。

```powershell
$env:ZX_NGINX_BINARY = 'C:\temporary-tools\nginx\nginx.exe'
# 可选：不设置时使用随机空闲端口；指定端口必须尚未被占用。
$env:ZX_NGINX_HTTP_PORT = '8080'
$env:ZX_NGINX_HTTPS_PORT = '8443'
python -m unittest tests.test_nginx_live_deployment -v
```

Linux 可指定已有 Nginx 二进制；`mime.types` 默认回退到 `/etc/nginx/mime.types`，也可用 `ZX_NGINX_MIME_TYPES` 指定。没有 `ZX_NGINX_BINARY` 时，这三项测试明确跳过，普通单元回归不隐式下载或启动服务。

每项测试独立创建临时配置、日志、证书，结束后关闭 Nginx 与 Flask，断言监听端口已释放并删除测试临时目录。本轮没有遗留进程或 `:8080/:8443` 监听。下载 ZIP 已删除；独立 Nginx 解压目录的递归清理被自动审批拒绝，工具仅返回 `blocked by policy`，因此解压包保留在 OS 临时目录且未运行。

## 验证边界

真实 Nginx 配置解析、HTTP/HTTPS 转发、端口保留、Origin 鉴权及日志排除已在本地独立 Windows Nginx 验证。Windows 会提示 `user` 指令不支持、`listen ... http2` 写法弃用；三种配置均成功加载。没有因此修改生产指令。

Docker daemon 不可用，因此没有执行最终 Linux Docker 镜像构建或容器内启动；也未在校园线上 Nginx、实际证书与域名部署验证。这些结果不能代替线上部署验收或真实跑步提交测试。
