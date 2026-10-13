"""Rule-based extraction of receipt fields; kept dependency-free for unit tests."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


DATE_PATTERNS = (
    (re.compile(r"\b([0-9Oo]{4})[-/.]([0-9Oo]{1,2})[-/.]([0-9Oo]{1,2})\b"), "ymd"),
    (re.compile(r"\b([0-9Oo]{1,2})[-/.]([0-9Oo]{1,2})[-/.]([0-9Oo]{2,4})\b"), "dmy"),
)
NAMED_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+([a-z]{3,9})\.?\s+(\d{2,4})\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(
    r"(?<![\w/])(?:Rp\s*)?"
    r"(\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{1,2})?|\d{1,12}(?:[.,]\d{1,2})?)"
    r"(?![\w/])",
    re.IGNORECASE,
)
TOTAL_HINT_RE = re.compile(
    r"\b(?:grand\s+total|total\s+due|amount\s+due|total|jumlah|tagihan|netto)\b",
    re.I,
)
NON_TOTAL_HINT_RE = re.compile(
    r"\b(?:sub\s*total|tax|pajak|change|kembali|cash|tunai|discount|diskon|saving)\b",
    re.I,
)
MONTH_NAMES = {
    "jan": 1,
    "januari": 1,
    "feb": 2,
    "februari": 2,
    "mar": 3,
    "maret": 3,
    "apr": 4,
    "april": 4,
    "mei": 5,
    "may": 5,
    "jun": 6,
    "juni": 6,
    "jul": 7,
    "juli": 7,
    "agu": 8,
    "agt": 8,
    "agustus": 8,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "okt": 10,
    "oct": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "des": 12,
    "dec": 12,
    "desember": 12,
}


def _year(value: str) -> int:
    result = int(value.replace("O", "0").replace("o", "0"))
    return result + (2000 if result < 70 else 1900) if result < 100 else result


def find_dates(text: str) -> list[str]:
    """Return every valid date in a line; OCR O/0 correction is numeric-only."""
    dates = []
    for pattern, order in DATE_PATTERNS:
        for match in pattern.finditer(text):
            values = [
                int(value.replace("O", "0").replace("o", "0"))
                for value in match.groups()
            ]
            if order == "ymd":
                year, month, day = values
            else:
                day, month, year = values
            year = _year(str(year))
            try:
                parsed = date(year, month, day).isoformat()
            except ValueError:
                continue
            if parsed not in dates:
                dates.append(parsed)

    for match in NAMED_DATE_RE.finditer(text):
        day, month_text, year_text = match.groups()
        month = next(
            (
                value
                for name, value in MONTH_NAMES.items()
                if month_text.lower().startswith(name)
            ),
            None,
        )
        if month is None:
            continue
        try:
            parsed = date(_year(year_text), month, int(day)).isoformat()
        except ValueError:
            continue
        if parsed not in dates:
            dates.append(parsed)
    return dates


def parse_date(text: str) -> str | None:
    candidates = find_dates(text)
    return candidates[0] if candidates else None


def parse_amount(raw: str) -> Decimal | None:
    value = re.sub(r"[^\d.,]", "", raw)
    if not value or not any(char.isdigit() for char in value):
        return None
    if "," in value and "." in value:
        decimal_mark = "," if value.rfind(",") > value.rfind(".") else "."
        grouping_mark = "." if decimal_mark == "," else ","
        value = value.replace(grouping_mark, "").replace(decimal_mark, ".")
    elif "," in value or "." in value:
        mark = "," if "," in value else "."
        parts = value.split(mark)
        if len(parts) > 2 or (len(parts[-1]) == 3 and all(len(part) == 3 for part in parts[1:])):
            value = "".join(parts)
        else:
            value = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _without_dates(text: str) -> str:
    for pattern, _order in DATE_PATTERNS:
        text = pattern.sub(" ", text)
    return NAMED_DATE_RE.sub(" ", text)


def _format_amount(amount: Decimal) -> str:
    rendered = format(amount, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def extract_fields(lines: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [str(line.get("text", "")) for line in lines]
    store = ""
    for text in texts[:6]:
        candidate = re.sub(r"\s+", " ", text).strip(" :|-")
        if len(candidate) < 3 or parse_date(candidate):
            continue
        if not any(
            word in candidate.lower()
            for word in ("receipt", "struk", "cashier", "kasir", "www.", "http")
        ):
            store = candidate[:100]
            break

    dates = []
    for text in texts:
        for found in find_dates(text):
            if found not in dates:
                dates.append(found)

    amounts = []
    for index, original in enumerate(texts):
        text = _without_dates(original)
        matches = list(MONEY_RE.finditer(text))
        previous_end = 0
        for match_index, match in enumerate(matches):
            amount = parse_amount(match.group(1))
            if amount is None or amount <= 0:
                previous_end = match.end()
                continue

            # Evaluate nearby labels per amount token. This allows a single OCR line
            # to contain both SUBTOTAL and TOTAL, or TOTAL followed by CASH/CHANGE.
            left_context = text[previous_end:match.start()]
            next_start = matches[match_index + 1].start() if match_index + 1 < len(matches) else len(text)
            right_context = text[match.end():next_start]
            previous_line = texts[index - 1] if index else ""
            explicit_total = bool(TOTAL_HINT_RE.search(left_context))
            if (
                not explicit_total
                and not NON_TOTAL_HINT_RE.search(left_context)
            ):
                explicit_total = bool(TOTAL_HINT_RE.search(right_context))
            if (
                match_index == 0
                and previous_line
                and len(previous_line) <= 64
                and not MONEY_RE.search(_without_dates(previous_line))
            ):
                left_context = previous_line + " " + left_context

            if NON_TOTAL_HINT_RE.search(left_context):
                previous_end = match.end()
                continue
            if (
                match_index == 0
                and NON_TOTAL_HINT_RE.search(previous_line)
                and not explicit_total
            ):
                previous_end = match.end()
                continue

            has_currency = bool(re.search(r"\bRp\b", match.group(0), re.I))
            raw_amount = match.group(1)
            has_grouping = bool(re.search(r"[.,]\d{3}(?:\b|[.,])", raw_amount))
            if not (explicit_total or has_currency or has_grouping):
                previous_end = match.end()
                continue

            score = 4 if explicit_total else 0
            if has_currency:
                score += 1
            if index >= max(0, len(texts) - 5):
                score += 1
            amounts.append((score, amount))
            previous_end = match.end()

    total = ""
    ambiguous_total = False
    if amounts:
        best_score = max(item[0] for item in amounts)
        best = {item[1] for item in amounts if item[0] == best_score}
        if len(best) == 1:
            total = _format_amount(next(iter(best)))
        else:
            ambiguous_total = True
    return {
        "store_name": store,
        "transaction_date": dates[0] if dates else "",
        "total_amount": total,
        "date_candidates": dates,
        "total_ambiguous": ambiguous_total,
    }
