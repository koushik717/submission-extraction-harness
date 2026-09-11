"""Flip-rate and majority-vote helpers for stability analysis."""

from __future__ import annotations

from collections import Counter
from typing import Any, Hashable

from submission_harness.schema import LossEvent, SubmissionExtraction
from submission_harness.verify.normalizers import (
    AmbiguousDateError,
    normalize_amount,
    normalize_code,
    normalize_date,
    normalize_int,
    normalize_text_tokens,
)
from submission_harness.verify.scorer import ALL_SCALAR_FIELDS, score_extraction


def canonical_field_value(extraction: SubmissionExtraction, field: str) -> Hashable:
    value = getattr(extraction, field)
    if field in {"effective_date", "expiration_date"}:
        try:
            return normalize_date(value)
        except AmbiguousDateError as exc:
            return ("ambiguous", tuple(str(c) for c in exc.candidates))
    if field == "industry_code":
        return normalize_code(value)
    if field == "industry_code_type":
        return None if value is None else str(value).upper()
    if field in {
        "per_occurrence_limit",
        "aggregate_limit",
        "deductible",
        "building_value",
        "contents_value",
    }:
        return normalize_amount(value)
    if field == "year_built":
        return normalize_int(value)
    if field in {"named_insured", "mailing_address", "business_description", "construction_type"}:
        tokens = normalize_text_tokens(value)
        return tuple(tokens) if tokens else None
    return value


def canonical_loss_history(extraction: SubmissionExtraction) -> Hashable:
    keys = []
    for event in extraction.loss_history:
        try:
            d = normalize_date(event.date)
        except AmbiguousDateError:
            d = str(event.date)
        cause = tuple(normalize_text_tokens(event.cause) or [])
        amount = normalize_amount(event.paid_amount)
        keys.append((d, cause, amount))
    return tuple(sorted(keys))


def values_agree(values: list[Hashable]) -> bool:
    if not values:
        return True
    return len(set(values)) == 1


def majority_value(values: list[Hashable]) -> Hashable:
    if not values:
        return None
    counts = Counter(values)
    return counts.most_common(1)[0][0]


def majority_vote_extraction(runs: list[SubmissionExtraction]) -> SubmissionExtraction:
    """Build a majority-vote extraction across runs (field-wise)."""
    if not runs:
        return SubmissionExtraction()
    data: dict[str, Any] = {}
    for field in ALL_SCALAR_FIELDS:
        cans = [canonical_field_value(r, field) for r in runs]
        maj = majority_value(cans)
        # Map canonical back approximately using first run that matches
        chosen = None
        for r in runs:
            if canonical_field_value(r, field) == maj:
                chosen = getattr(r, field)
                break
        data[field] = chosen

    loss_cans = [canonical_loss_history(r) for r in runs]
    maj_loss = majority_value(loss_cans)
    losses: list[LossEvent] = []
    for r in runs:
        if canonical_loss_history(r) == maj_loss:
            losses = list(r.loss_history)
            break
    data["loss_history"] = [e.model_dump() for e in losses]
    return SubmissionExtraction.model_validate(data)


def flip_rate_for_field(doc_run_values: dict[str, list[Hashable]]) -> float:
    """Fraction of documents where the N runs did not all agree."""
    if not doc_run_values:
        return 0.0
    flips = sum(1 for vals in doc_run_values.values() if not values_agree(vals))
    return flips / len(doc_run_values)


def single_vs_majority_accuracy(
    truth: SubmissionExtraction,
    runs: list[SubmissionExtraction],
    *,
    text_threshold: float = 0.8,
) -> tuple[float, float]:
    """Return (mean single-run aggregate accuracy, majority-vote accuracy)."""
    if not runs:
        return 0.0, 0.0
    singles = [
        score_extraction(truth, r, text_threshold=text_threshold).aggregate_accuracy
        for r in runs
    ]
    maj = majority_vote_extraction(runs)
    maj_acc = score_extraction(truth, maj, text_threshold=text_threshold).aggregate_accuracy
    return sum(singles) / len(singles), maj_acc
