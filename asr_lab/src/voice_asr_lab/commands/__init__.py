"""Build the complete CLI registry from independent command groups."""

from __future__ import annotations

from voice_asr_lab.commands.base import CommandRegistry
from voice_asr_lab.commands.corpus import CORPUS_COMMANDS
from voice_asr_lab.commands.experiment import EXPERIMENT_COMMANDS
from voice_asr_lab.commands.scaffold import SCAFFOLD_COMMANDS
from voice_asr_lab.commands.system import SYSTEM_COMMANDS


def build_command_registry() -> CommandRegistry:
    registry = CommandRegistry(default_command="describe")
    registry.register_all(SCAFFOLD_COMMANDS)
    registry.register_all(SYSTEM_COMMANDS)
    registry.register_all(CORPUS_COMMANDS)
    registry.register_all(EXPERIMENT_COMMANDS)
    return registry
