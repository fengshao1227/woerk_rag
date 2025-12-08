#!/bin/bash
# RAG 项目部署脚本
# 用法: ./scripts/deploy.sh [commit message]

set -e

# 配置
SERVER="ljf@34.180.100.55"
REMOTE_DIR="~/rag"
BRANCH="main"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========== RAG 项目部署 ==========${NC}"

# 1. 检查是否有未提交的更改
if [[ -n $(git status --porcelain) ]]; then
    echo -e "${YELLOW}检测到未提交的更改...${NC}"

    # 获取 commit message
    if [ -n "$1" ]; then
        COMMIT_MSG="$1"
    else
        COMMIT_MSG="chore: 更新代码 $(date '+%Y-%m-%d %H:%M')"
    fi

    echo -e "${YELLOW}提交更改: ${COMMIT_MSG}${NC}"
    git add -A
    git commit -m "$COMMIT_MSG"
fi

# 2. 推送到 GitHub
echo -e "${YELLOW}推送到 GitHub...${NC}"
git push origin $BRANCH

# 3. 在服务器上拉取并重启
echo -e "${YELLOW}更新服务器...${NC}"
ssh $SERVER << 'ENDSSH'
    cd ~/rag

    echo "拉取最新代码..."
    git pull origin main

    echo "重启服务..."
    sudo systemctl restart rag-api

    sleep 3

    # 检查服务状态
    if sudo systemctl is-active --quiet rag-api; then
        echo "✅ 服务启动成功"
    else
        echo "❌ 服务启动失败"
        sudo journalctl -u rag-api -n 20 --no-pager
        exit 1
    fi
ENDSSH

echo -e "${GREEN}========== 部署完成 ==========${NC}"
echo -e "访问: https://rag.litxczv.shop"
