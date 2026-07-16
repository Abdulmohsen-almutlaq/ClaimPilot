import asyncio
import hashlib
import uuid
from typing import Any, cast

from fastapi.testclient import TestClient
from httpx import Response

from app.db.session import session_factory
from app.models.case import Case


def _login(client: TestClient, email: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": "demo"})
    token: str = resp.json()["access_token"]
    return token


def _insert_case(**overrides: Any) -> str:
    async def _run() -> str:
        async with session_factory() as session:
            case = Case(
                document_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                **overrides,
            )
            session.add(case)
            await session.commit()
            return str(case.id)

    return asyncio.run(_run())


def _queued_human_case(ai_decision: str = "approve") -> str:
    return _insert_case(
        status="human_queue",
        route="human_queue",
        route_reason="amount_above_threshold",
        draft={"decision": ai_decision, "confidence": 0.95},
    )


def _decide(client: TestClient, token: str, case_id: str, decision: str) -> Response:
    return cast(
        Response,
        client.post(
            f"/cases/{case_id}/decision",
            json={"decision": decision, "notes": "reviewed"},
            headers={"Authorization": f"Bearer {token}"},
        ),
    )


def test_metrics_rejects_submitter_role(client: TestClient) -> None:
    token = _login(client, "submitter@demo.io")
    resp = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_metrics_shape_and_self_consistency(client: TestClient) -> None:
    """The suite shares one DB, so assert internal consistency rather than
    absolute counts — these invariants hold no matter what other tests created."""
    _insert_case(status="auto_approved", route="auto_approve", tokens_used=500)
    token = _login(client, "approver@demo.io")

    body = client.get("/metrics", headers={"Authorization": f"Bearer {token}"}).json()

    assert body["total_cases"] == sum(body["cases_by_status"].values())
    assert body["human_queue_depth"] == body["cases_by_status"].get("human_queue", 0)
    assert body["overridden_cases"] <= body["human_decided_cases"]
    assert body["total_cases"] >= 1

    terminal_statuses = ("auto_approved", "approved", "denied")
    terminal = sum(body["cases_by_status"].get(s, 0) for s in terminal_statuses)
    if terminal:
        expected = body["cases_by_status"].get("auto_approved", 0) / terminal
        assert body["automation_rate"] == expected
    else:
        assert body["automation_rate"] is None

    for rate in (body["automation_rate"], body["override_rate"]):
        assert rate is None or 0.0 <= rate <= 1.0


def test_metrics_override_rate_reflects_decisions(client: TestClient) -> None:
    token = _login(client, "approver@demo.io")
    # AI said deny, human approves -> one more override on the books.
    case_id = _queued_human_case(ai_decision="deny")
    before = client.get("/metrics", headers={"Authorization": f"Bearer {token}"}).json()

    assert _decide(client, token, case_id, "approve").status_code == 200

    after = client.get("/metrics", headers={"Authorization": f"Bearer {token}"}).json()
    assert after["human_decided_cases"] == before["human_decided_cases"] + 1
    assert after["overridden_cases"] == before["overridden_cases"] + 1
    assert after["override_rate"] == after["overridden_cases"] / after["human_decided_cases"]
