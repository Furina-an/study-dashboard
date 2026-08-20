"""数据备份测试：导出结构、导入恢复（含 id 重映射）、隔离、非法输入。"""
from datetime import date, datetime

from sqlalchemy import delete, select

from app.models import (
    AIConfig,
    MathChapter,
    MathItem,
    MathNote,
    MathProgress,
    Plan,
    Review,
    Session as SessionModel,
    Task,
    TaskCheckin,
)


def _user_id(client, headers):
    return client.get("/api/auth/me", headers=headers).json()["id"]


def _create_dataset(db, user_id):
    parent = Plan(user_id=user_id, title="大计划", status="todo")
    db.add(parent)
    db.flush()
    child = Plan(user_id=user_id, parent_id=parent.id, title="子计划", status="doing")
    db.add(child)
    db.flush()
    task = Task(
        user_id=user_id,
        plan_id=child.id,
        title="任务A",
        subject="数学",
        status="done",
        completed_at=datetime.now(),
    )
    db.add(task)
    db.flush()
    habit = Task(
        user_id=user_id,
        title="每日习惯",
        is_habit=True,
        habit_frequency="daily",
    )
    db.add(habit)
    db.flush()
    db.add(
        SessionModel(
            user_id=user_id,
            task_id=task.id,
            duration_minutes=25,
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )
    )
    db.add(
        TaskCheckin(user_id=user_id, task_id=habit.id, checkin_date=date.today())
    )
    db.add(
        Review(
            user_id=user_id,
            source_type="task",
            source_id=task.id,
            due_date=date.today(),
            interval_days=1,
        )
    )
    db.add(
        AIConfig(
            user_id=user_id,
            provider="deepseek",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        )
    )
    item = db.scalar(select(MathItem).order_by(MathItem.id).limit(1))
    db.add(MathProgress(user_id=user_id, item_id=item.id, done=True))
    chapter = db.scalar(select(MathChapter).order_by(MathChapter.id).limit(1))
    db.add(MathNote(user_id=user_id, chapter_id=chapter.id, content="第一章笔记"))
    db.commit()


def _wipe(db, user_id):
    for model in (
        MathNote,
        MathProgress,
        Review,
        SessionModel,
        TaskCheckin,
        Task,
        Plan,
        AIConfig,
    ):
        db.execute(delete(model).where(model.user_id == user_id))
    db.commit()


def test_export_requires_auth(client):
    assert client.get("/api/backup/export").status_code == 401


def test_export_structure(client, db_session, auth_headers):
    user_id = _user_id(client, auth_headers)
    _create_dataset(db_session, user_id)

    response = client.get("/api/backup/export", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == 1
    assert payload["user"]["username"] == "alice"
    data = payload["data"]
    assert len(data["plans"]) == 2
    assert len(data["tasks"]) == 2
    assert len(data["sessions"]) == 1
    assert len(data["checkins"]) == 1
    assert len(data["reviews"]) == 1
    assert data["ai_config"]["provider"] == "deepseek"
    # API Key 不导出
    assert "api_key" not in data["ai_config"]
    assert "api_key_encrypted" not in data["ai_config"]
    assert len(data["math_progress"]) == 1
    assert data["math_notes"]


def test_export_import_roundtrip(client, db_session, auth_headers):
    user_id = _user_id(client, auth_headers)
    _create_dataset(db_session, user_id)
    exported = client.get("/api/backup/export", headers=auth_headers).json()

    _wipe(db_session, user_id)

    response = client.post(
        "/api/backup/import", json=exported, headers=auth_headers
    )
    assert response.status_code == 200
    counts = response.json()["counts"]
    assert counts == {
        "plans": 2,
        "tasks": 2,
        "sessions": 1,
        "checkins": 1,
        "reviews": 1,
        "ai_config": 1,
        "math_progress": 1,
        "math_notes": 1,
        "settings": 1,
        "plan_templates": 0,
    }

    # 计划父子关系重映射正确
    plans = client.get("/api/plans", headers=auth_headers).json()
    by_id = {p["id"]: p for p in plans}
    child = next(p for p in plans if p["parent_id"] is not None)
    assert by_id[child["parent_id"]]["title"] == "大计划"

    # 任务归属计划、会话/打卡/复习 id 重映射正确
    tasks = client.get("/api/tasks", headers=auth_headers).json()
    task = next(t for t in tasks if t["title"] == "任务A")
    assert task["plan_id"] == child["id"]
    habit = next(t for t in tasks if t["title"] == "每日习惯")

    session = db_session.scalar(
        select(SessionModel).where(SessionModel.user_id == user_id)
    )
    assert session.task_id == task["id"]
    checkin = db_session.scalar(
        select(TaskCheckin).where(TaskCheckin.user_id == user_id)
    )
    assert checkin.task_id == habit["id"]
    review = db_session.scalar(
        select(Review).where(Review.user_id == user_id)
    )
    assert review.source_id == task["id"]

    # 高数进度与笔记恢复
    tree = client.get("/api/math/tree", headers=auth_headers).json()
    assert tree["done"] == 1
    assert tree["chapters"][0]["note"] == "第一章笔记"


def test_import_replaces_existing_data(client, db_session, auth_headers):
    user_id = _user_id(client, auth_headers)
    _create_dataset(db_session, user_id)
    exported = client.get("/api/backup/export", headers=auth_headers).json()
    # 追加一条多余任务后导入备份，应被覆盖清空
    db_session.add(Task(user_id=user_id, title="多余任务"))
    db_session.commit()
    assert len(client.get("/api/tasks", headers=auth_headers).json()) == 3

    response = client.post(
        "/api/backup/import", json=exported, headers=auth_headers
    )
    assert response.status_code == 200
    tasks = client.get("/api/tasks", headers=auth_headers).json()
    assert len(tasks) == 2
    assert all(t["title"] != "多余任务" for t in tasks)


def test_import_isolation(client, db_session, auth_headers, other_headers):
    user_a = _user_id(client, auth_headers)
    _create_dataset(db_session, user_a)
    exported = client.get("/api/backup/export", headers=auth_headers).json()
    _wipe(db_session, user_a)

    response = client.post(
        "/api/backup/import", json=exported, headers=other_headers
    )
    assert response.status_code == 200
    assert client.get("/api/tasks", headers=auth_headers).json() == []
    assert len(client.get("/api/tasks", headers=other_headers).json()) == 2


def test_import_invalid_payload(client, auth_headers):
    assert (
        client.post(
            "/api/backup/import",
            json={"schema_version": 999},
            headers=auth_headers,
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/backup/import",
            json={"schema_version": 1},
            headers=auth_headers,
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/backup/import",
            json={"schema_version": 1, "data": {"tasks": {}}},
            headers=auth_headers,
        ).status_code
        == 400
    )

def test_import_missing_id_returns_400(client, auth_headers):
    payload = {
        "schema_version": 1,
        "data": {"plans": [{"title": "没有 id 的计划"}]},
    }
    response = client.post("/api/backup/import", json=payload, headers=auth_headers)
    assert response.status_code == 400
