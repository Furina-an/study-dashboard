"""用户自建的计划拆解模板。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PlanTemplate, User
from ..schemas import (
    PlanTemplateChild,
    PlanTemplateCreate,
    PlanTemplateOut,
    PlanTemplateUpdate,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/plan-templates", tags=["plan-templates"])


def _to_out(row: PlanTemplate) -> PlanTemplateOut:
    try:
        children = json.loads(row.children or "[]")
    except (TypeError, ValueError):
        children = []
    return PlanTemplateOut(
        id=row.id,
        name=row.name,
        children=[PlanTemplateChild(**child) for child in children],
        created_at=row.created_at,
    )


def _get_owned(template_id: int, user_id: int, db: Session) -> PlanTemplate:
    row = db.scalar(
        select(PlanTemplate).where(
            PlanTemplate.id == template_id, PlanTemplate.user_id == user_id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    return row


@router.get("", response_model=list[PlanTemplateOut])
def list_templates(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    rows = db.scalars(
        select(PlanTemplate)
        .where(PlanTemplate.user_id == user.id)
        .order_by(PlanTemplate.created_at.desc())
    ).all()
    return [_to_out(row) for row in rows]


@router.post("", response_model=PlanTemplateOut, status_code=201)
def create_template(
    payload: PlanTemplateCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = PlanTemplate(
        user_id=user.id,
        name=payload.name,
        children=json.dumps(
            [child.model_dump() for child in payload.children], ensure_ascii=False
        ),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.patch("/{template_id}", response_model=PlanTemplateOut)
def update_template(
    template_id: int,
    payload: PlanTemplateUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_owned(template_id, user.id, db)
    if payload.name is not None:
        row.name = payload.name
    if payload.children is not None:
        row.children = json.dumps(
            [child.model_dump() for child in payload.children], ensure_ascii=False
        )
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_owned(template_id, user.id, db)
    db.delete(row)
    db.commit()
