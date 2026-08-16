"""PCM WAV file input and deterministic single-stream offline/realtime replay."""

from __future__ import annotations

import time
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from voice_asr_lab.experiment.timing import Clock


ReplayMode = Literal["offline", "realtime"]


@dataclass(frozen=True)
class WaveAudio:
    path: Path
    pcm_bytes: bytes
    frame_count: int
    sample_rate_hz: int
    channels: int
    sample_width_bits: int
    duration_ms: float


@dataclass(frozen=True)
class AudioChunk:
    index: int
    pcm_bytes: bytes
    frame_count: int
    duration_ms: float
    audio_offset_ms: float
    available_monotonic_ns: int


@dataclass(frozen=True)
class ReplaySummary:
    mode: ReplayMode
    chunk_count: int
    emitted_bytes: int
    audio_duration_ms: float
    monotonic_started_ns: int
    monotonic_finished_ns: int

    @property
    def elapsed_ms(self) -> float:
        return (self.monotonic_finished_ns - self.monotonic_started_ns) / 1_000_000


def load_wave_audio(path: Path) -> WaveAudio:
    """Read a local uncompressed PCM WAV without changing its samples."""

    with wave.open(str(path), "rb") as source:
        if source.getcomptype() != "NONE":
            raise ValueError(f"unsupported WAV compression: {source.getcomptype()}")
        frame_count = source.getnframes()
        sample_rate = source.getframerate()
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        if frame_count < 1 or sample_rate < 1 or channels < 1 or sample_width < 1:
            raise ValueError("WAV media properties must be positive")
        pcm_bytes = source.readframes(frame_count)
    expected_bytes = frame_count * channels * sample_width
    if len(pcm_bytes) != expected_bytes:
        raise ValueError(f"truncated WAV PCM: expected {expected_bytes} bytes, got {len(pcm_bytes)}")
    return WaveAudio(
        path=path,
        pcm_bytes=pcm_bytes,
        frame_count=frame_count,
        sample_rate_hz=sample_rate,
        channels=channels,
        sample_width_bits=sample_width * 8,
        duration_ms=frame_count * 1_000 / sample_rate,
    )


def replay_wave(
    audio: WaveAudio,
    *,
    chunk_ms: float,
    mode: ReplayMode,
    clock: Clock,
    sink: Callable[[AudioChunk], None],
) -> ReplaySummary:
    """Emit exactly one ordered stream of chunks; realtime follows audio duration."""

    if chunk_ms <= 0:
        raise ValueError("chunk_ms must be positive")
    if mode not in {"offline", "realtime"}:
        raise ValueError(f"unsupported replay mode: {mode}")
    frames_per_chunk = max(1, round(audio.sample_rate_hz * chunk_ms / 1_000))
    bytes_per_frame = audio.channels * (audio.sample_width_bits // 8)
    started_ns = clock.monotonic_ns()
    offset_frames = 0
    chunk_count = 0
    emitted_bytes = 0

    while offset_frames < audio.frame_count:
        frame_count = min(frames_per_chunk, audio.frame_count - offset_frames)
        duration_ms = frame_count * 1_000 / audio.sample_rate_hz
        if mode == "realtime":
            _delay(clock, duration_ms)
        byte_start = offset_frames * bytes_per_frame
        byte_finish = (offset_frames + frame_count) * bytes_per_frame
        offset_frames += frame_count
        chunk_bytes = audio.pcm_bytes[byte_start:byte_finish]
        sink(
            AudioChunk(
                index=chunk_count,
                pcm_bytes=chunk_bytes,
                frame_count=frame_count,
                duration_ms=duration_ms,
                audio_offset_ms=offset_frames * 1_000 / audio.sample_rate_hz,
                available_monotonic_ns=clock.monotonic_ns(),
            )
        )
        chunk_count += 1
        emitted_bytes += len(chunk_bytes)

    return ReplaySummary(
        mode=mode,
        chunk_count=chunk_count,
        emitted_bytes=emitted_bytes,
        audio_duration_ms=audio.duration_ms,
        monotonic_started_ns=started_ns,
        monotonic_finished_ns=clock.monotonic_ns(),
    )


def _delay(clock: Clock, milliseconds: float) -> None:
    advance = getattr(clock, "advance_ms", None)
    if callable(advance):
        advance(milliseconds)
    else:
        time.sleep(milliseconds / 1_000)
