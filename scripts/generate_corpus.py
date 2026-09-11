#!/usr/bin/env python3
"""Generate the synthetic submission corpus."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from submission_harness.corpus.generator import generate_corpus
from submission_harness.schema import DifficultyTier


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/default.yaml"),
        help="Path to default.yaml",
    )
    parser.add_argument(
        "--tier",
        action="append",
        choices=[t.value for t in DifficultyTier],
        help="Tier to generate (repeatable). Default: all tiers.",
    )
    parser.add_argument(
        "--per-tier",
        type=int,
        default=None,
        help="Documents per tier (overrides config).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Base seed (overrides config).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (overrides config).",
    )
    args = parser.parse_args()

    with args.config.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    tiers = (
        [DifficultyTier(t) for t in args.tier]
        if args.tier
        else list(DifficultyTier)
    )
    out = args.output or Path(cfg["corpus_output_dir"])
    records = generate_corpus(
        output_dir=out,
        base_seed=args.seed if args.seed is not None else int(cfg["seed"]),
        per_tier=(
            args.per_tier
            if args.per_tier is not None
            else int(cfg["corpus_size_per_tier"])
        ),
        tiers=tiers,
    )
    print(f"Generated {len(records)} documents under {out}")
    for rec in records[:5]:
        print(f"  - {rec.doc_id} (seed={rec.seed})")
    if len(records) > 5:
        print(f"  ... and {len(records) - 5} more")


if __name__ == "__main__":
    main()
