#!/bin/bash
# 索引整个项目

set -e

cd "$(dirname "$0")/.."

echo "======================================"
echo "RAG 项目索引脚本"
echo "======================================"

# 检查 Python 依赖
echo "检查 Python 依赖..."
if ! python -c "import qdrant_client" 2>/dev/null; then
    echo "错误: 未安装必需的 Python 包"
    echo "请运行: pip install -r requirements.txt"
    exit 1
fi

# 检查环境变量
if [ ! -f ".env" ]; then
    echo "错误: .env 文件不存在"
    echo "请复制 .env.example 到 .env 并配置"
    exit 1
fi

# 检查 Qdrant 是否运行
echo "检查 Qdrant 服务..."
if ! curl -s http://localhost:6333/ > /dev/null; then
    echo "错误: Qdrant 服务未运行"
    echo "请运行: ./scripts/start_qdrant.sh"
    exit 1
fi

# 开始索引
echo ""
echo "开始索引项目..."
echo "项目路径: $(pwd)/.."
echo ""

python -m rag.indexer.index_all

echo ""
echo "======================================"
echo "索引完成！"
echo "======================================"
echo ""
echo "下一步："
echo "1. 测试 CLI: python -m rag.qa.cli"
echo "2. 启动 API: uvicorn rag.api.server:app --reload"
