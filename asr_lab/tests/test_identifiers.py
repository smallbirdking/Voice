"""Tests for joining all evidence produced by one ASR experiment run."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone

from voice_asr_lab.cli import main
from voice_asr_lab.core.identifiers import (
    create_environment_snapshot_id,
    create_run_context,
    create_run_id,
    link_record,
    validate_run_context,
    validate_run_linkage,
)


class RunIdentifierTests(unittest.TestCase):
    environment_snapshot = {
        "schema_version": "1.0.0",
        "host": {"platform": "Windows", "python": "3.14.7"},
        "nvidia": {"gpu": "RTX 5060 Ti", "driver": "596.36"},
    }

    def create_context(self) -> dict[str, str]:
        return create_run_context(
            self.environment_snapshot,
            now=datetime(2026, 8, 16, 9, 10, 11, 123456, tzinfo=timezone.utc),
            entropy="a1b2c3d4e5f6",
        )

    def test_environment_id_is_stable_across_mapping_order(self) -> None:
        reordered = {
            "nvidia": self.environment_snapshot["nvidia"],
            "host": self.environment_snapshot["host"],
            "schema_version": "1.0.0",
        }

        self.assertEqual(
            create_environment_snapshot_id(self.environment_snapshot),
            create_environment_snapshot_id(reordered),
        )

    def test_environment_id_changes_when_snapshot_content_changes(self) -> None:
        changed = {**self.environment_snapshot, "nvidia": {"driver": "different"}}

        self.assertNotEqual(
            create_environment_snapshot_id(self.environment_snapshot),
            create_environment_snapshot_id(changed),
        )

    def test_run_id_has_a_deterministic_injectable_format(self) -> None:
        run_id = create_run_id(
            now=datetime(2026, 8, 16, 9, 10, 11, 123456, tzinfo=timezone.utc),
            entropy="a1b2c3d4e5f6",
        )

        self.assertEqual(run_id, "run-20260816T091011123456Z-a1b2c3d4e5f6")

    def test_run_context_matches_its_versioned_schema(self) -> None:
        self.assertEqual(validate_run_context(self.create_context()), [])

        invalid = {**self.create_context(), "run_id": "run-not-valid"}
        self.assertTrue(validate_run_context(invalid))

    def test_sample_resource_and_report_records_link_to_one_run(self) -> None:
        context = self.create_context()
        records = [
            link_record("sample_result", {"sample_id": "zh-001"}, context),
            link_record("resource_sample", {"sequence": 0}, context),
            link_record("report", {"sample_count": 1}, context),
        ]

        self.assertEqual(
            validate_run_linkage(context, self.environment_snapshot, records),
            [],
        )

    def test_linkage_rejects_cross_run_and_missing_records(self) -> None:
        context = self.create_context()
        sample = link_record("sample_result", {"sample_id": "zh-001"}, context)
        sample["run_id"] = "run-20260816T091011123456Z-000000000000"

        errors = validate_run_linkage(context, self.environment_snapshot, [sample])

        self.assertTrue(any("does not match the run context" in error for error in errors))
        self.assertTrue(any("missing required types" in error for error in errors))

    def test_cli_emits_a_valid_real_environment_linkage_demo(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["demo-run-linkage"])

        payload = json.loads(output.getvalue())
        context = payload["run_context"]
        environment_snapshot = payload["environment_snapshot"]
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["linkage_errors"], [])
        self.assertEqual(
            environment_snapshot["environment_snapshot_id"],
            context["environment_snapshot_id"],
        )
        self.assertEqual(
            validate_run_linkage(context, environment_snapshot["content"], payload["linked_records"]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
