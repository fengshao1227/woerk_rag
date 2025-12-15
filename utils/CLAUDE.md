# Utils Module

> [Home](../CLAUDE.md) > Utils

## Overview

Utility functions and services used across the RAG system.

## Key Files

| File | Description |
|------|-------------|
| `llm.py` | LLM abstraction (Anthropic/OpenAI) |
| `embeddings.py` | Embedding model (API/Local) |
| `task_queue.py` | Async knowledge addition queue |
| `scheduler.py` | Scheduled indexing service |
| `logger.py` | Logging configuration |
| `config_manager.py` | Dynamic config management |
| `error_handler.py` | Custom exception handling |
| `reference_highlighter.py` | Answer source highlighting |
| `version_tracker.py` | Knowledge versioning |

## LLM Client (`llm.py`)

### Supported Providers

1. **Anthropic Format** (Claude, third-party)
2. **OpenAI Format** (GPT, compatible APIs)

### Usage

```python
from utils.llm import get_llm_client

llm = get_llm_client()
response = llm.invoke([{"role": "user", "content": "Hello"}])
print(response.content)
print(response.usage)  # {"input_tokens": X, "output_tokens": Y}

# Streaming
for chunk in llm.invoke_stream(messages):
    print(chunk, end="")
```

### Features

- Uses `curl_cffi` to bypass Cloudflare
- Supports SSE streaming
- Token usage tracking

## Embedding Model (`embeddings.py`)

### Modes

1. **API Mode** (`EMBEDDING_PROVIDER=api`)
   - OpenAI-compatible embedding API
   - Configurable: base_url, model, dimension

2. **Local Mode** (`EMBEDDING_PROVIDER=local`)
   - BGE-M3 model via sentence-transformers
   - Requires ~2GB download on first use

### Usage

```python
from utils.embeddings import EmbeddingModel

model = EmbeddingModel()
vectors = model.encode(["text1", "text2"])  # np.ndarray
dim = model.get_embedding_dim()  # 1536 or 1024
```

## Task Queue (`task_queue.py`)

Async knowledge addition with background workers.

### Usage

```python
from utils.task_queue import get_task_queue, KnowledgeTaskPayload

queue = get_task_queue()
queue.set_dependencies(llm, embedding, qdrant, collection)

# Submit task
task_id = await queue.submit(KnowledgeTaskPayload(...))

# Check status
status = await queue.get_status(task_id)
```

### Configuration

- `max_workers`: 3 concurrent workers
- Uses `asyncio.Queue` (in-memory)

## Scheduler (`scheduler.py`)

Periodic background indexing.

```python
from utils.scheduler import get_scheduler, start_scheduler

scheduler = get_scheduler()
await start_scheduler()
```

### Configuration

```python
SCHEDULER_ENABLE = True
SCHEDULER_INTERVAL_MINUTES = 60
SCHEDULER_INDEX_CODE = True
SCHEDULER_INDEX_DOCS = True
```

## Logger (`logger.py`)

Centralized logging with file rotation.

```python
from utils.logger import logger

logger.info("Message")
logger.error("Error", exc_info=True)
```

Output: `logs/rag.log`

## Dependencies

- curl_cffi (HTTP with Cloudflare bypass)
- httpx (async HTTP)
- numpy (embeddings)
- sentence-transformers (local embedding, optional)
