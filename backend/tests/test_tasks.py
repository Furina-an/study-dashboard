def create_task(client, headers, **overrides):
    payload = {
        "title": "背 50 个单词",
        "subject": "英语",
        "estimated_minutes": 25,
        "status": "todo",
    }
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=headers)


def test_create_and_list_tasks(client, auth_headers):
    response = create_task(client, auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "背 50 个单词"
    assert data["subject"] == "英语"
    assert data["status"] == "todo"
    assert data["completed_at"] is None

    listed = client.get("/api/tasks", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_create_task_validation(client, auth_headers):
    assert (
        client.post("/api/tasks", json={"title": ""}, headers=auth_headers).status_code
        == 422
    )
    assert (
        client.post(
            "/api/tasks",
            json={"title": "x", "estimated_minutes": 0},
            headers=auth_headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/tasks",
            json={"title": "x", "status": "invalid"},
            headers=auth_headers,
        ).status_code
        == 422
    )


def test_patch_task_sets_completed_at(client, auth_headers):
    task_id = create_task(client, auth_headers).json()["id"]

    response = client.patch(
        f"/api/tasks/{task_id}", json={"status": "done"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "done"
    assert response.json()["completed_at"] is not None

    response = client.patch(
        f"/api/tasks/{task_id}", json={"status": "doing"}, headers=auth_headers
    )
    assert response.json()["completed_at"] is None


def test_patch_partial_update(client, auth_headers):
    task_id = create_task(client, auth_headers).json()["id"]
    response = client.patch(
        f"/api/tasks/{task_id}", json={"title": "新标题"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "新标题"
    assert response.json()["subject"] == "英语"


def test_patch_missing_task_returns_404(client, auth_headers):
    response = client.patch(
        "/api/tasks/999", json={"title": "x"}, headers=auth_headers
    )
    assert response.status_code == 404


def test_delete_task(client, auth_headers):
    task_id = create_task(client, auth_headers).json()["id"]
    assert (
        client.delete(f"/api/tasks/{task_id}", headers=auth_headers).status_code
        == 204
    )
    assert client.get("/api/tasks", headers=auth_headers).json() == []
    assert (
        client.delete("/api/tasks/999", headers=auth_headers).status_code == 404
    )


def test_task_due_date_create_update(client, auth_headers):
    task = create_task(client, auth_headers, due_date="2026-12-31").json()
    assert task["due_date"] == "2026-12-31"

    updated = client.patch(
        f"/api/tasks/{task['id']}", json={"due_date": "2026-12-25"}, headers=auth_headers
    ).json()
    assert updated["due_date"] == "2026-12-25"

    cleared = client.patch(
        f"/api/tasks/{task['id']}", json={"due_date": None}, headers=auth_headers
    ).json()
    assert cleared["due_date"] is None


def test_task_due_date_filter(client, auth_headers):
    client.post("/api/tasks", json={"title": "一月任务", "due_date": "2026-01-10"}, headers=auth_headers)
    client.post("/api/tasks", json={"title": "三月任务", "due_date": "2026-03-10"}, headers=auth_headers)
    client.post("/api/tasks", json={"title": "无截止"}, headers=auth_headers)

    listed = client.get(
        "/api/tasks?due_from=2026-01-01&due_to=2026-01-31", headers=auth_headers
    ).json()
    assert [t["title"] for t in listed] == ["一月任务"]

    listed2 = client.get("/api/tasks?due_from=2026-01-01", headers=auth_headers).json()
    assert {t["title"] for t in listed2} == {"一月任务", "三月任务"}
