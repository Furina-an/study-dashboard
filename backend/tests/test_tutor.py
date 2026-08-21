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


# ---------------- 免费/自定义双模式 + 调整窗口设置 ----------------

def test_settings_defaults(client, auth_headers, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    data = client.get("/api/tutor/settings", headers=auth_headers).json()
    assert data["mode"] == "custom"
    assert data["model"] == ""
    assert data["style"] == "socratic"
    assert data["temperature"] == 0.7
    assert data["max_tokens"] == 1000
    assert data["context_limit"] == 20
    assert data["free_available"] is False


def test_settings_save_and_validate(client, auth_headers):
    # 非法值 422
    assert (
        client.put("/api/tutor/settings", json={"mode": "hack"}, headers=auth_headers).status_code == 422
    )
    assert (
        client.put("/api/tutor/settings", json={"temperature": 9}, headers=auth_headers).status_code == 422
    )
    assert (
        client.put("/api/tutor/settings", json={"max_tokens": 10}, headers=auth_headers).status_code == 422
    )
    assert (
        client.put("/api/tutor/settings", json={"style": "bad"}, headers=auth_headers).status_code == 422
    )
    # 保存
    response = client.put(
        "/api/tutor/settings",
        json={
            "mode": "free",
            "model": "qwen-plus",
            "style": "detailed",
            "temperature": 1.2,
            "max_tokens": 2000,
            "context_limit": 8,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "free"
    assert data["model"] == "qwen-plus"
    assert data["style"] == "detailed"
    assert data["temperature"] == 1.2
    assert data["max_tokens"] == 2000
    assert data["context_limit"] == 8
    # 读取保持
    fetched = client.get("/api/tutor/settings", headers=auth_headers).json()
    assert fetched["context_limit"] == 8


def test_settings_isolation(client, auth_headers, other_headers):
    client.put(
        "/api/tutor/settings", json={"mode": "free", "max_tokens": 3000}, headers=auth_headers
    )
    data = client.get("/api/tutor/settings", headers=other_headers).json()
    assert data["mode"] == "custom"
    assert data["max_tokens"] == 1000


def test_free_mode_without_env_key(client, auth_headers, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client.put("/api/tutor/settings", json={"mode": "free"}, headers=auth_headers)
    response = client.post("/api/tutor/chat", json={"message": "hi"}, headers=auth_headers)
    assert response.status_code == 400
    assert "免费通道" in response.json()["detail"]


def test_free_mode_passes_params(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_BASE", "https://free.example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "free-model")
    monkeypatch.setenv("LLM_API_KEY", "free-key")
    calls = {}

    def fake_chat(*args, **kwargs):
        calls["base_url"] = args[0]
        calls["model"] = args[1]
        calls["messages"] = args[3]
        calls["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr("app.routers.tutor.chat_completion", fake_chat)
    client.put(
        "/api/tutor/settings",
        json={"mode": "free", "style": "concise", "temperature": 0.3, "max_tokens": 500},
        headers=auth_headers,
    )
    response = client.post(
        "/api/tutor/chat",
        json={"message": "解释一下", "subject": "数学"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert calls["base_url"] == "https://free.example.com/v1"
    assert calls["model"] == "free-model"
    assert calls["kwargs"]["temperature"] == 0.3
    assert calls["kwargs"]["max_tokens"] == 500
    system = calls["messages"][0]["content"]
    assert "简洁直接" in system
    assert "科目是「数学」" in calls["messages"][1]["content"]


def test_custom_mode_uses_saved_config_and_override(client, auth_headers, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client.put(
        "/api/ai/config",
        json={
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "sk-test-abc",
        },
        headers=auth_headers,
    )
    calls = {}

    def fake_chat(*args, **kwargs):
        calls["base_url"] = args[0]
        calls["model"] = args[1]
        calls["messages"] = args[3]
        calls["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr("app.routers.tutor.chat_completion", fake_chat)
    response = client.post(
        "/api/tutor/chat",
        json={
            "message": "hi",
            "model": "deepseek-reasoner",
            "temperature": 0.1,
            "max_tokens": 800,
            "style": "exam",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert calls["base_url"] == "https://api.deepseek.com/v1"
    assert calls["model"] == "deepseek-reasoner"
    assert calls["kwargs"]["temperature"] == 0.1
    assert calls["kwargs"]["max_tokens"] == 800
    assert "小测验" in calls["messages"][0]["content"]


def test_context_limit_truncation(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    client.put("/api/tutor/settings", json={"context_limit": 4}, headers=auth_headers)
    seen = {}

    def fake_chat(*args, **kwargs):
        seen["messages"] = args[3]
        return "ok"

    monkeypatch.setattr("app.routers.tutor.chat_completion", fake_chat)
    session_id = None
    for i in range(6):
        response = client.post(
            "/api/tutor/chat",
            json={"message": f"问题{i}", "session_id": session_id},
            headers=auth_headers,
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]
    history = [m for m in seen["messages"] if m["role"] != "system"]
    assert len(history) == 4
    contents = [m["content"] for m in history]
    assert "问题4" in contents
    assert "问题5" in contents
    assert "问题0" not in contents
