"""Versioned corpus reference-text normalization for ASR evaluation."""

from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any


NORMALIZATION_VERSION = "text-normalization-v1"
_ENGLISH_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")
_ABBREVIATION_PERIOD = re.compile(r"(?<=[A-Za-z])\.(?=[A-Za-z])")


def normalize_chinese(text: str) -> str:
    """Normalize Chinese references while retaining letters and numeric digits."""

    canonical = unicodedata.normalize("NFKC", text).lower()
    return "".join(character for character in canonical if _is_letter_or_number(character))


def normalize_english(text: str) -> str:
    """Normalize English into lowercase whitespace-separated evaluation tokens."""

    canonical = unicodedata.normalize("NFKC", text)
    canonical = canonical.replace("’", "'").replace("‘", "'")
    canonical = _ABBREVIATION_PERIOD.sub("", canonical).lower()
    return " ".join(_ENGLISH_TOKEN.findall(canonical))


def normalize_mixed(text: str) -> dict[str, Any]:
    """Retain original text and script segments alongside mixed normalization."""

    segments: list[dict[str, Any]] = []
    segment_language: str | None = None
    segment_start = 0
    for index, character in enumerate(text):
        character_language = _character_language(character)
        if character_language is None:
            continue
        if segment_language is None:
            segment_language = character_language
            segment_start = 0
        elif character_language != segment_language:
            segments.append(_segment(text, segment_start, index, segment_language))
            segment_start = index
            segment_language = character_language

    if segment_language is not None:
        segments.append(_segment(text, segment_start, len(text), segment_language))

    normalized_parts = [segment["normalized"] for segment in segments if segment["normalized"]]
    return {
        "original": text,
        "normalized": " ".join(normalized_parts),
        "segments": segments,
    }


def normalize_reference(text: str, language: str) -> dict[str, Any]:
    """Return the normalized text and retained segments for a manifest reference."""

    if language == "zh-CN":
        normalized = normalize_chinese(text)
        segment_language = "zh"
    elif language == "en-US":
        normalized = normalize_english(text)
        segment_language = "en"
    elif language == "zh-en":
        mixed = normalize_mixed(text)
        return {"normalized_text": mixed["normalized"], "language_segments": mixed["segments"]}
    else:
        raise ValueError(f"unsupported speech language: {language}")
    return {
        "normalized_text": normalized,
        "language_segments": [
            {
                "language": segment_language,
                "original": text,
                "normalized": normalized,
                "start": 0,
                "end": len(text),
            }
        ],
    }


def normalize_manifest_references(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return a copied manifest enriched with reproducible normalized references."""

    enriched = copy.deepcopy(manifest)
    samples = enriched.get("samples")
    if not isinstance(samples, list):
        raise ValueError("manifest samples must be a list")
    for sample in samples:
        reference = sample["reference"]
        text = reference.get("text")
        if text is None:
            reference["normalization_version"] = None
            reference["normalized_text"] = None
            reference["language_segments"] = []
            continue
        normalized = normalize_reference(text, sample["language"])
        reference["normalization_version"] = NORMALIZATION_VERSION
        reference.update(normalized)
    return enriched


def _segment(text: str, start: int, end: int, language: str) -> dict[str, Any]:
    original = text[start:end]
    normalized = normalize_chinese(original) if language == "zh" else normalize_english(original)
    return {
        "language": language,
        "original": original,
        "normalized": normalized,
        "start": start,
        "end": end,
    }


def _character_language(character: str) -> str | None:
    canonical = unicodedata.normalize("NFKC", character)
    if not canonical:
        return None
    codepoint = ord(canonical[0])
    if (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
    ):
        return "zh"
    if unicodedata.category(canonical[0]).startswith("L"):
        return "en"
    return None


def _is_letter_or_number(character: str) -> bool:
    return unicodedata.category(character)[0] in {"L", "N"}
