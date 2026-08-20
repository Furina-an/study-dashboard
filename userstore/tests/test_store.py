"""store 测试：往返、隔离、原子写、路径穿越防护、list_users。"""

from __future__ import annotations

import json

import pytest

from userstore.models import TaskRecord, UserData, UserInfo
from userstore.store import UserDataStore


def _sample_data(username="alice") -> UserData:
    return UserData(
        user=UserInfo(username=username, password_hash="h", created_at="t"),
        tasks=(TaskRecord(id=1, title="高数"),),
    )


def test_save_load_round_trip(data_root):
    store = UserDataStore(data_root)
    store.save("alice", _sample_data("alice"))
    loaded = store.load("alice")
    assert loaded.user.username == "alice"
    assert loaded.tasks[0].title == "高数"
    assert store.exists("alice")


def test_load_missing_returns_default(data_root):
    store = UserDataStore(data_root)
    data = store.load("nobody")
    assert data.user.username == "nobody"
    assert data.tasks == ()


def test_user_isolation(data_root):
    store = UserDataStore(data_root)
    store.save("alice", _sample_data("alice"))
    store.save("bob", _sample_data("bob"))
    assert store.load("alice").tasks[0].title == "高数"
    assert store.load("bob").tasks[0].title == "高数"
    assert (data_root / "users" / "alice.json").exists()
    assert (data_root / "users" / "bob.json").exists()
    payload = json.loads((data_root / "users" / "bob.json").read_text(encoding="utf-8"))
    assert payload["user"] == "bob"


def test_delete(data_root):
    store = UserDataStore(data_root)
    store.save("alice", _sample_data("alice"))
    assert store.delete("alice") is True
    assert store.delete("alice") is False
    assert not store.exists("alice")


def test_atomic_write_no_half_file(data_root, monkeypatch):
    store = UserDataStore(data_root)

    def boom(*_args, **_kwargs):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("userstore.store.os.replace", boom)
    with pytest.raises(OSError):
        store.save("alice", _sample_data("alice"))
    assert not (data_root / "users" / "alice.json").exists()
    leftovers = list((data_root / "users").glob(".alice.json.tmp-*"))
    assert leftovers == []


def test_invalid_username_rejected(data_root):
    store = UserDataStore(data_root)
    for bad in ("ab", "../evil", "a/b", ""):
        with pytest.raises(ValueError):
            store.save(bad, _sample_data(bad))
        with pytest.raises(ValueError):
            store.load(bad)


def test_path_traversal_rejected(data_root):
    store = UserDataStore(data_root)
    with pytest.raises(ValueError):
        store._user_path("../secret")
    with pytest.raises(ValueError):
        store._user_path("..\\secret")


def test_corrupted_json_raises(data_root):
    store = UserDataStore(data_root)
    (data_root / "users").mkdir(parents=True, exist_ok=True)
    (data_root / "users" / "alice.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="损坏"):
        store.load("alice")


def test_list_users_sorted(data_root):
    store = UserDataStore(data_root)
    store.save("zeta", _sample_data("zeta"))
    store.save("alice", _sample_data("alice"))
    store.save("mike", _sample_data("mike"))
    assert store.list_users() == ("alice", "mike", "zeta")
