#!/bin/bash
# RAG API 优雅重启脚本
# 解决端口占用问题,确保服务平滑切换

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
PORT=8000
MAX_WAIT=30
CHECK_INTERVAL=1
LOG_FILE="server.log"

echo -e "${GREEN}========== RAG API 优雅重启 ==========${NC}"

# 1. 查找旧进程
echo -e "${YELLOW}[1/6] 查找运行中的服务...${NC}"
OLD_PIDS=$(pgrep -f "uvicorn api.server:app" || true)

if [ -z "$OLD_PIDS" ]; then
    echo "✓ 没有运行中的服务"
else
    echo "找到运行中的进程: $OLD_PIDS"

    # 2. 优雅关闭 (SIGTERM)
    echo -e "${YELLOW}[2/6] 发送优雅关闭信号 (SIGTERM)...${NC}"
    for pid in $OLD_PIDS; do
        kill -TERM $pid 2>/dev/null || true
    done

    # 3. 等待进程退出
    echo -e "${YELLOW}[3/6] 等待进程退出...${NC}"
    WAITED=0
    while [ $WAITED -lt $MAX_WAIT ]; do
        # 检查进程是否还存在
        REMAINING=$(pgrep -f "uvicorn api.server:app" || true)
        if [ -z "$REMAINING" ]; then
            echo "✓ 所有进程已正常退出"
            break
        fi

        sleep $CHECK_INTERVAL
        WAITED=$((WAITED + CHECK_INTERVAL))
        echo -n "."
    done
    echo ""

    # 4. 强制杀死残留进程
    REMAINING=$(pgrep -f "uvicorn api.server:app" || true)
    if [ -n "$REMAINING" ]; then
        echo -e "${RED}⚠ 进程未正常退出,强制终止...${NC}"
        pkill -9 -f "uvicorn api.server:app" || true
        sleep 2
    fi
fi

# 5. 确认端口释放
echo -e "${YELLOW}[4/6] 确认端口 $PORT 已释放...${NC}"
WAITED=0
while [ $WAITED -lt 10 ]; do
    if ! lsof -i :$PORT >/dev/null 2>&1 && ! netstat -tlnp 2>/dev/null | grep -q ":$PORT "; then
        echo "✓ 端口 $PORT 已释放"
        break
    fi

    # 尝试释放端口
    fuser -k ${PORT}/tcp 2>/dev/null || true

    sleep 1
    WAITED=$((WAITED + 1))
done

# 最后检查
if lsof -i :$PORT >/dev/null 2>&1 || netstat -tlnp 2>/dev/null | grep -q ":$PORT "; then
    echo -e "${RED}✗ 端口 $PORT 仍被占用,无法启动服务${NC}"
    lsof -i :$PORT 2>/dev/null || netstat -tlnp 2>/dev/null | grep ":$PORT"
    exit 1
fi

# 6. 启动新服务
echo -e "${YELLOW}[5/6] 启动新服务...${NC}"

# 清空旧日志
> $LOG_FILE

# 启动服务
nohup python -m uvicorn api.server:app \
    --host 0.0.0.0 \
    --port $PORT \
    --timeout-keep-alive 120 \
    --workers 1 \
    > $LOG_FILE 2>&1 &

NEW_PID=$!
echo "新进程 PID: $NEW_PID"

# 7. 健康检查
echo -e "${YELLOW}[6/6] 等待服务启动...${NC}"
sleep 5

WAITED=0
MAX_STARTUP_WAIT=30
while [ $WAITED -lt $MAX_STARTUP_WAIT ]; do
    if curl -f -s http://localhost:$PORT/health >/dev/null 2>&1; then
        echo -e "${GREEN}✓ 服务启动成功!${NC}"
        echo ""
        echo "进程 PID: $NEW_PID"
        echo "日志文件: $LOG_FILE"
        echo "健康检查: http://localhost:$PORT/health"
        echo ""

        # 显示最近的日志
        echo -e "${GREEN}========== 最近日志 ==========${NC}"
        tail -10 $LOG_FILE

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
echo -e "${RED}========== 错误日志 ==========${NC}"
tail -30 $LOG_FILE
exit 1
