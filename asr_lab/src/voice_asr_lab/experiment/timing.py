"""Monotonic clocks, deterministic test time, and streaming latency derivation."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol


class Clock(Protocol):
    def monotonic_ns(self) -> int: ...

    def utc_now(self) -> datetime: ...


@dataclass(frozen=True)
class SystemClock:
    """Production clock: monotonic for durations, UTC wall time for audit only."""

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def utc_now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass
class ManualClock:
    """Deterministic clock advanced explicitly by tests and synthetic experiments."""

    current_ns: int = 0
    wall_origin: datetime = field(default_factory=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    monotonic_origin_ns: int = field(init=False)

    def __post_init__(self) -> None:
        if self.current_ns < 0:
            raise ValueError("manual clock cannot start before zero")
        if self.wall_origin.tzinfo is None or self.wall_origin.utcoffset() != timedelta(0):
            raise ValueError("manual clock wall origin must be UTC-aware")
        self.monotonic_origin_ns = self.current_ns

    def monotonic_ns(self) -> int:
        return self.current_ns

    def utc_now(self) -> datetime:
        elapsed_us = (self.current_ns - self.monotonic_origin_ns) // 1_000
        return self.wall_origin + timedelta(microseconds=elapsed_us)

    def advance_ms(self, milliseconds: float) -> int:
        if milliseconds < 0:
            raise ValueError("manual clock cannot move backwards")
        self.current_ns += round(milliseconds * 1_000_000)
        return self.current_ns


@dataclass
class MonotonicTimeline:
    """Named marks that reject time reversal and expose exact duration boundaries."""

    clock: Clock
    marks: dict[str, int] = field(default_factory=dict)
    _last_ns: int | None = None

    def mark(self, name: str) -> int:
        if not name:
            raise ValueError("timing mark name must not be empty")
        if name in self.marks:
            raise ValueError(f"timing mark already exists: {name}")
        point = self.clock.monotonic_ns()
        if self._last_ns is not None and point < self._last_ns:
            raise ValueError("monotonic clock moved backwards")
        self.marks[name] = point
        self._last_ns = point
        return point

    def duration_ms(self, start: str, finish: str) -> float:
        try:
            start_ns = self.marks[start]
            finish_ns = self.marks[finish]
        except KeyError as error:
            raise ValueError(f"unknown timing mark: {error.args[0]}") from error
        if finish_ns < start_ns:
            raise ValueError(f"timing mark {finish!r} precedes {start!r}")
        return ns_to_ms(finish_ns - start_ns)


def ns_to_ms(nanoseconds: int) -> float:
    return nanoseconds / 1_000_000


def format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("wall timestamp must be UTC-aware")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def derive_stream_latencies(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Derive latency facts from ordered events without using wall-clock timestamps."""

    first_audio = _first(events, "audio_received")
    first_partial = next(
        (
            event for event in events
            if event.get("event_type") == "partial"
            and isinstance(event.get("payload"), Mapping)
            and event["payload"].get("text")
        ),
        None,
    )
    finals = [event for event in events if event.get("event_type") == "final"]
    return {
        "first_partial_latency_ms": _between(first_audio, first_partial),
        "final_latency_ms": _final_latency(events, finals[-1]) if finals else None,
        "queue_latency_ms": _queue_latencies(events),
        "inference_duration_ms": _between(_first(events, "consumption_started"), finals[-1])
        if finals else None,
    }


def _queue_latencies(events: Sequence[Mapping[str, Any]]) -> list[float]:
    enqueued: dict[int, Mapping[str, Any]] = {}
    latencies: list[float] = []
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            continue
        chunk_index = payload.get("chunk_index")
        if not isinstance(chunk_index, int) or isinstance(chunk_index, bool):
            continue
        if event.get("event_type") == "enqueued":
            enqueued[chunk_index] = event
        elif event.get("event_type") == "consumption_started" and chunk_index in enqueued:
            duration = _between(enqueued.pop(chunk_index), event)
            if duration is not None:
                latencies.append(duration)
    return latencies


def _final_latency(events: Sequence[Mapping[str, Any]], final_event: Mapping[str, Any]) -> float | None:
    final_payload = final_event.get("payload")
    segment_id = final_payload.get("segment_id") if isinstance(final_payload, Mapping) else None
    candidates = [
        event for event in events
        if event.get("event_type") in {"vad_endpoint", "segment_committed"}
        and _segment_id(event) == segment_id
        and _point(event) <= _point(final_event)
    ]
    endpoints = [event for event in candidates if event.get("event_type") == "vad_endpoint"]
    start = endpoints[-1] if endpoints else (candidates[-1] if candidates else None)
    return _between(start, final_event)


def _first(events: Sequence[Mapping[str, Any]], event_type: str) -> Mapping[str, Any] | None:
    return next((event for event in events if event.get("event_type") == event_type), None)


def _segment_id(event: Mapping[str, Any]) -> Any:
    payload = event.get("payload")
    return payload.get("segment_id") if isinstance(payload, Mapping) else None


def _point(event: Mapping[str, Any] | None) -> int:
    if event is None:
        return 0
    value = event.get("monotonic_ns")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("event has no valid monotonic_ns")
    return value


def _between(start: Mapping[str, Any] | None, finish: Mapping[str, Any] | None) -> float | None:
    if start is None or finish is None:
        return None
    elapsed = _point(finish) - _point(start)
    if elapsed < 0:
        raise ValueError("event duration cannot be negative")
    return ns_to_ms(elapsed)
