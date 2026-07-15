"""CI gate for the eval harness (spec 5.8): the build fails if the committed
eval results are below the thresholds in configs/evals.yaml, or if they are
stale (dataset changed without re-running the evals).

The gate reads evals/results.json — the artifact of the last `make evals` run
against the live provider — so CI itself needs no API key, no database, and no
model download, yet a prompt/model/dataset change cannot merge without a fresh
eval run proving the thresholds still hold.

Run: pytest evals/test_evals.py
"""

import hashlib
import json
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = _ROOT / "evals" / "results.json"
DATASET_PATH = _ROOT / "evals" / "dataset" / "cases.jsonl"
THRESHOLDS_PATH = _ROOT / "configs" / "evals.yaml"


@pytest.fixture(scope="module")
def results() -> dict:
    assert RESULTS_PATH.exists(), "evals/results.json missing — run `make evals` and commit it"
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


def test_results_match_committed_dataset(results: dict) -> None:
    dataset_sha = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    assert results["dataset_sha256"] == dataset_sha, (
        "dataset changed since the last eval run — re-run `make evals` and commit results.json"
    )


def test_results_are_from_the_full_dataset(results: dict) -> None:
    assert not results.get("smoke"), "committed results.json must come from a full run, not --smoke"
    n_dataset = sum(1 for line in DATASET_PATH.read_text(encoding="utf-8").splitlines() if line)
    assert results["metrics"]["n_cases"] == n_dataset


def test_no_cases_crashed(results: dict) -> None:
    assert results["metrics"]["errors"] == 0


def test_thresholds(results: dict) -> None:
    thresholds: dict[str, float] = yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8"))[
        "thresholds"
    ]
    metrics = results["metrics"]
    failures = [
        f"{name}: {metrics.get(name)} < {minimum}"
        for name, minimum in thresholds.items()
        if metrics.get(name) is None or metrics[name] < minimum
    ]
    assert not failures, "eval thresholds not met:\n  " + "\n  ".join(failures)
