"""日历视图数据：按日期区间返回任务、复习节点与每日专注分钟。"""
from collections import defaultdict
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Review, Session as StudySession, Task, User
from ..schemas import CalendarOut
from ..security import get_current_user
from .reviews import _source_title

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("", response_model=CalendarOut)
def calendar_data(
    start: date = Query(...),
    end: date = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if end < start:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")
    if (end - start).days > 366:
        raise HTTPException(status_code=400, detail="查询区间不能超过一年")

    tasks = db.scalars(
        select(Task)
        .where(
            Task.user_id == user.id,
            Task.due_date.is_not(None),
            Task.due_date >= start,
            Task.due_date <= end,
        )
        .order_by(Task.due_date, Task.id)
    ).all()

    reviews = db.scalars(
        select(Review)
        .where(
            Review.user_id == user.id,
            Review.due_date >= start,
            Review.due_date <= end,
        )
        .order_by(Review.due_date, Review.id)
    ).all()

    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end, time.max)
    sessions = db.scalars(
        select(StudySession).where(
            StudySession.user_id == user.id,
            StudySession.completed_at >= start_dt,
            StudySession.completed_at <= end_dt,
        )
    ).all()
    focus: dict[str, int] = defaultdict(int)
    for session in sessions:
        focus[session.completed_at.date().isoformat()] += session.duration_minutes

    return CalendarOut(
        tasks=list(tasks),
        reviews=[
            {
                "id": review.id,
                "source_type": review.source_type,
                "source_id": review.source_id,
                "source_title": _source_title(db, review.source_type, review.source_id),
                "due_date": review.due_date.isoformat(),
                "reviewed_at": review.reviewed_at,
            }
            for review in reviews
        ],
        focus_minutes=dict(focus),
    )
