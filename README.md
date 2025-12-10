# RAG Knowledge Base System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![React](https://img.shields.io/badge/React-19-61DAFB.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**企业级个人知识库 RAG 系统**

基于 Claude Haiku 的检索增强生成系统，支持多源数据索引、混合检索、Agent 工具调用和可视化管理后台。

[功能特性](#功能特性) • [快速开始](#快速开始) • [架构设计](#架构设计) • [API 文档](#api-文档) • [部署指南](#部署指南)

</div>

---

## 功能特性

### 🔍 智能检索
- **混合检索**: 向量检索 + BM25 关键词检索，融合多路召回
- **灵活嵌入**: 支持 OpenAI Embedding API 或本地 BGE-M3 模型
- **BGE-Reranker**: 可选的检索结果重排（可禁用以节省资源）
- **语义缓存**: 相似问题缓存，加速响应并节省 Token
- **查询改写**: LLM 驱动的查询扩展和优化

### 📚 多源数据索引
- **代码索引**: Python/JavaScript/TypeScript 等代码解析
- **文档索引**: Markdown、PDF、Word 文档处理
- **增量更新**: 基于文件哈希的智能增量索引
- **知识分组**: 支持项目/技能/笔记等分类管理

### 🤖 AI 问答
- **上下文问答**: 基于检索结果的智能问答
- **对话记忆**: 多轮对话历史管理
- **对话压缩**: 自动压缩历史对话，支持超长会话
- **流式响应**: Server-Sent Events 实时输出
- **引用高亮**: 答案来源溯源和高亮标注

### 🛠️ Agent 框架
- **工具调用**: 支持计算器、代码执行、网络搜索等工具
- **多步推理**: 自动规划和执行复杂任务
- **可扩展**: 灵活的工具注册机制

### 🖥️ 可视化管理
- **LLM 管理**: 多供应商/多模型配置
- **知识库管理**: 知识条目 CRUD 和分组
- **使用统计**: Token 消耗和调用日志
- **模型测试**: 在线测试 LLM 连通性

### 🔌 Claude Desktop 集成
- **MCP Server**: 通过 Model Context Protocol 无缝接入
- **uvx 安装**: 一行命令快速安装

---

## 技术栈

| 类别 | 技术 |
|------|------|
| **后端框架** | FastAPI + Uvicorn |
| **向量数据库** | Qdrant |
| **嵌入模型** | OpenAI Embedding API (支持第三方) / 本地 BGE-M3 可选 |
| **重排模型** | BGE-Reranker (BAAI/bge-reranker-base) / 可禁用 |
| **大语言模型** | Claude Haiku / OpenAI 兼容 API |
| **编排框架** | LangChain |
| **前端框架** | React 19 + Vite + Ant Design |
| **元数据存储** | MySQL |
| **认证** | JWT (python-jose) |

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+ (前端开发)
- Docker (运行 Qdrant)
- MySQL 8.0+ (后台管理)

### 1. 克隆项目

```bash
git clone https://github.com/fengshao1227/woerk_rag.git
cd woerk_rag
```

### 2. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装 Python 依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# LLM 配置
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-haiku-20241022
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_API_BASE=https://api.anthropic.com  # 可选，自定义 API 地址

# Qdrant 配置
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=              # 可选
QDRANT_COLLECTION_NAME=rag_knowledge

# MySQL 配置 (后台管理)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=rag_admin

# 嵌入模型（推荐使用 API 模式）
EMBEDDING_PROVIDER=api
EMBEDDING_API_KEY=your_embedding_api_key
EMBEDDING_API_BASE=https://api.openai.com
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536

# Reranker（可选，设为 0 禁用）
RERANKER_ENABLE=0
```

### 4. 启动服务

```bash
# 启动 Qdrant
docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant

# 启动 API 服务
uvicorn api.server:app --host 0.0.0.0 --port 8000

# 或使用脚本
./scripts/start_api.sh
```

### 5. 访问服务

- **API 文档**: http://localhost:8000/docs
- **后台管理**: http://localhost:8000/admin
- **健康检查**: http://localhost:8000/health

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                         客户端层                                 │
├─────────────┬─────────────┬─────────────┬─────────────────────┤
│   CLI 问答   │  REST API   │ MCP Server  │   Admin 前端         │
└──────┬──────┴──────┬──────┴──────┬──────┴──────────┬──────────┘
       │             │             │                  │
       └─────────────┴──────┬──────┴──────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────┐
│                      FastAPI 服务层                            │
├───────────────────────────┼───────────────────────────────────┤
│  /query (RAG问答)  │  /search (检索)  │  /admin/api/* (管理)  │
└───────────────────────────┼───────────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────┐
│                        核心模块                                │
├─────────────┬─────────────┼─────────────┬─────────────────────┤
│  QA Chain   │  Retriever  │   Indexer   │      Agent          │
│  (问答链)    │  (混合检索)  │   (索引器)   │    (工具调用)        │
└──────┬──────┴──────┬──────┴──────┬──────┴──────────┬──────────┘
       │             │             │                  │
┌──────┴─────────────┴─────────────┴──────────────────┴──────────┐
│                        存储层                                   │
├─────────────────────────┬───────────────────────────────────────┤
│   Qdrant (向量存储)      │         MySQL (元数据)                │
└─────────────────────────┴───────────────────────────────────────┘
```

---

## 目录结构

```
rag/
├── api/                    # FastAPI REST API 服务
│   └── server.py           # 主服务入口
├── admin/                  # 后台管理模块
│   ├── routes.py           # API 路由
│   ├── models.py           # SQLAlchemy 模型
│   ├── schemas.py          # Pydantic Schema
│   ├── auth.py             # JWT 认证
│   └── usage_logger.py     # 使用日志
├── admin_frontend/         # React 管理后台
│   ├── src/
│   │   ├── pages/          # 页面组件
│   │   ├── services/       # API 服务
│   │   └── App.jsx         # 应用入口
│   └── package.json
├── mcp_server/             # Claude Desktop MCP Server
│   └── server.py           # MCP 服务实现
├── qa/                     # 问答模块
│   ├── chain.py            # QA Chain 实现
│   ├── cli.py              # 命令行交互
│   └── conversation_summarizer.py  # 对话压缩
├── retriever/              # 检索模块
│   ├── vector_store.py     # 向量存储
│   ├── hybrid_search.py    # 混合检索
│   ├── reranker.py         # 结果重排
│   ├── keyword_index.py    # 关键词索引
│   ├── semantic_cache.py   # 语义缓存
│   └── query_rewriter.py   # 查询改写
├── indexer/                # 索引模块
│   ├── index_all.py        # 统一索引入口
│   ├── code_indexer.py     # 代码索引
│   ├── doc_indexer.py      # 文档索引
│   ├── chunker.py          # 文本切分
│   └── incremental.py      # 增量索引
├── agent/                  # Agent 框架
│   ├── core.py             # Agent 核心
│   └── tools.py            # 工具注册
├── utils/                  # 工具函数
│   ├── embeddings.py       # 嵌入模型
│   ├── llm.py              # LLM 客户端
│   ├── logger.py           # 日志配置
│   └── db_manager.py       # 数据库管理
├── eval/                   # 评估模块
│   └── evaluator.py        # 检索质量评估
├── scripts/                # 部署脚本
│   ├── deploy.sh           # 生产部署
│   ├── start_api.sh        # 启动 API
│   └── index_project.sh    # 索引项目
├── config.py               # 配置管理
├── requirements.txt        # Python 依赖
└── pyproject.toml          # MCP Server 打包配置
```

---

## API 文档

### 公开端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/` | 重定向到后台 |

### 认证端点 (需登录)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/query` | RAG 问答 |
| POST | `/query/stream` | 流式 RAG 问答 |
| POST | `/search` | 向量检索 |
| POST | `/add_knowledge` | 添加知识 |
| POST | `/agent` | Agent 工具调用 |
| POST | `/clear-history` | 清空对话历史 |

### 后台管理 API

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/admin/api/auth/login` | 登录 |
| GET | `/admin/api/auth/me` | 当前用户 |
| GET | `/admin/api/stats` | 统计数据 |
| CRUD | `/admin/api/providers` | LLM 供应商管理 |
| CRUD | `/admin/api/models` | LLM 模型管理 |
| CRUD | `/admin/api/knowledge` | 知识库管理 |
| GET | `/admin/api/usage/logs` | 使用日志 |
| GET | `/admin/api/usage/stats` | 使用统计 |
| POST | `/admin/api/models/test` | 测试模型 |

### 请求示例

#### RAG 问答

```bash
curl -X POST https://your-domain/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "question": "这个项目的主要功能是什么？",
    "top_k": 5,
    "use_history": true
  }'
```

#### 向量检索

```bash
curl -X POST https://your-domain/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "query": "嵌入模型",
    "top_k": 10,
    "score_threshold": 0.5
  }'
```

---

## Claude Desktop 集成

### 方式一: uvx 安装 (推荐)

```bash
uvx --from git+https://github.com/fengshao1227/woerk_rag.git rag-mcp
```

### 方式二: 配置 claude_desktop_config.json

```json
{
  "mcpServers": {
    "rag-knowledge": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/fengshao1227/woerk_rag.git",
        "rag-mcp"
      ],
      "env": {
        "RAG_API_URL": "https://your-domain",
        "RAG_API_TOKEN": "your_token"
      }
    }
  }
}
```

### MCP 工具列表

| 工具 | 说明 |
|------|------|
| `query` | RAG 问答查询 |
| `search` | 向量检索 |
| `add_knowledge` | 添加知识条目 |

---

## 部署指南

### 本地开发

```bash
# 启动后端
./scripts/start_api.sh

# 启动前端开发服务器
cd admin_frontend
npm install
npm run dev
```

### 生产部署

```bash
# 一键部署
./scripts/deploy.sh

# 构建前端
cd admin_frontend
npm run build
```

### Docker 部署

```bash
# 启动 Qdrant
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v ./qdrant_storage:/qdrant/storage \
  qdrant/qdrant

# 构建并运行 API
docker build -t rag-api .
docker run -d \
  --name rag-api \
  -p 8000:8000 \
  --env-file .env \
  rag-api
```

---

## 环境变量参考

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_PROVIDER` | LLM 提供商 (anthropic/openai) | `anthropic` |
| `LLM_MODEL` | 模型名称 | `claude-3-5-haiku-20241022` |
| `ANTHROPIC_API_KEY` | Anthropic API Key | - |
| `ANTHROPIC_API_BASE` | 自定义 API 地址 | 官方地址 |
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `OPENAI_API_BASE` | OpenAI API 地址 | - |
| `QDRANT_HOST` | Qdrant 地址 | `localhost` |
| `QDRANT_PORT` | Qdrant 端口 | `6333` |
| `QDRANT_API_KEY` | Qdrant 认证密钥 | - |
| `QDRANT_COLLECTION_NAME` | 集合名称 | `rag_knowledge` |
| `EMBEDDING_PROVIDER` | 嵌入模式 (api/local) | `api` |
| `EMBEDDING_API_KEY` | 嵌入 API Key | - |
| `EMBEDDING_API_BASE` | 嵌入 API 地址 | `https://api.openai.com` |
| `EMBEDDING_MODEL` | 嵌入模型 | `text-embedding-3-small` |
| `EMBEDDING_DIM` | 嵌入维度 | `1536` |
| `RERANKER_ENABLE` | 启用重排 | `0` |
| `RERANKER_MODEL` | 重排模型 | `BAAI/bge-reranker-base` |
| `MYSQL_HOST` | MySQL 主机 | `localhost` |
| `MYSQL_DATABASE` | 数据库名 | `rag_admin` |

---

## 开发指南

### 添加新工具 (Agent)

```python
# agent/tools.py
from agent import Tool

def my_tool(query: str) -> str:
    """工具描述"""
    return "result"

# 注册工具
registry.register(Tool(
    name="my_tool",
    description="工具描述",
    func=my_tool,
    parameters={"query": {"type": "string", "description": "查询参数"}}
))
```

### 添加新索引器

```python
# indexer/my_indexer.py
class MyIndexer:
    def index(self, path: str) -> List[Dict]:
        """索引逻辑"""
        pass
```

---

## 常见问题

### Q: 如何切换 LLM 提供商？

编辑 `.env` 文件，设置 `LLM_PROVIDER=openai` 并配置相应的 API Key。也可以通过后台管理界面动态配置多个供应商和模型。

### Q: 如何启用/禁用 Reranker？

在 `.env` 中设置 `RERANKER_ENABLE=1` 启用或 `RERANKER_ENABLE=0` 禁用。

### Q: 嵌入模型首次加载很慢？

如果使用本地模式 (`EMBEDDING_PROVIDER=local`)，首次加载需要下载模型文件（约 2GB）。推荐使用 API 模式 (`EMBEDDING_PROVIDER=api`) 调用第三方嵌入服务，无需下载模型。

### Q: 如何查看系统日志？

```bash
./scripts/logs.sh
# 或
tail -f logs/rag.log
```

---

## License

MIT License © 2024

---

## 致谢

- [LangChain](https://github.com/langchain-ai/langchain) - LLM 应用框架
- [Qdrant](https://qdrant.tech/) - 向量数据库
- [BGE](https://github.com/FlagOpen/FlagEmbedding) - 嵌入和重排模型
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [Ant Design](https://ant.design/) - UI 组件库
