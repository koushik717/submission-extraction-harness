"""Corpus generation orchestration."""

from __future__ import annotations

from pathlib import Path

from submission_harness.corpus.tiers.ambiguous import generate_ambiguous_document
from submission_harness.corpus.tiers.clean_digital import generate_clean_digital_document
from submission_harness.corpus.tiers.handwritten import generate_handwritten_document
from submission_harness.corpus.tiers.incomplete import generate_incomplete_document
from submission_harness.corpus.tiers.scanned import generate_scanned_document
from submission_harness.schema import DifficultyTier, GroundTruthRecord

TIER_GENERATORS = {
    DifficultyTier.CLEAN_DIGITAL: generate_clean_digital_document,
    DifficultyTier.SCANNED: generate_scanned_document,
    DifficultyTier.HANDWRITTEN_FIELDS: generate_handwritten_document,
    DifficultyTier.INCOMPLETE: generate_incomplete_document,
    DifficultyTier.AMBIGUOUS: generate_ambiguous_document,
}


def generate_corpus(
    *,
    output_dir: Path,
    base_seed: int = 42,
    per_tier: int = 10,
    tiers: list[DifficultyTier] | None = None,
) -> list[GroundTruthRecord]:
    """Generate synthetic documents for the requested tiers."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    selected = tiers or list(DifficultyTier)
    records: list[GroundTruthRecord] = []

    for tier in selected:
        generator = TIER_GENERATORS.get(tier)
        if generator is None:
            raise NotImplementedError(
                f"Difficulty tier {tier.value!r} is not implemented yet."
            )
        for i in range(per_tier):
            records.append(
                generator(
                    doc_index=i,
                    base_seed=base_seed,
                    output_dir=output_dir,
                )
            )

    manifest = output_dir / "manifest.json"
    manifest.write_text(
        "[\n" + ",\n".join("  " + r.model_dump_json() for r in records) + "\n]\n",
        encoding="utf-8",
    )
    return records
