#!/usr/bin/env python3
"""Build REPORT.md + routing_policy.json from a stability run + single-pass preds.

If single-pass preds are missing, rebuilds evaluation from the first temp_0 run
of each document in the stability results.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from submission_harness.report.write_report import write_report
from submission_harness.routing.policy import build_routing_policy, write_routing_policy
from submission_harness.schema import GroundTruthRecord, SubmissionExtraction
from submission_harness.stability.runner import StabilityReport, ConditionStability
from submission_harness.verify.metrics import evaluate_pairs


def _load_stability(path: Path) -> StabilityReport:
    raw = json.loads(path.read_text(encoding="utf-8"))
    by_condition = {
        k: ConditionStability(**v) for k, v in raw["by_condition"].items()
    }
    return StabilityReport(
        by_condition=by_condition,
        spend_usd=raw["spend_usd"],
        n_extractions=raw["n_extractions"],
        provider=raw["provider"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/corpus"))
    parser.add_argument("--stability-dir", type=Path, default=Path("runs/stability"))
    parser.add_argument("--preds", type=Path, default=Path("runs/single_pass"))
    parser.add_argument("--out", type=Path, default=Path("runs/report"))
    parser.add_argument("--report", type=Path, default=Path("REPORT.md"))
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    thr = float(cfg.get("text_match", {}).get("token_overlap_threshold", 0.8))

    pairs = []
    for gt_path in sorted(args.corpus.glob("*/ground_truth.json")):
        record = GroundTruthRecord.model_validate_json(gt_path.read_text())
        pred_path = args.preds / f"{record.doc_id}.json"
        if pred_path.exists():
            pred = SubmissionExtraction.model_validate_json(pred_path.read_text())
        else:
            # Fallback: first temp_0 extraction from stability jsonl
            pred = None
            results = args.stability_dir / "results.jsonl"
            if results.exists():
                for line in results.read_text().splitlines():
                    row = json.loads(line)
                    if (
                        row.get("doc_id") == record.doc_id
                        and row.get("condition") == "temp_0"
                        and row.get("run_index") == 0
                    ):
                        pred = SubmissionExtraction.model_validate(row["extraction"])
                        break
            if pred is None:
                continue
        pairs.append((record, pred))

    evaluation = evaluate_pairs(pairs, text_threshold=thr)
    stability = _load_stability(args.stability_dir / "stability_report.json")
    policy = build_routing_policy(evaluation, stability)
    args.out.mkdir(parents=True, exist_ok=True)
    write_routing_policy(policy, args.out / "routing_policy.json")
    write_report(
        evaluation=evaluation,
        stability=stability,
        policy=policy,
        output_dir=args.out,
        report_path=args.report,
    )
    print(f"Wrote {args.report}")
    print(
        f"headline={evaluation.headline_aggregate:.3f} "
        f"range={evaluation.per_field_min:.3f}..{evaluation.per_field_max:.3f}"
    )


if __name__ == "__main__":
    main()
