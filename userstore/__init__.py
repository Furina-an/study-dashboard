"""userstore — 独立「用户信息储存系统」模块（纯标准库）。

数据布局（默认 data root = <project>/data，可用 DATA_ROOT 环境变量覆盖）：
  data/users/{username}.json          每用户一个 JSON 主文件
  data/backups/{username}-*.json      历史快照（每用户保留最新 10 份）
  data/uploads/{username}/            每用户上传空间（UUID 命名 + manifest.json）
  data/quarantine/                    隔离区
"""

from __future__ import annotations

import os
from pathlib import Path

from .backup import BackupManager
from .models import (
    ACCENTS,
    FILE_STATUSES,
    HABIT_FREQUENCIES,
    PLAN_STATUSES,
    SCAN_STATUSES,
    SOURCE_TYPES,
    TASK_STATUSES,
    THEME_MODES,
    AIConfigRecord,
    CheckinRecord,
    FileMeta,
    MathNoteRecord,
    PlanRecord,
    PlanTemplateRecord,
    ReviewRecord,
    SessionRecord,
    SettingsRecord,
    TaskRecord,
    UserData,
    UserInfo,
    USERNAME_RE,
    validate_username,
)
from .store import SCHEMA_VERSION, UserDataStore
from .uploads import ALLOWED_EXTENSIONS, DEFAULT_SIZE_CAP, UploadSpace

_DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "data"


def default_data_root() -> Path:
    """默认数据根目录：优先 DATA_ROOT 环境变量，否则 <project>/data。"""
    env = os.environ.get("DATA_ROOT")
    return Path(env) if env else _DEFAULT_ROOT


__all__ = [
    "UserDataStore",
    "BackupManager",
    "UploadSpace",
    "SCHEMA_VERSION",
    "DEFAULT_SIZE_CAP",
    "ALLOWED_EXTENSIONS",
    "default_data_root",
    # 记录类
    "UserData",
    "UserInfo",
    "TaskRecord",
    "PlanRecord",
    "SessionRecord",
    "CheckinRecord",
    "ReviewRecord",
    "SettingsRecord",
    "PlanTemplateRecord",
    "MathNoteRecord",
    "AIConfigRecord",
    "FileMeta",
    # 校验与常量
    "validate_username",
    "USERNAME_RE",
    "TASK_STATUSES",
    "PLAN_STATUSES",
    "HABIT_FREQUENCIES",
    "THEME_MODES",
    "ACCENTS",
    "FILE_STATUSES",
    "SCAN_STATUSES",
    "SOURCE_TYPES",
]
