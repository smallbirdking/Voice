"""Tests for content-addressed corpus version boundaries."""

from __future__ import annotations

import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from voice_asr_lab.cli import main
from voice_asr_lab.corpus.fingerprint import compute_corpus_fingerprint
from voice_asr_lab.corpus.manifest import load_corpus_manifest, validate_corpus_manifest


class CorpusFingerprintTests(unittest.TestCase):
    manifest_path = Path(__file__).parents[1] / "corpus" / "manifests" / "voice-asr-eval-v1.json"

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_corpus_manifest(cls.manifest_path)

    def test_stored_v1_fingerprint_matches_content_and_cli(self) -> None:
        expected = compute_corpus_fingerprint(self.manifest)
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(["fingerprint-corpus-manifest", str(self.manifest_path)])

        self.assertEqual(self.manifest["corpus_fingerprint"], expected)
        self.assertEqual(validate_corpus_manifest(self.manifest), [])
        self.assertEqual(exit_code, 0)
        self.assertTrue(json.loads(output.getvalue())["matches"])

    def test_audio_reference_tag_and_normalization_changes_get_new_fingerprints(self) -> None:
        original = compute_corpus_fingerprint(self.manifest)
        mutations = []

        audio = copy.deepcopy(self.manifest)
        audio["samples"][0]["audio"]["sha256"] = "0" * 64
        mutations.append(audio)

        reference = copy.deepcopy(self.manifest)
        reference["samples"][0]["reference"]["text"] += "新增"
        mutations.append(reference)

        tag = copy.deepcopy(self.manifest)
        tag["samples"][0]["scenario"] = "general-speech"
        mutations.append(tag)

        normalization = copy.deepcopy(self.manifest)
        normalization["samples"][0]["reference"]["normalization_version"] = "text-normalization-v2"
        mutations.append(normalization)

        fingerprints = {compute_corpus_fingerprint(mutation) for mutation in mutations}
        self.assertEqual(len(fingerprints), 4)
        self.assertNotIn(original, fingerprints)

    def test_timestamp_and_human_version_label_do_not_fake_content_change(self) -> None:
        relabeled = copy.deepcopy(self.manifest)
        relabeled["created_at"] = "2030-01-01T00:00:00Z"
        relabeled["corpus_version"] = "v2"

        self.assertEqual(
            compute_corpus_fingerprint(relabeled),
            compute_corpus_fingerprint(self.manifest),
        )

    def test_json_key_order_does_not_change_fingerprint(self) -> None:
        reversed_manifest = dict(reversed(list(self.manifest.items())))
        self.assertEqual(
            compute_corpus_fingerprint(reversed_manifest),
            compute_corpus_fingerprint(self.manifest),
        )


if __name__ == "__main__":
    unittest.main()
