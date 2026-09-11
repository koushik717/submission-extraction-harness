"""Pydantic schema for commercial insurance submission extraction.

All fields may be null when genuinely missing (incomplete tier) or when the
extractor cannot find them. Empty strings are never used for missing values.
"""

from __future__ import annotations

from datetime import date as Date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DifficultyTier(str, Enum):
    CLEAN_DIGITAL = "clean_digital"
    SCANNED = "scanned"
    HANDWRITTEN_FIELDS = "handwritten_fields"
    INCOMPLETE = "incomplete"
    AMBIGUOUS = "ambiguous"


class LossEvent(BaseModel):
    """A single prior loss entry on the submission."""

    model_config = ConfigDict(extra="forbid")

    # Field name is `date` (JSON key); type alias avoids shadowing datetime.date.
    date: Date | None = None
    cause: str | None = None
    paid_amount: float | None = None
    status: str | None = None

    @field_validator("cause", "status", mode="before")
    @classmethod
    def empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class SubmissionExtraction(BaseModel):
    """Structured fields extracted from (or generated for) a submission PDF."""

    model_config = ConfigDict(extra="forbid")

    named_insured: str | None = None
    mailing_address: str | None = None
    effective_date: Date | None = None
    expiration_date: Date | None = None
    industry_code: str | None = None
    industry_code_type: Literal["SIC", "NAICS"] | None = None
    business_description: str | None = None
    per_occurrence_limit: float | None = None
    aggregate_limit: float | None = None
    deductible: float | None = None
    building_value: float | None = None
    contents_value: float | None = None
    year_built: int | None = None
    construction_type: str | None = None
    loss_history: list[LossEvent] = Field(default_factory=list)

    @field_validator(
        "named_insured",
        "mailing_address",
        "industry_code",
        "business_description",
        "construction_type",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class GroundTruthRecord(BaseModel):
    """Ground truth shipped with each synthetic document."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    difficulty_tier: DifficultyTier
    seed: int
    extraction: SubmissionExtraction
