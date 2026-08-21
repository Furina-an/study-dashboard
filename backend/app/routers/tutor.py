"""AI 助教：聊天式辅导答疑（借鉴港大 DeepTutor 辅导模式）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..crypto import decrypt_secret
from ..database import get_db
from ..llm import chat_completion, env_config, extract_error_message
from ..models import AIConfig, TutorMessage, TutorSession, User
from ..schemas import (
    TutorChatRequest,
    TutorChatResult,
    TutorMessageOut,
    TutorSessionOut,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/tutor", tags=["tutor"])

SYSTEM_PROMPT = (
    "你是 StudyDash 的 AI 助教，一位耐心的私人辅导老师。"
    "目标是通过提问、举例和分步讲解帮助用户真正理解知识，而不是直接给答案。"
    "回答使用中文，条理清晰；涉及数学公式用 LaTeX（$...$）表示；"
    "如果用户的问题超出学习范围，请礼貌说明边界。"
)


def _resolve_credentials(user_id: int, db: Session) -> dict:
    """复用 ai.py 的优先级：已保存配置 > 环境变量。"""
    config = db.scalar(select(AIConfig).where(AIConfig.user_id == user_id))
    env = env_config()
    base_url = ((config.base_url if config else "") or env["base_url"]).rstrip("/")
    model = (config.model if config else "") or env["model"]
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


def _history_messages(session_id: int, db: Session) -> list[dict]:
    rows = db.scalars(
        select(TutorMessage)
        .where(TutorMessage.session_id == session_id)
        .order_by(TutorMessage.id)
        .limit(40)
    ).all()
    return [{"role": row.role, "content": row.content} for row in rows]


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
    creds = _resolve_credentials(user.id, db)
    if not creds["api_key"]:
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

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if payload.subject:
        messages.append(
            {
                "role": "system",
                "content": f"本次提问的科目是「{payload.subject}」，请围绕该科目辅导。",
            }
        )
    messages += _history_messages(session.id, db)

    try:
        reply = chat_completion(
            creds["base_url"],
            creds["model"],
            creds["api_key"],
            messages,
            timeout=120.0,
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
