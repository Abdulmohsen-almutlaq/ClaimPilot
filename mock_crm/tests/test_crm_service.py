import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_policy_found() -> None:
    resp = client.get("/policies/POL-AUTO-001")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_get_policy_not_found() -> None:
    resp = client.get("/policies/does-not-exist")
    assert resp.status_code == 404


def test_get_customer_found() -> None:
    resp = client.get("/customers/cust-1001")
    assert resp.status_code == 200
    assert resp.json()["email"] == "ava.thompson@example.com"


def test_get_customer_not_found() -> None:
    resp = client.get("/customers/does-not-exist")
    assert resp.status_code == 404


def test_chaos_down_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAOS_MODE", "down")
    resp = client.get("/policies/POL-AUTO-001")
    assert resp.status_code == 503


def test_chaos_errors_returns_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAOS_MODE", "errors")
    resp = client.get("/customers/cust-1001")
    assert resp.status_code == 500
