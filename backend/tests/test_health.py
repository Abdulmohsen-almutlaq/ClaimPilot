from fastapi.testclient import TestClient


def test_health_returns_status(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert set(body["dependencies"]) == {"db", "redis", "llm"}
