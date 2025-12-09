# 部署脚本模块

**导航**: [← 返回根目录](../CLAUDE.md) / **scripts/**

> 自动化部署、启动和运维脚本
>
> **最后更新**: 2025-12-08 23:26:20

## 模块概述

`scripts/` 模块包含项目的自动化脚本，用于简化部署、启动和日常运维操作，包括:
- 服务启动脚本
- 项目部署脚本
- 数据索引脚本
- 日志查看脚本

## 核心文件

| 文件 | 职责 | 使用场景 |
|------|------|----------|
| `start_api.sh` | 启动 API 服务 | 本地开发、测试 |
| `start_qdrant.sh` | 启动 Qdrant 容器 | 首次部署、重启服务 |
| `index_project.sh` | 索引项目代码和文档 | 数据初始化、增量更新 |
| `deploy.sh` | 生产环境部署 | 服务器部署 |
| `deploy-admin.sh` | 部署后台管理前端 | 前端更新 |
| `quick-deploy.sh` | 快速部署（跳过依赖） | 代码更新 |
| `logs.sh` | 查看服务日志 | 故障排查、监控 |

## 脚本详解

### 1. start_api.sh - 启动 API 服务

#### 功能
- 激活 Python 虚拟环境
- 启动 FastAPI 服务（开发模式）
- 支持热重载

#### 用法

```bash
./scripts/start_api.sh
```

#### 脚本内容

```bash
#!/bin/bash
# 启动 API 服务（开发模式）

cd "$(dirname "$0")/.."

# 激活虚拟环境
source venv/bin/activate

# 启动 API 服务
uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

#### 参数说明
- `--reload`: 代码变更自动重载
- `--host 0.0.0.0`: 允许外部访问
- `--port 8000`: 监听端口

### 2. start_qdrant.sh - 启动 Qdrant

#### 功能
- 检查 Docker 是否安装
- 启动 Qdrant 容器
- 持久化数据到本地目录

#### 用法

```bash
./scripts/start_qdrant.sh
```

#### 脚本内容

```bash
#!/bin/bash
# 启动 Qdrant 向量数据库

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "错误: 未安装 Docker"
    exit 1
fi

# 创建数据目录
mkdir -p ./qdrant_data

# 启动 Qdrant
docker run -d \
    --name qdrant \
    -p 6333:6333 \
    -p 6334:6334 \
    -v "$(pwd)/qdrant_data:/qdrant/storage" \
    qdrant/qdrant

echo "Qdrant 已启动"
echo "Web UI: http://localhost:6333/dashboard"
```

#### 数据持久化
- 数据存储: `./qdrant_data`
- 容器重启后数据保留

### 3. index_project.sh - 索引项目

#### 功能
- 索引项目代码和文档
- 调用 `indexer/index_all.py`
- 显示索引统计

#### 用法

```bash
./scripts/index_project.sh
```

#### 脚本内容

```bash
#!/bin/bash
# 索引项目代码和文档

cd "$(dirname "$0")/.."

# 激活虚拟环境
source venv/bin/activate

# 运行索引
python -m indexer.index_all

echo "索引完成！"
```

#### 注意事项
- 首次索引需要几分钟（取决于项目大小）
- 重复索引会覆盖旧数据（TODO: 增量索引）

### 4. deploy.sh - 生产部署

#### 功能
- 拉取最新代码
- 安装/更新依赖
- 重启服务
- 健康检查

#### 用法

```bash
./scripts/deploy.sh
```

#### 脚本内容

```bash
#!/bin/bash
# 生产环境部署脚本

set -e  # 遇到错误立即退出

echo "=== 开始部署 RAG API ==="

# 1. 拉取最新代码
echo "[1/5] 拉取最新代码..."
git pull origin main

# 2. 安装依赖
echo "[2/5] 安装依赖..."
source venv/bin/activate
pip install -r requirements.txt

# 3. 重启服务
echo "[3/5] 重启服务..."
pkill -f "uvicorn api.server:app" || true
sleep 2
nohup uvicorn api.server:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &

# 4. 等待启动
echo "[4/5] 等待服务启动..."
sleep 5

# 5. 健康检查
echo "[5/5] 健康检查..."
curl -f http://localhost:8000/health || {
    echo "健康检查失败！"
    exit 1
}

echo "=== 部署完成 ==="
```

#### 适用场景
- 服务器首次部署
- 代码更新后重新部署
- 依赖变更后部署

### 5. deploy-admin.sh - 部署前端

#### 功能
- 构建 React 前端
- 部署到服务器
- 配置 Nginx（可选）

#### 用法

```bash
./scripts/deploy-admin.sh
```

#### 脚本内容

```bash
#!/bin/bash
# 部署后台管理前端

set -e

echo "=== 开始部署前端 ==="

# 1. 进入前端目录
cd admin_frontend

# 2. 安装依赖
echo "[1/4] 安装依赖..."
npm install

# 3. 构建生产版本
echo "[2/4] 构建生产版本..."
npm run build

# 4. 部署到服务器
echo "[3/4] 上传到服务器..."
SERVER="user@your-server.com"
rsync -avz --delete dist/ $SERVER:/var/www/rag-admin/

# 5. 重载 Nginx
echo "[4/4] 重载 Nginx..."
ssh $SERVER "sudo nginx -s reload"

echo "=== 前端部署完成 ==="
echo "访问: https://your-domain.com/admin"
```

#### 配置说明
- 修改 `SERVER` 变量为实际服务器地址
- 确保 Nginx 配置正确

### 6. quick-deploy.sh - 快速部署

#### 功能
- 仅更新代码，跳过依赖安装
- 快速重启服务
- 适合小改动

#### 用法

```bash
./scripts/quick-deploy.sh
```

#### 脚本内容

```bash
#!/bin/bash
# 快速部署（跳过依赖安装）

set -e

echo "=== 快速部署 ==="

# 拉取代码
git pull origin main

# 重启服务
pkill -f "uvicorn api.server:app" || true
sleep 1
source venv/bin/activate
nohup uvicorn api.server:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &

# 健康检查
sleep 3
curl -f http://localhost:8000/health

echo "=== 部署完成 ==="
```

### 7. logs.sh - 查看日志

#### 功能
- 实时查看 API 日志
- 支持日志过滤

#### 用法

```bash
# 查看最近100行
./scripts/logs.sh

# 实时跟踪
./scripts/logs.sh -f

# 查看错误
./scripts/logs.sh | grep ERROR
```

#### 脚本内容

```bash
#!/bin/bash
# 查看服务日志

LOG_FILE="logs/api.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "日志文件不存在: $LOG_FILE"
    exit 1
fi

# 默认显示最后 100 行
tail -n 100 "$LOG_FILE" "$@"
```

## 使用流程

### 首次部署

```bash
# 1. 启动 Qdrant
./scripts/start_qdrant.sh

# 2. 索引数据
./scripts/index_project.sh

# 3. 启动 API 服务
./scripts/start_api.sh

# 4. 部署前端
./scripts/deploy-admin.sh
```

### 日常开发

```bash
# 启动 API 服务（开发模式）
./scripts/start_api.sh

# 前端开发（另一个终端）
cd admin_frontend
npm run dev
```

### 生产更新

```bash
# 完整部署（有依赖变更）
./scripts/deploy.sh

# 快速部署（无依赖变更）
./scripts/quick-deploy.sh
```

### 故障排查

```bash
# 查看日志
./scripts/logs.sh

# 实时监控
./scripts/logs.sh -f

# 检查服务状态
curl http://localhost:8000/health
```

## 环境要求

### 必需工具
- Bash 4.0+
- Python 3.10+
- Docker（用于 Qdrant）
- Git
- curl

### 可选工具
- Node.js 18+ (前端开发)
- rsync (远程部署)
- nginx (前端托管)

## 常见问题

### 1. 权限错误？
```bash
chmod +x scripts/*.sh
```

### 2. Docker 未启动？
```bash
# macOS
open -a Docker

# Linux
sudo systemctl start docker
```

### 3. 端口被占用？
```bash
# 查找占用进程
lsof -i :8000

# 杀死进程
kill -9 <PID>
```

### 4. 虚拟环境未激活？
```bash
source venv/bin/activate
```

## 后续改进

- [ ] 添加 systemd 服务配置
- [ ] 实现蓝绿部署脚本
- [ ] 添加自动备份脚本
- [ ] Docker Compose 一键部署
- [ ] CI/CD 集成（GitHub Actions）
- [ ] 健康检查和自动恢复
- [ ] 日志轮转配置
