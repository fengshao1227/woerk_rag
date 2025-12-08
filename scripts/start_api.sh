#!/bin/bash
# 启动 RAG API 服务

set -e

cd "$(dirname "$0")/.."

echo "======================================"
echo "启动 RAG API 服务"
echo "======================================"

# 检查环境
if [ ! -f ".env" ]; then
    echo "错误: .env 文件不存在"
    exit 1
fi

if ! curl -s http://localhost:6333/ > /dev/null; then
    echo "警告: Qdrant 服务似乎未运行"
    echo "请确保 Qdrant 正在运行"
fi

echo ""
echo "启动服务..."
echo "API 地址: http://localhost:8000"
echo "API 文档: http://localhost:8000/docs"
echo ""

uvicorn rag.api.server:app --host 0.0.0.0 --port 8000 --reload
