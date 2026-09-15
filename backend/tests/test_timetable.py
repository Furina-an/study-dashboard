"""课表：作息设置、课程 CRUD、导入解析、生成任务与备份往返。"""
import io
from datetime import date, timedelta

from openpyxl import Workbook

from app.routers.timetable import (
    parse_periods,
    parse_time_to_periods,
    parse_weekday,
    parse_weeks,
)

TERM_START = date(2026, 3, 2)  # 周一


def create_course(client, headers, **overrides):
    payload = {
        "name": "高等数学",
        "teacher": "张老师",
        "location": "教三 301",
        "weekday": 1,
        "start_period": 1,
        "end_period": 2,
        "weeks": [1, 2, 3],
    }
    payload.update(overrides)
    return client.post("/api/timetable/courses", json=payload, headers=headers)


# ---------------- 解析函数 ----------------

def test_parse_weekday_variants():
    assert parse_weekday("周一") == 1
    assert parse_weekday("星期一") == 1
    assert parse_weekday("星期二") == 2
    assert parse_weekday("三") == 3
    assert parse_weekday("4") == 4
    assert parse_weekday("Sun") == 7
    assert parse_weekday("") is None
    assert parse_weekday("教室") is None


def test_parse_periods_variants():
    assert parse_periods("1-2") == (1, 2)
    assert parse_periods("第1-2节") == (1, 2)
    assert parse_periods("1,2") == (1, 2)
    assert parse_periods("3") == (3, 3)
    assert parse_periods("") is None


def test_parse_weeks_variants():
    assert parse_weeks("1-16周") == list(range(1, 17))
    assert parse_weeks("1,3,5") == [1, 3, 5]
    assert parse_weeks("1-8,10-16") == [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16]
    odd = parse_weeks("1-10周单周")
    assert odd == [1, 3, 5, 7, 9]
    even = parse_weeks("双周")
    assert even[:3] == [2, 4, 6]
    assert parse_weeks("") is None


def test_parse_time_to_periods_reverse_lookup():
    from app.routers.timetable import DEFAULT_PERIODS

    assert parse_time_to_periods("08:00-09:40", DEFAULT_PERIODS) == (1, 2)
    assert parse_time_to_periods("14:00-15:40", DEFAULT_PERIODS) == (5, 6)
    assert parse_time_to_periods("07:00-07:45", DEFAULT_PERIODS) is None
    assert parse_time_to_periods("没有时间", DEFAULT_PERIODS) is None


# ---------------- 设置 ----------------

def test_settings_defaults(client, auth_headers):
    response = client.get("/api/timetable/settings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["term_start"] is None
    assert data["total_weeks"] == 16
    assert data["current_week"] is None
    assert len(data["periods"]) == 12
    assert data["periods"][0] == {"index": 1, "start": "08:00", "end": "08:45"}


def test_settings_update_and_current_week(client, auth_headers):
    response = client.put(
        "/api/timetable/settings",
        json={"term_start": TERM_START.isoformat(), "total_weeks": 18},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["term_start"] == TERM_START.isoformat()
    assert data["total_weeks"] == 18
    # 学期已过完（2026-03 到今天是第 20+ 周），current_week 为空
    assert data["current_week"] is None


def test_settings_invalid_values(client, auth_headers):
    assert (
        client.put(
            "/api/timetable/settings", json={"total_weeks": 0}, headers=auth_headers
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/timetable/settings",
            json={"periods": [{"index": 1, "start": "8:00", "end": "08:45"}]},
            headers=auth_headers,
        ).status_code
        == 422
    )
    response = client.put(
        "/api/timetable/settings",
        json={
            "periods": [
                {"index": 1, "start": "08:00", "end": "08:45"},
                {"index": 3, "start": "09:00", "end": "09:45"},
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "连续" in response.json()["detail"]

    response = client.put(
        "/api/timetable/settings",
        json={"periods": [{"index": 1, "start": "09:00", "end": "08:45"}]},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_settings_requires_auth(client):
    assert client.get("/api/timetable/settings").status_code == 401


def test_settings_isolation(client, auth_headers, other_headers):
    client.put(
        "/api/timetable/settings",
        json={"term_start": TERM_START.isoformat(), "total_weeks": 12},
        headers=auth_headers,
    )
    other = client.get("/api/timetable/settings", headers=other_headers).json()
    assert other["term_start"] is None
    assert other["total_weeks"] == 16


# ---------------- 课程 CRUD ----------------

def test_course_crud(client, auth_headers):
    created = create_course(client, auth_headers)
    assert created.status_code == 201
    course_id = created.json()["id"]
    assert created.json()["weeks"] == [1, 2, 3]

    listed = client.get("/api/timetable/courses", headers=auth_headers).json()
    assert len(listed) == 1

    patched = client.patch(
        f"/api/timetable/courses/{course_id}",
        json={"location": "教四 202", "start_period": 3, "end_period": 4},
        headers=auth_headers,
    )
    assert patched.status_code == 200
    assert patched.json()["location"] == "教四 202"
    assert patched.json()["start_period"] == 3

    assert (
        client.delete(
            f"/api/timetable/courses/{course_id}", headers=auth_headers
        ).status_code
        == 204
    )
    assert client.get("/api/timetable/courses", headers=auth_headers).json() == []


def test_course_invalid_payload(client, auth_headers):
    assert create_course(client, auth_headers, weekday=8).status_code == 422
    assert create_course(client, auth_headers, name="").status_code == 422
    assert create_course(client, auth_headers, end_period=0).status_code == 422


def test_course_isolation(client, auth_headers, other_headers):
    course_id = create_course(client, auth_headers).json()["id"]
    assert client.get("/api/timetable/courses", headers=other_headers).json() == []
    assert (
        client.patch(
            f"/api/timetable/courses/{course_id}",
            json={"name": "偷改"},
            headers=other_headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/timetable/courses/{course_id}", headers=other_headers
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/timetable/courses/{course_id}/generate-tasks",
            json={},
            headers=other_headers,
        ).status_code
        == 404
    )


# ---------------- 批量保存 ----------------

def test_bulk_save_append_and_replace(client, auth_headers):
    payload = {
        "courses": [
            {"name": "线性代数", "weekday": 2, "start_period": 1, "end_period": 2},
            {"name": "大学英语", "weekday": 3, "start_period": 3, "end_period": 4},
        ]
    }
    response = client.post(
        "/api/timetable/courses/bulk", json=payload, headers=auth_headers
    )
    assert response.status_code == 201
    assert len(response.json()) == 2

    append = client.post(
        "/api/timetable/courses/bulk",
        json={"courses": [{"name": "体育", "weekday": 4, "start_period": 5, "end_period": 6}]},
        headers=auth_headers,
    )
    assert len(append.json()) == 1
    assert len(client.get("/api/timetable/courses", headers=auth_headers).json()) == 3

    replaced = client.post(
        "/api/timetable/courses/bulk",
        json={**payload, "replace": True},
        headers=auth_headers,
    )
    assert len(replaced.json()) == 2
    titles = {
        c["name"] for c in client.get("/api/timetable/courses", headers=auth_headers).json()
    }
    assert titles == {"线性代数", "大学英语"}


# ---------------- 表格解析 ----------------

def test_parse_rows_by_mapping(client, auth_headers):
    rows = [
        ["高等数学", "周一", "1-2节", "1-16周", "张老师"],
        ["数据结构", "周三", "3-4", "1-8周", "李老师"],
        ["无效课程", "周八", "1-2", "", ""],
    ]
    response = client.post(
        "/api/timetable/import/parse-rows",
        json={
            "rows": rows,
            "mapping": {"name": 0, "weekday": 1, "periods": 2, "weeks": 3, "teacher": 4},
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["courses"]) == 2
    assert data["courses"][0]["name"] == "高等数学"
    assert data["courses"][0]["weeks"] == list(range(1, 17))
    assert data["courses"][1]["start_period"] == 3
    assert any("第 3 行" in warning for warning in data["warnings"])


def test_parse_rows_time_reverse_lookup_and_conflict(client, auth_headers):
    rows = [
        ["高等数学", "周一", "08:00-09:40"],
        ["高等数学实验", "周一", "08:00-08:45"],
        ["凌晨课", "周一", "06:00-06:45"],
    ]
    response = client.post(
        "/api/timetable/import/parse-rows",
        json={"rows": rows, "mapping": {"name": 0, "weekday": 1, "time": 2}},
        headers=auth_headers,
    )
    data = response.json()
    assert len(data["courses"]) == 2
    assert data["courses"][0]["start_period"] == 1
    assert data["courses"][0]["end_period"] == 2
    assert any("冲突" in warning for warning in data["warnings"])
    assert any("凌晨课" in warning for warning in data["warnings"])


def _make_xlsx() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["课程名称", "星期", "节次", "起止周", "任课教师", "上课地点"])
    sheet.append(["高等数学", "周一", "1-2", "1-16周", "张老师", "教三301"])
    sheet.append(["数据结构", "周四", "5-6", "1-8周", "李老师", "教二202"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_parse_file_xlsx(client, auth_headers):
    response = client.post(
        "/api/timetable/import/parse-file?filename=课表.xlsx",
        content=_make_xlsx(),
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["headers"][0] == "课程名称"
    assert data["total_rows"] == 2
    assert data["truncated"] is False
    assert data["suggested_mapping"]["name"] == 0
    assert data["suggested_mapping"]["weekday"] == 1
    assert data["suggested_mapping"]["periods"] == 2
    assert data["suggested_mapping"]["weeks"] == 3

    parsed = client.post(
        "/api/timetable/import/parse-rows",
        json={"rows": data["rows"], "mapping": data["suggested_mapping"]},
        headers=auth_headers,
    ).json()
    assert {c["name"] for c in parsed["courses"]} == {"高等数学", "数据结构"}
    assert parsed["courses"][0]["location"] == "教三301"


def test_parse_file_csv(client, auth_headers):
    body = "课程名,星期,节次,周次\n离散数学,周五,7-8,1-16周\n".encode("utf-8")
    response = client.post(
        "/api/timetable/import/parse-file?filename=table.csv",
        content=body,
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["rows"][0][0] == "离散数学"


def test_parse_file_rejects_bad_input(client, auth_headers):
    assert (
        client.post(
            "/api/timetable/import/parse-file?filename=a.xls",
            content=b"x",
            headers=auth_headers,
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/timetable/import/parse-file?filename=a.txt",
            content=b"x",
            headers=auth_headers,
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/timetable/import/parse-file?filename=a.csv",
            content=b"",
            headers=auth_headers,
        ).status_code
        == 400
    )


# ---------------- AI 解析 ----------------

def test_parse_text_without_ai(client, auth_headers, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    response = client.post(
        "/api/timetable/import/parse-text",
        json={"text": "周一 1-2 节 高等数学"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "LLM_API_KEY" in response.json()["detail"]


def test_parse_text_success(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    content = (
        '```json\n{"courses":[{"name":"高等数学","teacher":"张老师","location":"教三301",'
        '"weekday":1,"start_period":1,"end_period":2,"weeks":[1,2,3]}]}\n```'
    )
    monkeypatch.setattr(
        "app.routers.timetable.chat_completion", lambda *a, **k: content
    )
    response = client.post(
        "/api/timetable/import/parse-text",
        json={"text": "周一 1-2 节 高等数学 教三301"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["courses"]) == 1
    assert data["courses"][0]["name"] == "高等数学"
    assert data["courses"][0]["weeks"] == [1, 2, 3]


def test_parse_text_unparseable(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.routers.timetable.chat_completion", lambda *a, **k: "看不懂"
    )
    response = client.post(
        "/api/timetable/import/parse-text",
        json={"text": "随便写点"},
        headers=auth_headers,
    )
    assert response.status_code == 502


# ---------------- 生成任务 ----------------

def test_generate_tasks_requires_term_start(client, auth_headers):
    client.post(
        "/api/timetable/courses/bulk",
        json={"courses": [{"name": "高等数学", "weekday": 1, "start_period": 1, "end_period": 2}]},
        headers=auth_headers,
    )
    response = client.post(
        "/api/timetable/generate-tasks", json={}, headers=auth_headers
    )
    assert response.status_code == 400
    assert "学期" in response.json()["detail"]


def test_generate_tasks_dates_and_minutes(client, auth_headers):
    client.put(
        "/api/timetable/settings",
        json={"term_start": TERM_START.isoformat(), "total_weeks": 16},
        headers=auth_headers,
    )
    course_id = create_course(
        client, auth_headers, weeks=[1, 3], location="教三301"
    ).json()["id"]

    response = client.post(
        f"/api/timetable/courses/{course_id}/generate-tasks",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["created"] == 2
    assert data["skipped"] == 0
    # 第 1 周周一 = 学期开始当天；第 3 周周一 = +14 天
    assert sorted(task["due_date"] for task in data["tasks"]) == [
        TERM_START.isoformat(),
        (TERM_START + timedelta(days=14)).isoformat(),
    ]
    # 第 1 节 08:00 到第 2 节 09:40 共 100 分钟
    assert data["tasks"][0]["estimated_minutes"] == 100
    assert data["tasks"][0]["title"] == "高等数学（教三301）"
    assert data["tasks"][0]["plan_id"] == data["plan_id"]

    # 幂等：再次生成全部跳过
    again = client.post("/api/timetable/generate-tasks", json={}, headers=auth_headers)
    assert again.json()["created"] == 0
    assert again.json()["skipped"] == 2

    # 任务挂到自动创建的「课表」计划，且能在任务页看到
    plans = client.get("/api/plans", headers=auth_headers).json()
    assert any(plan["title"] == "课表" for plan in plans)
    tasks = client.get("/api/tasks", headers=auth_headers).json()
    assert len([t for t in tasks if t["title"].startswith("高等数学")]) == 2


def test_generate_tasks_without_courses(client, auth_headers):
    client.put(
        "/api/timetable/settings",
        json={"term_start": TERM_START.isoformat()},
        headers=auth_headers,
    )
    response = client.post(
        "/api/timetable/generate-tasks", json={}, headers=auth_headers
    )
    assert response.status_code == 400


def test_generate_tasks_isolation(client, auth_headers, other_headers):
    client.put(
        "/api/timetable/settings",
        json={"term_start": TERM_START.isoformat()},
        headers=auth_headers,
    )
    create_course(client, auth_headers, weeks=[1])
    assert (
        client.post(
            "/api/timetable/generate-tasks", json={}, headers=other_headers
        ).status_code
        == 400
    )
    assert client.get("/api/tasks", headers=other_headers).json() == []


# ---------------- 备份往返 ----------------

def test_backup_roundtrip_includes_timetable(client, auth_headers):
    client.put(
        "/api/timetable/settings",
        json={"term_start": TERM_START.isoformat(), "total_weeks": 14},
        headers=auth_headers,
    )
    create_course(client, auth_headers)

    exported = client.get("/api/backup/export", headers=auth_headers).json()
    assert len(exported["data"]["courses"]) == 1
    assert exported["data"]["timetable_settings"]["total_weeks"] == 14

    # 先清掉本地数据，验证导入确实从备份恢复
    course_id = client.get("/api/timetable/courses", headers=auth_headers).json()[0]["id"]
    client.delete(f"/api/timetable/courses/{course_id}", headers=auth_headers)

    imported = client.post(
        "/api/backup/import", json=exported, headers=auth_headers
    ).json()
    assert imported["counts"]["courses"] == 1
    assert imported["counts"]["timetable_settings"] == 1

    restored = client.get("/api/timetable/courses", headers=auth_headers).json()
    assert len(restored) == 1
    assert restored[0]["name"] == "高等数学"
    settings = client.get("/api/timetable/settings", headers=auth_headers).json()
    assert settings["term_start"] == TERM_START.isoformat()
    assert settings["total_weeks"] == 14
