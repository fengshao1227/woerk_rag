# RAG Knowledge Base System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![React](https://img.shields.io/badge/React-19-61DAFB.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**企业级个人知识库 RAG 系统**

基于 Claude/OpenAI 的检索增强生成系统，支持多源数据索引、混合检索、异步任务队列、Agent 工具调用和可视化管理后台。

[功能特性](#功能特性) • [快速开始](#快速开始) • [架构设计](#架构设计) • [API 文档](#api-文档) • [部署指南](#部署指南)

</div>

---

## 功能特性

### 🔍 智能检索
- **混合检索**: 向量检索 + BM25 关键词检索，融合多路召回
- **灵活嵌入**: 支持 OpenAI Embedding API 或本地 BGE-M3 模型
- **嵌入热重载**: 后台切换嵌入供应商无需重启服务
- **BGE-Reranker**: 可选的检索结果重排（可禁用以节省资源）
- **语义缓存**: 相似问题缓存，加速响应并节省 Token
- **查询改写**: LLM 驱动的查询扩展和优化

### 📚 多源数据索引
- **代码索引**: Python/JavaScript/TypeScript 等代码解析
- **文档索引**: Markdown、PDF、Word 文档处理
- **增量更新**: 基于文件哈希的智能增量索引
- **定时索引**: 后台自动定时更新索引
- **知识分组**: 支持项目/技能/笔记等分类管理

### 🤖 AI 问答
- **上下文问答**: 基于检索结果的智能问答
- **对话记忆**: 多轮对话历史管理
- **对话压缩**: 自动压缩历史对话，支持超长会话
- **流式响应**: Server-Sent Events 实时输出
- **引用高亮**: 答案来源溯源和高亮标注

### 🛠️ Agent 框架
- **工具调用**: 支持计算器、代码执行、网络搜索等工具
- **多步推理**: ReAct 模式自动规划和执行复杂任务
- **可扩展**: 灵活的工具注册机制

### ⚡ 异步任务队列 (新功能)
- **非阻塞添加**: 知识添加请求立即返回，后台异步处理
- **多 Worker**: 3 个并发 Worker 处理任务队列
- **状态追踪**: 支持查询任务处理状态和历史
- **高并发**: 支持大量并发知识添加请求

### 🖥️ 可视化管理
- **LLM 管理**: 多供应商/多模型配置，支持 Anthropic/OpenAI 格式
- **嵌入管理**: 嵌入模型供应商管理和热切换
- **知识库管理**: 知识条目 CRUD 和分组管理
- **使用统计**: Token 消耗和调用日志
- **模型测试**: 在线测试 LLM/嵌入模型连通性

### 🔌 Claude Desktop 集成
- **MCP Server**: 通过 Model Context Protocol 无缝接入
- **API Key 认证**: 使用卡密认证，无需暴露管理员密码
- **uvx 安装**: 一行命令快速安装
- **分组过滤**: 支持按知识分组检索
- **多会话支持**: HTTP/SSE 模式支持多客户端并发

---

## 技术栈

| 类别 | 技术 |
|------|------|
| **后端框架** | FastAPI + Uvicorn |
| **向量数据库** | Qdrant |
| **嵌入模型** | OpenAI Embedding API (支持第三方) / 本地 BGE-M3 可选 |
| **重排模型** | BGE-Reranker (BAAI/bge-reranker-base) / 可禁用 |
| **大语言模型** | Claude Haiku/Sonnet / OpenAI 兼容 API |
| **编排框架** | LangChain |
| **前端框架** | React 19 + Vite + Ant Design + TailwindCSS |
| **元数据存储** | MySQL |
| **认证** | JWT (python-jose) |
| **任务队列** | asyncio.Queue (内存队列) |

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

### 4. 初始化数据库

```sql
-- 创建数据库
CREATE DATABASE IF NOT EXISTS rag_admin DEFAULT CHARACTER SET utf8mb4;

-- 运行初始化脚本（包含用户表、供应商表、知识表等）
-- 表结构会在首次启动时自动创建
```

### 5. 启动服务

```bash
# 启动 Qdrant
docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant

# 启动 API 服务
uvicorn api.server:app --host 0.0.0.0 --port 8000

# 或使用脚本
./scripts/start_api.sh
```

### 6. 访问服务

- **API 文档**: http://localhost:8000/docs
- **后台管理**: http://localhost:8000/admin
- **健康检查**: http://localhost:8000/health

**默认管理员账户**: `admin` / `admin123`

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
│  /agent (工具调用) │  /add_knowledge (异步入队)               │
└───────────────────────────┼───────────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────┐
│                        核心模块                                │
├─────────────┬─────────────┼─────────────┬─────────────────────┤
│  QA Chain   │  Retriever  │   Indexer   │      Agent          │
│  (问答链)    │  (混合检索)  │   (索引器)   │    (工具调用)        │
├─────────────┴─────────────┴─────────────┴─────────────────────┤
│                      Task Queue (异步任务队列)                  │
│                    3 Workers 并发处理知识添加                   │
└───────────────────────────┼───────────────────────────────────┘
                            │
┌───────────────────────────┼───────────────────────────────────┐
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
│   ├── embeddings.py       # 嵌入模型（支持热重载）
│   ├── llm.py              # LLM 客户端
│   ├── logger.py           # 日志配置
│   ├── scheduler.py        # 定时索引调度器
│   └── task_queue.py       # 异步任务队列
├── eval/                   # 评估模块
│   └── evaluator.py        # 检索质量评估
├── scripts/                # 部署脚本
│   ├── deploy.sh           # 生产部署
│   ├── quick-deploy-new.sh # 快速部署
│   ├── graceful-restart.sh # 优雅重启
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
| POST | `/add_knowledge` | 添加知识（异步，立即返回 task_id） |
| GET | `/add_knowledge/status/{task_id}` | 查询知识添加任务状态 |
| GET | `/add_knowledge/tasks` | 列出知识添加任务列表 |
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
| CRUD | `/admin/api/embedding-providers` | 嵌入供应商管理 |
| CRUD | `/admin/api/knowledge` | 知识库管理 |
| CRUD | `/admin/api/groups` | 知识分组管理 |
| CRUD | `/admin/api/api-keys` | MCP 卡密管理 |
| POST | `/mcp/verify` | 验证 MCP 卡密（公开） |
| GET | `/admin/api/usage/logs` | 使用日志 |
| GET | `/admin/api/usage/stats` | 使用统计 |
| POST | `/admin/api/models/test` | 测试 LLM 模型 |
| GET | `/admin/api/scheduler/status` | 定时索引调度器状态 |

### 请求示例

#### RAG 问答

```bash
curl -X POST https://your-domain/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "question": "这个项目的主要功能是什么？",
    "top_k": 5,
    "use_history": true,
    "group_names": ["my-project"]
  }'
```

#### 添加知识（异步）

```bash
# 提交任务（立即返回 task_id）
curl -X POST https://your-domain/add_knowledge \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "content": "这是一条知识内容...",
    "title": "知识标题",
    "category": "note",
    "group_names": ["my-project"]
  }'

# 响应示例
{
  "success": true,
  "message": "任务已提交，正在后台处理",
  "task_id": "abc123...",
  "status": "pending"
}

# 查询任务状态
curl -X GET https://your-domain/add_knowledge/status/abc123... \
  -H "Authorization: Bearer <token>"

# 响应示例（完成后）
{
  "success": true,
  "message": "知识添加成功！",
  "task_id": "abc123...",
  "status": "completed",
  "result_id": "def456..."
}
```

#### 向量检索

```bash
curl -X POST https://your-domain/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "query": "嵌入模型",
    "top_k": 10,
    "score_threshold": 0.5,
    "group_names": ["my-project"]
  }'
```

---

## Claude Desktop 集成

### 方式一: API Key 认证 (推荐)

1. 在后台管理 -> MCP卡密 页面创建卡密
2. 配置 `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rag-knowledge": {
      "command": "python",
      "args": ["/path/to/rag/mcp_server/server.py"],
      "env": {
        "RAG_API_KEY": "rag_sk_你的卡密"
      }
    }
  }
}
```

### 方式二: uvx 安装

```bash
uvx --from git+https://github.com/fengshao1227/woerk_rag.git rag-mcp
```

### 方式三: HTTP/SSE 模式 (多会话)

适用于多个 Claude 窗口同时使用：

```bash
# 先启动 MCP Server (HTTP 模式)
RAG_API_KEY=rag_sk_xxx python mcp_server/server.py --http
```

```json
{
  "mcpServers": {
    "rag-knowledge": {
      "url": "http://localhost:8766/sse"
    }
  }
}
```

### MCP 工具列表

| 工具 | 说明 |
|------|------|
| `query` | RAG 问答查询，支持 group_names 分组过滤 |
| `search` | 向量检索，支持 group_names 分组过滤 |
| `add_knowledge` | 添加知识条目，支持 group_names 分组 |

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
# 一键部署（提交 + 推送 + 服务器更新）
./scripts/quick-deploy-new.sh "feat: 新功能描述"

# 仅重启服务（优雅重启，零端口冲突）
ssh user@server "cd ~/rag && bash scripts/graceful-restart.sh"

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

### Q: 添加知识为什么是异步的？

为了支持高并发，知识添加采用异步任务队列模式。请求会立即返回 `task_id`，后台 Worker 异步处理 LLM 提取和向量化。使用 `/add_knowledge/status/{task_id}` 查询处理状态。

### Q: 如何查看系统日志？

```bash
./scripts/logs.sh
# 或
tail -f logs/rag.log
# 或
ssh user@server "tail -f ~/rag/server.log"
```

### Q: 部署后出现 500 错误？

检查端口冲突和进程状态：
```bash
# 查看进程
ps aux | grep uvicorn

# 优雅重启（推荐）
bash scripts/graceful-restart.sh
```

---

## 更新日志

### v1.3.0 (2025-12-11)
- ✨ 新增 MCP 卡密管理功能，支持 API Key 认证
- ✨ 后台新增 MCP卡密 管理页面
- ✨ MCP Server 支持 HTTP/SSE 多会话模式
- ✨ 知识库支持按分组筛选，新增"未分组"虚拟分组
- 🔧 部署脚本自动检测前端更改并构建上传
- 🔧 认证模块支持 JWT 和 API Key 双重认证

### v1.2.0 (2025-12-11)
- ✨ 新增异步任务队列，知识添加支持高并发
- ✨ 新增任务状态查询和任务列表 API
- 🐛 修复多进程部署时端口冲突问题
- 🔧 优化服务启动脚本，采用单进程模式

### v1.1.0 (2025-12-08)
- ✨ 新增知识分组管理功能
- ✨ MCP 工具支持 group_names 分组过滤
- ✨ 新增嵌入供应商管理和热重载
- ✨ 新增定时索引调度器
- 🔧 完善 CLAUDE.md 文档体系

### v1.0.0 (2025-12-01)
- 🎉 首次发布
- 基础 RAG 问答功能
- 后台管理系统
- MCP Server 集成

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
