"""用户信息储存系统的数据模型（纯标准库）。

用 Python 类（@dataclass）表示每条记录，聚合类 UserData 表示一个用户的全部数据。
数据容器约定：
- dict：JSON 载荷（to_dict / from_dict）；
- tuple：不可变集合与状态枚举（如 TASK_STATUSES、UserData 中的记录集合）；
- str：标识 / 状态 / 日期；
- set / tuple：去重与白名单。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

# ---------------- 状态常量（tuple 枚举） ----------------
TASK_STATUSES = ("todo", "doing", "done")
PLAN_STATUSES = ("todo", "doing", "done")
HABIT_FREQUENCIES = ("daily", "weekdays", "custom")
THEME_MODES = ("light", "dark", "system")
ACCENTS = ("indigo", "green", "rose", "amber", "violet")
FILE_STATUSES = ("uploaded", "approved", "rejected", "quarantined")
SCAN_STATUSES = ("pending", "clean", "infected", "error")
SOURCE_TYPES = ("task", "plan")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,50}$")


def validate_username(username: Any) -> str:
    """校验用户名：3-50 位字母 / 数字 / 下划线。"""
    if not isinstance(username, str) or not USERNAME_RE.fullmatch(username):
        raise ValueError(
            f"非法用户名：{username!r}（仅允许 3-50 位字母/数字/下划线）"
        )
    return username


def _text(value: Any, default: str = "", limit: int | None = None) -> str:
    text = str(value) if value is not None else default
    return text[:limit] if limit else text


def _int(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if low <= number <= high else default


def _opt_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return _int(value, 0, 0, 2**31 - 1) or None


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value) if value is not None else default


def _str_list(value: Any) -> tuple[str, ...]:
    items = value if isinstance(value, list) else []
    return tuple(_text(item, "", 500) for item in items if item not in (None, ""))


def _int_list(value: Any, low: int, high: int) -> tuple[int, ...]:
    items = value if isinstance(value, list) else []
    return tuple(
        number for number in (_int(item, low - 1, low, high) for item in items)
        if low <= number <= high
    )


def _dict_list(value: Any) -> tuple[dict[str, Any], ...]:
    items = value if isinstance(value, list) else []
    return tuple(item for item in items if isinstance(item, dict))


def _enum(value: Any, allowed: tuple[str, ...], default: str, label: str) -> str:
    text = _text(value, default, 20)
    if text not in allowed:
        raise ValueError(f"非法{label}：{text!r}（允许：{', '.join(allowed)}）")
    return text


# ---------------- 记录类 ----------------


@dataclass(frozen=True)
class UserInfo:
    """账号信息：用户名 / 密码哈希（不透明字符串）/ 创建时间。"""

    username: str
    password_hash: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "UserInfo":
        payload = payload or {}
        return cls(
            username=_text(payload.get("username"), "", 50),
            password_hash=_text(payload.get("password_hash"), "", 255),
            created_at=_text(payload.get("created_at"), "", 40),
        )


@dataclass(frozen=True)
class TaskRecord:
    id: int
    title: str
    plan_id: int | None = None
    subject: str = ""
    estimated_minutes: int = 25
    status: str = "todo"
    is_habit: bool = False
    habit_frequency: str = "daily"
    habit_days: tuple[int, ...] = ()
    created_at: str = ""
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "title": self.title,
            "subject": self.subject,
            "estimated_minutes": self.estimated_minutes,
            "status": self.status,
            "is_habit": self.is_habit,
            "habit_frequency": self.habit_frequency,
            "habit_days": list(self.habit_days),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "TaskRecord":
        payload = payload or {}
        return cls(
            id=_int(payload.get("id"), 0, 1, 2**31 - 1),
            plan_id=_opt_int(payload.get("plan_id")),
            title=_text(payload.get("title"), "", 200),
            subject=_text(payload.get("subject"), "", 50),
            estimated_minutes=_int(payload.get("estimated_minutes"), 25, 1, 600),
            status=_enum(payload.get("status"), TASK_STATUSES, "todo", "任务状态"),
            is_habit=_bool(payload.get("is_habit")),
            habit_frequency=_enum(
                payload.get("habit_frequency"), HABIT_FREQUENCIES, "daily", "习惯频率"
            ),
            habit_days=_int_list(payload.get("habit_days"), 1, 7),
            created_at=_text(payload.get("created_at"), "", 40),
            completed_at=_text(payload.get("completed_at"), "", 40) or None,
        )


@dataclass(frozen=True)
class PlanRecord:
    id: int
    title: str
    parent_id: int | None = None
    description: str = ""
    status: str = "todo"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "PlanRecord":
        payload = payload or {}
        return cls(
            id=_int(payload.get("id"), 0, 1, 2**31 - 1),
            parent_id=_opt_int(payload.get("parent_id")),
            title=_text(payload.get("title"), "", 100),
            description=_text(payload.get("description"), "", 500),
            status=_enum(payload.get("status"), PLAN_STATUSES, "todo", "计划状态"),
            created_at=_text(payload.get("created_at"), "", 40),
        )


@dataclass(frozen=True)
class SessionRecord:
    id: int
    duration_minutes: int
    task_id: int | None = None
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "duration_minutes": self.duration_minutes,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "SessionRecord":
        payload = payload or {}
        return cls(
            id=_int(payload.get("id"), 0, 1, 2**31 - 1),
            task_id=_opt_int(payload.get("task_id")),
            duration_minutes=_int(payload.get("duration_minutes"), 25, 1, 600),
            started_at=_text(payload.get("started_at"), "", 40),
            completed_at=_text(payload.get("completed_at"), "", 40),
        )


@dataclass(frozen=True)
class CheckinRecord:
    id: int
    task_id: int
    checkin_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "checkin_date": self.checkin_date,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "CheckinRecord":
        payload = payload or {}
        return cls(
            id=_int(payload.get("id"), 0, 1, 2**31 - 1),
            task_id=_int(payload.get("task_id"), 0, 1, 2**31 - 1),
            checkin_date=_text(payload.get("checkin_date"), "", 20),
        )


@dataclass(frozen=True)
class ReviewRecord:
    id: int
    source_type: str
    source_id: int
    due_date: str
    interval_days: int = 1
    reviewed_at: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "due_date": self.due_date,
            "interval_days": self.interval_days,
            "reviewed_at": self.reviewed_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ReviewRecord":
        payload = payload or {}
        return cls(
            id=_int(payload.get("id"), 0, 1, 2**31 - 1),
            source_type=_enum(payload.get("source_type"), SOURCE_TYPES, "task", "复习来源"),
            source_id=_int(payload.get("source_id"), 0, 1, 2**31 - 1),
            due_date=_text(payload.get("due_date"), "", 20),
            interval_days=_int(payload.get("interval_days"), 1, 1, 365),
            reviewed_at=_text(payload.get("reviewed_at"), "", 40) or None,
            created_at=_text(payload.get("created_at"), "", 40),
        )


@dataclass(frozen=True)
class SettingsRecord:
    theme_mode: str = "system"
    accent: str = "indigo"
    pomodoro_durations: tuple[int, ...] = (25, 45, 60)
    pomodoro_default: int = 25
    review_intervals: tuple[int, ...] = (1, 2, 4, 7, 15, 30)
    habit_frequency_default: str = "daily"
    default_estimated_minutes: int = 25
    hub_cards: tuple[dict[str, Any], ...] = ()
    task_subjects: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme_mode": self.theme_mode,
            "accent": self.accent,
            "pomodoro_durations": list(self.pomodoro_durations),
            "pomodoro_default": self.pomodoro_default,
            "review_intervals": list(self.review_intervals),
            "habit_frequency_default": self.habit_frequency_default,
            "default_estimated_minutes": self.default_estimated_minutes,
            "hub_cards": list(self.hub_cards),
            "task_subjects": list(self.task_subjects),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "SettingsRecord":
        payload = payload or {}
        durations = _int_list(payload.get("pomodoro_durations"), 1, 180)
        if not durations:
            durations = (25, 45, 60)
        intervals = _int_list(payload.get("review_intervals"), 1, 365)
        if not intervals:
            intervals = (1, 2, 4, 7, 15, 30)
        default = _int(payload.get("pomodoro_default"), durations[0], 1, 180)
        if default not in durations:
            default = durations[0]
        return cls(
            theme_mode=_enum(
                payload.get("theme_mode"), THEME_MODES, "system", "主题模式"
            ),
            accent=_enum(payload.get("accent"), ACCENTS, "indigo", "强调色"),
            pomodoro_durations=durations,
            pomodoro_default=default,
            review_intervals=intervals,
            habit_frequency_default=_enum(
                payload.get("habit_frequency_default"),
                HABIT_FREQUENCIES,
                "daily",
                "习惯默认频率",
            ),
            default_estimated_minutes=_int(
                payload.get("default_estimated_minutes"), 25, 1, 600
            ),
            hub_cards=_dict_list(payload.get("hub_cards")),
            task_subjects=_str_list(payload.get("task_subjects")),
        )


@dataclass(frozen=True)
class PlanTemplateRecord:
    id: int
    name: str
    children: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "children": list(self.children)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "PlanTemplateRecord":
        payload = payload or {}
        return cls(
            id=_int(payload.get("id"), 0, 1, 2**31 - 1),
            name=_text(payload.get("name"), "", 50),
            children=_dict_list(payload.get("children")),
        )


@dataclass(frozen=True)
class MathNoteRecord:
    chapter_key: str
    content: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"chapter_key": self.chapter_key, "content": self.content}

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "MathNoteRecord":
        payload = payload or {}
        return cls(
            chapter_key=_text(payload.get("chapter_key"), "", 30),
            content=_text(payload.get("content"), "", 5000),
        )


@dataclass(frozen=True)
class AIConfigRecord:
    provider: str = "custom"
    base_url: str = ""
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "AIConfigRecord":
        payload = payload or {}
        return cls(
            provider=_text(payload.get("provider"), "custom", 30),
            base_url=_text(payload.get("base_url"), "", 300),
            model=_text(payload.get("model"), "", 100),
        )


@dataclass(frozen=True)
class FileMeta:
    """上传文件元数据（二进制留在 uploads 目录，此处只存索引）。"""

    file_id: str
    original_name: str
    ext: str
    size_bytes: int = 0
    category: str = ""
    description: str = ""
    status: str = "uploaded"
    scan_status: str = "pending"
    scan_message: str = ""
    integrated: bool = False
    admin_note: str = ""
    uploaded_at: str = ""

    def stored_name(self) -> str:
        return f"{self.file_id}{self.ext}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "original_name": self.original_name,
            "ext": self.ext,
            "size_bytes": self.size_bytes,
            "category": self.category,
            "description": self.description,
            "status": self.status,
            "scan_status": self.scan_status,
            "scan_message": self.scan_message,
            "integrated": self.integrated,
            "admin_note": self.admin_note,
            "uploaded_at": self.uploaded_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "FileMeta":
        payload = payload or {}
        return cls(
            file_id=_text(payload.get("file_id"), "", 64),
            original_name=_text(payload.get("original_name"), "", 255),
            ext=_text(payload.get("ext"), "", 20),
            size_bytes=_int(payload.get("size_bytes"), 0, 0, 2**31 - 1),
            category=_text(payload.get("category"), "", 50),
            description=_text(payload.get("description"), "", 200),
            status=_enum(payload.get("status"), FILE_STATUSES, "uploaded", "文件状态"),
            scan_status=_enum(
                payload.get("scan_status"), SCAN_STATUSES, "pending", "扫描状态"
            ),
            scan_message=_text(payload.get("scan_message"), "", 300),
            integrated=_bool(payload.get("integrated")),
            admin_note=_text(payload.get("admin_note"), "", 500),
            uploaded_at=_text(payload.get("uploaded_at"), "", 40),
        )


# ---------------- 聚合类 ----------------


@dataclass(frozen=True)
class UserData:
    """一个用户的全部数据（JSON 主文件的载荷）。"""

    user: UserInfo
    tasks: tuple[TaskRecord, ...] = ()
    plans: tuple[PlanRecord, ...] = ()
    sessions: tuple[SessionRecord, ...] = ()
    checkins: tuple[CheckinRecord, ...] = ()
    reviews: tuple[ReviewRecord, ...] = ()
    settings: SettingsRecord | None = None
    plan_templates: tuple[PlanTemplateRecord, ...] = ()
    math_progress: tuple[str, ...] = ()
    math_notes: tuple[MathNoteRecord, ...] = ()
    ai_config: AIConfigRecord | None = None
    files: tuple[FileMeta, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "user": self.user.to_dict(),
            "tasks": [task.to_dict() for task in self.tasks],
            "plans": [plan.to_dict() for plan in self.plans],
            "sessions": [session.to_dict() for session in self.sessions],
            "checkins": [checkin.to_dict() for checkin in self.checkins],
            "reviews": [review.to_dict() for review in self.reviews],
            "settings": self.settings.to_dict() if self.settings else None,
            "plan_templates": [
                template.to_dict() for template in self.plan_templates
            ],
            "math_progress": list(self.math_progress),
            "math_notes": [note.to_dict() for note in self.math_notes],
            "ai_config": self.ai_config.to_dict() if self.ai_config else None,
            "files": [file_meta.to_dict() for file_meta in self.files],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "UserData":
        payload = payload or {}

        def _records(record_type, key: str):
            items = payload.get(key) or []
            return tuple(
                record_type.from_dict(item) for item in items if isinstance(item, dict)
            )

        return cls(
            user=UserInfo.from_dict(payload.get("user")),
            tasks=_records(TaskRecord, "tasks"),
            plans=_records(PlanRecord, "plans"),
            sessions=_records(SessionRecord, "sessions"),
            checkins=_records(CheckinRecord, "checkins"),
            reviews=_records(ReviewRecord, "reviews"),
            settings=(
                SettingsRecord.from_dict(payload["settings"])
                if isinstance(payload.get("settings"), dict)
                else None
            ),
            plan_templates=_records(PlanTemplateRecord, "plan_templates"),
            math_progress=_str_list(payload.get("math_progress")),
            math_notes=_records(MathNoteRecord, "math_notes"),
            ai_config=(
                AIConfigRecord.from_dict(payload["ai_config"])
                if isinstance(payload.get("ai_config"), dict)
                else None
            ),
            files=_records(FileMeta, "files"),
        )

    def with_user(self, username: str) -> "UserData":
        """返回复制品，并把账号名替换为指定用户（用于恢复）。"""
        validate_username(username)
        return replace(self, user=replace(self.user, username=username))
