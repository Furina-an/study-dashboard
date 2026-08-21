"""AI 助教：会话、聊天持久化与用户隔离测试。"""


def test_chat_without_key(client, auth_headers, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    response = client.post(
        "/api/tutor/chat",
        json={"message": "什么是导数？"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "AI" in response.json()["detail"]


def test_chat_creates_session_and_persists(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.routers.tutor.chat_completion",
        lambda *a, **k: "导数就是变化率。",
    )
    response = client.post(
        "/api/tutor/chat",
        json={"message": "什么是导数？", "subject": "数学"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "导数就是变化率。"
    assert data["title"] == "什么是导数？"
    session_id = data["session_id"]

    messages = client.get(
        f"/api/tutor/sessions/{session_id}/messages", headers=auth_headers
    ).json()
    assert len(messages) == 2
    assert [m["role"] for m in messages] == ["user", "assistant"]

    sessions = client.get("/api/tutor/sessions", headers=auth_headers).json()
    assert len(sessions) == 1
    assert sessions[0]["message_count"] == 2
    assert sessions[0]["title"] == "什么是导数？"


def test_chat_continues_existing_session(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.routers.tutor.chat_completion",
        lambda *a, **k: "回答",
    )
    first = client.post(
        "/api/tutor/chat", json={"message": "第一问"}, headers=auth_headers
    ).json()
    second = client.post(
        "/api/tutor/chat",
        json={"session_id": first["session_id"], "message": "第二问"},
        headers=auth_headers,
    )
    assert second.status_code == 200
    assert second.json()["session_id"] == first["session_id"]
    sessions = client.get("/api/tutor/sessions", headers=auth_headers).json()
    assert len(sessions) == 1
    assert sessions[0]["message_count"] == 4


def test_delete_session(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.routers.tutor.chat_completion",
        lambda *a, **k: "回答",
    )
    session_id = client.post(
        "/api/tutor/chat", json={"message": "你好"}, headers=auth_headers
    ).json()["session_id"]
    response = client.delete(
        f"/api/tutor/sessions/{session_id}", headers=auth_headers
    )
    assert response.status_code == 204
    assert (
        client.get(
            f"/api/tutor/sessions/{session_id}/messages", headers=auth_headers
        ).status_code
        == 404
    )


def test_user_isolation(client, auth_headers, other_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.routers.tutor.chat_completion",
        lambda *a, **k: "回答",
    )
    session_id = client.post(
        "/api/tutor/chat", json={"message": "A 的对话"}, headers=auth_headers
    ).json()["session_id"]

    # B 看不到 A 的会话
    assert (
        client.get(
            f"/api/tutor/sessions/{session_id}/messages", headers=other_headers
        ).status_code
        == 404
    )
    # B 的会话列表为空
    assert client.get("/api/tutor/sessions", headers=other_headers).json() == []
    # B 不能删 A 的会话
    assert (
        client.delete(
            f"/api/tutor/sessions/{session_id}", headers=other_headers
        ).status_code
        == 404
    )
