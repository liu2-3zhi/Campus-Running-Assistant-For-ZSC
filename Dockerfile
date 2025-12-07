# Dockerfile for Python Running Helper
# 使用官方Python 3.11镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（包括nginx）
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
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装Playwright浏览器
RUN playwright install chromium
RUN playwright install-deps chromium

# 复制应用程序文件
COPY . .

# 复制nginx配置文件
COPY nginx.conf /etc/nginx/nginx.conf

# 创建必要的目录
RUN mkdir -p /app/ssl /app/cache /app/logs /var/log/nginx

# 暴露端口 80 (HTTP) 和 443 (HTTPS)
EXPOSE 80 443

# 设置环境变量
ENV PYTHONUNBUFFERED=1

RUN chmod -R 777 . 

# 创建启动脚本
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh


ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

RUN apt-get update && apt-get install -y dos2unix parallel


# 在构建阶段就转换换行符
RUN find /app/ \
      -type d \( -path '*/.git' -o -path '/app/logs/archive' \) -prune -o \
      -type f \( -name "*.py" -o -name "*.sh" -o -name "*.js" -o -name "*.css" -o -name "*.html" -o -name "*.txt" -o -name "*.md" \) -print0 \
    | parallel -0 -j$(nproc) --verbose dos2unix {}


# 启动时再做一次（可选），并打印提示
ENTRYPOINT ["/bin/sh", "-c", \
  "echo '==> 开始批量转换换行符(仅针对代码文件)...' && \
   find /app/ \
     -type d \\( -path '*/.git' -o -path '/app/logs/archive' -o -path '/app/system_accounts/images' \\) -prune -o \
     -type f \\( -name '*.py' -o -name '*.sh' -o -name '*.js' -o -name '*.css' -o -name '*.html' \\) -print0 \
   | parallel -0 -j$(nproc) dos2unix {} && \
   echo '==> 换行符转换完成，启动主程序...' && \
   exec /app/docker-entrypoint.sh"]