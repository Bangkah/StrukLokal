from __future__ import annotations

import csv
import io
import os
import re
import secrets
import threading
import uuid
from datetime import date
from decimal import Decimal
from functools import wraps

import numpy as np
from flask import Flask, Response, abort, flash, redirect, render_template, request, session, url_for
from PIL import Image, ImageOps, UnidentifiedImageError
import pypdfium2 as pdfium
from werkzeug.exceptions import RequestEntityTooLarge
from parser import extract_fields


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Keep PaddleX's model/cache files inside the project folder so setup works
# without writing to the user's home directory and the app can reuse the cache.
RUNTIME_HOME = os.path.join(BASE_DIR, ".paddle_home")
os.environ["USERPROFILE"] = RUNTIME_HOME
os.environ["HOME"] = RUNTIME_HOME
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", os.path.join(BASE_DIR, ".paddlex_cache"))
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 5
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_DIMENSION = 2600
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("STRUKLOKAL_SECRET", secrets.token_hex(32)),
    MAX_CONTENT_LENGTH=MAX_FILE_BYTES + 256 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=False,  # The app binds to loopback over HTTP.
)

# Session data is deliberately process-local and disappears when the app stops.
TRANSACTIONS: dict[str, list[dict]] = {}
OCR_ENGINE = None
OCR_LOCK = threading.Lock()


def current_rows() -> list[dict]:
    sid = session.get("sid")
    if not sid:
        sid = secrets.token_urlsafe(24)
        session["sid"] = sid
    return TRANSACTIONS.setdefault(sid, [])


@app.before_request
def csrf_setup():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(24)


def csrf_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.form.get("csrf_token") != session.get("csrf_token"):
            abort(400, description="Token formulir tidak valid. Muat ulang halaman lalu coba lagi.")
        return view(*args, **kwargs)
    return wrapped


def get_ocr_engine():
    global OCR_ENGINE
    if OCR_ENGINE is None:
        with OCR_LOCK:
            if OCR_ENGINE is None:
                from paddleocr import PaddleOCR

                OCR_ENGINE = PaddleOCR(
                    lang="id",
                    ocr_version="PP-OCRv6",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    engine="paddle",
                )
    return OCR_ENGINE


def check_extension(filename: str) -> str:
    if "." not in filename:
        raise ValueError("Jenis berkas tidak didukung. Gunakan JPG, PNG, atau PDF.")
    extension = filename.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Jenis berkas tidak didukung. Gunakan JPG, PNG, atau PDF.")
    return extension


def image_to_array(data: bytes) -> np.ndarray:
    try:
        with Image.open(io.BytesIO(data)) as opened:
            if opened.width * opened.height > MAX_IMAGE_PIXELS:
                raise ValueError("Gambar memiliki resolusi terlalu besar untuk diproses dengan aman.")
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
            return np.asarray(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Gambar rusak atau tidak dapat dibaca.") from exc


def document_pages(data: bytes, extension: str) -> list[np.ndarray]:
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
                rect = page.get_size()
                longest_side = max(float(rect[0]), float(rect[1]), 1.0)
                scale = min(1.6, MAX_IMAGE_DIMENSION / longest_side)
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil().convert("RGB")
                image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
                pages.append(np.asarray(image))
                del bitmap
            finally:
                page.close()
        return pages
    finally:
        pdf.close()


def _result_lines(result) -> list[dict]:
    lines = []
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
            box = boxes[index]
            lines.append({"text": cleaned, "score": score, "box": box})
    return lines


def valid_amount(value: str) -> bool:
    return bool(re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", value.strip())) and Decimal(value) > 0


def template_context(**kwargs):
    rows = current_rows()
    return dict(
        rows=rows,
        verified_count=sum(bool(row["verified"]) for row in rows),
        pending_count=sum(not row["verified"] for row in rows),
        csrf_token=session["csrf_token"],
        **kwargs,
    )


@app.get("/")
def index():
    return render_template("index.html", **template_context())


@app.post("/upload")
@csrf_required
def upload():
    uploaded = request.files.get("receipt")
    if not uploaded or not uploaded.filename:
        flash("Pilih berkas JPG, PNG, atau PDF terlebih dahulu.", "error")
        return redirect(url_for("index"))
    try:
        extension = check_extension(uploaded.filename)
        data = uploaded.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("Ukuran berkas melebihi batas 10 MB.")
        pages = document_pages(data, extension)
        ocr = get_ocr_engine()
        lines = []
        for page in pages:
            lines.extend(_result_lines(ocr.predict(page)))
        fields = extract_fields(lines)
        row = {
            "id": uuid.uuid4().hex,
            "filename": os.path.basename(uploaded.filename)[:120],
            **fields,
            "raw_text": "\n".join(item["text"] for item in lines),
            "verified": False,
        }
        current_rows().insert(0, row)
        flash("OCR selesai. Periksa kolom bertanda sebelum menyetujui transaksi.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        # Avoid exposing OCR internals or extracted user data in the UI or logs.
        app.logger.warning("Pemrosesan dokumen gagal (%s).", type(exc).__name__)
        flash("Dokumen tidak dapat diproses. Periksa formatnya atau coba gambar yang lebih jelas.", "error")
    return redirect(url_for("index"))


@app.post("/transaction/<row_id>/save")
@csrf_required
def save_transaction(row_id: str):
    row = next((item for item in current_rows() if item["id"] == row_id), None)
    if row is None:
        abort(404)
    store = request.form.get("store_name", "").strip()[:100]
    raw_date = request.form.get("transaction_date", "").strip()
    total = request.form.get("total_amount", "").strip()
    try:
        parsed_date = date.fromisoformat(raw_date)
    except ValueError:
        parsed_date = None
    if not store:
        flash("Nama toko harus diisi.", "error")
    elif parsed_date is None:
        flash("Tanggal harus valid dan menggunakan format YYYY-MM-DD.", "error")
    elif not valid_amount(total):
        flash("Total harus berupa angka positif dengan maksimal dua angka desimal.", "error")
    else:
        row.update(store_name=store, transaction_date=parsed_date.isoformat(), total_amount=format(Decimal(total), "f"), verified=True)
        flash("Transaksi disetujui dan ditandai terverifikasi.", "success")
    return redirect(url_for("index"))


@app.post("/transaction/<row_id>/delete")
@csrf_required
def delete_transaction(row_id: str):
    sid = session.get("sid")
    if sid in TRANSACTIONS:
        TRANSACTIONS[sid] = [item for item in TRANSACTIONS[sid] if item["id"] != row_id]
    return redirect(url_for("index"))


@app.post("/clear")
@csrf_required
def clear_transactions():
    sid = session.get("sid")
    TRANSACTIONS.pop(sid, None)
    session.pop("sid", None)
    flash("Data sesi telah dihapus.", "success")
    return redirect(url_for("index"))


def safe_csv_cell(value: str) -> str:
    value = str(value)
    if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@app.get("/export.csv")
def export_csv():
    approved = [row for row in current_rows() if row["verified"]]
    if not approved:
        flash("Belum ada transaksi terverifikasi untuk diekspor.", "error")
        return redirect(url_for("index"))
    output = io.StringIO(newline="")
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["store_name", "transaction_date", "total_amount"])
    for row in approved:
        writer.writerow([safe_csv_cell(row["store_name"]), safe_csv_cell(row["transaction_date"]), safe_csv_cell(row["total_amount"])])
    content = "\ufeff" + output.getvalue()
    return Response(
        content,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=struklokal-transaksi.csv", "Cache-Control": "no-store"},
    )


@app.errorhandler(RequestEntityTooLarge)
def too_large(_error):
    flash("Ukuran berkas melebihi batas 10 MB.", "error")
    return redirect(url_for("index")), 413


@app.after_request
def privacy_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    return response


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
