"""管理员：邀请码生成与控制 + 用户概览。

管理员由 ADMIN_USERNAMES 环境变量指定（逗号分隔，默认 admin）。
通过邀请码的数量/有效期/使用次数控制注册人数。
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import InviteCode, User
from ..schemas import (
    AdminStatsOut,
    AdminUserOut,
    AdminUserUpdate,
    InviteCreate,
    InviteOut,
    InviteUpdate,
)
from ..security import get_current_user, is_admin_user

router = APIRouter(prefix="/api/admin", tags=["admin"])

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉易混淆的 I/O/0/1


def _require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not is_admin_user(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    return user


def _generate_code() -> str:
    """生成 12 位邀请码，形如 ABCD-EFGH-JKLM。"""
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def _invite_out(invite: InviteCode) -> InviteOut:
    return InviteOut(
        id=invite.id,
        code=invite.code,
        created_by=invite.created_by,
        max_uses=invite.max_uses,
        used_count=invite.used_count,
        expires_at=invite.expires_at,
        active=invite.active,
        remark=invite.remark,
        created_at=invite.created_at,
    )


def _user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        username=user.username,
        created_at=user.created_at,
        is_active=user.is_active,
        is_admin=is_admin_user(user),
    )


@router.get("/stats", response_model=AdminStatsOut)
def admin_stats(
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    total_users = db.scalar(select(func.count(User.id))) or 0
    total_invites = db.scalar(select(func.count(InviteCode.id))) or 0
    active_invites = (
        db.scalar(
            select(func.count(InviteCode.id)).where(InviteCode.active.is_(True))
        )
        or 0
    )
    unused_invites = (
        db.scalar(
            select(func.count(InviteCode.id)).where(
                InviteCode.active.is_(True),
                InviteCode.used_count < InviteCode.max_uses,
            )
        )
        or 0
    )
    return AdminStatsOut(
        total_users=total_users,
        total_invites=total_invites,
        active_invites=active_invites,
        unused_invites=unused_invites,
    )


@router.get("/invites", response_model=list[InviteOut])
def list_invites(
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(InviteCode).order_by(InviteCode.created_at.desc(), InviteCode.id.desc())
    ).all()
    return [_invite_out(row) for row in rows]


@router.post("/invites", response_model=list[InviteOut], status_code=201)
def create_invites(
    payload: InviteCreate,
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    expires_at = (
        datetime.now() + timedelta(days=payload.expires_days)
        if payload.expires_days
        else None
    )
    created: list[InviteCode] = []
    for _ in range(payload.count):
        invite = InviteCode(
            code=_generate_code(),
            created_by=admin.id,
            max_uses=payload.max_uses,
            expires_at=expires_at,
            remark=payload.remark,
        )
        db.add(invite)
        created.append(invite)
    db.commit()
    for invite in created:
        db.refresh(invite)
    return [_invite_out(invite) for invite in created]


@router.patch("/invites/{invite_id}", response_model=InviteOut)
def update_invite(
    invite_id: int,
    payload: InviteUpdate,
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    invite = db.get(InviteCode, invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    if payload.active is not None:
        invite.active = payload.active
    if payload.max_uses is not None:
        invite.max_uses = payload.max_uses
    if payload.remark is not None:
        invite.remark = payload.remark
    db.commit()
    db.refresh(invite)
    return _invite_out(invite)


@router.delete("/invites/{invite_id}", status_code=204)
def delete_invite(
    invite_id: int,
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    invite = db.get(InviteCode, invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    db.delete(invite)
    db.commit()


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(User).order_by(User.created_at.desc(), User.id.desc())
    ).all()
    return [_user_out(user) for user in rows]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not payload.is_active:
        if user.id == admin.id:
            raise HTTPException(status_code=400, detail="不能禁用自己")
        if is_admin_user(user):
            raise HTTPException(status_code=400, detail="不能禁用管理员账号")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return _user_out(user)
