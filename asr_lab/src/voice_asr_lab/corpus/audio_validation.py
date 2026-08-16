"""Validate corpus audio bytes and WAV properties against its manifest."""

from __future__ import annotations

import hashlib
import wave
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from voice_asr_lab.corpus.manifest import validate_corpus_manifest


def check_corpus_audio(manifest: Any, corpus_root: Path) -> dict[str, Any]:
    """Return a per-sample audit without hiding failed or missing inputs."""

    corpus_root = corpus_root.resolve()
    manifest_errors = validate_corpus_manifest(manifest)
    sample_reports: list[dict[str, Any]] = []

    if isinstance(manifest, Mapping) and isinstance(manifest.get("samples"), list):
        for index, sample in enumerate(manifest["samples"]):
            sample_reports.append(_check_sample(index, sample, corpus_root))

    failed_samples = sum(report["status"] == "failed" for report in sample_reports)
    status = "passed" if not manifest_errors and failed_samples == 0 else "failed"
    return {
        "status": status,
        "corpus_root": str(corpus_root),
        "manifest_errors": manifest_errors,
        "sample_count": len(sample_reports),
        "passed_samples": len(sample_reports) - failed_samples,
        "failed_samples": failed_samples,
        "samples": sample_reports,
    }


def inspect_pcm_wave(path: Path) -> dict[str, Any]:
    """Read the media facts needed by the input contract from one PCM WAV."""

    digest = _sha256_file(path)
    with wave.open(str(path), "rb") as stream:
        if stream.getcomptype() != "NONE":
            raise wave.Error(f"unsupported WAV compression {stream.getcomptype()!r}")
        sample_width_bits = stream.getsampwidth() * 8
        codec = f"pcm-s{sample_width_bits}le"
        frame_count = stream.getnframes()
        sample_rate = stream.getframerate()
        duration_ms = (frame_count * 1_000 + sample_rate // 2) // sample_rate
        return {
            "sha256": digest,
            "format": {
                "container": "wav",
                "codec": codec,
                "sample_rate_hz": sample_rate,
                "channels": stream.getnchannels(),
                "sample_width_bits": sample_width_bits,
            },
            "frame_count": frame_count,
            "duration_ms": duration_ms,
        }


def _check_sample(index: int, sample: Any, corpus_root: Path) -> dict[str, Any]:
    sample_id = sample.get("sample_id") if isinstance(sample, Mapping) else None
    report: dict[str, Any] = {
        "sample_id": sample_id if isinstance(sample_id, str) else f"<index:{index}>",
        "status": "failed",
        "path": None,
        "declared": None,
        "actual": None,
        "errors": [],
    }
    errors: list[str] = report["errors"]

    if not isinstance(sample, Mapping) or not isinstance(sample.get("audio"), Mapping):
        errors.append("sample does not contain a valid audio object")
        return report

    declared = sample["audio"]
    report["declared"] = declared
    relative_path = declared.get("path")
    if not isinstance(relative_path, str):
        errors.append("audio.path is not a string")
        return report

    path = corpus_root.joinpath(*PurePosixPath(relative_path).parts)
    report["path"] = str(path.resolve())
    if not path.is_file():
        errors.append(f"audio file does not exist: {relative_path}")
        return report

    try:
        actual = inspect_pcm_wave(path)
    except (OSError, EOFError, wave.Error) as error:
        errors.append(f"unable to inspect PCM WAV: {error}")
        return report

    report["actual"] = actual
    _compare(errors, "sha256", declared.get("sha256"), actual["sha256"])
    declared_format = declared.get("format")
    if isinstance(declared_format, Mapping):
        for field in ("container", "codec", "sample_rate_hz", "channels", "sample_width_bits"):
            _compare(errors, f"format.{field}", declared_format.get(field), actual["format"][field])
    else:
        errors.append("declared format is not an object")
    _compare(errors, "duration_ms", declared.get("duration_ms"), actual["duration_ms"])

    if not errors:
        report["status"] = "passed"
    return report


def _compare(errors: list[str], field: str, declared: Any, actual: Any) -> None:
    if declared != actual:
        errors.append(f"{field} mismatch: declared {declared!r}, actual {actual!r}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
