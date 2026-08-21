from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    tasks: Mapped[list["Task"]] = relationship(back_populates="user")
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
    plans: Mapped[list["Plan"]] = relationship(back_populates="user")
    task_checkins: Mapped[list["TaskCheckin"]] = relationship(back_populates="user")
    reviews: Mapped[list["Review"]] = relationship(back_populates="user")
    ai_config: Mapped["AIConfig | None"] = relationship(
        back_populates="user", uselist=False
    )
    math_progress: Mapped[list["MathProgress"]] = relationship(
        back_populates="user"
    )
    math_notes: Mapped[list["MathNote"]] = relationship(back_populates="user")
    settings: Mapped["UserSettings | None"] = relationship(
        back_populates="user", uselist=False
    )
    plan_templates: Mapped[list["PlanTemplate"]] = relationship(
        back_populates="user"
    )
    files: Mapped[list["StudyFile"]] = relationship(back_populates="user")


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(
        String(500), default="", server_default=""
    )
    status: Mapped[str] = mapped_column(
        String(10), default="todo", server_default="todo"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped["User"] = relationship(back_populates="plans")
    parent: Mapped["Plan | None"] = relationship(
        remote_side=[id], back_populates="children"
    )
    children: Mapped[list["Plan"]] = relationship(back_populates="parent")
    tasks: Mapped[list["Task"]] = relationship(back_populates="plan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(50), default="", server_default="")
    estimated_minutes: Mapped[int] = mapped_column(
        Integer, default=25, server_default="25"
    )
    status: Mapped[str] = mapped_column(
        String(10), default="todo", server_default="todo"
    )
    is_habit: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    habit_frequency: Mapped[str] = mapped_column(
        String(10), default="daily", server_default="daily", nullable=False
    )
    habit_days: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )

    user: Mapped["User"] = relationship(back_populates="tasks")
    plan: Mapped["Plan | None"] = relationship(back_populates="tasks")
    sessions: Mapped[list["Session"]] = relationship(back_populates="task")
    checkins: Mapped[list["TaskCheckin"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped["User"] = relationship(back_populates="sessions")
    task: Mapped["Task | None"] = relationship(back_populates="sessions")


class TaskCheckin(Base):
    __tablename__ = "task_checkins"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "task_id", "checkin_date", name="uq_task_checkin_per_day"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped["User"] = relationship(back_populates="task_checkins")
    task: Mapped["Task"] = relationship(back_populates="checkins")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(10), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped["User"] = relationship(back_populates="reviews")
class AIConfig(Base):
    __tablename__ = "ai_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False, unique=True
    )
    provider: Mapped[str] = mapped_column(
        String(30), default="custom", server_default="custom", nullable=False
    )
    base_url: Mapped[str] = mapped_column(
        String(300), default="https://api.openai.com/v1", nullable=False
    )
    model: Mapped[str] = mapped_column(
        String(100), default="gpt-4o-mini", nullable=False
    )
    api_key_encrypted: Mapped[str] = mapped_column(
        String(500), default="", server_default="", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    user: Mapped["User"] = relationship(back_populates="ai_config")


class MathChapter(Base):
    __tablename__ = "math_chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chapter_key: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    num: Mapped[str] = mapped_column(String(10), default="", server_default="")
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    short: Mapped[str] = mapped_column(String(100), default="", server_default="")
    note_label: Mapped[str] = mapped_column(String(100), default="", server_default="")
    note_placeholder: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    items: Mapped[list["MathItem"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan"
    )
    notes: Mapped[list["MathNote"]] = relationship(back_populates="chapter")


class MathItem(Base):
    __tablename__ = "math_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("math_chapters.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    item_key: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    sub_title: Mapped[str] = mapped_column(String(100), nullable=False)
    tag: Mapped[str] = mapped_column(String(20), default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    segments: Mapped[str] = mapped_column(Text, nullable=False)

    chapter: Mapped["MathChapter"] = relationship(back_populates="items")
    progress: Mapped[list["MathProgress"]] = relationship(back_populates="item")


class MathProgress(Base):
    __tablename__ = "math_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "item_id", name="uq_math_progress_per_item"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("math_items.id", ondelete="CASCADE"), index=True, nullable=False
    )
    done: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    user: Mapped["User"] = relationship(back_populates="math_progress")
    item: Mapped["MathItem"] = relationship(back_populates="progress")


class MathNote(Base):
    __tablename__ = "math_notes"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "chapter_id", name="uq_math_note_per_chapter"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("math_chapters.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, default="", server_default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    user: Mapped["User"] = relationship(back_populates="math_notes")
    chapter: Mapped["MathChapter"] = relationship(back_populates="notes")


class UserSettings(Base):
    """按账号的个性化设置；JSON 字段以文本存储。"""

    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, unique=True, nullable=False
    )
    theme_mode: Mapped[str] = mapped_column(
        String(10), default="system", server_default="system", nullable=False
    )
    accent: Mapped[str] = mapped_column(
        String(20), default="indigo", server_default="indigo", nullable=False
    )
    pomodoro_durations: Mapped[str] = mapped_column(
        Text, default="[25,45,60]", server_default="[25,45,60]", nullable=False
    )
    pomodoro_default: Mapped[int] = mapped_column(
        Integer, default=25, server_default="25", nullable=False
    )
    review_intervals: Mapped[str] = mapped_column(
        Text, default="[1,2,4,7,15,30]",
        server_default="[1,2,4,7,15,30]", nullable=False,
    )
    habit_frequency_default: Mapped[str] = mapped_column(
        String(10), default="daily", server_default="daily", nullable=False
    )
    default_estimated_minutes: Mapped[int] = mapped_column(
        Integer, default=25, server_default="25", nullable=False
    )
    hub_cards: Mapped[str] = mapped_column(
        Text, default="[]", server_default="[]", nullable=False
    )
    task_subjects: Mapped[str] = mapped_column(
        Text, default="[]", server_default="[]", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    user: Mapped["User"] = relationship(back_populates="settings")


class PlanTemplate(Base):
    """用户自建的计划拆解模板（children 为 JSON 数组）。"""

    __tablename__ = "plan_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    children: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped["User"] = relationship(back_populates="plan_templates")


class StudyFile(Base):
    """用户上传的学习文件。

    - 磁盘按用户分目录隔离，文件名一律用 UUID 重命名；
    - status：uploaded / approved / rejected / quarantined；
    - scan_status：pending / clean / infected / error（查杀病毒预留）；
    - integrated：运营是否已把文件整合进学习内容。
    """

    __tablename__ = "study_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ext: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(100), default="", server_default=""
    )
    category: Mapped[str] = mapped_column(String(50), default="", server_default="")
    description: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    status: Mapped[str] = mapped_column(
        String(20), default="uploaded", server_default="uploaded", nullable=False
    )
    scan_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    scan_message: Mapped[str] = mapped_column(
        String(300), default="", server_default=""
    )
    integrated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    is_recommended: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    admin_note: Mapped[str] = mapped_column(
        String(500), default="", server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    user: Mapped["User"] = relationship(back_populates="files")

class ScanLog(Base):
    """安全中心：全量杀毒扫描日志（只记录扫描结果，不触碰用户文件内容）。"""

    __tablename__ = "scan_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    triggered_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual", nullable=False
    )
    total_files: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    clean_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    infected_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    error_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    message: Mapped[str] = mapped_column(
        String(300), default="", server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MathResource(Base):
    """高数资料：管理员发布的共享学习资料（用户只读浏览/下载）。"""

    __tablename__ = "math_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(
        String(500), default="", server_default=""
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ext: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    content_type: Mapped[str] = mapped_column(
        String(100), default="", server_default=""
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class InviteCode(Base):
    """管理员生成的注册邀请码（按次数与有效期控制使用者人数）。"""

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    max_uses: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    used_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    remark: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
