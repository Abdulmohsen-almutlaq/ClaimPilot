import asyncio
import hashlib
import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.db.session import session_factory
from app.models.case import Case


def _login(client: TestClient, email: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": "demo"})
    token: str = resp.json()["access_token"]
    return token


def _insert_case(**overrides: Any) -> str:
    """Insert a case directly, bypassing the pipeline, to test the decision
    endpoint against exact pre-states (queued, human_queue, etc.)."""

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
        extracted_fields={"claimant_name": "Jane Doe", "claimed_amount": "95000"},
    )


def _decide(client: TestClient, token: str, case_id: str, decision: str) -> Any:
    return client.post(
        f"/cases/{case_id}/decision",
        json={"decision": decision, "notes": "reviewed"},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_decision_rejects_submitter_role(client: TestClient) -> None:
    case_id = _queued_human_case()
    token = _login(client, "submitter@demo.io")
    assert _decide(client, token, case_id, "approve").status_code == 403


def test_decision_404_for_unknown_case(client: TestClient) -> None:
    token = _login(client, "approver@demo.io")
    resp = _decide(client, token, "00000000-0000-0000-0000-000000000000", "approve")
    assert resp.status_code == 404


def test_decision_409_when_case_not_in_human_queue(client: TestClient) -> None:
    case_id = _insert_case(status="queued")
    token = _login(client, "approver@demo.io")
    assert _decide(client, token, case_id, "approve").status_code == 409


def test_approve_matching_ai_is_not_an_override(client: TestClient) -> None:
    case_id = _queued_human_case(ai_decision="approve")
    token = _login(client, "approver@demo.io")

    resp = _decide(client, token, case_id, "approve")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["human_decision"] == "approve"
    assert body["ai_decision"] == "approve"
    assert body["overridden"] is False


def test_decision_against_ai_draft_is_an_override(client: TestClient) -> None:
    case_id = _queued_human_case(ai_decision="reject")
    token = _login(client, "approver@demo.io")

    resp = _decide(client, token, case_id, "approve")

    assert resp.status_code == 200
    assert resp.json()["overridden"] is True


def test_decided_case_cannot_be_decided_again(client: TestClient) -> None:
    case_id = _queued_human_case()
    token = _login(client, "approver@demo.io")

    assert _decide(client, token, case_id, "reject").status_code == 200
    assert _decide(client, token, case_id, "approve").status_code == 409


def test_decision_is_recorded_on_case_and_in_audit_trail(client: TestClient) -> None:
    case_id = _queued_human_case()
    token = _login(client, "approver@demo.io")
    _decide(client, token, case_id, "reject")

    detail = client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {token}"}).json()
    assert detail["status"] == "rejected"
    assert detail["human_decision"] == "reject"
    assert detail["overridden"] is True
    assert detail["decided_by"] == "approver@demo.io"
    assert detail["decided_at"] is not None

    audit = client.get(
        f"/cases/{case_id}/audit", headers={"Authorization": f"Bearer {token}"}
    ).json()
    decisions = [e for e in audit if e["event_type"] == "human_decision"]
    assert len(decisions) == 1
    assert decisions[0]["actor"] == "approver@demo.io"
    assert decisions[0]["payload"]["overridden"] is True
    assert decisions[0]["payload"]["ai_decision"] == "approve"


def test_queue_listing_returns_human_queue_cases(client: TestClient) -> None:
    case_id = _queued_human_case()
    token = _login(client, "approver@demo.io")

    resp = client.get("/cases?status=human_queue", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    rows = {row["case_id"]: row for row in resp.json()}
    assert case_id in rows
    row = rows[case_id]
    assert row["route_reason"] == "amount_above_threshold"
    assert row["claimant_name"] == "Jane Doe"
    assert row["claimed_amount"] == "95000"


def test_queue_listing_rejects_submitter_role(client: TestClient) -> None:
    token = _login(client, "submitter@demo.io")
    resp = client.get("/cases?status=human_queue", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
