"""PDF rendering for synthetic commercial insurance submissions.

Layout is intentionally ACORD-like but original — not a copy of any real form.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from submission_harness.schema import SubmissionExtraction


@dataclass
class DisplayOverrides:
    """Optional per-field display strings (ambiguous / incomplete tiers)."""

    values: dict[str, str] = field(default_factory=dict)
    loss_rows: list[tuple[str, str, str, str]] | None = None


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:,.0f}"


def _fmt_date(value) -> str:
    if value is None:
        return "—"
    return value.strftime("%m/%d/%Y")


def _fmt_optional(value) -> str:
    if value is None:
        return "—"
    return str(value)


def _disp(overrides: DisplayOverrides | None, key: str, default: str) -> str:
    if overrides and key in overrides.values:
        return overrides.values[key]
    return default


def render_submission_pdf(
    extraction: SubmissionExtraction,
    output_path: Path,
    *,
    form_title: str = "Commercial Property & General Liability Submission",
    form_id: str = "CPS-GL-100 (Synthetic)",
    overrides: DisplayOverrides | None = None,
) -> Path:
    """Write a crisp PDF for a synthetic submission."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FormTitle",
        parent=styles["Heading1"],
        fontSize=14,
        spaceAfter=4,
        textColor=colors.HexColor("#1a1a1a"),
    )
    subtitle_style = ParagraphStyle(
        "FormSub",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#555555"),
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=10,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#0b3d5c"),
    )
    cell = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    story: list = []
    story.append(Paragraph(form_title, title_style))
    story.append(
        Paragraph(
            f"{form_id} &nbsp;|&nbsp; For research evaluation only — "
            "synthetic data, not a real insurance form.",
            subtitle_style,
        )
    )

    story.append(Paragraph("1. Applicant", section_style))
    code_label = extraction.industry_code_type or "Code"
    applicant_rows = [
        [
            Paragraph("<b>Named Insured</b>", cell),
            Paragraph(
                _disp(overrides, "named_insured", _fmt_optional(extraction.named_insured)),
                cell,
            ),
        ],
        [
            Paragraph("<b>Mailing Address</b>", cell),
            Paragraph(
                _disp(
                    overrides, "mailing_address", _fmt_optional(extraction.mailing_address)
                ),
                cell,
            ),
        ],
        [
            Paragraph(f"<b>{code_label} Code</b>", cell),
            Paragraph(
                _disp(overrides, "industry_code", _fmt_optional(extraction.industry_code)),
                cell,
            ),
        ],
        [
            Paragraph("<b>Business Description</b>", cell),
            Paragraph(
                _disp(
                    overrides,
                    "business_description",
                    _fmt_optional(extraction.business_description),
                ),
                cell,
            ),
        ],
    ]
    applicant = Table(applicant_rows, colWidths=[1.8 * inch, 5.2 * inch])
    applicant.setStyle(_grid_style())
    story.append(applicant)

    story.append(Paragraph("2. Policy Period", section_style))
    period = Table(
        [
            [
                Paragraph("<b>Effective Date</b>", cell),
                Paragraph(
                    _disp(overrides, "effective_date", _fmt_date(extraction.effective_date)),
                    cell,
                ),
                Paragraph("<b>Expiration Date</b>", cell),
                Paragraph(
                    _disp(
                        overrides, "expiration_date", _fmt_date(extraction.expiration_date)
                    ),
                    cell,
                ),
            ]
        ],
        colWidths=[1.5 * inch, 2.0 * inch, 1.5 * inch, 2.0 * inch],
    )
    period.setStyle(_grid_style())
    story.append(period)

    story.append(Paragraph("3. Liability Limits", section_style))
    # Prefer compound Limits line when override provides it
    if overrides and "limits_compound" in overrides.values:
        limits = Table(
            [
                [
                    Paragraph("<b>Limits</b>", cell),
                    Paragraph(overrides.values["limits_compound"], cell),
                    Paragraph("<b>Deductible</b>", cell),
                    Paragraph(
                        _disp(overrides, "deductible", _fmt_money(extraction.deductible)),
                        cell,
                    ),
                ]
            ],
            colWidths=[1.5 * inch, 2.0 * inch, 1.5 * inch, 2.0 * inch],
        )
    else:
        limits = Table(
            [
                [
                    Paragraph("<b>Per-Occurrence</b>", cell),
                    Paragraph(
                        _disp(
                            overrides,
                            "per_occurrence_limit",
                            _fmt_money(extraction.per_occurrence_limit),
                        ),
                        cell,
                    ),
                    Paragraph("<b>Aggregate</b>", cell),
                    Paragraph(
                        _disp(
                            overrides,
                            "aggregate_limit",
                            _fmt_money(extraction.aggregate_limit),
                        ),
                        cell,
                    ),
                ],
                [
                    Paragraph("<b>Deductible</b>", cell),
                    Paragraph(
                        _disp(overrides, "deductible", _fmt_money(extraction.deductible)),
                        cell,
                    ),
                    Paragraph("", cell),
                    Paragraph("", cell),
                ],
            ],
            colWidths=[1.5 * inch, 2.0 * inch, 1.5 * inch, 2.0 * inch],
        )
    limits.setStyle(_grid_style())
    story.append(limits)

    story.append(Paragraph("4. Property Schedule", section_style))
    prop = Table(
        [
            [
                Paragraph("<b>Building Value</b>", cell),
                Paragraph(
                    _disp(overrides, "building_value", _fmt_money(extraction.building_value)),
                    cell,
                ),
                Paragraph("<b>Contents Value</b>", cell),
                Paragraph(
                    _disp(overrides, "contents_value", _fmt_money(extraction.contents_value)),
                    cell,
                ),
            ],
            [
                Paragraph("<b>Year Built</b>", cell),
                Paragraph(
                    _disp(overrides, "year_built", _fmt_optional(extraction.year_built)),
                    cell,
                ),
                Paragraph("<b>Construction Type</b>", cell),
                Paragraph(
                    _disp(
                        overrides,
                        "construction_type",
                        _fmt_optional(extraction.construction_type),
                    ),
                    cell,
                ),
            ],
        ],
        colWidths=[1.5 * inch, 2.0 * inch, 1.5 * inch, 2.0 * inch],
    )
    prop.setStyle(_grid_style())
    story.append(prop)

    story.append(Paragraph("5. Loss History (prior 5 years)", section_style))
    loss_header = [
        Paragraph("<b>Date</b>", cell),
        Paragraph("<b>Cause</b>", cell),
        Paragraph("<b>Paid Amount</b>", cell),
        Paragraph("<b>Status</b>", cell),
    ]
    loss_rows = [loss_header]
    if overrides and overrides.loss_rows is not None:
        for d, c, a, s in overrides.loss_rows:
            loss_rows.append(
                [
                    Paragraph(d, cell),
                    Paragraph(c, cell),
                    Paragraph(a, cell),
                    Paragraph(s, cell),
                ]
            )
    elif extraction.loss_history:
        for event in extraction.loss_history:
            loss_rows.append(
                [
                    Paragraph(_fmt_date(event.date), cell),
                    Paragraph(_fmt_optional(event.cause), cell),
                    Paragraph(_fmt_money(event.paid_amount), cell),
                    Paragraph(_fmt_optional(event.status), cell),
                ]
            )
    else:
        loss_rows.append(
            [
                Paragraph("None reported", cell),
                Paragraph("—", cell),
                Paragraph("—", cell),
                Paragraph("—", cell),
            ]
        )
    losses = Table(
        loss_rows,
        colWidths=[1.1 * inch, 3.4 * inch, 1.3 * inch, 1.2 * inch],
    )
    losses.setStyle(_grid_style())
    story.append(losses)

    story.append(Spacer(1, 0.25 * inch))
    story.append(
        Paragraph(
            "Producer certification: values above are synthetic fixtures generated "
            "for LLM evaluation. No real insured, claim, or policy data is present.",
            ParagraphStyle(
                "Footer",
                parent=styles["Normal"],
                fontSize=7,
                textColor=colors.HexColor("#666666"),
            ),
        )
    )

    doc.build(story)
    return output_path


def _grid_style() -> TableStyle:
    return TableStyle(
        [
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#333333")),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f6f9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
    )
