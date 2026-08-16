"""Tests for the preserved machine-readable environment baseline."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from voice_asr_lab.system.baseline import (
    collect_environment_baseline,
    validate_environment_baseline,
    write_environment_baseline,
)
from voice_asr_lab.cli import main


class EnvironmentBaselineTests(unittest.TestCase):
    workspace = Path(__file__).parents[2]
    lab_root = Path(__file__).parents[1]

    def collect(self) -> dict[str, object]:
        return collect_environment_baseline(
            self.workspace,
            captured_at=datetime(2026, 8, 16, 10, 11, 12, tzinfo=timezone.utc),
        )

    def test_collected_baseline_matches_schema_and_nested_probes(self) -> None:
        baseline = self.collect()

        self.assertEqual(validate_environment_baseline(baseline), [])
        self.assertEqual(baseline["project"]["name"], "voice-asr-lab")
        self.assertEqual(baseline["policies"]["network"]["policy_id"], "local-asr-no-cloud-audio")

    def test_content_change_invalidates_environment_snapshot_id(self) -> None:
        baseline = self.collect()
        changed = copy.deepcopy(baseline)
        changed["nvidia"]["status"] = "changed-after-capture"

        errors = validate_environment_baseline(changed)

        self.assertTrue(any("does not match baseline content" in error for error in errors))

    def test_write_round_trip_refuses_to_overwrite_evidence(self) -> None:
        baseline = self.collect()
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "baseline.json"

            saved_path = write_environment_baseline(baseline, output_path)
            loaded = json.loads(saved_path.read_text(encoding="utf-8"))

            self.assertEqual(loaded, baseline)
            with self.assertRaises(FileExistsError):
                write_environment_baseline(baseline, output_path)

    def test_cli_saves_a_valid_baseline_to_an_explicit_path(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "captured.json"

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "capture-baseline",
                        "--workspace",
                        str(self.workspace),
                        "--output",
                        str(output_path),
                    ]
                )

            summary = json.loads(output.getvalue())
            baseline = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(summary["status"], "saved")
            self.assertEqual(validate_environment_baseline(baseline), [])
            self.assertEqual(summary["environment_snapshot_id"], baseline["environment_snapshot_id"])

    def test_cli_does_not_overwrite_an_existing_baseline(self) -> None:
        error_output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "existing.json"
            output_path.write_text("preserve me", encoding="utf-8")

            with redirect_stderr(error_output):
                exit_code = main(["capture-baseline", "--output", str(output_path)])

            payload = json.loads(error_output.getvalue())
            self.assertEqual(exit_code, 2)
            self.assertEqual(payload["status"], "output-exists")
            self.assertEqual(output_path.read_text(encoding="utf-8"), "preserve me")

    def test_retained_first_baseline_and_learning_report_share_one_id(self) -> None:
        baseline_path = self.lab_root / "reports" / "baselines" / "environment-baseline-v1.json"
        report_path = self.lab_root / "reports" / "baselines" / "environment-baseline-v1.md"

        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        report = report_path.read_text(encoding="utf-8")

        self.assertEqual(validate_environment_baseline(baseline), [])
        self.assertIn(baseline["environment_snapshot_id"], report)
        self.assertIn(baseline["source_control"]["head_commit"], report)


if __name__ == "__main__":
    unittest.main()
