"""
数据库连接管理器
统一管理数据库连接，使用连接池和上下文管理器
"""

from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from config import Config
from utils.logger import logger


class DatabaseManager:
    """数据库连接管理器"""

    _instance: Optional['DatabaseManager'] = None
    _engine = None
    _session_factory = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._init_engine()

    def _init_engine(self):
        """初始化数据库引擎和连接池"""
        try:
            database_url = Config.get_database_url()

            self._engine = create_engine(
                database_url,
                poolclass=QueuePool,
                pool_size=5,           # 连接池大小
                max_overflow=10,       # 最大溢出连接数
                pool_timeout=30,       # 获取连接超时时间
                pool_recycle=3600,     # 连接回收时间（1小时）
                pool_pre_ping=True,    # 连接前检查有效性
                echo=False             # 不打印 SQL 语句
            )

            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False
            )

            logger.info("数据库连接池初始化成功")

        except Exception as e:
            logger.error(f"数据库连接池初始化失败: {e}")
            raise

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        获取数据库会话的上下文管理器

        使用方式:
            db_manager = DatabaseManager()
            with db_manager.get_session() as session:
                # 使用 session 进行数据库操作
                session.query(...)
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败，已回滚: {e}")
            raise
        finally:
            session.close()

    @contextmanager
    def get_session_no_commit(self) -> Generator[Session, None, None]:
        """
        获取数据库会话（不自动提交）
        用于需要手动控制事务的场景
        """
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def execute_with_retry(self, func, max_retries: int = 3, *args, **kwargs):
        """
        带重试的数据库操作执行器

        Args:
            func: 要执行的函数，接收 session 作为第一个参数
            max_retries: 最大重试次数
            *args, **kwargs: 传递给 func 的其他参数
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                with self.get_session() as session:
                    return func(session, *args, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"数据库操作失败 (尝试 {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    import time
                    time.sleep(0.5 * (attempt + 1))  # 指数退避

        raise last_error

    def health_check(self) -> bool:
        """检查数据库连接健康状态"""
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return False

    def get_pool_status(self) -> dict:
        """获取连接池状态"""
        if self._engine is None:
            return {"status": "not_initialized"}

        pool = self._engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalidatedcount() if hasattr(pool, 'invalidatedcount') else 0
        }


# 全局单例
db_manager = DatabaseManager()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI 依赖注入用的数据库会话获取器"""
    with db_manager.get_session() as session:
        yield session
