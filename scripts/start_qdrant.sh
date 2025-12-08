#!/bin/bash
# 启动 Qdrant 向量数据库

echo "启动 Qdrant 向量数据库..."

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: 未安装 Docker"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Qdrant 容器是否已经运行
if docker ps | grep -q qdrant; then
    echo "Qdrant 已经在运行"
    docker ps | grep qdrant
    exit 0
fi

# 检查容器是否存在但未运行
if docker ps -a | grep -q qdrant; then
    echo "启动已存在的 Qdrant 容器..."
    docker start qdrant
else
    echo "创建并启动新的 Qdrant 容器..."
    docker run -d --name qdrant \
        -p 6333:6333 \
        -p 6334:6334 \
        -v $(pwd)/qdrant_storage:/qdrant/storage \
        qdrant/qdrant
fi

# 等待服务启动
echo "等待 Qdrant 服务启动..."
sleep 3

# 验证服务
if curl -s http://localhost:6333/ > /dev/null; then
    echo "✓ Qdrant 启动成功！"
    echo "API: http://localhost:6333"
    echo "Dashboard: http://localhost:6333/dashboard"
else
    echo "✗ Qdrant 启动失败"
    echo "请检查日志: docker logs qdrant"
    exit 1
fi
