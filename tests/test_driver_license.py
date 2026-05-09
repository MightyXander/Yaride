from __future__ import annotations

from datetime import date
from unittest import TestCase

from app.driver_license import (
    normalize_dl_series_number,
    parse_expiry_date,
    validate_license_not_expired,
)


class DriverLicenseTests(TestCase):
    def test_normalize_valid_compact(self) -> None:
        ok, norm, err = normalize_dl_series_number("9916АВ123456")
        self.assertTrue(ok)
        self.assertEqual(norm, "9916АВ123456")
        self.assertIsNone(err)

    def test_normalize_latin_letters(self) -> None:
        ok, norm, err = normalize_dl_series_number("9916AB123456")
        self.assertTrue(ok)
        self.assertEqual(norm, "9916АВ123456")
        self.assertIsNone(err)

    def test_normalize_with_spaces(self) -> None:
        ok, norm, err = normalize_dl_series_number("99 16 АВ 123 456")
        self.assertTrue(ok)
        self.assertEqual(norm, "9916АВ123456")

    def test_reject_wrong_length(self) -> None:
        ok, norm, err = normalize_dl_series_number("9916АВ12345")
        self.assertFalse(ok)
        self.assertIsNone(norm)
        self.assertIsNotNone(err)

    def test_reject_digits_instead_of_letters(self) -> None:
        ok, norm, err = normalize_dl_series_number("991677123456")
        self.assertFalse(ok)
        self.assertIsNone(norm)

    def test_parse_expiry(self) -> None:
        ok, d, err = parse_expiry_date("31.12.2030")
        self.assertTrue(ok)
        self.assertEqual(d, date(2030, 12, 31))
        self.assertIsNone(err)

    def test_validate_not_expired(self) -> None:
        ok, err = validate_license_not_expired(date(2030, 1, 1), today=date(2026, 1, 1))
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_validate_expired(self) -> None:
        ok, err = validate_license_not_expired(date(2020, 1, 1), today=date(2026, 1, 1))
        self.assertFalse(ok)
        self.assertIsNotNone(err)
