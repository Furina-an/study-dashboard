from datetime import datetime, timedelta

from app.models import Session as SessionModel
from app.models import Task


def _user_id(client, headers):
    return client.get("/api/auth/me", headers=headers).json()["id"]


def test_today_stats_empty(client, auth_headers):
    response = client.get("/api/stats/today", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "date": datetime.now().date().isoformat(),
        "focus_minutes": 0,
        "focus_count": 0,
        "tasks_completed": 0,
    }


def test_today_stats_aggregates(client, db_session, auth_headers):
    user_id = _user_id(client, auth_headers)
    now = datetime.now()
    db_session.add_all(
        [
            SessionModel(
                user_id=user_id, duration_minutes=25, completed_at=now, started_at=now
            ),
            SessionModel(
                user_id=user_id,
                duration_minutes=45,
                completed_at=now - timedelta(minutes=1),
                started_at=now - timedelta(minutes=1),
            ),
            SessionModel(
                user_id=user_id,
                duration_minutes=60,
                completed_at=now - timedelta(days=1),
                started_at=now - timedelta(days=1),
            ),
            Task(user_id=user_id, title="今日完成", status="done", completed_at=now),
            Task(
                user_id=user_id,
                title="昨日完成",
                status="done",
                completed_at=now - timedelta(days=1),
            ),
        ]
    )
    db_session.commit()

    data = client.get("/api/stats/today", headers=auth_headers).json()
    assert data["focus_minutes"] == 70
    assert data["focus_count"] == 2
    assert data["tasks_completed"] == 1


def test_trend_returns_all_days_with_fill(client, db_session, auth_headers):
    user_id = _user_id(client, auth_headers)
    now = datetime.now()
    db_session.add_all(
        [
            SessionModel(
                user_id=user_id, duration_minutes=25, completed_at=now, started_at=now
            ),
            SessionModel(
                user_id=user_id,
                duration_minutes=50,
                completed_at=now - timedelta(days=2),
                started_at=now - timedelta(days=2),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/stats/trend?days=7", headers=auth_headers)
    assert response.status_code == 200
    points = response.json()
    assert len(points) == 7
    assert points[-1]["focus_minutes"] == 25
    assert points[4]["focus_minutes"] == 50
    assert points[0]["focus_minutes"] == 0
    assert all(p["focus_count"] >= 0 for p in points)


def test_trend_days_validation(client, auth_headers):
    assert (
        client.get("/api/stats/trend?days=0", headers=auth_headers).status_code == 422
    )
    assert (
        client.get("/api/stats/trend?days=999", headers=auth_headers).status_code
        == 422
    )