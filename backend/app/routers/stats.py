from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Session, Task, User
from ..schemas import (
    HeatmapPoint,
    StreakStats,
    TodayStats,
    TrendPoint,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/today", response_model=TodayStats)
def today_stats(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    today = date.today()
    start = datetime.combine(today, time.min)
    end = datetime.combine(today, time.max)

    sessions = db.scalars(
        select(Session).where(
            Session.user_id == user.id,
            Session.completed_at >= start,
            Session.completed_at <= end,
        )
    ).all()
    tasks_done = db.scalars(
        select(Task).where(
            Task.user_id == user.id,
            Task.status == "done",
            Task.completed_at >= start,
            Task.completed_at <= end,
        )
    ).all()

    return TodayStats(
        date=today.isoformat(),
        focus_minutes=sum(s.duration_minutes for s in sessions),
        focus_count=len(sessions),
        tasks_completed=len(tasks_done),
    )


@router.get("/trend", response_model=list[TrendPoint])
def trend_stats(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    start_date = today - timedelta(days=days - 1)
    start = datetime.combine(start_date, time.min)

    sessions = db.scalars(
        select(Session).where(
            Session.user_id == user.id, Session.completed_at >= start
        )
    ).all()

    by_day: dict[date, dict[str, int]] = defaultdict(
        lambda: {"focus_minutes": 0, "focus_count": 0}
    )
    for session in sessions:
        day = session.completed_at.date()
        by_day[day]["focus_minutes"] += session.duration_minutes
        by_day[day]["focus_count"] += 1

    points = []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        aggregate = by_day.get(day, {"focus_minutes": 0, "focus_count": 0})
        points.append(TrendPoint(date=day.isoformat(), **aggregate))
    return points


@router.get("/heatmap", response_model=list[HeatmapPoint])
def heatmap_stats(
    days: int = Query(105, ge=7, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    start_date = today - timedelta(days=days - 1)
    start = datetime.combine(start_date, time.min)

    sessions = db.scalars(
        select(Session).where(
            Session.user_id == user.id, Session.completed_at >= start
        )
    ).all()

    by_day: dict[date, int] = defaultdict(int)
    for session in sessions:
        by_day[session.completed_at.date()] += session.duration_minutes

    return [
        HeatmapPoint(date=day.isoformat(), focus_minutes=by_day.get(day, 0))
        for day in (start_date + timedelta(days=offset) for offset in range(days))
    ]


@router.get("/streak", response_model=StreakStats)
def streak_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = db.scalars(
        select(Session).where(Session.user_id == user.id)
    ).all()
    focused_days = sorted({s.completed_at.date() for s in sessions})
    day_set = set(focused_days)
    today = date.today()

    # 当前连续天数：今天已专注则从今天往前数，否则允许昨天为断点
    cursor = today if today in day_set else today - timedelta(days=1)
    current = 0
    while cursor in day_set:
        current += 1
        cursor -= timedelta(days=1)

    # 历史最长连续天数
    best = 0
    run = 0
    prev: date | None = None
    for day in focused_days:
        run = run + 1 if prev is not None and (day - prev).days == 1 else 1
        best = max(best, run)
        prev = day

    return StreakStats(
        current_streak=current,
        best_streak=best,
        focused_days=len(focused_days),
        total_focus_minutes=sum(s.duration_minutes for s in sessions),
    )
