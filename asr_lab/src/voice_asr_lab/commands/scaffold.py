"""Scaffold command proving the lab has no product-service side effects."""

from __future__ import annotations

import argparse

from voice_asr_lab import __version__
from voice_asr_lab.commands.base import CommandDefinition, CommandResult


def describe_scaffold() -> dict[str, object]:
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


def _handle_describe(_: argparse.Namespace) -> CommandResult:
    return CommandResult(describe_scaffold())


SCAFFOLD_COMMANDS = (
    CommandDefinition(
        name="describe",
        help="describe the isolated lab boundary",
        handler=_handle_describe,
        examples=("python -m voice_asr_lab describe",),
    ),
)
