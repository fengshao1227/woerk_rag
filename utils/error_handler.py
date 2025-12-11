"""
统一错误处理装饰器
"""
from functools import wraps
from fastapi import HTTPException
from utils.logger import logger
from typing import Callable, Any


def handle_api_errors(func: Callable) -> Callable:
    """
    统一API错误处理装饰器

    自动捕获异常并记录日志,避免在每个端点重复try-except

    Usage:
        @handle_api_errors
        async def my_endpoint(...):
            ...
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # FastAPI HTTPException 直接抛出
            raise
        except Exception as e:
            # 其他异常统一处理
            logger.error(f"{func.__name__} 执行失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
    return wrapper


def handle_sync_errors(func: Callable) -> Callable:
    """
    同步函数的错误处理装饰器

    Usage:
        @handle_sync_errors
        def my_function(...):
            ...
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"{func.__name__} 执行失败: {e}", exc_info=True)
            raise
    return wrapper
