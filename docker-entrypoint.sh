#!/bin/bash
# Docker启动脚本 - 使用nginx作为前端服务器，supervisor管理进程

set -e

mkdir -p /var/log/nginx/
touch /var/log/nginx/access_json.log
touch /app/nginx.conf


# 打印启动信息
echo "================================================="
echo "  跑步助手 Docker 容器启动 (Nginx前端模式)"
echo "================================================="

# 检查config.ini是否存在，如果不存在则创建
if [ ! -f "/app/config.ini" ]; then
    echo "配置文件不存在，将在首次运行时自动创建"
fi

# ==========================================
# 0. 配置读取模块 (修复：支持注释、容错处理)
# ==========================================

# 初始化默认值
ssl_enabled="false"
https_only="false"

# 定义读取函数：处理行内注释(#,;)、去空格、转小写
get_ini_value() {
    local key=$1
    local file=$2
    if [ -f "$file" ]; then
        # 1. grep: 查找以 key 开头的行
        # 2. head: 只取第一行防止重复
        # 3. cut: 移除 # 和 ; 后面的注释
        # 4. cut: 提取 = 后面的值
        # 5. tr: 转小写并移除所有空格
        grep -E "^[[:space:]]*$key[[:space:]]*=" "$file" | head -n 1 | \
        cut -d '#' -f 1 | cut -d ';' -f 1 | \
        cut -d '=' -f 2- | \
        tr '[:upper:]' '[:lower:]' | tr -d '[:space:]'
    fi
}

# 执行读取
val_ssl=$(get_ini_value "ssl_enabled" "/app/config.ini")
if [ -n "$val_ssl" ]; then ssl_enabled="$val_ssl"; fi

val_https=$(get_ini_value "https_only" "/app/config.ini")
if [ -n "$val_https" ]; then https_only="$val_https"; fi

echo "配置状态检测: SSL=$ssl_enabled, HTTPS_ONLY=$https_only"

# 创建supervisor配置
cat > /etc/supervisor/conf.d/python-running.conf <<'SUPERVISOR_EOF'
[supervisord]
nodaemon=true
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.pid

[program:nginx]
command=/usr/sbin/nginx -g "daemon off;"
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/nginx-stdout.log
stderr_logfile=/var/log/supervisor/nginx-stderr.log
priority=1

[program:flask-backend]
command=python3 /app/main.py --host 0.0.0.0 --port 5000
directory=/app
autostart=true
autorestart=true
# 修改：将日志重定向到标准输出/错误，以便 docker logs 可以捕获
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
priority=10

[program:nginx-log-forwarder]
command=python3 /app/nginx_log_forwarder.py
directory=/app
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/nginx-log-forwarder-stdout.log
stderr_logfile=/var/log/supervisor/nginx-log-forwarder-stderr.log
priority=20
# 依赖Flask后端先启动
startsecs=10
SUPERVISOR_EOF

# ==========================================
# 1. 生成通用的 Nginx Location 配置
#    (避免代码重复，供 HTTP 和 HTTPS 共同引用)
# ==========================================
cat > /etc/nginx/app_locations.conf <<'LOCATIONS_EOF'
        # 静态文件根目录
        root /app;

        # 默认首页
        index index.html;

        # 客户端最大上传大小
        client_max_body_size 100M;

        # 1. Favicon (位于 /app/favicon.ico)
        location = /favicon.ico {
            root /app;
            log_not_found off;
            access_log off;
            add_header Access-Control-Allow-Origin *;
        }

        # 2 & 3. Scripts 和 Styles 目录
        location ~ ^/(scripts|styles)/ {
            root /app;
            # 设置较长的缓存时间，因为静态资源通常不常变
            expires 7d;
            access_log off;
            add_header Access-Control-Allow-Origin *;
            
            # 【核心修复】如果静态文件不存在，代理到后端(Flask)处理
            # 解决后端动态生成脚本(如模板渲染的js)或路径被误拦截的问题
            try_files $uri @backend;
        }

        # 4. 根目录头像 (位于 /app/default_avatar.png)
        location = /default_avatar.png {
            root /app;
        }

        # 5. Static 路径别名 (URL: /static/... -> File: /app/...)
        location = /static/default_avatar.png {
            alias /app/default_avatar.png;
            add_header Access-Control-Allow-Origin *;
        }

        # 6. API 路径头像特例 (优先级高于通用的 API 正则匹配)
        # 必须使用 = 精确匹配，否则会被下方的 ~ ^/(api|...) 规则拦截
        # 1. 精确匹配默认头像（最高优先级）
        location = /api/avatar/default_avatar.png {
            alias /app/default_avatar.png;
            add_header Access-Control-Allow-Origin *;
        }

        # 2. 禁止访问索引文件
        location = /api/avatar/_index.json {
            return 404;
        }

        # 3. 其余头像文件
        location ~ ^/api/avatar/(.+)$ {
            alias /app/system_accounts/images/$1;
            add_header Access-Control-Allow-Origin *;

            # 如果文件不存在，直接 404（不落到 @backend）
            try_files $uri =404;
        }

        # WebSocket支持 - SocketIO
        location /socket.io/ {
            proxy_pass http://127.0.0.1:5000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
            proxy_read_timeout 86400;
        }

        # API请求代理到Flask后端
        location ~ ^/(api|auth|logs|cdn-cache|avatar|system-announcement)/ {
            proxy_pass http://127.0.0.1:5000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
            proxy_read_timeout 300;
            proxy_connect_timeout 300;
            proxy_send_timeout 300;
        }

        # UUID会话路径 (1/2) - 合法UUID格式 (白名单)
        # 严格匹配 UUID v4 格式 (8-4-4-4-12)，忽略大小写
        location ~* "^/uuid=[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$" {
            # 验证通过，返回前端入口文件
            try_files /index.html =404;
            
            # 禁用缓存，确保每次都能获取最新的index.html
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            add_header Pragma "no-cache";
            add_header Expires "0";
        }

        # UUID会话路径 (2/2) - 非法UUID格式 (黑名单)
        # 凡是以 /uuid= 开头但未匹配上方规则的，均为非法格式，直接重定向回首页
        location ~ ^/uuid= {
            return 302 /;
        }

        # 首页 - 优先尝试静态文件，如果不存在则代理到Flask
        location = / {
            try_files /index.html @backend;
        }

        # 其他请求 - 先尝试静态文件，不存在则代理到Flask
        location / {
            try_files $uri $uri/ @backend;
        }

        # 后端代理fallback
        location @backend {
            proxy_pass http://127.0.0.1:5000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
LOCATIONS_EOF

# ==========================================
# 2. 生成主 Nginx 配置
# ==========================================

# 检查SSL证书和启用状态
if [ -f "/app/ssl/fullchain.pem" ] && [ -f "/app/ssl/privkey.key" ] && [ "$ssl_enabled" = "true" ]; then
    echo "检测到SSL证书文件且SSL已启用"
    
    # 开始写入 nginx.conf 头部
    cat > /etc/nginx/nginx.conf <<'HEAD_EOF'
user  www-data;
worker_processes  auto;
error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
    worker_connections  1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for"';
    
    # JSON格式日志 - 用于结构化日志记录和分析
    log_format  json_combined escape=json
        '{'
            '"time_local":"$time_local",'
            '"remote_addr":"$remote_addr",'
            '"remote_user":"$remote_user",'
            '"request":"$request",'
            '"status":"$status",'
            '"body_bytes_sent":"$body_bytes_sent",'
            '"request_time":"$request_time",'
            '"http_referer":"$http_referer",'
            '"http_user_agent":"$http_user_agent",'
            '"http_x_forwarded_for":"$http_x_forwarded_for"'
        '}';
    
    # 传统格式访问日志
    access_log  /var/log/nginx/access.log  main;
    # JSON格式访问日志（用于程序化处理和转发到Python日志系统）
    access_log  /var/log/nginx/access_json.log  json_combined;
    
    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;
    keepalive_timeout  65;
    types_hash_max_size 2048;
    gzip  on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml font/truetype font/opentype application/vnd.ms-fontobject image/svg+xml;
HEAD_EOF

    # 根据 https_only 配置端口 80 的行为
    if [ "$https_only" = "true" ]; then
        echo "HTTPS Only 模式: 开启，Port 80 将重定向到 HTTPS"
        cat >> /etc/nginx/nginx.conf <<'EOF_80_REDIRECT'
    # HTTP服务器 - 强制重定向到HTTPS
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }
EOF_80_REDIRECT
    else
        echo "HTTPS Only 模式: 关闭，Port 80 将正常提供服务 (HTTP + HTTPS 并存)"
        cat >> /etc/nginx/nginx.conf <<'EOF_80_NORMAL'
    # HTTP服务器 - 正常服务
    server {
        listen 80;
        server_name _;
        include /etc/nginx/app_locations.conf;
    }
EOF_80_NORMAL
    fi

    # 配置端口 443 (HTTPS)
    cat >> /etc/nginx/nginx.conf <<'EOF_443'
    # HTTPS服务器 - 端口443
    server {
        listen 443 ssl http2;
        server_name _;

        # SSL证书配置
        ssl_certificate /app/ssl/fullchain.pem;
        ssl_certificate_key /app/ssl/privkey.key;

        # SSL安全配置
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;
        
        # 引用通用Location配置
        include /etc/nginx/app_locations.conf;
    }
}
EOF_443

else
    echo "SSL未启用或证书缺失，仅启用HTTP模式（80端口）"
    
    # 写入完整的 HTTP-Only 配置
    cat > /etc/nginx/nginx.conf <<'HTTP_ONLY_EOF'
user  www-data;
worker_processes  auto;
error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
    worker_connections  1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for"';
    
    # JSON格式日志 - 用于结构化日志记录和分析
    log_format  json_combined escape=json
        '{'
            '"time_local":"$time_local",'
            '"remote_addr":"$remote_addr",'
            '"remote_user":"$remote_user",'
            '"request":"$request",'
            '"status":"$status",'
            '"body_bytes_sent":"$body_bytes_sent",'
            '"request_time":"$request_time",'
            '"http_referer":"$http_referer",'
            '"http_user_agent":"$http_user_agent",'
            '"http_x_forwarded_for":"$http_x_forwarded_for"'
        '}';
    
    # 传统格式访问日志
    access_log  /var/log/nginx/access.log  main;
    # JSON格式访问日志（用于程序化处理和转发到Python日志系统）
    access_log  /var/log/nginx/access_json.log  json_combined;
    
    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;
    keepalive_timeout  65;
    types_hash_max_size 2048;
    gzip  on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml font/truetype font/opentype application/vnd.ms-fontobject image/svg+xml;

    # HTTP服务器 - 端口80
    server {
        listen 80;
        server_name _;
        include /etc/nginx/app_locations.conf;
    }
}
HTTP_ONLY_EOF
fi

# 创建日志目录
mkdir -p /var/log/supervisor /var/log/nginx

# 测试nginx配置
echo "测试nginx配置..."
nginx -t

# 启动supervisor（管理nginx和flask后端）
echo "启动服务..."
echo "- Nginx将监听端口80和443（如果启用SSL）"
echo "- Flask后端将监听127.0.0.1:5000"
echo "================================================="
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/python-running.conf