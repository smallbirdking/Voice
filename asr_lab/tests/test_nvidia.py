"""Tests for NVIDIA visibility and graceful no-GPU behavior."""

from __future__ import annotations

import copy
import io
import json
import subprocess
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from voice_asr_lab.cli import main
from voice_asr_lab.system.nvidia import collect_nvidia_snapshot, validate_nvidia_snapshot


NO_TOOLKIT = {
    "status": "not-installed",
    "executable": None,
    "version": None,
    "details": "nvcc was not found on PATH or under CUDA_PATH.",
}


class NvidiaEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = collect_nvidia_snapshot()

    def test_collected_snapshot_matches_versioned_schema(self) -> None:
        self.assertEqual(validate_nvidia_snapshot(self.snapshot), [])
        self.assertEqual(self.snapshot["schema_version"], "1.0.0")

    def test_schema_rejects_missing_visibility(self) -> None:
        invalid_snapshot = copy.deepcopy(self.snapshot)
        invalid_snapshot.pop("visibility")

        errors = validate_nvidia_snapshot(invalid_snapshot)

        self.assertTrue(any("missing required property 'visibility'" in error for error in errors))

    def test_no_nvidia_smi_produces_a_valid_no_gpu_result(self) -> None:
        with (
            patch("voice_asr_lab.system.nvidia._find_nvidia_smi", return_value=None),
            patch("voice_asr_lab.system.nvidia._probe_nvcc", return_value=NO_TOOLKIT),
        ):
            snapshot = collect_nvidia_snapshot()

        self.assertEqual(snapshot["status"], "not-installed")
        self.assertEqual(snapshot["gpus"], [])
        self.assertFalse(snapshot["visibility"]["nvidia_smi_visible"])
        self.assertEqual(validate_nvidia_snapshot(snapshot), [])

    def test_successful_query_records_gpu_memory_driver_and_cuda(self) -> None:
        query_result = SimpleNamespace(
            returncode=0,
            stdout=b"0, GPU-test, NVIDIA Test GPU, 555.42, 16384, 15000\r\n",
            stderr=b"",
        )
        summary_result = SimpleNamespace(
            returncode=0,
            stdout=b"Driver Version: 555.42 CUDA Version: 12.5",
            stderr=b"",
        )

        with (
            patch("voice_asr_lab.system.nvidia._find_nvidia_smi", return_value="nvidia-smi"),
            patch("voice_asr_lab.system.nvidia._probe_nvcc", return_value=NO_TOOLKIT),
            patch("voice_asr_lab.system.nvidia.subprocess.run", side_effect=[query_result, summary_result]),
        ):
            snapshot = collect_nvidia_snapshot()

        self.assertEqual(snapshot["status"], "available")
        self.assertEqual(snapshot["nvidia_smi"]["driver_supported_cuda_version"], "12.5")
        self.assertEqual(snapshot["gpus"][0]["driver_version"], "555.42")
        self.assertEqual(snapshot["gpus"][0]["memory_total_mib"], 16384)
        self.assertEqual(validate_nvidia_snapshot(snapshot), [])

    def test_query_timeout_is_recorded_instead_of_raised(self) -> None:
        with (
            patch("voice_asr_lab.system.nvidia._find_nvidia_smi", return_value="nvidia-smi"),
            patch("voice_asr_lab.system.nvidia._probe_nvcc", return_value=NO_TOOLKIT),
            patch(
                "voice_asr_lab.system.nvidia.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["nvidia-smi"], timeout=10),
            ),
        ):
            snapshot = collect_nvidia_snapshot()

        self.assertEqual(snapshot["status"], "timeout")
        self.assertTrue(snapshot["errors"])
        self.assertEqual(validate_nvidia_snapshot(snapshot), [])

    def test_cli_emits_a_schema_valid_snapshot(self) -> None:
        output = io.StringIO()

        with (
            patch("voice_asr_lab.commands.system.collect_nvidia_snapshot", return_value=self.snapshot),
            redirect_stdout(output),
        ):
            exit_code = main(["probe-nvidia"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue()), self.snapshot)


if __name__ == "__main__":
    unittest.main()
