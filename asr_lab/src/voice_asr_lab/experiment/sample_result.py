"""Validation for immutable per-sample raw ASR experiment results."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from voice_asr_lab.core.paths import LAB_ROOT
from voice_asr_lab.core.schema_validation import load_schema, validate_json_schema


SAMPLE_RESULT_SCHEMA = LAB_ROOT / "schemas" / "sample-result.schema.json"


def load_sample_result(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        result = json.load(stream)
    if not isinstance(result, dict):
        raise ValueError("sample result root must be a JSON object")
    return result


def validate_sample_result(result: Any) -> list[str]:
    """Validate structure plus outcome, timing, text, and reference invariants."""

    errors = validate_json_schema(result, load_schema(SAMPLE_RESULT_SCHEMA))
    if not isinstance(result, Mapping):
        return errors

    _validate_timing(result.get("timing"), errors)
    _validate_outcome(result.get("outcome"), result.get("transcription"), errors)
    _validate_normalization(result.get("corpus"), result.get("input"), result.get("transcription"), errors)
    _validate_resource_refs(result.get("resource_sample_refs"), errors)
    return errors


def _validate_timing(timing: Any, errors: list[str]) -> None:
    if not isinstance(timing, Mapping):
        return
    point_names = (
        "monotonic_started_ns",
        "inference_started_ns",
        "inference_finished_ns",
        "monotonic_finished_ns",
    )
    points = [timing.get(name) for name in point_names]
    if all(isinstance(point, int) and not isinstance(point, bool) for point in points):
        if points != sorted(points):
            errors.append("$.timing: monotonic points must be non-decreasing")
        expected_inference_ms = (points[2] - points[1]) / 1_000_000
        expected_total_ms = (points[3] - points[0]) / 1_000_000
        _compare_duration(timing, "inference_duration_ms", expected_inference_ms, errors)
        _compare_duration(timing, "total_duration_ms", expected_total_ms, errors)

    started_at = _parse_utc(timing.get("started_at"), "$.timing.started_at", errors)
    finished_at = _parse_utc(timing.get("finished_at"), "$.timing.finished_at", errors)
    if started_at is not None and finished_at is not None and finished_at < started_at:
        errors.append("$.timing.finished_at: must not precede started_at")


def _validate_outcome(outcome: Any, transcription: Any, errors: list[str]) -> None:
    if not isinstance(outcome, Mapping):
        return
    status = outcome.get("status")
    process_exit_code = outcome.get("process_exit_code")
    error = outcome.get("error")
    if status == "succeeded":
        if error is not None:
            errors.append("$.outcome.error: succeeded result must not contain an error")
        if process_exit_code not in {None, 0}:
            errors.append("$.outcome.process_exit_code: succeeded result must use 0 or null")
        if isinstance(transcription, Mapping):
            if not isinstance(transcription.get("raw_text"), str):
                errors.append("$.transcription.raw_text: succeeded result requires a string")
            if not isinstance(transcription.get("normalized_text"), str):
                errors.append("$.transcription.normalized_text: succeeded result requires a string")
    elif isinstance(status, str):
        if not isinstance(error, Mapping):
            errors.append("$.outcome.error: non-succeeded result requires structured error evidence")
        if process_exit_code == 0:
            errors.append("$.outcome.process_exit_code: non-succeeded result must not use 0")


def _validate_normalization(corpus: Any, input_record: Any, transcription: Any, errors: list[str]) -> None:
    if not all(isinstance(item, Mapping) for item in (corpus, input_record, transcription)):
        return
    reference_version = corpus.get("reference_normalization_version")
    result_version = transcription.get("normalization_version")
    if input_record.get("language") == "none":
        if reference_version is not None or result_version is not None:
            errors.append("$.transcription.normalization_version: non-speech result must use null versions")
    elif reference_version != result_version:
        errors.append("$.transcription.normalization_version: must match corpus reference version")


def _validate_resource_refs(refs: Any, errors: list[str]) -> None:
    if (
        isinstance(refs, list)
        and all(isinstance(ref, str) for ref in refs)
        and len(refs) != len(set(refs))
    ):
        errors.append("$.resource_sample_refs: references must be unique")


def _compare_duration(timing: Mapping[str, Any], field: str, expected: float, errors: list[str]) -> None:
    actual = timing.get(field)
    if isinstance(actual, (int, float)) and not isinstance(actual, bool):
        if abs(float(actual) - expected) > 0.000001:
            errors.append(f"$.timing.{field}: expected {expected} from monotonic points, got {actual}")


def _parse_utc(value: Any, path: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00") if value.endswith("Z") else None
    except ValueError:
        parsed = None
    if parsed is None:
        errors.append(f"{path}: must be a valid UTC timestamp ending in Z")
    return parsed
