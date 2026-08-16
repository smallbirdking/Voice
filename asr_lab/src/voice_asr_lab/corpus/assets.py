"""Corpus-owned deterministic audio fixtures for the v1 corpus."""

from __future__ import annotations

import hashlib
import struct
import wave
from collections.abc import Iterable
from pathlib import Path


DEFAULT_SAMPLE_RATE = 44_100
DEFAULT_CHANNELS = 2
DEFAULT_SAMPLE_WIDTH = 2
NOISE_SEED = 0x564F4943
NOISE_PEAK = 2_500


def prepare_owned_corpus_assets(source_root: Path) -> list[dict[str, object]]:
    """Create silence, noise, and a licensed bilingual composite without overwrites."""

    source_root = source_root.resolve()
    silence_path = source_root / "silence-001.wav"
    noise_path = source_root / "noise-001.wav"
    mixed_path = source_root / "zh-en-mixed-001.wav"

    write_silence_wave(silence_path, duration_ms=2_000)
    write_noise_wave(noise_path, duration_ms=3_000)
    concatenate_pcm16_waves(
        [source_root / "zh-short-command-001.wav", source_root / "en-short-command-001.wav"],
        mixed_path,
        gap_ms=250,
    )

    return [_describe_wave(path) for path in (silence_path, noise_path, mixed_path)]


def write_silence_wave(
    output_path: Path,
    *,
    duration_ms: int,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    channels: int = DEFAULT_CHANNELS,
) -> Path:
    """Write a deterministic PCM16 silence WAV and refuse to overwrite evidence."""

    frame_count = _duration_to_frames(duration_ms, sample_rate)
    return _write_pcm16_wave(output_path, sample_rate, channels, b"\x00\x00" * channels * frame_count)


def write_noise_wave(
    output_path: Path,
    *,
    duration_ms: int,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    channels: int = DEFAULT_CHANNELS,
    seed: int = NOISE_SEED,
    peak: int = NOISE_PEAK,
) -> Path:
    """Write deterministic bounded xorshift32 noise as PCM16 WAV."""

    if not 0 < peak <= 32_767:
        raise ValueError("noise peak must be in the range 1..32767")

    sample_count = _duration_to_frames(duration_ms, sample_rate) * channels
    state = seed & 0xFFFFFFFF
    if state == 0:
        raise ValueError("noise seed must not reduce to zero")

    frames = bytearray(sample_count * DEFAULT_SAMPLE_WIDTH)
    for index in range(sample_count):
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        state &= 0xFFFFFFFF
        centered = (state & 0xFFFF) - 32_768
        sample = centered * peak // 32_768
        struct.pack_into("<h", frames, index * DEFAULT_SAMPLE_WIDTH, sample)

    return _write_pcm16_wave(output_path, sample_rate, channels, bytes(frames))


def concatenate_pcm16_waves(
    input_paths: Iterable[Path],
    output_path: Path,
    *,
    gap_ms: int,
) -> Path:
    """Concatenate compatible PCM16 WAVs with a deterministic silence gap."""

    paths = list(input_paths)
    if len(paths) < 2:
        raise ValueError("at least two input WAV files are required")

    chunks: list[bytes] = []
    expected_format: tuple[int, int, int] | None = None
    for path in paths:
        with wave.open(str(path), "rb") as stream:
            current_format = (stream.getframerate(), stream.getnchannels(), stream.getsampwidth())
            if current_format[2] != DEFAULT_SAMPLE_WIDTH or stream.getcomptype() != "NONE":
                raise ValueError(f"{path}: expected uncompressed PCM16 WAV")
            if expected_format is None:
                expected_format = current_format
            elif current_format != expected_format:
                raise ValueError(f"{path}: WAV format differs from the first component")
            chunks.append(stream.readframes(stream.getnframes()))

    assert expected_format is not None
    sample_rate, channels, _ = expected_format
    gap_frames = _duration_to_frames(gap_ms, sample_rate)
    gap = b"\x00\x00" * channels * gap_frames
    payload = gap.join(chunks)
    return _write_pcm16_wave(output_path, sample_rate, channels, payload)


def _write_pcm16_wave(output_path: Path, sample_rate: int, channels: int, frames: bytes) -> Path:
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite corpus source: {output_path}")
    if sample_rate <= 0 or channels <= 0:
        raise ValueError("sample rate and channel count must be positive")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(DEFAULT_SAMPLE_WIDTH)
        stream.setframerate(sample_rate)
        stream.setcomptype("NONE", "not compressed")
        stream.writeframes(frames)
    return output_path.resolve()


def _duration_to_frames(duration_ms: int, sample_rate: int) -> int:
    if duration_ms <= 0:
        raise ValueError("duration must be positive")
    return (duration_ms * sample_rate + 500) // 1_000


def _describe_wave(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as stream:
        duration_ms = (stream.getnframes() * 1_000 + stream.getframerate() // 2) // stream.getframerate()
        result: dict[str, object] = {
            "path": str(path.resolve()),
            "sample_rate_hz": stream.getframerate(),
            "channels": stream.getnchannels(),
            "sample_width_bits": stream.getsampwidth() * 8,
            "duration_ms": duration_ms,
        }
    result["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result
