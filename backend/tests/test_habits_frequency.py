"""习惯频率测试：工作日 / 自定义星期打卡、streak 语义。"""
from datetime import date, timedelta

from sqlalchemy import select

from app.models import TaskCheckin


def _user_id(client, headers):
    return client.get("/api/auth/me", headers=headers).json()["id"]


def test_weekdays_habit_scheduling(client, auth_headers):
    habit = client.post(
        "/api/tasks",
        json={"title": "工作日习惯", "is_habit": True, "habit_frequency": "weekdays"},
        headers=auth_headers,
    ).json()
    assert habit["habit_frequency"] == "weekdays"
    assert habit["habit_days"] is None

    weekday = date.today().isoweekday()
    response = client.post(
        f"/api/tasks/{habit['id']}/checkin", headers=auth_headers
    )
    if weekday <= 5:
        assert response.status_code == 200
    else:
        assert response.status_code == 400

    data = client.get("/api/habits", headers=auth_headers).json()[0]
    assert data["scheduled_today"] == (weekday <= 5)


def test_custom_days_habit(client, auth_headers):
    today = date.today()
    weekday = today.isoweekday()
    other_day = (weekday % 7) + 1  # 与今天不同的某天
    habit = client.post(
        "/api/tasks",
        json={
            "title": "自定义习惯",
            "is_habit": True,
            "habit_frequency": "custom",
            "habit_days": [other_day],
        },
        headers=auth_headers,
    ).json()
    assert habit["habit_days"] == [other_day]
    assert (
        client.post(
            f"/api/tasks/{habit['id']}/checkin", headers=auth_headers
        ).status_code
        == 400
    )

    client.patch(
        f"/api/tasks/{habit['id']}",
        json={"habit_days": sorted({other_day, weekday})},
        headers=auth_headers,
    )
    response = client.post(
        f"/api/tasks/{habit['id']}/checkin", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["current_streak"] == 1


def test_custom_frequency_requires_days(client, auth_headers):
    response = client.post(
        "/api/tasks",
        json={"title": "坏习惯", "is_habit": True, "habit_frequency": "custom"},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_habit_days_range(client, auth_headers):
    response = client.post(
        "/api/tasks",
        json={
            "title": "坏习惯",
            "is_habit": True,
            "habit_frequency": "custom",
            "habit_days": [0, 8],
        },
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_weekday_streak_skips_weekend(client, db_session, auth_headers):
    user_id = _user_id(client, auth_headers)
    habit = client.post(
        "/api/tasks",
        json={"title": "工作日", "is_habit": True, "habit_frequency": "weekdays"},
        headers=auth_headers,
    ).json()
    today = date.today()
    # 最近 3 个工作日全部打卡
    days = []
    cursor = today
    while len(days) < 3:
        if cursor.isoweekday() <= 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    for day in reversed(days):
        db_session.add(
            TaskCheckin(user_id=user_id, task_id=habit["id"], checkin_date=day)
        )
    db_session.commit()

    entry = client.get("/api/habits", headers=auth_headers).json()[0]
    assert entry["current_streak"] == 3

