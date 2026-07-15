# Engineering Principles

These are the rules this codebase is written to. Most are enforced mechanically
(CI fails when they're violated); the rest are conventions reviewers hold the
line on. When in doubt, prefer boring and explicit over clever.

## Enforced by CI

| Principle | Enforcement |
|---|---|
| Everything is typed | `mypy --strict` on `app/` — zero errors |
| One style, no debates | `ruff` (pycodestyle, pyflakes, isort, pyupgrade, bugbear) |
| Behavior is proven, not claimed | `pytest` with coverage ≥ 80% on `app/` |
| Failure paths are tested first | reliability tests (resumability, audit immutability, CRM chaos) are integration tests against real Postgres/Redis, not mocks of our own code |

## Design rules

1. **No unvalidated LLM output crosses a system boundary.** Every model response
   is parsed into a Pydantic schema; parse failure is a retried, then failed,
   call — never a silently accepted string. LLM text is data, not instructions:
   document content is fenced (`<document>…`) and prompts say so explicitly.

2. **Dependency injection over globals.** Nodes take `llm_client`/`retriever`
   as explicit parameters; tests substitute fakes at the same seam production
   code uses (`adapter_factory=`, `retriever=`). If you can't fake it in a
   test without monkeypatching, the seam is wrong.

3. **Small interfaces, `Protocol` not inheritance.** `ChatAdapter`,
   `EmbeddingBackend`, `Retriever` are structural protocols with one or two
   methods. Implementations don't import each other.

4. **Config is data, not code.** Model names, endpoints, temperatures, token
   budgets, thresholds, prompt versions: `configs/*.yaml`. Secrets: `.env`
   only. Nothing tunable is hardcoded; changing provider (Anthropic → DeepSeek
   → local Ollama) is a config edit, zero code changes.

5. **Deterministic by default, semantic by choice.** Anything on the CI-gated
   eval path (embeddings, dataset generation) must be reproducible bit-for-bit.
   Non-deterministic upgrades (dense embeddings, live models) are opt-in config.

6. **Use validated domain data to shrink the problem.** Example: once the
   claim's category is validated, evidence retrieval is scoped to that
   category's clauses — similarity search alone shouldn't fight noise that
   structured data already eliminates.

7. **Every state transition is observable and auditable.** Nodes write status
   changes; `audit_log` is append-only (DB trigger rejects UPDATE/DELETE);
   model + prompt versions travel with every call result.

8. **Failures land somewhere visible.** A crashed pipeline records
   `status="error"` + the exception on the case; a dead dependency routes to
   `human_queue` with a reason. Nothing hangs in `queued` forever, nothing
   fails silently.

9. **Leverage open source; hand-roll only with a reason.** Hand-rolled code
   needs a written justification in its docstring or commit. Current map:

   | Concern | Open-source project |
   |---|---|
   | API, validation, ORM, migrations | FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
   | Agent graph + checkpoints | LangGraph (+ langgraph-checkpoint-postgres) |
   | LLM provider adapters | LangChain (ChatAnthropic / ChatOpenAI) |
   | Vector search | pgvector |
   | RAG embeddings | fastembed (ONNX) running HF `all-MiniLM-L6-v2` |
   | Queue / DLQ | arq + redis-py |
   | PDF extraction | pdfplumber |
   | Tests / lint / types | pytest, respx, ruff, mypy |

   Justified hand-rolls: the **hashing embedder** (tests/CI only — offline and
   bit-for-bit reproducible, where a model download would not be) and the
   **circuit breaker** (~25 lines; aiobreaker/pybreaker don't offer the
   injectable clock our deterministic half-open tests need).

10. **Comments explain *why*, never *what*.** Especially: comments that record
    a live failure the code now prevents (see `retrieve.py`, `worker.py`,
    `session.py`) are the most valuable lines in the file. Keep them.

## Working agreements

- Migrations are append-only history: never edit an applied migration; add a new one.
- Prompts are versioned files; changing behavior means a new `name.vN.md`, not
  editing `v1` in place.
- Commit messages explain the why and record what was actually verified
  (live runs, not just unit tests) — they are the project's engineering log.
