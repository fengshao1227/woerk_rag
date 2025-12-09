#!/bin/bash
# 快速部署 - 仅更新服务器（不提交代码）
# 用法: ./scripts/quick-deploy.sh

set -e

# 加载配置
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

check_config

echo "🚀 快速更新服务器 ($SERVER)..."

ssh $SERVER << ENDSSH
    cd $REMOTE_DIR
    git pull origin $GIT_BRANCH
    sudo systemctl restart rag-api
    sleep 2
    sudo systemctl status rag-api --no-pager | head -10
ENDSSH

echo "✅ 更新完成: $API_URL"
