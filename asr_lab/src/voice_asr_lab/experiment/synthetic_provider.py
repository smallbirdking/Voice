"""Deterministic synthetic streaming provider for testing the experiment pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal

from voice_asr_lab.experiment.events import empty_event_payload
from voice_asr_lab.experiment.timing import Clock, format_utc


SyntheticStatus = Literal["succeeded", "failed", "cancelled"]


@dataclass(frozen=True)
class SyntheticProviderConfig:
    partial_texts: tuple[str, ...] = ("synthetic",)
    final_text: str = "synthetic final"
    queue_delay_ms: float = 1.0
    partial_interval_ms: float = 10.0
    endpoint_delay_ms: float = 5.0
    final_delay_ms: float = 8.0
    cancel_after_partials: int | None = None
    fail_at: Literal["consumption", "final"] | None = None

    def __post_init__(self) -> None:
        delays = (
            self.queue_delay_ms,
            self.partial_interval_ms,
            self.endpoint_delay_ms,
            self.final_delay_ms,
        )
        if any(delay < 0 for delay in delays):
            raise ValueError("synthetic delays must not be negative")
        if any(not text for text in self.partial_texts):
            raise ValueError("synthetic partial text must not be empty")
        if self.cancel_after_partials is not None:
            if not 0 <= self.cancel_after_partials <= len(self.partial_texts):
                raise ValueError("cancel_after_partials is outside the configured partial range")
        if self.fail_at is not None and self.cancel_after_partials is not None:
            raise ValueError("synthetic failure and cancellation are mutually exclusive")


@dataclass(frozen=True)
class SyntheticRun:
    events: tuple[dict[str, Any], ...]
    status: SyntheticStatus
    raw_text: str | None
    error: dict[str, Any] | None


@dataclass(frozen=True)
class SyntheticRunContext:
    run_id: str
    environment_snapshot_id: str
    sample_id: str
    session_id: str


class SyntheticProvider:
    provider_id = "synthetic"
    implementation_version = "1.0.0"

    def __init__(self, config: SyntheticProviderConfig, clock: Clock) -> None:
        self.config = config
        self.clock = clock

    def run(
        self,
        context: SyntheticRunContext,
        *,
        audio: bytes,
        audio_duration_ms: float,
    ) -> SyntheticRun:
        if audio_duration_ms < 0:
            raise ValueError("audio duration must not be negative")
        recorder = _EventRecorder(self.clock, context, self.provider_id, audio_duration_ms)
        recorder.emit(
            "audio_received",
            chunk_index=0,
            chunk_duration_ms=audio_duration_ms,
            byte_count=len(audio),
        )
        recorder.emit("enqueued", chunk_index=0, queue_depth=1)
        _delay(self.clock, self.config.queue_delay_ms)
        recorder.emit("consumption_started", chunk_index=0, queue_depth=0)

        if self.config.fail_at == "consumption":
            return self._fail(recorder, "consumption")
        if self.config.cancel_after_partials == 0:
            return self._cancel(recorder)

        for revision, text in enumerate(self.config.partial_texts, start=1):
            _delay(self.clock, self.config.partial_interval_ms)
            recorder.emit(
                "partial",
                text=text,
                revision=revision,
                segment_id="segment-0001",
                provider_payload={"stable": False, "revision": revision},
            )
            if self.config.cancel_after_partials == revision:
                return self._cancel(recorder)

        _delay(self.clock, self.config.endpoint_delay_ms)
        recorder.emit(
            "vad_endpoint",
            segment_id="segment-0001",
            endpoint_source="synthetic-vad",
        )
        recorder.emit(
            "segment_committed",
            segment_id="segment-0001",
            reason="vad-endpoint",
        )
        if self.config.fail_at == "final":
            return self._fail(recorder, "final")

        _delay(self.clock, self.config.final_delay_ms)
        recorder.emit(
            "final",
            text=self.config.final_text,
            segment_id="segment-0001",
            provider_payload={"stable": True},
        )
        recorder.emit("closed", reason="completed")
        return SyntheticRun(tuple(recorder.events), "succeeded", self.config.final_text, None)

    def _cancel(self, recorder: "_EventRecorder") -> SyntheticRun:
        recorder.emit("cancelled", reason="configured-cancellation")
        recorder.emit("closed", reason="cancelled")
        return SyntheticRun(tuple(recorder.events), "cancelled", None, _error("cancel", "cancelled"))

    def _fail(self, recorder: "_EventRecorder", stage: str) -> SyntheticRun:
        recorder.emit("cancelled", reason=f"synthetic-failure:{stage}")
        recorder.emit("closed", reason="failed")
        return SyntheticRun(tuple(recorder.events), "failed", None, _error(stage, "synthetic-failure"))


class _EventRecorder:
    def __init__(
        self,
        clock: Clock,
        context: SyntheticRunContext,
        provider_id: str,
        audio_duration_ms: float,
    ) -> None:
        self.clock = clock
        self.context = context
        self.provider_id = provider_id
        self.audio_duration_ms = audio_duration_ms
        self.events: list[dict[str, Any]] = []

    def emit(self, event_type: str, **payload: Any) -> None:
        sequence = len(self.events)
        self.events.append(
            {
                "schema_version": "1.0.0",
                "record_type": "stream_event",
                "run_id": self.context.run_id,
                "environment_snapshot_id": self.context.environment_snapshot_id,
                "sample_id": self.context.sample_id,
                "provider_id": self.provider_id,
                "session_id": self.context.session_id,
                "event_id": f"event-{sequence + 1:06d}",
                "sequence": sequence,
                "event_type": event_type,
                "monotonic_ns": self.clock.monotonic_ns(),
                "wall_time": format_utc(self.clock.utc_now()),
                "audio_offset_ms": self.audio_duration_ms,
                "payload": empty_event_payload(**payload),
            }
        )


def _delay(clock: Clock, milliseconds: float) -> None:
    advance = getattr(clock, "advance_ms", None)
    if callable(advance):
        advance(milliseconds)
    elif milliseconds:
        time.sleep(milliseconds / 1_000)


def _error(stage: str, code: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "type": "SyntheticProviderError",
        "code": code,
        "message": f"synthetic provider ended at {stage}",
        "retryable": False,
        "details": {"configured": True},
    }
