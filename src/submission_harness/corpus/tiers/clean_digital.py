"""Clean digital tier: crisp generated PDF, all fields present."""

from __future__ import annotations

import random
from pathlib import Path

from submission_harness.corpus.fields import sample_extraction
from submission_harness.corpus.render_pdf import render_submission_pdf
from submission_harness.schema import (
    DifficultyTier,
    GroundTruthRecord,
)


def generate_clean_digital_document(
    *,
    doc_index: int,
    base_seed: int,
    output_dir: Path,
) -> GroundTruthRecord:
    """Generate one clean_digital document + ground_truth.json."""
    doc_seed = base_seed + doc_index * 1009
    rng = random.Random(doc_seed)
    extraction = sample_extraction(rng)

    doc_id = f"clean_digital_{doc_index:03d}"
    doc_dir = Path(output_dir) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = doc_dir / "document.pdf"
    render_submission_pdf(extraction, pdf_path)

    record = GroundTruthRecord(
        doc_id=doc_id,
        difficulty_tier=DifficultyTier.CLEAN_DIGITAL,
        seed=doc_seed,
        extraction=extraction,
    )
    (doc_dir / "ground_truth.json").write_text(
        record.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return record
