#!/bin/bash
# RAG MCP Server 启动脚本 (HTTP/SSE 多窗口模式)
#
# 使用方法:
#   ./scripts/start-mcp-server.sh
#
# 启动后，在 Claude Code 中配置:
#   claude mcp add rag-knowledge --url http://127.0.0.1:8766/sse

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 配置
MCP_HOST="${MCP_HOST:-127.0.0.1}"
MCP_PORT="${MCP_PORT:-8766}"
PID_FILE="$PROJECT_DIR/.mcp-server.pid"
LOG_FILE="$PROJECT_DIR/mcp-server.log"

# 检查是否已运行
check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0  # 正在运行
        else
            rm -f "$PID_FILE"
        fi
    fi
    return 1  # 未运行
}

# 停止服务
stop_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}停止 MCP Server (PID: $PID)...${NC}"
            kill "$PID" 2>/dev/null || true
            sleep 1
            if ps -p "$PID" > /dev/null 2>&1; then
                kill -9 "$PID" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi
}

# 启动服务
start_server() {
    cd "$PROJECT_DIR"

    # 检查 API Key
    if [ -z "$RAG_API_KEY" ]; then
        # 尝试从 .env 读取
        if [ -f ".env" ]; then
            export $(grep -E '^RAG_API_KEY=' .env | xargs)
        fi
    fi

    if [ -z "$RAG_API_KEY" ]; then
        echo -e "${RED}错误: 未设置 RAG_API_KEY${NC}"
        echo ""
        echo "请设置环境变量:"
        echo "  export RAG_API_KEY=rag_sk_你的卡密"
        echo ""
        echo "或在 .env 文件中添加:"
        echo "  RAG_API_KEY=rag_sk_你的卡密"
        exit 1
    fi

    # 激活虚拟环境
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi

    echo -e "${GREEN}启动 RAG MCP Server (HTTP/SSE 模式)${NC}"
    echo -e "  监听地址: http://$MCP_HOST:$MCP_PORT"
    echo -e "  SSE 端点: http://$MCP_HOST:$MCP_PORT/sse"
    echo ""

    # 后台启动
    nohup python mcp_server/server.py --http > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    sleep 2

    if check_running; then
        echo -e "${GREEN}✓ MCP Server 启动成功 (PID: $(cat $PID_FILE))${NC}"
        echo ""
        echo -e "${YELLOW}Claude Code 配置命令:${NC}"
        echo "  claude mcp add rag-knowledge --url http://$MCP_HOST:$MCP_PORT/sse"
        echo ""
        echo -e "${YELLOW}查看日志:${NC}"
        echo "  tail -f $LOG_FILE"
    else
        echo -e "${RED}✗ MCP Server 启动失败${NC}"
        echo "查看日志: cat $LOG_FILE"
        exit 1
    fi
}

# 主逻辑
case "${1:-start}" in
    start)
        if check_running; then
            echo -e "${YELLOW}MCP Server 已在运行 (PID: $(cat $PID_FILE))${NC}"
            echo "使用 '$0 restart' 重启，或 '$0 stop' 停止"
            exit 0
        fi
        start_server
        ;;
    stop)
        stop_server
        echo -e "${GREEN}✓ MCP Server 已停止${NC}"
        ;;
    restart)
        stop_server
        sleep 1
        start_server
        ;;
    status)
        if check_running; then
            echo -e "${GREEN}MCP Server 正在运行 (PID: $(cat $PID_FILE))${NC}"
            echo "SSE 端点: http://$MCP_HOST:$MCP_PORT/sse"
        else
            echo -e "${YELLOW}MCP Server 未运行${NC}"
        fi
        ;;
    logs)
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo "日志文件不存在"
        fi
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
