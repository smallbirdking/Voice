"""Tests for the versioned corpus manifest input contract."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from voice_asr_lab.cli import main
from voice_asr_lab.corpus.manifest import load_corpus_manifest, validate_corpus_manifest


class CorpusManifestTests(unittest.TestCase):
    lab_root = Path(__file__).parents[1]
    example_path = lab_root / "corpus" / "manifests" / "schema-example.json"
    v1_path = lab_root / "corpus" / "manifests" / "voice-asr-eval-v1.json"

    @classmethod
    def setUpClass(cls) -> None:
        cls.example = load_corpus_manifest(cls.example_path)

    def test_example_covers_speech_and_non_speech_contracts(self) -> None:
        self.assertEqual(validate_corpus_manifest(self.example), [])
        self.assertEqual(self.example["schema_version"], "1.0.0")
        self.assertEqual(len(self.example["samples"]), 2)

    def test_schema_requires_audio_digest_and_rejects_extra_fields(self) -> None:
        missing_digest = copy.deepcopy(self.example)
        missing_digest["samples"][0]["audio"].pop("sha256")
        unexpected_field = copy.deepcopy(self.example)
        unexpected_field["samples"][0]["provider_hint"] = "must-not-enter-input-contract"

        missing_errors = validate_corpus_manifest(missing_digest)
        extra_errors = validate_corpus_manifest(unexpected_field)

        self.assertTrue(any("missing required property 'sha256'" in error for error in missing_errors))
        self.assertTrue(any("unexpected property 'provider_hint'" in error for error in extra_errors))

    def test_versioned_manifest_cannot_be_empty(self) -> None:
        empty = copy.deepcopy(self.example)
        empty["samples"] = []

        errors = validate_corpus_manifest(empty)

        self.assertTrue(any("array has fewer than 1 items" in error for error in errors))

    def test_sample_ids_must_be_unique(self) -> None:
        duplicate = copy.deepcopy(self.example)
        duplicate["samples"][1]["sample_id"] = duplicate["samples"][0]["sample_id"]

        errors = validate_corpus_manifest(duplicate)

        self.assertTrue(any("duplicate sample_id" in error for error in errors))

    def test_audio_paths_cannot_escape_corpus_source(self) -> None:
        for unsafe_path in (
            "source/../outside.wav",
            "source//duplicate-separator.wav",
            "source/./normalized-away.wav",
            "C:/outside.wav",
            "source\\outside.wav",
        ):
            with self.subTest(unsafe_path=unsafe_path):
                invalid = copy.deepcopy(self.example)
                invalid["samples"][0]["audio"]["path"] = unsafe_path

                errors = validate_corpus_manifest(invalid)

                self.assertTrue(any("audio.path" in error for error in errors))

    def test_speech_requires_language_text_and_normalization_version(self) -> None:
        invalid = copy.deepcopy(self.example)
        sample = invalid["samples"][0]
        sample["language"] = "none"
        sample["reference"] = {"text": "   ", "normalization_version": None}

        errors = validate_corpus_manifest(invalid)

        self.assertTrue(any("speech sample must declare a language" in error for error in errors))
        self.assertTrue(any("requires non-blank text" in error for error in errors))
        self.assertTrue(any("requires a version" in error for error in errors))

    def test_non_speech_requires_null_reference_fields(self) -> None:
        invalid = copy.deepcopy(self.example)
        sample = invalid["samples"][1]
        sample["language"] = "zh-CN"
        sample["reference"] = {
            "text": "不应存在的参考文字",
            "normalization_version": "reference-normalization-v1",
        }

        errors = validate_corpus_manifest(invalid)

        self.assertTrue(any("non-speech sample must use 'none'" in error for error in errors))
        self.assertTrue(any("must use null text" in error for error in errors))

    def test_cli_reports_valid_manifest_without_reading_audio(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["validate-corpus-manifest", str(self.example_path)])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "valid")
        self.assertEqual(payload["sample_count"], 2)
        self.assertEqual(payload["errors"], [])

    def test_cli_returns_machine_readable_error_for_invalid_json(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "invalid.json"
            invalid_path.write_text("{not-json", encoding="utf-8")

            with redirect_stderr(output):
                exit_code = main(["validate-corpus-manifest", str(invalid_path)])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "invalid")
        self.assertTrue(payload["errors"])

    def test_v1_manifest_covers_required_languages_and_scenarios(self) -> None:
        manifest = load_corpus_manifest(self.v1_path)

        self.assertEqual(validate_corpus_manifest(manifest), [])
        self.assertEqual({sample["language"] for sample in manifest["samples"]}, {"zh-CN", "en-US", "zh-en", "none"})
        self.assertTrue(
            {"general-speech", "long-form", "short-command", "silence", "noise-only"}.issubset(
                {sample["scenario"] for sample in manifest["samples"]}
            )
        )

    def test_v1_manifest_registers_license_evidence_for_every_sample(self) -> None:
        manifest = load_corpus_manifest(self.v1_path)

        for sample in manifest["samples"]:
            with self.subTest(sample_id=sample["sample_id"]):
                license_record = sample["source"]["license"]
                self.assertTrue(license_record["identifier"])
                self.assertTrue(license_record["evidence"])

        restricted = {
            sample["sample_id"]
            for sample in manifest["samples"]
            if sample["source"]["license"]["redistribution"] == "restricted"
        }
        self.assertEqual(restricted, {"zh-short-command-001", "zh-long-form-001", "zh-en-mixed-001"})


if __name__ == "__main__":
    unittest.main()
