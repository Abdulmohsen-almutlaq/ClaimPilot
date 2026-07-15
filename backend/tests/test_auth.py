import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth.dependencies import require_role
from app.models.user import User


def test_login_success(client: TestClient) -> None:
    resp = client.post("/auth/login", json={"email": "approver@demo.io", "password": "demo"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_invalid_password(client: TestClient) -> None:
    resp = client.post("/auth/login", json={"email": "approver@demo.io", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(client: TestClient) -> None:
    resp = client.post("/auth/login", json={"email": "nobody@demo.io", "password": "demo"})
    assert resp.status_code == 401


def test_me_requires_token(client: TestClient) -> None:
    resp = client.get("/auth/me")
    assert resp.status_code in (401, 403)


def test_me_with_valid_token(client: TestClient) -> None:
    login = client.post("/auth/login", json={"email": "admin@demo.io", "password": "demo"})
    token = login.json()["access_token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"email": "admin@demo.io", "role": "admin"}


async def test_require_role_allows_matching_role() -> None:
    dependency = require_role("admin", "approver")
    user = User(email="approver@demo.io", password_hash="x", role="approver")
    assert await dependency(user=user) == user


async def test_require_role_blocks_non_matching_role() -> None:
    dependency = require_role("admin")
    user = User(email="submitter@demo.io", password_hash="x", role="submitter")
    with pytest.raises(HTTPException) as exc_info:
        await dependency(user=user)
    assert exc_info.value.status_code == 403
