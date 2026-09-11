"""Local PDF-text extraction backend (offline / no API key).

Parses ``pdftotext`` output with deterministic regexes. When temperature is
null or 0, results are stable. When temperature > 0, a seeded perturbation
may flip a small set of ambiguous-prone fields so stability analysis has a
non-trivial control — this approximates sampling noise without an LLM.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from submission_harness.verify.normalizers import normalize_amount, split_compound_limits


class LocalParserBackend:
    name = "local"

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None,
        model: str,
    ) -> tuple[str, dict[str, int]]:
        pdf_path = None
        raw_text = ""
        run_id = "0"
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str) and content.startswith("LOCAL_PDF:"):
                # Format: LOCAL_PDF:<path>\nRUN:<n>\n
                lines = content.splitlines()
                pdf_path = lines[0].removeprefix("LOCAL_PDF:").strip()
                for line in lines[1:]:
                    if line.startswith("RUN:"):
                        run_id = line.removeprefix("RUN:").strip()
            elif isinstance(content, str) and "BEGIN DOCUMENT" in content:
                raw_text = content

        if pdf_path:
            raw_text = pdftotext(Path(pdf_path))

        parsed = parse_submission_text(raw_text)
        if temperature is not None and temperature > 0:
            parsed = perturb(parsed, seed_key=f"{pdf_path}:{run_id}:{temperature}")

        text = json.dumps(parsed)
        # Fake token usage for cost accounting (local is free → 0 charged via price table miss)
        usage = {
            "prompt_tokens": max(len(raw_text) // 4, 1),
            "completion_tokens": max(len(text) // 4, 1),
        }
        return text, usage


def pdftotext(path: Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""


def _field(text: str, label: str) -> str | None:
    # Prefer a label that appears as its own left-column token.
    patterns = [
        rf"(?m)^\s*{re.escape(label)}\s{{2,}}(.+?)\s{{2,}}\S",
        rf"(?m)^\s*{re.escape(label)}\s{{2,}}(.+)$",
        rf"{re.escape(label)}\s*[:|]?\s*(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            val = re.split(r"\s{2,}|\n", val)[0].strip()
            if val in {"—", "-", "None reported", ""}:
                return None
            return val
    return None


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    # Dual-written "MM/DD/YY (DD/MM/YY)" — take the first form only
    if "(" in raw:
        raw = raw.split("(", 1)[0].strip()
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _money(raw: str | None) -> float | None:
    if not raw:
        return None
    if "/" in raw and re.search(r"\d", raw):
        left, _right = split_compound_limits(raw)
        return left
    return normalize_amount(raw)


def parse_submission_text(text: str) -> dict[str, Any]:
    named = _field(text, "Named Insured")
    address = _field(text, "Mailing Address")
    code_type = None
    code = None
    m = re.search(r"\b(SIC|NAICS)\s+Code\b\s*[:|]?\s*([A-Za-z0-9\-]+)", text, re.I)
    if m:
        code_type = m.group(1).upper()
        code = re.sub(r"\D", "", m.group(2)) or None
    desc = _field(text, "Business Description")

    eff = _parse_date(_field(text, "Effective Date"))
    exp = _parse_date(_field(text, "Expiration Date"))

    per_occ = _money(_field(text, "Per-Occurrence"))
    agg = _money(_field(text, "Aggregate"))
    limits_line = _field(text, "Limits")
    if limits_line:
        left, right = split_compound_limits(limits_line)
        if per_occ is None:
            per_occ = left
        if agg is None:
            agg = right

    deductible = _money(_field(text, "Deductible"))
    building = _money(_field(text, "Building Value"))
    contents = _money(_field(text, "Contents Value"))
    year_raw = _field(text, "Year Built")
    year_built = None
    if year_raw and re.search(r"\d{4}", year_raw):
        year_built = int(re.search(r"\d{4}", year_raw).group(0))
    construction = _field(text, "Construction Type")

    losses: list[dict[str, Any]] = []
    if not re.search(r"None reported", text, re.I):
        # Dual dates: 09/15/20 (15/09/20)  Cause...
        row_re = re.compile(
            r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4}(?:\s*\(\d{1,2}/\d{1,2}/\d{2,4}\))?)"
            r"\s+(?P<cause>.+?)\s+"
            r"(?P<amt>\$?[\d,]+(?:\.\d+)?|\d+\.?\d*[MmKk]?)"
            r"\s+(?P<status>Closed|Open|Subrogation|Denied)",
            re.MULTILINE,
        )
        for m in row_re.finditer(text):
            losses.append(
                {
                    "date": _parse_date(m.group("date")),
                    "cause": m.group("cause").strip(),
                    "paid_amount": normalize_amount(m.group("amt")),
                    "status": m.group("status"),
                }
            )

    return {
        "named_insured": named,
        "mailing_address": address,
        "effective_date": eff,
        "expiration_date": exp,
        "industry_code": code,
        "industry_code_type": code_type,
        "business_description": desc,
        "per_occurrence_limit": per_occ,
        "aggregate_limit": agg,
        "deductible": deductible,
        "building_value": building,
        "contents_value": contents,
        "year_built": year_built,
        "construction_type": construction,
        "loss_history": losses,
    }


def perturb(parsed: dict[str, Any], *, seed_key: str) -> dict[str, Any]:
    """Mild nondeterminism for temperature > 0 runs."""
    digest = hashlib.sha256(seed_key.encode()).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    out = json.loads(json.dumps(parsed))  # deep copy via JSON

    # ~25% chance to drop a loss or tweak an amount slightly
    if out.get("loss_history") and rng.random() < 0.25:
        if rng.random() < 0.5 and out["loss_history"]:
            out["loss_history"] = out["loss_history"][:-1]
        else:
            for loss in out["loss_history"]:
                if loss.get("paid_amount") is not None and rng.random() < 0.5:
                    loss["paid_amount"] = float(loss["paid_amount"]) + rng.choice(
                        [-500.0, 500.0, 0.0]
                    )

    # Occasionally mis-read construction type casing / year off-by-one
    if out.get("year_built") is not None and rng.random() < 0.15:
        out["year_built"] = int(out["year_built"]) + rng.choice([-1, 1])
    if out.get("named_insured") and rng.random() < 0.1:
        out["named_insured"] = out["named_insured"].replace(" LLC", "").replace(" Inc", "")

    return out
