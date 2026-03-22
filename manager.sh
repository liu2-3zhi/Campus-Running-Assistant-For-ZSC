#!/bin/bash

# --- 配置部分 ---

# 1. screen 会话的英文名称
SESSION_NAME="zis_runner_helper"

# 获取脚本文件所在的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 2. 临时的 screen 配置文件路径
SCREEN_RC_FILE="${SCRIPT_DIR}/${SESSION_NAME}.screenrc"

# 3. 定义要运行的脚本文件路径
TARGET_SCRIPT="${SCRIPT_DIR}/start.sh"

# 4. 你想在后台运行的实际命令
COMMAND_TO_RUN="${TARGET_SCRIPT} --port 443 --host 0.0.0.0"

# --- 脚本正文 ---

# 检查 'screen' 是否安装
if ! command -v screen &> /dev/null; then
    echo "错误: 'screen' 未安装。"
    echo "请先安装 'screen' (例如: sudo apt install screen 或 yum install screen)"
    exit 1
fi

# 显示主菜单
show_menu() {
    clear
    echo "================================================="
    echo " 电子科技大学中山学院校园跑步助手 (Screen 管理器)"
    echo " (ZIS Runner Helper - Session Manager)"
    echo "================================================="
    echo "  会话名称: $SESSION_NAME"
    echo "  运行命令: $COMMAND_TO_RUN"
    echo "-------------------------------------------------"
    echo "  1. 启动 / 连接会话 (Start / Attach Session)"
    echo "  2. 关闭会话 (Stop Session)"
    echo "  0. 退出脚本 (Exit)"
    echo "-------------------------------------------------"
    echo -n "请输入选项 [0-2]: "
}

# 辅助函数：清理残留文件
cleanup_rc_file() {
    if [ -f "$SCREEN_RC_FILE" ]; then
        # 尝试删除
        rm "$SCREEN_RC_FILE" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "已清理残留的配置文件: $SCREEN_RC_FILE"
        else
            echo "警告: 无法删除残留文件 '$SCREEN_RC_FILE' (可能权限不足)。"
            echo "尝试强制修改权限..."
            chmod 777 "$SCREEN_RC_FILE" 2>/dev/null && rm "$SCREEN_RC_FILE"
        fi
    fi
}

# 辅助函数：检查并修复权限
check_and_fix_permissions() {
    echo "正在检查文件权限..."
    
    # 1. 检查目标启动脚本 (start.sh)
    if [ -f "$TARGET_SCRIPT" ]; then
        if [ ! -x "$TARGET_SCRIPT" ]; then
            echo "权限检查: '$TARGET_SCRIPT' 缺少执行权限。"
            echo "正在尝试修复权限 (chmod +x) ..."
            chmod +x "$TARGET_SCRIPT"
            if [ $? -ne 0 ]; then
                echo "错误: 无法修改 '$TARGET_SCRIPT' 的权限。请手动执行: chmod +x $TARGET_SCRIPT"
                return 1
            else
                echo " -> '$TARGET_SCRIPT' 权限修复成功。"
            fi
        fi
    else
        echo "严重错误: 未找到启动脚本 '$TARGET_SCRIPT'，请确认文件位置。"
        return 1
    fi
    
    # 2. 检查当前目录是否可写 (用于创建 .screenrc)
    if [ ! -w "$SCRIPT_DIR" ]; then
        echo "错误: 当前目录 '$SCRIPT_DIR' 不可写，无法创建配置文件。"
        return 1
    fi
    
    # 3. 检查残留的 RC 文件权限 (如果存在)
    if [ -f "$SCREEN_RC_FILE" ]; then
        if [ ! -w "$SCREEN_RC_FILE" ]; then
            echo "警告: 发现残留配置文件 '$SCREEN_RC_FILE' 且无写权限。"
            echo "尝试赋予权限..."
            chmod +w "$SCREEN_RC_FILE"
        fi
    fi
    
    return 0
}

# 功能 1: 启动或连接会话
start_session() {
    # 1. 检查会话是否已在运行
    if screen -ls | grep -q "\.$SESSION_NAME\s"; then
        echo "会话 '$SESSION_NAME' 已在运行。正在连接..."
        sleep 1
        exec screen -r "$SESSION_NAME"
    else
        # 2. 启动新会话流程
        echo "未找到会话。准备启动新的会话 '$SESSION_NAME'..."
        
        # --- 步骤 A: 权限检查 ---
        check_and_fix_permissions
        if [ $? -ne 0 ]; then
            echo "权限检查失败，取消启动。"
            sleep 3
            return
        fi
        
        # --- 步骤 B: 清理残留文件 (防止上次意外退出导致文件存在) ---
        cleanup_rc_file
        
        # --- 步骤 C: 创建配置文件 ---
        echo "正在创建顶部提示栏配置文件: $SCREEN_RC_FILE"
        # 使用 try-catch 风格确保文件能写入
        {
            echo "hardstatus alwaysfirstline"
            echo "hardstatus string \"%{= Yk} 提示: 按 Ctrl+A 然后按 D (分离会话)，返回到主终端 %{= Kk}\""
        } > "$SCREEN_RC_FILE"
        
        if [ ! -f "$SCREEN_RC_FILE" ]; then
            echo "错误: 配置文件创建失败，无法启动。"
            sleep 2
            return
        fi
        
        # --- 步骤 D: 启动 Screen ---
        screen -c "$SCREEN_RC_FILE" -dmS "$SESSION_NAME" bash -c "$COMMAND_TO_RUN; exec bash"
        
        # 检查是否启动成功
        sleep 1 # 给一点时间让 screen 启动
        if screen -ls | grep -q "\.$SESSION_NAME\s"; then
            echo "会话已在后台启动。现在连接..."
            sleep 1
            exec screen -r "$SESSION_NAME"
        else
            echo "-------------------------------------------------"
            echo "错误：无法启动会话 '$SESSION_NAME'。"
            echo "可能原因："
            echo "1. 端口被占用"
            echo "2. start.sh 脚本内部报错 (请尝试手动运行 ./start.sh 排查)"
            echo "-------------------------------------------------"
            # 启动失败也要清理临时文件
            cleanup_rc_file
            sleep 5
        fi
    fi
}

# 功能 2: 关闭会话
stop_session() {
    # 尝试关闭 Screen 会话
    if screen -ls | grep -q "\.$SESSION_NAME\s"; then
        echo "正在发送关闭命令到会话 '$SESSION_NAME'..."
        screen -S "$SESSION_NAME" -X quit
        
        sleep 1
        if screen -ls | grep -q "\.$SESSION_NAME\s"; then
            echo "错误：会话未能正常关闭。请手动检查: screen -ls"
        else
            echo "会话 '$SESSION_NAME' 已成功关闭。"
        fi
    else
        echo "会话 '$SESSION_NAME' 当前未运行。"
    fi
    
    # --- 无论会话之前是否在运行，都检查并清理残留文件 ---
    cleanup_rc_file
    # --------------------------------------------------
    
    echo ""
    echo "按 Enter 键返回菜单..."
    read -r
}

# 主循环
main() {
    while true; do
        show_menu
        read -r choice
        case $choice in
            1)
                start_session
                # 如果 start_session 里的 exec 执行了，下面的代码不会跑
                # 如果没执行 exec (比如启动失败)，会跑到这里
                echo "正在返回菜单..."
                sleep 1
            ;;
            2)
                stop_session
            ;;
            0)
                echo "正在退出。"
                # 退出前也可以尝试清理一下，保持环境整洁
                cleanup_rc_file
                break
            ;;
            *)
                echo "无效选项 '$choice'，请重试。"
                sleep 1
            ;;
        esac
    done
}

# 运行主函数
main