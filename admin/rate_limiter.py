"""
登录限流模块 - 防止暴力破解

特性:
- 基于 IP 和用户名的双重限流
- 可配置的失败阈值和锁定时间
- 自动清理过期记录
- 支持手动解锁
"""
import time
from typing import Dict, Optional, Tuple
from threading import Lock
from dataclasses import dataclass, field
from datetime import datetime
import os

# 配置参数
MAX_FAILED_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))  # 最大失败次数
LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "300"))  # 锁定时间（5分钟）
CLEANUP_INTERVAL = 3600  # 清理间隔（1小时）


@dataclass
class LoginAttempt:
    """登录尝试记录"""
    failed_count: int = 0
    last_failed_at: float = 0
    locked_until: float = 0
    first_failed_at: float = 0


class RateLimiter:
    """
    登录限流器

    使用内存存储（适合单实例部署）
    生产环境可扩展为 Redis 实现
    """

    def __init__(self):
        self._ip_attempts: Dict[str, LoginAttempt] = {}
        self._username_attempts: Dict[str, LoginAttempt] = {}
        self._lock = Lock()
        self._last_cleanup = time.time()

    def _cleanup_expired(self) -> None:
        """清理过期的锁定记录"""
        now = time.time()
        if now - self._last_cleanup < CLEANUP_INTERVAL:
            return

        with self._lock:
            # 清理 IP 记录
            expired_ips = [
                ip for ip, attempt in self._ip_attempts.items()
                if now > attempt.locked_until and now - attempt.last_failed_at > LOCKOUT_SECONDS * 2
            ]
            for ip in expired_ips:
                del self._ip_attempts[ip]

            # 清理用户名记录
            expired_users = [
                username for username, attempt in self._username_attempts.items()
                if now > attempt.locked_until and now - attempt.last_failed_at > LOCKOUT_SECONDS * 2
            ]
            for username in expired_users:
                del self._username_attempts[username]

            self._last_cleanup = now

    def check_rate_limit(self, ip: str, username: str) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        检查是否被限流

        Returns:
            (is_allowed, error_message, remaining_seconds)
        """
        self._cleanup_expired()
        now = time.time()

        with self._lock:
            # 检查 IP 锁定
            ip_attempt = self._ip_attempts.get(ip)
            if ip_attempt and now < ip_attempt.locked_until:
                remaining = int(ip_attempt.locked_until - now)
                return False, f"IP 已被锁定，请在 {remaining} 秒后重试", remaining

            # 检查用户名锁定
            user_attempt = self._username_attempts.get(username)
            if user_attempt and now < user_attempt.locked_until:
                remaining = int(user_attempt.locked_until - now)
                return False, f"账户已被锁定，请在 {remaining} 秒后重试", remaining

        return True, None, None

    def record_failed_attempt(self, ip: str, username: str) -> Tuple[int, bool]:
        """
        记录失败的登录尝试

        Returns:
            (remaining_attempts, is_locked)
        """
        now = time.time()

        with self._lock:
            # 记录 IP 失败
            if ip not in self._ip_attempts:
                self._ip_attempts[ip] = LoginAttempt(first_failed_at=now)
            ip_attempt = self._ip_attempts[ip]

            # 如果上次失败超过锁定时间，重置计数
            if now - ip_attempt.last_failed_at > LOCKOUT_SECONDS:
                ip_attempt.failed_count = 0
                ip_attempt.first_failed_at = now

            ip_attempt.failed_count += 1
            ip_attempt.last_failed_at = now

            # 记录用户名失败
            if username not in self._username_attempts:
                self._username_attempts[username] = LoginAttempt(first_failed_at=now)
            user_attempt = self._username_attempts[username]

            if now - user_attempt.last_failed_at > LOCKOUT_SECONDS:
                user_attempt.failed_count = 0
                user_attempt.first_failed_at = now

            user_attempt.failed_count += 1
            user_attempt.last_failed_at = now

            # 检查是否需要锁定
            max_failed = max(ip_attempt.failed_count, user_attempt.failed_count)
            is_locked = False

            if max_failed >= MAX_FAILED_ATTEMPTS:
                lock_until = now + LOCKOUT_SECONDS
                ip_attempt.locked_until = lock_until
                user_attempt.locked_until = lock_until
                is_locked = True

            remaining = MAX_FAILED_ATTEMPTS - max_failed
            return max(0, remaining), is_locked

    def record_successful_login(self, ip: str, username: str) -> None:
        """记录成功登录，清除失败记录"""
        with self._lock:
            if ip in self._ip_attempts:
                del self._ip_attempts[ip]
            if username in self._username_attempts:
                del self._username_attempts[username]

    def unlock_ip(self, ip: str) -> bool:
        """手动解锁 IP"""
        with self._lock:
            if ip in self._ip_attempts:
                del self._ip_attempts[ip]
                return True
            return False

    def unlock_username(self, username: str) -> bool:
        """手动解锁用户名"""
        with self._lock:
            if username in self._username_attempts:
                del self._username_attempts[username]
                return True
            return False

    def get_status(self, ip: Optional[str] = None, username: Optional[str] = None) -> dict:
        """获取限流状态（用于调试和监控）"""
        now = time.time()
        result = {}

        with self._lock:
            if ip and ip in self._ip_attempts:
                attempt = self._ip_attempts[ip]
                result["ip"] = {
                    "failed_count": attempt.failed_count,
                    "is_locked": now < attempt.locked_until,
                    "remaining_lockout": max(0, int(attempt.locked_until - now)),
                    "first_failed_at": datetime.fromtimestamp(attempt.first_failed_at).isoformat() if attempt.first_failed_at else None,
                }

            if username and username in self._username_attempts:
                attempt = self._username_attempts[username]
                result["username"] = {
                    "failed_count": attempt.failed_count,
                    "is_locked": now < attempt.locked_until,
                    "remaining_lockout": max(0, int(attempt.locked_until - now)),
                    "first_failed_at": datetime.fromtimestamp(attempt.first_failed_at).isoformat() if attempt.first_failed_at else None,
                }

        return result


# 全局限流器实例
rate_limiter = RateLimiter()
