"""模型层测试：to_dict/from_dict 往返一致、非法状态报错、容错解析。"""

from __future__ import annotations

import pytest

from userstore.models import (
    AIConfigRecord,
    CheckinRecord,
    FileMeta,
    MathNoteRecord,
    PlanRecord,
    PlanTemplateRecord,
    ReviewRecord,
    SessionRecord,
    SettingsRecord,
    TaskRecord,
    UserData,
    UserInfo,
    validate_username,
)

RECORDS = [
    UserInfo(username="alice", password_hash="x" * 60, created_at="2026-01-01T00:00:00"),
    TaskRecord(id=1, title="gaoshu", subject="math", estimated_minutes=45,
               status="doing", is_habit=True, habit_frequency="daily",
               habit_days=(1, 3, 5), plan_id=2, completed_at=None),
    PlanRecord(id=2, parent_id=1, title="sub", description="desc", status="doing"),
    SessionRecord(id=3, duration_minutes=25, task_id=1,
                  started_at="2026-01-01T09:00:00", completed_at="2026-01-01T09:25:00"),
    CheckinRecord(id=4, task_id=1, checkin_date="2026-08-19"),
    ReviewRecord(id=5, source_type="task", source_id=1, due_date="2026-08-20",
                 interval_days=1, reviewed_at=None, created_at="2026-08-19"),
    SettingsRecord(theme_mode="dark", accent="amber", pomodoro_durations=(25, 50),
                   pomodoro_default=50, review_intervals=(1, 3, 7),
                   habit_frequency_default="weekdays", default_estimated_minutes=30),
    PlanTemplateRecord(id=6, name="tpl", children=[{"title": "a", "description": "b"}]),
    MathNoteRecord(chapter_key="ch1", content="notes"),
    AIConfigRecord(provider="deepseek", base_url="https://api.deepseek.com", model="deepseek-chat"),
    FileMeta(file_id="a" * 32, original_name="notes.pdf", ext=".pdf",
             size_bytes=1024, category="docs", status="quarantined",
             scan_status="clean", integrated=True, admin_note="ok"),
]


@pytest.mark.parametrize("record", RECORDS, ids=lambda r: type(r).__name__)
def test_record_round_trip(record):
    # 往返一致：to_dict 后再 from_dict，再 to_dict 应完全一致
    restored = type(record).from_dict(record.to_dict())
    assert restored.to_dict() == record.to_dict()


def test_user_data_round_trip():
    data = UserData(
        user=UserInfo(username="alice", password_hash="h", created_at="t"),
        tasks=(TaskRecord(id=1, title="t"),),
        plans=(PlanRecord(id=2, title="p"),),
        sessions=(SessionRecord(id=3, duration_minutes=25),),
        checkins=(CheckinRecord(id=4, task_id=1, checkin_date="2026-08-19"),),
        reviews=(ReviewRecord(id=5, source_type="task", source_id=1, due_date="d"),),
        settings=SettingsRecord(accent="rose"),
        plan_templates=(PlanTemplateRecord(id=6, name="n"),),
        math_progress=("ch1", "ch2"),
        math_notes=(MathNoteRecord(chapter_key="ch1", content="c"),),
        ai_config=AIConfigRecord(base_url="u", model="m"),
        files=(FileMeta(file_id="b" * 32, original_name="f.pdf", ext=".pdf"),),
    )
    restored = UserData.from_dict(data.to_dict())
    assert restored.to_dict() == data.to_dict()


def test_invalid_status_raises():
    with pytest.raises(ValueError):
        TaskRecord.from_dict({"id": 1, "title": "t", "status": "bogus"})
    with pytest.raises(ValueError):
        ReviewRecord.from_dict(
            {"id": 1, "source_type": "nonsense", "source_id": 1, "due_date": "d"}
        )


def test_from_dict_tolerates_missing_and_extra():
    task = TaskRecord.from_dict({"extra_key": 1})
    assert task.id == 0
    assert task.title == ""
    assert task.status == "todo"
    assert TaskRecord.from_dict(None).title == ""
    assert TaskRecord.from_dict({"id": "x"}).id == 0


def test_validate_username():
    validate_username("alice_01")
    for bad in ("ab", "a" * 51, "user name", "user/name", "\u4e2d\u6587\u540d", "", None, 123):
        with pytest.raises(ValueError):
            validate_username(bad)
