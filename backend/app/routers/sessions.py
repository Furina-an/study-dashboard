from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Session, Task, User
from ..schemas import SessionCreate, SessionOut
from ..security import get_current_user

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=201)
def create_session(
    payload: SessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.task_id is not None:
        task = db.scalar(
            select(Task).where(
                Task.id == payload.task_id, Task.user_id == user.id
            )
        )
        if task is None:
            raise HTTPException(status_code=404, detail="关联任务不存在")
    now = datetime.now()
    session = Session(
        user_id=user.id,
        task_id=payload.task_id,
        duration_minutes=payload.duration_minutes,
        started_at=payload.started_at or now,
        completed_at=payload.completed_at or now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session