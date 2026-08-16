"""Tests for versioned, ordered streaming fact events."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from voice_asr_lab.cli import main
from voice_asr_lab.experiment.events import (
    EVENT_TYPES,
    empty_event_payload,
    load_stream_events,
    validate_stream_event,
    validate_stream_events,
)


class StreamEventTests(unittest.TestCase):
    example_path = Path(__file__).parents[1] / "schemas" / "stream-event.example.jsonl"

    @classmethod
    def setUpClass(cls) -> None:
        cls.events = load_stream_events(cls.example_path)

    def test_success_example_is_ordered_linked_and_closed(self) -> None:
        self.assertEqual(validate_stream_events(self.events), [])
        self.assertEqual(self.events[0]["event_type"], "audio_received")
        self.assertEqual(self.events[-1]["event_type"], "closed")

    def test_schema_enum_covers_every_required_fact_type(self) -> None:
        self.assertEqual(
            set(EVENT_TYPES),
            {
                "audio_received", "enqueued", "consumption_started", "partial",
                "vad_endpoint", "segment_committed", "final", "cancelled", "closed",
            },
        )

    def test_event_specific_payload_is_required(self) -> None:
        invalid = copy.deepcopy(self.events[3])
        invalid["payload"]["text"] = ""
        errors = validate_stream_event(invalid)
        self.assertTrue(any("partial text must be non-empty" in error for error in errors))

    def test_final_may_be_empty_for_a_successful_non_speech_sample(self) -> None:
        final = copy.deepcopy(self.events[6])
        final["payload"]["text"] = ""

        self.assertEqual(validate_stream_event(final), [])

    def test_sequence_time_linkage_and_terminal_close_are_cross_checked(self) -> None:
        invalid = copy.deepcopy(self.events)
        invalid[2]["sequence"] = 7
        invalid[3]["monotonic_ns"] = 1
        invalid[4]["session_id"] = "session-other"
        invalid.pop()
        errors = validate_stream_events(invalid)
        self.assertTrue(any("contiguous order" in error for error in errors))
        self.assertTrue(any("non-decreasing" in error for error in errors))
        self.assertTrue(any("session_id" in error for error in errors))
        self.assertTrue(any("closed event" in error for error in errors))

    def test_cancelled_stream_requires_a_following_close(self) -> None:
        cancelled = copy.deepcopy(self.events[:3])
        cancelled_event = copy.deepcopy(cancelled[-1])
        cancelled_event.update({
            "event_id": "event-000004", "sequence": 3, "event_type": "cancelled",
            "monotonic_ns": 1_001_000_000,
            "payload": empty_event_payload(reason="caller-requested"),
        })
        close_event = copy.deepcopy(cancelled_event)
        close_event.update({
            "event_id": "event-000005", "sequence": 4, "event_type": "closed",
            "monotonic_ns": 1_002_000_000,
            "payload": empty_event_payload(reason="cancelled"),
        })
        self.assertEqual(validate_stream_events(cancelled + [cancelled_event, close_event]), [])
        errors = validate_stream_events(cancelled + [cancelled_event])
        self.assertTrue(any("cancelled must be followed" in error for error in errors))

    def test_jsonl_loader_rejects_blank_lines_and_cli_reports_machine_json(self) -> None:
        success = io.StringIO()
        with redirect_stdout(success):
            success_code = main(["validate-stream-events", str(self.example_path)])
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "events.jsonl"
            invalid_path.write_text("{}\n\n", encoding="utf-8")
            failure = io.StringIO()
            with redirect_stderr(failure):
                failure_code = main(["validate-stream-events", str(invalid_path)])
        self.assertEqual(success_code, 0)
        self.assertEqual(json.loads(success.getvalue())["event_count"], 8)
        self.assertEqual(failure_code, 2)
        self.assertIn("blank JSONL lines", failure.getvalue())


if __name__ == "__main__":
    unittest.main()
