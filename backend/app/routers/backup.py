"""数据备份：导出当前账号全部数据 / 从备份 JSON 恢复（覆盖式）。"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    AIConfig,
    MathChapter,
    MathItem,
    MathNote,
    MathProgress,
    Plan,
    PlanTemplate,
    Review,
    Session as StudySession,
    Task,
    TaskCheckin,
    User,
    UserSettings,
)
from .settings import _get_or_create, _merged, _validate_and_apply
from ..security import get_current_user

router = APIRouter(prefix="/api/backup", tags=["backup"])

SCHEMA_VERSION = 1
TASK_STATUSES = {"todo", "doing", "done"}


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _status(value, default: str = "todo") -> str:
    return value if value in TASK_STATUSES else default


def _text(value, default: str = "", limit: int | None = None) -> str:
    text = str(value) if value is not None else default
    return text[:limit] if limit else text


def _int(value, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if low <= number <= high else default


def _entry_id(entry: dict, label: str) -> int:
    """备份条目缺少有效 id 时给出明确 400，而不是 500。"""
    try:
        return int(entry["id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=400, detail=f"{label} 条目缺少有效 id"
        )


@router.get("/export")
def export_backup(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    tasks = db.scalars(
        select(Task).where(Task.user_id == user.id).order_by(Task.id)
    ).all()
    plans = db.scalars(
        select(Plan).where(Plan.user_id == user.id).order_by(Plan.id)
    ).all()
    sessions = db.scalars(
        select(StudySession).where(StudySession.user_id == user.id).order_by(
            StudySession.id
        )
    ).all()
    checkins = db.scalars(
        select(TaskCheckin).where(TaskCheckin.user_id == user.id).order_by(
            TaskCheckin.id
        )
    ).all()
    reviews = db.scalars(
        select(Review).where(Review.user_id == user.id).order_by(Review.id)
    ).all()
    ai_config = db.scalar(
        select(AIConfig).where(AIConfig.user_id == user.id)
    )
    progress = db.scalars(
        select(MathProgress).where(MathProgress.user_id == user.id)
    ).all()
    notes = db.scalars(
        select(MathNote).where(MathNote.user_id == user.id)
    ).all()

    item_keys = {}
    if progress:
        item_rows = db.scalars(select(MathItem)).all()
        item_keys = {row.id: row.item_key for row in item_rows}
    chapter_keys = {}
    if notes:
        chapter_rows = db.scalars(select(MathChapter)).all()
        chapter_keys = {row.id: row.chapter_key for row in chapter_rows}

    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "user": {"id": user.id, "username": user.username},
        "data": {
            "plans": [
                {
                    "id": plan.id,
                    "parent_id": plan.parent_id,
                    "title": plan.title,
                    "description": plan.description,
                    "status": plan.status,
                    "created_at": _iso(plan.created_at),
                }
                for plan in plans
            ],
            "tasks": [
                {
                    "id": task.id,
                    "plan_id": task.plan_id,
                    "title": task.title,
                    "subject": task.subject,
                    "estimated_minutes": task.estimated_minutes,
                    "status": task.status,
                    "is_habit": task.is_habit,
                    "habit_frequency": task.habit_frequency,
                    "created_at": _iso(task.created_at),
                    "completed_at": _iso(task.completed_at),
                }
                for task in tasks
            ],
            "sessions": [
                {
                    "task_id": session.task_id,
                    "duration_minutes": session.duration_minutes,
                    "started_at": _iso(session.started_at),
                    "completed_at": _iso(session.completed_at),
                }
                for session in sessions
            ],
            "checkins": [
                {
                    "task_id": checkin.task_id,
                    "checkin_date": checkin.checkin_date.isoformat(),
                }
                for checkin in checkins
            ],
            "reviews": [
                {
                    "source_type": review.source_type,
                    "source_id": review.source_id,
                    "due_date": review.due_date.isoformat(),
                    "interval_days": review.interval_days,
                    "reviewed_at": _iso(review.reviewed_at),
                    "created_at": _iso(review.created_at),
                }
                for review in reviews
            ],
            # 注意：API Key 加密存储，不随备份导出；导入后需在「AI 设置」重新填写
            "ai_config": (
                {
                    "provider": ai_config.provider,
                    "base_url": ai_config.base_url,
                    "model": ai_config.model,
                }
                if ai_config is not None
                else None
            ),
            "math_progress": [
                item_keys.get(row.item_id) for row in progress if row.done
            ],
            "math_notes": {
                chapter_keys.get(row.chapter_id): row.content
                for row in notes
                if row.chapter_id in chapter_keys
            },
            "settings": _merged(_get_or_create(db, user.id)),
            "plan_templates": [
                {
                    "name": template.name,
                    "children": json.loads(template.children or "[]"),
                }
                for template in db.scalars(
                    select(PlanTemplate).where(
                        PlanTemplate.user_id == user.id
                    )
                ).all()
            ],
        },
    }


@router.post("/import")
def import_backup(
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise HTTPException(
            status_code=400,
            detail="备份文件版本不支持（需要 schema_version=1）",
        )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="备份文件缺少 data 字段")
    for key in ("plans", "tasks", "sessions", "checkins", "reviews"):
        if key in data and not isinstance(data[key], list):
            raise HTTPException(status_code=400, detail=f"{key} 字段格式不正确")

    # 1) 清空当前账号现有数据（覆盖式恢复）
    db.execute(delete(MathNote).where(MathNote.user_id == user.id))
    db.execute(delete(MathProgress).where(MathProgress.user_id == user.id))
    db.execute(delete(Review).where(Review.user_id == user.id))
    db.execute(delete(StudySession).where(StudySession.user_id == user.id))
    db.execute(delete(TaskCheckin).where(TaskCheckin.user_id == user.id))
    db.execute(delete(Task).where(Task.user_id == user.id))
    db.execute(delete(Plan).where(Plan.user_id == user.id))
    db.execute(delete(AIConfig).where(AIConfig.user_id == user.id))
    db.execute(delete(UserSettings).where(UserSettings.user_id == user.id))
    db.execute(delete(PlanTemplate).where(PlanTemplate.user_id == user.id))
    db.flush()

    counts = {
        "plans": 0,
        "tasks": 0,
        "sessions": 0,
        "checkins": 0,
        "reviews": 0,
        "ai_config": 0,
        "math_progress": 0,
        "math_notes": 0,
        "settings": 0,
        "plan_templates": 0,
    }

    # 2) 计划（先建行拿新 id，再回填父子关系）
    plan_map: dict[int, int] = {}
    for plan in data.get("plans", []):
        row = Plan(
            user_id=user.id,
            title=_text(plan.get("title"), "未命名计划", 100),
            description=_text(plan.get("description"), "", 500),
            status=_status(plan.get("status"), "todo"),
            created_at=_parse_dt(plan.get("created_at")),
        )
        db.add(row)
        db.flush()
        plan_map[_entry_id(plan, "计划")] = row.id
        counts["plans"] += 1
    for plan in data.get("plans", []):
        parent_id = plan.get("parent_id")
        if parent_id is not None and int(parent_id) in plan_map:
            row = db.get(Plan, plan_map[_entry_id(plan, "计划")])
            if row is not None:
                row.parent_id = plan_map[int(parent_id)]
    db.flush()

    # 3) 任务（plan_id 重映射）
    task_map: dict[int, int] = {}
    for task in data.get("tasks", []):
        plan_id = task.get("plan_id")
        row = Task(
            user_id=user.id,
            plan_id=plan_map[int(plan_id)] if plan_id in plan_map else None,
            title=_text(task.get("title"), "未命名任务", 200),
            subject=_text(task.get("subject"), "", 50),
            estimated_minutes=_int(task.get("estimated_minutes"), 25, 1, 600),
            status=_status(task.get("status"), "todo"),
            is_habit=bool(task.get("is_habit", False)),
            habit_frequency=(
                task.get("habit_frequency")
                if task.get("habit_frequency") in ("daily",)
                else "daily"
            ),
            created_at=_parse_dt(task.get("created_at")),
            completed_at=_parse_dt(task.get("completed_at")),
        )
        db.add(row)
        db.flush()
        task_map[_entry_id(task, "任务")] = row.id
        counts["tasks"] += 1

    # 4) 专注记录
    for session in data.get("sessions", []):
        task_id = session.get("task_id")
        db.add(
            StudySession(
                user_id=user.id,
                task_id=task_map[int(task_id)] if task_id in task_map else None,
                duration_minutes=_int(
                    session.get("duration_minutes"), 25, 1, 600
                ),
                started_at=_parse_dt(session.get("started_at")),
                completed_at=_parse_dt(session.get("completed_at")),
            )
        )
        counts["sessions"] += 1

    # 5) 习惯打卡（按 任务+日期 去重，避免唯一约束冲突）
    seen_checkins: set[tuple[int, str]] = set()
    for checkin in data.get("checkins", []):
        task_id = checkin.get("task_id")
        if task_id not in task_map:
            continue
        checkin_date = _parse_date(checkin.get("checkin_date"))
        if checkin_date is None:
            continue
        key = (task_map[int(task_id)], checkin_date.isoformat())
        if key in seen_checkins:
            continue
        seen_checkins.add(key)
        db.add(
            TaskCheckin(
                user_id=user.id,
                task_id=task_map[int(task_id)],
                checkin_date=checkin_date,
            )
        )
        counts["checkins"] += 1

    # 6) 复习节点（任务/计划 id 重映射）
    for review in data.get("reviews", []):
        source_type = (
            review.get("source_type")
            if review.get("source_type") in ("task", "plan")
            else "task"
        )
        source_id = review.get("source_id")
        source_map = task_map if source_type == "task" else plan_map
        if source_id not in source_map:
            continue
        db.add(
            Review(
                user_id=user.id,
                source_type=source_type,
                source_id=source_map[int(source_id)],
                due_date=_parse_date(review.get("due_date")) or date.today(),
                interval_days=_int(review.get("interval_days"), 1, 1, 365),
                reviewed_at=_parse_dt(review.get("reviewed_at")),
                created_at=_parse_dt(review.get("created_at")),
            )
        )
        counts["reviews"] += 1

    # 7) AI 配置（API Key 无法恢复，仅恢复服务商/地址/模型）
    ai_config = data.get("ai_config")
    if isinstance(ai_config, dict) and ai_config.get("base_url"):
        db.add(
            AIConfig(
                user_id=user.id,
                provider=_text(ai_config.get("provider"), "custom", 30),
                base_url=_text(ai_config.get("base_url"), "", 300),
                model=_text(ai_config.get("model"), "", 100),
            )
        )
        counts["ai_config"] = 1

    # 8) 个性化设置与计划模板
    settings_data = data.get("settings")
    if isinstance(settings_data, dict):
        row = UserSettings(user_id=user.id)
        db.add(row)
        db.flush()
        _validate_and_apply(db, row, settings_data, commit=False)
        counts["settings"] = 1
    for template in data.get("plan_templates", []):
        if not isinstance(template, dict) or not template.get("name"):
            continue
        children = template.get("children")
        if not isinstance(children, list) or not children:
            continue
        db.add(
            PlanTemplate(
                user_id=user.id,
                name=str(template["name"])[:50],
                children=json.dumps(
                    [
                        {
                            "title": str(child.get("title", ""))[:100],
                            "description": str(child.get("description", ""))[:500],
                        }
                        for child in children
                        if isinstance(child, dict)
                    ],
                    ensure_ascii=False,
                ),
            )
        )
        counts["plan_templates"] += 1

    # 9) 高数进度与笔记（按内容键映射）
    item_key_map = {}
    progress_keys = data.get("math_progress")
    if progress_keys:
        item_rows = db.scalars(select(MathItem)).all()
        item_key_map = {row.item_key: row.id for row in item_rows}
        for item_key in dict.fromkeys(progress_keys):
            item_id = item_key_map.get(item_key)
            if item_id is None:
                continue
            db.add(
                MathProgress(user_id=user.id, item_id=item_id, done=True)
            )
            counts["math_progress"] += 1

    chapter_key_map = {}
    math_notes = data.get("math_notes")
    if isinstance(math_notes, dict):
        chapter_rows = db.scalars(select(MathChapter)).all()
        chapter_key_map = {row.chapter_key: row.id for row in chapter_rows}
        for chapter_key, content in math_notes.items():
            chapter_id = chapter_key_map.get(chapter_key)
            if chapter_id is None:
                continue
            db.add(
                MathNote(
                    user_id=user.id,
                    chapter_id=chapter_id,
                    content=_text(content, "", 5000),
                )
            )
            counts["math_notes"] += 1

    db.commit()
    return {"ok": True, "schema_version": SCHEMA_VERSION, "counts": counts}
