"""学习文件测试：上传校验、越权隔离、管理员整合、查毒预留。"""

import os
import shutil
import sys
import uuid
from pathlib import Path

import pytest

# 上传大小上限设为 5MB（每个测试的目录由 autouse fixture 隔离）
os.environ["MAX_UPLOAD_MB"] = "5"

PDF_HEAD = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n" + b"x" * 200


@pytest.fixture(autouse=True)
def _fresh_upload_dir(monkeypatch):
    root = Path(__file__).resolve().parent / ".upload_tmp"
    tmp = root / f"test_{uuid.uuid4().hex}"
    tmp.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def _upload(
    client,
    headers,
    filename="notes.pdf",
    data=PDF_HEAD,
    category="数学",
    description="高数笔记",
    content_type="application/pdf",
):
    return client.post(
        "/api/files",
        content=data,
        headers={
            **headers,
            "Content-Type": content_type,
        },
        params={"filename": filename, "category": category, "description": description},
    )


def _register(client, username):
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "secret123",
            "invite_code": "test-invite",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_upload_and_list_and_download(client, auth_headers, _fresh_upload_dir):
    response = _upload(client, auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["original_name"] == "notes.pdf"
    assert data["size_bytes"] == len(PDF_HEAD)
    assert data["category"] == "数学"
    assert data["status"] == "uploaded"
    assert data["scan_status"] == "pending"
    assert data["integrated"] is False
    file_id = data["id"]

    listed = client.get("/api/files", headers=auth_headers).json()
    assert len(listed) == 1
    assert listed[0]["id"] == file_id

    download = client.get(f"/api/files/{file_id}/download", headers=auth_headers)
    assert download.status_code == 200
    assert download.content == PDF_HEAD
    assert "attachment" in download.headers.get("content-disposition", "")


def test_upload_requires_auth(client):
    assert client.post("/api/files", content=PDF_HEAD).status_code == 401


def test_upload_rejects_bad_extension(client, auth_headers):
    response = _upload(client, auth_headers, filename="virus.exe", data=b"MZ\x90\x00")
    assert response.status_code == 400
    assert "不支持的文件类型" in response.json()["detail"]


def test_upload_rejects_mismatched_content(client, auth_headers):
    # 扩展名是 pdf，但内容是脚本 → 魔数校验拒绝
    response = _upload(client, auth_headers, filename="fake.pdf", data=b"#!/bin/sh\nrm -rf /\n")
    assert response.status_code == 400
    assert "不匹配" in response.json()["detail"]


def test_upload_rejects_too_large(client, auth_headers):
    big = PDF_HEAD + b"a" * (5 * 1024 * 1024 + 1)
    response = _upload(client, auth_headers, data=big)
    assert response.status_code == 413


def test_files_isolated_between_users(client, auth_headers):
    created = _upload(client, auth_headers).json()
    other = _register(client, "bob")

    listed = client.get("/api/files", headers=other).json()
    assert listed == []

    assert client.get(f"/api/files/{created['id']}/download", headers=other).status_code == 404
    assert client.delete(f"/api/files/{created['id']}", headers=other).status_code == 404
    assert client.get("/api/files", headers=auth_headers).json() != []


def test_admin_can_manage_and_integrate(client, auth_headers):
    created = _upload(client, auth_headers).json()
    admin = _register(client, "admin")  # ADMIN_USERNAMES 默认包含 admin

    # 管理员能看到全部文件
    listed = client.get("/api/files?scope=all", headers=admin).json()
    assert any(item["id"] == created["id"] for item in listed)
    # 普通用户即使传 scope=all 也只能看到自己的文件
    own = client.get("/api/files?scope=all", headers=auth_headers).json()
    assert len(own) == 1
    assert own[0]["id"] == created["id"]

    # 运营整合：放行 + 标记已整合 + 备注
    updated = client.patch(
        f"/api/files/{created['id']}",
        json={"status": "approved", "integrated": True, "admin_note": "已收录进高数资料库"},
        headers=admin,
    ).json()
    assert updated["status"] == "approved"
    assert updated["integrated"] is True
    assert updated["admin_note"] == "已收录进高数资料库"

    # 管理员可下载任意文件
    download = client.get(f"/api/files/{created['id']}/download", headers=admin)
    assert download.status_code == 200


def test_admin_quarantine_blocks_owner_download(client, auth_headers, _fresh_upload_dir):
    created = _upload(client, auth_headers).json()
    admin = _register(client, "admin")

    quarantined = client.patch(
        f"/api/files/{created['id']}", json={"status": "quarantined"}, headers=admin
    ).json()
    assert quarantined["status"] == "quarantined"

    # 本人也不能下载被隔离文件
    assert (
        client.get(f"/api/files/{created['id']}/download", headers=auth_headers).status_code
        == 403
    )
    # 文件确实移入隔离区（隔离目录内有一个文件）
    quarantine_dir = _fresh_upload_dir / "quarantine"
    assert len(list(quarantine_dir.iterdir())) == 1

    # 管理员放行后恢复可下载
    released = client.patch(
        f"/api/files/{created['id']}", json={"status": "approved"}, headers=admin
    ).json()
    assert released["status"] == "approved"
    assert (
        client.get(f"/api/files/{created['id']}/download", headers=auth_headers).status_code
        == 200
    )


def test_admin_only_operations_denied_for_normal_user(client, auth_headers):
    created = _upload(client, auth_headers).json()
    assert (
        client.patch(f"/api/files/{created['id']}", json={"status": "approved"}, headers=auth_headers).status_code
        == 403
    )
    assert (
        client.post(f"/api/files/{created['id']}/scan", headers=auth_headers).status_code
        == 403
    )


def test_scan_placeholder_message(client, auth_headers):
    created = _upload(client, auth_headers).json()
    admin = _register(client, "admin")
    result = client.post(f"/api/files/{created['id']}/scan", headers=admin).json()
    assert result["scan_status"] in ("pending", "clean")
    assert "SCAN_COMMAND" in result["scan_message"]


def test_scan_hook_infected_quarantines(monkeypatch, client, auth_headers, _fresh_upload_dir):
    scan_script = _fresh_upload_dir / "fake_scan.py"
    scan_script.write_text(
        "import sys\nsys.exit(int(sys.argv[1]))\n", encoding="utf-8"
    )
    monkeypatch.setenv("SCAN_COMMAND", f"{sys.executable} {scan_script} 1")

    created = _upload(client, auth_headers).json()
    assert created["scan_status"] == "infected"
    assert created["status"] == "quarantined"
    assert (
        client.get(f"/api/files/{created['id']}/download", headers=auth_headers).status_code
        == 403
    )


def test_scan_hook_clean_passes(monkeypatch, client, auth_headers, _fresh_upload_dir):
    scan_script = _fresh_upload_dir / "fake_scan.py"
    scan_script.write_text(
        "import sys\nsys.exit(int(sys.argv[1]))\n", encoding="utf-8"
    )
    monkeypatch.setenv("SCAN_COMMAND", f"{sys.executable} {scan_script} 0")

    created = _upload(client, auth_headers).json()
    assert created["scan_status"] == "clean"
    assert created["status"] == "uploaded"


def test_delete_removes_row_and_file(client, auth_headers):
    created = _upload(client, auth_headers).json()
    assert client.delete(f"/api/files/{created['id']}", headers=auth_headers).status_code == 204
    assert client.get("/api/files", headers=auth_headers).json() == []
    assert (
        client.get(f"/api/files/{created['id']}/download", headers=auth_headers).status_code
        == 404
    )
