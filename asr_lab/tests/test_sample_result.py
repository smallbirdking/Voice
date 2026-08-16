"""Tests for the per-sample raw experiment result contract."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from voice_asr_lab.cli import main
from voice_asr_lab.experiment.sample_result import load_sample_result, validate_sample_result


class SampleResultTests(unittest.TestCase):
    example_path = Path(__file__).parents[1] / "schemas" / "sample-result.example.json"

    @classmethod
    def setUpClass(cls) -> None:
        cls.example = load_sample_result(cls.example_path)

    def test_success_example_covers_every_raw_fact_group(self) -> None:
        self.assertEqual(validate_sample_result(self.example), [])
        self.assertEqual(self.example["record_type"], "sample_result")
        self.assertEqual(self.example["outcome"], {
            "status": "succeeded",
            "process_exit_code": 0,
            "error": None,
        })
        self.assertTrue(self.example["configuration"])
        self.assertTrue(self.example["resource_sample_refs"])

    def test_schema_requires_environment_model_configuration_text_time_and_resources(self) -> None:
        required_fields = (
            "environment_snapshot_id",
            "model",
            "configuration",
            "transcription",
            "timing",
            "resource_sample_refs",
        )
        for field in required_fields:
            with self.subTest(field=field):
                invalid = copy.deepcopy(self.example)
                invalid.pop(field)
                errors = validate_sample_result(invalid)
                self.assertTrue(any(f"missing required property '{field}'" in error for error in errors))

    def test_failed_result_preserves_structured_error_and_nullable_text(self) -> None:
        failed = copy.deepcopy(self.example)
        failed["transcription"].update(
            {"raw_text": None, "normalized_text": None, "provider_payload": None}
        )
        failed["outcome"] = {
            "status": "failed",
            "process_exit_code": 17,
            "error": {
                "stage": "inference",
                "type": "RuntimeError",
                "code": "synthetic-failure",
                "message": "configured failure",
                "retryable": False,
                "details": {"attempt": 1},
            },
        }

        self.assertEqual(validate_sample_result(failed), [])

    def test_provider_payload_preserves_non_object_native_shapes(self) -> None:
        native_list = copy.deepcopy(self.example)
        native_list["transcription"]["provider_payload"] = [
            {"text": "请举起你的左手。", "confidence": 0.91}
        ]

        self.assertEqual(validate_sample_result(native_list), [])

    def test_success_and_failure_exit_status_rules_are_cross_checked(self) -> None:
        success_with_error = copy.deepcopy(self.example)
        success_with_error["outcome"]["process_exit_code"] = 1
        success_with_error["outcome"]["error"] = {
            "stage": "inference",
            "type": "Unexpected",
            "code": None,
            "message": "must not coexist with success",
            "retryable": False,
            "details": {},
        }
        failure_without_error = copy.deepcopy(self.example)
        failure_without_error["outcome"]["status"] = "timeout"

        success_errors = validate_sample_result(success_with_error)
        failure_errors = validate_sample_result(failure_without_error)

        self.assertTrue(any("succeeded result must not contain an error" in error for error in success_errors))
        self.assertTrue(any("succeeded result must use 0 or null" in error for error in success_errors))
        self.assertTrue(any("requires structured error evidence" in error for error in failure_errors))
        self.assertTrue(any("must not use 0" in error for error in failure_errors))

    def test_monotonic_order_and_derived_durations_are_cross_checked(self) -> None:
        invalid = copy.deepcopy(self.example)
        invalid["timing"]["inference_finished_ns"] = 999_000_000
        invalid["timing"]["inference_duration_ms"] = 99
        invalid["timing"]["total_duration_ms"] = 99

        errors = validate_sample_result(invalid)

        self.assertTrue(any("monotonic points must be non-decreasing" in error for error in errors))
        self.assertTrue(any("inference_duration_ms" in error for error in errors))
        self.assertTrue(any("total_duration_ms" in error for error in errors))

    def test_wall_clock_and_resource_references_are_auditable(self) -> None:
        invalid = copy.deepcopy(self.example)
        invalid["timing"]["finished_at"] = "not-a-time"
        invalid["resource_sample_refs"].append("resource-sample-000001")

        errors = validate_sample_result(invalid)

        self.assertTrue(any("valid UTC timestamp" in error for error in errors))
        self.assertTrue(any("references must be unique" in error for error in errors))

    def test_non_speech_success_uses_empty_text_and_null_normalization_version(self) -> None:
        silence = copy.deepcopy(self.example)
        silence["input"]["language"] = "none"
        silence["input"]["scenario"] = "silence"
        silence["corpus"]["reference_normalization_version"] = None
        silence["transcription"].update(
            {
                "raw_text": "",
                "normalized_text": "",
                "normalization_version": None,
                "detected_language": None,
            }
        )

        self.assertEqual(validate_sample_result(silence), [])

    def test_cli_emits_machine_readable_success_and_load_failure(self) -> None:
        success_output = io.StringIO()
        with redirect_stdout(success_output):
            success_code = main(["validate-sample-result", str(self.example_path)])

        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.json"
            failure_output = io.StringIO()
            with redirect_stderr(failure_output):
                failure_code = main(["validate-sample-result", str(missing_path)])

        self.assertEqual(success_code, 0)
        self.assertEqual(json.loads(success_output.getvalue())["status"], "valid")
        self.assertEqual(failure_code, 2)
        self.assertEqual(json.loads(failure_output.getvalue())["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
