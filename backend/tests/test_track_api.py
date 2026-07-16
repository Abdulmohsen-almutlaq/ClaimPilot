import asyncio
import hashlib
import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.db.session import session_factory
from app.models.case import Case


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


def test_track_requires_matching_policy_number(client: TestClient) -> None:
    case_id = _insert_case(
        status="human_queue", extracted_fields={"policy_number": "POL-TRACK-001"}
    )

    # wrong policy and unknown case answer identically — existence is not leaked
    wrong = client.get(f"/track/{case_id}?policy_number=POL-WRONG")
    unknown = client.get(
        "/track/00000000-0000-0000-0000-000000000000?policy_number=POL-TRACK-001"
    )
    assert wrong.status_code == unknown.status_code == 404
    assert wrong.json() == unknown.json()


def test_track_returns_coarse_phase_without_auth(client: TestClient) -> None:
    case_id = _insert_case(
        status="human_queue", extracted_fields={"policy_number": "POL-TRACK-002"}
    )

    resp = client.get(f"/track/{case_id}?policy_number=pol-track-002")  # case-insensitive

    assert resp.status_code == 200
    body = resp.json()
    assert body["phase"] == "in_review"
    assert body["decided_at"] is None
    assert set(body) == {"case_id", "phase", "submitted_at", "decided_at"}


def test_track_maps_internal_states_to_processing(client: TestClient) -> None:
    case_id = _insert_case(status="error", extracted_fields={"policy_number": "POL-TRACK-003"})
    resp = client.get(f"/track/{case_id}?policy_number=POL-TRACK-003")
    assert resp.json()["phase"] == "processing"


def test_track_case_without_extracted_policy_is_404(client: TestClient) -> None:
    case_id = _insert_case(status="queued")
    resp = client.get(f"/track/{case_id}?policy_number=POL-ANY")
    assert resp.status_code == 404
