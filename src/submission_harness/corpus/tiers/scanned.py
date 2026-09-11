"""Scanned tier: low-DPI rasterization with slight rotation and noise."""

from __future__ import annotations

import io
import random
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from submission_harness.corpus.fields import sample_extraction
from submission_harness.corpus.render_pdf import render_submission_pdf
from submission_harness.corpus.tiers._common import write_ground_truth
from submission_harness.schema import DifficultyTier, GroundTruthRecord


def generate_scanned_document(
    *,
    doc_index: int,
    base_seed: int,
    output_dir: Path,
) -> GroundTruthRecord:
    doc_seed = base_seed + 10_000 + doc_index * 1009
    rng = random.Random(doc_seed)
    extraction = sample_extraction(rng)

    doc_id = f"scanned_{doc_index:03d}"
    doc_dir = Path(output_dir) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "clean.pdf"
        render_submission_pdf(extraction, clean)
        raster = _rasterize_with_artifacts(clean, rng)
        _images_to_pdf(raster, doc_dir / "document.pdf")

    record = GroundTruthRecord(
        doc_id=doc_id,
        difficulty_tier=DifficultyTier.SCANNED,
        seed=doc_seed,
        extraction=extraction,
    )
    write_ground_truth(record, doc_dir)
    return record


def _rasterize_with_artifacts(pdf_path: Path, rng: random.Random) -> list[Image.Image]:
    with tempfile.TemporaryDirectory() as tmp:
        prefix = Path(tmp) / "page"
        subprocess.run(
            ["pdftoppm", "-r", "72", "-png", str(pdf_path), str(prefix)],
            check=True,
            capture_output=True,
        )
        pages = sorted(Path(tmp).glob("page*.png"))
        images: list[Image.Image] = []
        for page in pages:
            img = Image.open(page).convert("RGB")
            angle = rng.uniform(-2.5, 2.5)
            img = img.rotate(angle, resample=Image.Resampling.BILINEAR, expand=False, fillcolor=(245, 245, 240))
            # Noise
            noise = Image.effect_noise(img.size, rng.uniform(8, 18)).convert("RGB")
            img = Image.blend(img, noise, alpha=0.12)
            img = ImageEnhance.Contrast(img).enhance(0.85)
            img = img.filter(ImageFilter.SMOOTH)
            images.append(img)
        return images


def _images_to_pdf(images: list[Image.Image], output: Path) -> None:
    c = canvas.Canvas(str(output), pagesize=letter)
    width, height = letter
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=55)
        buf.seek(0)
        c.drawImage(ImageReader(buf), 0, 0, width=width, height=height)
        c.showPage()
    c.save()
