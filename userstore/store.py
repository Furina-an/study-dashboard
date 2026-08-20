"""用户数据主文件存储（纯标准库）。

每个用户一个 JSON 主文件：data/users/{username}.json。
写文件采用「临时文件 + os.replace」原子替换，避免半文件。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from .models import UserData, UserInfo, validate_username

SCHEMA_VERSION = 1

_ENCODING = "utf-8"


class UserDataStore:
    """按用户名读写用户主文件。data_root 为数据根目录。"""

    def __init__(self, data_root: str | Path) -> None:
        self.data_root = Path(data_root)
        self.users_dir = self.data_root / "users"
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # ---------- 内部工具 ----------

    def _lock_for(self, username: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(username)
            if lock is None:
                lock = threading.Lock()
                self._locks[username] = lock
            return lock

    def _user_path(self, username: str) -> Path:
        """校验用户名并返回主文件路径（含路径穿越防护）。"""
        validate_username(username)
        root = self.data_root.resolve()
        path = (self.users_dir / f"{username}.json").resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"非法路径：{path}")
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

    def _default_data(self, username: str) -> UserData:
        return UserData(user=UserInfo(username=username))

    # ---------- 公开 API ----------

    def exists(self, username: str) -> bool:
        """该用户名是否存在主文件。"""
        validate_username(username)
        return self._user_path(username).exists()

    def load(self, username: str) -> UserData:
        """读取用户数据；不存在则返回默认空数据。损坏 JSON 抛 ValueError。"""
        validate_username(username)
        with self._lock_for(username):
            path = self._user_path(username)
            if not path.exists():
                return self._default_data(username)
            try:
                raw = path.read_text(encoding=_ENCODING)
                payload = json.loads(raw)
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"用户数据损坏：{path}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"用户数据格式错误：{path}")
            # 兼容信封格式 {schema_version, user, data} 与旧平铺格式
            inner = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            data = UserData.from_dict(inner)
            # 内容与文件名不一致时以文件名为准，保证按用户隔离。
            return data.with_user(username)

    def save(self, username: str, data: UserData) -> Path:
        """保存用户数据（原子写）。data 与 username 不一致时以 username 为准。"""
        validate_username(username)
        normalized = data.with_user(username)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "user": username,
            "data": normalized.to_dict(),
        }
        with self._lock_for(username):
            path = self._user_path(username)
            self._atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
            return path

    def delete(self, username: str) -> bool:
        """删除用户主文件，返回是否确实删除。"""
        validate_username(username)
        with self._lock_for(username):
            path = self._user_path(username)
            if not path.exists():
                return False
            path.unlink()
            return True

    def list_users(self) -> tuple[str, ...]:
        """按用户名排序返回所有用户。"""
        if not self.users_dir.is_dir():
            return ()
        names = []
        for path in self.users_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding=_ENCODING))
            except (OSError, json.JSONDecodeError):
                continue
            user = payload.get("user") if isinstance(payload, dict) else None
            if isinstance(user, str):
                names.append(user)
            else:
                names.append(path.stem)
        return tuple(sorted(set(names)))
