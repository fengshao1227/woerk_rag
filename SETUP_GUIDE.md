# RAG 系统部署指南

## 1. 环境准备

### 1.1 安装 Python 依赖

```bash
cd /Users/li/Desktop/work7_8/www/bv-fm-ssr/rag
pip install -r requirements.txt
```

### 1.2 启动 Qdrant 向量数据库

使用 Docker 启动（推荐）：

```bash
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

或者安装本地版本：

```bash
# macOS
brew install qdrant

# 启动服务
qdrant
```

验证 Qdrant 是否运行：

```bash
curl http://localhost:6333/
```

### 1.3 配置环境变量

```bash
cd /Users/li/Desktop/work7_8/www/bv-fm-ssr/rag
cp .env.example .env
```

编辑 `.env` 文件，填入您的配置：

```bash
# 必须配置：Claude API Key
ANTHROPIC_API_KEY=sk-ant-xxx

# 其他配置保持默认即可
```

## 2. 数据索引

### 2.1 索引整个项目（代码+文档）

```bash
cd /Users/li/Desktop/work7_8/www/bv-fm-ssr
python -m rag.indexer.index_all
```

这将索引：
- PHP 代码文件
- JavaScript/Vue 文件
- Markdown 文档
- 其他配置的文件类型

预计时间：5-15 分钟（取决于项目大小）

### 2.2 仅索引代码

```bash
python -m rag.indexer.code_indexer
```

### 2.3 仅索引文档

```bash
python -m rag.indexer.doc_indexer
```

### 2.4 增量更新

如果修改了代码或文档，可以重新运行索引命令，系统会自动更新。

## 3. 使用方式

### 3.1 CLI 交互模式（推荐入门）

```bash
cd /Users/li/Desktop/work7_8/www/bv-fm-ssr
python -m rag.qa.cli
```

交互示例：

```
> 如何实现工作流审批？
[回答]
工作流审批通过 ApprovalProcessService 实现...

[参考来源 (3 个)]
1. app/Services/V2/ApprovalProcessService.php (相似度: 0.892)
   ...

> clear  # 清空对话历史
对话历史已清空

> quit  # 退出
再见！
```

### 3.2 API 服务模式

启动 API 服务：

```bash
cd /Users/li/Desktop/work7_8/www/bv-fm-ssr
uvicorn rag.api.server:app --host 0.0.0.0 --port 8000 --reload
```

访问 API 文档：http://localhost:8000/docs

调用示例：

```bash
# 问答
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "如何实现工作流审批？",
    "top_k": 5,
    "use_history": true
  }'

# 向量检索
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "工作流审批",
    "top_k": 5,
    "filters": {"type": "code", "language": "php"}
  }'

# 清空对话历史
curl -X POST http://localhost:8000/clear_history
```

## 4. 高级配置

### 4.1 调整检索参数

编辑 `.env` 文件：

```bash
# 返回结果数量
TOP_K=5

# 文本切分大小
CHUNK_SIZE=512
CHUNK_OVERLAP=50

# 嵌入模型（可选其他模型）
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cpu  # 或 cuda（如果有 GPU）
```

### 4.2 过滤特定类型内容

在查询时使用过滤器：

```python
from rag.qa.chain import QAChatChain

chain = QAChatChain()

# 仅搜索 PHP 代码
result = chain.query(
    "如何实现工作流？",
    filters={"type": "code", "language": "php"}
)

# 仅搜索文档
result = chain.query(
    "项目架构是什么？",
    filters={"type": "document"}
)
```

### 4.3 调整 Claude 模型参数

编辑 `rag/qa/chain.py`：

```python
self.llm = ChatAnthropic(
    anthropic_api_key=ANTHROPIC_API_KEY,
    model_name=ANTHROPIC_MODEL,
    temperature=0.7,  # 调整创造性（0-1）
    max_tokens=4096   # 调整最大输出长度
)
```

## 5. 常见问题

### Q1: 索引时报错 "ANTHROPIC_API_KEY 未配置"

**解决**：确保 `.env` 文件中配置了正确的 API Key。

### Q2: 无法连接到 Qdrant

**解决**：
1. 检查 Qdrant 是否运行：`curl http://localhost:6333/`
2. 检查 `.env` 中的 `QDRANT_HOST` 和 `QDRANT_PORT` 配置

### Q3: 索引速度很慢

**解决**：
1. 使用 GPU 加速：设置 `EMBEDDING_DEVICE=cuda`
2. 调整 `.env` 中的 `IGNORE_PATTERNS`，排除不需要的文件
3. 减小 `CHUNK_SIZE` 值

### Q4: 回答质量不好

**解决**：
1. 增加 `TOP_K` 值，检索更多相关内容
2. 调整 `CHUNK_SIZE`，使切分更合理
3. 使用 `filters` 过滤无关内容
4. 清空对话历史重新提问

### Q5: 内存不足

**解决**：
1. 使用更小的嵌入模型
2. 减小 `CHUNK_SIZE`
3. 分批索引：先索引部分文件，测试后再索引全部

## 6. 性能优化

### 6.1 使用 GPU 加速（如果可用）

```bash
# 安装 CUDA 版本的 PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 修改 .env
EMBEDDING_DEVICE=cuda
```

### 6.2 启用混合检索

目前实现了混合检索框架，但关键词索引需要额外构建。可以在索引时同步构建。

### 6.3 批量索引优化

对于大型项目，可以使用多进程索引（需要额外实现）。

## 7. 监控与日志

### 查看日志

```bash
tail -f /Users/li/Desktop/work7_8/www/bv-fm-ssr/rag/logs/rag.log
```

### 调整日志级别

修改 `.env`：

```bash
LOG_LEVEL=DEBUG  # 可选：DEBUG, INFO, WARNING, ERROR
```

## 8. 下一步计划

- [ ] 实现重排序（Reranker）
- [ ] 集成 Obsidian/Notion 同步
- [ ] 添加评估指标和监控
- [ ] 实现定时增量索引
- [ ] 添加权限控制
- [ ] 前端 UI 界面
