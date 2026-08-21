"""安全中心扫描、推荐文件分享、高数资料管理测试。"""

import shutil
import uuid
from pathlib import Path

import pytest

PDF_HEAD = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n" + b"x" * 200


@pytest.fixture(autouse=True)
def _fresh_upload_dir(monkeypatch):
    root = Path(__file__).resolve().parent / ".upload_tmp"
    tmp = root / f"test_{uuid.uuid4().hex}"
    tmp.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


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


def _admin_headers(client):
    return _register(client, "admin")


def _upload(client, headers, filename="notes.pdf", data=PDF_HEAD):
    return client.post(
        "/api/files",
        content=data,
        headers={**headers, "Content-Type": "application/pdf"},
        params={"filename": filename},
    )


# ---------------- 推荐文件分享 ----------------

def test_recommended_visible_and_downloadable(client, _fresh_upload_dir):
    admin = _admin_headers(client)
    user = _register(client, "bob")
    fid = _upload(client, admin).json()["id"]
    # 未推荐：普通用户推荐列表为空
    assert client.get("/api/files/recommended", headers=user).json() == []
    # 管理员标记推荐
    response = client.patch(
        f"/api/files/{fid}", json={"is_recommended": True}, headers=admin
    )
    assert response.status_code == 200
    assert response.json()["is_recommended"] is True
    rec = client.get("/api/files/recommended", headers=user).json()
    assert len(rec) == 1 and rec[0]["id"] == fid
    # 普通用户可下载推荐文件
    assert client.get(f"/api/files/{fid}/download", headers=user).status_code == 200


def test_quarantined_recommended_hidden_from_users(client, _fresh_upload_dir):
    admin = _admin_headers(client)
    user = _register(client, "bob")
    fid = _upload(client, admin).json()["id"]
    client.patch(
        f"/api/files/{fid}",
        json={"status": "quarantined", "is_recommended": True},
        headers=admin,
    )
    assert client.get("/api/files/recommended", headers=user).json() == []
    # 非上传者下载隔离文件：不暴露存在，返回 404；管理员仍可下载（运营权限）
    assert client.get(f"/api/files/{fid}/download", headers=user).status_code == 404
    assert client.get(f"/api/files/{fid}/download", headers=admin).status_code == 200


# ---------------- 安全中心扫描 ----------------

def test_scan_summary_and_all_and_logs(client, _fresh_upload_dir):
    admin = _admin_headers(client)
    _upload(client, admin)
    summary = client.get("/api/admin/scan-summary", headers=admin).json()
    assert summary["total_files"] == 1
    assert summary["pending"] == 1
    assert summary["scan_command_configured"] is False
    # 全量扫描（未配置命令 → 全部 pending，不触碰文件）
    result = client.post("/api/admin/scan-all", headers=admin).json()
    assert result["total"] == 1
    assert result["pending"] == 1
    assert "扫描完成" in result["message"]
    logs = client.get("/api/admin/scan-logs", headers=admin).json()
    assert len(logs) == 1
    assert logs[0]["action"] == "manual"
    assert logs[0]["total_files"] == 1
    # 非管理员 403
    user = _register(client, "bob")
    assert client.post("/api/admin/scan-all", headers=user).status_code == 403
    assert client.get("/api/admin/scan-summary", headers=user).status_code == 403


def test_scan_error_when_command_bad(client, _fresh_upload_dir, monkeypatch):
    monkeypatch.setenv("SCAN_COMMAND", "no-such-scanner-xyz")
    admin = _admin_headers(client)
    _upload(client, admin)
    result = client.post("/api/admin/scan-all", headers=admin).json()
    assert result["error"] == 1
    summary = client.get("/api/admin/scan-summary", headers=admin).json()
    assert summary["error"] == 1
    assert summary["scan_command_configured"] is True


# ---------------- 高数资料 ----------------

def test_math_resources_crud(client, _fresh_upload_dir):
    admin = _admin_headers(client)
    user = _register(client, "bob")
    # 非管理员上传 403
    assert (
        client.post(
            "/api/math/resources",
            content=PDF_HEAD,
            headers={**user, "Content-Type": "application/pdf"},
            params={"filename": "a.pdf", "title": "x"},
        ).status_code
        == 403
    )
    # 管理员上传
    response = client.post(
        "/api/math/resources",
        content=PDF_HEAD,
        headers={**admin, "Content-Type": "application/pdf"},
        params={"filename": "outline.pdf", "title": "高数提纲", "description": "期末用"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "高数提纲"
    rid = data["id"]
    # 用户可见并可下载
    listed = client.get("/api/math/resources", headers=user).json()
    assert [item["id"] for item in listed] == [rid]
    assert client.get(f"/api/math/resources/{rid}/download", headers=user).status_code == 200
    # 管理员编辑；非管理员编辑 403
    updated = client.patch(
        f"/api/math/resources/{rid}", json={"title": "高数提纲v2"}, headers=admin
    )
    assert updated.status_code == 200 and updated.json()["title"] == "高数提纲v2"
    assert (
        client.patch(
            f"/api/math/resources/{rid}", json={"title": "hack"}, headers=user
        ).status_code
        == 403
    )
    # 删除后列表为空
    assert client.delete(f"/api/math/resources/{rid}", headers=admin).status_code == 204
    assert client.get("/api/math/resources", headers=user).json() == []
    # 不存在 404
    assert (
        client.patch(
            "/api/math/resources/99999", json={"title": "x"}, headers=admin
        ).status_code
        == 404
    )
