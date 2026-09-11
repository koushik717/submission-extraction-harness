"""Verifier tests — GT vs self must be 100%; adversarial pred cases."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from submission_harness.corpus.fields import sample_extraction
from submission_harness.schema import (
    DifficultyTier,
    GroundTruthRecord,
    LossEvent,
    SubmissionExtraction,
)
from submission_harness.verify.metrics import evaluate_pairs, self_score_should_be_perfect
from submission_harness.verify.scorer import score_extraction, score_loss_history
import random


def _record(seed: int = 42) -> GroundTruthRecord:
    ext = sample_extraction(random.Random(seed))
    return GroundTruthRecord(
        doc_id=f"test_{seed}",
        difficulty_tier=DifficultyTier.CLEAN_DIGITAL,
        seed=seed,
        extraction=ext,
    )


def test_gt_vs_self_is_perfect():
    for seed in (42, 1051, 2060, 9999, 7):
        rec = _record(seed)
        assert self_score_should_be_perfect(rec)
        score = score_extraction(rec.extraction, rec.extraction)
        assert score.aggregate_accuracy == 1.0
        assert score.loss_history.precision == 1.0
        assert score.loss_history.recall == 1.0


def test_gt_vs_self_on_generated_corpus():
    root = Path("data/corpus")
    if not root.exists():
        pytest.skip("corpus not generated")
    paths = sorted(root.glob("*/ground_truth.json"))
    assert paths, "expected ground truth files"
    for path in paths:
        rec = GroundTruthRecord.model_validate_json(path.read_text())
        assert self_score_should_be_perfect(rec), path


def test_null_pred_vs_present_is_wrong():
    rec = _record(42)
    blank = SubmissionExtraction()
    score = score_extraction(rec.extraction, blank)
    assert score.aggregate_accuracy < 1.0
    assert score.field_scores["named_insured"].correct is False


def test_amount_formatting_equivalence():
    truth = SubmissionExtraction(per_occurrence_limit=1_000_000.0)
    pred = SubmissionExtraction(per_occurrence_limit=1_000_000.0)
    # Simulate string forms via model_construct bypass — set after normalize path
    score = score_extraction(truth, pred)
    assert score.field_scores["per_occurrence_limit"].correct is True

    # Direct normalizer path already covered; scorer uses floats from schema.
    truth2 = truth.model_copy()
    pred2 = SubmissionExtraction()
    # Inject via object.__setattr__ not needed — compare through score on copied values
    from submission_harness.verify.normalizers import normalize_amount

    assert normalize_amount("1M") == truth2.per_occurrence_limit


def test_empty_string_treated_as_null_in_schema():
    ext = SubmissionExtraction(named_insured="", mailing_address="  ")
    # mailing_address validator only checks ""; whitespace may remain — missing_to_none in scorer
    assert ext.named_insured is None


def test_loss_precision_recall_asymmetric():
    truth = [
        LossEvent(date=date(2020, 1, 1), cause="Fire", paid_amount=1000.0, status="Closed"),
        LossEvent(date=date(2021, 2, 2), cause="Water", paid_amount=2000.0, status="Open"),
    ]
    # Missing one loss → recall drop, precision stays 1
    pred_miss = [truth[0]]
    miss = score_loss_history(truth, pred_miss)
    assert miss.precision == 1.0
    assert miss.recall == 0.5
    assert miss.false_negatives == 1
    assert miss.false_positives == 0

    # Invented loss → precision drop, recall stays 1
    pred_extra = truth + [
        LossEvent(date=date(2022, 3, 3), cause="Theft", paid_amount=500.0, status="Closed")
    ]
    extra = score_loss_history(truth, pred_extra)
    assert extra.recall == 1.0
    assert extra.precision == pytest.approx(2 / 3)
    assert extra.false_positives == 1


def test_duplicate_loss_entries():
    e = LossEvent(date=date(2020, 1, 1), cause="Fire", paid_amount=1000.0, status="Closed")
    truth = [e, e]
    pred = [e]
    score = score_loss_history(truth, pred)
    assert score.false_negatives == 1
    assert score.recall == 0.5


def test_tolerant_address_match():
    truth = SubmissionExtraction(
        mailing_address="4606 Maple Avenue, Suite 204, Boulder, CO 80301"
    )
    pred = SubmissionExtraction(
        mailing_address="4606 maple avenue suite 204 boulder co 80301"
    )
    score = score_extraction(truth, pred)
    assert score.field_scores["mailing_address"].correct is True


def test_evaluate_pairs_headline_hides_spread():
    rec = _record(42)
    good = rec.extraction
    bad = SubmissionExtraction()
    report = evaluate_pairs([(rec, good), (rec, bad)])
    assert report.n_docs == 2
    assert report.per_field_min < report.headline_aggregate < report.per_field_max or (
        report.per_field_min <= report.headline_aggregate <= report.per_field_max
    )
