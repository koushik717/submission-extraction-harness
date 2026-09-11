"""Ambiguous tier: date dual-formats, 1M/2M limits, mixed currency notation."""

from __future__ import annotations

import random
from pathlib import Path

from submission_harness.corpus.fields import sample_extraction
from submission_harness.corpus.render_pdf import DisplayOverrides, render_submission_pdf
from submission_harness.corpus.tiers._common import write_ground_truth
from submission_harness.schema import DifficultyTier, GroundTruthRecord


def _fmt_m(value: float) -> str:
    if value >= 1_000_000 and value % 1_000_000 == 0:
        return f"{int(value // 1_000_000)}M"
    if value >= 1_000 and value % 1_000 == 0:
        return f"{int(value // 1_000)}K"
    return f"{value:.0f}"


def generate_ambiguous_document(
    *,
    doc_index: int,
    base_seed: int,
    output_dir: Path,
) -> GroundTruthRecord:
    doc_seed = base_seed + 40_000 + doc_index * 1009
    rng = random.Random(doc_seed)
    extraction = sample_extraction(rng)

    # Dual date display: US and EU forms side by side when day <= 12 (ambiguous)
    def dual(d) -> str:
        if d is None:
            return "—"
        us = d.strftime("%m/%d/%y")
        eu = d.strftime("%d/%m/%y")
        return f"{us} ({eu})"

    per = extraction.per_occurrence_limit or 1_000_000.0
    agg = extraction.aggregate_limit or 2_000_000.0
    compound = f"{_fmt_m(per)}/{_fmt_m(agg)}"

    # Mix currency styles
    building = extraction.building_value or 0
    contents = extraction.contents_value or 0
    building_disp = f"{building:,.0f}"  # no dollar sign
    contents_disp = f"${contents:,.0f}"

    loss_rows = None
    if extraction.loss_history:
        loss_rows = []
        for i, event in enumerate(extraction.loss_history):
            amt = event.paid_amount or 0
            amt_s = f"{_fmt_m(amt)}" if i % 2 == 0 else f"${amt:,.0f}"
            loss_rows.append(
                (
                    dual(event.date) if event.date else "—",
                    event.cause or "—",
                    amt_s,
                    event.status or "—",
                )
            )

    overrides = DisplayOverrides(
        values={
            "effective_date": dual(extraction.effective_date),
            "expiration_date": dual(extraction.expiration_date),
            "limits_compound": compound,
            "deductible": (
                f"{extraction.deductible:,.0f}"
                if extraction.deductible is not None
                else "—"
            ),
            "building_value": building_disp,
            "contents_value": contents_disp,
        },
        loss_rows=loss_rows,
    )

    doc_id = f"ambiguous_{doc_index:03d}"
    doc_dir = Path(output_dir) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    render_submission_pdf(extraction, doc_dir / "document.pdf", overrides=overrides)

    record = GroundTruthRecord(
        doc_id=doc_id,
        difficulty_tier=DifficultyTier.AMBIGUOUS,
        seed=doc_seed,
        extraction=extraction,
    )
    write_ground_truth(record, doc_dir)
    return record
