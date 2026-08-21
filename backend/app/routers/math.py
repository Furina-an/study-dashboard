"""高数复习接口：管理员共享资料区 + 进度/笔记（按用户隔离）。"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MathChapter, MathItem, MathNote, MathProgress, MathResource, User
from ..schemas import (
    MathChapterOut,
    MathItemOut,
    MathNoteUpdate,
    MathProgressUpdate,
    MathResourceCreate,
    MathResourceOut,
    MathResourceUpdate,
    MathSubOut,
    MathTreeOut,
)
from ..security import get_current_user, is_admin_user
from .. import storage

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


# ---------------- 高数资料：管理员发布、全员可浏览下载 ----------------

def _resource_out(row: MathResource) -> MathResourceOut:
    return MathResourceOut(
        id=row.id,
        title=row.title,
        description=row.description,
        original_name=row.original_name,
        ext=row.ext,
        size_bytes=row.size_bytes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/resources", response_model=list[MathResourceOut])
def list_resources(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(MathResource).order_by(MathResource.created_at.desc(), MathResource.id.desc())
    ).all()
    return [_resource_out(row) for row in rows]


@router.get("/resources/{resource_id}/download")
def download_resource(
    resource_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(MathResource, resource_id)
    if row is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    path = storage.math_resource_dir() / row.stored_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="资料文件在磁盘上不存在")
    return FileResponse(
        path,
        media_type=row.content_type or "application/octet-stream",
        filename=row.original_name,
    )


@router.post("/resources", response_model=MathResourceOut, status_code=201)
async def upload_resource(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    filename = request.query_params.get("filename", "")
    title = request.query_params.get("title", "")
    description = request.query_params.get("description", "")
    content_type = request.headers.get("Content-Type", "") or ""

    if not title.strip():
        raise HTTPException(status_code=422, detail="标题不能为空")
    title = title[:100]
    description = description[:500]

    ext = storage.sanitize_ext(filename)
    if ext is None:
        allowed = ", ".join(sorted(storage.ALLOWED_EXTS))
        raise HTTPException(status_code=400, detail=f"不支持的文件类型，仅允许：{allowed}")

    max_bytes = storage.max_upload_mb() * 1024 * 1024
    raw = await request.body()
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件超过大小限制（最大 {storage.max_upload_mb()}MB）",
        )

    storage.ensure_dirs()
    dest_dir = storage.math_resource_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored_name = storage.new_stored_name(ext)
    dest = dest_dir / stored_name
    try:
        dest.write_bytes(raw)
    except OSError:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="文件写入失败，请稍后重试")

    if not storage.content_matches_ext(dest, ext):
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="文件内容与扩展名不匹配，已拒绝上传")

    row = MathResource(
        title=title,
        description=description,
        original_name=filename[:255] or "未命名",
        stored_name=stored_name,
        ext=ext,
        size_bytes=len(raw),
        content_type=content_type[:100],
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _resource_out(row)


@router.patch("/resources/{resource_id}", response_model=MathResourceOut)
def update_resource(
    resource_id: int,
    payload: MathResourceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    row = db.get(MathResource, resource_id)
    if row is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    if payload.title is not None:
        row.title = payload.title.strip()[:100]
    if payload.description is not None:
        row.description = payload.description[:500]
    db.commit()
    db.refresh(row)
    return _resource_out(row)


@router.delete("/resources/{resource_id}", status_code=204)
def delete_resource(
    resource_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    row = db.get(MathResource, resource_id)
    if row is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    try:
        (storage.math_resource_dir() / row.stored_name).unlink(missing_ok=True)
    except OSError:
        pass
    db.delete(row)
    db.commit()
    return None
