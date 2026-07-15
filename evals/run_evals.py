"""Runs the labeled eval dataset through the real pipeline graph and scores it
(spec 5.8): per-field extraction accuracy, decision accuracy + confusion matrix,
citation accuracy, routing correctness (high-risk recall), injection resistance,
cost and latency.

Requires the docker stack (postgres + mock CRM) and the provider API key in .env.

Usage:
    python evals/run_evals.py             # full 62-case run
    python evals/run_evals.py --smoke     # stratified 15-case subset (PRs)
    python evals/run_evals.py --gate      # exit 1 if configs/evals.yaml thresholds fail

Outputs evals/results.json (committed as the CI-gate baseline) and evals/report.md.
"""

import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "backend"))

from scoring import aggregate, score_case  # noqa: E402

from app.llm.client import LLMClient  # noqa: E402
from app.llm.registry import load_models_config  # noqa: E402
from app.pipeline.graph import compile_graph  # noqa: E402
from app.rag.retrieve import build_default_retriever  # noqa: E402

DATASET_PATH = _ROOT / "evals" / "dataset" / "cases.jsonl"
RESULTS_PATH = _ROOT / "evals" / "results.json"
REPORT_PATH = _ROOT / "evals" / "report.md"
THRESHOLDS_PATH = _ROOT / "configs" / "evals.yaml"

CONCURRENCY = 4


def load_dataset() -> tuple[list[dict[str, Any]], str]:
    raw = DATASET_PATH.read_bytes()
    cases = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    return cases, hashlib.sha256(raw).hexdigest()


def smoke_subset(cases: list[dict[str, Any]], size: int = 15) -> list[dict[str, Any]]:
    """One case per scenario class first (tags[1]), then fill in dataset order —
    a PR-sized subset that still touches every failure mode."""
    picked: list[dict[str, Any]] = []
    seen_classes: set[str] = set()
    for case in cases:
        scenario = case["tags"][1] if len(case["tags"]) > 1 else case["tags"][0]
        if scenario not in seen_classes:
            seen_classes.add(scenario)
            picked.append(case)
    for case in cases:
        if len(picked) >= size:
            break
        if case not in picked:
            picked.append(case)
    return picked[:size]


async def run_one(
    graph: Any, case: dict[str, Any], semaphore: asyncio.Semaphore
) -> dict[str, Any]:
    async with semaphore:
        start = time.monotonic()
        try:
            final = await graph.ainvoke(
                {"case_id": case["case_id"], "document_text": case["document_text"]}
            )
            final = dict(final)
        except Exception as exc:  # a crashed case is a scored failure, not a crashed run
            final = {"status": "error", "_error": f"{type(exc).__name__}: {exc}"}
        final["_latency_seconds"] = round(time.monotonic() - start, 2)
        print(
            f"  {case['case_id']}  status={final.get('status')}  "
            f"({final['_latency_seconds']}s)",
            flush=True,
        )
        return score_case(case, final)


async def run_all(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    llm_client = LLMClient()
    graph = compile_graph(llm_client, build_default_retriever(), None)
    semaphore = asyncio.Semaphore(CONCURRENCY)
    return list(await asyncio.gather(*(run_one(graph, c, semaphore) for c in cases)))


def write_report(results: dict[str, Any]) -> None:
    m = results["metrics"]
    lines = [
        "# Eval Report",
        "",
        f"- Generated: {results['generated_at']}",
        f"- Provider/model: {results['provider']} / {results['model']}",
        f"- Cases: {m['n_cases']}  |  Errors: {m['errors']}",
        f"- Total cost: ${m['total_cost_usd']}  |  Tokens: {m['total_tokens']}",
        f"- Latency p50/p95: {m['p50_latency_seconds']}s / {m['p95_latency_seconds']}s",
        "",
        "## Metrics",
        "",
        "| Metric | Score |",
        "|---|---|",
        f"| Extraction accuracy (per-field) | {m['extraction_accuracy']} |",
        f"| Decision accuracy | {m['decision_accuracy']} |",
        f"| Citation accuracy ({m['citation_eligible_cases']} eligible) | {m['citation_accuracy']} |",
        f"| Routing status accuracy | {m['routing_status_accuracy']} |",
        f"| High-risk recall | {m['high_risk_recall']} |",
        f"| Injection resistance | {m['injection_resistance']} |",
        "",
        "## Extraction per field",
        "",
        "| Field | Accuracy |",
        "|---|---|",
    ]
    lines += [f"| {f} | {v} |" for f, v in m["extraction_per_field"].items()]
    lines += ["", "## Decision confusion matrix (gold -> predicted)", ""]
    decisions = sorted({d for row in m["decision_confusion"].values() for d in row})
    lines.append("| gold \\ predicted | " + " | ".join(decisions) + " |")
    lines.append("|---|" + "---|" * len(decisions))
    for gold, row in sorted(m["decision_confusion"].items()):
        lines.append(f"| {gold} | " + " | ".join(str(row.get(d, 0)) for d in decisions) + " |")

    misses = [
        s
        for s in results["per_case"]
        if s["error"]
        or s["decision_hit"] is False
        or s["citation_hit"] is False
        or not s["status_hit"]
        or not all(s["field_hits"].values())
    ]
    lines += ["", f"## Misses ({len(misses)})", ""]
    for s in misses:
        bad_fields = [f for f, hit in s["field_hits"].items() if not hit]
        detail = []
        if s["error"]:
            detail.append(f"error={s['error']}")
        if s["decision_hit"] is False:
            detail.append(f"decision {s['decision']} != {s['gold_decision']}")
        if s["citation_hit"] is False:
            detail.append("citation missed")
        if not s["status_hit"]:
            detail.append(f"status {s['status']} != {s['gold_status']}")
        if bad_fields:
            detail.append(f"fields: {', '.join(bad_fields)}")
        if s.get("route_reason"):
            detail.append(f"route_reason={s['route_reason']}")
        if s.get("citations") is not None:
            detail.append(f"cited={s['citations']}")
        lines.append(f"- `{s['case_id']}` [{', '.join(s['tags'])}] — {'; '.join(detail)}")
        if s.get("qa_reasons"):
            lines.append(f"  - qa_reasons: {s['qa_reasons']}")
        if s.get("reasoning"):
            lines.append(f"  - reasoning: {s['reasoning']}")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def check_gate(metrics: dict[str, Any]) -> list[str]:
    thresholds: dict[str, float] = yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8"))[
        "thresholds"
    ]
    failures = []
    for name, minimum in thresholds.items():
        actual = metrics.get(name)
        if actual is None or actual < minimum:
            failures.append(f"{name}: {actual} < {minimum}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="stratified 15-case subset")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--gate", action="store_true", help="exit 1 if thresholds fail")
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if hasattr(sys.stdout, "reconfigure"):
        # Windows consoles default to cp1252, which crashes printing Arabic
        # case content; CI/Linux are already UTF-8 so this is a no-op there.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    cases, dataset_sha = load_dataset()
    if args.smoke:
        cases = smoke_subset(cases)
    if args.limit:
        cases = cases[: args.limit]

    config = load_models_config()
    provider = config.default_provider
    model = config.provider(provider).model
    print(f"running {len(cases)} cases against {provider}/{model} ...", flush=True)

    scored = asyncio.run(run_all(cases))
    metrics = aggregate(scored)

    results = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset_sha256": dataset_sha,
        "smoke": args.smoke,
        "provider": provider,
        "model": model,
        "metrics": metrics,
        "per_case": scored,
    }
    RESULTS_PATH.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    write_report(results)
    print(json.dumps(metrics, indent=2))
    print(f"\nwrote {RESULTS_PATH.name} and {REPORT_PATH.name}")

    if args.gate:
        failures = check_gate(metrics)
        if failures:
            print("\nEVAL GATE FAILED:\n  " + "\n  ".join(failures))
            raise SystemExit(1)
        print("\neval gate passed")


if __name__ == "__main__":
    main()
