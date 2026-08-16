"""Transparent ASR accuracy, command, silence, and realtime-factor metrics."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any


_MIXED_UNIT = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]|[a-z0-9]+(?:'[a-z0-9]+)*", re.IGNORECASE)


def character_error_rate(reference: str, hypothesis: str) -> dict[str, Any]:
    return edit_metrics([char for char in reference if not char.isspace()], [char for char in hypothesis if not char.isspace()])


def word_error_rate(reference: str, hypothesis: str) -> dict[str, Any]:
    return edit_metrics(reference.split(), hypothesis.split())


def mixed_error_rate(reference: str, hypothesis: str) -> dict[str, Any]:
    return edit_metrics(mixed_units(reference), mixed_units(hypothesis))


def mixed_units(text: str) -> list[str]:
    """Tokenize normalized mixed text as individual Han characters and Latin words."""

    return [match.group(0).lower() for match in _MIXED_UNIT.finditer(text)]


def edit_metrics(reference: Sequence[str], hypothesis: Sequence[str]) -> dict[str, Any]:
    """Return auditable Levenshtein distance and one deterministic edit breakdown."""

    # Cell: distance, substitutions, deletions, insertions.
    previous = [(index, 0, 0, index) for index in range(len(hypothesis) + 1)]
    for ref_index, ref_unit in enumerate(reference, start=1):
        current = [(ref_index, 0, ref_index, 0)]
        for hyp_index, hyp_unit in enumerate(hypothesis, start=1):
            if ref_unit == hyp_unit:
                current.append(previous[hyp_index - 1])
                continue
            diagonal = previous[hyp_index - 1]
            above = previous[hyp_index]
            left = current[hyp_index - 1]
            candidates = (
                (diagonal[0] + 1, diagonal[1] + 1, diagonal[2], diagonal[3]),
                (above[0] + 1, above[1], above[2] + 1, above[3]),
                (left[0] + 1, left[1], left[2], left[3] + 1),
            )
            current.append(min(candidates))
        previous = current

    distance, substitutions, deletions, insertions = previous[-1]
    denominator = len(reference)
    return {
        "reference_units": denominator,
        "hypothesis_units": len(hypothesis),
        "edit_distance": distance,
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "rate": distance / denominator if denominator else None,
    }


def keyword_hits(hypothesis: str, keywords: Sequence[str]) -> dict[str, Any]:
    hypothesis_units = mixed_units(hypothesis)
    details: list[dict[str, Any]] = []
    for keyword in keywords:
        keyword_units = mixed_units(keyword)
        hit = bool(keyword_units) and _contains_sequence(hypothesis_units, keyword_units)
        details.append({"keyword": keyword, "hit": hit})
    hit_count = sum(1 for detail in details if detail["hit"])
    return {
        "keyword_count": len(details),
        "hit_count": hit_count,
        "hit_rate": hit_count / len(details) if details else None,
        "all_hit": bool(details) and hit_count == len(details),
        "details": details,
    }


def silence_false_recognition(hypothesis: str) -> dict[str, Any]:
    visible = "".join(char for char in hypothesis if not char.isspace())
    return {"false_recognition": bool(visible), "recognized_character_count": len(visible)}


def realtime_factor(inference_duration_ms: float, audio_duration_ms: float) -> float:
    if inference_duration_ms < 0:
        raise ValueError("inference duration must not be negative")
    if audio_duration_ms <= 0:
        raise ValueError("audio duration must be positive")
    return inference_duration_ms / audio_duration_ms


def compute_sample_metrics(
    *,
    language: str,
    scenario: str,
    reference: str,
    hypothesis: str,
    audio_duration_ms: float,
    inference_duration_ms: float,
    keywords: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "cer": character_error_rate(reference, hypothesis) if language == "zh-CN" else None,
        "wer": word_error_rate(reference, hypothesis) if language == "en-US" else None,
        "mixed_error": mixed_error_rate(reference, hypothesis) if language == "zh-en" else None,
        "keyword": keyword_hits(hypothesis, keywords) if keywords else None,
        "silence": silence_false_recognition(hypothesis)
        if scenario in {"silence", "noise-only"} else None,
        "realtime_factor": realtime_factor(inference_duration_ms, audio_duration_ms),
    }


def _contains_sequence(source: Sequence[str], target: Sequence[str]) -> bool:
    return any(source[index:index + len(target)] == list(target) for index in range(len(source) - len(target) + 1))
