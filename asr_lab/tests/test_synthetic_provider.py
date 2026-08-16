"""Tests for deterministic success, failure, and cancellation provider behavior."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from voice_asr_lab.experiment.events import validate_stream_events
from voice_asr_lab.experiment.synthetic_provider import (
    SyntheticProvider,
    SyntheticProviderConfig,
    SyntheticRunContext,
)
from voice_asr_lab.experiment.timing import ManualClock, derive_stream_latencies


CONTEXT = SyntheticRunContext(
    run_id="run-20260816T120000000000Z-a1b2c3d4e5f6",
    environment_snapshot_id="env-sha256-" + "1" * 64,
    sample_id="zh-short-command-001",
    session_id="session-synthetic-001",
)


def run_provider(config: SyntheticProviderConfig):
    clock = ManualClock(1_000_000_000, datetime(2026, 8, 16, tzinfo=timezone.utc))
    return SyntheticProvider(config, clock).run(CONTEXT, audio=b"\x00" * 6400, audio_duration_ms=200)


class SyntheticProviderTests(unittest.TestCase):
    def test_success_is_deterministic_and_has_configured_delays(self) -> None:
        config = SyntheticProviderConfig(
            partial_texts=("请", "请举起"), final_text="请举起你的左手。",
            queue_delay_ms=2, partial_interval_ms=10, endpoint_delay_ms=5, final_delay_ms=8,
        )
        first = run_provider(config)
        second = run_provider(config)

        self.assertEqual(first, second)
        self.assertEqual(first.status, "succeeded")
        self.assertEqual(validate_stream_events(first.events), [])
        latencies = derive_stream_latencies(first.events)
        self.assertEqual(latencies["queue_latency_ms"], [2.0])
        self.assertEqual(latencies["first_partial_latency_ms"], 12.0)
        self.assertEqual(latencies["final_latency_ms"], 8.0)

    def test_configured_failure_has_structured_error_and_closed_stream(self) -> None:
        result = run_provider(SyntheticProviderConfig(fail_at="final"))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "synthetic-failure")
        self.assertEqual(result.events[-2]["event_type"], "cancelled")
        self.assertEqual(result.events[-1]["event_type"], "closed")
        self.assertEqual(validate_stream_events(result.events), [])

    def test_configured_cancellation_stops_after_requested_partial(self) -> None:
        result = run_provider(
            SyntheticProviderConfig(partial_texts=("one", "two"), cancel_after_partials=1)
        )

        self.assertEqual(result.status, "cancelled")
        self.assertEqual([event["event_type"] for event in result.events].count("partial"), 1)
        self.assertNotIn("final", [event["event_type"] for event in result.events])
        self.assertEqual(validate_stream_events(result.events), [])

    def test_invalid_configuration_is_rejected_before_running(self) -> None:
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            SyntheticProviderConfig(fail_at="final", cancel_after_partials=0)
        with self.assertRaisesRegex(ValueError, "must not be negative"):
            SyntheticProviderConfig(queue_delay_ms=-1)


if __name__ == "__main__":
    unittest.main()
