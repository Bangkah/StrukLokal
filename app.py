from __future__ import annotations

import csv
import io
import os
import re
import secrets
import uuid
from datetime import date
from decimal import Decimal
from functools import wraps
from typing import Any

from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.exceptions import RequestEntityTooLarge

from receipt_ocr import MAX_FILE_BYTES, process_receipt

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("STRUKLOKAL_SECRET", secrets.token_hex(32)),
    MAX_CONTENT_LENGTH=MAX_FILE_BYTES + 256 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=False,  # The app binds to loopback over HTTP.
)

# Session data is deliberately process-local and disappears when the app stops.
TRANSACTIONS: dict[str, list[dict[str, Any]]] = {}


def current_rows() -> list[dict[str, Any]]:
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
            abort(
                400,
                description=(
                    "Token formulir tidak valid. Muat ulang halaman lalu coba lagi."
                ),
            )
        return view(*args, **kwargs)

    return wrapped


def valid_amount(value: str) -> bool:
    matches_format = re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", value.strip())
    return bool(matches_format) and Decimal(value) > 0


def template_context(**kwargs: Any) -> dict[str, Any]:
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
        data = uploaded.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("Ukuran berkas melebihi batas 10 MB.")
        fields, raw_text = process_receipt(data, uploaded.filename)
        row = {
            "id": uuid.uuid4().hex,
            "filename": os.path.basename(uploaded.filename)[:120],
            **fields,
            "raw_text": raw_text,
            "verified": False,
        }
        current_rows().insert(0, row)
        flash(
            "OCR selesai. Periksa kolom bertanda sebelum menyetujui transaksi.",
            "success",
        )
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception as exc:  # noqa: BLE001
        # Avoid exposing OCR internals or extracted user data in the UI or logs.
        app.logger.warning("Pemrosesan dokumen gagal (%s).", type(exc).__name__)
        flash(
            (
                "Dokumen tidak dapat diproses. Periksa formatnya atau coba "
                "gambar yang lebih jelas."
            ),
            "error",
        )
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
        flash(
            "Tanggal harus valid dan menggunakan format YYYY-MM-DD.",
            "error",
        )
    elif not valid_amount(total):
        flash(
            "Total harus berupa angka positif dengan maksimal dua angka desimal.",
            "error",
        )
    else:
        row.update(
            store_name=store,
            transaction_date=parsed_date.isoformat(),
            total_amount=format(Decimal(total), "f"),
            verified=True,
        )
        flash(
            "Transaksi disetujui dan ditandai terverifikasi.",
            "success",
        )
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
        writer.writerow(
            [
                safe_csv_cell(row["store_name"]),
                safe_csv_cell(row["transaction_date"]),
                safe_csv_cell(row["total_amount"]),
            ]
        )
    content = "\ufeff" + output.getvalue()
    return Response(
        content,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=struklokal-transaksi.csv",
            "Cache-Control": "no-store",
        },
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
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    )
    return response


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
