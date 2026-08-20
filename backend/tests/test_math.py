"""高数复习模块测试：树结构、进度、笔记、用户隔离、幂等种子。"""
import json

from app.models import MathChapter, MathItem
from app.math_data import seed_math_if_empty


def test_tree_shape(client, auth_headers):
    response = client.get("/api/math/tree", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 108
    assert payload["done"] == 0
    assert len(payload["chapters"]) == 7
    first = payload["chapters"][0]
    assert first["title"] == "函数与极限"
    assert first["total"] == 21
    # 至少有一个章节包含公式段
    any_math = any(
        seg.get("t") == "math"
        for ch in payload["chapters"]
        for sub in ch["subs"]
        for item in sub["items"]
        for seg in item["segments"]
    )
    assert any_math


def test_tree_requires_auth(client):
    assert client.get("/api/math/tree").status_code == 401


def test_progress_toggle_and_summary(client, auth_headers):
    payload = client.get("/api/math/tree", headers=auth_headers).json()
    item_id = payload["chapters"][0]["subs"][0]["items"][0]["id"]

    response = client.put(
        f"/api/math/items/{item_id}/progress",
        json={"done": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["done"] is True

    payload = client.get("/api/math/tree", headers=auth_headers).json()
    assert payload["done"] == 1
    assert payload["chapters"][0]["done"] == 1
    target = payload["chapters"][0]["subs"][0]["items"][0]
    assert target["done"] is True

    # 幂等：再次提交同样状态不报错
    response = client.put(
        f"/api/math/items/{item_id}/progress",
        json={"done": True},
        headers=auth_headers,
    )
    assert response.status_code == 200

    # 撤销
    response = client.put(
        f"/api/math/items/{item_id}/progress",
        json={"done": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = client.get("/api/math/tree", headers=auth_headers).json()
    assert payload["done"] == 0


def test_progress_404(client, auth_headers):
    response = client.put(
        "/api/math/items/99999/progress",
        json={"done": True},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_note_save_and_isolation(client, auth_headers, other_headers):
    payload = client.get("/api/math/tree", headers=auth_headers).json()
    chapter_id = payload["chapters"][0]["id"]

    response = client.put(
        f"/api/math/chapters/{chapter_id}/note",
        json={"content": "第一章笔记：极限重点"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    own = client.get("/api/math/tree", headers=auth_headers).json()
    assert own["chapters"][0]["note"] == "第一章笔记：极限重点"

    other = client.get("/api/math/tree", headers=other_headers).json()
    assert other["chapters"][0]["note"] == ""


def test_note_404(client, auth_headers):
    response = client.put(
        "/api/math/chapters/99999/note",
        json={"content": "x"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_reset_progress(client, auth_headers):
    payload = client.get("/api/math/tree", headers=auth_headers).json()
    item_id = payload["chapters"][0]["subs"][0]["items"][0]["id"]
    client.put(
        f"/api/math/items/{item_id}/progress",
        json={"done": True},
        headers=auth_headers,
    )
    response = client.delete("/api/math/progress", headers=auth_headers)
    assert response.status_code == 200
    payload = client.get("/api/math/tree", headers=auth_headers).json()
    assert payload["done"] == 0


def test_progress_isolation(client, auth_headers, other_headers):
    payload = client.get("/api/math/tree", headers=auth_headers).json()
    item_id = payload["chapters"][0]["subs"][0]["items"][0]["id"]
    client.put(
        f"/api/math/items/{item_id}/progress",
        json={"done": True},
        headers=auth_headers,
    )
    other = client.get("/api/math/tree", headers=other_headers).json()
    assert other["done"] == 0


def test_seed_idempotent(db_session):
    assert db_session.query(MathChapter).count() == 7
    assert db_session.query(MathItem).count() == 108
    seeded = seed_math_if_empty(db_session)
    assert seeded is False
    assert db_session.query(MathChapter).count() == 7
    assert db_session.query(MathItem).count() == 108
    # 段落数据可被 JSON 解析
    sample = db_session.query(MathItem).first()
    parsed = json.loads(sample.segments)
    assert isinstance(parsed, list) and parsed
