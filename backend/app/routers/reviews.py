import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Plan, Review, Task, User, UserSettings
from ..schemas import ReviewCompleteResult, ReviewOut
from ..security import get_current_user

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30]


def user_review_intervals(db: Session, user_id: int) -> list[int]:
    """读取用户自定义复习间隔；未配置或非法时回退默认。"""
    row = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if row is None:
        return REVIEW_INTERVALS
    try:
        intervals = json.loads(row.review_intervals or "")
        if (
            isinstance(intervals, list)
            and intervals
            and all(isinstance(i, int) and 1 <= i <= 365 for i in intervals)
        ):
            return sorted(set(intervals))
    except (TypeError, ValueError):
        pass
    return REVIEW_INTERVALS


def generate_reviews(
    db: Session,
    user_id: int,
    source_type: str,
    source_id: int,
    completed_at: datetime,
) -> None:
    """任务/计划完成时生成艾宾浩斯复习节点；同一轮未复习完前不重复生成。

    间隔取该用户自定义 `review_intervals`（默认 1/2/4/7/15/30）。
    """
    intervals = user_review_intervals(db, user_id)
    existing = db.scalar(
        select(Review.id).where(
            Review.user_id == user_id,
            Review.source_type == source_type,
            Review.source_id == source_id,
            Review.interval_days == intervals[0],
            Review.reviewed_at.is_(None),
        )
    )
    if existing is not None:
        return
    base = completed_at.date()
    for interval in intervals:
        db.add(
            Review(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
                due_date=base + timedelta(days=interval),
                interval_days=interval,
            )
        )


def _source_title(db: Session, source_type: str, source_id: int) -> str:
    item = (
        db.get(Task, source_id) if source_type == "task" else db.get(Plan, source_id)
    )
    return item.title if item is not None else "（已删除）"


def _to_out(db: Session, review: Review) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        source_type=review.source_type,
        source_id=review.source_id,
        source_title=_source_title(db, review.source_type, review.source_id),
        due_date=review.due_date.isoformat(),
        interval_days=review.interval_days,
        reviewed_at=review.reviewed_at,
        created_at=review.created_at,
    )


def _owned_review(review_id: int, user_id: int, db: Session) -> Review:
    review = db.scalar(
        select(Review).where(Review.id == review_id, Review.user_id == user_id)
    )
    if review is None:
        raise HTTPException(status_code=404, detail="复习记录不存在")
    return review


@router.get("", response_model=list[ReviewOut])
def list_reviews(
    status: str = Query("due", pattern="^(due|upcoming|all)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    statement = select(Review).where(Review.user_id == user.id)
    if status == "due":
        statement = statement.where(
            Review.reviewed_at.is_(None), Review.due_date <= today
        ).order_by(Review.due_date.asc())
    elif status == "upcoming":
        statement = statement.where(
            Review.reviewed_at.is_(None),
            Review.due_date > today,
            Review.due_date <= today + timedelta(days=30),
        ).order_by(Review.due_date.asc())
    else:
        statement = statement.order_by(Review.due_date.desc())
    return [_to_out(db, review) for review in db.scalars(statement).all()]


@router.post("/complete-due", response_model=ReviewCompleteResult)
def complete_due_reviews(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    reviews = db.scalars(
        select(Review).where(
            Review.user_id == user.id,
            Review.reviewed_at.is_(None),
            Review.due_date <= today,
        )
    ).all()
    now = datetime.now()
    for review in reviews:
        review.reviewed_at = now
    db.commit()
    return ReviewCompleteResult(completed=len(reviews))


@router.post("/{review_id}/complete", response_model=ReviewOut)
def complete_review(
    review_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = _owned_review(review_id, user.id, db)
    review.reviewed_at = datetime.now()
    db.commit()
    db.refresh(review)
    return _to_out(db, review)
