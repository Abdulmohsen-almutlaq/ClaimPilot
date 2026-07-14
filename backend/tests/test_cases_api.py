import io
from typing import cast

from fastapi.testclient import TestClient
from httpx import Response
from reportlab.pdfgen import canvas


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
