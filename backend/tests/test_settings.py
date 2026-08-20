"""个性化设置测试：默认值、部分更新、校验、隔离、复习间隔生效。"""


def test_settings_defaults(client, auth_headers):
    response = client.get("/api/settings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["theme_mode"] == "system"
    assert data["accent"] == "indigo"
    assert data["pomodoro_durations"] == [25, 45, 60]
    assert data["pomodoro_default"] == 25
    assert data["review_intervals"] == [1, 2, 4, 7, 15, 30]
    assert data["habit_frequency_default"] == "daily"
    assert data["default_estimated_minutes"] == 25
    assert len(data["hub_cards"]) == 8
    assert data["task_subjects"] == []


def test_settings_requires_auth(client):
    assert client.get("/api/settings").status_code == 401


def test_settings_partial_update_keeps_rest(client, auth_headers):
    response = client.put(
        "/api/settings",
        json={"accent": "green", "pomodoro_default": 45},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["accent"] == "green"
    assert data["pomodoro_default"] == 45
    assert data["theme_mode"] == "system"
    assert data["pomodoro_durations"] == [25, 45, 60]


def test_settings_durations_and_intervals_normalized(client, auth_headers):
    response = client.put(
        "/api/settings",
        json={"pomodoro_durations": [10, 20, 30], "review_intervals": [7, 3, 7, 1]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pomodoro_durations"] == [10, 20, 30]
    # 默认时长不在列表 → 回退第一项
    assert data["pomodoro_default"] == 10
    # 去重排序
    assert data["review_intervals"] == [1, 3, 7]


def test_settings_validation(client, auth_headers):
    cases = [
        {"pomodoro_durations": [200]},
        {"pomodoro_durations": [1, 2, 3, 4, 5, 6]},
        {"pomodoro_durations": []},
        {"review_intervals": [400]},
        {"review_intervals": [1, 2, 3, 4, 5, 6, 7, 8, 9]},
        {"theme_mode": "blue"},
        {"accent": "pink"},
        {"habit_frequency_default": "weekly"},
        {"hub_cards": [{"key": "nope", "visible": True, "order": 0}]},
        {"hub_cards": [{"key": "tasks", "visible": True, "order": 0}, {"key": "tasks", "visible": True, "order": 1}]},
        {"task_subjects": [f"科目{i}" for i in range(51)]},
    ]
    for payload in cases:
        response = client.put("/api/settings", json=payload, headers=auth_headers)
        assert response.status_code == 400, f"{payload} 应返回 400"


def test_settings_subject_truncated(client, auth_headers):
    response = client.put(
        "/api/settings", json={"task_subjects": ["  数学  ", "x" * 60]}, headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task_subjects"] == ["数学", "x" * 50]


def test_settings_hub_cards_patch_completes(client, auth_headers):
    response = client.put(
        "/api/settings",
        json={"hub_cards": [{"key": "tasks", "visible": False, "order": 0}, {"key": "math", "visible": True, "order": 1}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["hub_cards"]) == 8
    by_key = {card["key"]: card for card in data["hub_cards"]}
    assert by_key["tasks"]["visible"] is False
    assert by_key["math"]["order"] == 1
    assert by_key["stats"]["visible"] is True


def test_settings_isolation(client, auth_headers, other_headers):
    client.put("/api/settings", json={"accent": "rose"}, headers=auth_headers)
    other = client.get("/api/settings", headers=other_headers).json()
    assert other["accent"] == "indigo"


def test_custom_review_intervals_used(client, auth_headers):
    client.put(
        "/api/settings", json={"review_intervals": [2, 5, 9]}, headers=auth_headers
    )
    task = client.post(
        "/api/tasks", json={"title": "任务", "status": "todo"}, headers=auth_headers
    ).json()
    client.patch(
        f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers
    )
    reviews = client.get("/api/reviews?status=all", headers=auth_headers).json()
    intervals = sorted(
        {r["interval_days"] for r in reviews if r["source_id"] == task["id"]}
    )
    assert intervals == [2, 5, 9]


def test_default_review_intervals_unchanged(client, auth_headers):
    task = client.post(
        "/api/tasks", json={"title": "任务", "status": "todo"}, headers=auth_headers
    ).json()
    client.patch(
        f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers
    )
    reviews = client.get("/api/reviews?status=all", headers=auth_headers).json()
    intervals = sorted(
        {r["interval_days"] for r in reviews if r["source_id"] == task["id"]}
    )
    assert intervals == [1, 2, 4, 7, 15, 30]
