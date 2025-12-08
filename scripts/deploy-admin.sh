#!/bin/bash
# Admin 后台管理系统部署脚本
# 用法: ./scripts/deploy-admin.sh [commit message]

set -e

# 配置
SERVER="ljf@34.180.100.55"
REMOTE_DIR="~/rag"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ADMIN_FRONTEND_DIR="$LOCAL_DIR/admin_frontend"
BRANCH="main"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========== Admin 后台部署 ==========${NC}"

# 1. 检查 node/npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}错误: npm 未安装${NC}"
    exit 1
fi

# 2. 构建前端
echo -e "${YELLOW}[1/6] 构建前端...${NC}"
cd "$ADMIN_FRONTEND_DIR"
npm run build

if [ ! -d "dist" ]; then
    echo -e "${RED}错误: 构建失败，dist 目录不存在${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 前端构建完成${NC}"

# 3. 提交代码（如果有更改）
cd "$LOCAL_DIR"
if [[ -n $(git status --porcelain) ]]; then
    echo -e "${YELLOW}[2/6] 提交代码更改...${NC}"

    if [ -n "$1" ]; then
        COMMIT_MSG="$1"
    else
        COMMIT_MSG="chore: 更新 admin 后台 $(date '+%Y-%m-%d %H:%M')"
    fi

    git add -A
    git commit -m "$COMMIT_MSG"
    echo -e "${GREEN}✓ 代码已提交${NC}"
else
    echo -e "${BLUE}[2/6] 跳过: 无代码更改${NC}"
fi

# 4. 推送到 GitHub
echo -e "${YELLOW}[3/6] 推送到 GitHub...${NC}"
git push origin $BRANCH
echo -e "${GREEN}✓ 已推送到 GitHub${NC}"

# 5. 备份远程旧版本并上传新版本
echo -e "${YELLOW}[4/6] 备份远程旧版本...${NC}"
BACKUP_NAME="dist_backup_$(date '+%Y%m%d_%H%M%S')"
ssh $SERVER << ENDSSH
    cd $REMOTE_DIR/admin_frontend

    # 备份旧版本（如果存在）
    if [ -d "dist" ]; then
        echo "备份旧版本到 $BACKUP_NAME..."
        mv dist $BACKUP_NAME
        echo "✓ 已备份到 $BACKUP_NAME"
    fi

    # 清理超过 7 天的备份
    find . -maxdepth 1 -name "dist_backup_*" -type d -mtime +7 -exec rm -rf {} \; 2>/dev/null || true
ENDSSH
echo -e "${GREEN}✓ 远程备份完成${NC}"

echo -e "${YELLOW}[5/6] 上传新版本...${NC}"
scp -r "$ADMIN_FRONTEND_DIR/dist" "$SERVER:$REMOTE_DIR/admin_frontend/"
echo -e "${GREEN}✓ 上传完成${NC}"

# 6. 拉取代码并重启服务
echo -e "${YELLOW}[6/6] 更新服务器并重启服务...${NC}"
# 拉取代码
ssh $SERVER "cd $REMOTE_DIR && git pull origin main"

# 重启服务（使用 bash -c 和完全分离输出避免 SSH 挂起）
ssh $SERVER "fuser -k 8000/tcp 2>/dev/null || true"
sleep 2
ssh -f $SERVER "cd $REMOTE_DIR && source venv/bin/activate && nohup python api/server.py > server.log 2>&1 < /dev/null &"
echo -e "${GREEN}✓ 服务启动命令已发送${NC}"

# 等待服务启动
echo "等待服务启动..."
sleep 8

# 检查服务状态（最多重试 3 次）
for i in 1 2 3; do
    if curl -s --max-time 5 https://rag.litxczv.shop/health > /dev/null; then
        echo -e "${GREEN}✓ 服务启动成功${NC}"
        break
    else
        if [ $i -lt 3 ]; then
            echo "重试中... ($i/3)"
            sleep 3
        else
            echo -e "${YELLOW}⚠ 服务可能未正常启动，请手动检查${NC}"
        fi
    fi
done

# 7. 清理本地构建产物
echo -e "${YELLOW}清理本地构建产物...${NC}"
rm -rf "$ADMIN_FRONTEND_DIR/dist"
echo -e "${GREEN}✓ 本地 dist 已清理${NC}"

echo ""
echo -e "${GREEN}========== 部署完成 ==========${NC}"
echo -e "后台地址: ${BLUE}https://rag.litxczv.shop/admin${NC}"
echo -e "账号: admin / admin123"
echo ""
echo -e "${YELLOW}远程备份位置: $REMOTE_DIR/admin_frontend/$BACKUP_NAME${NC}"
