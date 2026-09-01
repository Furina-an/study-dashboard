"""日历视图测试：任务/复习/专注按日期区间返回，用户隔离。"""
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.models import Review, Session as SessionModel, Task


def _user_id(client, headers):
    return client.get("/api/auth/me", headers=headers).json()["id"]


def _add_session(db, user_id, minutes, day):
    completed = datetime.combine(day, datetime.min.time()) + timedelta(hours=10)
    db.add(
        SessionModel(
            user_id=user_id,
            duration_minutes=minutes,
            started_at=completed,
            completed_at=completed,
        )
    )


def test_calendar_requires_auth(client):
    resp = client.get("/api/calendar?start=2026-01-01&end=2026-01-31")
    assert resp.status_code == 401


def test_calendar_returns_tasks_reviews_focus(client, db_session, auth_headers):
    user_id = _user_id(client, auth_headers)
    today = date.today()
    t1 = Task(user_id=user_id, title="到期任务", due_date=today)
    t2 = Task(user_id=user_id, title="区间外任务", due_date=today + timedelta(days=20))
    db_session.add_all([t1, t2])
    db_session.flush()
    db_session.add(
        Review(
            user_id=user_id,
            source_type="task",
            source_id=t1.id,
            due_date=today,
            interval_days=1,
        )
    )
    _add_session(db_session, user_id, 25, today)
    _add_session(db_session, user_id, 50, today + timedelta(days=20))
    db_session.commit()

    start = today - timedelta(days=7)
    end = today + timedelta(days=7)
    resp = client.get(
        f"/api/calendar?start={start.isoformat()}&end={end.isoformat()}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert [t["title"] for t in data["tasks"]] == ["到期任务"]
    assert data["tasks"][0]["due_date"] == today.isoformat()
    assert len(data["reviews"]) == 1
    assert data["reviews"][0]["source_title"] == "到期任务"
    assert data["focus_minutes"].get(today.isoformat()) == 25
    assert data["focus_minutes"].get((today + timedelta(days=20)).isoformat()) is None


def test_calendar_invalid_range(client, auth_headers):
    assert (
        client.get(
            "/api/calendar?start=2026-02-01&end=2026-01-01",
            headers=auth_headers,
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/api/calendar?start=2026-01-01&end=2027-02-01",
            headers=auth_headers,
        ).status_code
        == 400
    )


def test_calendar_isolation(client, db_session, auth_headers, other_headers):
    user_a = _user_id(client, auth_headers)
    user_b = _user_id(client, other_headers)
    db_session.add(Task(user_id=user_a, title="A的任务", due_date=date.today()))
    db_session.add(Task(user_id=user_b, title="B的任务", due_date=date.today()))
    db_session.commit()

    resp = client.get(
        f"/api/calendar?start={date.today().isoformat()}&end={date.today().isoformat()}",
        headers=other_headers,
    )
    assert [t["title"] for t in resp.json()["tasks"]] == ["B的任务"]
