#!/bin/bash
# 快速部署 - 仅更新服务器（不提交代码）
# 用法: ./scripts/quick-deploy.sh

set -e

SERVER="ljf@34.180.100.55"

echo "🚀 快速更新服务器..."

ssh $SERVER << 'ENDSSH'
    cd ~/rag
    git pull origin main
    sudo systemctl restart rag-api
    sleep 2
    sudo systemctl status rag-api --no-pager | head -10
ENDSSH

echo "✅ 更新完成: https://rag.litxczv.shop"
