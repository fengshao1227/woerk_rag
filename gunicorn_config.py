"""
Gunicorn 配置文件
使用 Uvicorn Worker 实现多进程异步服务
"""
import multiprocessing
import os

# 服务器绑定
bind = "0.0.0.0:8000"

# Worker 配置
workers = 2  # 低配服务器使用 2 个 worker
worker_class = "uvicorn.workers.UvicornWorker"  # 使用 Uvicorn Worker

# 超时配置
timeout = 120  # 请求超时（秒）
keepalive = 5  # Keep-Alive 超时

# 优雅重启
graceful_timeout = 30  # 优雅关闭超时
max_requests = 1000  # Worker 处理请求数后重启（防止内存泄漏）
max_requests_jitter = 50  # 随机抖动

# 日志配置
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程命名
proc_name = "rag-api"

# 预加载应用（节省内存）
preload_app = False  # 设为 False 避免共享状态问题

# Worker 临时目录
worker_tmp_dir = "/dev/shm"  # 使用内存文件系统（Linux）

# 性能优化
worker_connections = 1000  # 每个 worker 最大连接数


def on_starting(server):
    """服务启动时回调"""
    print("🚀 RAG API 服务正在启动...")


def on_reload(server):
    """重载时回调"""
    print("🔄 RAG API 服务正在重载...")


def worker_int(worker):
    """Worker 被中断时回调"""
    print(f"⚠️  Worker {worker.pid} 被中断")


def worker_abort(worker):
    """Worker 异常退出时回调"""
    print(f"❌ Worker {worker.pid} 异常退出")


def post_worker_init(worker):
    """Worker 初始化完成后回调"""
    print(f"✅ Worker {worker.pid} 初始化完成")
