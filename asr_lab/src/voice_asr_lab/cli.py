"""Minimal command-line entry point for the isolated ASR lab."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from voice_asr_lab import __version__
from voice_asr_lab.baseline import (
    DEFAULT_BASELINE_OUTPUT,
    collect_environment_baseline,
    validate_environment_baseline,
    write_environment_baseline,
)
from voice_asr_lab.environment import collect_host_snapshot, validate_host_snapshot
from voice_asr_lab.identifiers import (
    create_run_context,
    link_record,
    validate_run_linkage,
)
from voice_asr_lab.nvidia import collect_nvidia_snapshot, validate_nvidia_snapshot
from voice_asr_lab.offline_boundary import (
    DEFAULT_CACHE_ROOT,
    DEFAULT_MANIFEST_PATH,
    prepare_synthetic_cache,
    run_offline_synthetic_smoke,
)


DEFAULT_WORKSPACE = Path(__file__).resolve().parents[3]


def describe_scaffold() -> dict[str, object]:
    """Return the observable boundary of the initial lab scaffold."""

    return {
        "name": "voice-asr-lab",
        "version": __version__,
        "stage": "scaffold",
        "purpose": "evaluate-local-asr-providers",
        "services_started": [],
        "excluded_product_modules": [
            "gateway",
            "database",
            "recording",
            "commands",
            "devices",
            "vision",
            "client",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voice-asr-lab")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("describe", help="describe the isolated lab boundary")

    host_probe = subcommands.add_parser("probe-host", help="emit a host environment snapshot")
    host_probe.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help="workspace path whose disk is measured",
    )
    subcommands.add_parser("probe-nvidia", help="emit NVIDIA GPU and CUDA visibility")
    subcommands.add_parser(
        "demo-run-linkage",
        help="emit one run context and three records linked to its environment snapshot",
    )
    prepare_cache = subcommands.add_parser(
        "prepare-synthetic-cache",
        help="create the tiny deterministic cache fixture used by the offline smoke test",
    )
    prepare_cache.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    offline_smoke = subcommands.add_parser(
        "offline-smoke",
        help="verify cached local work completes while external Python sockets are blocked",
    )
    offline_smoke.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    offline_smoke.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    capture_baseline = subcommands.add_parser(
        "capture-baseline",
        help="collect and save one content-addressed environment baseline",
    )
    capture_baseline.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    capture_baseline.add_argument("--output", type=Path, default=DEFAULT_BASELINE_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a side-effect-limited lab command."""

    _configure_utf8(sys.stdout)
    _configure_utf8(sys.stderr)
    arguments = build_parser().parse_args(argv)
    command = arguments.command or "describe"

    if command == "probe-host":
        snapshot = collect_host_snapshot(arguments.workspace)
        schema_errors = validate_host_snapshot(snapshot)
        if schema_errors:
            print(json.dumps({"schema_errors": schema_errors}, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        payload: dict[str, object] = snapshot
    elif command == "probe-nvidia":
        snapshot = collect_nvidia_snapshot()
        schema_errors = validate_nvidia_snapshot(snapshot)
        if schema_errors:
            print(json.dumps({"schema_errors": schema_errors}, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        payload = snapshot
    elif command == "demo-run-linkage":
        host_snapshot = collect_host_snapshot(DEFAULT_WORKSPACE)
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
            print(json.dumps({"schema_errors": schema_errors}, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        payload = {
            "schema_version": "1.0.0",
            "run_context": context,
            "environment_snapshot": {
                "environment_snapshot_id": context["environment_snapshot_id"],
                "content": environment_snapshot,
            },
            "linked_records": linked_records,
            "linkage_errors": [],
        }
    elif command == "prepare-synthetic-cache":
        payload = prepare_synthetic_cache(arguments.cache_root)
    elif command == "offline-smoke":
        payload = run_offline_synthetic_smoke(arguments.cache_root, arguments.manifest)
        if payload["status"] != "passed":
            print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
    elif command == "capture-baseline":
        baseline = collect_environment_baseline(arguments.workspace)
        schema_errors = validate_environment_baseline(baseline)
        if schema_errors:
            print(json.dumps({"schema_errors": schema_errors}, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        try:
            output_path = write_environment_baseline(baseline, arguments.output)
        except FileExistsError:
            print(
                json.dumps(
                    {
                        "status": "output-exists",
                        "output": str(arguments.output.resolve()),
                        "error": "existing baseline evidence was not overwritten",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2
        payload = {
            "status": "saved",
            "environment_snapshot_id": baseline["environment_snapshot_id"],
            "output": str(output_path),
            "source_commit": baseline["source_control"]["head_commit"],
            "source_dirty": baseline["source_control"]["dirty"],
            "probe_errors": baseline["errors"],
        }
    else:
        payload = describe_scaffold()


    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _configure_utf8(stream: object) -> None:
    """Emit machine-readable JSON as UTF-8 even on legacy Windows code pages."""

    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
