"""Corpus preprocessing into the deterministic ASR input contract."""

from __future__ import annotations

import sys
import wave
from array import array
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from voice_asr_lab.corpus.audio_validation import check_corpus_audio, inspect_pcm_wave


TARGET_SAMPLE_RATE_HZ = 16_000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH_BITS = 16
PREPROCESSING_ALGORITHM = "pcm16-mono-linear-v1"


def preprocess_corpus(
    manifest: Mapping[str, Any],
    corpus_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Validate and convert every corpus sample without overwriting any input."""

    corpus_root = corpus_root.resolve()
    output_root = output_root.resolve()
    source_audit = check_corpus_audio(manifest, corpus_root)
    if source_audit["status"] != "passed":
        raise ValueError("source corpus audio validation failed; preprocessing was not started")

    samples = manifest.get("samples")
    if not isinstance(samples, list):
        raise ValueError("manifest samples must be a list")

    source_paths = {
        _source_path(corpus_root, sample).resolve()
        for sample in samples
        if isinstance(sample, Mapping)
    }
    targets = [output_root / f"{sample['sample_id']}.wav" for sample in samples]
    if len({target.resolve() for target in targets}) != len(targets):
        raise ValueError("preprocessing targets are not unique")
    for target in targets:
        if target.resolve() in source_paths:
            raise ValueError(f"refusing to overwrite source audio: {target}")
        if target.exists():
            raise FileExistsError(f"derived audio already exists: {target}")

    output_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for sample, target in zip(samples, targets, strict=True):
        source = _source_path(corpus_root, sample)
        records.append(preprocess_pcm16_wave(sample["sample_id"], source, target))

    return {
        "status": "created",
        "algorithm": PREPROCESSING_ALGORITHM,
        "output_root": str(output_root),
        "sample_count": len(records),
        "samples": records,
    }


def preprocess_pcm16_wave(sample_id: str, source: Path, target: Path) -> dict[str, Any]:
    """Convert one PCM16 WAV to deterministic 16 kHz mono PCM16 WAV."""

    source = source.resolve()
    target = target.resolve()
    if source == target:
        raise ValueError(f"refusing to overwrite source audio: {source}")
    if target.exists():
        raise FileExistsError(f"derived audio already exists: {target}")

    source_facts = inspect_pcm_wave(source)
    source_format = source_facts["format"]
    if source_format["codec"] != "pcm-s16le":
        raise ValueError(f"unsupported source codec: {source_format['codec']}")

    with wave.open(str(source), "rb") as stream:
        frame_count = stream.getnframes()
        channels = stream.getnchannels()
        source_rate = stream.getframerate()
        samples = array("h")
        samples.frombytes(stream.readframes(frame_count))
    if sys.byteorder != "little":
        samples.byteswap()

    mono = _downmix_pcm16(samples, channels)
    converted = _resample_linear_pcm16(mono, source_rate, TARGET_SAMPLE_RATE_HZ)

    target.parent.mkdir(parents=True, exist_ok=True)
    output_bytes = array("h", converted)
    if sys.byteorder != "little":
        output_bytes.byteswap()
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(TARGET_CHANNELS)
        stream.setsampwidth(TARGET_SAMPLE_WIDTH_BITS // 8)
        stream.setframerate(TARGET_SAMPLE_RATE_HZ)
        stream.writeframes(output_bytes.tobytes())

    output_facts = inspect_pcm_wave(target)
    return {
        "sample_id": sample_id,
        "algorithm": PREPROCESSING_ALGORITHM,
        "source": {"path": str(source), **source_facts},
        "output": {"path": str(target), **output_facts},
    }


def _source_path(corpus_root: Path, sample: Mapping[str, Any]) -> Path:
    relative = sample["audio"]["path"]
    return corpus_root.joinpath(*PurePosixPath(relative).parts)


def _downmix_pcm16(samples: array[int], channels: int) -> list[int]:
    if channels < 1:
        raise ValueError("source audio must have at least one channel")
    if len(samples) % channels:
        raise ValueError("PCM sample count is not divisible by channel count")
    if channels == 1:
        return list(samples)
    return [
        _round_divide_signed(sum(samples[index : index + channels]), channels)
        for index in range(0, len(samples), channels)
    ]


def _resample_linear_pcm16(samples: list[int], source_rate: int, target_rate: int) -> list[int]:
    if source_rate < 1 or target_rate < 1:
        raise ValueError("sample rates must be positive")
    if not samples:
        return []
    if source_rate == target_rate:
        return samples.copy()

    output_count = _round_divide_signed(len(samples) * target_rate, source_rate)
    converted: list[int] = []
    last_index = len(samples) - 1
    for output_index in range(output_count):
        source_position = output_index * source_rate
        left_index, remainder = divmod(source_position, target_rate)
        left_index = min(left_index, last_index)
        right_index = min(left_index + 1, last_index)
        weighted = (
            samples[left_index] * (target_rate - remainder)
            + samples[right_index] * remainder
        )
        converted.append(_clamp_pcm16(_round_divide_signed(weighted, target_rate)))
    return converted


def _round_divide_signed(numerator: int, denominator: int) -> int:
    """Round halves away from zero without platform-dependent floating point."""

    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if numerator >= 0:
        return (numerator + denominator // 2) // denominator
    return -((-numerator + denominator // 2) // denominator)


def _clamp_pcm16(value: int) -> int:
    return max(-32_768, min(32_767, value))
