"""Extraction agent + local parser integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from submission_harness.client.cost_guard import CostGuard, SpendCapExceeded
from submission_harness.client.llm_client import LLMClient, extract_json_object
from submission_harness.client.rate_limit import RateLimiter
from submission_harness.corpus.generator import generate_corpus
from submission_harness.extract.agent import ExtractionAgent
from submission_harness.extract.providers.local_parser import LocalParserBackend
from submission_harness.schema import DifficultyTier
from submission_harness.verify.scorer import score_extraction


@pytest.fixture(scope="module")
def tiny_corpus(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("corpus")
    generate_corpus(
        output_dir=root,
        base_seed=42,
        per_tier=1,
        tiers=[
            DifficultyTier.CLEAN_DIGITAL,
            DifficultyTier.AMBIGUOUS,
            DifficultyTier.INCOMPLETE,
            DifficultyTier.SCANNED,
        ],
    )
    return root


def _local_agent(cap: float = 5.0) -> tuple[ExtractionAgent, LLMClient]:
    client = LLMClient(
        backends={"local": LocalParserBackend()},
        cost_guard=CostGuard(cap_usd=cap),
        rate_limiter=RateLimiter(rpm=1000),
        provider_models={"local": "local-pdf-parser"},
    )
    return ExtractionAgent(client, default_provider="local"), client


def test_local_extract_clean_near_perfect(tiny_corpus: Path):
    agent, _ = _local_agent()
    from submission_harness.schema import GroundTruthRecord

    gt = GroundTruthRecord.model_validate_json(
        (tiny_corpus / "clean_digital_000" / "ground_truth.json").read_text()
    )
    pred = agent.extract(
        tiny_corpus / "clean_digital_000" / "document.pdf", temperature=0.0
    )
    score = score_extraction(gt.extraction, pred)
    assert score.aggregate_accuracy == 1.0


def test_local_extract_ambiguous_handles_1m_2m(tiny_corpus: Path):
    agent, _ = _local_agent()
    from submission_harness.schema import GroundTruthRecord

    gt = GroundTruthRecord.model_validate_json(
        (tiny_corpus / "ambiguous_000" / "ground_truth.json").read_text()
    )
    pred = agent.extract(
        tiny_corpus / "ambiguous_000" / "document.pdf", temperature=0.0
    )
    score = score_extraction(gt.extraction, pred)
    assert score.field_scores["per_occurrence_limit"].correct
    assert score.field_scores["aggregate_limit"].correct
    assert score.aggregate_accuracy == 1.0


def test_scanned_has_little_text_signal(tiny_corpus: Path):
    agent, _ = _local_agent()
    from submission_harness.schema import GroundTruthRecord

    gt = GroundTruthRecord.model_validate_json(
        (tiny_corpus / "scanned_000" / "ground_truth.json").read_text()
    )
    pred = agent.extract(
        tiny_corpus / "scanned_000" / "document.pdf", temperature=0.0
    )
    score = score_extraction(gt.extraction, pred)
    assert score.aggregate_accuracy < 0.3


def test_temp0_stable_across_runs(tiny_corpus: Path):
    agent, _ = _local_agent()
    pdf = tiny_corpus / "clean_digital_000" / "document.pdf"
    a = agent.extract(pdf, temperature=0.0, run_id="0")
    b = agent.extract(pdf, temperature=0.0, run_id="1")
    assert a.model_dump() == b.model_dump()


def test_spend_cap_aborts_during_extract(tiny_corpus: Path):
    class _Expensive:
        name = "mock"

        def complete(self, *, messages, temperature, model):
            return (
                '{"named_insured": null, "loss_history": []}',
                {"prompt_tokens": 500_000, "completion_tokens": 500_000},
            )

    client = LLMClient(
        backends={"mock": _Expensive()},
        cost_guard=CostGuard(cap_usd=0.01),
        rate_limiter=RateLimiter(rpm=1000),
        provider_models={"mock": "gpt-4o"},
    )
    agent = ExtractionAgent(client, default_provider="mock")
    with pytest.raises(SpendCapExceeded):
        agent.extract(tiny_corpus / "clean_digital_000" / "document.pdf")


def test_extract_json_object_strips_fences():
    data = extract_json_object('```json\n{"named_insured": null, "loss_history": []}\n```')
    assert data["named_insured"] is None
    assert data["loss_history"] == []
