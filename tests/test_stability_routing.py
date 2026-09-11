"""Stability + routing + report smoke tests."""

from __future__ import annotations

from pathlib import Path

from submission_harness.corpus.generator import generate_corpus
from submission_harness.routing.policy import (
    build_routing_policy,
    classify_field,
    format_routing_table,
    write_routing_policy,
)
from submission_harness.schema import DifficultyTier, SubmissionExtraction
from submission_harness.stability.flip_rate import (
    majority_vote_extraction,
    single_vs_majority_accuracy,
)
from submission_harness.stability.runner import run_stability
from submission_harness.verify.metrics import evaluate_pairs
from submission_harness.report.write_report import write_report


def test_classify_routing_thresholds():
    thresholds = {
        "auto_post": {"min_accuracy": 0.95, "max_flip_rate": 0.05},
        "always_human": {"max_accuracy": 0.80, "min_flip_rate": 0.20},
    }
    assert classify_field(accuracy=0.99, flip_rate=0.01, thresholds=thresholds) == "auto_post"
    assert classify_field(accuracy=0.70, flip_rate=0.30, thresholds=thresholds) == "always_human"
    assert classify_field(accuracy=0.90, flip_rate=0.10, thresholds=thresholds) == "review"


def test_majority_vote_helps_when_runs_disagree():
    truth = SubmissionExtraction(year_built=1984, named_insured="Acme LLC")
    runs = [
        SubmissionExtraction(year_built=1984, named_insured="Acme LLC"),
        SubmissionExtraction(year_built=1985, named_insured="Acme LLC"),
        SubmissionExtraction(year_built=1984, named_insured="Acme"),
    ]
    maj = majority_vote_extraction(runs)
    assert maj.year_built == 1984
    single, majority = single_vs_majority_accuracy(truth, runs)
    assert majority >= single


def test_stability_runner_checkpoint_resume(tmp_path: Path):
    corpus = tmp_path / "corpus"
    generate_corpus(
        output_dir=corpus,
        base_seed=3,
        per_tier=1,
        tiers=[DifficultyTier.CLEAN_DIGITAL, DifficultyTier.AMBIGUOUS],
    )
    # Tiny config
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        """
seed: 3
corpus_size_per_tier: 1
corpus_output_dir: unused
spend_cap_usd: 5.0
rate_limit_rpm: 1000
default_provider: local
stability:
  n_runs: 2
  conditions: [temp_0, temp_default]
providers:
  openai: {model: gpt-4o-mini, default_temperature: 1.0}
  anthropic: {model: claude-3-5-haiku-latest, default_temperature: 1.0}
text_match:
  token_overlap_threshold: 0.8
"""
    )
    run_dir = tmp_path / "run1"
    report = run_stability(
        corpus_dir=corpus,
        run_dir=run_dir,
        config_path=cfg,
        provider="local",
        n_runs=2,
    )
    assert "temp_0" in report.by_condition
    assert "temp_default" in report.by_condition
    assert report.by_condition["temp_0"].n_docs == 2
    # Resume should skip completed keys
    n_before = len((run_dir / "results.jsonl").read_text().splitlines())
    report2 = run_stability(
        corpus_dir=corpus,
        run_dir=run_dir,
        config_path=cfg,
        provider="local",
        n_runs=2,
    )
    n_after = len((run_dir / "results.jsonl").read_text().splitlines())
    assert n_after == n_before
    assert report2.by_condition["temp_0"].mean_single_accuracy >= 0.9


def test_report_and_routing_artifacts(tmp_path: Path):
    corpus = tmp_path / "corpus"
    records = generate_corpus(
        output_dir=corpus,
        base_seed=5,
        per_tier=1,
        tiers=[DifficultyTier.CLEAN_DIGITAL],
    )
    pairs = [(records[0], records[0].extraction)]
    evaluation = evaluate_pairs(pairs)

    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        """
seed: 5
spend_cap_usd: 5.0
rate_limit_rpm: 1000
default_provider: local
stability:
  n_runs: 2
  conditions: [temp_0, temp_default]
providers:
  openai: {model: gpt-4o-mini, default_temperature: 1.0}
  anthropic: {model: claude-3-5-haiku-latest, default_temperature: 1.0}
text_match: {token_overlap_threshold: 0.8}
"""
    )
    stab = run_stability(
        corpus_dir=corpus,
        run_dir=tmp_path / "stab",
        config_path=cfg,
        provider="local",
        n_runs=2,
    )
    # thresholds file
    thr = tmp_path / "routing.yaml"
    thr.write_text(
        """
auto_post: {min_accuracy: 0.95, max_flip_rate: 0.05}
always_human: {max_accuracy: 0.80, min_flip_rate: 0.20}
flip_rate_source: max_of_conditions
"""
    )
    policy = build_routing_policy(evaluation, stab, thresholds_path=thr)
    assert policy.fields
    table = format_routing_table(policy)
    assert "auto_post" in table or "review" in table or "always_human" in table
    out = tmp_path / "report"
    write_routing_policy(policy, out / "routing_policy.json")
    report_path = write_report(
        evaluation=evaluation,
        stability=stab,
        policy=policy,
        output_dir=out,
        report_path=tmp_path / "REPORT.md",
    )
    assert report_path.exists()
    assert (out / "charts" / "per_field_accuracy.png").exists()
    assert (out / "routing_policy.json").exists()
