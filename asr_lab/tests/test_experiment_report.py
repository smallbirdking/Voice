"""Tests for complete aggregation including failed sample evidence."""

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
from voice_asr_lab.experiment.report import (
    build_experiment_report,
    load_sample_results_jsonl,
    render_experiment_report_markdown,
    write_experiment_report,
)
from voice_asr_lab.experiment.sample_result import load_sample_result


class ExperimentReportTests(unittest.TestCase):
    root = Path(__file__).parents[1]

    @classmethod
    def setUpClass(cls) -> None:
        cls.success = load_sample_result(cls.root / "schemas" / "sample-result.example.json")
        cls.manifest = load_corpus_manifest(
            cls.root / "corpus" / "manifests" / "voice-asr-eval-v1.json"
        )

    def failed_result(self) -> dict:
        result = copy.deepcopy(self.success)
        result["input"].update(
            {"sample_id": "en-general-speech-001", "language": "en-US", "scenario": "general-speech"}
        )
        result["input"]["audio"]["duration_ms"] = 967
        result["transcription"].update(
            {"raw_text": None, "normalized_text": None, "detected_language": None, "provider_payload": None}
        )
        result["outcome"] = {
            "status": "failed", "process_exit_code": 7,
            "error": {
                "stage": "inference", "type": "SyntheticProviderError",
                "code": "configured-failure", "message": "configured failure",
                "retryable": False, "details": {},
            },
        }
        return result

    def test_failed_sample_is_retained_but_not_fabricated_as_accuracy(self) -> None:
        report = build_experiment_report(
            [self.success, self.failed_result()], self.manifest,
            generated_at="2026-08-16T12:00:01.000000Z",
        )

        self.assertEqual(report["status"], "completed_with_failures")
        self.assertEqual(report["summary"], {
            "sample_count": 2, "succeeded_count": 1, "failed_count": 1,
            "outcome_counts": {"failed": 1, "succeeded": 1},
        })
        self.assertEqual(len(report["samples"]), 2)
        self.assertEqual(report["failures"][0]["sample_id"], "en-general-speech-001")
        self.assertEqual(report["accuracy"]["cer"]["rate"], 0.0)
        self.assertEqual(report["accuracy"]["wer"]["evaluated_samples"], 0)

    def test_markdown_lists_success_and_failure(self) -> None:
        report = build_experiment_report([self.success, self.failed_result()], self.manifest)
        markdown = render_experiment_report_markdown(report)

        self.assertIn("zh-short-command-001", markdown)
        self.assertIn("en-general-speech-001", markdown)
        self.assertIn("configured-failure", markdown)
        self.assertIn("未被静默删除", markdown)

    def test_jsonl_loader_validates_every_line_and_duplicate_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "results.jsonl"
            path.write_text(json.dumps(self.success, ensure_ascii=False) + "\n", encoding="utf-8")
            self.assertEqual(len(load_sample_results_jsonl(path)), 1)
        with self.assertRaisesRegex(ValueError, "identifiers must be unique"):
            build_experiment_report([self.success, self.success], self.manifest)

    def test_writer_and_cli_create_matching_reports_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            results_path = temp / "results.jsonl"
            json_path = temp / "report.json"
            markdown_path = temp / "report.md"
            results_path.write_text(
                "\n".join(
                    json.dumps(item, ensure_ascii=False)
                    for item in (self.success, self.failed_result())
                ) + "\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "aggregate-results", str(results_path),
                        str(self.root / "corpus" / "manifests" / "voice-asr-eval-v1.json"),
                        "--output-json", str(json_path), "--output-markdown", str(markdown_path),
                    ]
                )
            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["failed_count"], 1)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["summary"]["sample_count"], 2)
            self.assertIn("en-general-speech-001", markdown_path.read_text(encoding="utf-8"))
            with self.assertRaises(FileExistsError):
                write_experiment_report(
                    build_experiment_report([self.success], self.manifest), json_path, markdown_path
                )


if __name__ == "__main__":
    unittest.main()
