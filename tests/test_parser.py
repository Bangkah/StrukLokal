import unittest
from decimal import Decimal

from parser import extract_fields, find_dates, parse_amount, parse_date


def ocr_lines(*texts):
    return [{"text": text} for text in texts]


class ReceiptParserTests(unittest.TestCase):
    def test_total_label_on_previous_line(self):
        fields = extract_fields(ocr_lines(
            "TOKO MAKMUR", "Tanggal 12/10/2026", "TOTAL", "Rp 125.000"
        ))
        self.assertEqual(fields["transaction_date"], "2026-10-12")
        self.assertEqual(fields["total_amount"], "125000")
        self.assertFalse(fields["total_ambiguous"])

    def test_date_and_currency_amount_on_same_line(self):
        fields = extract_fields(ocr_lines("TOKO MAKMUR", "Tanggal 12/10/2026 Rp 125.000"))
        self.assertEqual(fields["transaction_date"], "2026-10-12")
        self.assertEqual(fields["total_amount"], "125000")
        self.assertFalse(fields["total_ambiguous"])

    def test_subtotal_and_tax_are_ignored_in_favor_of_grand_total(self):
        fields = extract_fields(ocr_lines(
            "TOKO MAKMUR", "Subtotal Rp 100.000", "Pajak Rp 10.000", "Grand Total", "Rp 110.000"
        ))
        self.assertEqual(fields["total_amount"], "110000")
        self.assertFalse(fields["total_ambiguous"])

    def test_total_after_tax_line_is_not_rejected(self):
        fields = extract_fields(ocr_lines(
            "TOKO MAKMUR", "Subtotal Rp 100.000", "Pajak Rp 10.000", "TOTAL Rp 110.000"
        ))
        self.assertEqual(fields["total_amount"], "110000")
        self.assertFalse(fields["total_ambiguous"])

    def test_tied_total_candidates_are_flagged(self):
        fields = extract_fields(ocr_lines(
            "TOKO MAKMUR", "Rp 120.000", "Rp 125.000", "Catatan: simpan struk"
        ))
        self.assertEqual(fields["total_amount"], "")
        self.assertTrue(fields["total_ambiguous"])

    def test_unlabelled_date_numbers_are_not_amount_candidates(self):
        fields = extract_fields(ocr_lines("TOKO MAKMUR", "Tanggal 12/10/2026", "Kasir 02"))
        self.assertEqual(fields["total_amount"], "")
        self.assertFalse(fields["total_ambiguous"])

    def test_amount_formats(self):
        self.assertEqual(parse_amount("Rp 1.234.567"), Decimal("1234567"))
        self.assertEqual(parse_amount("1.234,50"), Decimal("1234.50"))
        self.assertEqual(parse_amount("1,234.50"), Decimal("1234.50"))

    def test_date_validation(self):
        self.assertEqual(parse_date("12/10/2026"), "2026-10-12")
        self.assertIsNone(parse_date("31/02/2026"))

    def test_named_indonesian_months(self):
        self.assertEqual(parse_date("12 Oktober 2026"), "2026-10-12")
        self.assertEqual(parse_date("12 Okt 2026"), "2026-10-12")
        self.assertEqual(parse_date("12 Mei 2026"), "2026-05-12")

    def test_ocr_zero_correction_only_affects_numeric_date(self):
        self.assertEqual(parse_date("12/1O/2026"), "2026-10-12")
        self.assertEqual(parse_date("12 Oktober 2026"), "2026-10-12")

    def test_subtotal_and_total_tokens_on_same_line(self):
        fields = extract_fields(ocr_lines("TOKO MAKMUR", "SUBTOTAL Rp 100.000 TOTAL Rp 110.000"))
        self.assertEqual(fields["total_amount"], "110000")
        self.assertFalse(fields["total_ambiguous"])

    def test_total_cash_and_change_on_same_line(self):
        fields = extract_fields(ocr_lines("TOKO MAKMUR", "TOTAL 125000 CASH 200000 KEMBALI 75000"))
        self.assertEqual(fields["total_amount"], "125000")
        self.assertFalse(fields["total_ambiguous"])

    def test_all_dates_on_one_line_are_candidates(self):
        fields = extract_fields(ocr_lines("TOKO MAKMUR", "Belanja 12/10/2026 Dicetak 13/10/2026 Rp 125.000"))
        self.assertEqual(fields["date_candidates"], ["2026-10-12", "2026-10-13"])
        self.assertEqual(fields["transaction_date"], "2026-10-12")
        self.assertEqual(find_dates("12 Okt 2026 / 14/10/2026"), ["2026-10-14", "2026-10-12"])


if __name__ == "__main__":
    unittest.main()
