"""
JWT 认证模块
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from admin.database import get_db
from admin.models import User, MCPApiKey

load_dotenv()

# JWT 配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "rag-admin-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))  # 刷新 Token 有效期

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer Token 认证 (可选，因为我们也支持 API Key)
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT Access Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT Refresh Token（用于刷新 Access Token）"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str, expected_type: str = None) -> Optional[dict]:
    """
    解码 JWT Token

    Args:
        token: JWT Token 字符串
        expected_type: 期望的 Token 类型 ("access" 或 "refresh")
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # 验证 Token 类型
        if expected_type and payload.get("type") != expected_type:
            return None
        return payload
    except JWTError:
        return None


def verify_api_key(api_key: str, db: Session) -> Optional[MCPApiKey]:
    """验证 API Key 并返回卡密记录"""
    if not api_key:
        return None

    key_record = db.query(MCPApiKey).filter(
        MCPApiKey.key == api_key,
        MCPApiKey.is_active == True
    ).first()

    if not key_record:
        return None

    # 检查过期时间
    if key_record.expires_at and key_record.expires_at < datetime.now():
        return None

    # 更新使用统计
    key_record.last_used_at = datetime.now()
    key_record.usage_count += 1
    db.commit()

    return key_record


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    获取当前登录用户

    支持两种认证方式:
    1. Bearer Token (JWT): Authorization: Bearer <token>
    2. API Key: X-API-Key: rag_sk_xxx
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 方式1: 检查 X-API-Key 请求头 (MCP 客户端使用)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        key_record = verify_api_key(api_key, db)
        if key_record:
            # 如果卡密绑定了用户，返回该用户（继承用户权限）
            if key_record.user_id:
                bound_user = db.query(User).filter(User.id == key_record.user_id).first()
                if bound_user and bound_user.is_active:
                    return bound_user
                # 用户不存在或已禁用
                logger.warning(f"卡密 {key_record.name} 绑定的用户已失效(user_id={key_record.user_id})，拒绝访问")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="卡密绑定的用户已禁用或不存在"
                )
            # 未绑定用户的卡密（旧卡密），返回管理员用户以保持向后兼容
            # 警告：这是临时兼容方案，旧卡密应尽快绑定到具体用户
            logger.warning(f"旧卡密 {key_record.name} 未绑定用户，使用管理员权限（安全风险）")
            admin_user = db.query(User).filter(User.role == "admin").first()
            if admin_user:
                return admin_user
            # 如果没有管理员用户，拒绝访问（不再创建临时管理员）
            logger.error("系统中没有管理员用户，无法处理旧卡密")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统配置错误"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key 无效或已过期"
            )

    # 方式2: 检查 Bearer Token (JWT)
    if credentials:
        token = credentials.credentials
        payload = decode_token(token)

        if payload is None:
            raise credentials_exception

        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise credentials_exception

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户已被禁用"
            )

        return user

    # 没有提供任何认证凭据
    raise credentials_exception


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """获取当前管理员用户"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """验证用户登录"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
