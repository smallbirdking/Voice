"""Common experiment record validation commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from voice_asr_lab.commands.base import CommandDefinition, CommandResult
from voice_asr_lab.corpus.manifest import load_corpus_manifest
from voice_asr_lab.experiment.events import load_stream_events, validate_stream_events
from voice_asr_lab.experiment.pipeline import run_synthetic_experiment
from voice_asr_lab.experiment.report import (
    build_experiment_report,
    load_sample_results_jsonl,
    write_experiment_report,
)
from voice_asr_lab.experiment.sample_result import load_sample_result, validate_sample_result


def _configure_sample_result(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("result", type=Path)


def _handle_validate_sample_result(arguments: argparse.Namespace) -> CommandResult:
    try:
        result = load_sample_result(arguments.result)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return CommandResult.failure(
            {
                "status": "invalid",
                "result": str(arguments.result.resolve()),
                "sample_id": None,
                "errors": [f"unable to load sample result: {error}"],
            }
        )
    errors = validate_sample_result(result)
    payload = {
        "status": "valid" if not errors else "invalid",
        "result": str(arguments.result.resolve()),
        "run_id": result.get("run_id"),
        "sample_id": result.get("input", {}).get("sample_id")
        if isinstance(result.get("input"), dict)
        else None,
        "errors": errors,
    }
    return CommandResult(payload) if not errors else CommandResult.failure(payload)


def _configure_stream_events(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("events", type=Path)


def _handle_validate_stream_events(arguments: argparse.Namespace) -> CommandResult:
    try:
        events = load_stream_events(arguments.events)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return CommandResult.failure(
            {
                "status": "invalid",
                "events": str(arguments.events.resolve()),
                "event_count": 0,
                "errors": [f"unable to load stream events: {error}"],
            }
        )
    errors = validate_stream_events(events)
    payload = {
        "status": "valid" if not errors else "invalid",
        "events": str(arguments.events.resolve()),
        "event_count": len(events),
        "event_types": [event.get("event_type") for event in events],
        "errors": errors,
    }
    return CommandResult(payload) if not errors else CommandResult.failure(payload)


def _configure_aggregate_results(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("results", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-markdown", required=True, type=Path)


def _handle_aggregate_results(arguments: argparse.Namespace) -> CommandResult:
    try:
        results = load_sample_results_jsonl(arguments.results)
        manifest = load_corpus_manifest(arguments.manifest)
        report = build_experiment_report(results, manifest)
        json_path, markdown_path = write_experiment_report(
            report, arguments.output_json, arguments.output_markdown
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return CommandResult.failure(
            {
                "status": "failed", "results": str(arguments.results.resolve()),
                "errors": [str(error)],
            }
        )
    return CommandResult(
        {
            "status": "saved", "report_status": report["status"],
            "sample_count": report["summary"]["sample_count"],
            "failed_count": report["summary"]["failed_count"],
            "output_json": str(json_path), "output_markdown": str(markdown_path),
            "errors": [],
        }
    )


def _configure_synthetic_experiment(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--derived-root", required=True, type=Path)
    parser.add_argument("--environment-baseline", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)


def _handle_synthetic_experiment(arguments: argparse.Namespace) -> CommandResult:
    try:
        artifacts = run_synthetic_experiment(
            arguments.manifest, arguments.derived_root,
            arguments.environment_baseline, arguments.output_dir,
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return CommandResult.failure(
            {"status": "failed", "output_dir": str(arguments.output_dir.resolve()), "errors": [str(error)]}
        )
    return CommandResult(
        {
            "status": "saved", "run_id": artifacts.report["run_id"],
            "sample_count": artifacts.report["summary"]["sample_count"],
            "failed_count": artifacts.report["summary"]["failed_count"],
            "event_file_count": len(artifacts.event_paths),
            "output_dir": str(artifacts.output_dir), "errors": [],
        }
    )


EXPERIMENT_COMMANDS = (
    CommandDefinition(
        "validate-sample-result",
        "validate one per-sample raw ASR experiment result",
        _handle_validate_sample_result,
        _configure_sample_result,
        examples=(
            "python -m voice_asr_lab validate-sample-result "
            "asr_lab/schemas/sample-result.example.json",
        ),
    ),
    CommandDefinition(
        "validate-stream-events",
        "validate ordered streaming fact events from JSONL",
        _handle_validate_stream_events,
        _configure_stream_events,
        examples=(
            "python -m voice_asr_lab validate-stream-events "
            "asr_lab/schemas/stream-event.example.jsonl",
        ),
    ),
    CommandDefinition(
        "aggregate-results",
        "aggregate per-sample JSONL into JSON and Markdown reports",
        _handle_aggregate_results,
        _configure_aggregate_results,
        examples=(
            "python -m voice_asr_lab aggregate-results results.jsonl "
            "asr_lab/corpus/manifests/voice-asr-eval-v1.json "
            "--output-json report.json --output-markdown report.md",
        ),
    ),
    CommandDefinition(
        "run-synthetic-experiment",
        "run the common experiment pipeline with the synthetic provider",
        _handle_synthetic_experiment,
        _configure_synthetic_experiment,
        examples=(
            "python -m voice_asr_lab run-synthetic-experiment "
            "asr_lab/corpus/manifests/voice-asr-eval-v1.json "
            "--derived-root asr_lab/corpus/derived/v1 "
            "--environment-baseline asr_lab/reports/baselines/environment-baseline-v1.json "
            "--output-dir asr_lab/reports/synthetic/common-tools-v1",
        ),
    ),
)
