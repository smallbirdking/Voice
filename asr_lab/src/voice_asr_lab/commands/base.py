"""Command, registry, and result objects for the CLI composition root."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any


ConfigureParser = Callable[[argparse.ArgumentParser], None]
CommandHandler = Callable[[argparse.Namespace], "CommandResult"]


@dataclass(frozen=True)
class CommandResult:
    """Separate a command's JSON payload from transport and process concerns."""

    payload: Mapping[str, Any]
    exit_code: int = 0

    @classmethod
    def failure(cls, payload: Mapping[str, Any], exit_code: int = 2) -> "CommandResult":
        return cls(payload=payload, exit_code=exit_code)


@dataclass(frozen=True)
class CommandDefinition:
    """Describe one argparse command and the strategy that executes it."""

    name: str
    help: str
    handler: CommandHandler
    configure_parser: ConfigureParser | None = None
    examples: tuple[str, ...] = ()


class CommandRegistry:
    """Register concrete commands and dispatch them by stable command name."""

    def __init__(self, *, default_command: str) -> None:
        self._default_command = default_command
        self._definitions: dict[str, CommandDefinition] = {}

    @property
    def command_names(self) -> tuple[str, ...]:
        return tuple(self._definitions)

    @property
    def command_definitions(self) -> tuple[CommandDefinition, ...]:
        return tuple(self._definitions.values())

    def register(self, definition: CommandDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"duplicate command registration: {definition.name}")
        if not definition.examples:
            raise ValueError(f"command has no usage examples: {definition.name}")
        self._definitions[definition.name] = definition

    def register_all(self, definitions: Iterable[CommandDefinition]) -> None:
        for definition in definitions:
            self.register(definition)

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        subcommands = parser.add_subparsers(dest="command")
        for definition in self._definitions.values():
            command_parser = subcommands.add_parser(
                definition.name,
                help=definition.help,
                description=definition.help,
                epilog=_format_examples(definition.examples),
                formatter_class=argparse.RawDescriptionHelpFormatter,
            )
            if definition.configure_parser is not None:
                definition.configure_parser(command_parser)

    def dispatch(self, arguments: argparse.Namespace) -> CommandResult:
        command_name = arguments.command or self._default_command
        try:
            definition = self._definitions[command_name]
        except KeyError as error:
            raise ValueError(f"unregistered command: {command_name}") from error
        return definition.handler(arguments)


def _format_examples(examples: tuple[str, ...]) -> str:
    rendered = "\n\n".join(f"  {example}" for example in examples)
    return f"Examples:\n{rendered}"
