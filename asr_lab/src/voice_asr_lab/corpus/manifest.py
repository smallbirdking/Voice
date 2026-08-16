"""Corpus manifest structural and semantic validation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from voice_asr_lab.corpus.fingerprint import compute_corpus_fingerprint
from voice_asr_lab.core.schema_validation import load_schema, validate_json_schema
from voice_asr_lab.corpus.text_normalization import NORMALIZATION_VERSION, normalize_reference


LAB_ROOT = Path(__file__).resolve().parents[3]
CORPUS_MANIFEST_SCHEMA = LAB_ROOT / "schemas" / "corpus-manifest.schema.json"
NON_SPEECH_SCENARIOS = frozenset({"silence", "noise-only"})


def load_corpus_manifest(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON corpus manifest."""

    with path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    if not isinstance(manifest, dict):
        raise ValueError("corpus manifest root must be a JSON object")
    return manifest


def validate_corpus_manifest(manifest: Any) -> list[str]:
    """Validate the versioned structure and cross-field corpus invariants."""

    errors = validate_json_schema(manifest, load_schema(CORPUS_MANIFEST_SCHEMA))
    if not isinstance(manifest, Mapping):
        return errors

    samples = manifest.get("samples")
    if not isinstance(samples, list):
        return errors

    stored_fingerprint = manifest.get("corpus_fingerprint")
    if isinstance(stored_fingerprint, str):
        computed_fingerprint = compute_corpus_fingerprint(manifest)
        if stored_fingerprint != computed_fingerprint:
            errors.append(
                "$.corpus_fingerprint: does not match comparison-relevant manifest content"
            )

    seen_sample_ids: set[str] = set()
    for index, sample in enumerate(samples):
        if not isinstance(sample, Mapping):
            continue

        sample_path = f"$.samples[{index}]"
        sample_id = sample.get("sample_id")
        if isinstance(sample_id, str):
            if sample_id in seen_sample_ids:
                errors.append(f"{sample_path}.sample_id: duplicate sample_id {sample_id!r}")
            seen_sample_ids.add(sample_id)

        audio = sample.get("audio")
        if isinstance(audio, Mapping):
            audio_path = audio.get("path")
            if isinstance(audio_path, str) and not _is_safe_corpus_relative_path(audio_path):
                errors.append(
                    f"{sample_path}.audio.path: must be a safe POSIX path below corpus/source"
                )

        scenario = sample.get("scenario")
        language = sample.get("language")
        reference = sample.get("reference")
        if isinstance(reference, Mapping):
            text = reference.get("text")
            normalization_version = reference.get("normalization_version")
            normalized_text = reference.get("normalized_text")
            language_segments = reference.get("language_segments")
            if scenario in NON_SPEECH_SCENARIOS:
                if language != "none":
                    errors.append(f"{sample_path}.language: non-speech sample must use 'none'")
                if (
                    text is not None
                    or normalization_version is not None
                    or normalized_text is not None
                    or language_segments != []
                ):
                    errors.append(
                        f"{sample_path}.reference: non-speech sample must use null text, version, "
                        "normalized text and empty segments"
                    )
            elif isinstance(scenario, str):
                if language == "none":
                    errors.append(f"{sample_path}.language: speech sample must declare a language")
                if not isinstance(text, str) or not text.strip():
                    errors.append(f"{sample_path}.reference.text: speech sample requires non-blank text")
                if not isinstance(normalization_version, str) or not normalization_version.strip():
                    errors.append(
                        f"{sample_path}.reference.normalization_version: speech sample requires a version"
                    )
                elif normalization_version != NORMALIZATION_VERSION:
                    errors.append(
                        f"{sample_path}.reference.normalization_version: unsupported version "
                        f"{normalization_version!r}"
                    )
                if not isinstance(normalized_text, str) or not normalized_text.strip():
                    errors.append(
                        f"{sample_path}.reference.normalized_text: speech sample requires normalized text"
                    )
                if not isinstance(language_segments, list) or not language_segments:
                    errors.append(
                        f"{sample_path}.reference.language_segments: speech sample requires segments"
                    )
                if (
                    isinstance(text, str)
                    and text.strip()
                    and language in {"zh-CN", "en-US", "zh-en"}
                ):
                    expected = normalize_reference(text, language)
                    if normalized_text != expected["normalized_text"]:
                        errors.append(
                            f"{sample_path}.reference.normalized_text: does not match "
                            f"{NORMALIZATION_VERSION}"
                        )
                    if language_segments != expected["language_segments"]:
                        errors.append(
                            f"{sample_path}.reference.language_segments: do not match "
                            f"{NORMALIZATION_VERSION}"
                        )

    return errors


def _is_safe_corpus_relative_path(value: str) -> bool:
    """Return whether a manifest path stays below the corpus/source directory."""

    if "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and path.as_posix() == value
        and len(path.parts) > 1
        and path.parts[0] == "source"
        and all(part not in {"", ".", ".."} for part in path.parts)
    )
