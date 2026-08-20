def test_create_session_with_task(client, auth_headers):
    task_id = client.post(
        "/api/tasks", json={"title": "高数复习"}, headers=auth_headers
    ).json()["id"]

    response = client.post(
        "/api/sessions",
        json={"task_id": task_id, "duration_minutes": 25},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["task_id"] == task_id
    assert data["duration_minutes"] == 25
    assert data["completed_at"] is not None


def test_create_session_without_task(client, auth_headers):
    response = client.post(
        "/api/sessions", json={"duration_minutes": 45}, headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["task_id"] is None


def test_create_session_missing_task_returns_404(client, auth_headers):
    response = client.post(
        "/api/sessions",
        json={"task_id": 999, "duration_minutes": 25},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_create_session_validation(client, auth_headers):
    response = client.post(
        "/api/sessions", json={"duration_minutes": 0}, headers=auth_headers
    )
    assert response.status_code == 422