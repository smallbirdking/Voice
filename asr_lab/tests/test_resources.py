"""Tests for resource sampling and failure preservation."""

from __future__ import annotations

import unittest

from voice_asr_lab.experiment.resources import (
    ResourceSampler,
    probe_current_process,
    validate_resource_sample,
)
from voice_asr_lab.experiment.timing import ManualClock


CONTEXT = {
    "run_id": "run-20260816T120000000000Z-a1b2c3d4e5f6",
    "environment_snapshot_id": "env-sha256-" + "2" * 64,
    "provider_id": "synthetic",
    "session_id": "session-resource-001",
    "sample_id": "zh-short-command-001",
}


class ResourceTests(unittest.TestCase):
    def test_cpu_memory_and_gpu_samples_are_linked_and_delta_based(self) -> None:
        readings = iter(((100_000_000, 10_000), (130_000_000, 12_000)))
        gpu = lambda: [{
            "index": 0, "uuid": "GPU-test", "utilization_percent": 12.0,
            "memory_used_mib": 256.0, "memory_free_mib": 16_000.0,
        }]
        clock = ManualClock(1_000_000_000)
        sampler = ResourceSampler(clock, process_probe=lambda: next(readings), gpu_probe=gpu)

        first = sampler.sample(CONTEXT)
        clock.advance_ms(100)
        second = sampler.sample(CONTEXT)

        self.assertEqual(validate_resource_sample(first), [])
        self.assertEqual(validate_resource_sample(second), [])
        self.assertIsNone(first["cpu"]["percent_since_previous"])
        self.assertEqual(second["cpu"]["percent_since_previous"], 30.0)
        self.assertEqual(second["process"]["memory_rss_bytes"], 12_000)
        self.assertEqual(second["resource_sample_id"], "resource-sample-000002")

    def test_probe_failures_become_evidence_and_do_not_raise(self) -> None:
        def fail_process():
            raise PermissionError("process denied")

        def fail_gpu():
            raise RuntimeError("gpu unavailable")

        sample = ResourceSampler(
            ManualClock(), process_probe=fail_process, gpu_probe=fail_gpu
        ).sample(CONTEXT)

        self.assertEqual(validate_resource_sample(sample), [])
        self.assertIsNone(sample["cpu"]["process_time_ms"])
        self.assertIsNone(sample["process"]["memory_rss_bytes"])
        self.assertEqual(sample["gpu"]["status"], "error")
        self.assertEqual({error["collector"] for error in sample["errors"]}, {"process", "gpu"})

    def test_missing_nvidia_tool_is_unavailable_not_an_exception(self) -> None:
        def missing_gpu():
            raise FileNotFoundError("nvidia-smi")

        sample = ResourceSampler(
            ManualClock(), process_probe=lambda: (0, 1), gpu_probe=missing_gpu
        ).sample(CONTEXT)

        self.assertEqual(sample["gpu"]["status"], "unavailable")
        self.assertEqual(validate_resource_sample(sample), [])

    def test_real_process_probe_returns_cpu_time_and_rss(self) -> None:
        cpu_time_ns, memory_rss_bytes = probe_current_process()

        self.assertGreaterEqual(cpu_time_ns, 0)
        self.assertGreater(memory_rss_bytes, 0)


if __name__ == "__main__":
    unittest.main()
