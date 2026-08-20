"""用户数据快照与恢复（纯标准库）。

快照：data/backups/{username}-YYYYmmdd-HHMMSS.json（每用户独立，默认保留最新 10 份）。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import UserData, validate_username
from .store import SCHEMA_VERSION, UserDataStore

_ENCODING = "utf-8"

_SNAPSHOT_RE = re.compile(
    r"^(?P<user>[A-Za-z0-9_]+)-(?P<stamp>\d{8}-\d{6})(?:-(?P<counter>\d+))?\.json$"
)


class BackupManager:
    """基于 UserDataStore 的快照管理。keep 为每用户保留的快照份数。"""

    def __init__(self, store: UserDataStore, keep: int = 10) -> None:
        self.store = store
        self.keep = max(1, int(keep))
        self.backups_dir = store.data_root / "backups"

    # ---------- 内部工具 ----------

    def _snapshot_path(self, username: str, now: datetime | None = None) -> Path:
        stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
        base = self.backups_dir / f"{username}-{stamp}.json"
        path = base
        counter = 1
        while path.exists():
            path = self.backups_dir / f"{username}-{stamp}-{counter}.json"
            counter += 1
        return path

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
    def _sort_key(name: str) -> tuple[str, int]:
        match = _SNAPSHOT_RE.match(name)
        if match:
            return (match.group("stamp"), int(match.group("counter") or 0))
        return (name, 0)

    def _prune(self, username: str) -> None:
        for old in self.list_snapshots(username)[self.keep:]:
            old.unlink(missing_ok=True)

    # ---------- 公开 API ----------

    def snapshot(self, username: str) -> Path:
        """为指定用户生成全量 JSON 快照并返回路径。"""
        validate_username(username)
        data = self.store.load(username)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "user": username,
            "data": data.to_dict(),
        }
        path = self._snapshot_path(username)
        self._atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
        self._prune(username)
        return path

    def list_snapshots(self, username: str) -> tuple[Path, ...]:
        """返回该用户快照路径，最新在前。"""
        validate_username(username)
        if not self.backups_dir.is_dir():
            return ()
        paths = sorted(
            self.backups_dir.glob(f"{username}-*.json"),
            key=lambda p: self._sort_key(p.name),
            reverse=True,
        )
        return tuple(paths)

    def restore(self, username: str, path: str | Path) -> UserData:
        """从快照恢复并覆盖主文件。校验 schema_version 与用户名匹配。"""
        validate_username(username)
        snapshot = Path(path)
        if not snapshot.is_file():
            raise FileNotFoundError(f"快照不存在：{snapshot}")
        try:
            raw = snapshot.read_text(encoding=_ENCODING)
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"快照损坏：{snapshot}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"快照格式错误：{snapshot}")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"快照 schema_version 不兼容：{payload.get('schema_version')!r}"
            )
        if payload.get("user") != username:
            raise ValueError(
                f"快照用户名不匹配：快照属于 {payload.get('user')!r}，目标为 {username!r}"
            )
        data_payload = payload.get("data")
        if not isinstance(data_payload, dict):
            raise ValueError(f"快照缺少 data 字段：{snapshot}")
        data = UserData.from_dict(data_payload).with_user(username)
        self.store.save(username, data)
        return data

    def restore_latest(self, username: str) -> UserData:
        """恢复该用户最新一份快照。"""
        snaps = self.list_snapshots(username)
        if not snaps:
            raise FileNotFoundError(f"用户 {username} 没有可用快照")
        return self.restore(username, snaps[0])
