#!/bin/bash
# 查看服务器日志
# 用法: ./scripts/logs.sh [行数]

SERVER="ljf@34.180.100.55"
LINES=${1:-50}

echo "📋 RAG API 日志 (最近 $LINES 行)..."
ssh $SERVER "sudo journalctl -u rag-api -n $LINES --no-pager"
