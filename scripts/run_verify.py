#!/usr/bin/env python3
"""Score saved extractions (or GT vs self) and print field/tier tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from submission_harness.schema import GroundTruthRecord, SubmissionExtraction
from submission_harness.verify.metrics import evaluate_pairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/corpus"))
    parser.add_argument("--preds", type=Path, default=None, help="Dir of {doc_id}.json preds")
    parser.add_argument("--self-check", action="store_true", help="Score GT vs itself")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    thr = float(cfg.get("text_match", {}).get("token_overlap_threshold", 0.8))

    pairs = []
    for gt_path in sorted(args.corpus.glob("*/ground_truth.json")):
        record = GroundTruthRecord.model_validate_json(gt_path.read_text())
        if args.self_check:
            pred = record.extraction
        else:
            if args.preds is None:
                raise SystemExit("--preds required unless --self-check")
            pred_path = args.preds / f"{record.doc_id}.json"
            if not pred_path.exists():
                continue
            pred = SubmissionExtraction.model_validate_json(pred_path.read_text())
        pairs.append((record, pred))

    report = evaluate_pairs(pairs, text_threshold=thr)
    print(f"docs={report.n_docs} headline={report.headline_aggregate:.3f}")
    print(f"per-field range {report.per_field_min:.3f} .. {report.per_field_max:.3f}")
    for name, fa in report.per_field.items():
        print(f"  {name:24s} {fa.accuracy:.3f}")
    for tier, ta in report.by_tier.items():
        print(f"tier {tier:20s} {ta.aggregate_accuracy:.3f} (n={ta.n_docs})")

    if args.self_check and report.headline_aggregate != 1.0:
        raise SystemExit("SELF-CHECK FAILED: verifier is broken")


if __name__ == "__main__":
    main()
