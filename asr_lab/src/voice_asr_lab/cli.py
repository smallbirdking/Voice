"""Thin CLI composition root for the isolated ASR lab."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from voice_asr_lab.commands import build_command_registry
from voice_asr_lab.commands.base import CommandRegistry
from voice_asr_lab.commands.scaffold import describe_scaffold
from voice_asr_lab.core.paths import WORKSPACE_ROOT as DEFAULT_WORKSPACE


def build_parser(registry: CommandRegistry | None = None) -> argparse.ArgumentParser:
    """Build argparse from registered commands without importing domain logic here."""

    active_registry = registry or build_command_registry()
    parser = argparse.ArgumentParser(prog="voice-asr-lab")
    active_registry.configure_parser(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse, dispatch, and render one machine-readable command result."""

    _configure_utf8(sys.stdout)
    _configure_utf8(sys.stderr)
    registry = build_command_registry()
    arguments = build_parser(registry).parse_args(argv)
    result = registry.dispatch(arguments)
    output = sys.stderr if result.exit_code else sys.stdout
    print(json.dumps(result.payload, ensure_ascii=False, indent=2), file=output)
    return result.exit_code


def _configure_utf8(stream: object) -> None:
    """Emit machine-readable JSON as UTF-8 even on legacy Windows code pages."""

    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
