#!/bin/bash
# RAG API 优雅重启脚本
# 使用 systemd 管理服务，避免端口冲突

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
PORT=8000
LOG_FILE="server.log"
SERVICE_NAME="rag-api.service"

echo -e "${GREEN}========== RAG API 优雅重启 ===========${NC}"

# 检查是否有 systemd 服务
if systemctl is-enabled $SERVICE_NAME >/dev/null 2>&1; then
    echo -e "${YELLOW}[1/3] 使用 systemd 重启服务...${NC}"

    # 使用 systemd 重启（会自动处理端口释放）
    sudo systemctl restart $SERVICE_NAME

    echo -e "${YELLOW}[2/3] 等待服务启动...${NC}"
    sleep 3

    # 健康检查
    echo -e "${YELLOW}[3/3] 健康检查...${NC}"
    WAITED=0
    MAX_WAIT=30
    while [ $WAITED -lt $MAX_WAIT ]; do
        if curl -f -s http://localhost:$PORT/health >/dev/null 2>&1; then
            echo -e "${GREEN}✓ 服务启动成功!${NC}"
            echo ""

            # 显示服务状态
            systemctl status $SERVICE_NAME --no-pager -l | head -15
            echo ""

            # 显示最近日志
            echo -e "${GREEN}========== 最近日志 ===========${NC}"
            tail -10 $LOG_FILE 2>/dev/null || journalctl -u $SERVICE_NAME -n 10 --no-pager

            exit 0
        fi

        sleep 2
        WAITED=$((WAITED + 2))
        echo -n "."
    done
    echo ""

    # 启动失败
    echo -e "${RED}✗ 服务启动失败${NC}"
    echo ""
    echo -e "${RED}========== 错误日志 ===========${NC}"
    journalctl -u $SERVICE_NAME -n 30 --no-pager
    exit 1
else
    # 回退到手动模式（本地开发环境）
    echo -e "${YELLOW}未检测到 systemd 服务，使用手动模式...${NC}"

    # 1. 查找并关闭旧进程
    echo -e "${YELLOW}[1/4] 关闭旧服务...${NC}"
    pkill -f "uvicorn.*api.server:app" || true
    pkill -f "gunicorn.*api.server:app" || true
    sleep 3

    # 2. 确认端口释放
    echo -e "${YELLOW}[2/4] 确认端口释放...${NC}"
    WAITED=0
    while [ $WAITED -lt 10 ]; do
        if ! lsof -i :$PORT >/dev/null 2>&1; then
            echo "✓ 端口 $PORT 已释放"
            break
        fi
        fuser -k ${PORT}/tcp 2>/dev/null || true
        sleep 1
        WAITED=$((WAITED + 1))
    done

    # 3. 启动新服务
    echo -e "${YELLOW}[3/4] 启动新服务...${NC}"
    > $LOG_FILE

    cd "$(dirname "$0")/.."
    source venv/bin/activate

    nohup uvicorn api.server:app \
        --host 0.0.0.0 \
        --port $PORT \
        --workers 2 \
        --timeout-keep-alive 120 \
        > $LOG_FILE 2>&1 &

    NEW_PID=$!
    echo "新进程 PID: $NEW_PID"

    # 4. 健康检查
    echo -e "${YELLOW}[4/4] 等待服务启动...${NC}"
    sleep 5

    WAITED=0
    while [ $WAITED -lt 30 ]; do
        if curl -f -s http://localhost:$PORT/health >/dev/null 2>&1; then
            echo -e "${GREEN}✓ 服务启动成功!${NC}"
            tail -10 $LOG_FILE
            exit 0
        fi
        sleep 2
        WAITED=$((WAITED + 2))
        echo -n "."
    done
    echo ""

    echo -e "${RED}✗ 服务启动失败${NC}"
    tail -30 $LOG_FILE
    exit 1
fi
