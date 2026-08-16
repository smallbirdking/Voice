"""Tests for corpus audio-to-manifest consistency checks."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from voice_asr_lab.corpus.audio_validation import check_corpus_audio
from voice_asr_lab.cli import main
from voice_asr_lab.corpus.manifest import load_corpus_manifest


class AudioValidationTests(unittest.TestCase):
    lab_root = Path(__file__).parents[1]
    corpus_root = lab_root / "corpus"
    manifest_path = corpus_root / "manifests" / "voice-asr-eval-v1.json"

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_corpus_manifest(cls.manifest_path)

    def test_retained_v1_audio_matches_every_manifest_declaration(self) -> None:
        report = check_corpus_audio(self.manifest, self.corpus_root)

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["sample_count"], 7)
        self.assertEqual(report["passed_samples"], 7)
        self.assertEqual(report["failed_samples"], 0)

    def test_missing_file_names_the_sample_and_relative_path(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["samples"][0]["audio"]["path"] = "source/not-present.wav"

        report = check_corpus_audio(invalid, self.corpus_root)

        sample = report["samples"][0]
        self.assertEqual(sample["sample_id"], "zh-short-command-001")
        self.assertTrue(any("does not exist: source/not-present.wav" in error for error in sample["errors"]))

    def test_digest_and_media_mismatches_have_separate_reasons(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        audio = invalid["samples"][0]["audio"]
        audio["sha256"] = "0" * 64
        audio["format"]["sample_rate_hz"] = 16_000
        audio["format"]["channels"] = 2
        audio["duration_ms"] = 1

        report = check_corpus_audio(invalid, self.corpus_root)
        errors = report["samples"][0]["errors"]

        self.assertTrue(any(error.startswith("sha256 mismatch") for error in errors))
        self.assertTrue(any(error.startswith("format.sample_rate_hz mismatch") for error in errors))
        self.assertTrue(any(error.startswith("format.channels mismatch") for error in errors))
        self.assertTrue(any(error.startswith("duration_ms mismatch") for error in errors))

    def test_malformed_wave_is_reported_instead_of_raising(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "source").mkdir()
            (root / "source" / "bad.wav").write_bytes(b"not-a-wave")
            invalid["samples"] = [invalid["samples"][0]]
            invalid["samples"][0]["audio"]["path"] = "source/bad.wav"

            report = check_corpus_audio(invalid, root)

        self.assertTrue(any("unable to inspect PCM WAV" in error for error in report["samples"][0]["errors"]))

    def test_cli_emits_machine_readable_success_and_failure(self) -> None:
        success_output = io.StringIO()
        with redirect_stdout(success_output):
            success_code = main(["check-corpus-audio", str(self.manifest_path)])

        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "missing.json"
            failure_output = io.StringIO()
            with redirect_stderr(failure_output):
                failure_code = main(["check-corpus-audio", str(invalid_path)])

        self.assertEqual(success_code, 0)
        self.assertEqual(json.loads(success_output.getvalue())["status"], "passed")
        self.assertEqual(failure_code, 2)
        self.assertEqual(json.loads(failure_output.getvalue())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
