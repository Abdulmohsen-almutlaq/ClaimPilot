from app.pipeline.nodes.evidence import run_evidence
from app.pipeline.schemas import Evidence
from app.pipeline.state import CaseState


class _StubRetriever:
    def __init__(self, evidence: list[Evidence]) -> None:
        self._evidence = evidence
        self.queries: list[str] = []

    async def retrieve(self, query: str) -> list[Evidence]:
        self.queries.append(query)
        return self._evidence


_FIELDS = {
    "claimant_name": "Jane Doe",
    "policy_number": "POL-AUTO-001",
    "incident_date": "2026-01-05",
    "claimed_amount": "1200.00",
    "category": "auto",
    "description": "Rear-end collision at a stop light",
}


async def test_evidence_found_moves_case_forward() -> None:
    retriever = _StubRetriever(
        [Evidence(clause_id="AUTO-001", text="Collision coverage.", similarity=0.8)]
    )
    state: CaseState = {"extracted_fields": _FIELDS}
    update = await run_evidence(state, retriever=retriever)

    assert update["status"] == "evidence_retrieved"
    assert update["evidence"][0]["clause_id"] == "AUTO-001"
    # query is built from the extracted fields, not raw document text
    assert "auto" in retriever.queries[0]
    assert "Rear-end collision" in retriever.queries[0]


async def test_no_evidence_flags_for_human() -> None:
    retriever = _StubRetriever([])
    state: CaseState = {"extracted_fields": _FIELDS}
    update = await run_evidence(state, retriever=retriever)

    assert update["evidence"] == []
    assert update["status"] == "human_queue"
    assert update["route"] == "human_queue"
