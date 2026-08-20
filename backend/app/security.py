import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import InviteCode, User

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

bearer_scheme = HTTPBearer(auto_error=False)


def _secret_key() -> str:
    return os.getenv("SECRET_KEY", "dev-secret-change-me-please-set-in-env-var-0123456789")


def _invite_code() -> str:
    return os.getenv("INVITE_CODE", "studydash")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def is_master_invite_code(code: str) -> bool:
    """环境变量 INVITE_CODE 作为主邀请码，永远可用。"""
    return secrets.compare_digest(code, _invite_code())


def find_valid_invite(code: str, db: Session) -> InviteCode | None:
    """在数据库中查找仍可用的邀请码（启用、未过期、未用完）。"""
    invite = db.scalar(select(InviteCode).where(InviteCode.code == code))
    if invite is None or not invite.active:
        return None
    if invite.expires_at is not None and invite.expires_at < datetime.now():
        return None
    if invite.used_count >= invite.max_uses:
        return None
    return invite


def verify_invite_code(code: str, db: Session | None = None) -> bool:
    """邀请码有效：主邀请码或数据库邀请码（db 为空时只校验主码）。"""
    if is_master_invite_code(code):
        return True
    if db is None:
        return False
    return find_valid_invite(code, db) is not None


def consume_invite_code(code: str, db: Session) -> None:
    """注册成功后消耗一次数据库邀请码（主码不计数）。"""
    invite = db.scalar(select(InviteCode).where(InviteCode.code == code))
    if invite is not None:
        invite.used_count += 1
        db.add(invite)


def is_admin_user(user: User) -> bool:
    """运营管理员：由 ADMIN_USERNAMES 环境变量指定（逗号分隔）。"""
    admins = [
        name.strip()
        for name in os.getenv("ADMIN_USERNAMES", "admin").split(",")
        if name.strip()
    ]
    return user.username in admins


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="请先登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(
            credentials.credentials, _secret_key(), algorithms=[ALGORITHM]
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号已被禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
