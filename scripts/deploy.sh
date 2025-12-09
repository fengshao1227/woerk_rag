#!/bin/bash
# RAG 项目部署脚本
# 用法: ./scripts/deploy.sh [commit message]

set -e

# 加载配置
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

check_config

show_config
echo -e "${GREEN}========== RAG 项目部署 ==========${NC}"

# 1. 检查是否有未提交的更改
if [[ -n $(git status --porcelain) ]]; then
    log_warn "检测到未提交的更改..."

    # 获取 commit message
    if [ -n "$1" ]; then
        COMMIT_MSG="$1"
    else
        COMMIT_MSG="chore: 更新代码 $(date '+%Y-%m-%d %H:%M')"
    fi

    log_info "提交更改: ${COMMIT_MSG}"
    git add -A
    git commit -m "$COMMIT_MSG"
fi

# 2. 推送到 GitHub
log_info "推送到 GitHub..."
git push origin $GIT_BRANCH

# 3. 在服务器上拉取并重启
log_info "更新服务器..."
ssh $SERVER << ENDSSH
    cd $REMOTE_DIR

    echo "拉取最新代码..."
    git pull origin $GIT_BRANCH

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
echo -e "访问: $API_URL"
