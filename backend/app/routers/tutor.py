"""AI 助教：聊天式辅导答疑（借鉴港大 DeepTutor 辅导模式）。

支持「免费（管理员共享通道）」与「自定义 API」双模式；
每个账号可保存默认参数（模型/风格/温度/最大长度/上下文条数），
单次对话可在请求中临时覆盖 model/style/temperature/max_tokens。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..crypto import decrypt_secret
from ..database import get_db
from ..llm import chat_completion, env_config, extract_error_message
from ..models import AIConfig, TutorMessage, TutorSession, TutorSettings, User
from ..schemas import (
    TutorChatRequest,
    TutorChatResult,
    TutorMessageOut,
    TutorSessionOut,
    TutorSettingsOut,
    TutorSettingsUpdate,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/tutor", tags=["tutor"])

BASE_TUTOR_PROMPT = (
    "你是 StudyDash 的 AI 助教，一位耐心的私人辅导老师。"
    "回答使用中文，条理清晰；涉及数学公式用 LaTeX（$...$）表示；"
    "如果用户的问题超出学习范围，请礼貌说明边界。"
)

STYLE_PROMPTS = {
    "socratic": "教学方式：苏格拉底式。通过反问、提示和拆解问题引导用户自己得出结论，而不是直接给答案。",
    "concise": "教学方式：简洁直接。先给结论要点，再简短解释，避免冗长。",
    "detailed": "教学方式：详细讲解。深入展开原理与推导，分步骤给出完整解释。",
    "exam": "教学方式：考试风格。讲解要点后出一道相关小测验题检验理解，并给出提示。",
}

TUTOR_DEFAULTS = {
    "mode": "custom",
    "model": "",
    "style": "socratic",
    "temperature": 0.7,
    "max_tokens": 1000,
    "context_limit": 20,
}


def _get_settings(user_id: int, db: Session) -> TutorSettings | None:
    return db.scalar(
        select(TutorSettings).where(TutorSettings.user_id == user_id)
    )


def _merged_settings(user_id: int, db: Session) -> dict:
    stored = _get_settings(user_id, db)
    data = dict(TUTOR_DEFAULTS)
    if stored is not None:
        data.update(
            {
                "mode": stored.mode or "custom",
                "model": stored.model or "",
                "style": stored.style or "socratic",
                "temperature": float(stored.temperature),
                "max_tokens": int(stored.max_tokens),
                "context_limit": int(stored.context_limit),
            }
        )
    return data


def _resolve_credentials(
    user_id: int, db: Session, mode: str, model_override: str
) -> dict:
    """免费模式只走环境变量；自定义模式沿用「已保存配置 > 环境变量」。"""
    env = env_config()
    if mode == "free":
        return {
            "base_url": env["base_url"],
            "model": (model_override or "").strip() or env["model"],
            "api_key": env["api_key"],
        }
    config = db.scalar(select(AIConfig).where(AIConfig.user_id == user_id))
    base_url = ((config.base_url if config else "") or env["base_url"]).rstrip("/")
    model = (
        (model_override or "").strip()
        or (config.model if config else "")
        or env["model"]
    )
    api_key = (
        (decrypt_secret(config.api_key_encrypted) if config else "") or env["api_key"]
    )
    return {"base_url": base_url, "model": model, "api_key": api_key}


def _owned_session(session_id: int, user_id: int, db: Session) -> TutorSession:
    session = db.scalar(
        select(TutorSession).where(
            TutorSession.id == session_id, TutorSession.user_id == user_id
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    return session


def _history_messages(session_id: int, db: Session, limit: int) -> list[dict]:
    """按时间顺序返回最近 limit 条消息。"""
    rows = db.scalars(
        select(TutorMessage)
        .where(TutorMessage.session_id == session_id)
        .order_by(TutorMessage.id.desc())
        .limit(limit)
    ).all()
    rows.reverse()
    return [{"role": row.role, "content": row.content} for row in rows]


@router.get("/settings", response_model=TutorSettingsOut)
def get_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = _merged_settings(user.id, db)
    data["free_available"] = bool(env_config()["api_key"])
    return data


@router.put("/settings", response_model=TutorSettingsOut)
def save_settings(
    payload: TutorSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="没有需要保存的配置")
    settings = _get_settings(user.id, db)
    if settings is None:
        settings = TutorSettings(user_id=user.id)
        db.add(settings)
    for key, value in changes.items():
        if key == "model" and isinstance(value, str):
            value = value.strip()
        setattr(settings, key, value)
    db.commit()
    data = _merged_settings(user.id, db)
    data["free_available"] = bool(env_config()["api_key"])
    return data


@router.get("/sessions", response_model=list[TutorSessionOut])
def list_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(TutorSession)
        .where(TutorSession.user_id == user.id)
        .order_by(TutorSession.updated_at.desc())
    ).all()
    result = []
    for row in rows:
        count = db.scalar(
            select(func.count(TutorMessage.id)).where(
                TutorMessage.session_id == row.id
            )
        )
        result.append(
            {
                "id": row.id,
                "title": row.title,
                "message_count": count or 0,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )
    return result


@router.get("/sessions/{session_id}/messages", response_model=list[TutorMessageOut])
def get_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _owned_session(session_id, user.id, db)
    return db.scalars(
        select(TutorMessage)
        .where(TutorMessage.session_id == session_id)
        .order_by(TutorMessage.id)
    ).all()


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, user.id, db)
    db.delete(session)
    db.commit()


@router.post("/chat", response_model=TutorChatResult)
def chat(
    payload: TutorChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = _merged_settings(user.id, db)
    mode = prefs["mode"]
    style = payload.style or prefs["style"]
    if style not in STYLE_PROMPTS:
        style = "socratic"
    temperature = (
        payload.temperature
        if payload.temperature is not None
        else prefs["temperature"]
    )
    max_tokens = (
        payload.max_tokens if payload.max_tokens is not None else prefs["max_tokens"]
    )
    context_limit = prefs["context_limit"]

    creds = _resolve_credentials(
        user.id, db, mode, payload.model or prefs["model"]
    )
    if not creds["api_key"]:
        if mode == "free":
            raise HTTPException(
                status_code=400,
                detail="管理员尚未配置免费通道，请切换到「自定义 API」或联系管理员",
            )
        raise HTTPException(
            status_code=400,
            detail="尚未配置 AI 服务，请先到「AI 设置」填写 API Key（支持 DeepSeek/通义/OpenAI 等）",
        )

    if payload.session_id is not None:
        session = _owned_session(payload.session_id, user.id, db)
    else:
        session = TutorSession(
            user_id=user.id, title=(payload.message[:30] or "新对话")
        )
        db.add(session)
        db.flush()

    db.add(
        TutorMessage(
            session_id=session.id,
            user_id=user.id,
            role="user",
            content=payload.message,
        )
    )
    db.commit()

    system_prompt = BASE_TUTOR_PROMPT + " " + STYLE_PROMPTS[style]
    messages = [{"role": "system", "content": system_prompt}]
    if payload.subject:
        messages.append(
            {
                "role": "system",
                "content": f"本次提问的科目是「{payload.subject}」，请围绕该科目辅导。",
            }
        )
    messages += _history_messages(session.id, db, context_limit)

    try:
        reply = chat_completion(
            creds["base_url"],
            creds["model"],
            creds["api_key"],
            messages,
            timeout=120.0,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # noqa: BLE001 - 统一转成用户可读错误
        db.add(
            TutorMessage(
                session_id=session.id,
                user_id=user.id,
                role="assistant",
                content=f"⚠️ 调用 AI 失败：{extract_error_message(exc)}",
            )
        )
        db.commit()
        raise HTTPException(status_code=502, detail=extract_error_message(exc))

    reply = (reply or "").strip() or "（模型未返回内容，请重试）"
    db.add(
        TutorMessage(
            session_id=session.id,
            user_id=user.id,
            role="assistant",
            content=reply,
        )
    )
    db.commit()
    return TutorChatResult(session_id=session.id, title=session.title, reply=reply)
