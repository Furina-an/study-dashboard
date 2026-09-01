"""AI 每日学习计划测试。"""
from datetime import date, timedelta


def _deadline(days: int = 3) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def test_daily_plan_requires_auth(client):
    resp = client.post(
        "/api/plans/daily-plan", json={"goal": "目标", "deadline": _deadline()}
    )
    assert resp.status_code == 401


def test_daily_plan_without_ai(client, auth_headers, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    resp = client.post(
        "/api/plans/daily-plan",
        json={"goal": "考研数学", "deadline": _deadline()},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "LLM_API_KEY" in resp.json()["detail"]


def test_daily_plan_deadline_in_past(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    resp = client.post(
        "/api/plans/daily-plan",
        json={"goal": "目标", "deadline": _deadline(-1)},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_daily_plan_creates_plan_and_scheduled_tasks(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    content = (
        '{"tasks":[{"title":"复习第一章","estimated_minutes":60},'
        '{"title":"做习题","estimated_minutes":30},'
        '{"title":"整理错题","estimated_minutes":30},'
        '{"title":"模拟测试","estimated_minutes":90}]}'
    )
    monkeypatch.setattr("app.routers.plans.chat_completion", lambda *a, **k: content)
    deadline = date.today() + timedelta(days=2)
    resp = client.post(
        "/api/plans/daily-plan",
        json={
            "goal": "线性代数冲刺",
            "deadline": deadline.isoformat(),
            "daily_minutes": 60,
            "subject": "数学",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["plan"]["title"] == "线性代数冲刺"
    assert body["plan"]["parent_id"] is None
    tasks = body["tasks"]
    assert len(tasks) == 4
    assert all(t["plan_id"] == body["plan"]["id"] for t in tasks)
    assert all(t["subject"] == "数学" for t in tasks)
    due_dates = sorted(t["due_date"] for t in tasks)
    assert all(date.fromisoformat(d) <= deadline for d in due_dates)
    # 每日 60 分钟：60→今天；30+30→明天；90→最后一天
    assert due_dates[0] == date.today().isoformat()
    assert due_dates[1] == due_dates[2]
    assert due_dates[3] == deadline.isoformat()


def test_daily_plan_attach_to_existing_plan_and_isolation(
    client, auth_headers, other_headers, monkeypatch
):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.routers.plans.chat_completion",
        lambda *a, **k: '{"tasks":[{"title":"任务A","estimated_minutes":30}]}',
    )
    plan = client.post(
        "/api/plans", json={"title": "目标计划"}, headers=auth_headers
    ).json()
    resp = client.post(
        "/api/plans/daily-plan",
        json={"goal": "目标", "deadline": _deadline(1), "plan_id": plan["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["plan"]["id"] == plan["id"]
    assert len(resp.json()["tasks"]) == 1

    # 用户 B 用 A 的 plan_id → 404
    resp = client.post(
        "/api/plans/daily-plan",
        json={"goal": "目标", "deadline": _deadline(1), "plan_id": plan["id"]},
        headers=other_headers,
    )
    assert resp.status_code == 404


def test_daily_plan_ai_unparseable(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.routers.plans.chat_completion", lambda *a, **k: "不是 JSON"
    )
    resp = client.post(
        "/api/plans/daily-plan",
        json={"goal": "目标", "deadline": _deadline(1)},
        headers=auth_headers,
    )
    assert resp.status_code == 502
