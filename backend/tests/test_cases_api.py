import asyncio
import hashlib
import io
import uuid
from typing import Any, cast

from fastapi.testclient import TestClient
from httpx import Response
from reportlab.pdfgen import canvas

from app.db.session import session_factory
from app.models.case import Case


def _build_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, text)
    pdf.save()
    return buffer.getvalue()


def _login(client: TestClient, email: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": "demo"})
    token: str = resp.json()["access_token"]
    return token


def _upload(client: TestClient, token: str, pdf_bytes: bytes) -> Response:
    return cast(
        Response,
        client.post(
            "/cases",
            files={"file": ("claim.pdf", pdf_bytes, "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        ),
    )


def test_create_case_returns_201_and_queued_status(client: TestClient) -> None:
    token = _login(client, "submitter@demo.io")
    resp = _upload(client, token, _build_pdf("Claim for Jane Doe, policy POL-AUTO-001"))

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "queued"
    assert body["case_id"]


def test_create_case_is_idempotent_on_document_hash(client: TestClient) -> None:
    token = _login(client, "submitter@demo.io")
    pdf_bytes = _build_pdf("Duplicate submission test")

    first = _upload(client, token, pdf_bytes)
    second = _upload(client, token, pdf_bytes)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["case_id"] == second.json()["case_id"]


def test_create_case_rejects_approver_role(client: TestClient) -> None:
    token = _login(client, "approver@demo.io")
    resp = _upload(client, token, _build_pdf("Not allowed"))

    assert resp.status_code == 403


def test_create_case_rejects_empty_file(client: TestClient) -> None:
    token = _login(client, "submitter@demo.io")
    resp = _upload(client, token, b"")

    assert resp.status_code == 400


def test_get_case_not_found(client: TestClient) -> None:
    token = _login(client, "approver@demo.io")
    resp = client.get(
        "/cases/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_get_case_after_create(client: TestClient) -> None:
    submitter_token = _login(client, "submitter@demo.io")
    created = _upload(client, submitter_token, _build_pdf("Fetch me back"))
    case_id = created.json()["case_id"]

    approver_token = _login(client, "approver@demo.io")
    resp = client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {approver_token}"})

    assert resp.status_code == 200
    assert resp.json()["case_id"] == case_id
    assert resp.json()["status"] == "queued"
    assert resp.json()["evidence"] is None


def _insert_case(**overrides: Any) -> str:
    """Insert a case directly, bypassing the pipeline, so the detail endpoint
    can be tested against pipeline outputs a fresh upload never has."""

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


def test_list_cases_search_matches_claimant_and_policy(client: TestClient) -> None:
    marker = uuid.uuid4().hex[:8]
    matching = _insert_case(
        status="approved",
        extracted_fields={"claimant_name": f"Fahad {marker}", "policy_number": "POL-X-001"},
    )
    by_policy = _insert_case(
        status="rejected",
        extracted_fields={"claimant_name": "Someone Else", "policy_number": f"POL-{marker}-9"},
    )
    _insert_case(
        status="approved",
        extracted_fields={"claimant_name": "No Match", "policy_number": "POL-Y-002"},
    )
    token = _login(client, "approver@demo.io")

    # case-insensitive match on the claimant name
    resp = client.get(
        f"/cases?q=fahad {marker}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert [row["case_id"] for row in resp.json()] == [matching]

    # match on the policy number
    resp = client.get(
        f"/cases?q=POL-{marker}", headers={"Authorization": f"Bearer {token}"}
    )
    assert [row["case_id"] for row in resp.json()] == [by_policy]

    # no matches
    resp = client.get(
        f"/cases?q={uuid.uuid4().hex}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.json() == []


def test_list_cases_order_desc_returns_newest_first(client: TestClient) -> None:
    marker = uuid.uuid4().hex[:8]
    older = _insert_case(
        status="approved", extracted_fields={"claimant_name": f"Order {marker} A"}
    )
    newer = _insert_case(
        status="approved", extracted_fields={"claimant_name": f"Order {marker} B"}
    )
    token = _login(client, "approver@demo.io")

    resp = client.get(
        f"/cases?q=Order {marker}&order=desc", headers={"Authorization": f"Bearer {token}"}
    )
    assert [row["case_id"] for row in resp.json()] == [newer, older]

    resp = client.get(
        f"/cases?q=Order {marker}", headers={"Authorization": f"Bearer {token}"}
    )
    assert [row["case_id"] for row in resp.json()] == [older, newer]


def test_get_case_returns_retrieved_evidence(client: TestClient) -> None:
    evidence = [
        {
            "clause_id": "AUTO-001",
            "text": "Collision damage is covered up to SAR 50,000 per incident.",
            "similarity": 0.87,
        },
        {
            "clause_id": "AUTO-014",
            "text": "Claims must be filed within 30 days of the incident.",
            "similarity": 0.61,
        },
    ]
    case_id = _insert_case(status="human_queue", evidence=evidence)

    token = _login(client, "approver@demo.io")
    resp = client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()["evidence"] == evidence


def test_audit_endpoint_requires_approver_or_admin(client: TestClient) -> None:
    submitter_token = _login(client, "submitter@demo.io")
    created = _upload(client, submitter_token, _build_pdf("Audit RBAC check"))
    case_id = created.json()["case_id"]

    resp = client.get(
        f"/cases/{case_id}/audit", headers={"Authorization": f"Bearer {submitter_token}"}
    )
    assert resp.status_code == 403

    approver_token = _login(client, "approver@demo.io")
    resp = client.get(
        f"/cases/{case_id}/audit", headers={"Authorization": f"Bearer {approver_token}"}
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_audit_endpoint_404_for_unknown_case(client: TestClient) -> None:
    approver_token = _login(client, "approver@demo.io")
    resp = client.get(
        "/cases/00000000-0000-0000-0000-000000000000/audit",
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert resp.status_code == 404
