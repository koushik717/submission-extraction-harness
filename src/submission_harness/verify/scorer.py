"""Field-level scoring against ground truth.

Exact-match fields (after normalization): identifiers, codes, dates, amounts,
year_built, construction_type, industry_code_type.

Tolerant fields (token overlap ≥ threshold): business_description, mailing_address,
named_insured.

Loss history: set comparison on (date, cause, amount) — precision and recall
reported separately.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from submission_harness.schema import LossEvent, SubmissionExtraction
from submission_harness.verify.normalizers import (
    AmbiguousDateError,
    normalize_amount,
    normalize_code,
    normalize_date,
    normalize_identifier,
    normalize_int,
    normalize_text_tokens,
    token_overlap,
)

EXACT_FIELDS: tuple[str, ...] = (
    "effective_date",
    "expiration_date",
    "industry_code",
    "industry_code_type",
    "per_occurrence_limit",
    "aggregate_limit",
    "deductible",
    "building_value",
    "contents_value",
    "year_built",
    "construction_type",
)

TEXT_FIELDS: tuple[str, ...] = (
    "named_insured",
    "mailing_address",
    "business_description",
)

ALL_SCALAR_FIELDS: tuple[str, ...] = EXACT_FIELDS + TEXT_FIELDS


@dataclass
class FieldScore:
    field: str
    correct: bool
    detail: str = ""


@dataclass
class LossHistoryScore:
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    exact_set_match: bool


@dataclass
class ExtractionScore:
    field_scores: dict[str, FieldScore]
    loss_history: LossHistoryScore
    aggregate_accuracy: float
    scalar_accuracy: float

    @property
    def per_field_correct(self) -> dict[str, bool]:
        out = {k: v.correct for k, v in self.field_scores.items()}
        out["loss_history"] = self.loss_history.exact_set_match
        return out


def _norm_exact(field_name: str, value: Any) -> Any:
    if field_name in {"effective_date", "expiration_date"}:
        try:
            return normalize_date(value)
        except AmbiguousDateError:
            return ("__ambiguous__", str(value))
    if field_name == "industry_code":
        return normalize_code(value)
    if field_name == "industry_code_type":
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        return str(value).strip().upper()
    if field_name in {
        "per_occurrence_limit",
        "aggregate_limit",
        "deductible",
        "building_value",
        "contents_value",
    }:
        return normalize_amount(value)
    if field_name == "year_built":
        return normalize_int(value)
    if field_name == "construction_type":
        tokens = normalize_text_tokens(value)
        return " ".join(tokens) if tokens else None
    return normalize_identifier(value)


def _loss_key(event: LossEvent) -> tuple[str | None, str | None, float | None]:
    try:
        d = normalize_date(event.date)
    except AmbiguousDateError:
        d = f"ambiguous:{event.date}"
    cause_tokens = normalize_text_tokens(event.cause)
    cause = " ".join(cause_tokens) if cause_tokens else None
    amount = normalize_amount(event.paid_amount)
    return (d, cause, amount)


def score_loss_history(
    truth: Iterable[LossEvent],
    pred: Iterable[LossEvent],
) -> LossHistoryScore:
    truth_keys = [_loss_key(e) for e in truth]
    pred_keys = [_loss_key(e) for e in pred]
    tc, pc = Counter(truth_keys), Counter(pred_keys)
    tp = sum((tc & pc).values())
    fp = sum((pc - tc).values())
    fn = sum((tc - pc).values())
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 1.0
    )
    return LossHistoryScore(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        exact_set_match=(fp == 0 and fn == 0),
    )


def score_extraction(
    truth: SubmissionExtraction,
    pred: SubmissionExtraction,
    *,
    text_threshold: float = 0.8,
) -> ExtractionScore:
    field_scores: dict[str, FieldScore] = {}

    for name in EXACT_FIELDS:
        tv = _norm_exact(name, getattr(truth, name))
        pv = _norm_exact(name, getattr(pred, name))
        field_scores[name] = FieldScore(
            field=name,
            correct=tv == pv,
            detail=f"truth={tv!r} pred={pv!r}",
        )

    for name in TEXT_FIELDS:
        tv = getattr(truth, name)
        pv = getattr(pred, name)
        overlap = token_overlap(tv, pv)
        field_scores[name] = FieldScore(
            field=name,
            correct=overlap >= text_threshold,
            detail=f"overlap={overlap:.3f} threshold={text_threshold}",
        )

    loss = score_loss_history(truth.loss_history, pred.loss_history)
    scalar_vals = [fs.correct for fs in field_scores.values()]
    scalar_accuracy = sum(scalar_vals) / len(scalar_vals) if scalar_vals else 1.0
    all_vals = scalar_vals + [loss.exact_set_match]
    aggregate = sum(all_vals) / len(all_vals)

    return ExtractionScore(
        field_scores=field_scores,
        loss_history=loss,
        aggregate_accuracy=aggregate,
        scalar_accuracy=scalar_accuracy,
    )
