import httpx
import pytest


CONFIG_PAYLOAD = {
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "api_key": "sk-test-1234567890",
}


def test_get_config_default(client, auth_headers):
    response = client.get("/api/ai/config", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["has_api_key"] is False
    assert data["api_key_masked"] == ""
    assert data["base_url"]


def test_save_and_get_config_masked(client, auth_headers):
    response = client.put("/api/ai/config", json=CONFIG_PAYLOAD, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "deepseek"
    assert data["base_url"] == "https://api.deepseek.com/v1"
    assert data["model"] == "deepseek-chat"
    assert data["has_api_key"] is True
    # 掩码：不含完整 key
    assert "sk-test-1234567890" not in data["api_key_masked"]
    assert data["api_key_masked"].endswith("7890")
    assert data["api_key_masked"].startswith("sk-*")

    fetched = client.get("/api/ai/config", headers=auth_headers).json()
    assert fetched["api_key_masked"] == data["api_key_masked"]


def test_save_without_key_keeps_old(client, auth_headers):
    client.put("/api/ai/config", json=CONFIG_PAYLOAD, headers=auth_headers)
    response = client.put(
        "/api/ai/config",
        json={**CONFIG_PAYLOAD, "api_key": ""},
        headers=auth_headers,
    )
    data = response.json()
    assert data["has_api_key"] is True
    assert data["api_key_masked"].endswith("7890")


def test_save_updates_key(client, auth_headers):
    client.put("/api/ai/config", json=CONFIG_PAYLOAD, headers=auth_headers)
    response = client.put(
        "/api/ai/config",
        json={**CONFIG_PAYLOAD, "api_key": "sk-new-abcdef"},
        headers=auth_headers,
    )
    assert response.json()["api_key_masked"].endswith("cdef")


def test_delete_config(client, auth_headers):
    client.put("/api/ai/config", json=CONFIG_PAYLOAD, headers=auth_headers)
    assert client.delete("/api/ai/config", headers=auth_headers).status_code == 204
    data = client.get("/api/ai/config", headers=auth_headers).json()
    assert data["has_api_key"] is False
    assert data["api_key_masked"] == ""


def test_config_isolation(client, auth_headers, other_headers):
    client.put("/api/ai/config", json=CONFIG_PAYLOAD, headers=auth_headers)
    other = client.get("/api/ai/config", headers=other_headers).json()
    assert other["has_api_key"] is False
    assert other["api_key_masked"] == ""


def test_ai_config_requires_login(client):
    assert client.get("/api/ai/config").status_code == 401
    assert client.put("/api/ai/config", json=CONFIG_PAYLOAD).status_code == 401
    assert client.post("/api/ai/test", json={}).status_code == 401


def test_ai_test_without_key(client, auth_headers, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    response = client.post("/api/ai/test", json={}, headers=auth_headers)
    assert response.status_code == 400
    assert "API Key" in response.json()["detail"]


def test_ai_test_success_with_saved_config(client, auth_headers, monkeypatch):
    client.put("/api/ai/config", json=CONFIG_PAYLOAD, headers=auth_headers)
    calls = {}

    def fake_chat(base_url, model, api_key, messages, timeout=60.0):
        calls.update(
            base_url=base_url, model=model, api_key=api_key, timeout=timeout
        )
        return "你好"

    monkeypatch.setattr("app.routers.ai.chat_completion", fake_chat)
    response = client.post("/api/ai/test", json={}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "连接成功" in data["message"]
    assert data["latency_ms"] >= 0
    assert calls["base_url"] == "https://api.deepseek.com/v1"
    assert calls["model"] == "deepseek-chat"
    assert calls["api_key"] == "sk-test-1234567890"


def test_ai_test_uses_payload_first(client, auth_headers, monkeypatch):
    client.put("/api/ai/config", json=CONFIG_PAYLOAD, headers=auth_headers)
    calls = {}

    def fake_chat(base_url, model, api_key, messages, timeout=60.0):
        calls.update(base_url=base_url, model=model, api_key=api_key)
        return "你好"

    monkeypatch.setattr("app.routers.ai.chat_completion", fake_chat)
    response = client.post(
        "/api/ai/test",
        json={"base_url": "https://custom.example/v1", "model": "my-model", "api_key": "sk-temp"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert calls["base_url"] == "https://custom.example/v1"
    assert calls["model"] == "my-model"
    assert calls["api_key"] == "sk-temp"


def test_ai_test_http_error(client, auth_headers, monkeypatch):
    def fake_chat(*a, **k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("app.routers.ai.chat_completion", fake_chat)
    client.put("/api/ai/config", json=CONFIG_PAYLOAD, headers=auth_headers)
    response = client.post("/api/ai/test", json={}, headers=auth_headers)
    assert response.status_code == 400
    assert "网络错误" in response.json()["detail"] or "调用失败" in response.json()["detail"]


def test_breakdown_uses_user_config_first(client, auth_headers, monkeypatch):
    # 保存用户配置；环境变量配置一个不同的 key
    client.put("/api/ai/config", json=CONFIG_PAYLOAD, headers=auth_headers)
    monkeypatch.setenv("LLM_API_KEY", "env-key-should-not-be-used")
    calls = {}

    def fake_chat(base_url, model, api_key, messages, timeout=60.0):
        calls.update(base_url=base_url, model=model, api_key=api_key)
        return '{"children":[{"title":"用户配置生成的子计划"}]}'

    monkeypatch.setattr("app.routers.plans.chat_completion", fake_chat)
    plan = client.post("/api/plans", json={"title": "AI 计划"}, headers=auth_headers).json()
    response = client.post(
        f"/api/plans/{plan['id']}/breakdown",
        json={"mode": "ai"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    created = response.json()["created"]
    assert created[0]["title"] == "用户配置生成的子计划"
    assert calls["api_key"] == "sk-test-1234567890"
    assert calls["base_url"] == "https://api.deepseek.com/v1"
    assert calls["model"] == "deepseek-chat"


def test_breakdown_ai_without_any_config(client, auth_headers, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    plan = client.post("/api/plans", json={"title": "AI 计划"}, headers=auth_headers).json()
    response = client.post(
        f"/api/plans/{plan['id']}/breakdown",
        json={"mode": "ai"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "AI 设置" in response.json()["detail"]
