"""System inspection, offline-boundary, and baseline CLI commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from voice_asr_lab.commands.base import CommandDefinition, CommandResult
from voice_asr_lab.core.identifiers import create_run_context, link_record, validate_run_linkage
from voice_asr_lab.core.paths import WORKSPACE_ROOT
from voice_asr_lab.system.baseline import (
    DEFAULT_BASELINE_OUTPUT,
    collect_environment_baseline,
    validate_environment_baseline,
    write_environment_baseline,
)
from voice_asr_lab.system.host import collect_host_snapshot, validate_host_snapshot
from voice_asr_lab.system.nvidia import collect_nvidia_snapshot, validate_nvidia_snapshot
from voice_asr_lab.system.offline_boundary import (
    DEFAULT_CACHE_ROOT,
    DEFAULT_MANIFEST_PATH,
    prepare_synthetic_cache,
    run_offline_synthetic_smoke,
)


def _configure_host(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        type=Path,
        default=WORKSPACE_ROOT,
        help="workspace path whose disk is measured",
    )


def _configure_prepare_cache(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)


def _configure_offline_smoke(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)


def _configure_baseline(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", type=Path, default=WORKSPACE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_BASELINE_OUTPUT)


def _handle_probe_host(arguments: argparse.Namespace) -> CommandResult:
    snapshot = collect_host_snapshot(arguments.workspace)
    schema_errors = validate_host_snapshot(snapshot)
    if schema_errors:
        return CommandResult.failure({"schema_errors": schema_errors})
    return CommandResult(snapshot)


def _handle_probe_nvidia(_: argparse.Namespace) -> CommandResult:
    snapshot = collect_nvidia_snapshot()
    schema_errors = validate_nvidia_snapshot(snapshot)
    if schema_errors:
        return CommandResult.failure({"schema_errors": schema_errors})
    return CommandResult(snapshot)


def _handle_run_linkage(_: argparse.Namespace) -> CommandResult:
    host_snapshot = collect_host_snapshot(WORKSPACE_ROOT)
    nvidia_snapshot = collect_nvidia_snapshot()
    environment_snapshot = {
        "schema_version": "1.0.0",
        "host": host_snapshot,
        "nvidia": nvidia_snapshot,
    }
    context = create_run_context(environment_snapshot)
    linked_records = [
        link_record("sample_result", {"sample_id": "linkage-demo"}, context),
        link_record("resource_sample", {"sequence": 0}, context),
        link_record("report", {"title": "linkage-demo"}, context),
    ]
    schema_errors = [
        *(f"host: {error}" for error in validate_host_snapshot(host_snapshot)),
        *(f"nvidia: {error}" for error in validate_nvidia_snapshot(nvidia_snapshot)),
        *validate_run_linkage(context, environment_snapshot, linked_records),
    ]
    if schema_errors:
        return CommandResult.failure({"schema_errors": schema_errors})
    return CommandResult(
        {
            "schema_version": "1.0.0",
            "run_context": context,
            "environment_snapshot": {
                "environment_snapshot_id": context["environment_snapshot_id"],
                "content": environment_snapshot,
            },
            "linked_records": linked_records,
            "linkage_errors": [],
        }
    )


def _handle_prepare_cache(arguments: argparse.Namespace) -> CommandResult:
    return CommandResult(prepare_synthetic_cache(arguments.cache_root))


def _handle_offline_smoke(arguments: argparse.Namespace) -> CommandResult:
    payload = run_offline_synthetic_smoke(arguments.cache_root, arguments.manifest)
    if payload["status"] != "passed":
        return CommandResult.failure(payload)
    return CommandResult(payload)


def _handle_capture_baseline(arguments: argparse.Namespace) -> CommandResult:
    baseline = collect_environment_baseline(arguments.workspace)
    schema_errors = validate_environment_baseline(baseline)
    if schema_errors:
        return CommandResult.failure({"schema_errors": schema_errors})
    try:
        output_path = write_environment_baseline(baseline, arguments.output)
    except FileExistsError:
        return CommandResult.failure(
            {
                "status": "output-exists",
                "output": str(arguments.output.resolve()),
                "error": "existing baseline evidence was not overwritten",
            }
        )
    return CommandResult(
        {
            "status": "saved",
            "environment_snapshot_id": baseline["environment_snapshot_id"],
            "output": str(output_path),
            "source_commit": baseline["source_control"]["head_commit"],
            "source_dirty": baseline["source_control"]["dirty"],
            "probe_errors": baseline["errors"],
        }
    )


SYSTEM_COMMANDS = (
    CommandDefinition(
        "probe-host",
        "emit a host environment snapshot",
        _handle_probe_host,
        _configure_host,
        examples=("python -m voice_asr_lab probe-host --workspace .",),
    ),
    CommandDefinition(
        "probe-nvidia",
        "emit NVIDIA GPU and CUDA visibility",
        _handle_probe_nvidia,
        examples=("python -m voice_asr_lab probe-nvidia",),
    ),
    CommandDefinition(
        "demo-run-linkage",
        "emit one run context and three records linked to its environment snapshot",
        _handle_run_linkage,
        examples=("python -m voice_asr_lab demo-run-linkage",),
    ),
    CommandDefinition(
        "prepare-synthetic-cache",
        "create the tiny deterministic cache fixture used by the offline smoke test",
        _handle_prepare_cache,
        _configure_prepare_cache,
        examples=(
            "python -m voice_asr_lab prepare-synthetic-cache",
            "python -m voice_asr_lab prepare-synthetic-cache --cache-root asr_lab/tmp/cache-demo",
        ),
    ),
    CommandDefinition(
        "offline-smoke",
        "verify cached local work completes while external Python sockets are blocked",
        _handle_offline_smoke,
        _configure_offline_smoke,
        examples=(
            "python -m voice_asr_lab offline-smoke",
            "python -m voice_asr_lab offline-smoke --cache-root asr_lab/models/cache "
            "--manifest asr_lab/models/manifests/synthetic-smoke.json",
        ),
    ),
    CommandDefinition(
        "capture-baseline",
        "collect and save one content-addressed environment baseline",
        _handle_capture_baseline,
        _configure_baseline,
        examples=(
            "python -m voice_asr_lab capture-baseline --workspace . "
            "--output asr_lab/reports/baselines/environment-baseline-local.json",
        ),
    ),
)
