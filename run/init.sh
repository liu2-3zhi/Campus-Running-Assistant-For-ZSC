#!/bin/bash
# 获取脚本文件所在的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
touch $SCRIPT_DIR/ssh
touch $SCRIPT_DIR/config.ini
mkdir -p $SCRIPT_DIR/cache
mkdir -p $SCRIPT_DIR/logs
touch $SCRIPT_DIR/messages.json
touch $SCRIPT_DIR/permissions.json
touch $SCRIPT_DIR/reminders.json
mkdir -p $SCRIPT_DIR/background_tasks
mkdir -p $SCRIPT_DIR/school_accounts
mkdir -p $SCRIPT_DIR/sessions
mkdir -p $SCRIPT_DIR/tokens
mkdir -p $SCRIPT_DIR/system_accounts
mkdir -p $SCRIPT_DIR/payment_orders
touch $SCRIPT_DIR/payment_methods.json
mkdir -p $SCRIPT_DIR/configs