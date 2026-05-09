from unittest import TestCase

from app.security.rating_input import MAX_REVIEW_CHARS, normalize_review_text, parse_rate_callback_data


class RatingInputTests(TestCase):
    def test_parse_rate_ok(self) -> None:
        self.assertEqual(parse_rate_callback_data("rate:12:345678901:5"), (12, 345678901, 5))

    def test_parse_rate_rejects_bad(self) -> None:
        self.assertIsNone(parse_rate_callback_data("rate:x:1:5"))
        self.assertIsNone(parse_rate_callback_data("rate:1:1:6"))
        self.assertIsNone(parse_rate_callback_data("rate:1:1:0"))
        self.assertIsNone(parse_rate_callback_data("wrong:1:1:5"))

    def test_normalize_review(self) -> None:
        self.assertIsNone(normalize_review_text("  -  "))
        self.assertIsNone(normalize_review_text("\n"))
        self.assertEqual(normalize_review_text("  hello "), "hello")
        long = "a" * (MAX_REVIEW_CHARS + 50)
        self.assertEqual(len(normalize_review_text(long) or ""), MAX_REVIEW_CHARS)
