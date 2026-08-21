"""题库：手动录入 + AI 一键出题（借鉴港大 DeepTutor 智能出题模式）。"""

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crypto import decrypt_secret
from ..database import get_db
from ..llm import chat_completion, env_config, extract_error_message
from ..models import AIConfig, Question, User
from ..schemas import (
    GenerateQuestionsRequest,
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _owned_question(question_id: int, user_id: int, db: Session) -> Question:
    question = db.scalar(
        select(Question).where(
            Question.id == question_id, Question.user_id == user_id
        )
    )
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return question


def _validate_answer(options: list[str], answer: int) -> None:
    if answer < 0 or answer >= len(options):
        raise HTTPException(status_code=422, detail="答案序号超出选项范围")


@router.get("", response_model=list[QuestionOut])
def list_questions(
    subject: str = "",
    source: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Question).where(Question.user_id == user.id)
    if subject:
        stmt = stmt.where(Question.subject == subject)
    if source:
        stmt = stmt.where(Question.source == source)
    return db.scalars(stmt.order_by(Question.id.desc())).all()


@router.post("", response_model=QuestionOut, status_code=201)
def create_question(
    payload: QuestionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    options = [option.strip() for option in payload.options]
    _validate_answer(options, payload.answer)
    question = Question(
        user_id=user.id,
        subject=payload.subject.strip(),
        question=payload.question.strip(),
        options=options,
        answer=payload.answer,
        explanation=payload.explanation.strip(),
        source="manual",
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.patch("/{question_id}", response_model=QuestionOut)
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = _owned_question(question_id, user.id, db)
    changes = payload.model_dump(exclude_unset=True)
    if "options" in changes and changes["options"] is not None:
        _validate_answer(changes["options"], changes.get("answer", question.answer))
    for key, value in changes.items():
        if value is None and key == "answer":
            continue
        if isinstance(value, str):
            value = value.strip()
        setattr(question, key, value)
    db.commit()
    db.refresh(question)
    return question


@router.delete("/{question_id}", status_code=204)
def delete_question(
    question_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = _owned_question(question_id, user.id, db)
    db.delete(question)
    db.commit()


def _parse_questions_content(content: str) -> list[dict]:
    """解析 LLM 返回的题目 JSON 数组，兼容代码块包裹与残缺项。"""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    result = []
    for item in data:
        if not isinstance(item, dict) or not item.get("question"):
            continue
        options = item.get("options")
        if not isinstance(options, list) or len(options) < 2:
            continue
        options = [str(option).strip() for option in options[:6]]
        try:
            answer = int(item.get("answer", 0))
        except (TypeError, ValueError):
            answer = 0
        if answer < 0 or answer >= len(options):
            answer = 0
        result.append(
            {
                "question": str(item["question"]).strip()[:2000],
                "options": options,
                "answer": answer,
                "explanation": str(item.get("explanation", "")).strip()[:2000],
            }
        )
    return result


@router.post("/generate", response_model=list[QuestionOut])
def generate_questions(
    payload: GenerateQuestionsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = db.scalar(select(AIConfig).where(AIConfig.user_id == user.id))
    env = env_config()
    base_url = ((config.base_url if config else "") or env["base_url"]).rstrip("/")
    model = (config.model if config else "") or env["model"]
    api_key = (
        (decrypt_secret(config.api_key_encrypted) if config else "") or env["api_key"]
    )
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="尚未配置 AI 服务，请先到「AI 设置」填写 API Key",
        )

    prompt = (
        f"你是出题老师，为科目「{payload.subject}」生成 {payload.count} 道单选题"
        f"（知识点：{payload.topic or '综合'}）。\n"
        "只输出一个 JSON 数组，不要任何多余文字：\n"
        '[{"question": "题干", "options": ["选项A", "选项B", "选项C", "选项D"], '
        '"answer": 0, "explanation": "解析"}]'
    )
    try:
        reply = chat_completion(
            base_url,
            model,
            api_key,
            [{"role": "user", "content": prompt}],
            timeout=120.0,
        )
    except Exception as exc:  # noqa: BLE001 - 统一转成用户可读错误
        raise HTTPException(status_code=502, detail=extract_error_message(exc))

    items = _parse_questions_content(reply)
    if not items:
        raise HTTPException(
            status_code=502, detail="AI 返回内容无法解析为题目，请重试或减少数量"
        )

    created = []
    for item in items:
        question = Question(
            user_id=user.id,
            subject=payload.subject.strip(),
            source="ai",
            **item,
        )
        db.add(question)
        created.append(question)
    db.commit()
    for question in created:
        db.refresh(question)
    return created
