"""Handwritten-fields tier: a few values drawn in a handwriting-style glyph image."""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io

from submission_harness.corpus.fields import sample_extraction
from submission_harness.corpus.render_pdf import DisplayOverrides, render_submission_pdf
from submission_harness.corpus.tiers._common import write_ground_truth
from submission_harness.schema import DifficultyTier, GroundTruthRecord


def generate_handwritten_document(
    *,
    doc_index: int,
    base_seed: int,
    output_dir: Path,
) -> GroundTruthRecord:
    doc_seed = base_seed + 20_000 + doc_index * 1009
    rng = random.Random(doc_seed)
    extraction = sample_extraction(rng)

    doc_id = f"handwritten_fields_{doc_index:03d}"
    doc_dir = Path(output_dir) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    # Blank typed values for fields that only appear as handwriting glyphs.
    overrides = DisplayOverrides(
        values={
            "named_insured": "(see handwritten endorsement)",
            "deductible": "(handwritten)",
            "year_built": "(handwritten)",
        }
    )
    base_pdf = doc_dir / "_base.pdf"
    render_submission_pdf(extraction, base_pdf, overrides=overrides)

    final = doc_dir / "document.pdf"
    _stamp_handwriting(base_pdf, final, extraction, rng)

    record = GroundTruthRecord(
        doc_id=doc_id,
        difficulty_tier=DifficultyTier.HANDWRITTEN_FIELDS,
        seed=doc_seed,
        extraction=extraction,
    )
    write_ground_truth(record, doc_dir)
    base_pdf.unlink(missing_ok=True)
    return record


def _handwriting_image(text: str, rng: random.Random) -> Image.Image:
    # Use default bitmap font with jittered glyph positions to mimic handwriting.
    width = max(40 * len(text), 200)
    img = Image.new("RGB", (width, 48), (255, 255, 252))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/MarkerFelt.ttc", 22)
    except OSError:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Comic Sans MS.ttf", 20)
        except OSError:
            font = ImageFont.load_default()

    x = 8
    for ch in text:
        y = 8 + rng.randint(-3, 3)
        draw.text((x, y), ch, fill=(20, 40, 90), font=font)
        x += 12 + rng.randint(-2, 4)
    return img


def _stamp_handwriting(base_pdf: Path, output: Path, extraction, rng: random.Random) -> None:
    # Copy base pages then append a handwriting addendum page.
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas as rl_canvas

    # Build addendum
    addendum_buf = io.BytesIO()
    c = rl_canvas.Canvas(addendum_buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(0.75 * inch, 10.2 * inch, "Handwritten field endorsements (synthetic)")
    c.setFont("Helvetica", 9)
    c.drawString(
        0.75 * inch,
        9.9 * inch,
        "The following values were written by hand on the paper submission:",
    )

    fields = [
        ("Named Insured", extraction.named_insured or ""),
        ("Deductible", f"{extraction.deductible:,.0f}" if extraction.deductible else ""),
        ("Year Built", str(extraction.year_built or "")),
    ]
    y = 9.3 * inch
    for label, value in fields:
        c.setFont("Helvetica", 9)
        c.drawString(0.75 * inch, y, f"{label}:")
        img = _handwriting_image(value, rng)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        c.drawImage(ImageReader(buf), 2.2 * inch, y - 0.15 * inch, height=0.45 * inch, mask="auto")
        y -= 0.7 * inch
    c.save()
    addendum_buf.seek(0)

    writer = PdfWriter()
    for page in PdfReader(str(base_pdf)).pages:
        writer.add_page(page)
    for page in PdfReader(addendum_buf).pages:
        writer.add_page(page)
    with output.open("wb") as fh:
        writer.write(fh)
