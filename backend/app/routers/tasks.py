from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Plan, Task, TaskCheckin, User
from ..schemas import CheckinResult, TaskCreate, TaskOut, TaskUpdate
from ..security import get_current_user
from .habits import habit_scheduled, habit_streak
from .reviews import generate_reviews

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _get_owned_task(task_id: int, user_id: int, db: Session) -> Task:
    task = db.scalar(
        select(Task).where(Task.id == task_id, Task.user_id == user_id)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


def _validate_plan(plan_id: int | None, user_id: int, db: Session) -> None:
    if plan_id is None:
        return
    plan = db.scalar(
        select(Plan).where(Plan.id == plan_id, Plan.user_id == user_id)
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="所属计划不存在")


def _apply_status_change(task: Task, status: str | None) -> bool:
    """Keep completed_at consistent with the status field. 返回是否刚变为 done。"""
    if status is None or status == task.status:
        return False
    if status == "done" and task.status != "done":
        task.completed_at = datetime.now()
        return True
    if status != "done":
        task.completed_at = None
    return False


def _maybe_generate_reviews(db: Session, task: Task) -> None:
    """非习惯任务刚完成时生成复习节点。"""
    if task.status == "done" and not task.is_habit and task.completed_at is not None:
        generate_reviews(db, task.user_id, "task", task.id, task.completed_at)


def _normalize_habit(data: dict) -> None:
    """校验习惯频率与打卡星期；非 custom 频率时清空 habit_days。"""
    frequency = data.get("habit_frequency") or "daily"
    habit_days = data.get("habit_days")
    if frequency == "custom":
        if not habit_days:
            raise HTTPException(status_code=400, detail="自定义频率需选择打卡星期")
        if any(not 1 <= day <= 7 for day in habit_days):
            raise HTTPException(status_code=400, detail="打卡星期需在 1-7（1=周一）")
        data["habit_days"] = sorted(set(habit_days))
    else:
        data["habit_days"] = None


@router.get("", response_model=list[TaskOut])
def list_tasks(
    plan_id: int | None = Query(None),
    habit: bool | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_plan(plan_id, user.id, db)
    statement = select(Task).where(Task.user_id == user.id)
    if plan_id is not None:
        statement = statement.where(Task.plan_id == plan_id)
    if habit is not None:
        statement = statement.where(Task.is_habit.is_(habit))
    return db.scalars(statement.order_by(Task.created_at.desc())).all()


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_plan(payload.plan_id, user.id, db)
    data = payload.model_dump()
    if data.get("is_habit"):
        _normalize_habit(data)
    else:
        data["habit_frequency"] = "daily"
        data["habit_days"] = None
    if data.get("is_habit"):
        # 习惯任务不进入永久 done，避免状态与打卡语义冲突
        data["status"] = "todo"
        data["completed_at"] = None
    task = Task(**data, user_id=user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    _maybe_generate_reviews(db, task)
    if task.status == "done" and not task.is_habit:
        db.commit()
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned_task(task_id, user.id, db)
    changes = payload.model_dump(exclude_unset=True)
    _validate_plan(changes.get("plan_id"), user.id, db)
    if "habit_frequency" in changes or "habit_days" in changes:
        if "habit_frequency" not in changes:
            changes["habit_frequency"] = task.habit_frequency or "daily"
        _normalize_habit(changes)
    became_done = _apply_status_change(task, changes.get("status"))
    for key, value in changes.items():
        setattr(task, key, value)
    if task.is_habit and task.status == "done":
        # 习惯任务以打卡为准，不允许手动置为 done
        task.status = "todo"
        task.completed_at = None
    db.commit()
    db.refresh(task)
    if became_done or task.status == "done":
        _maybe_generate_reviews(db, task)
        db.commit()
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned_task(task_id, user.id, db)
    db.delete(task)
    db.commit()


@router.post("/{task_id}/checkin", response_model=CheckinResult)
def checkin_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned_task(task_id, user.id, db)
    if not task.is_habit:
        raise HTTPException(status_code=400, detail="只有习惯任务可以打卡")
    today = date.today()
    if not habit_scheduled(task.habit_frequency, task.habit_days, today):
        raise HTTPException(status_code=400, detail="今天不是该习惯的应打卡日")
    existing = db.scalar(
        select(TaskCheckin).where(
            TaskCheckin.user_id == user.id,
            TaskCheckin.task_id == task.id,
            TaskCheckin.checkin_date == today,
        )
    )
    if existing is None:
        db.add(
            TaskCheckin(user_id=user.id, task_id=task.id, checkin_date=today)
        )
        db.commit()
    return CheckinResult(
        checked=True,
        checkin_date=today.isoformat(),
        current_streak=habit_streak(
            db, user.id, task.id, today, task.habit_frequency, task.habit_days
        ),
    )


@router.delete("/{task_id}/checkin", response_model=CheckinResult)
def uncheckin_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned_task(task_id, user.id, db)
    if not task.is_habit:
        raise HTTPException(status_code=400, detail="只有习惯任务可以打卡")
    today = date.today()
    existing = db.scalar(
        select(TaskCheckin).where(
            TaskCheckin.user_id == user.id,
            TaskCheckin.task_id == task.id,
            TaskCheckin.checkin_date == today,
        )
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
    return CheckinResult(
        checked=False,
        checkin_date=today.isoformat(),
        current_streak=habit_streak(
            db, user.id, task.id, today, task.habit_frequency, task.habit_days
        ),
    )

