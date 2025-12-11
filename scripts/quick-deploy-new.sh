#!/bin/bash
# RAG 项目快速部署脚本
# 支持本地推送 + 前端构建 + 服务器自动拉取重启

set -e

# 配置
REMOTE_USER="ljf"
REMOTE_HOST="34.180.100.55"
REMOTE_DIR="~/rag"
GIT_BRANCH="main"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========== RAG 快速部署 ==========${NC}"

# 0. 检查前端是否有更改，如果有则构建
FRONTEND_DIR="$PROJECT_DIR/admin_frontend"
FRONTEND_CHANGED=false

# 检查 admin_frontend/src 目录是否有更改
if [[ -n $(git status --porcelain "$FRONTEND_DIR/src" 2>/dev/null) ]]; then
    FRONTEND_CHANGED=true
fi

if [ "$FRONTEND_CHANGED" = true ]; then
    echo -e "${YELLOW}[0/5] 检测到前端更改，构建前端...${NC}"
    cd "$FRONTEND_DIR"
    npm run build --silent
    echo "✓ 前端构建完成"
    cd "$PROJECT_DIR"
else
    echo -e "${GREEN}[0/5] 前端无更改，跳过构建${NC}"
fi

# 1. 检查是否有未提交的更改
if [[ -n $(git status --porcelain) ]]; then
    echo -e "${YELLOW}[1/5] 提交本地更改...${NC}"

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
    echo -e "${GREEN}[1/5] 没有未提交的更改${NC}"
fi

# 2. 推送到远程
echo -e "${YELLOW}[2/5] 推送到 GitHub...${NC}"
git push origin $GIT_BRANCH
echo "✓ 推送成功"

# 3. 在服务器上拉取并重启
echo -e "${YELLOW}[3/5] 更新服务器...${NC}"
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

# 4. 如果前端有更改，上传 dist 目录
if [ "$FRONTEND_CHANGED" = true ]; then
    echo -e "${YELLOW}[4/5] 上传前端文件...${NC}"
    scp -r -o StrictHostKeyChecking=no "$FRONTEND_DIR/dist/"* ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/admin_frontend/dist/
    echo "✓ 前端上传完成"
else
    echo -e "${GREEN}[4/5] 前端无更改，跳过上传${NC}"
fi

# 5. 健康检查
echo -e "${YELLOW}[5/5] 远程健康检查...${NC}"
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
