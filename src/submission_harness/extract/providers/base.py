"""Provider protocol."""

from __future__ import annotations

from typing import Any, Protocol


class ProviderBackend(Protocol):
    name: str

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None,
        model: str,
    ) -> tuple[str, dict[str, int]]: ...
