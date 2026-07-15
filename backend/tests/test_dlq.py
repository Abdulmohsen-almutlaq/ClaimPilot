import uuid

import pytest
from fakes import FakeRetriever
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.dlq import dlq_depth, list_dlq, pop_dlq_entry
from app.db.session import session_factory
from app.llm.adapters import StructuredOutputError, TokenUsage
from app.llm.client import LLMClient
from app.models.case import Case
from app.pipeline.checkpointer import setup_checkpointer_tables
from app.worker import run_case_pipeline


class _AlwaysFailsAdapter:
    def __init__(self, **kwargs: object) -> None:
        pass

    async def generate(
        self, *, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> tuple[BaseModel, TokenUsage]:
        raise StructuredOutputError("boom")


def _login(client: TestClient, email: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": "demo"})
    token: str = resp.json()["access_token"]
    return token


async def _create_failing_case() -> uuid.UUID:
    async with session_factory() as session:
        case = Case(document_hash=str(uuid.uuid4()), document_text="text", status="queued")
        session.add(case)
        await session.commit()
        await session.refresh(case)
    return case.id


async def _fail_case_into_dlq(case_id: uuid.UUID) -> None:
    await setup_checkpointer_tables()
    llm_client = LLMClient(adapter_factory=_AlwaysFailsAdapter)
    with pytest.raises(Exception, match="exhausted"):
        await run_case_pipeline({}, str(case_id), llm_client=llm_client, retriever=FakeRetriever())


async def test_failed_pipeline_lands_in_dlq_with_full_context() -> None:
    case_id = await _create_failing_case()
    await _fail_case_into_dlq(case_id)

    entries = await list_dlq()
    match = [e for e in entries if e["case_id"] == str(case_id)]
    assert len(match) == 1
    assert "exhausted" in match[0]["error"]
    assert "Traceback" in match[0]["traceback"]
    assert match[0]["failed_at"]

    assert await pop_dlq_entry(str(case_id)) is not None  # cleanup
    assert await pop_dlq_entry(str(case_id)) is None  # and it's really gone


async def test_dlq_depth_counts_entries() -> None:
    before = await dlq_depth()
    case_id = await _create_failing_case()
    await _fail_case_into_dlq(case_id)
    assert await dlq_depth() == before + 1
    await pop_dlq_entry(str(case_id))


async def test_requeue_endpoint_requeues_and_removes_from_dlq(client: TestClient) -> None:
    case_id = await _create_failing_case()
    await _fail_case_into_dlq(case_id)

    token = _login(client, "admin@demo.io")
    resp = client.post(
        f"/admin/dlq/{case_id}/requeue", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"case_id": str(case_id), "status": "queued"}

    async with session_factory() as session:
        case = await session.get(Case, case_id)
        assert case is not None
        assert case.status == "queued"
    assert await pop_dlq_entry(str(case_id)) is None  # removed by the requeue


def test_requeue_404_when_not_in_dlq(client: TestClient) -> None:
    token = _login(client, "admin@demo.io")
    resp = client.post(
        f"/admin/dlq/{uuid.uuid4()}/requeue", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


def test_dlq_endpoints_are_admin_only(client: TestClient) -> None:
    token = _login(client, "approver@demo.io")
    assert client.get("/admin/dlq", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert (
        client.post(
            f"/admin/dlq/{uuid.uuid4()}/requeue", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 403
    )
