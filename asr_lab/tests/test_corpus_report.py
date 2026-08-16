"""Tests for retained v1 corpus coverage and quality reports."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from voice_asr_lab.cli import main
from voice_asr_lab.corpus.manifest import load_corpus_manifest
from voice_asr_lab.corpus.report import (
    build_corpus_report,
    render_corpus_report_markdown,
    write_corpus_report,
)
from voice_asr_lab.corpus.preprocessing import preprocess_corpus


class CorpusReportTests(unittest.TestCase):
    lab_root = Path(__file__).parents[1]
    corpus_root = lab_root / "corpus"
    manifest_path = corpus_root / "manifests" / "voice-asr-eval-v1.json"

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_corpus_manifest(cls.manifest_path)
        cls._derived_temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._derived_temp.cleanup)
        cls.derived_root = Path(cls._derived_temp.name)
        preprocess_corpus(cls.manifest, cls.corpus_root, cls.derived_root)

    def test_real_v1_report_has_complete_coverage_and_no_dropped_samples(self) -> None:
        report = build_corpus_report(self.manifest, self.corpus_root, self.derived_root)

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["corpus"]["sample_count"], 7)
        self.assertTrue(report["coverage"]["complete"])
        self.assertTrue(all(report["coverage"]["required"].values()))
        self.assertEqual({sample["sample_id"] for sample in report["samples"]}, {
            sample["sample_id"] for sample in self.manifest["samples"]
        })
        self.assertEqual(report["validation"]["source_audio"]["passed_samples"], 7)
        self.assertEqual(report["validation"]["derived_audio"]["passed_samples"], 7)

    def test_every_derived_sample_has_the_fixed_input_contract_and_digest(self) -> None:
        report = build_corpus_report(self.manifest, self.corpus_root, self.derived_root)
        expected_format = report["validation"]["derived_audio"]["required_format"]

        for sample in report["samples"]:
            with self.subTest(sample_id=sample["sample_id"]):
                facts = sample["derived_audio"]["facts"]
                self.assertEqual(facts["format"], expected_format)
                self.assertRegex(facts["sha256"], r"^[0-9a-f]{64}$")

    def test_markdown_and_json_share_the_same_version_boundary(self) -> None:
        report = build_corpus_report(self.manifest, self.corpus_root, self.derived_root)
        markdown = render_corpus_report_markdown(report)

        self.assertIn(report["corpus"]["corpus_fingerprint"], markdown)
        self.assertIn("样本数：7", markdown)
        self.assertIn("commercial_use_ready=false", markdown)

    def test_bad_source_prevents_a_passing_report(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["samples"][0]["audio"]["sha256"] = "0" * 64

        report = build_corpus_report(invalid, self.corpus_root, self.derived_root)

        self.assertEqual(report["status"], "failed")
        self.assertTrue(any("source: sha256 mismatch" in error for error in report["errors"]))

    def test_writer_checks_both_targets_before_writing_either(self) -> None:
        report = build_corpus_report(self.manifest, self.corpus_root, self.derived_root)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            markdown_path.write_text("keep", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                write_corpus_report(report, json_path, markdown_path)

            self.assertFalse(json_path.exists())
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "keep")

    def test_cli_writes_matching_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main([
                    "report-corpus",
                    str(self.manifest_path),
                    "--derived-root",
                    str(self.derived_root),
                    "--output-json",
                    str(json_path),
                    "--output-markdown",
                    str(markdown_path),
                ])

            payload = json.loads(output.getvalue())
            saved = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["status"], "saved")
            self.assertEqual(saved["corpus"]["corpus_fingerprint"], payload["corpus_fingerprint"])
            self.assertIn(payload["corpus_fingerprint"], markdown)


if __name__ == "__main__":
    unittest.main()
