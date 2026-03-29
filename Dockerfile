# Dockerfile for Python Running Helper
# 使用官方Python 3.11镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（含 Chromium 运行所需动态库、nginx、supervisor）
# 注意：安装完成后清理 apt 索引，减少镜像体积
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt并安装Python依赖
# 这里复用缓存层：只有 requirements.txt 变化时才会重新安装依赖
COPY ./ssl/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright Chromium 及其系统依赖
RUN playwright install chromium
RUN playwright install-deps chromium

# 安装换行符转换与并行处理工具
RUN apt-get update && apt-get install -y dos2unix parallel

# 复制应用程序文件
COPY . .

# 复制 nginx 日志转发脚本（用于集中处理日志）
COPY ./nginx/nginx_log_forwarder.py /app/nginx_log_forwarder.py

# 创建必要的目录
RUN mkdir -p /app/ssl /app/cache /app/logs /var/log/nginx

# 暴露端口 80 (HTTP) 和 443 (HTTPS)
EXPOSE 80 443

# 设置环境变量：关闭 Python 输出缓冲，便于容器日志实时观察
ENV PYTHONUNBUFFERED=1

# 放宽权限，确保运行时可读写项目目录（保持与当前项目行为一致）
RUN chmod -R 777 . 

# 复制入口脚本并赋予执行权限
COPY ./docker/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# 设置容器时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

# 预创建运行期所需文件与目录，避免启动时因缺失路径报错
RUN touch /app/ssh
RUN touch /app/config.ini
RUN mkdir -p /app/cache
RUN mkdir -p /app/logs
RUN touch /app/messages.json
RUN touch /app/permissions.json
RUN touch /app/reminders.json
RUN mkdir -p /app/background_tasks
RUN mkdir -p /app/school_accounts
RUN mkdir -p /app/sessions
RUN mkdir -p /app/tokens
RUN mkdir -p /app/system_accounts
RUN mkdir -p /app/payment_orders
RUN touch /app/payment_methods.json
RUN mkdir -p /app/configs
RUN mkdir -p /app/uploads


# 在构建阶段批量转换换行符（CRLF -> LF）
# - 排除 .git 与日志归档目录
# - 仅处理常见源码与文本文件
# - 使用 GNU parallel 提升转换速度
RUN find /app/ \
      -type d \( -path '*/.git' -o -path '/app/logs/archive' \) -prune -o \
      -type f \( -name "*.py" -o -name "*.sh" -o -name "*.js" -o -name "*.css" -o -name "*.html" -o -name "*.txt" -o -name "*.md" \) -print0 \
    | parallel -0 -j$(nproc) --verbose dos2unix {}


# 启动时再次执行一次换行符修正（双保险），然后启动主程序
# 额外排除 /app/system_accounts/images，避免处理二进制/图片目录
ENTRYPOINT ["/bin/sh", "-c", \
  "echo '==> 开始批量转换换行符(仅针对代码文件)...' && \
   find /app/ \
     -type d \\( -path '*/.git' -o -path '/app/logs/archive' -o -path '/app/system_accounts/images' \\) -prune -o \
     -type f \\( -name '*.py' -o -name '*.sh' -o -name '*.js' -o -name '*.css' -o -name '*.html' \\) -print0 \
   | parallel -0 -j$(nproc) dos2unix {} && \
   echo '==> 换行符转换完成，启动主程序...' && \
   exec /app/docker-entrypoint.sh"]
