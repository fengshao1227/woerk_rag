#!/bin/bash
# ============================================
# RAG 项目部署配置文件
# 所有部署脚本共享此配置
# ============================================

# 服务器连接配置
SERVER_USER="ljf"
SERVER_HOST="34.180.100.55"
SERVER="${SERVER_USER}@${SERVER_HOST}"

# 远程路径配置
REMOTE_DIR="~/rag"
REMOTE_VENV="venv"

# Git 配置
GIT_BRANCH="main"

# 服务配置
API_PORT="8000"
API_URL="https://rag.litxczv.shop"
ADMIN_URL="${API_URL}/admin"

# 服务启动等待时间(秒)
STARTUP_WAIT=18
HEALTH_CHECK_TIMEOUT=10
HEALTH_CHECK_RETRIES=3

# SSH 选项 (可选)
# SSH_KEY="~/.ssh/id_rsa"
# SSH_OPTIONS="-o StrictHostKeyChecking=no"

# ============================================
# 以下为辅助函数，无需修改
# ============================================

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 输出函数
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查配置是否有效
check_config() {
    if [ -z "$SERVER_HOST" ] || [ "$SERVER_HOST" = "YOUR_SERVER_IP" ]; then
        log_error "请先配置 scripts/config.sh 中的服务器地址"
        log_info "编辑 scripts/config.sh，设置 SERVER_HOST"
        exit 1
    fi
}

# SSH 连接测试
test_ssh_connection() {
    log_info "测试 SSH 连接..."
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SERVER" "echo ok" &>/dev/null; then
        log_success "SSH 连接正常"
        return 0
    else
        log_error "无法连接到 $SERVER"
        log_info "请检查:"
        log_info "  1. 服务器地址是否正确"
        log_info "  2. SSH 密钥是否配置"
        log_info "  3. 网络是否畅通"
        return 1
    fi
}

# 健康检查
health_check() {
    local url="${1:-$API_URL/health}"
    local retries="${2:-$HEALTH_CHECK_RETRIES}"

    for i in $(seq 1 $retries); do
        if curl -s --max-time $HEALTH_CHECK_TIMEOUT "$url" > /dev/null; then
            log_success "服务运行正常"
            return 0
        else
            if [ $i -lt $retries ]; then
                log_warn "重试中... ($i/$retries)"
                sleep 5
            fi
        fi
    done
    log_warn "服务可能未正常启动，请手动检查"
    return 1
}

# 显示当前配置
show_config() {
    echo ""
    echo "========== 当前配置 =========="
    echo "服务器: $SERVER"
    echo "远程目录: $REMOTE_DIR"
    echo "Git 分支: $GIT_BRANCH"
    echo "API 地址: $API_URL"
    echo "后台地址: $ADMIN_URL"
    echo "==============================="
    echo ""
}
