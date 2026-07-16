import uuid
from typing import Any

from fastapi.testclient import TestClient


def _login(client: TestClient, email: str, password: str = "demo") -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    token: str = resp.json()["access_token"]
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user(client: TestClient, token: str, **overrides: Any) -> Any:
    payload = {
        "email": f"user-{uuid.uuid4().hex[:8]}@demo.io",
        "password": "secret",
        "role": "approver",
    } | overrides
    return client.post("/admin/users", json=payload, headers=_auth(token))


def test_users_endpoints_require_admin(client: TestClient) -> None:
    token = _login(client, "approver@demo.io")
    assert client.get("/admin/users", headers=_auth(token)).status_code == 403
    assert _create_user(client, token).status_code == 403


def test_create_user_and_login_with_it(client: TestClient) -> None:
    admin_token = _login(client, "admin@demo.io")
    resp = _create_user(client, admin_token, password="newpass", role="submitter")

    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "submitter"

    new_token = _login(client, body["email"], password="newpass")
    me = client.get("/auth/me", headers=_auth(new_token)).json()
    assert me["email"] == body["email"]
    assert me["role"] == "submitter"


def test_create_user_duplicate_email_409(client: TestClient) -> None:
    admin_token = _login(client, "admin@demo.io")
    email = f"dup-{uuid.uuid4().hex[:8]}@demo.io"
    assert _create_user(client, admin_token, email=email).status_code == 201
    assert _create_user(client, admin_token, email=email).status_code == 409


def test_create_user_rejects_bad_email_and_role(client: TestClient) -> None:
    admin_token = _login(client, "admin@demo.io")
    assert _create_user(client, admin_token, email="not-an-email").status_code == 422
    assert _create_user(client, admin_token, role="superuser").status_code == 422


def test_list_users_contains_created_user(client: TestClient) -> None:
    admin_token = _login(client, "admin@demo.io")
    created = _create_user(client, admin_token).json()

    users = client.get("/admin/users", headers=_auth(admin_token)).json()
    assert created["email"] in {u["email"] for u in users}


def test_update_role_and_self_guard(client: TestClient) -> None:
    admin_token = _login(client, "admin@demo.io")
    created = _create_user(client, admin_token, role="submitter").json()

    resp = client.patch(
        f"/admin/users/{created['id']}", json={"role": "approver"}, headers=_auth(admin_token)
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "approver"

    users = client.get("/admin/users", headers=_auth(admin_token)).json()
    me = next(u for u in users if u["email"] == "admin@demo.io")
    resp = client.patch(
        f"/admin/users/{me['id']}", json={"role": "submitter"}, headers=_auth(admin_token)
    )
    assert resp.status_code == 409


def test_delete_user_and_self_guard(client: TestClient) -> None:
    admin_token = _login(client, "admin@demo.io")
    created = _create_user(client, admin_token).json()

    assert (
        client.delete(f"/admin/users/{created['id']}", headers=_auth(admin_token)).status_code
        == 204
    )
    users = client.get("/admin/users", headers=_auth(admin_token)).json()
    assert created["email"] not in {u["email"] for u in users}

    me = next(u for u in users if u["email"] == "admin@demo.io")
    assert (
        client.delete(f"/admin/users/{me['id']}", headers=_auth(admin_token)).status_code == 409
    )

    unknown = "00000000-0000-0000-0000-000000000000"
    assert client.delete(f"/admin/users/{unknown}", headers=_auth(admin_token)).status_code == 404
