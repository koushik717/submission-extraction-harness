"""Shared helpers for difficulty-tier generation."""

from __future__ import annotations

from pathlib import Path

from submission_harness.schema import GroundTruthRecord


def write_ground_truth(record: GroundTruthRecord, doc_dir: Path) -> None:
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "ground_truth.json").write_text(
        record.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
