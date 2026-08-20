"""uploads 测试：blob 落盘、manifest 索引、隔离、白名单、魔数、大小上限。"""

from __future__ import annotations

import json

import pytest

from userstore.uploads import UploadSpace

PNG_HEAD = b"\x89PNG\r\n\x1a\n" + b"0" * 32
PDF_BYTES = b"%PDF-1.7\n%test\n" + b"0" * 32
ZIP_BYTES = b"PK\x03\x04" + b"0" * 32


def _read_manifest(root, username):
    path = root / "uploads" / username / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_put_writes_blob_and_manifest(data_root):
    space = UploadSpace(data_root)
    meta = space.put("alice", PDF_BYTES, "笔记.pdf", category="docs", description="高数")
    assert meta.file_id and meta.ext == ".pdf"
    assert meta.original_name == "笔记.pdf"
    blob = data_root / "uploads" / "alice" / meta.stored_name()
    assert blob.is_file()
    assert blob.read_bytes() == PDF_BYTES
    manifest = _read_manifest(data_root, "alice")
    assert manifest["user"] == "alice"
    assert len(manifest["files"]) == 1
    assert manifest["files"][0]["file_id"] == meta.file_id
    assert space.get("alice", meta.file_id) == PDF_BYTES


def test_user_isolation(data_root):
    space = UploadSpace(data_root)
    m1 = space.put("alice", PDF_BYTES, "a.pdf")
    m2 = space.put("bob", PNG_HEAD, "b.png")
    assert [f.file_id for f in space.list("alice")] == [m1.file_id]
    assert [f.file_id for f in space.list("bob")] == [m2.file_id]
    with pytest.raises(FileNotFoundError):
        space.get("alice", m2.file_id)
    assert not (data_root / "uploads" / "alice" / m2.stored_name()).exists()


def test_extension_whitelist(data_root):
    space = UploadSpace(data_root)
    with pytest.raises(ValueError, match="扩展名"):
        space.put("alice", b"hello", "virus.exe")
    with pytest.raises(ValueError, match="扩展名"):
        space.put("alice", b"hello", "no_ext")


def test_magic_mismatch_rejected(data_root):
    space = UploadSpace(data_root)
    with pytest.raises(ValueError, match="魔数"):
        space.put("alice", b"this is not a pdf at all", "fake.pdf")
    with pytest.raises(ValueError, match="魔数"):
        space.put("alice", b"hello world", "fake.png")


def test_empty_and_size_cap(data_root):
    space = UploadSpace(data_root)
    with pytest.raises(ValueError, match="为空"):
        space.put("alice", b"", "empty.pdf")
    with pytest.raises(ValueError, match="上限"):
        space.put("alice", PDF_BYTES + b"x" * 200, "big.pdf", size_cap=100)


def test_quarantine_release_remove(data_root):
    space = UploadSpace(data_root)
    meta = space.put("alice", ZIP_BYTES, "archive.zip")
    q = space.quarantine("alice", meta.file_id, reason="疑似病毒")
    assert q.is_file()
    assert not (data_root / "uploads" / "alice" / meta.stored_name()).exists()
    manifest = _read_manifest(data_root, "alice")
    assert manifest["files"][0]["status"] == "quarantined"
    assert manifest["files"][0]["scan_message"] == "疑似病毒"

    dst = space.release("alice", meta.file_id)
    assert dst == data_root / "uploads" / "alice" / meta.stored_name()
    assert dst.is_file()
    assert not q.exists()
    assert _read_manifest(data_root, "alice")["files"][0]["status"] == "uploaded"

    space.remove("alice", meta.file_id)
    assert not dst.exists()
    assert _read_manifest(data_root, "alice")["files"] == []


def test_release_non_quarantined_rejected(data_root):
    space = UploadSpace(data_root)
    meta = space.put("alice", PDF_BYTES, "ok.pdf")
    with pytest.raises(ValueError, match="未在隔离区"):
        space.release("alice", meta.file_id)


def test_remove_missing(data_root):
    space = UploadSpace(data_root)
    with pytest.raises(FileNotFoundError):
        space.remove("alice", "0" * 32)
    with pytest.raises(ValueError, match="文件 ID"):
        space.get("alice", "../evil")


def test_ensure_user_file_idempotent(data_root):
    space = UploadSpace(data_root)
    path = space.ensure_user_file("carol")
    assert path.is_file()
    again = space.ensure_user_file("carol")
    assert again == path
    assert _read_manifest(data_root, "carol")["files"] == []
