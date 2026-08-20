"""backup 测试：快照内容、恢复、用户名匹配、损坏快照、保留 10 份。"""

from __future__ import annotations

import json

import pytest

from userstore.backup import BackupManager
from userstore.models import TaskRecord, UserData, UserInfo
from userstore.store import UserDataStore


def _sample(username="alice", title="高数") -> UserData:
    return UserData(
        user=UserInfo(username=username, password_hash="h", created_at="t"),
        tasks=(TaskRecord(id=1, title=title),),
    )


def test_snapshot_contains_schema_and_data(data_root):
    store = UserDataStore(data_root)
    store.save("alice", _sample())
    mgr = BackupManager(store)
    path = mgr.snapshot("alice")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["user"] == "alice"
    assert payload["data"]["tasks"][0]["title"] == "高数"


def test_restore_overwrites(data_root):
    store = UserDataStore(data_root)
    store.save("alice", _sample(title="旧标题"))
    mgr = BackupManager(store)
    mgr.snapshot("alice")
    # 改动主文件
    store.save("alice", _sample(title="新标题"))
    assert store.load("alice").tasks[0].title == "新标题"
    data = mgr.restore_latest("alice")
    assert data.tasks[0].title == "旧标题"
    assert store.load("alice").tasks[0].title == "旧标题"


def test_restore_username_mismatch_rejected(data_root):
    store = UserDataStore(data_root)
    store.save("alice", _sample())
    mgr = BackupManager(store)
    path = mgr.snapshot("alice")
    with pytest.raises(ValueError, match="不匹配"):
        mgr.restore("bob", path)


def test_restore_missing_snapshot(data_root):
    store = UserDataStore(data_root)
    mgr = BackupManager(store)
    with pytest.raises(FileNotFoundError):
        mgr.restore("alice", data_root / "nope.json")
    with pytest.raises(FileNotFoundError):
        mgr.restore_latest("alice")


def test_restore_corrupted_snapshot(data_root):
    store = UserDataStore(data_root)
    mgr = BackupManager(store)
    bad = data_root / "backups" / "alice-20260101-000000.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="损坏"):
        mgr.restore("alice", bad)


def test_restore_bad_schema_version(data_root):
    store = UserDataStore(data_root)
    mgr = BackupManager(store)
    path = data_root / "backups" / "alice-20260101-000000.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 99, "user": "alice", "data": {}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema_version"):
        mgr.restore("alice", path)


def test_prune_keeps_latest_10(data_root):
    store = UserDataStore(data_root)
    store.save("alice", _sample())
    mgr = BackupManager(store, keep=10)
    for _ in range(12):
        mgr.snapshot("alice")
    snaps = mgr.list_snapshots("alice")
    assert len(snaps) == 10
    # 保留的是最新的 10 份
    all_files = sorted((data_root / "backups").glob("alice-*.json"))
    assert len(all_files) == 10


def test_snapshot_per_user_isolated(data_root):
    store = UserDataStore(data_root)
    store.save("alice", _sample())
    store.save("bob", _sample(username="bob", title="英语"))
    mgr = BackupManager(store)
    mgr.snapshot("alice")
    mgr.snapshot("bob")
    assert len(mgr.list_snapshots("alice")) == 1
    assert len(mgr.list_snapshots("bob")) == 1
