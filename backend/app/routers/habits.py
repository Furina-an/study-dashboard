from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Task, TaskCheckin, User
from ..schemas import HabitDay, HabitOut
from ..security import get_current_user

router = APIRouter(prefix="/api/habits", tags=["habits"])


def habit_scheduled(frequency: str, habit_days: list[int] | None, day: date) -> bool:
    """判断某天是否为该习惯的应打卡日。1=周一 … 7=周日。"""
    if frequency == "daily":
        return True
    weekday = day.isoweekday()
    if frequency == "weekdays":
        return weekday <= 5
    if frequency == "custom":
        return weekday in (habit_days or [])
    return True


def habit_streak(
    db: Session,
    user_id: int,
    task_id: int,
    today: date,
    frequency: str = "daily",
    habit_days: list[int] | None = None,
) -> int:
    """连续应打卡日均已打卡的天数。

    - 今天已打卡则从今天往前数；否则从昨天往前数（允许“昨天断点”）。
    - 只统计应打卡日，非应打卡日自动跳过（如周末）。daily 行为与旧版一致。
    """
    checked = set(
        db.scalars(
            select(TaskCheckin.checkin_date).where(
                TaskCheckin.user_id == user_id, TaskCheckin.task_id == task_id
            )
        ).all()
    )
    cursor = today if today in checked else today - timedelta(days=1)
    for _ in range(8):
        if habit_scheduled(frequency, habit_days, cursor):
            break
        cursor -= timedelta(days=1)
    streak = 0
    while cursor in checked:
        streak += 1
        cursor -= timedelta(days=1)
        for _ in range(8):
            if habit_scheduled(frequency, habit_days, cursor):
                break
            cursor -= timedelta(days=1)
    return streak


def _last_7_days(db: Session, user_id: int, task_id: int, today: date) -> list[HabitDay]:
    start = today - timedelta(days=6)
    checked = set(
        db.scalars(
            select(TaskCheckin.checkin_date).where(
                TaskCheckin.user_id == user_id,
                TaskCheckin.task_id == task_id,
                TaskCheckin.checkin_date >= start,
            )
        ).all()
    )
    return [
        HabitDay(date=day.isoformat(), checked=day in checked)
        for day in (start + timedelta(days=offset) for offset in range(7))
    ]


@router.get("", response_model=list[HabitOut])
def list_habits(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = db.scalars(
        select(Task)
        .where(Task.user_id == user.id, Task.is_habit.is_(True))
        .order_by(Task.created_at.desc())
    ).all()
    today = date.today()
    return [
        HabitOut(
            id=task.id,
            title=task.title,
            subject=task.subject,
            estimated_minutes=task.estimated_minutes,
            status=task.status,
            plan_id=task.plan_id,
            is_habit=task.is_habit,
            habit_frequency=task.habit_frequency,
            checked_today=today in {
                c.checkin_date
                for c in db.scalars(
                    select(TaskCheckin).where(
                        TaskCheckin.user_id == user.id, TaskCheckin.task_id == task.id
                    )
                ).all()
            },
            habit_days=task.habit_days,
            scheduled_today=habit_scheduled(task.habit_frequency, task.habit_days, today),
            current_streak=habit_streak(
                db, user.id, task.id, today,
                task.habit_frequency, task.habit_days,
            ),
            last_7_days=_last_7_days(db, user.id, task.id, today),
        )
        for task in tasks
    ]
