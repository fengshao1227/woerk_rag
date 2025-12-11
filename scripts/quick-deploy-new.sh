#!/bin/bash
# RAG 项目快速部署脚本
# 支持本地推送 + 服务器自动拉取重启

set -e

# 配置
REMOTE_USER="ljf"
REMOTE_HOST="34.180.100.55"
REMOTE_DIR="~/rag"
GIT_BRANCH="main"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========== RAG 快速部署 ==========${NC}"

# 1. 检查是否有未提交的更改
if [[ -n $(git status --porcelain) ]]; then
    echo -e "${YELLOW}[1/4] 提交本地更改...${NC}"

    # 获取 commit message
    if [ -n "$1" ]; then
        COMMIT_MSG="$1"
    else
        COMMIT_MSG="chore: 更新代码 $(date '+%Y-%m-%d %H:%M')"
    fi

    git add -A
    git commit -m "$COMMIT_MSG"
    echo "✓ 已提交: $COMMIT_MSG"
else
    echo -e "${GREEN}[1/4] 没有未提交的更改${NC}"
fi

# 2. 推送到远程
echo -e "${YELLOW}[2/4] 推送到 GitHub...${NC}"
git push origin $GIT_BRANCH
echo "✓ 推送成功"

# 3. 在服务器上拉取并重启
echo -e "${YELLOW}[3/4] 更新服务器...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "bash -s" << 'ENDSSH'
    set -e

    cd ~/rag
    echo "→ 拉取最新代码..."
    git pull origin main

    echo "→ 激活虚拟环境..."
    source venv/bin/activate

    echo "→ 执行优雅重启..."
    bash scripts/graceful-restart.sh

    echo "✓ 服务器更新完成"
ENDSSH

# 4. 健康检查
echo -e "${YELLOW}[4/4] 远程健康检查...${NC}"
sleep 2

if curl -f -s https://rag.litxczv.shop/health >/dev/null; then
    echo -e "${GREEN}✓ 服务运行正常${NC}"
    echo ""
    echo -e "${GREEN}========== 部署完成 ==========${NC}"
    echo "API: https://rag.litxczv.shop"
    echo "管理后台: https://rag.litxczv.shop/admin"
else
    echo -e "${RED}✗ 健康检查失败${NC}"
    echo "请登录服务器查看日志: ssh ${REMOTE_USER}@${REMOTE_HOST}"
    exit 1
fi
