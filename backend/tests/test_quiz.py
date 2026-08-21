"""题库 + 测验 + 掌握度：CRUD、AI 出题、答题与用户隔离测试。"""

QUESTION_PAYLOAD = {
    "subject": "数学",
    "question": "1 + 1 = ?",
    "options": ["1", "2", "3"],
    "answer": 1,
    "explanation": "1+1=2",
}


def _create_question(client, headers, **overrides):
    payload = {**QUESTION_PAYLOAD, **overrides}
    return client.post("/api/questions", json=payload, headers=headers)


def test_question_crud(client, auth_headers):
    # 创建
    response = _create_question(client, auth_headers)
    assert response.status_code == 201
    question = response.json()
    assert question["source"] == "manual"
    assert question["answer"] == 1
    qid = question["id"]

    # 答案越界 → 422
    assert (
        _create_question(
            client, auth_headers, answer=5, options=["A", "B"]
        ).status_code
        == 422
    )

    # 列表 + 科目过滤
    _create_question(client, auth_headers, subject="英语", question="apple 是什么？")
    listed = client.get(
        "/api/questions?subject=数学", headers=auth_headers
    ).json()
    assert len(listed) == 1
    assert listed[0]["question"] == "1 + 1 = ?"

    # 修改
    updated = client.patch(
        f"/api/questions/{qid}",
        json={"answer": 0, "explanation": "更正：1+1=2"},
        headers=auth_headers,
    ).json()
    assert updated["answer"] == 0

    # 删除
    assert client.delete(f"/api/questions/{qid}", headers=auth_headers).status_code == 204
    assert (
        client.get("/api/questions", headers=auth_headers).json().__len__() == 1
    )


def test_quiz_session_strips_answer(client, auth_headers):
    _create_question(client, auth_headers)
    _create_question(client, auth_headers, question="2 + 2 = ?", answer=2)
    response = client.get(
        "/api/quiz/session?subject=数学&count=2", headers=auth_headers
    )
    assert response.status_code == 200
    questions = response.json()
    assert len(questions) == 2
    for item in questions:
        assert "answer" not in item
        assert "explanation" not in item
        assert "options" in item


def test_quiz_empty_bank(client, auth_headers):
    response = client.get("/api/quiz/session", headers=auth_headers)
    assert response.status_code == 404


def test_quiz_answer_and_mastery(client, auth_headers):
    qid = _create_question(client, auth_headers).json()["id"]
    # 答错
    wrong = client.post(
        "/api/quiz/answer",
        json={"question_id": qid, "answer_index": 0},
        headers=auth_headers,
    )
    assert wrong.status_code == 200
    assert wrong.json()["correct"] is False
    assert wrong.json()["correct_answer"] == 1
    assert wrong.json()["explanation"] == "1+1=2"
    # 答对
    right = client.post(
        "/api/quiz/answer",
        json={"question_id": qid, "answer_index": 1},
        headers=auth_headers,
    )
    assert right.json()["correct"] is True
    # 越界
    assert (
        client.post(
            "/api/quiz/answer",
            json={"question_id": qid, "answer_index": 9},
            headers=auth_headers,
        ).status_code
        == 422
    )

    mastery = client.get("/api/quiz/mastery", headers=auth_headers).json()
    assert mastery["total_answered"] == 2
    assert mastery["total_correct"] == 1
    assert mastery["overall_accuracy"] == 0.5
    assert mastery["subjects"][0]["subject"] == "数学"
    assert mastery["subjects"][0]["correct"] == 1


def test_ai_generate_without_key(client, auth_headers, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    response = client.post(
        "/api/questions/generate",
        json={"subject": "数学", "topic": "导数", "count": 3},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_ai_generate_success(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    content = (
        '[{"question": "导数的定义", "options": ["极限", "积分", "斜率"], '
        '"answer": 0, "explanation": "导数是变化率的极限"}]'
    )
    monkeypatch.setattr(
        "app.routers.questions.chat_completion",
        lambda *a, **k: content,
    )
    response = client.post(
        "/api/questions/generate",
        json={"subject": "数学", "topic": "导数", "count": 1},
        headers=auth_headers,
    )
    assert response.status_code == 200
    created = response.json()
    assert len(created) == 1
    assert created[0]["source"] == "ai"
    assert created[0]["subject"] == "数学"
    assert created[0]["answer"] == 0


def test_ai_generate_unparseable(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.routers.questions.chat_completion",
        lambda *a, **k: "这不是 JSON",
    )
    response = client.post(
        "/api/questions/generate",
        json={"subject": "数学", "count": 3},
        headers=auth_headers,
    )
    assert response.status_code == 502


def test_user_isolation(client, auth_headers, other_headers):
    qid = _create_question(client, auth_headers).json()["id"]
    # B 看不到 A 的题目
    assert client.get("/api/questions", headers=other_headers).json() == []
    # B 改/删 A 的题目 → 404
    assert (
        client.patch(
            f"/api/questions/{qid}", json={"explanation": "x"}, headers=other_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/questions/{qid}", headers=other_headers).status_code
        == 404
    )
    # B 答 A 的题 → 404
    assert (
        client.post(
            "/api/quiz/answer",
            json={"question_id": qid, "answer_index": 0},
            headers=other_headers,
        ).status_code
        == 404
    )
    # B 的掌握度为空
    assert client.get("/api/quiz/mastery", headers=other_headers).json()[
        "total_answered"
    ] == 0
