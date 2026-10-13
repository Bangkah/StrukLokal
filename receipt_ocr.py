"""Document decoding and local PaddleOCR inference."""

from __future__ import annotations

import io
import os
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError

from parser import extract_fields

BASE_DIR = Path(__file__).resolve().parent
RUNTIME_HOME = BASE_DIR / ".paddle_home"
MODEL_CACHE_DIR = BASE_DIR / ".paddlex_cache"

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 5
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_DIMENSION = 2600
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}

OCRLine = dict[str, Any]
OCR_ENGINE: Any | None = None
OCR_LOCK = threading.Lock()


@contextmanager
def _project_cache_environment() -> Iterator[None]:
    """Point Paddle's home-based caches at this project during initialization."""
    cache_variables = ("HOME", "USERPROFILE", "PADDLE_PDX_CACHE_HOME")
    previous = {name: os.environ.get(name) for name in cache_variables}

    os.environ["HOME"] = str(RUNTIME_HOME)
    os.environ["USERPROFILE"] = str(RUNTIME_HOME)
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(MODEL_CACHE_DIR)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def check_extension(filename: str) -> str:
    """Return a supported lower-case extension or raise a user-safe error."""
    if "." not in filename:
        raise ValueError("Jenis berkas tidak didukung. Gunakan JPG, PNG, atau PDF.")

    extension = filename.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Jenis berkas tidak didukung. Gunakan JPG, PNG, atau PDF.")
    return extension


def image_to_array(data: bytes) -> np.ndarray:
    """Decode, orient, and downscale an uploaded image for OCR."""
    try:
        with Image.open(io.BytesIO(data)) as opened:
            if opened.width * opened.height > MAX_IMAGE_PIXELS:
                raise ValueError(
                    "Gambar memiliki resolusi terlalu besar untuk diproses dengan aman."
                )

            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail(
                (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
                Image.Resampling.LANCZOS,
            )
            return np.asarray(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Gambar rusak atau tidak dapat dibaca.") from exc


def document_pages(data: bytes, extension: str) -> list[np.ndarray]:
    """Decode an image or render each allowed PDF page to an RGB array."""
    if extension != "pdf":
        return [image_to_array(data)]

    try:
        pdf = pdfium.PdfDocument(data)
    except Exception as exc:
        raise ValueError("PDF rusak atau tidak dapat dibaca.") from exc

    try:
        if len(pdf) < 1:
            raise ValueError("PDF tidak memiliki halaman.")
        if len(pdf) > MAX_PDF_PAGES:
            raise ValueError("PDF melebihi batas 5 halaman.")

        pages = []
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            try:
                width, height = page.get_size()
                longest_side = max(float(width), float(height), 1.0)
                scale = min(1.6, MAX_IMAGE_DIMENSION / longest_side)
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil().convert("RGB")
                image.thumbnail(
                    (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
                    Image.Resampling.LANCZOS,
                )
                pages.append(np.asarray(image))
                del bitmap
            finally:
                page.close()
        return pages
    finally:
        pdf.close()


def _result_lines(result: Iterable[Any] | None) -> list[OCRLine]:
    """Normalize PaddleOCR's pipeline response to parser-friendly lines."""
    lines: list[OCRLine] = []
    for page_result in result or []:
        payload = getattr(page_result, "json", None)
        if callable(payload):
            payload = payload()
        if isinstance(payload, dict) and isinstance(payload.get("res"), dict):
            payload = payload["res"]
        if not isinstance(payload, dict):
            continue

        texts = payload.get("rec_texts")
        scores = payload.get("rec_scores")
        boxes = payload.get("dt_polys")
        texts = texts.tolist() if hasattr(texts, "tolist") else (texts or [])
        scores = scores.tolist() if hasattr(scores, "tolist") else (scores or [])
        boxes = boxes.tolist() if hasattr(boxes, "tolist") else (boxes or [])

        for index, text in enumerate(texts):
            cleaned = str(text).strip()
            if not cleaned:
                continue
            score = float(scores[index]) if index < len(scores) else None
            box = boxes[index] if index < len(boxes) else None
            lines.append({"text": cleaned, "score": score, "box": box})
    return lines


def build_ocr_engine() -> Any:
    """Create the configured Indonesian OCR engine and cache its models locally."""
    with _project_cache_environment():
        from paddleocr import PaddleOCR

        return PaddleOCR(
            lang="id",
            ocr_version="PP-OCRv6",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            engine="paddle",
        )


def get_ocr_engine() -> Any:
    """Initialize PaddleOCR only once, on first document upload."""
    global OCR_ENGINE
    if OCR_ENGINE is None:
        with OCR_LOCK:
            if OCR_ENGINE is None:
                OCR_ENGINE = build_ocr_engine()
    return OCR_ENGINE


def process_receipt(data: bytes, filename: str) -> tuple[dict[str, Any], str]:
    """Run OCR and field extraction for one uploaded receipt."""
    extension = check_extension(filename)
    pages = document_pages(data, extension)
    engine = get_ocr_engine()

    lines: list[OCRLine] = []
    for page in pages:
        lines.extend(_result_lines(engine.predict(page)))

    fields = extract_fields(lines)
    raw_text = "\n".join(line["text"] for line in lines)
    return fields, raw_text
