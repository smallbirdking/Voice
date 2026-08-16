"""Tests that document Chinese reference normalization v1."""

from __future__ import annotations

import unittest

from voice_asr_lab.corpus.text_normalization import NORMALIZATION_VERSION, normalize_chinese


class ChineseNormalizationTests(unittest.TestCase):
    def test_punctuation_and_whitespace_are_removed(self) -> None:
        self.assertEqual(normalize_chinese(" 你 好，世界！\n"), "你好世界")

    def test_latin_case_is_lowered_but_digits_are_retained(self) -> None:
        self.assertEqual(normalize_chinese("ASR版本 2.0"), "asr版本20")

    def test_fullwidth_letters_digits_and_punctuation_use_nfkc(self) -> None:
        self.assertEqual(normalize_chinese("ＡＳＲ１２３，测试。"), "asr123测试")

    def test_no_number_to_spoken_form_rewrite_is_attempted(self) -> None:
        self.assertEqual(normalize_chinese("今天是2026年8月16日"), "今天是2026年8月16日")

    def test_rule_set_has_an_explicit_version(self) -> None:
        self.assertEqual(NORMALIZATION_VERSION, "text-normalization-v1")


if __name__ == "__main__":
    unittest.main()
