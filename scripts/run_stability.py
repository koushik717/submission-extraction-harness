#!/usr/bin/env python3
"""Run checkpointed stability sweep (N runs × temp conditions)."""

from __future__ import annotations

import argparse
from pathlib import Path

from submission_harness.client.cost_guard import SpendCapExceeded
from submission_harness.stability.runner import run_stability


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--corpus", type=Path, default=Path("data/corpus"))
    parser.add_argument("--run-dir", type=Path, default=Path("runs/stability"))
    parser.add_argument("--provider", default=None)
    parser.add_argument("--n-runs", type=int, default=None)
    parser.add_argument("--doc-limit", type=int, default=None)
    args = parser.parse_args()

    try:
        report = run_stability(
            corpus_dir=args.corpus,
            run_dir=args.run_dir,
            config_path=args.config,
            provider=args.provider,
            n_runs=args.n_runs,
            doc_limit=args.doc_limit,
        )
    except SpendCapExceeded as exc:
        print(f"ABORTED by spend cap: {exc}")
        raise SystemExit(2) from exc

    print(f"Provider: {report.provider}")
    print(f"Spend: ${report.spend_usd:.4f}")
    for name, cond in report.by_condition.items():
        print(
            f"{name}: single={cond.mean_single_accuracy:.3f} "
            f"majority={cond.mean_majority_accuracy:.3f} docs={cond.n_docs}"
        )


if __name__ == "__main__":
    main()
