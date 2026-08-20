def test_register_success(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "carol", "password": "secret123", "invite_code": "test-invite"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data
    assert data["user"]["username"] == "carol"


def test_register_duplicate_username(client, auth_headers):
    response = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "secret123", "invite_code": "test-invite"},
    )
    assert response.status_code == 409


def test_register_wrong_invite_code(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "dave", "password": "secret123", "invite_code": "wrong-code"},
    )
    assert response.status_code == 400


def test_register_validation(client):
    # 密码过短
    assert (
        client.post(
            "/api/auth/register",
            json={"username": "eve", "password": "123", "invite_code": "test-invite"},
        ).status_code
        == 422
    )
    # 用户名过短
    assert (
        client.post(
            "/api/auth/register",
            json={"username": "ab", "password": "secret123", "invite_code": "test-invite"},
        ).status_code
        == 422
    )
    # 用户名含非法字符
    assert (
        client.post(
            "/api/auth/register",
            json={"username": "bad name", "password": "secret123", "invite_code": "test-invite"},
        ).status_code
        == 422
    )


def test_login_success(client, auth_headers):
    response = client.post(
        "/api/auth/login", json={"username": "alice", "password": "secret123"}
    )
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "alice"


def test_login_wrong_password(client, auth_headers):
    response = client.post(
        "/api/auth/login", json={"username": "alice", "password": "wrongpass"}
    )
    assert response.status_code == 401


def test_login_unknown_user(client):
    response = client.post(
        "/api/auth/login", json={"username": "nobody", "password": "secret123"}
    )
    assert response.status_code == 401


def test_me_with_token(client, auth_headers):
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_me_without_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_protected_routes_require_auth(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/stats/today").status_code == 401
    assert client.post("/api/sessions", json={"duration_minutes": 25}).status_code == 401


def test_data_isolation_between_users(client, auth_headers, other_headers):
    created = client.post(
        "/api/tasks", json={"title": "A 的任务"}, headers=auth_headers
    )
    assert created.status_code == 201
    task_id = created.json()["id"]

    # B 看不到 A 的任务
    assert client.get("/api/tasks", headers=other_headers).json() == []
    # B 不能修改/删除 A 的任务
    assert (
        client.patch(
            f"/api/tasks/{task_id}", json={"title": "x"}, headers=other_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/tasks/{task_id}", headers=other_headers).status_code
        == 404
    )
    # B 不能用 A 的任务 id 记录专注
    assert (
        client.post(
            "/api/sessions",
            json={"task_id": task_id, "duration_minutes": 25},
            headers=other_headers,
        ).status_code
        == 404
    )
    # A 给任务记录一次专注
    assert (
        client.post(
            "/api/sessions",
            json={"task_id": task_id, "duration_minutes": 25},
            headers=auth_headers,
        ).status_code
        == 201
    )
    # 统计互不影响
    assert (
        client.get("/api/stats/today", headers=other_headers).json()["focus_minutes"]
        == 0
    )
    assert (
        client.get("/api/stats/today", headers=auth_headers).json()["focus_count"]
        == 1
    )