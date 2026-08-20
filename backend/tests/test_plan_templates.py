"""自定义计划模板测试：CRUD、隔离、拆解。"""


def test_template_crud_and_isolation(client, auth_headers, other_headers):
    payload = {
        "name": "我的备考模板",
        "children": [
            {"title": "看教材", "description": "第1-3章"},
            {"title": "刷真题", "description": ""},
        ],
    }
    response = client.post("/api/plan-templates", json=payload, headers=auth_headers)
    assert response.status_code == 201
    template = response.json()
    assert template["name"] == "我的备考模板"
    assert len(template["children"]) == 2
    tpl_id = template["id"]

    assert len(client.get("/api/plan-templates", headers=auth_headers).json()) == 1
    assert client.get("/api/plan-templates", headers=other_headers).json() == []

    updated = client.patch(
        f"/api/plan-templates/{tpl_id}",
        json={"name": "改名", "children": [{"title": "只有一项"}]},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "改名"
    assert len(updated.json()["children"]) == 1

    # 越权 404
    assert (
        client.patch(
            f"/api/plan-templates/{tpl_id}", json={"name": "x"}, headers=other_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/plan-templates/{tpl_id}", headers=other_headers).status_code
        == 404
    )

    assert client.delete(f"/api/plan-templates/{tpl_id}", headers=auth_headers).status_code == 204
    assert client.get("/api/plan-templates", headers=auth_headers).json() == []


def test_template_validation(client, auth_headers):
    assert (
        client.post(
            "/api/plan-templates",
            json={"name": "", "children": [{"title": "x"}]},
            headers=auth_headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/plan-templates",
            json={"name": "t", "children": []},
            headers=auth_headers,
        ).status_code
        == 422
    )


def test_breakdown_with_user_template(client, auth_headers):
    plan = client.post(
        "/api/plans", json={"title": "大计划"}, headers=auth_headers
    ).json()
    tpl = client.post(
        "/api/plan-templates",
        json={
            "name": "模板",
            "children": [{"title": "子1", "description": "描述"}, {"title": "子2"}],
        },
        headers=auth_headers,
    ).json()
    response = client.post(
        f"/api/plans/{plan['id']}/breakdown",
        json={"mode": "template", "template_id": tpl["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    created = response.json()["created"]
    assert len(created) == 2
    assert {child["title"] for child in created} == {"子1", "子2"}


def test_breakdown_with_other_users_template(client, auth_headers, other_headers):
    plan = client.post(
        "/api/plans", json={"title": "大计划"}, headers=auth_headers
    ).json()
    tpl = client.post(
        "/api/plan-templates",
        json={"name": "A 的模板", "children": [{"title": "x"}]},
        headers=auth_headers,
    ).json()
    response = client.post(
        f"/api/plans/{plan['id']}/breakdown",
        json={"mode": "template", "template_id": tpl["id"]},
        headers=other_headers,
    )
    assert response.status_code == 404


def test_breakdown_requires_template(client, auth_headers):
    plan = client.post(
        "/api/plans", json={"title": "大计划"}, headers=auth_headers
    ).json()
    response = client.post(
        f"/api/plans/{plan['id']}/breakdown",
        json={"mode": "template"},
        headers=auth_headers,
    )
    assert response.status_code == 400
