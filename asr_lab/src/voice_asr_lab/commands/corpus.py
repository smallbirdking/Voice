"""Versioned corpus CLI commands and manifest-loading template."""

from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path
from typing import Any

from voice_asr_lab.commands.base import CommandDefinition, CommandResult
from voice_asr_lab.corpus.assets import prepare_owned_corpus_assets
from voice_asr_lab.corpus.audio_validation import check_corpus_audio
from voice_asr_lab.corpus.fingerprint import compute_corpus_fingerprint
from voice_asr_lab.corpus.manifest import load_corpus_manifest, validate_corpus_manifest
from voice_asr_lab.corpus.preprocessing import preprocess_corpus
from voice_asr_lab.corpus.report import build_corpus_report, write_corpus_report


def _manifest_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("manifest", type=Path)


def _configure_owned_assets(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-root", type=Path, required=True)


def _configure_audio_check(parser: argparse.ArgumentParser) -> None:
    _manifest_argument(parser)
    parser.add_argument(
        "--corpus-root",
        type=Path,
        help="corpus root; defaults to the parent of the manifest directory",
    )


def _configure_preprocessing(parser: argparse.ArgumentParser) -> None:
    _manifest_argument(parser)
    parser.add_argument("--corpus-root", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)


def _configure_report(parser: argparse.ArgumentParser) -> None:
    _manifest_argument(parser)
    parser.add_argument("--corpus-root", type=Path)
    parser.add_argument("--derived-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)


def _load_manifest(
    manifest_path: Path,
    *,
    status: str = "failed",
    prefix_error: bool = False,
) -> tuple[dict[str, Any] | None, CommandResult | None]:
    """Translate all manifest loading failures into the shared result contract."""

    try:
        return load_corpus_manifest(manifest_path), None
    except (OSError, json.JSONDecodeError, ValueError) as error:
        message = f"unable to load corpus manifest: {error}" if prefix_error else str(error)
        return None, CommandResult.failure(
            {
                "status": status,
                "manifest": str(manifest_path.resolve()),
                "errors": [message],
            }
        )


def _handle_validate_manifest(arguments: argparse.Namespace) -> CommandResult:
    manifest, failure = _load_manifest(arguments.manifest, status="invalid", prefix_error=True)
    if failure is not None:
        payload = dict(failure.payload)
        payload["sample_count"] = None
        return CommandResult.failure(payload)
    assert manifest is not None
    schema_errors = validate_corpus_manifest(manifest)
    payload = {
        "status": "valid" if not schema_errors else "invalid",
        "manifest": str(arguments.manifest.resolve()),
        "corpus_id": manifest.get("corpus_id"),
        "corpus_version": manifest.get("corpus_version"),
        "sample_count": len(manifest.get("samples", []))
        if isinstance(manifest.get("samples"), list)
        else None,
        "errors": schema_errors,
    }
    return CommandResult(payload) if not schema_errors else CommandResult.failure(payload)


def _handle_owned_assets(arguments: argparse.Namespace) -> CommandResult:
    try:
        assets = prepare_owned_corpus_assets(arguments.source_root)
    except (OSError, ValueError, wave.Error) as error:
        return CommandResult.failure(
            {
                "status": "failed",
                "source_root": str(arguments.source_root.resolve()),
                "error": str(error),
            }
        )
    return CommandResult(
        {
            "status": "created",
            "source_root": str(arguments.source_root.resolve()),
            "assets": assets,
        }
    )


def _handle_audio_check(arguments: argparse.Namespace) -> CommandResult:
    manifest, failure = _load_manifest(arguments.manifest)
    if failure is not None:
        return failure
    assert manifest is not None
    corpus_root = arguments.corpus_root or arguments.manifest.resolve().parents[1]
    payload = check_corpus_audio(manifest, corpus_root)
    payload["manifest"] = str(arguments.manifest.resolve())
    return CommandResult(payload) if payload["status"] == "passed" else CommandResult.failure(payload)


def _handle_preprocess(arguments: argparse.Namespace) -> CommandResult:
    manifest, failure = _load_manifest(arguments.manifest)
    if failure is not None:
        payload = dict(failure.payload)
        payload["output_root"] = str(arguments.output_root.resolve())
        return CommandResult.failure(payload)
    assert manifest is not None
    try:
        corpus_root = arguments.corpus_root or arguments.manifest.resolve().parents[1]
        payload = preprocess_corpus(manifest, corpus_root, arguments.output_root)
        payload["manifest"] = str(arguments.manifest.resolve())
        return CommandResult(payload)
    except (OSError, ValueError, wave.Error) as error:
        return CommandResult.failure(
            {
                "status": "failed",
                "manifest": str(arguments.manifest.resolve()),
                "output_root": str(arguments.output_root.resolve()),
                "errors": [str(error)],
            }
        )


def _handle_fingerprint(arguments: argparse.Namespace) -> CommandResult:
    manifest, failure = _load_manifest(arguments.manifest)
    if failure is not None:
        return failure
    assert manifest is not None
    computed = compute_corpus_fingerprint(manifest)
    stored = manifest.get("corpus_fingerprint")
    payload = {
        "status": "matched" if stored == computed else "mismatched",
        "manifest": str(arguments.manifest.resolve()),
        "corpus_id": manifest.get("corpus_id"),
        "corpus_version": manifest.get("corpus_version"),
        "stored_fingerprint": stored,
        "computed_fingerprint": computed,
        "matches": stored == computed,
    }
    return CommandResult(payload) if stored == computed else CommandResult.failure(payload)


def _handle_report(arguments: argparse.Namespace) -> CommandResult:
    manifest, failure = _load_manifest(arguments.manifest)
    if failure is not None:
        return failure
    assert manifest is not None
    try:
        corpus_root = arguments.corpus_root or arguments.manifest.resolve().parents[1]
        report = build_corpus_report(manifest, corpus_root, arguments.derived_root)
        if report["status"] != "passed":
            return CommandResult.failure(report)
        json_path, markdown_path = write_corpus_report(
            report,
            arguments.output_json,
            arguments.output_markdown,
        )
        return CommandResult(
            {
                "status": "saved",
                "corpus_id": report["corpus"]["corpus_id"],
                "corpus_version": report["corpus"]["corpus_version"],
                "corpus_fingerprint": report["corpus"]["corpus_fingerprint"],
                "sample_count": report["corpus"]["sample_count"],
                "coverage_complete": report["coverage"]["complete"],
                "json_report": str(json_path),
                "markdown_report": str(markdown_path),
            }
        )
    except (OSError, ValueError, wave.Error) as error:
        return CommandResult.failure(
            {
                "status": "failed",
                "manifest": str(arguments.manifest.resolve()),
                "errors": [str(error)],
            }
        )


CORPUS_COMMANDS = (
    CommandDefinition(
        "validate-corpus-manifest",
        "validate corpus manifest fields and cross-field rules without reading audio",
        _handle_validate_manifest,
        _manifest_argument,
        examples=(
            "python -m voice_asr_lab validate-corpus-manifest "
            "asr_lab/corpus/manifests/voice-asr-eval-v1.json",
        ),
    ),
    CommandDefinition(
        "prepare-corpus-owned-assets",
        "create deterministic silence, noise, and bilingual source assets",
        _handle_owned_assets,
        _configure_owned_assets,
        examples=(
            "python -m voice_asr_lab prepare-corpus-owned-assets "
            "--source-root path/to/new-source-directory",
        ),
    ),
    CommandDefinition(
        "check-corpus-audio",
        "check corpus files, digests, WAV properties, and manifest declarations",
        _handle_audio_check,
        _configure_audio_check,
        examples=(
            "python -m voice_asr_lab check-corpus-audio "
            "asr_lab/corpus/manifests/voice-asr-eval-v1.json",
            "python -m voice_asr_lab check-corpus-audio manifest.json --corpus-root path/to/corpus",
        ),
    ),
    CommandDefinition(
        "preprocess-corpus",
        "create deterministic 16 kHz mono PCM16 derived corpus audio",
        _handle_preprocess,
        _configure_preprocessing,
        examples=(
            "python -m voice_asr_lab preprocess-corpus "
            "asr_lab/corpus/manifests/voice-asr-eval-v1.json "
            "--output-root asr_lab/corpus/derived/demo-v1",
        ),
    ),
    CommandDefinition(
        "fingerprint-corpus-manifest",
        "compute and compare the corpus content fingerprint",
        _handle_fingerprint,
        _manifest_argument,
        examples=(
            "python -m voice_asr_lab fingerprint-corpus-manifest "
            "asr_lab/corpus/manifests/voice-asr-eval-v1.json",
        ),
    ),
    CommandDefinition(
        "report-corpus",
        "validate source and derived audio and retain v1 coverage reports",
        _handle_report,
        _configure_report,
        examples=(
            "python -m voice_asr_lab report-corpus "
            "asr_lab/corpus/manifests/voice-asr-eval-v1.json "
            "--derived-root asr_lab/corpus/derived/v1 "
            "--output-json asr_lab/reports/corpus/voice-asr-eval-v1-local.json "
            "--output-markdown asr_lab/reports/corpus/voice-asr-eval-v1-local.md",
        ),
    ),
)
