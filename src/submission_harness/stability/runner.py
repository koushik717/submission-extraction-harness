"""Stability runner: N extractions × {temp_0, temp_default}, checkpointed."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from submission_harness.checkpoint import CheckpointStore
from submission_harness.client.cost_guard import SpendCapExceeded
from submission_harness.client.llm_client import build_default_client
from submission_harness.extract.agent import ExtractionAgent
from submission_harness.schema import GroundTruthRecord, SubmissionExtraction
from submission_harness.stability.flip_rate import (
    canonical_field_value,
    canonical_loss_history,
    flip_rate_for_field,
    single_vs_majority_accuracy,
)
from submission_harness.verify.scorer import ALL_SCALAR_FIELDS


@dataclass
class ConditionStability:
    condition: str
    flip_rates: dict[str, float]
    mean_single_accuracy: float
    mean_majority_accuracy: float
    n_docs: int


@dataclass
class StabilityReport:
    by_condition: dict[str, ConditionStability]
    spend_usd: float
    n_extractions: int
    provider: str


def load_corpus(corpus_dir: Path) -> list[tuple[GroundTruthRecord, Path]]:
    items = []
    for gt_path in sorted(Path(corpus_dir).glob("*/ground_truth.json")):
        record = GroundTruthRecord.model_validate_json(gt_path.read_text(encoding="utf-8"))
        pdf = gt_path.parent / "document.pdf"
        if pdf.exists():
            items.append((record, pdf))
    return items


def run_stability(
    *,
    corpus_dir: Path,
    run_dir: Path,
    config_path: Path = Path("configs/default.yaml"),
    provider: str | None = None,
    n_runs: int | None = None,
    doc_limit: int | None = None,
) -> StabilityReport:
    with config_path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    n = n_runs if n_runs is not None else int(cfg["stability"]["n_runs"])
    conditions = list(cfg["stability"]["conditions"])
    provider = provider or cfg.get("default_provider", "local")
    # Fall back to local if requested cloud provider has no key
    client = build_default_client(
        spend_cap_usd=float(cfg["spend_cap_usd"]),
        rate_limit_rpm=int(cfg["rate_limit_rpm"]),
        provider_models={
            "openai": cfg["providers"]["openai"]["model"],
            "anthropic": cfg["providers"]["anthropic"]["model"],
            "local": "local-pdf-parser",
        },
    )
    if provider not in client.backends:
        provider = "local"

    agent = ExtractionAgent(client, default_provider=provider)
    store = CheckpointStore(run_dir)
    store.update_meta(provider=provider, n_runs=n, conditions=conditions)

    docs = load_corpus(corpus_dir)
    if doc_limit is not None:
        docs = docs[:doc_limit]

    default_temps = {
        "temp_0": 0.0,
        "temp_default": float(
            cfg["providers"].get(provider, cfg["providers"]["openai"]).get(
                "default_temperature", 1.0
            )
        )
        if provider != "local"
        else 1.0,
    }

    n_extractions = 0
    # doc_id -> condition -> list[extraction]
    collected: dict[str, dict[str, list[SubmissionExtraction]]] = defaultdict(
        lambda: defaultdict(list)
    )
    truths: dict[str, GroundTruthRecord] = {r.doc_id: r for r, _ in docs}

    try:
        for record, pdf in docs:
            for condition in conditions:
                temp = default_temps[condition]
                for i in range(n):
                    key = f"{record.doc_id}|{condition}|{i}"
                    if store.is_done(key):
                        # reload from checkpoint later
                        continue
                    extraction = agent.extract(
                        pdf, provider=provider, temperature=temp, run_id=str(i)
                    )
                    store.save_result(
                        key,
                        {
                            "doc_id": record.doc_id,
                            "condition": condition,
                            "run_index": i,
                            "extraction": extraction.model_dump(mode="json"),
                        },
                    )
                    n_extractions += 1
    except SpendCapExceeded as exc:
        store.update_meta(aborted=True, abort_reason=str(exc))
        raise

    # Load all results (including resumed)
    for row in store.load_results():
        doc_id = row["doc_id"]
        condition = row["condition"]
        collected[doc_id][condition].append(
            SubmissionExtraction.model_validate(row["extraction"])
        )

    text_threshold = float(cfg.get("text_match", {}).get("token_overlap_threshold", 0.8))
    by_condition: dict[str, ConditionStability] = {}

    for condition in conditions:
        field_docs: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        single_accs: list[float] = []
        maj_accs: list[float] = []
        n_docs = 0
        for doc_id, cond_map in collected.items():
            runs = cond_map.get(condition, [])
            if len(runs) < n:
                continue
            n_docs += 1
            truth = truths[doc_id].extraction
            for fname in list(ALL_SCALAR_FIELDS) + ["loss_history"]:
                if fname == "loss_history":
                    vals = [canonical_loss_history(r) for r in runs]
                else:
                    vals = [canonical_field_value(r, fname) for r in runs]
                field_docs[fname][doc_id] = vals
            s_acc, m_acc = single_vs_majority_accuracy(
                truth, runs, text_threshold=text_threshold
            )
            single_accs.append(s_acc)
            maj_accs.append(m_acc)

        flip_rates = {
            fname: flip_rate_for_field(doc_map)
            for fname, doc_map in field_docs.items()
        }
        by_condition[condition] = ConditionStability(
            condition=condition,
            flip_rates=flip_rates,
            mean_single_accuracy=sum(single_accs) / len(single_accs) if single_accs else 0.0,
            mean_majority_accuracy=sum(maj_accs) / len(maj_accs) if maj_accs else 0.0,
            n_docs=n_docs,
        )

    spend = client.cost_guard.spent_usd
    store.update_meta(spend_usd=spend, finished=True)
    report = StabilityReport(
        by_condition=by_condition,
        spend_usd=spend,
        n_extractions=n_extractions,
        provider=provider,
    )
    (run_dir / "stability_report.json").write_text(
        _dump_stability(report), encoding="utf-8"
    )
    return report


def _dump_stability(report: StabilityReport) -> str:
    import json

    payload = {
        "provider": report.provider,
        "spend_usd": report.spend_usd,
        "n_extractions": report.n_extractions,
        "by_condition": {
            name: {
                "condition": c.condition,
                "flip_rates": c.flip_rates,
                "mean_single_accuracy": c.mean_single_accuracy,
                "mean_majority_accuracy": c.mean_majority_accuracy,
                "n_docs": c.n_docs,
            }
            for name, c in report.by_condition.items()
        },
    }
    return json.dumps(payload, indent=2) + "\n"
