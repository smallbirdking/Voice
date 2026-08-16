"""Tests for the versioned host environment snapshot."""

from __future__ import annotations

import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from voice_asr_lab.cli import main
from voice_asr_lab.system.host import (
    _decode_command_output,
    _probe_wsl,
    collect_host_snapshot,
    validate_host_snapshot,
)


class HostEnvironmentTests(unittest.TestCase):
    workspace = Path(__file__).parents[2]

    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = collect_host_snapshot(cls.workspace)

    def test_collected_snapshot_matches_versioned_schema(self) -> None:
        self.assertEqual(validate_host_snapshot(self.snapshot), [])
        self.assertEqual(self.snapshot["schema_version"], "1.0.0")
        self.assertEqual(Path(self.snapshot["disk"]["path"]), self.workspace.resolve())

    def test_schema_rejects_a_missing_required_section(self) -> None:
        invalid_snapshot = copy.deepcopy(self.snapshot)
        invalid_snapshot.pop("python")

        errors = validate_host_snapshot(invalid_snapshot)

        self.assertTrue(any("missing required property 'python'" in error for error in errors))

    def test_wsl_probe_is_explicit_when_executable_is_missing(self) -> None:
        with (
            patch("voice_asr_lab.system.host.platform.system", return_value="Windows"),
            patch("voice_asr_lab.system.host.shutil.which", return_value=None),
        ):
            result = _probe_wsl()

        self.assertEqual(result["status"], "not-installed")
        self.assertIsNone(result["wsl2_detected"])

    def test_utf16_wsl_output_is_decoded_before_json_serialization(self) -> None:
        message = "拒绝访问。\r\n错误代码: Wsl/Service/E_ACCESSDENIED"

        self.assertEqual(_decode_command_output(message.encode("utf-16-le")), message)

    def test_cli_emits_the_schema_valid_snapshot(self) -> None:
        output = io.StringIO()

        with (
            patch("voice_asr_lab.commands.system.collect_host_snapshot", return_value=self.snapshot),
            redirect_stdout(output),
        ):
            exit_code = main(["probe-host", "--workspace", str(self.workspace)])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue()), self.snapshot)


if __name__ == "__main__":
    unittest.main()
