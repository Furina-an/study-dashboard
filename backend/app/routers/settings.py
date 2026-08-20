"""个性化设置：按账号存储，所有值以完整形态读写。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, UserSettings
from ..schemas import UserSettingsOut, UserSettingsUpdate
from ..security import get_current_user
from .. import storage

router = APIRouter(prefix="/api/settings", tags=["settings"])

ACCENTS = {"indigo", "green", "rose", "amber", "violet"}
HUB_CARD_KEYS = ["math", "pomodoro", "tasks", "plans", "reviews", "stats", "ai", "files"]
DEFAULT_POMODORO_DURATIONS = [25, 45, 60]
DEFAULT_REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30]


def _json_list(value: str | None, fallback: list):
    try:
        parsed = json.loads(value or "")
        return parsed if isinstance(parsed, list) else list(fallback)
    except (TypeError, ValueError):
        return list(fallback)


def _default_hub_cards() -> list[dict]:
    return [
        {"key": key, "visible": True, "order": index}
        for index, key in enumerate(HUB_CARD_KEYS)
    ]


def _get_or_create(db: Session, user_id: int) -> UserSettings:
    row = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if row is None:
        row = UserSettings(user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _merged(row: UserSettings) -> dict:
    durations = _json_list(row.pomodoro_durations, DEFAULT_POMODORO_DURATIONS)
    if not durations:
        durations = DEFAULT_POMODORO_DURATIONS[:]
    intervals = _json_list(row.review_intervals, DEFAULT_REVIEW_INTERVALS)
    if not intervals:
        intervals = DEFAULT_REVIEW_INTERVALS[:]
    default_duration = row.pomodoro_default
    if default_duration not in durations:
        default_duration = durations[0]

    stored_cards = _json_list(row.hub_cards, [])
    existing = {
        card["key"]: card
        for card in stored_cards
        if isinstance(card, dict) and card.get("key") in HUB_CARD_KEYS
    }
    hub_cards = []
    for index, key in enumerate(HUB_CARD_KEYS):
        entry = existing.get(key) or {}
        hub_cards.append(
            {
                "key": key,
                "visible": bool(entry.get("visible", True)),
                "order": int(entry.get("order", index)),
            }
        )

    return {
        "theme_mode": row.theme_mode if row.theme_mode in ("light", "dark", "system") else "system",
        "accent": row.accent if row.accent in ACCENTS else "indigo",
        "pomodoro_durations": durations,
        "pomodoro_default": default_duration,
        "review_intervals": intervals,
        "habit_frequency_default": (
            row.habit_frequency_default
            if row.habit_frequency_default in ("daily", "weekdays", "custom")
            else "daily"
        ),
        "default_estimated_minutes": row.default_estimated_minutes,
        "hub_cards": hub_cards,
        "task_subjects": _json_list(row.task_subjects, []),
        "max_upload_mb": storage.max_upload_mb(),
    }


@router.get("", response_model=UserSettingsOut)
def get_settings(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return _merged(_get_or_create(db, user.id))


def _validate_and_apply(
    db: Session, row: UserSettings, updates: dict, commit: bool = True
) -> dict:
    """校验并持久化设置更新；供 API 与备份导入共用。updates 为字段名->值 字典。"""
    current = _merged(row)

    if "theme_mode" in updates:
        if updates["theme_mode"] not in ("light", "dark", "system"):
            raise HTTPException(status_code=400, detail="主题模式取值无效")
        current["theme_mode"] = updates["theme_mode"]
    if "accent" in updates:
        if updates["accent"] not in ACCENTS:
            raise HTTPException(status_code=400, detail="强调色取值无效")
        current["accent"] = updates["accent"]

    if "pomodoro_durations" in updates:
        durations = updates["pomodoro_durations"]
        if not 1 <= len(durations) <= 5:
            raise HTTPException(status_code=400, detail="番茄时长需保留 1-5 项")
        if any(not 1 <= d <= 180 for d in durations):
            raise HTTPException(status_code=400, detail="每项时长需在 1-180 分钟")
        current["pomodoro_durations"] = list(dict.fromkeys(durations))
    if "pomodoro_default" in updates:
        current["pomodoro_default"] = updates["pomodoro_default"]
    if "review_intervals" in updates:
        intervals = updates["review_intervals"]
        if not 1 <= len(intervals) <= 8:
            raise HTTPException(status_code=400, detail="复习间隔需保留 1-8 项")
        if any(not 1 <= interval <= 365 for interval in intervals):
            raise HTTPException(status_code=400, detail="复习间隔需在 1-365 天")
        current["review_intervals"] = sorted(set(intervals))
    if "habit_frequency_default" in updates:
        if updates["habit_frequency_default"] not in ("daily", "weekdays", "custom"):
            raise HTTPException(status_code=400, detail="习惯频率取值无效")
        current["habit_frequency_default"] = updates["habit_frequency_default"]
    if "default_estimated_minutes" in updates:
        current["default_estimated_minutes"] = updates["default_estimated_minutes"]

    if "hub_cards" in updates:
        hub_cards_payload = updates["hub_cards"]
        seen: set[str] = set()
        normalized = []
        for card in hub_cards_payload:
            if isinstance(card, dict):
                key, visible, order = (
                    card.get("key"),
                    bool(card.get("visible", True)),
                    card.get("order", 0),
                )
            else:
                key = getattr(card, "key", None)
                visible = bool(getattr(card, "visible", True))
                order = getattr(card, "order", 0)
            if key not in HUB_CARD_KEYS:
                raise HTTPException(status_code=400, detail=f"未知功能卡片：{key}")
            if key in seen:
                raise HTTPException(status_code=400, detail=f"功能卡片重复：{key}")
            seen.add(key)
            normalized.append({"key": key, "visible": visible, "order": order})
        for index, key in enumerate(HUB_CARD_KEYS):
            if key not in seen:
                normalized.append({"key": key, "visible": True, "order": index})
        normalized.sort(key=lambda card: HUB_CARD_KEYS.index(card["key"]))
        current["hub_cards"] = normalized

    if "task_subjects" in updates:
        subjects = [
            str(subject).strip()[:50]
            for subject in updates["task_subjects"]
            if str(subject).strip()
        ]
        if len(subjects) > 50:
            raise HTTPException(status_code=400, detail="科目库最多 50 项")
        current["task_subjects"] = list(dict.fromkeys(subjects))

    if current["pomodoro_default"] not in current["pomodoro_durations"]:
        current["pomodoro_default"] = current["pomodoro_durations"][0]

    row.theme_mode = current["theme_mode"]
    row.accent = current["accent"]
    row.pomodoro_durations = json.dumps(current["pomodoro_durations"])
    row.pomodoro_default = current["pomodoro_default"]
    row.review_intervals = json.dumps(current["review_intervals"])
    row.habit_frequency_default = current["habit_frequency_default"]
    row.default_estimated_minutes = current["default_estimated_minutes"]
    row.hub_cards = json.dumps(current["hub_cards"])
    row.task_subjects = json.dumps(current["task_subjects"])
    if commit:
        db.commit()
        db.refresh(row)
    return _merged(row)


@router.put("", response_model=UserSettingsOut)
def update_settings(
    payload: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_or_create(db, user.id)
    return _validate_and_apply(db, row, payload.model_dump(exclude_unset=True))
