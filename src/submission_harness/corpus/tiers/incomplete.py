"""Incomplete tier: 2–4 fields genuinely missing (null in GT and blank on PDF)."""

from __future__ import annotations

import random
from pathlib import Path

from submission_harness.corpus.fields import sample_extraction
from submission_harness.corpus.render_pdf import DisplayOverrides, render_submission_pdf
from submission_harness.corpus.tiers._common import write_ground_truth
from submission_harness.schema import DifficultyTier, GroundTruthRecord, SubmissionExtraction

_NULLABLE = [
    "named_insured",
    "mailing_address",
    "industry_code",
    "business_description",
    "per_occurrence_limit",
    "aggregate_limit",
    "deductible",
    "building_value",
    "contents_value",
    "year_built",
    "construction_type",
]


def generate_incomplete_document(
    *,
    doc_index: int,
    base_seed: int,
    output_dir: Path,
) -> GroundTruthRecord:
    doc_seed = base_seed + 30_000 + doc_index * 1009
    rng = random.Random(doc_seed)
    extraction = sample_extraction(rng)

    n_missing = rng.randint(2, 4)
    # Don't null both dates together with everything — keep policy period usually
    candidates = list(_NULLABLE)
    rng.shuffle(candidates)
    missing = candidates[:n_missing]

    data = extraction.model_dump()
    for key in missing:
        if key == "industry_code":
            data["industry_code"] = None
            data["industry_code_type"] = None
        else:
            data[key] = None
    # Occasionally clear loss history as a "missing" block
    if rng.random() < 0.25:
        data["loss_history"] = []

    extraction = SubmissionExtraction.model_validate(data)

    overrides = DisplayOverrides(
        values={key: "—" for key in missing if key != "industry_code_type"}
    )
    if "industry_code" in missing:
        overrides.values["industry_code"] = "—"

    doc_id = f"incomplete_{doc_index:03d}"
    doc_dir = Path(output_dir) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    render_submission_pdf(extraction, doc_dir / "document.pdf", overrides=overrides)

    record = GroundTruthRecord(
        doc_id=doc_id,
        difficulty_tier=DifficultyTier.INCOMPLETE,
        seed=doc_seed,
        extraction=extraction,
    )
    write_ground_truth(record, doc_dir)
    return record
