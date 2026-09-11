"""Value normalizers for exact-match field comparison.

Canonical forms:
- dates → ISO ``YYYY-MM-DD``
- amounts → float dollars (``1M`` / ``$1,000,000`` → ``1000000.0``)
- codes / identifiers → stripped uppercase (alnum kept)
- free text → lowercased whitespace-normalized token list
- null vs empty string → both treated as missing (None)
"""

from __future__ import annotations

import re
from datetime import date as Date
from datetime import datetime
from typing import Any

_CURRENCY_RE = re.compile(r"[$€£]\s*")
_COMMA_RE = re.compile(r",")
_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")

_SUFFIX_MULT = {
    "k": 1_000,
    "m": 1_000_000,
    "mm": 1_000_000,
    "b": 1_000_000_000,
}


def missing_to_none(value: Any) -> Any:
    """Treat empty string / whitespace-only as missing."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def normalize_identifier(value: Any) -> str | None:
    value = missing_to_none(value)
    if value is None:
        return None
    text = str(value).strip().upper()
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text or None


def normalize_code(value: Any) -> str | None:
    """SIC / NAICS: digits only, preserve leading structure as string of digits."""
    value = missing_to_none(value)
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits or None


def normalize_date(value: Any) -> str | None:
    """Normalize to ISO date string.

    Accepts ``date``, ISO strings, and common US/EU slash forms.
    Ambiguous ``MM/DD/YY`` vs ``DD/MM/YY`` is resolved by trying month-first
    then day-first when both are plausible; if both parse to valid dates and
    disagree, raises ``AmbiguousDateError`` so callers can treat as mismatch
    rather than silently guessing.
    """
    value = missing_to_none(value)
    if value is None:
        return None
    if isinstance(value, Date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()

    text = str(value).strip()
    if not text:
        return None

    # ISO first
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass

    # Explicit long forms
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass

    slash = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})", text)
    if slash:
        a, b, y = slash.groups()
        year = int(y)
        if year < 100:
            year += 2000 if year < 70 else 1900
        n1, n2 = int(a), int(b)
        candidates: list[Date] = []
        # month-first (US)
        if 1 <= n1 <= 12 and 1 <= n2 <= 31:
            try:
                candidates.append(Date(year, n1, n2))
            except ValueError:
                pass
        # day-first (EU)
        if 1 <= n2 <= 12 and 1 <= n1 <= 31:
            try:
                d = Date(year, n2, n1)
                if d not in candidates:
                    candidates.append(d)
            except ValueError:
                pass
        if len(candidates) == 1:
            return candidates[0].isoformat()
        if len(candidates) > 1:
            raise AmbiguousDateError(text, candidates)
        return None

    return None


class AmbiguousDateError(ValueError):
    def __init__(self, raw: str, candidates: list[Date]):
        self.raw = raw
        self.candidates = candidates
        super().__init__(f"Ambiguous date {raw!r}: {candidates}")


def normalize_amount(value: Any) -> float | None:
    """Parse money-like values into float dollars.

    Examples: ``1000000``, ``$1,000,000``, ``1M``, ``1.5M``, ``$2.5MM``.
    Slash forms like ``1M/2M`` are rejected (return None) — callers should
    split compound limit strings before normalizing.
    """
    value = missing_to_none(value)
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None
    if "/" in text and re.search(r"\d", text.split("/")[0]) and re.search(
        r"\d", text.split("/")[-1]
    ):
        # Compound like "1M/2M" — not a single amount.
        return None

    text = _CURRENCY_RE.sub("", text)
    text = _COMMA_RE.sub("", text)
    text = text.strip().lower().replace(" ", "")

    mult = 1.0
    for suffix, factor in sorted(_SUFFIX_MULT.items(), key=lambda kv: -len(kv[0])):
        if text.endswith(suffix):
            mult = float(factor)
            text = text[: -len(suffix)]
            break

    if not text or not re.fullmatch(r"-?\d+(\.\d+)?", text):
        return None
    return float(text) * mult


def normalize_int(value: Any) -> int | None:
    value = missing_to_none(value)
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip()
    if re.fullmatch(r"\d{4}", text):
        return int(text)
    try:
        return int(float(text))
    except ValueError:
        return None


def normalize_text_tokens(value: Any) -> list[str] | None:
    value = missing_to_none(value)
    if value is None:
        return None
    text = str(value).lower()
    tokens = _TOKEN_RE.findall(text)
    return tokens or None


def token_overlap(a: Any, b: Any) -> float:
    """Jaccard overlap on normalized tokens. Missing/missing → 1.0; one missing → 0.0."""
    ta = normalize_text_tokens(a)
    tb = normalize_text_tokens(b)
    if ta is None and tb is None:
        return 1.0
    if ta is None or tb is None:
        return 0.0
    sa, sb = set(ta), set(tb)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def split_compound_limits(value: Any) -> tuple[float | None, float | None]:
    """Parse ``1M/2M`` style occurrence/aggregate pairs."""
    value = missing_to_none(value)
    if value is None:
        return None, None
    text = str(value).strip()
    if "/" not in text:
        amt = normalize_amount(text)
        return amt, None
    left, right = text.split("/", 1)
    return normalize_amount(left.strip()), normalize_amount(right.strip())
