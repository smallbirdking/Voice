"""Hand-checkable tests for ASR derived metrics."""

from __future__ import annotations

import unittest

from voice_asr_lab.experiment.metrics import (
    character_error_rate,
    compute_sample_metrics,
    keyword_hits,
    mixed_error_rate,
    realtime_factor,
    silence_false_recognition,
    word_error_rate,
)


class MetricTests(unittest.TestCase):
    def test_cer_has_one_deletion_over_four_reference_characters(self) -> None:
        result = character_error_rate("你好世界", "你好世")
        self.assertEqual(result["edit_distance"], 1)
        self.assertEqual(result["deletions"], 1)
        self.assertEqual(result["rate"], 0.25)

    def test_wer_has_one_deletion_and_one_substitution(self) -> None:
        result = word_error_rate("raise your left hand", "raise left hands")
        self.assertEqual(result["edit_distance"], 2)
        self.assertEqual(result["reference_units"], 4)
        self.assertEqual(result["rate"], 0.5)
        self.assertEqual(result["deletions"] + result["substitutions"] + result["insertions"], 2)

    def test_mixed_error_counts_han_characters_and_latin_words(self) -> None:
        result = mixed_error_rate("请打开 meeting", "请打开 mode")
        self.assertEqual(result["reference_units"], 4)
        self.assertEqual(result["edit_distance"], 1)
        self.assertEqual(result["rate"], 0.25)

    def test_keyword_matching_uses_units_not_accidental_substrings(self) -> None:
        result = keyword_hits("please raise your left hand", ("raise", "left hand", "and"))
        self.assertEqual(result["hit_count"], 2)
        self.assertFalse(result["all_hit"])
        self.assertFalse(result["details"][-1]["hit"])

    def test_silence_false_recognition_and_realtime_factor_are_explicit(self) -> None:
        self.assertEqual(
            silence_false_recognition(" noise "),
            {"false_recognition": True, "recognized_character_count": 5},
        )
        self.assertEqual(realtime_factor(500, 2_000), 0.25)
        with self.assertRaisesRegex(ValueError, "positive"):
            realtime_factor(1, 0)

    def test_sample_metric_selects_language_and_scenario_specific_outputs(self) -> None:
        result = compute_sample_metrics(
            language="zh-CN",
            scenario="short-command",
            reference="请举起左手",
            hypothesis="请举起左手",
            audio_duration_ms=1_000,
            inference_duration_ms=100,
            keywords=("举起", "左手"),
        )
        self.assertEqual(result["cer"]["rate"], 0.0)
        self.assertIsNone(result["wer"])
        self.assertTrue(result["keyword"]["all_hit"])
        self.assertEqual(result["realtime_factor"], 0.1)


if __name__ == "__main__":
    unittest.main()
