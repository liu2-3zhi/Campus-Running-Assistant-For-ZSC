# 跑步助手

## 项目介绍

跑步助手是一个基于 Python Flask 的校园跑 Web 应用，围绕校园跑任务场景提供统一的 Web 化入口与配套能力。当前代码中可以明确看到的能力包括：账号与会话管理、自动签到配置、支付订单处理、健康检查、Nginx 日志转发、主题与随机背景处理，以及支付商品名生成等模块。

- 技术栈：Python、Flask、Flask-SocketIO、Playwright、Nginx
- 体验地址：http://run.zelly.cn

## 功能特点

- 提供校园跑相关场景的 Web 化管理入口
- 启动时自动初始化配置、权限文件与默认管理员账号
- 支持自动签到配置与会话持久化
- 支持支付订单状态流转、二维码缓存与支付方式配置
- 提供 `/health` 健康检查与 Nginx 访问日志转发能力
- 支持主题样式与随机背景缓存
- 内置支付商品名生成器，当前已注册 `lomei` 与 `travel_service` 两种模式

## 本地运行

以下示例以 Linux / macOS 为例：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r ssl/requirements.txt
python -m playwright install chromium
python main.py --host 127.0.0.1 --port 5000
```

启动后可通过 `http://127.0.0.1:5000` 访问系统。

如果在 Linux 环境下使用 Playwright 时仍缺少浏览器依赖，可额外执行：

```bash
bash After_pip_install.sh
```

首次启动时，程序会自动创建 `configs/config.json`、`permissions.json` 以及默认管理员账号。若相关配置或数据文件缺失，程序也会尝试自动补齐或重建。

默认管理员账号：

- 账号：admin
- 密码：admin

建议首次登录后立即修改默认密码。

## 启动参数说明

程序支持以下常用启动参数：

- `--host`：监听地址，默认 `127.0.0.1`
- `--port`：监听端口，默认 `5000`
- `--log-level`：日志级别，可选 `debug`、`info`、`warning`、`error`、`critical`

关于 `--host` 和 `--port`，建议注意：

- 默认 `127.0.0.1` 仅监听本机访问，适合本地调试
- 如需局域网访问、反向代理或容器场景，可使用 `--host 0.0.0.0`
- 使用 `0.0.0.0` 时，浏览器访问应使用实际服务器 IP 或域名，而不是直接访问 `0.0.0.0`
- 如果使用默认端口 `5000` 且端口被占用，程序会自动尝试其他常见端口
- 如果手动指定了非默认端口，程序会直接尝试绑定；若端口不可用，则启动失败
- 在 Linux / macOS 上直接绑定 `80`、`443` 等低位端口时，通常需要更高权限

示例：

```bash
python main.py --host 0.0.0.0 --port 5000 --log-level info
```

## 容器运行

项目已经提供可直接拉取的镜像：

```bash
docker pull xenlia/campus-running-assistant-for-zsc:latest
```

如需使用 Docker Compose，可直接使用下面这份配置：

```yaml
version: '3.8'

services:
  python-running-helper:
    image: xenlia/campus-running-assistant-for-zsc:latest
    container_name: python-running-helper
    ports:
      - "8480:80"
      - "8843:443"
    volumes:
      - ./ssl:/app/ssl
      - ./cache:/app/cache
      - ./logs:/app/logs
      - ./messages.json:/app/messages.json
      - ./permissions.json:/app/permissions.json
      - ./reminders.json:/app/reminders.json
      - ./background_tasks:/app/background_tasks
      - ./school_accounts:/app/school_accounts
      - ./sessions:/app/sessions
      - ./tokens:/app/tokens
      - ./system_accounts:/app/system_accounts
      - ./payment_orders:/app/payment_orders
      - ./payment_methods.json:/app/payment_methods.json
      - ./configs:/app/configs
      - ./uploads:/app/uploads
      - ./Remove_Acoount:/app/Remove_Acoount
      - ./User_Billing:/app/User_Billing
      - ./amap_watermark_control.json:/app/amap_watermark_control.json
      - ./random_background_image:/app/random_background_image
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

启动前建议先准备下面这些挂载项。

目录：

- `ssl`
- `cache`
- `logs`
- `background_tasks`
- `school_accounts`
- `sessions`
- `tokens`
- `system_accounts`
- `payment_orders`
- `configs`
- `uploads`
- `Remove_Acoount`
- `User_Billing`
- `random_background_image`

文件：

- `messages.json`
- `permissions.json`
- `reminders.json`
- `payment_methods.json`
- `amap_watermark_control.json`

如果你想一次性准备好，可以直接执行：

```bash
mkdir -p ssl cache logs background_tasks school_accounts sessions tokens system_accounts payment_orders configs uploads Remove_Acoount User_Billing random_background_image

touch messages.json permissions.json reminders.json payment_methods.json amap_watermark_control.json
```

准备完成后再执行：

```bash
docker compose up -d
```

访问时建议这样理解：

- 默认先访问 `http://127.0.0.1:8480`
- 若已准备 `ssl/fullchain.pem` 与 `ssl/privkey.key`，并在配置中启用 `ssl_enabled`，可访问 `https://127.0.0.1:8843`
- 若同时启用 `https_only`，HTTP 端口会重定向到 HTTPS
- 容器内后端服务运行在 `0.0.0.0:5000`，但对外访问仍以 Nginx 暴露的端口为准

## 配置说明

当前运行时主配置文件为 `configs/config.json`，首次启动时会自动创建。

## 兼容性说明

项目主要在 **ZSC** 环境下完成验证与开发；对于其他环境或不同部署方式，请以实际运行结果为准。

## 依赖的开源项目

1. [Editor.md](https://github.com/pandao/editor.md)
