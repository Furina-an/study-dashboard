"""测验：随机组卷 + 答题反馈 + 掌握度统计（借鉴港大 DeepTutor 测验/掌握练习模式）。"""

import random
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Question, QuizAttempt, User
from ..schemas import (
    MasteryStats,
    MasterySubject,
    QuizAnswerRequest,
    QuizAnswerResult,
    QuizQuestionOut,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


@router.get("/session", response_model=list[QuizQuestionOut])
def build_quiz(
    subject: str = "",
    count: int = 5,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (1 <= count <= 20):
        raise HTTPException(status_code=422, detail="题量需在 1-20 之间")
    stmt = select(Question).where(Question.user_id == user.id)
    if subject:
        stmt = stmt.where(Question.subject == subject)
    questions = db.scalars(stmt).all()
    if not questions:
        raise HTTPException(
            status_code=404, detail="题库为空，请先在「题库」录入或 AI 生成题目"
        )
    picked = random.sample(questions, min(count, len(questions)))
    return [
        QuizQuestionOut(
            id=question.id,
            subject=question.subject,
            question=question.question,
            options=question.options,
        )
        for question in picked
    ]


@router.post("/answer", response_model=QuizAnswerResult)
def answer_question(
    payload: QuizAnswerRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = db.scalar(
        select(Question).where(
            Question.id == payload.question_id, Question.user_id == user.id
        )
    )
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    if payload.answer_index >= len(question.options):
        raise HTTPException(status_code=422, detail="答案序号超出选项范围")
    correct = payload.answer_index == question.answer
    db.add(
        QuizAttempt(
            user_id=user.id,
            question_id=question.id,
            answer_index=payload.answer_index,
            correct=correct,
        )
    )
    db.commit()
    return QuizAnswerResult(
        correct=correct,
        correct_answer=question.answer,
        explanation=question.explanation,
    )


@router.get("/mastery", response_model=MasteryStats)
def mastery_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempts = db.execute(
        select(QuizAttempt, Question.subject)
        .join(Question, QuizAttempt.question_id == Question.id)
        .where(QuizAttempt.user_id == user.id)
    ).all()

    by_subject: dict[str, list[bool]] = defaultdict(list)
    recent: dict[str, list[bool]] = defaultdict(list)
    since = datetime.now() - timedelta(days=7)
    for attempt, subject in attempts:
        key = subject or "未分类"
        by_subject[key].append(attempt.correct)
        if attempt.answered_at >= since:
            recent[key].append(attempt.correct)

    subjects = []
    total_answered = 0
    total_correct = 0
    for subject, results in sorted(by_subject.items()):
        correct_count = sum(1 for result in results if result)
        total_answered += len(results)
        total_correct += correct_count
        recent_results = recent.get(subject, [])
        subjects.append(
            MasterySubject(
                subject=subject,
                total=len(results),
                correct=correct_count,
                accuracy=round(correct_count / len(results), 3) if results else 0.0,
                last_7d_total=len(recent_results),
                last_7d_correct=sum(1 for result in recent_results if result),
            )
        )
    return MasteryStats(
        subjects=subjects,
        total_answered=total_answered,
        total_correct=total_correct,
        overall_accuracy=round(total_correct / total_answered, 3)
        if total_answered
        else 0.0,
    )
