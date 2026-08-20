from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from ..security import (
    consume_invite_code,
    create_access_token,
    find_valid_invite,
    get_current_user,
    hash_password,
    is_admin_user,
    is_master_invite_code,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        created_at=user.created_at,
        is_admin=is_admin_user(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    invite = find_valid_invite(payload.invite_code, db)
    if invite is None and not is_master_invite_code(payload.invite_code):
        raise HTTPException(status_code=400, detail="邀请码不正确或已失效")
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists is not None:
        raise HTTPException(status_code=409, detail="用户名已被占用")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    if invite is not None:
        consume_invite_code(payload.invite_code, db)
        db.commit()
    db.refresh(user)
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=_user_out(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=_user_out(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)
