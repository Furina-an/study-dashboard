import os
import sys
from pathlib import Path

# 固定测试用密钥/邀请码（security.py 在调用时读取环境变量）
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef-0123456789abcdef"
os.environ["INVITE_CODE"] = "test-invite"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.math_data import seed_math_if_empty  # noqa: E402

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(
    bind=test_engine, autocommit=False, autoflush=False
)

REGISTER_PAYLOAD = {
    "username": "alice",
    "password": "secret123",
    "invite_code": "test-invite",
}


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with TestSessionLocal() as _db:
        seed_math_if_empty(_db)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with TestSessionLocal() as _db:
        seed_math_if_empty(_db)

    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def auth_headers(client):
    response = client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def other_headers(client):
    response = client.post(
        "/api/auth/register",
        json={**REGISTER_PAYLOAD, "username": "bob"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}