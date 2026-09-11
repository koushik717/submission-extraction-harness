"""Corpus generation smoke tests (all tiers, seeded reproducibility)."""

from __future__ import annotations

from pathlib import Path

from submission_harness.corpus.generator import generate_corpus
from submission_harness.schema import DifficultyTier, GroundTruthRecord
from submission_harness.verify.metrics import self_score_should_be_perfect


def test_generate_all_tiers_small(tmp_path: Path):
    records = generate_corpus(
        output_dir=tmp_path,
        base_seed=7,
        per_tier=1,
        tiers=list(DifficultyTier),
    )
    assert len(records) == 5
    for rec in records:
        assert self_score_should_be_perfect(rec)
        pdf = tmp_path / rec.doc_id / "document.pdf"
        gt = tmp_path / rec.doc_id / "ground_truth.json"
        assert pdf.exists() and pdf.stat().st_size > 500
        assert gt.exists()
        loaded = GroundTruthRecord.model_validate_json(gt.read_text())
        assert loaded.doc_id == rec.doc_id


def test_clean_digital_reproducible(tmp_path: Path):
    a = generate_corpus(
        output_dir=tmp_path / "a",
        base_seed=42,
        per_tier=2,
        tiers=[DifficultyTier.CLEAN_DIGITAL],
    )
    b = generate_corpus(
        output_dir=tmp_path / "b",
        base_seed=42,
        per_tier=2,
        tiers=[DifficultyTier.CLEAN_DIGITAL],
    )
    assert [r.model_dump() for r in a] == [r.model_dump() for r in b]


def test_incomplete_has_nulls(tmp_path: Path):
    records = generate_corpus(
        output_dir=tmp_path,
        base_seed=11,
        per_tier=3,
        tiers=[DifficultyTier.INCOMPLETE],
    )
    for rec in records:
        data = rec.extraction.model_dump()
        nulls = sum(1 for k, v in data.items() if k != "loss_history" and v is None)
        assert nulls >= 2
