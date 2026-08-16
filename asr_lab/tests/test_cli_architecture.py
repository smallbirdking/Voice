"""Architecture tests for the command/registry CLI design."""

from __future__ import annotations

import argparse
import ast
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from voice_asr_lab.commands import build_command_registry
from voice_asr_lab.commands.base import CommandDefinition, CommandRegistry, CommandResult
from voice_asr_lab.cli import build_parser


class CliArchitectureTests(unittest.TestCase):
    def test_registry_contains_each_public_command_exactly_once(self) -> None:
        registry = build_command_registry()

        self.assertEqual(
            set(registry.command_names),
            {
                "describe",
                "probe-host",
                "probe-nvidia",
                "demo-run-linkage",
                "prepare-synthetic-cache",
                "offline-smoke",
                "capture-baseline",
                "validate-corpus-manifest",
                "prepare-corpus-owned-assets",
                "check-corpus-audio",
                "preprocess-corpus",
                "fingerprint-corpus-manifest",
                "report-corpus",
                "validate-sample-result",
                "validate-stream-events",
                "aggregate-results",
                "run-synthetic-experiment",
            },
        )
        self.assertEqual(len(registry.command_names), 17)

    def test_registry_rejects_duplicate_command_names(self) -> None:
        command = CommandDefinition(
            "same",
            "first",
            lambda _: CommandResult({"ok": True}),
            examples=("python -m voice_asr_lab same",),
        )
        registry = CommandRegistry(default_command="same")
        registry.register(command)

        with self.assertRaisesRegex(ValueError, "duplicate command registration"):
            registry.register(command)

    def test_registry_dispatches_the_default_command_strategy(self) -> None:
        registry = CommandRegistry(default_command="default")
        registry.register(
            CommandDefinition(
                "default",
                "default command",
                lambda _: CommandResult({"selected": "default"}),
                examples=("python -m voice_asr_lab default",),
            )
        )

        result = registry.dispatch(argparse.Namespace(command=None))

        self.assertEqual(result.payload, {"selected": "default"})
        self.assertEqual(result.exit_code, 0)

    def test_parser_is_built_from_registry_definitions(self) -> None:
        parser = build_parser()

        arguments = parser.parse_args(["preprocess-corpus", "manifest.json", "--output-root", "derived"])

        self.assertEqual(arguments.command, "preprocess-corpus")
        self.assertEqual(arguments.manifest, Path("manifest.json"))
        self.assertEqual(arguments.output_root, Path("derived"))

    def test_every_command_help_contains_its_copyable_examples(self) -> None:
        registry = build_command_registry()
        parser = build_parser(registry)

        for definition in registry.command_definitions:
            with self.subTest(command=definition.name):
                self.assertTrue(definition.examples)
                for example in definition.examples:
                    self.assertIn(f"python -m voice_asr_lab {definition.name}", example)
                output = io.StringIO()
                with redirect_stdout(output), self.assertRaises(SystemExit) as exit_context:
                    parser.parse_args([definition.name, "--help"])
                help_text = output.getvalue()
                self.assertEqual(exit_context.exception.code, 0)
                self.assertIn("Examples:", help_text)
                for example in definition.examples:
                    self.assertIn(example, help_text)

    def test_cli_composition_root_does_not_import_domain_implementations(self) -> None:
        cli_path = Path(__file__).parents[1] / "src" / "voice_asr_lab" / "cli.py"
        tree = ast.parse(cli_path.read_text(encoding="utf-8"))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }

        self.assertFalse(any(module.startswith("voice_asr_lab.corpus") for module in imported_modules))
        self.assertFalse(any(module.startswith("voice_asr_lab.system") for module in imported_modules))


if __name__ == "__main__":
    unittest.main()
