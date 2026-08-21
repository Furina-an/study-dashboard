from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    subject: str = Field("", max_length=50)
    estimated_minutes: int = Field(25, ge=1, le=600)
    status: str = Field("todo", pattern="^(todo|doing|done)$")
    plan_id: int | None = None
    is_habit: bool = False
    habit_frequency: str = Field("daily", pattern="^(daily|weekdays|custom)$")
    habit_days: list[int] | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    subject: str | None = Field(None, max_length=50)
    estimated_minutes: int | None = Field(None, ge=1, le=600)
    status: str | None = Field(None, pattern="^(todo|doing|done)$")
    plan_id: int | None = Field(None)
    is_habit: bool | None = None
    habit_frequency: str | None = Field(None, pattern="^(daily|weekdays|custom)$")
    habit_days: list[int] | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    subject: str
    estimated_minutes: int
    status: str
    plan_id: int | None
    is_habit: bool
    habit_frequency: str
    habit_days: list[int] | None
    created_at: datetime
    completed_at: datetime | None


class SessionCreate(BaseModel):
    task_id: int | None = None
    duration_minutes: int = Field(..., ge=1, le=600)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int | None
    duration_minutes: int
    started_at: datetime
    completed_at: datetime


class TodayStats(BaseModel):
    date: str
    focus_minutes: int
    focus_count: int
    tasks_completed: int


class TrendPoint(BaseModel):
    date: str
    focus_minutes: int
    focus_count: int


class HeatmapPoint(BaseModel):
    date: str
    focus_minutes: int


class StreakStats(BaseModel):
    current_streak: int
    best_streak: int
    focused_days: int
    total_focus_minutes: int


class HabitDay(BaseModel):
    date: str
    checked: bool


class HabitOut(BaseModel):
    id: int
    title: str
    subject: str
    estimated_minutes: int
    status: str
    plan_id: int | None
    is_habit: bool
    habit_frequency: str
    habit_days: list[int] | None = None
    checked_today: bool
    scheduled_today: bool = True
    current_streak: int
    last_7_days: list[HabitDay]


class CheckinResult(BaseModel):
    checked: bool
    checkin_date: str
    current_streak: int


class ReviewOut(BaseModel):
    id: int
    source_type: str
    source_id: int
    source_title: str
    due_date: str
    interval_days: int
    reviewed_at: datetime | None
    created_at: datetime


class ReviewCompleteResult(BaseModel):
    completed: int


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(..., min_length=6, max_length=72)
    invite_code: str = Field(..., min_length=1, max_length=100)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime
    is_admin: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class FileOut(BaseModel):
    id: int
    user_id: int
    owner_username: str = ""
    original_name: str
    ext: str
    size_bytes: int
    content_type: str
    category: str
    description: str
    status: str
    scan_status: str
    scan_message: str = ""
    integrated: bool
    is_recommended: bool = False
    admin_note: str
    created_at: datetime
    updated_at: datetime


class FileUpdate(BaseModel):
    status: str | None = Field(
        None, pattern="^(uploaded|approved|rejected|quarantined)$"
    )
    scan_status: str | None = Field(None, pattern="^(pending|clean|infected|error)$")
    integrated: bool | None = None
    is_recommended: bool | None = None
    admin_note: str | None = Field(None, max_length=500)
    category: str | None = Field(None, max_length=50)
    description: str | None = Field(None, max_length=200)


class PlanCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)
    parent_id: int | None = None
    status: str = Field("todo", pattern="^(todo|doing|done)$")


class PlanUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    status: str | None = Field(None, pattern="^(todo|doing|done)$")
    parent_id: int | None = Field(None)


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None
    title: str
    description: str
    status: str
    created_at: datetime


class BreakdownRequest(BaseModel):
    mode: str = Field(..., pattern="^(template|ai)$")
    template_key: str | None = Field(None, max_length=50)
    template_id: int | None = None


class BreakdownResult(BaseModel):
    created: list[PlanOut]
class AIConfigOut(BaseModel):
    provider: str
    base_url: str
    model: str
    api_key_masked: str
    has_api_key: bool
    updated_at: datetime | None


class AIConfigUpdate(BaseModel):
    provider: str = Field("custom", max_length=30)
    base_url: str = Field(..., min_length=1, max_length=300)
    model: str = Field(..., min_length=1, max_length=100)
    # 留空表示保留已保存的 key
    api_key: str | None = Field(None, max_length=500)


class AITestRequest(BaseModel):
    provider: str | None = Field(None, max_length=30)
    base_url: str | None = Field(None, max_length=300)
    model: str | None = Field(None, max_length=100)
    api_key: str | None = Field(None, max_length=500)


class AITestResult(BaseModel):
    ok: bool
    message: str
    latency_ms: int | None = None


class MathSegment(BaseModel):
    t: str = "text"
    v: str | None = None
    tex: str | None = None
    fallback: str | None = None
    block: bool = False


class MathItemOut(BaseModel):
    id: int
    item_key: str
    tag: str
    done: bool = False
    segments: list[MathSegment]


class MathSubOut(BaseModel):
    title: str
    tag: str
    items: list[MathItemOut]


class MathChapterOut(BaseModel):
    id: int
    chapter_key: str
    num: str
    title: str
    short: str
    note: str = ""
    note_label: str = ""
    note_placeholder: str = ""
    done: int = 0
    total: int = 0
    subs: list[MathSubOut]


class MathTreeOut(BaseModel):
    chapters: list[MathChapterOut]
    done: int = 0
    total: int = 0


class MathProgressUpdate(BaseModel):
    done: bool


class MathNoteUpdate(BaseModel):
    content: str = Field("", max_length=5000)



class HubCardSetting(BaseModel):
    key: str
    visible: bool = True
    order: int = 0


class UserSettingsOut(BaseModel):
    theme_mode: str
    accent: str
    pomodoro_durations: list[int]
    pomodoro_default: int
    review_intervals: list[int]
    habit_frequency_default: str
    default_estimated_minutes: int
    hub_cards: list[HubCardSetting]
    task_subjects: list[str]
    max_upload_mb: int = 20


class UserSettingsUpdate(BaseModel):
    theme_mode: str | None = None
    accent: str | None = None
    pomodoro_durations: list[int] | None = None
    pomodoro_default: int | None = Field(None, ge=1, le=180)
    review_intervals: list[int] | None = None
    habit_frequency_default: str | None = None
    default_estimated_minutes: int | None = Field(None, ge=1, le=600)
    hub_cards: list[HubCardSetting] | None = None
    task_subjects: list[str] | None = None


class PlanTemplateChild(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)


class PlanTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    children: list[PlanTemplateChild] = Field(..., min_length=1, max_length=20)


class PlanTemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    children: list[PlanTemplateChild] | None = Field(
        None, min_length=1, max_length=20
    )


class PlanTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    children: list[PlanTemplateChild]
    created_at: datetime


# ---------------- 管理员：邀请码生成与控制 ----------------


class InviteCreate(BaseModel):
    count: int = Field(1, ge=1, le=50)
    max_uses: int = Field(1, ge=1, le=1000)
    expires_days: int | None = Field(None, ge=1, le=3650)
    remark: str = Field("", max_length=200)


class InviteUpdate(BaseModel):
    active: bool | None = None
    max_uses: int | None = Field(None, ge=1, le=1000)
    remark: str | None = Field(None, max_length=200)


class InviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    created_by: int | None
    max_uses: int
    used_count: int
    expires_at: datetime | None
    active: bool
    remark: str
    created_at: datetime

    @property
    def remaining(self) -> int:
        return max(0, self.max_uses - self.used_count)


class AdminUserUpdate(BaseModel):
    is_active: bool


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime
    is_active: bool = True
    is_admin: bool = False


class AdminStatsOut(BaseModel):
    total_users: int
    total_invites: int
    active_invites: int
    unused_invites: int


# ---------------- 安全中心：杀毒扫描 ----------------

class ScanSummaryOut(BaseModel):
    total_files: int
    pending: int
    clean: int
    infected: int
    error: int
    scan_command_configured: bool
    scan_command: str


class ScanLogOut(BaseModel):
    id: int
    action: str
    total_files: int
    clean_count: int
    infected_count: int
    error_count: int
    skipped_count: int
    message: str
    created_at: datetime


class ScanAllResult(BaseModel):
    total: int
    clean: int
    infected: int
    error: int
    pending: int
    skipped: int
    message: str


# ---------------- 高数资料（管理员共享区） ----------------

class MathResourceCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)


class MathResourceUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class MathResourceOut(BaseModel):
    id: int
    title: str
    description: str
    original_name: str
    ext: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime
