"""上传文件存储空间（纯标准库）。

data/uploads/{username}/      每用户上传空间
  <uuid>.<ext>                二进制文件（UUID 命名，原名只存元数据）
  manifest.json               文件元数据索引
data/quarantine/              隔离区（病毒/管理员隔离文件移入）
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import FileMeta, validate_username

_ENCODING = "utf-8"
_MANIFEST = "manifest.json"

# 扩展名白名单（frozenset 用于 O(1) 校验）
ALLOWED_EXTENSIONS = frozenset(
    {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".txt", ".md", ".csv", ".log",
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
        ".zip", ".7z", ".rar",
        ".mp3", ".mp4", ".wav",
        ".json", ".py", ".js", ".html", ".css",
    }
)

DEFAULT_SIZE_CAP = 50 * 1024 * 1024  # 50 MB
_FILE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _check_magic(ext: str, head: bytes) -> bool:
    """按文件头魔数校验；未定义魔数的文本类扩展名直接放行。"""
    if ext == ".pdf":
        return head.startswith(b"%PDF")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    if ext == ".webp":
        return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == ".svg":
        return head.lstrip().startswith((b"<?xml", b"<svg", b"<!DOCTYPE"))
    if ext == ".zip":
        return head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    if ext in (".docx", ".xlsx", ".pptx"):
        return head.startswith(b"PK\x03\x04")
    if ext == ".7z":
        return head.startswith(b"7z\xbc\xaf'\x1c")
    if ext == ".rar":
        return head.startswith(b"Rar!\x1a\x07")
    if ext == ".mp3":
        return head.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3"))
    if ext == ".mp4":
        return len(head) >= 8 and head[4:8] == b"ftyp"
    if ext == ".wav":
        return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WAVE"
    return True  # 文本类等未定义魔数


def _text_safe(value: Any) -> str:
    return str(value)[:255] if value is not None else ""


class UploadSpace:
    """每用户上传空间：blob 落盘 + manifest 索引 + 隔离区。"""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.uploads_dir = self.root / "uploads"
        self.quarantine_dir = self.root / "quarantine"
        self._locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()

    # ---------- 内部工具 ----------

    def _lock_for(self, username: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(username)
            if lock is None:
                lock = threading.RLock()
                self._locks[username] = lock
            return lock

    def _user_dir(self, username: str) -> Path:
        validate_username(username)
        root = self.root.resolve()
        path = (self.uploads_dir / username).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"非法路径：{path}")
        return path

    def _manifest_path(self, username: str) -> Path:
        return self._user_dir(username) / _MANIFEST

    def _load_manifest(self, username: str) -> list[FileMeta]:
        path = self._manifest_path(username)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding=_ENCODING))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"manifest 损坏：{path}") from exc
        if not isinstance(payload, dict):
            return []
        files = payload.get("files") or []
        return [FileMeta.from_dict(item) for item in files if isinstance(item, dict)]

    def _write_manifest(self, username: str, files: list[FileMeta]) -> Path:
        path = self._manifest_path(username)
        payload = {
            "user": username,
            "files": [item.to_dict() for item in files],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{_MANIFEST}.tmp-{os.getpid()}")
        try:
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding=_ENCODING
            )
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
        return path

    def _blob_path(self, username: str, meta: FileMeta) -> Path:
        user_dir = self._user_dir(username)
        path = (user_dir / meta.stored_name()).resolve()
        if not path.is_relative_to(user_dir):
            raise ValueError(f"非法文件路径：{path}")
        return path

    def _quarantine_path(self, username: str, meta: FileMeta) -> Path:
        return self.quarantine_dir / f"{username}-{meta.file_id}{meta.ext}"

    @staticmethod
    def _atomic_write(path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        try:
            tmp.write_text(payload, encoding=_ENCODING)
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    @staticmethod
    def _atomic_write_bytes(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        try:
            tmp.write_bytes(payload)
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    # ---------- 公开 API ----------

    def ensure_user_file(self, username: str) -> Path:
        """确保用户上传目录与 manifest 存在（幂等）。"""
        validate_username(username)
        with self._lock_for(username):
            path = self._manifest_path(username)
            if not path.exists():
                self._write_manifest(username, [])
            return path

    def put(
        self,
        username: str,
        data: bytes,
        original_name: str,
        category: str = "",
        description: str = "",
        size_cap: int | None = None,
    ) -> FileMeta:
        """上传一个文件。校验扩展名白名单 + 文件头魔数 + 大小上限。"""
        validate_username(username)
        blob = bytes(data)
        if not blob:
            raise ValueError("文件内容为空")
        cap = size_cap if size_cap is not None else DEFAULT_SIZE_CAP
        if cap > 0 and len(blob) > cap:
            raise ValueError(f"文件大小 {len(blob)} 字节超过上限 {cap} 字节")
        name = original_name or "unnamed"
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"不允许的扩展名：{ext!r}")
        if not _check_magic(ext, blob[:16]):
            raise ValueError(f"文件头魔数与扩展名 {ext} 不符，疑似伪装文件")

        with self._lock_for(username):
            self.ensure_user_file(username)
            files = self._load_manifest(username)
            file_id = uuid.uuid4().hex
            meta = FileMeta(
                file_id=file_id,
                original_name=_text_safe(name),
                ext=ext,
                size_bytes=len(blob),
                category=_text_safe(category),
                description=_text_safe(description),
                status="uploaded",
                scan_status="pending",
                uploaded_at=self._now(),
            )
            blob_path = self._blob_path(username, meta)
            self._atomic_write_bytes(blob_path, blob)
            files.append(meta)
            self._write_manifest(username, files)
            return meta

    def get_path(self, username: str, file_id: str) -> Path:
        """返回已落盘 blob 的绝对路径（只读用途）。"""
        meta = self._find(username, file_id)
        path = self._blob_path(username, meta)
        if not path.is_file():
            raise FileNotFoundError(f"文件不存在：{path}")
        return path

    def get(self, username: str, file_id: str) -> bytes:
        return self.get_path(username, file_id).read_bytes()

    def remove(self, username: str, file_id: str) -> FileMeta:
        """删除文件：移除 blob 并从 manifest 摘除。"""
        with self._lock_for(username):
            meta = self._find(username, file_id)
            blob_path = self._blob_path(username, meta)
            blob_path.unlink(missing_ok=True)
            files = self._load_manifest(username)
            self._write_manifest(
                username, [item for item in files if item.file_id != file_id]
            )
            return meta

    def quarantine(self, username: str, file_id: str, reason: str = "") -> Path:
        """把文件移入隔离区，manifest 标记 quarantined。"""
        with self._lock_for(username):
            meta = self._find(username, file_id)
            src = self._blob_path(username, meta)
            dst = self._quarantine_path(username, meta)
            src.parent.mkdir(parents=True, exist_ok=True)
            self.quarantine_dir.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
            self._replace_meta(
                username,
                file_id,
                status="quarantined",
                scan_status="pending",
                scan_message=_text_safe(reason),
            )
            return dst

    def release(self, username: str, file_id: str) -> Path:
        """从隔离区放行回用户空间，manifest 标记 uploaded。"""
        with self._lock_for(username):
            meta = self._find(username, file_id)
            if meta.status != "quarantined":
                raise ValueError(f"文件未在隔离区：{file_id}")
            src = self._quarantine_path(username, meta)
            if not src.is_file():
                raise FileNotFoundError(f"隔离文件不存在：{src}")
            dst = self._blob_path(username, meta)
            os.replace(src, dst)
            self._replace_meta(
                username,
                file_id,
                status="uploaded",
                scan_status="pending",
                scan_message="",
            )
            return dst

    def list(self, username: str) -> tuple[FileMeta, ...]:
        """返回该用户全部文件元数据，按上传时间排序。"""
        validate_username(username)
        with self._lock_for(username):
            files = self._load_manifest(username)
        return tuple(sorted(files, key=lambda item: item.uploaded_at))

    # ---------- 内部辅助 ----------

    def _find(self, username: str, file_id: str) -> FileMeta:
        validate_username(username)
        if not _FILE_ID_RE.fullmatch(file_id):
            raise ValueError(f"非法文件 ID：{file_id!r}")
        files = self._load_manifest(username)
        for item in files:
            if item.file_id == file_id:
                return item
        raise FileNotFoundError(f"文件不存在：{file_id}")

    def _replace_meta(
        self,
        username: str,
        file_id: str,
        **changes: Any,
    ) -> FileMeta:
        files = self._load_manifest(username)
        for index, item in enumerate(files):
            if item.file_id == file_id:
                payload = item.to_dict()
                payload.update(changes)
                updated = FileMeta.from_dict(payload)
                files[index] = updated
                self._write_manifest(username, files)
                return updated
        raise FileNotFoundError(f"文件不存在：{file_id}")
