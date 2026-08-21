"""学习文件：用户上传 + 运营整合（管理员）。

安全隔离：
- 按用户分目录存储（uploads/files/{user_id}/），UUID 重命名，不挂载静态目录；
- 扩展名白名单 + 文件头魔数校验，上传大小限制；
- 隔离区（uploads/quarantine/）：病毒命中或被管理员隔离的文件移入，
  非管理员禁止下载；
- 查杀病毒预留：SCAN_COMMAND 配置后自动/手动扫描（见 app/storage.py）。
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import StudyFile, User
from ..schemas import FileOut, FileUpdate
from ..security import get_current_user, is_admin_user
from .. import storage

router = APIRouter(prefix="/api/files", tags=["files"])


def _get_file_or_404(db: Session, file_id: int) -> StudyFile:
    row = db.get(StudyFile, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return row


def _require_access(row: StudyFile, user: User) -> None:
    """越权访问一律返回 404，避免暴露文件是否存在。"""
    if row.user_id != user.id and not is_admin_user(user):
        raise HTTPException(status_code=404, detail="文件不存在")


def _to_out(row: StudyFile, db: Session) -> FileOut:
    owner = db.get(User, row.user_id)
    return FileOut(
        id=row.id,
        user_id=row.user_id,
        owner_username=owner.username if owner else "",
        original_name=row.original_name,
        ext=row.ext,
        size_bytes=row.size_bytes,
        content_type=row.content_type,
        category=row.category,
        description=row.description,
        status=row.status,
        scan_status=row.scan_status,
        scan_message=row.scan_message,
        integrated=row.integrated,
        is_recommended=row.is_recommended,
        admin_note=row.admin_note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[FileOut])
def list_files(
    scope: str = "mine",
    status: str | None = None,
    user_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(StudyFile).where(StudyFile.user_id == user.id)
    if is_admin_user(user) and (scope == "all" or user_id is not None):
        query = select(StudyFile)
        if user_id is not None:
            query = query.where(StudyFile.user_id == user_id)
    if status:
        if status not in storage.FILE_STATUS:
            raise HTTPException(status_code=400, detail="非法文件状态")
        query = query.where(StudyFile.status == status)
    rows = db.scalars(query.order_by(StudyFile.created_at.desc())).all()
    return [_to_out(row, db) for row in rows]


@router.get("/recommended", response_model=list[FileOut])
def list_recommended(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员推荐的学习资料：所有登录用户可见、可下载（隔离文件除外）。"""
    query = select(StudyFile).where(
        StudyFile.is_recommended.is_(True),
        StudyFile.status != "quarantined",
    )
    rows = db.scalars(query.order_by(StudyFile.updated_at.desc())).all()
    return [_to_out(row, db) for row in rows]


@router.post("", response_model=FileOut, status_code=201)
async def upload_file(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 上传采用「原始二进制 body + 查询参数元数据」，避免 multipart 依赖
    filename = request.query_params.get("filename", "")
    category = request.query_params.get("category", "")
    description = request.query_params.get("description", "")
    content_type = request.headers.get("Content-Type", "") or ""

    ext = storage.sanitize_ext(filename)
    if ext is None:
        allowed = ", ".join(sorted(storage.ALLOWED_EXTS))
        raise HTTPException(status_code=400, detail=f"不支持的文件类型，仅允许：{allowed}")

    max_bytes = storage.max_upload_mb() * 1024 * 1024
    try:
        declared = int(request.headers.get("Content-Length", "") or "0")
        if declared > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"文件超过大小限制（最大 {storage.max_upload_mb()}MB）",
            )
    except ValueError:
        declared = 0

    raw = await request.body()
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件超过大小限制（最大 {storage.max_upload_mb()}MB）",
        )

    storage.ensure_dirs()
    dest_dir = storage.user_dir(user.id)
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

    scan_status, scan_message = storage.scan_file(dest)
    row = StudyFile(
        user_id=user.id,
        original_name=filename[:255] or "未命名",
        stored_name=stored_name,
        ext=ext,
        size_bytes=len(raw),
        content_type=content_type[:100],
        category=(category or "")[:50],
        description=(description or "")[:200],
        status="quarantined" if scan_status == "infected" else "uploaded",
        scan_status=scan_status,
        scan_message=scan_message,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if row.status == "quarantined":
        storage.move_to_quarantine(row)
    return _to_out(row, db)


@router.get("/{file_id}/download")
def download_file(
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_file_or_404(db, file_id)
    # 管理员推荐分享的文件对全员开放；隔离文件仍仅管理员可下载
    if not (row.is_recommended and row.status != "quarantined"):
        _require_access(row, user)
    if row.status == "quarantined" and not is_admin_user(user):
        raise HTTPException(status_code=403, detail="文件已被隔离，无法下载")
    path = storage.file_path(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件在磁盘上不存在")
    return FileResponse(
        path,
        media_type=row.content_type or "application/octet-stream",
        filename=row.original_name,
    )


@router.delete("/{file_id}", status_code=204)
def delete_file(
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_file_or_404(db, file_id)
    _require_access(row, user)
    storage.delete_file(row)
    db.delete(row)
    db.commit()
    return None


@router.patch("/{file_id}", response_model=FileOut)
def update_file(
    file_id: int,
    payload: FileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_file_or_404(db, file_id)
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if payload.status is not None:
        if payload.status not in storage.FILE_STATUS:
            raise HTTPException(status_code=400, detail="非法文件状态")
        row.status = payload.status
    if payload.scan_status is not None:
        if payload.scan_status not in storage.SCAN_STATUS:
            raise HTTPException(status_code=400, detail="非法扫描状态")
        row.scan_status = payload.scan_status
    if payload.integrated is not None:
        row.integrated = payload.integrated
    if payload.is_recommended is not None:
        row.is_recommended = payload.is_recommended
    if payload.admin_note is not None:
        row.admin_note = payload.admin_note[:500]
    if payload.category is not None:
        row.category = payload.category[:50]
    if payload.description is not None:
        row.description = payload.description[:200]

    # 隔离 / 放行时同步磁盘位置
    if row.status == "quarantined":
        storage.move_to_quarantine(row)
    else:
        storage.release_from_quarantine(row)

    db.commit()
    db.refresh(row)
    return _to_out(row, db)


@router.post("/{file_id}/scan", response_model=FileOut)
def rescan_file(
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_file_or_404(db, file_id)
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    path = storage.file_path(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件在磁盘上不存在")
    scan_status, scan_message = storage.scan_file(path)
    row.scan_status = scan_status
    row.scan_message = scan_message
    if scan_status == "infected":
        row.status = "quarantined"
        storage.move_to_quarantine(row)
    db.commit()
    db.refresh(row)
    return _to_out(row, db)
