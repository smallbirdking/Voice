"""Minimal command-line entry point for the isolated ASR lab."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from voice_asr_lab import __version__
from voice_asr_lab.environment import collect_host_snapshot, validate_host_snapshot
from voice_asr_lab.nvidia import collect_nvidia_snapshot, validate_nvidia_snapshot


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
    else:
        payload = describe_scaffold()


    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _configure_utf8(stream: object) -> None:
    """Emit machine-readable JSON as UTF-8 even on legacy Windows code pages."""

    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
