def create_plan(client, headers, **overrides):
    payload = {"title": "大计划", "description": "描述", "status": "todo"}
    payload.update(overrides)
    return client.post("/api/plans", json=payload, headers=headers)


def test_create_and_list_plans(client, auth_headers):
    root = create_plan(client, auth_headers)
    assert root.status_code == 201
    root_id = root.json()["id"]
    child = create_plan(client, auth_headers, title="子计划", parent_id=root_id)
    assert child.status_code == 201
    assert child.json()["parent_id"] == root_id

    listed = client.get("/api/plans", headers=auth_headers).json()
    assert len(listed) == 2
    assert {p["title"] for p in listed} == {"大计划", "子计划"}


def test_create_plan_with_invalid_parent(client, auth_headers):
    response = create_plan(client, auth_headers, parent_id=999)
    assert response.status_code == 404


def test_patch_plan_fields_and_reparent(client, auth_headers):
    root = create_plan(client, auth_headers).json()
    child = create_plan(client, auth_headers, title="子", parent_id=root["id"]).json()

    response = client.patch(
        f"/api/plans/{child['id']}", json={"title": "改名", "status": "doing"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "改名"
    assert response.json()["status"] == "doing"

    # 移动到根（parent_id=None）
    response = client.patch(
        f"/api/plans/{child['id']}", json={"parent_id": None}, headers=auth_headers
    )
    assert response.json()["parent_id"] is None


def test_patch_plan_cycle_detection(client, auth_headers):
    a = create_plan(client, auth_headers, title="A").json()
    b = create_plan(client, auth_headers, title="B", parent_id=a["id"]).json()
    c = create_plan(client, auth_headers, title="C", parent_id=b["id"]).json()

    # 自己当自己的父级
    assert client.patch(f"/api/plans/{a['id']}", json={"parent_id": a["id"]}, headers=auth_headers).status_code == 400
    # 移动到自己的后代下（成环）
    assert client.patch(f"/api/plans/{a['id']}", json={"parent_id": c["id"]}, headers=auth_headers).status_code == 400
    # 父计划不存在
    assert client.patch(f"/api/plans/{a['id']}", json={"parent_id": 999}, headers=auth_headers).status_code == 404


def test_plan_isolation(client, auth_headers, other_headers):
    plan = create_plan(client, auth_headers).json()
    assert client.get("/api/plans", headers=other_headers).json() == []
    assert client.patch(f"/api/plans/{plan['id']}", json={"title": "x"}, headers=other_headers).status_code == 404
    assert client.delete(f"/api/plans/{plan['id']}", headers=other_headers).status_code == 404


def test_delete_plan_cascades_and_detaches_tasks(client, auth_headers):
    a = create_plan(client, auth_headers, title="A").json()
    b = create_plan(client, auth_headers, title="B", parent_id=a["id"]).json()
    c = create_plan(client, auth_headers, title="C", parent_id=b["id"]).json()

    task = client.post(
        "/api/tasks", json={"title": "挂 B 的任务", "plan_id": b["id"]}, headers=auth_headers
    ).json()

    assert client.delete(f"/api/plans/{a['id']}", headers=auth_headers).status_code == 204
    assert client.get("/api/plans", headers=auth_headers).json() == []
    # 任务仍在，但 plan_id 被置空
    task_after = client.get("/api/tasks", headers=auth_headers).json()
    assert len(task_after) == 1
    assert task_after[0]["plan_id"] is None


def test_task_attached_to_plan_and_filter(client, auth_headers):
    p1 = create_plan(client, auth_headers, title="计划一").json()
    p2 = create_plan(client, auth_headers, title="计划二").json()

    t1 = client.post(
        "/api/tasks", json={"title": "任务一", "plan_id": p1["id"]}, headers=auth_headers
    ).json()
    client.post("/api/tasks", json={"title": "任务二", "plan_id": p2["id"]}, headers=auth_headers)
    client.post("/api/tasks", json={"title": "无计划任务"}, headers=auth_headers)

    assert t1["plan_id"] == p1["id"]
    filtered = client.get(f"/api/tasks?plan_id={p1['id']}", headers=auth_headers).json()
    assert [t["title"] for t in filtered] == ["任务一"]
    # 其他用户的计划 id 过滤 → 404
    assert client.get("/api/tasks?plan_id=999", headers=auth_headers).status_code == 404


def test_task_with_invalid_plan(client, auth_headers, other_headers):
    foreign = create_plan(client, other_headers).json()
    assert client.post(
        "/api/tasks", json={"title": "x", "plan_id": 999}, headers=auth_headers
    ).status_code == 404
    assert client.post(
        "/api/tasks", json={"title": "x", "plan_id": foreign["id"]}, headers=auth_headers
    ).status_code == 404
    # 解除挂接
    own = create_plan(client, auth_headers).json()
    task = client.post(
        "/api/tasks", json={"title": "x", "plan_id": own["id"]}, headers=auth_headers
    ).json()
    updated = client.patch(
        f"/api/tasks/{task['id']}", json={"plan_id": None}, headers=auth_headers
    ).json()
    assert updated["plan_id"] is None


def test_breakdown_template(client, auth_headers):
    plan = create_plan(client, auth_headers, title="学习计划").json()
    response = client.post(
        f"/api/plans/{plan['id']}/breakdown",
        json={"mode": "template", "template_key": "study"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    created = response.json()["created"]
    assert 4 <= len(created) <= 6
    assert all(item["parent_id"] == plan["id"] for item in created)
    titles = [item["title"] for item in created]
    assert "预习资料" in titles and "学习核心内容" in titles

    # 未知模板 → 400
    assert client.post(
        f"/api/plans/{plan['id']}/breakdown",
        json={"mode": "template", "template_key": "nope"},
        headers=auth_headers,
    ).status_code == 400


class _FakeLLMResponse:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_breakdown_ai_without_key(client, auth_headers, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    plan = create_plan(client, auth_headers).json()
    response = client.post(
        f"/api/plans/{plan['id']}/breakdown",
        json={"mode": "ai"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "LLM_API_KEY" in response.json()["detail"]


def test_breakdown_ai_success(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    content = '{"children":[{"title":"AI子计划1","description":"说明一"},{"title":"AI子计划2"}]}'
    monkeypatch.setattr(
        "app.routers.plans.chat_completion",
        lambda *a, **k: content,
    )
    plan = create_plan(client, auth_headers, title="AI 计划").json()
    response = client.post(
        f"/api/plans/{plan['id']}/breakdown",
        json={"mode": "ai"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    created = response.json()["created"]
    assert [item["title"] for item in created] == ["AI子计划1", "AI子计划2"]
    assert created[0]["description"] == "说明一"


def test_breakdown_ai_unparseable(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.routers.plans.chat_completion",
        lambda *a, **k: "不是 JSON",
    )
    plan = create_plan(client, auth_headers).json()
    response = client.post(
        f"/api/plans/{plan['id']}/breakdown",
        json={"mode": "ai"},
        headers=auth_headers,
    )
    assert response.status_code == 502