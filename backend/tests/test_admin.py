from datetime import datetime, timedelta
import pytest
from datetime import datetime, timedelta

from app.models import InviteCode


def _register(client, username, invite_code="test-invite"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123", "invite_code": invite_code},
    )


@pytest.fixture()
def admin_headers(client):
    response = _register(client, "admin")
    assert response.status_code == 201
    assert response.json()["user"]["is_admin"] is True
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_invites(client, headers, count=1, max_uses=1, **extra):
    payload = {"count": count, "max_uses": max_uses, **extra}
    return client.post("/api/admin/invites", json=payload, headers=headers)


def test_non_admin_forbidden(client, auth_headers):
    assert client.get("/api/admin/invites", headers=auth_headers).status_code == 403
    assert client.get("/api/admin/stats", headers=auth_headers).status_code == 403
    assert client.get("/api/admin/users", headers=auth_headers).status_code == 403
    assert (
        client.post("/api/admin/invites", json={"count": 1}, headers=auth_headers).status_code
        == 403
    )


def test_unauthenticated_forbidden(client):
    assert client.get("/api/admin/invites").status_code == 401


def test_generate_invites(client, admin_headers):
    response = _create_invites(
        client, admin_headers, count=3, max_uses=2, expires_days=30, remark="第一批"
    )
    assert response.status_code == 201
    codes = response.json()
    assert len(codes) == 3
    for code in codes:
        assert len(code["code"].split("-")) == 3  # XXXX-XXXX-XXXX
        assert code["max_uses"] == 2
        assert code["used_count"] == 0
        assert code["active"] is True
        assert code["remark"] == "第一批"
        assert code["expires_at"] is not None
    # 无重复码
    raw = [code["code"] for code in codes]
    assert len(set(raw)) == 3


def test_register_consumes_db_invite(client, admin_headers):
    response = _create_invites(client, admin_headers, count=1, max_uses=1)
    code = response.json()[0]["code"]
    assert _register(client, "carol", code).status_code == 201
    # 第二次使用同码失败
    assert _register(client, "dave", code).status_code == 400
    # 用完后 used_count 与剩余统计正确
    invite = client.get("/api/admin/invites", headers=admin_headers).json()[0]
    assert invite["used_count"] == 1
    assert invite["max_uses"] == 1


def test_disabled_invite_rejected(client, admin_headers):
    code = _create_invites(client, admin_headers, count=1).json()[0]
    invite_id = code["id"]
    assert (
        client.patch(
            f"/api/admin/invites/{invite_id}",
            json={"active": False},
            headers=admin_headers,
        ).json()["active"]
        is False
    )
    assert _register(client, "carol", code["code"]).status_code == 400


def test_expired_invite_rejected(client, db_session):
    from app.models import User
    from app.security import hash_password

    db_session.add(User(username="admin", password_hash=hash_password("secret123")))
    db_session.commit()
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    code = _create_invites(client, headers, count=1).json()[0]
    invite = db_session.query(InviteCode).filter_by(id=code["id"]).one()
    invite.expires_at = datetime.now() - timedelta(days=1)
    db_session.commit()
    assert _register(client, "carol", code["code"]).status_code == 400


def test_master_code_still_works(client):
    assert _register(client, "eve").status_code == 201


def test_admin_stats(client, admin_headers):
    _create_invites(client, admin_headers, count=2, max_uses=3)
    stats = client.get("/api/admin/stats", headers=admin_headers).json()
    assert stats["total_users"] == 1  # 仅 admin
    assert stats["total_invites"] == 2
    assert stats["active_invites"] == 2
    assert stats["unused_invites"] == 2


def test_admin_users_list(client, admin_headers):
    _register(client, "carol")
    users = client.get("/api/admin/users", headers=admin_headers).json()
    names = {user["username"]: user for user in users}
    assert set(names) >= {"admin", "carol"}
    assert names["admin"]["is_admin"] is True
    assert names["carol"]["is_admin"] is False


def test_update_and_delete_invite(client, admin_headers):
    code = _create_invites(client, admin_headers, count=1).json()[0]
    invite_id = code["id"]
    updated = client.patch(
        f"/api/admin/invites/{invite_id}",
        json={"max_uses": 5, "remark": "内部使用"},
        headers=admin_headers,
    ).json()
    assert updated["max_uses"] == 5
    assert updated["remark"] == "内部使用"
    assert client.delete(f"/api/admin/invites/{invite_id}", headers=admin_headers).status_code == 204
    assert client.patch(f"/api/admin/invites/{invite_id}", json={}, headers=admin_headers).status_code == 404


def test_disable_user_blocks_login_and_old_token(client, admin_headers):
    reg = _register(client, "carol")
    carol_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    # 禁用前正常访问
    assert client.get("/api/tasks", headers=carol_headers).status_code == 200
    users = client.get("/api/admin/users", headers=admin_headers).json()
    carol = next(u for u in users if u["username"] == "carol")
    assert carol["is_active"] is True
    updated = client.patch(
        f"/api/admin/users/{carol['id']}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    # 登录被拒
    assert (
        client.post(
            "/api/auth/login", json={"username": "carol", "password": "secret123"}
        ).status_code
        == 401
    )
    # 旧 token 立即失效
    assert client.get("/api/tasks", headers=carol_headers).status_code == 401


def test_enable_user_restores_access(client, admin_headers):
    _register(client, "carol")
    users = client.get("/api/admin/users", headers=admin_headers).json()
    carol = next(u for u in users if u["username"] == "carol")
    client.patch(
        f"/api/admin/users/{carol['id']}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert (
        client.post(
            "/api/auth/login", json={"username": "carol", "password": "secret123"}
        ).status_code
        == 401
    )
    client.patch(
        f"/api/admin/users/{carol['id']}",
        json={"is_active": True},
        headers=admin_headers,
    )
    assert (
        client.post(
            "/api/auth/login", json={"username": "carol", "password": "secret123"}
        ).status_code
        == 200
    )


def test_admin_cannot_disable_self(client, admin_headers):
    users = client.get("/api/admin/users", headers=admin_headers).json()
    admin = next(u for u in users if u["username"] == "admin")
    response = client.patch(
        f"/api/admin/users/{admin['id']}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_admin_cannot_disable_other_admin(client, admin_headers, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "admin,carol")
    _register(client, "carol")
    users = client.get("/api/admin/users", headers=admin_headers).json()
    carol = next(u for u in users if u["username"] == "carol")
    response = client.patch(
        f"/api/admin/users/{carol['id']}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_non_admin_cannot_update_user(client, auth_headers):
    response = client.patch(
        "/api/admin/users/1", json={"is_active": False}, headers=auth_headers
    )
    assert response.status_code == 403


def test_update_user_not_found(client, admin_headers):
    response = client.patch(
        "/api/admin/users/99999", json={"is_active": False}, headers=admin_headers
    )
    assert response.status_code == 404
