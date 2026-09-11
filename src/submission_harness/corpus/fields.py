"""Synthetic field samplers for commercial property / GL submissions.

All names, addresses, and codes are fabricated. No real insureds or PII.
"""

from __future__ import annotations

import random
from datetime import date as Date
from datetime import timedelta

from submission_harness.schema import LossEvent, SubmissionExtraction

_COMPANY_PREFIXES = [
    "Northbridge",
    "Summit",
    "Cedar",
    "Harbor",
    "Prairie",
    "Ironwood",
    "Lakeside",
    "Meridian",
    "Oakridge",
    "Silverline",
]

_COMPANY_SUFFIXES = [
    "Logistics LLC",
    "Manufacturing Inc",
    "Properties LP",
    "Wholesale Co",
    "Services Corp",
    "Distribution LLC",
    "Holdings Inc",
    "Fabrics LLC",
    "Packaging Inc",
    "Cold Storage LLC",
]

_STREETS = [
    "River Road",
    "Industrial Parkway",
    "Commerce Drive",
    "Maple Avenue",
    "Depot Street",
    "Frontier Boulevard",
    "Warehouse Lane",
    "Mill Street",
]

_CITIES = [
    ("Springfield", "IL", "62701"),
    ("Franklin", "TN", "37064"),
    ("Hudson", "OH", "44236"),
    ("Boulder", "CO", "80301"),
    ("Asheville", "NC", "28801"),
    ("Boise", "ID", "83702"),
    ("Madison", "WI", "53703"),
    ("Tulsa", "OK", "74103"),
]

_CONSTRUCTION = [
    "Frame",
    "Joisted Masonry",
    "Non-Combustible",
    "Masonry Non-Combustible",
    "Modified Fire Resistive",
    "Fire Resistive",
]

_BUSINESSES = [
    ("5311", "SIC", "Department store retail operations"),
    ("4213", "SIC", "Long-haul trucking and freight brokerage"),
    ("3089", "SIC", "Plastic product fabrication"),
    ("5141", "SIC", "Grocery wholesale distribution"),
    ("4225", "SIC", "General warehousing and storage"),
    ("236210", "NAICS", "Industrial building construction"),
    ("424410", "NAICS", "General line grocery merchant wholesalers"),
    ("493110", "NAICS", "General warehousing and storage"),
    ("311612", "NAICS", "Meat processed from carcasses"),
    ("332710", "NAICS", "Machine shops"),
]

_LOSS_CAUSES = [
    "Water damage from roof leak",
    "Windstorm damage to exterior",
    "Fire in electrical room",
    "Theft of inventory",
    "Hail damage to roof",
    "Sprinkler leakage",
    "Vehicle impact to loading dock",
]

_LOSS_STATUSES = ["Closed", "Open", "Subrogation", "Denied"]


def _money(rng: random.Random, low: int, high: int, step: int = 1000) -> float:
    n = rng.randrange(low // step, high // step + 1)
    return float(n * step)


def sample_extraction(rng: random.Random) -> SubmissionExtraction:
    """Draw a complete ground-truth extraction from a seeded RNG."""
    prefix = rng.choice(_COMPANY_PREFIXES)
    suffix = rng.choice(_COMPANY_SUFFIXES)
    named = f"{prefix} {suffix}"

    street_no = rng.randint(100, 9800)
    street = rng.choice(_STREETS)
    city, state, zip_code = rng.choice(_CITIES)
    unit = ""
    if rng.random() < 0.35:
        unit = f", Suite {rng.randint(100, 899)}"
    address = f"{street_no} {street}{unit}, {city}, {state} {zip_code}"

    # Policy term: effective on a weekday-ish date, 12-month term.
    year = rng.randint(2024, 2026)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    effective = Date(year, month, day)
    expiration = Date(year + 1, month, day)

    code, code_type, description = rng.choice(_BUSINESSES)

    per_occ = rng.choice([500_000.0, 1_000_000.0, 2_000_000.0, 5_000_000.0])
    aggregate = per_occ * rng.choice([1, 2])
    deductible = rng.choice([1_000.0, 2_500.0, 5_000.0, 10_000.0, 25_000.0])

    building = _money(rng, 250_000, 8_000_000, 25_000)
    contents = _money(rng, 50_000, 2_500_000, 10_000)
    year_built = rng.randint(1955, 2019)
    construction = rng.choice(_CONSTRUCTION)

    n_losses = rng.randint(0, 3)
    losses: list[LossEvent] = []
    for _ in range(n_losses):
        loss_year = rng.randint(effective.year - 5, effective.year - 1)
        loss_date = Date(loss_year, rng.randint(1, 12), rng.randint(1, 28))
        # Keep loss dates strictly before effective for realism.
        if loss_date >= effective:
            loss_date = effective - timedelta(days=rng.randint(30, 800))
        losses.append(
            LossEvent(
                date=loss_date,
                cause=rng.choice(_LOSS_CAUSES),
                paid_amount=_money(rng, 0, 250_000, 500),
                status=rng.choice(_LOSS_STATUSES),
            )
        )
    losses.sort(key=lambda event: event.date or Date.min)

    return SubmissionExtraction(
        named_insured=named,
        mailing_address=address,
        effective_date=effective,
        expiration_date=expiration,
        industry_code=code,
        industry_code_type=code_type,  # type: ignore[arg-type]
        business_description=description,
        per_occurrence_limit=per_occ,
        aggregate_limit=aggregate,
        deductible=deductible,
        building_value=building,
        contents_value=contents,
        year_built=year_built,
        construction_type=construction,
        loss_history=losses,
    )
