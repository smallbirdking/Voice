"""Tests for mixed-language normalization and manifest evidence."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from voice_asr_lab.corpus.manifest import load_corpus_manifest, validate_corpus_manifest
from voice_asr_lab.corpus.text_normalization import normalize_manifest_references, normalize_mixed


class MixedNormalizationTests(unittest.TestCase):
    manifest_path = Path(__file__).parents[1] / "corpus" / "manifests" / "voice-asr-eval-v1.json"

    def test_mixed_text_retains_original_normalized_and_language_segments(self) -> None:
        result = normalize_mixed("你好，Voice ASR! 请继续。")

        self.assertEqual(result["original"], "你好，Voice ASR! 请继续。")
        self.assertEqual(result["normalized"], "你好 voice asr 请继续")
        self.assertEqual([segment["language"] for segment in result["segments"]], ["zh", "en", "zh"])
        self.assertEqual(
            "".join(segment["original"] for segment in result["segments"]),
            result["original"],
        )
        for segment in result["segments"]:
            self.assertEqual(
                result["original"][segment["start"] : segment["end"]],
                segment["original"],
            )

    def test_manifest_enrichment_preserves_original_input(self) -> None:
        original = load_corpus_manifest(self.manifest_path)
        without_derived_references = copy.deepcopy(original)
        for sample in without_derived_references["samples"]:
            sample["reference"].pop("normalized_text")
            sample["reference"].pop("language_segments")

        enriched = normalize_manifest_references(without_derived_references)

        self.assertNotIn("normalized_text", without_derived_references["samples"][0]["reference"])
        self.assertEqual(enriched, original)

    def test_v1_mixed_sample_keeps_both_language_statistics_inputs(self) -> None:
        manifest = load_corpus_manifest(self.manifest_path)
        sample = next(sample for sample in manifest["samples"] if sample["language"] == "zh-en")

        self.assertEqual(sample["reference"]["normalized_text"], "请举起你的左手 please respond")
        self.assertEqual(
            {segment["language"] for segment in sample["reference"]["language_segments"]},
            {"zh", "en"},
        )
        self.assertEqual(validate_corpus_manifest(manifest), [])

    def test_manifest_validation_detects_stale_normalized_or_segment_data(self) -> None:
        manifest = load_corpus_manifest(self.manifest_path)
        manifest["samples"][0]["reference"]["normalized_text"] = "stale"
        manifest["samples"][4]["reference"]["language_segments"][0]["end"] = 1

        errors = validate_corpus_manifest(manifest)

        self.assertTrue(any("normalized_text: does not match" in error for error in errors))
        self.assertTrue(any("language_segments: do not match" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
