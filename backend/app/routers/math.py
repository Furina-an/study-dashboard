"""高数复习接口：提纲内容（全局只读）+ 进度/笔记（按用户隔离）。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MathChapter, MathItem, MathNote, MathProgress, User
from ..schemas import (
    MathChapterOut,
    MathItemOut,
    MathNoteUpdate,
    MathProgressUpdate,
    MathSubOut,
    MathTreeOut,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/math", tags=["math"])


@router.get("/tree", response_model=MathTreeOut)
def math_tree(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    chapters = db.scalars(
        select(MathChapter).order_by(MathChapter.sort_order)
    ).all()
    items = db.scalars(
        select(MathItem).order_by(MathItem.sort_order)
    ).all()
    by_chapter: dict[int, list[MathItem]] = {}
    for item in items:
        by_chapter.setdefault(item.chapter_id, []).append(item)

    progress_rows = db.scalars(
        select(MathProgress).where(MathProgress.user_id == user.id)
    ).all()
    done_ids = {row.item_id for row in progress_rows if row.done}
    notes = db.scalars(
        select(MathNote).where(MathNote.user_id == user.id)
    ).all()
    notes_by_chapter = {row.chapter_id: row.content for row in notes}

    chapters_out: list[MathChapterOut] = []
    total_done = 0
    total = 0
    for chapter in chapters:
        chapter_items = by_chapter.get(chapter.id, [])
        chapter_done = 0
        subs: list[MathSubOut] = []
        for item in chapter_items:
            is_done = item.id in done_ids
            if is_done:
                chapter_done += 1
                total_done += 1
            total += 1
            if not subs or subs[-1].title != item.sub_title:
                subs.append(
                    MathSubOut(title=item.sub_title, tag=item.tag, items=[])
                )
            subs[-1].items.append(
                MathItemOut(
                    id=item.id,
                    item_key=item.item_key,
                    tag=item.tag,
                    done=is_done,
                    segments=json.loads(item.segments),
                )
            )
        chapters_out.append(
            MathChapterOut(
                id=chapter.id,
                chapter_key=chapter.chapter_key,
                num=chapter.num,
                title=chapter.title,
                short=chapter.short,
                note=notes_by_chapter.get(chapter.id, ""),
                note_label=chapter.note_label,
                note_placeholder=chapter.note_placeholder,
                done=chapter_done,
                total=len(chapter_items),
                subs=subs,
            )
        )
    return MathTreeOut(chapters=chapters_out, done=total_done, total=total)


@router.put("/items/{item_id}/progress")
def update_progress(
    item_id: int,
    payload: MathProgressUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(MathItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    record = db.scalar(
        select(MathProgress).where(
            MathProgress.user_id == user.id, MathProgress.item_id == item_id
        )
    )
    if record is None:
        db.add(
            MathProgress(user_id=user.id, item_id=item_id, done=payload.done)
        )
    else:
        record.done = payload.done
    db.commit()
    return {"ok": True, "item_id": item_id, "done": payload.done}


@router.put("/chapters/{chapter_id}/note")
def update_note(
    chapter_id: int,
    payload: MathNoteUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chapter = db.get(MathChapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    record = db.scalar(
        select(MathNote).where(
            MathNote.user_id == user.id, MathNote.chapter_id == chapter_id
        )
    )
    if record is None:
        db.add(
            MathNote(
                user_id=user.id, chapter_id=chapter_id, content=payload.content
            )
        )
    else:
        record.content = payload.content
    db.commit()
    return {"ok": True, "chapter_id": chapter_id}


@router.delete("/progress")
def reset_progress(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    rows = db.scalars(
        select(MathProgress).where(MathProgress.user_id == user.id)
    ).all()
    for row in rows:
        db.delete(row)
    db.commit()
    return {"ok": True, "cleared": len(rows)}
