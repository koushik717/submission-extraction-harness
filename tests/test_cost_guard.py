"""Cost guard abort tests."""

from __future__ import annotations

import pytest

from submission_harness.client.cost_guard import CostGuard, SpendCapExceeded
from submission_harness.client.llm_client import LLMClient, estimate_cost
from submission_harness.client.rate_limit import RateLimiter


class _ChargingBackend:
    name = "mock"

    def complete(self, *, messages, temperature, model):
        return ('{"named_insured": null, "loss_history": []}', {"prompt_tokens": 100000, "completion_tokens": 100000})


def test_spend_cap_aborts():
    guard = CostGuard(cap_usd=0.05)
    client = LLMClient(
        backends={"mock": _ChargingBackend()},
        cost_guard=guard,
        rate_limiter=RateLimiter(rpm=1000),
        provider_models={"mock": "gpt-4o"},
    )
    # gpt-4o pricing: 2.5/10 per MTok → 100k+100k = 0.25+1.0 = 1.25 > 0.05
    with pytest.raises(SpendCapExceeded):
        client.complete(
            provider="mock",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0,
        )


def test_estimate_cost_positive():
    assert estimate_cost("gpt-4o-mini", {"prompt_tokens": 1_000_000, "completion_tokens": 0}) == pytest.approx(0.15)
