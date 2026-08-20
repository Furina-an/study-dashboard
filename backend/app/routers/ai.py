import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crypto import decrypt_secret, encrypt_secret
from ..database import get_db
from ..llm import DEFAULT_BASE_URL, DEFAULT_MODEL, chat_completion, env_config, extract_error_message
from ..models import AIConfig, User
from ..schemas import AIConfigOut, AIConfigUpdate, AITestRequest, AITestResult
from ..security import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai"])


def mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return api_key[:3] + "*" * max(4, len(api_key) - 7) + api_key[-4:]


def _get_config(user_id: int, db: Session) -> AIConfig | None:
    return db.scalar(select(AIConfig).where(AIConfig.user_id == user_id))


def _to_out(config: AIConfig | None) -> AIConfigOut:
    if config is None:
        return AIConfigOut(
            provider="custom",
            base_url=DEFAULT_BASE_URL,
            model=DEFAULT_MODEL,
            api_key_masked="",
            has_api_key=False,
            updated_at=None,
        )
    key = decrypt_secret(config.api_key_encrypted)
    return AIConfigOut(
        provider=config.provider,
        base_url=config.base_url,
        model=config.model,
        api_key_masked=mask_key(key),
        has_api_key=bool(key),
        updated_at=config.updated_at,
    )


@router.get("/config", response_model=AIConfigOut)
def get_config(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _to_out(_get_config(user.id, db))


@router.put("/config", response_model=AIConfigOut)
def save_config(
    payload: AIConfigUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = _get_config(user.id, db)
    if config is None:
        config = AIConfig(user_id=user.id)
        db.add(config)
    config.provider = (payload.provider or "custom").strip() or "custom"
    config.base_url = (payload.base_url or DEFAULT_BASE_URL).strip().rstrip("/")
    config.model = (payload.model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if payload.api_key and payload.api_key.strip():
        config.api_key_encrypted = encrypt_secret(payload.api_key.strip())
    db.commit()
    db.refresh(config)
    return _to_out(config)


@router.delete("/config", status_code=204)
def delete_config(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = _get_config(user.id, db)
    if config is not None:
        db.delete(config)
        db.commit()


def _resolve_credentials(
    payload: AITestRequest, user_id: int, db: Session
) -> dict:
    """测试参数优先级：请求体 > 已保存配置 > 环境变量。"""
    config = _get_config(user_id, db)
    env = env_config()
    base_url = (
        (payload.base_url or "").strip()
        or (config.base_url if config else "")
        or env["base_url"]
    ).rstrip("/")
    model = (
        (payload.model or "").strip()
        or (config.model if config else "")
        or env["model"]
    )
    api_key = (
        (payload.api_key or "").strip()
        or (decrypt_secret(config.api_key_encrypted) if config else "")
        or env["api_key"]
    )
    return {"base_url": base_url, "model": model, "api_key": api_key}


@router.post("/test", response_model=AITestResult)
def test_config(
    payload: AITestRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    creds = _resolve_credentials(payload, user.id, db)
    if not creds["api_key"]:
        raise HTTPException(status_code=400, detail="请先填写 API Key")
    start = time.perf_counter()
    try:
        reply = chat_completion(
            creds["base_url"],
            creds["model"],
            creds["api_key"],
            [{"role": "user", "content": "请只回复两个字：你好"}],
            timeout=30.0,
        )
    except Exception as exc:  # noqa: BLE001 - 统一转成用户可读错误
        raise HTTPException(status_code=400, detail=extract_error_message(exc))
    latency = int((time.perf_counter() - start) * 1000)
    return AITestResult(
        ok=True,
        message=f"连接成功，模型回复：{reply.strip()[:50]}",
        latency_ms=latency,
    )
