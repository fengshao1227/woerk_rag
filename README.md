# 个人/项目知识库 RAG 系统

基于 Claude 3.5 Haiku 4.5 的个人知识库检索增强生成系统。

## 功能特性

- 📚 多源数据索引：代码库、Markdown文档、PDF、知识笔记
- 🔍 混合检索：向量检索 + 关键词检索
- 💬 智能问答：基于 Claude Haiku 4.5 的上下文问答
- 🔄 增量更新：支持代码库和文档的增量索引
- 📊 评估监控：检索质量评估和日志记录

## 技术栈

- **嵌入模型**: BGE-M3 (BAAI/bge-m3)
- **向量库**: Qdrant (本地)
- **编排框架**: LangChain
- **大模型**: Claude 3.5 Haiku 4.5 (Anthropic API)
- **存储**: SQLite (元数据)

## 快速开始

### 1. 安装依赖

```bash
cd rag
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并填写：

```bash
cp .env.example .env
```

需要配置：
- `ANTHROPIC_API_KEY`: Claude API 密钥
- `QDRANT_HOST`: Qdrant 服务地址（默认 localhost:6333）
- `PROJECT_ROOT`: 项目根目录路径

### 3. 启动 Qdrant（如果未运行）

```bash
docker run -p 6333:6333 qdrant/qdrant
```

### 4. 索引数据

```bash
# 索引整个项目代码库
python -m rag.indexer.index_code --path /path/to/project

# 索引文档
python -m rag.indexer.index_docs --path /path/to/docs

# 索引所有（代码+文档）
python -m rag.indexer.index_all
```

### 5. 启动问答服务

```bash
# CLI 模式
python -m rag.qa.cli

# API 服务模式
uvicorn rag.api.server:app --host 0.0.0.0 --port 8000
```

## 目录结构

```
rag/
├── indexer/          # 数据索引模块
│   ├── code_indexer.py    # 代码索引
│   ├── doc_indexer.py     # 文档索引
│   └── chunker.py         # 文本切分
├── retriever/        # 检索模块
│   ├── vector_store.py    # 向量检索
│   └── hybrid_search.py   # 混合检索
├── qa/               # 问答模块
│   ├── cli.py             # CLI 交互
│   └── chain.py           # LangChain 链
├── api/              # API 服务
│   └── server.py          # FastAPI 服务
├── utils/            # 工具函数
│   ├── embeddings.py      # 嵌入模型
│   └── logger.py          # 日志
└── config.py         # 配置管理
```

## 使用示例

### CLI 问答

```bash
$ python -m rag.qa.cli
> 如何实现工作流审批？
[检索到 3 个相关片段]
[回答] 工作流审批通过 ApprovalProcessService 实现...
```

### API 调用

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "如何实现工作流审批？", "top_k": 5}'
```

## 开发计划

- [x] Phase 1: 基础 PoC（当前阶段）
- [ ] Phase 2: 增强功能（重排、混合检索、Obsidian/Notion 同步）
- [ ] Phase 3: 生产化（服务化、定时重建、权限过滤）
