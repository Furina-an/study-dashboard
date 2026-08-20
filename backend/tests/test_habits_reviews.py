from datetime import date, datetime, timedelta


def _user_id(client, headers):
    return client.get("/api/auth/me", headers=headers).json()["id"]


def create_task(client, headers, **overrides):
    payload = {
        "title": "测试任务",
        "subject": "",
        "estimated_minutes": 25,
        "status": "todo",
        "is_habit": False,
    }
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=headers)


def make_habit(client, headers, title="每日背单词"):
    return create_task(client, headers, title=title, is_habit=True)


# ---------- 习惯打卡 ----------

def test_habit_create_and_checkin_idempotent(client, auth_headers):
    habit = make_habit(client, auth_headers).json()
    assert habit["is_habit"] is True
    assert habit["habit_frequency"] == "daily"

    first = client.post(f"/api/tasks/{habit['id']}/checkin", headers=auth_headers)
    assert first.status_code == 200
    assert first.json()["checked"] is True
    assert first.json()["current_streak"] == 1

    again = client.post(f"/api/tasks/{habit['id']}/checkin", headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["checked"] is True
    assert again.json()["current_streak"] == 1

    habits = client.get("/api/habits", headers=auth_headers).json()
    assert len(habits) == 1
    assert habits[0]["checked_today"] is True
    assert habits[0]["current_streak"] == 1
    today_checked = [d for d in habits[0]["last_7_days"] if d["checked"]]
    assert len(today_checked) == 1

    undone = client.delete(f"/api/tasks/{habit['id']}/checkin", headers=auth_headers)
    assert undone.status_code == 200
    assert undone.json()["checked"] is False
    assert undone.json()["current_streak"] == 0
    habits = client.get("/api/habits", headers=auth_headers).json()
    assert habits[0]["checked_today"] is False


def test_checkin_rejected_for_normal_task(client, auth_headers):
    task = create_task(client, auth_headers).json()
    assert (
        client.post(f"/api/tasks/{task['id']}/checkin", headers=auth_headers).status_code
        == 400
    )
    assert (
        client.delete(f"/api/tasks/{task['id']}/checkin", headers=auth_headers).status_code
        == 400
    )


def test_habit_streak_with_history(client, db_session, auth_headers):
    from app.models import TaskCheckin

    user_id = _user_id(client, auth_headers)
    habit = make_habit(client, auth_headers).json()
    today = date.today()
    for offset in (1, 2):
        db_session.add(
            TaskCheckin(
                user_id=user_id,
                task_id=habit["id"],
                checkin_date=today - timedelta(days=offset),
            )
        )
    db_session.commit()
    # 昨天、前天已打卡，今天未打卡 → 从昨天起算连续 2 天
    habits = client.get("/api/habits", headers=auth_headers).json()
    assert habits[0]["current_streak"] == 2
    assert habits[0]["checked_today"] is False


# ---------- 复习提醒 ----------

def test_task_done_generates_reviews(client, auth_headers):
    task = create_task(client, auth_headers).json()
    done = client.patch(
        f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers
    )
    assert done.status_code == 200

    reviews = client.get("/api/reviews?status=all", headers=auth_headers).json()
    assert len(reviews) == 6
    assert sorted(r["interval_days"] for r in reviews) == [1, 2, 4, 7, 15, 30]
    assert all(r["source_type"] == "task" for r in reviews)
    assert all(r["source_title"] == "测试任务" for r in reviews)

    # 防重复：重开再完成不会重复生成
    client.patch(f"/api/tasks/{task['id']}", json={"status": "todo"}, headers=auth_headers)
    client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers)
    reviews = client.get("/api/reviews?status=all", headers=auth_headers).json()
    assert len(reviews) == 6


def test_habit_task_does_not_generate_reviews(client, auth_headers):
    habit = make_habit(client, auth_headers).json()
    resp = client.patch(
        f"/api/tasks/{habit['id']}", json={"status": "done"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "todo"
    assert client.get("/api/reviews?status=all", headers=auth_headers).json() == []


def test_plan_done_generates_reviews(client, auth_headers):
    plan = client.post(
        "/api/plans", json={"title": "备考计划"}, headers=auth_headers
    ).json()
    client.patch(
        f"/api/plans/{plan['id']}", json={"status": "done"}, headers=auth_headers
    )
    reviews = client.get("/api/reviews?status=all", headers=auth_headers).json()
    assert len(reviews) == 6
    assert all(r["source_type"] == "plan" for r in reviews)


def test_reviews_due_query_and_complete(client, db_session, auth_headers):
    from app.models import Review

    task = create_task(client, auth_headers).json()
    client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers)

    # 把 interval=1 的节点改到昨天，使其变为逾期
    review = db_session.query(Review).filter_by(interval_days=1).first()
    review.due_date = date.today() - timedelta(days=1)
    db_session.commit()

    due = client.get("/api/reviews?status=due", headers=auth_headers).json()
    assert len(due) == 1
    assert due[0]["interval_days"] == 1

    upcoming = client.get("/api/reviews?status=upcoming", headers=auth_headers).json()
    assert len(upcoming) == 5

    done = client.post(f"/api/reviews/{due[0]['id']}/complete", headers=auth_headers)
    assert done.status_code == 200
    assert done.json()["reviewed_at"] is not None
    assert client.get("/api/reviews?status=due", headers=auth_headers).json() == []

    result = client.post("/api/reviews/complete-due", headers=auth_headers)
    assert result.status_code == 200
    assert result.json()["completed"] == 0


def test_reviews_regenerate_after_all_reviewed(client, auth_headers):
    task = create_task(client, auth_headers).json()
    client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers)
    reviews = client.get("/api/reviews?status=all", headers=auth_headers).json()
    for review in reviews:
        client.post(f"/api/reviews/{review['id']}/complete", headers=auth_headers)
    # 全部复习完后再次完成同一任务 → 生成新一轮
    client.patch(f"/api/tasks/{task['id']}", json={"status": "todo"}, headers=auth_headers)
    client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers)
    reviews = client.get("/api/reviews?status=all", headers=auth_headers).json()
    assert len(reviews) == 12


# ---------- 用户隔离 ----------

def test_habits_and_reviews_isolation(client, auth_headers, other_headers):
    habit = make_habit(client, auth_headers, title="A 的习惯").json()
    client.post(f"/api/tasks/{habit['id']}/checkin", headers=auth_headers)

    task = create_task(client, auth_headers).json()
    client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers)

    assert client.get("/api/habits", headers=other_headers).json() == []
    assert client.get("/api/reviews?status=all", headers=other_headers).json() == []

    assert (
        client.post(
            f"/api/tasks/{habit['id']}/checkin", headers=other_headers
        ).status_code
        == 404
    )
    review_id = client.get(
        "/api/reviews?status=all", headers=auth_headers
    ).json()[0]["id"]
    assert (
        client.post(
            f"/api/reviews/{review_id}/complete", headers=other_headers
        ).status_code
        == 404
    )


# ---------- 统计：热力图与 streak ----------

def test_heatmap_and_streak(client, db_session, auth_headers):
    from app.models import Session as SessionModel

    user_id = _user_id(client, auth_headers)
    today = date.today()
    sessions = [
        SessionModel(user_id=user_id, task_id=None, duration_minutes=25, completed_at=datetime.combine(today, datetime.min.time())),
        SessionModel(user_id=user_id, task_id=None, duration_minutes=25, completed_at=datetime.combine(today - timedelta(days=1), datetime.min.time())),
        SessionModel(user_id=user_id, task_id=None, duration_minutes=25, completed_at=datetime.combine(today - timedelta(days=3), datetime.min.time())),
    ]
    db_session.add_all(sessions)
    db_session.commit()

    heatmap = client.get("/api/stats/heatmap?days=105", headers=auth_headers).json()
    assert len(heatmap) == 105
    by_date = {p["date"]: p["focus_minutes"] for p in heatmap}
    assert by_date[today.isoformat()] == 25
    assert by_date[(today - timedelta(days=1)).isoformat()] == 25
    assert by_date[(today - timedelta(days=3)).isoformat()] == 25
    assert by_date[(today - timedelta(days=2)).isoformat()] == 0

    streak = client.get("/api/stats/streak", headers=auth_headers).json()
    assert streak["current_streak"] == 2  # 今天+昨天
    assert streak["best_streak"] == 2
    assert streak["focused_days"] == 3
    assert streak["total_focus_minutes"] == 75


def test_heatmap_days_validation(client, auth_headers):
    assert (
        client.get("/api/stats/heatmap?days=5", headers=auth_headers).status_code == 422
    )
    assert (
        client.get("/api/stats/heatmap?days=400", headers=auth_headers).status_code
        == 422
    )

def test_migrate_script_idempotent():
    import os
    import shutil
    import sqlite3
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent.parent
    tmp_dir = Path(tempfile.mkdtemp(prefix="migrate_test_", dir=backend_dir))
    try:
        db_file = tmp_dir / "old.db"
        conn = sqlite3.connect(str(db_file))
        conn.executescript(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                subject VARCHAR(50),
                estimated_minutes INTEGER,
                status VARCHAR(10),
                created_at DATETIME
            );
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY,
                task_id INTEGER,
                duration_minutes INTEGER,
                started_at DATETIME,
                completed_at DATETIME
            );
            INSERT INTO tasks (title, subject, estimated_minutes, status, created_at)
            VALUES ('旧任务', '语文', 25, 'todo', '2026-01-01 10:00:00');
            """
        )
        conn.commit()
        conn.close()

        env = dict(os.environ)
        env["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
        env["SECRET_KEY"] = "test-secret-key-0123456789abcdef-0123456789abcdef"

        def run_migrate():
            return subprocess.run(
                [
                    sys.executable,
                    "scripts/migrate_local.py",
                    "--username",
                    "admin",
                    "--password",
                    "admin123",
                ],
                cwd=str(backend_dir),
                env=env,
                capture_output=True,
                text=True,
            )

        first = run_migrate()
        assert first.returncode == 0, first.stderr
        second = run_migrate()
        assert second.returncode == 0, second.stderr

        conn = sqlite3.connect(str(db_file))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        assert {"user_id", "plan_id", "is_habit", "habit_frequency"} <= cols
        count = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id IS NOT NULL"
        ).fetchone()[0]
        assert count == 1
        conn.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
