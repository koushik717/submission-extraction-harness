#!/usr/bin/env python3
"""Single-run extraction sanity pass over the corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from submission_harness.client.cost_guard import SpendCapExceeded
from submission_harness.client.llm_client import build_default_client
from submission_harness.extract.agent import ExtractionAgent
from submission_harness.schema import GroundTruthRecord
from submission_harness.verify.metrics import evaluate_pairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--provider", default=None)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("runs/single_pass"))
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    provider = args.provider or cfg.get("default_provider", "local")
    corpus = args.corpus or Path(cfg["corpus_output_dir"])
    args.out.mkdir(parents=True, exist_ok=True)

    client = build_default_client(
        spend_cap_usd=float(cfg["spend_cap_usd"]),
        rate_limit_rpm=int(cfg["rate_limit_rpm"]),
    )
    if provider not in client.backends:
        print(f"Provider {provider!r} unavailable; falling back to local")
        provider = "local"

    agent = ExtractionAgent(client, default_provider=provider)
    pairs = []
    gt_paths = sorted(corpus.glob("*/ground_truth.json"))[: args.limit]
    try:
        for gt_path in gt_paths:
            record = GroundTruthRecord.model_validate_json(gt_path.read_text())
            pdf = gt_path.parent / "document.pdf"
            pred = agent.extract(pdf, provider=provider, temperature=0.0)
            pairs.append((record, pred))
            (args.out / f"{record.doc_id}.json").write_text(
                pred.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
    except SpendCapExceeded as exc:
        print(f"ABORTED: {exc}")
        raise SystemExit(2) from exc

    report = evaluate_pairs(
        pairs,
        text_threshold=float(cfg.get("text_match", {}).get("token_overlap_threshold", 0.8)),
    )
    summary = {
        "provider": provider,
        "n_docs": report.n_docs,
        "headline_aggregate": report.headline_aggregate,
        "per_field_min": report.per_field_min,
        "per_field_max": report.per_field_max,
        "spend_usd": client.cost_guard.spent_usd,
        "per_field": {k: v.accuracy for k, v in report.per_field.items()},
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
