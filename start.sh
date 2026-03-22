#!/bin/bash

# --- 配置 ---
VENV_NAME="zs_campus_run_helper_venv"
PYTHON_CMD="python3" # 如果你的默认 python 是 3.x，可以改成 "python"
EXTRA_SCRIPT_NAME="After_pip_install.sh" # 定义额外脚本的文件名
# --- 结束配置 ---

# 获取脚本文件所在的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# --- 功能函数 ---

# 检查环境函数
check_environment() {
    # 检查 python 命令是否存在
    if ! command -v $PYTHON_CMD &> /dev/null; then
        echo "错误: $PYTHON_CMD 未找到。"
        echo "请安装 Python 3 并确保它在您的 PATH 中。"
        exit 1
    fi
    
    # 检查依赖文件是否存在
    if [ ! -f "${SCRIPT_DIR}/requirements.txt" ]; then
        echo "错误: 未找到 requirements.txt 文件。"
        echo "请确保依赖文件与此脚本位于同一目录。"
        exit 1
    fi
}

# 手动模式说明
show_manual_mode() {
    echo "--- 手动模式说明 ---"
    echo "请按以下步骤手动操作："
    echo "1. (如果需要) 创建虚拟环境: $PYTHON_CMD -m venv $VENV_NAME"
    echo "2. 激活虚拟环境: source $VENV_NAME/bin/activate"
    echo "3. 安装依赖: pip install -r ${SCRIPT_DIR}/requirements.txt"
    echo "4. (可选) 赋予权限并执行: chmod +x ${SCRIPT_DIR}/$EXTRA_SCRIPT_NAME && source ${SCRIPT_DIR}/$EXTRA_SCRIPT_NAME"
    echo "5. 运行程序: $PYTHON_CMD ${SCRIPT_DIR}/main.py"
    echo "6. (完成后) 退出虚拟环境: deactivate"
}

# 自动启动逻辑
run_auto_start() {
    # 传入的所有参数 ($@) 都会传递给 main.py
    
    # 1. 检查虚拟环境是否存在
    if [ ! -f "$VENV_NAME/bin/activate" ]; then
        echo "未找到虚拟环境 '$VENV_NAME'。正在创建..."
        $PYTHON_CMD -m venv $VENV_NAME
        if [ $? -ne 0 ]; then
            echo "创建虚拟环境失败。请尝试使用 'manual' 模式运行。"
            exit 1
        fi
    else
        echo "找到虚拟环境 '$VENV_NAME'。"
    fi
    
    # 2. 激活虚拟环境
    echo "正在激活虚拟环境..."
    source $VENV_NAME/bin/activate
    if [ $? -ne 0 ]; then
        echo "激活虚拟环境失败。请尝试使用 'manual' 模式运行。"
        exit 1
    fi
    
    # 3. 安装/更新依赖
    echo "正在从 requirements.txt 安装/更新依赖..."
    pip install -r "${SCRIPT_DIR}/requirements.txt"
    if [ $? -ne 0 ]; then
        echo "安装依赖失败。请检查 requirements.txt 文件和网络连接。"
        echo "请尝试使用 'manual' 模式运行。"
        exit 1
    fi
    
    # 3.5 执行额外安装脚本 (例如 Playwright install)
    EXTRA_SCRIPT_PATH="${SCRIPT_DIR}/${EXTRA_SCRIPT_NAME}"
    
    if [ -f "$EXTRA_SCRIPT_PATH" ]; then
        echo "-----------------------------------------"
        echo "检测到额外配置脚本: $EXTRA_SCRIPT_NAME"
        
        if [ ! -x "$EXTRA_SCRIPT_PATH" ]; then
            echo "检测到脚本缺少执行权限，正在授权 (chmod +x) ..."
            chmod +x "$EXTRA_SCRIPT_PATH"
        fi
        
        echo "正在执行额外指令..."
        source "$EXTRA_SCRIPT_PATH"
        
        if [ $? -ne 0 ]; then
            echo "警告: 额外脚本执行返回错误。将尝试继续运行主程序..."
        else
            echo "额外指令执行完毕。"
        fi
    fi
    
    # 4. 启动 main.py
    echo "-----------------------------------------"
    echo "准备就绪。正在启动 main.py ..."
    cd "$SCRIPT_DIR"
    # 注意：这里的 "$@" 将传递任何命令行参数给 Python
    $PYTHON_CMD "${SCRIPT_DIR}/main.py" "$@"
    
    echo "-----------------------------------------"
    echo "程序已退出。"
}

# 显示菜单
show_menu() {
    while true; do
        clear
        echo "================================================="
        echo "      ZIS Runner Helper - 启动脚本"
        echo "================================================="
        echo "  1. 自动启动程序 (Run Auto Mode)"
        echo "  2. 查看手动模式说明 (Manual Instructions)"
        echo "  0. 退出 (Exit)"
        echo "-------------------------------------------------"
        echo -n "请输入选项 [0-2]: "
        read -r choice
        case $choice in
            1)
                # 可以在这里提示输入额外参数，或者直接运行默认
                run_auto_start
                # 运行完后暂停一下，让用户看清楚输出
                echo "按 Enter 返回菜单..."
                read -r
            ;;
            2)
                show_manual_mode
                echo ""
                echo "按 Enter 返回菜单..."
                read -r
            ;;
            0)
                exit 0
            ;;
            *)
                echo "无效选项。"
                sleep 1
            ;;
        esac
    done
}

# --- 主逻辑入口 ---

check_environment

# 如果没有参数，显示菜单
if [ $# -eq 0 ]; then
    show_menu
else
    # 如果有参数
    if [ "$1" == "manual" ]; then
        show_manual_mode
        exit 0
    else
        # 如果参数不是 manual，假设是传递给 main.py 的参数（如 --port）
        # 直接运行自动模式
        run_auto_start "$@"
    fi
fi