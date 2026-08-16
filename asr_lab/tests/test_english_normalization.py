"""Tests that document English reference normalization v1."""

from __future__ import annotations

import unittest

from voice_asr_lab.corpus.text_normalization import normalize_english


class EnglishNormalizationTests(unittest.TestCase):
    def test_case_punctuation_and_whitespace_become_stable_tokens(self) -> None:
        self.assertEqual(
            normalize_english("  Hello,   WORLD!\nPlease respond. "),
            "hello world please respond",
        )

    def test_internal_apostrophes_and_curly_apostrophes_are_preserved(self) -> None:
        self.assertEqual(normalize_english("Don't say it isn’t ready."), "don't say it isn't ready")

    def test_letter_abbreviation_periods_are_removed(self) -> None:
        self.assertEqual(
            normalize_english("The U.S.A. awarded a Ph.D."),
            "the usa awarded a phd",
        )

    def test_hyphens_split_words_and_decimal_punctuation_splits_digits(self) -> None:
        self.assertEqual(normalize_english("REAL-TIME version 2.0"), "real time version 2 0")

    def test_fullwidth_compatibility_characters_use_nfkc(self) -> None:
        self.assertEqual(normalize_english("ＨＥＬＬＯ　１２３！"), "hello 123")


if __name__ == "__main__":
    unittest.main()
