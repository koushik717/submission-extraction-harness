"""Rollups: per-field accuracy, by difficulty tier, headline aggregate."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from submission_harness.schema import DifficultyTier, GroundTruthRecord, SubmissionExtraction
from submission_harness.verify.scorer import ExtractionScore, score_extraction


@dataclass
class FieldAccuracy:
    field: str
    correct: int
    total: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass
class TierAccuracy:
    tier: str
    aggregate_accuracy: float
    n_docs: int
    per_field: dict[str, FieldAccuracy]


@dataclass
class EvaluationReport:
    per_field: dict[str, FieldAccuracy]
    by_tier: dict[str, TierAccuracy]
    headline_aggregate: float
    n_docs: int
    per_field_min: float
    per_field_max: float
    scores: list[ExtractionScore] = field(default_factory=list)


def evaluate_pairs(
    pairs: Iterable[tuple[GroundTruthRecord, SubmissionExtraction]],
    *,
    text_threshold: float = 0.8,
) -> EvaluationReport:
    per_field_counts: dict[str, list[bool]] = defaultdict(list)
    tier_field: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    tier_agg: dict[str, list[float]] = defaultdict(list)
    scores: list[ExtractionScore] = []
    all_agg: list[float] = []

    n = 0
    for record, pred in pairs:
        score = score_extraction(
            record.extraction, pred, text_threshold=text_threshold
        )
        scores.append(score)
        n += 1
        all_agg.append(score.aggregate_accuracy)
        tier = (
            record.difficulty_tier.value
            if isinstance(record.difficulty_tier, DifficultyTier)
            else str(record.difficulty_tier)
        )
        tier_agg[tier].append(score.aggregate_accuracy)

        for name, correct in score.per_field_correct.items():
            per_field_counts[name].append(correct)
            tier_field[tier][name].append(correct)

    per_field = {
        name: FieldAccuracy(name, sum(vals), len(vals))
        for name, vals in sorted(per_field_counts.items())
    }
    by_tier: dict[str, TierAccuracy] = {}
    for tier, fields in sorted(tier_field.items()):
        by_tier[tier] = TierAccuracy(
            tier=tier,
            aggregate_accuracy=sum(tier_agg[tier]) / len(tier_agg[tier]),
            n_docs=len(tier_agg[tier]),
            per_field={
                name: FieldAccuracy(name, sum(vals), len(vals))
                for name, vals in sorted(fields.items())
            },
        )

    accuracies = [fa.accuracy for fa in per_field.values()]
    return EvaluationReport(
        per_field=per_field,
        by_tier=by_tier,
        headline_aggregate=sum(all_agg) / len(all_agg) if all_agg else 0.0,
        n_docs=n,
        per_field_min=min(accuracies) if accuracies else 0.0,
        per_field_max=max(accuracies) if accuracies else 0.0,
        scores=scores,
    )


def self_score_should_be_perfect(
    record: GroundTruthRecord, text_threshold: float = 0.8
) -> bool:
    """GT compared with itself must be 100% — verifier sanity check."""
    score = score_extraction(
        record.extraction, record.extraction, text_threshold=text_threshold
    )
    return score.aggregate_accuracy == 1.0 and all(score.per_field_correct.values())
