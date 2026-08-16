"""Versioned streaming fact events and ordered JSONL validation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from voice_asr_lab.core.paths import LAB_ROOT
from voice_asr_lab.core.schema_validation import load_schema, validate_json_schema


STREAM_EVENT_SCHEMA = LAB_ROOT / "schemas" / "stream-event.schema.json"
EVENT_TYPES = (
    "audio_received", "enqueued", "consumption_started", "partial",
    "vad_endpoint", "segment_committed", "final", "cancelled", "closed",
)
_PAYLOAD_RULES: dict[str, tuple[str, ...]] = {
    "audio_received": ("chunk_index", "chunk_duration_ms", "byte_count"),
    "enqueued": ("chunk_index", "queue_depth"),
    "consumption_started": ("chunk_index", "queue_depth"),
    "partial": ("text", "revision", "segment_id"),
    "vad_endpoint": ("endpoint_source", "segment_id"),
    "segment_committed": ("segment_id", "reason"),
    "final": ("text", "segment_id"),
    "cancelled": ("reason",),
    "closed": ("reason",),
}


def empty_event_payload(**values: Any) -> dict[str, Any]:
    """Return the stable payload shape with event-specific facts filled in."""

    payload = {
        "chunk_index": None, "chunk_duration_ms": None, "byte_count": None,
        "queue_depth": None, "text": None, "revision": None,
        "segment_id": None, "endpoint_source": None, "reason": None,
        "provider_payload": None,
    }
    unknown = set(values) - set(payload)
    if unknown:
        raise ValueError(f"unknown stream event payload fields: {sorted(unknown)}")
    payload.update(values)
    return payload


def load_stream_events(path: Path) -> list[dict[str, Any]]:
    """Load non-empty JSONL where every physical line is one event."""

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise ValueError(f"line {line_number}: blank JSONL lines are not allowed")
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError(f"line {line_number}: stream event must be a JSON object")
            events.append(event)
    if not events:
        raise ValueError("stream event JSONL must contain at least one event")
    return events


def validate_stream_event(event: Any) -> list[str]:
    """Validate one event's structure and event-specific fact payload."""

    errors = validate_json_schema(event, load_schema(STREAM_EVENT_SCHEMA))
    if not isinstance(event, Mapping):
        return errors
    _validate_utc(event.get("wall_time"), "$.wall_time", errors)
    event_type = event.get("event_type")
    payload = event.get("payload")
    if isinstance(event_type, str) and isinstance(payload, Mapping):
        for field in _PAYLOAD_RULES.get(event_type, ()):
            value = payload.get(field)
            if value is None:
                errors.append(f"$.payload.{field}: {event_type} requires a non-null value")
        if event_type == "partial" and not payload.get("text"):
            errors.append("$.payload.text: partial text must be non-empty")
    return errors


def validate_stream_events(events: Any) -> list[str]:
    """Validate an ordered event stream including linkage, sequence, and closure."""

    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
        return ["$: expected an event sequence"]
    if not events:
        return ["$: event stream must not be empty"]
    errors: list[str] = []
    for index, event in enumerate(events):
        errors.extend(_at_index(validate_stream_event(event), index))
    if not all(isinstance(event, Mapping) for event in events):
        return errors
    _validate_linkage(events, errors)
    _validate_order(events, errors)
    return errors


def _validate_linkage(events: Sequence[Mapping[str, Any]], errors: list[str]) -> None:
    for field in ("run_id", "environment_snapshot_id", "sample_id", "provider_id", "session_id"):
        values = {event.get(field) for event in events if isinstance(event.get(field), str)}
        if len(values) > 1:
            errors.append(f"$[*].{field}: all events must share one value")


def _validate_order(events: Sequence[Mapping[str, Any]], errors: list[str]) -> None:
    sequences = [event.get("sequence") for event in events]
    if all(isinstance(value, int) and not isinstance(value, bool) for value in sequences):
        expected = list(range(len(events)))
        if sequences != expected:
            errors.append(f"$[*].sequence: expected contiguous order {expected}, got {sequences}")
    event_ids = [event.get("event_id") for event in events]
    if all(isinstance(value, str) for value in event_ids) and len(event_ids) != len(set(event_ids)):
        errors.append("$[*].event_id: event identifiers must be unique")
    points = [event.get("monotonic_ns") for event in events]
    if all(isinstance(value, int) and not isinstance(value, bool) for value in points):
        if points != sorted(points):
            errors.append("$[*].monotonic_ns: event time must be non-decreasing")
    types = [event.get("event_type") for event in events]
    closed_positions = [index for index, value in enumerate(types) if value == "closed"]
    if closed_positions != [len(events) - 1]:
        errors.append("$[*].event_type: exactly one closed event must terminate the stream")
    if "cancelled" in types and types.index("cancelled") >= len(events) - 1:
        errors.append("$[*].event_type: cancelled must be followed by closed")


def _validate_utc(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        return
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00") if value.endswith("Z") else None
    except ValueError:
        parsed = None
    if parsed is None:
        errors.append(f"{path}: must be a valid UTC timestamp ending in Z")


def _at_index(errors: list[str], index: int) -> list[str]:
    return [error.replace("$", f"$[{index}]", 1) for error in errors]
