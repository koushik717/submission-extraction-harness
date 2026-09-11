"""Extraction agent: document → validated SubmissionExtraction JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from submission_harness.client.llm_client import LLMClient, extract_json_object
from submission_harness.extract.prompts import SYSTEM_PROMPT, user_prompt_for_text
from submission_harness.extract.providers.local_parser import pdftotext
from submission_harness.schema import SubmissionExtraction


class ExtractionAgent:
    def __init__(self, client: LLMClient, *, default_provider: str = "local") -> None:
        self.client = client
        self.default_provider = default_provider

    def extract(
        self,
        pdf_path: Path,
        *,
        provider: str | None = None,
        temperature: float | None = None,
        run_id: str = "0",
    ) -> SubmissionExtraction:
        provider = provider or self.default_provider
        pdf_path = Path(pdf_path)

        if provider == "local":
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"LOCAL_PDF:{pdf_path}\nRUN:{run_id}\n",
                },
            ]
        else:
            text = pdftotext(pdf_path)
            # If no text layer (scanned), tell the model explicitly
            if not text.strip():
                text = (
                    "[Document appears to be a scanned/image PDF with no extractable "
                    "text layer. Return all fields as null and loss_history as [].]"
                )
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt_for_text(text)},
            ]

        resp = self.client.complete(
            provider=provider, messages=messages, temperature=temperature
        )
        data = extract_json_object(resp.text)
        data = _coerce_nulls(data)
        return SubmissionExtraction.model_validate(data)


def _coerce_nulls(data: dict[str, Any]) -> dict[str, Any]:
    """Empty strings → null; ensure loss_history is a list."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        if value == "":
            out[key] = None
        else:
            out[key] = value
    if "loss_history" not in out or out["loss_history"] is None:
        out["loss_history"] = []
    cleaned_losses = []
    for event in out["loss_history"]:
        if not isinstance(event, dict):
            continue
        cleaned_losses.append(
            {k: (None if v == "" else v) for k, v in event.items()}
        )
    out["loss_history"] = cleaned_losses
    return out
