"""学习文件存储与安全隔离。

- 文件保存在后端 uploads/ 目录，不挂载为静态资源，外部无法直接访问；
- 按用户分目录隔离：uploads/files/{user_id}/...；
- 隔离区：uploads/quarantine/...（被判定为恶意或被管理员隔离的文件）；
- 文件名一律用 UUID 重命名，扩展名白名单 + 文件头魔数校验；
- 上传大小限制（MAX_UPLOAD_MB，默认 20MB）；
- 查杀病毒预留：配置 SCAN_COMMAND（如 clamscan --no-summary）后自动/手动扫描，
  未配置时 scan_status 保持 pending，不影响上传与本人下载。
"""

import os
import subprocess
import uuid
from pathlib import Path

FILE_STATUS = {"uploaded", "approved", "rejected", "quarantined"}
SCAN_STATUS = {"pending", "clean", "infected", "error"}

ALLOWED_EXTS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".csv",
    ".md",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
}

# 扩展名 -> 文件头魔数（内容嗅探，防止改后缀的脚本/可执行文件混入）
_MAGIC = {
    ".pdf": [(b"%PDF", 0)],
    ".png": [(b"\x89PNG\r\n\x1a\n", 0)],
    ".jpg": [(b"\xff\xd8\xff", 0)],
    ".jpeg": [(b"\xff\xd8\xff", 0)],
    ".gif": [(b"GIF87a", 0), (b"GIF89a", 0)],
    ".webp": [(b"RIFF", 0)],
    ".docx": [(b"PK\x03\x04", 0)],
    ".pptx": [(b"PK\x03\x04", 0)],
    ".xlsx": [(b"PK\x03\x04", 0)],
    ".doc": [(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0)],
    ".xls": [(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0)],
    ".ppt": [(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0)],
    ".md": [(b"", 0)],
    ".txt": [(b"", 0)],
    ".csv": [(b"", 0)],
}


def upload_root() -> Path:
    configured = os.getenv("UPLOAD_DIR", "").strip()
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parent.parent / "uploads"


def ensure_dirs() -> None:
    root = upload_root()
    (root / "files").mkdir(parents=True, exist_ok=True)
    (root / "quarantine").mkdir(parents=True, exist_ok=True)


def max_upload_mb() -> int:
    try:
        return max(1, int(os.getenv("MAX_UPLOAD_MB", "20")))
    except ValueError:
        return 20


def sanitize_ext(filename: str) -> str | None:
    """返回小写扩展名（含点）；白名单外返回 None。"""
    ext = Path(filename or "").suffix.lower()
    return ext if ext in ALLOWED_EXTS else None


def content_matches_ext(path: Path, ext: str) -> bool:
    """读取文件头做魔数校验；纯文本类（无魔数规则）直接放行。"""
    rules = _MAGIC.get(ext)
    if not rules or any(sig == b"" for sig, _ in rules):
        return True
    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError:
        return False
    return any(head.startswith(sig) for sig, _ in rules)


def new_stored_name(ext: str) -> str:
    return f"{uuid.uuid4().hex}{ext}"


def file_path(row) -> Path:
    """按记录状态解析磁盘路径（隔离区或用户目录）。"""
    root = upload_root()
    if row.status == "quarantined":
        return root / "quarantine" / row.stored_name
    return root / "files" / str(row.user_id) / row.stored_name


def user_dir(user_id: int) -> Path:
    return upload_root() / "files" / str(user_id)


def quarantine_path(row) -> Path:
    return upload_root() / "quarantine" / row.stored_name


def move_to_quarantine(row) -> None:
    # 注意：调用方通常已把 status 改为 quarantined，
    # 因此源路径必须显式取用户目录，不能依赖 file_path(row)。
    _move_file(user_dir(row.user_id) / row.stored_name, quarantine_path(row))


def release_from_quarantine(row) -> None:
    _move_file(quarantine_path(row), user_dir(row.user_id) / row.stored_name)


def _move_file(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(str(src), str(dst))


def delete_file(row) -> None:
    try:
        file_path(row).unlink(missing_ok=True)
    except OSError:
        pass


def scan_file(path: Path) -> tuple[str, str]:
    """病毒扫描钩子（查杀病毒预留）。

    - 配置 SCAN_COMMAND（如 `clamscan --no-summary`）后执行扫描：
      退出码 0=干净，1=发现病毒，其他=扫描出错；
    - 未配置时返回 (pending, 提示)，不阻塞上传与本人下载。
    """
    cmd = os.getenv("SCAN_COMMAND", "").strip()
    if not cmd:
        return "pending", "未配置 SCAN_COMMAND，已跳过扫描（查毒预留）"
    try:
        result = subprocess.run(
            cmd.split() + [str(path)],
            capture_output=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "error", f"扫描执行失败：{exc}"
    if result.returncode == 0:
        return "clean", "扫描完成：未发现风险"
    if result.returncode == 1:
        return "infected", "扫描发现病毒/恶意内容，文件已隔离"
    return "error", f"扫描器返回码 {result.returncode}"
