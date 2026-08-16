"""Tests for the side-effect-free ASR lab scaffold."""

from __future__ import annotations

import io
import json
import socket
import subprocess
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from voice_asr_lab.cli import main


class ScaffoldTests(unittest.TestCase):
    def test_project_has_no_runtime_dependencies_yet(self) -> None:
        project_file = Path(__file__).parents[1] / "pyproject.toml"

        with project_file.open("rb") as stream:
            project = tomllib.load(stream)["project"]

        self.assertEqual(project["dependencies"], [])

    def test_cli_describes_an_isolated_scaffold(self) -> None:
        output = io.StringIO()

        with (
            patch.object(subprocess, "Popen") as start_process,
            patch.object(socket, "create_connection") as connect_network,
            redirect_stdout(output),
        ):
            exit_code = main([])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["stage"], "scaffold")
        self.assertEqual(payload["services_started"], [])
        self.assertIn("gateway", payload["excluded_product_modules"])
        self.assertIn("database", payload["excluded_product_modules"])
        start_process.assert_not_called()
        connect_network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
