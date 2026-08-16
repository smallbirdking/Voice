"""Deterministic tests for monotonic ASR timing boundaries."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from voice_asr_lab.experiment.events import load_stream_events
from voice_asr_lab.experiment.timing import ManualClock, MonotonicTimeline, derive_stream_latencies, format_utc


class TimingTests(unittest.TestCase):
    def test_manual_clock_and_timeline_make_inference_duration_exact(self) -> None:
        clock = ManualClock(1_000_000_000, datetime(2026, 8, 16, tzinfo=timezone.utc))
        timeline = MonotonicTimeline(clock)
        timeline.mark("inference_started")
        clock.advance_ms(37.5)
        timeline.mark("inference_finished")
        self.assertEqual(timeline.duration_ms("inference_started", "inference_finished"), 37.5)
        self.assertEqual(format_utc(clock.utc_now()), "2026-08-16T00:00:00.037500Z")

    def test_manual_clock_rejects_backwards_time_and_duplicate_marks(self) -> None:
        clock = ManualClock()
        timeline = MonotonicTimeline(clock)
        timeline.mark("start")
        with self.assertRaisesRegex(ValueError, "backwards"):
            clock.advance_ms(-1)
        with self.assertRaisesRegex(ValueError, "already exists"):
            timeline.mark("start")

    def test_partial_final_queue_and_inference_boundaries_are_explicit(self) -> None:
        path = Path(__file__).parents[1] / "schemas" / "stream-event.example.jsonl"
        latencies = derive_stream_latencies(load_stream_events(path))
        self.assertEqual(latencies["first_partial_latency_ms"], 50.0)
        self.assertEqual(latencies["queue_latency_ms"], [0.1])
        self.assertEqual(latencies["final_latency_ms"], 20.0)
        self.assertEqual(latencies["inference_duration_ms"], 219.8)

    def test_commit_is_final_start_when_no_vad_endpoint_exists(self) -> None:
        path = Path(__file__).parents[1] / "schemas" / "stream-event.example.jsonl"
        events = [event for event in load_stream_events(path) if event["event_type"] != "vad_endpoint"]
        for sequence, event in enumerate(events):
            event["sequence"] = sequence
        self.assertEqual(derive_stream_latencies(events)["final_latency_ms"], 19.9)


if __name__ == "__main__":
    unittest.main()
