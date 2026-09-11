"""Single rate-limited, cost-governed LLM client for all providers."""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv

from submission_harness.client.cost_guard import CostGuard, SpendCapExceeded
from submission_harness.client.rate_limit import RateLimiter


# Approximate USD per 1M tokens (input, output) — conservative defaults.
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-3-5-haiku-latest": (0.80, 4.00),
    "claude-3-5-sonnet-latest": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "local-pdf-parser": (0.0, 0.0),
}


class ProviderBackend(Protocol):
    name: str

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None,
        model: str,
    ) -> tuple[str, dict[str, int]]:
        """Return (text, usage_dict with prompt_tokens/completion_tokens)."""


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    temperature: float | None
    cost_usd: float
    usage: dict[str, int]


class LLMClient:
    """All LLM traffic must go through this client."""

    def __init__(
        self,
        *,
        backends: dict[str, ProviderBackend],
        cost_guard: CostGuard,
        rate_limiter: RateLimiter,
        provider_models: dict[str, str],
    ) -> None:
        self.backends = backends
        self.cost_guard = cost_guard
        self.rate_limiter = rate_limiter
        self.provider_models = provider_models

    def complete(
        self,
        *,
        provider: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        self.cost_guard.ensure_under_cap()
        if provider not in self.backends:
            raise KeyError(f"Unknown provider {provider!r}. Have: {list(self.backends)}")
        backend = self.backends[provider]
        model_name = model or self.provider_models.get(provider)
        if not model_name:
            raise ValueError(f"No model configured for provider {provider}")

        if provider != "local":
            self.rate_limiter.wait()
        text, usage = backend.complete(
            messages=messages, temperature=temperature, model=model_name
        )
        cost = estimate_cost(model_name, usage)
        self.cost_guard.charge(cost)
        return LLMResponse(
            text=text,
            provider=provider,
            model=model_name,
            temperature=temperature,
            cost_usd=cost,
            usage=usage,
        )


def estimate_cost(model: str, usage: dict[str, int]) -> float:
    inp, out = _PRICE_PER_MTOK.get(model, (1.0, 5.0))
    pt = usage.get("prompt_tokens", 0)
    ct = usage.get("completion_tokens", 0)
    return (pt * inp + ct * out) / 1_000_000.0


def build_default_client(
    *,
    spend_cap_usd: float = 5.0,
    rate_limit_rpm: int = 30,
    provider_models: dict[str, str] | None = None,
) -> LLMClient:
    load_dotenv()
    from submission_harness.extract.providers.anthropic_provider import AnthropicBackend
    from submission_harness.extract.providers.local_parser import LocalParserBackend
    from submission_harness.extract.providers.openai_provider import OpenAIBackend

    models = provider_models or {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-haiku-latest",
        "local": "local-pdf-parser",
    }
    backends: dict[str, ProviderBackend] = {"local": LocalParserBackend()}
    if os.getenv("OPENAI_API_KEY"):
        backends["openai"] = OpenAIBackend()
    if os.getenv("ANTHROPIC_API_KEY"):
        backends["anthropic"] = AnthropicBackend()

    return LLMClient(
        backends=backends,
        cost_guard=CostGuard(cap_usd=spend_cap_usd),
        rate_limiter=RateLimiter(rpm=rate_limit_rpm),
        provider_models=models,
    )


def pdf_to_data_url(path: Path) -> str:
    data = Path(path).read_bytes()
    b64 = base64.standard_b64encode(data).decode("ascii")
    return f"data:application/pdf;base64,{b64}"


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse strict JSON from model output; tolerate optional markdown fences."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    return json.loads(cleaned)


__all__ = [
    "LLMClient",
    "LLMResponse",
    "SpendCapExceeded",
    "build_default_client",
    "estimate_cost",
    "extract_json_object",
    "pdf_to_data_url",
]
