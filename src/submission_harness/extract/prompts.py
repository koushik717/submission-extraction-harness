"""Extraction prompts — strict JSON, explicit nulls, no guessing."""

from __future__ import annotations

SYSTEM_PROMPT = """\
You extract structured fields from a commercial insurance submission document.
Return ONLY a single JSON object matching this schema (no markdown, no commentary):

{
  "named_insured": string | null,
  "mailing_address": string | null,
  "effective_date": "YYYY-MM-DD" | null,
  "expiration_date": "YYYY-MM-DD" | null,
  "industry_code": string | null,
  "industry_code_type": "SIC" | "NAICS" | null,
  "business_description": string | null,
  "per_occurrence_limit": number | null,
  "aggregate_limit": number | null,
  "deductible": number | null,
  "building_value": number | null,
  "contents_value": number | null,
  "year_built": number | null,
  "construction_type": string | null,
  "loss_history": [
    {
      "date": "YYYY-MM-DD" | null,
      "cause": string | null,
      "paid_amount": number | null,
      "status": string | null
    }
  ]
}

Rules:
- Missing fields MUST be JSON null (never empty string, never invent values).
- Amounts are plain numbers in USD (e.g. 1000000 not "$1M").
- Dates are ISO YYYY-MM-DD.
- If limits appear as "1M/2M", map to per_occurrence_limit=1000000 and aggregate_limit=2000000.
- loss_history is [] when none reported.
"""


def user_prompt_for_text(document_text: str) -> str:
    return (
        "Extract fields from the following submission document text.\n\n"
        f"----- BEGIN DOCUMENT -----\n{document_text}\n----- END DOCUMENT -----\n"
    )
