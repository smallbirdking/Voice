"""Tests for the boundary between retained evidence and local artifacts."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


class StorageLayoutTests(unittest.TestCase):
    lab_root = Path(__file__).parents[1]
    repository_root = lab_root.parent
    layout_file = lab_root / "storage-layout.json"

    @classmethod
    def setUpClass(cls) -> None:
        cls.layout = json.loads(cls.layout_file.read_text(encoding="utf-8"))
        cls.entries = {entry["id"]: entry for entry in cls.layout["directories"]}

    def check_ignored(self, lab_relative_path: str) -> bool:
        repository_relative_path = (Path("asr_lab") / lab_relative_path).as_posix()
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                "--no-index",
                "--",
                repository_relative_path,
            ],
            cwd=self.repository_root,
            check=False,
        )
        self.assertIn(
            result.returncode,
            (0, 1),
            f"git check-ignore failed for {repository_relative_path}",
        )
        return result.returncode == 0

    def test_layout_declares_every_required_asset_class(self) -> None:
        self.assertEqual(self.layout["schema_version"], "1.0.0")
        self.assertEqual(
            set(self.entries),
            {
                "model_cache",
                "model_manifests",
                "corpus_source",
                "corpus_manifests",
                "corpus_derived",
                "temporary_results",
                "retained_reports",
                "logs",
            },
        )

        for entry in self.entries.values():
            with self.subTest(directory=entry["path"]):
                self.assertIn(entry["git_policy"], {"ignored", "tracked"})
                self.assertTrue(entry["retention"])
                self.assertTrue(entry["purpose"])
                self.assertTrue((self.lab_root / entry["path"]).is_dir())

    def test_large_and_reproducible_local_artifacts_are_ignored(self) -> None:
        ignored_examples = {
            "models/cache/funasr/model.safetensors",
            "models/cache/sherpa-onnx/model.onnx",
            "corpus/derived/v1/sample-16khz.wav",
            "tmp/run-in-progress/raw-results.jsonl",
            "logs/funasr/debug.log",
        }

        for path in ignored_examples:
            with self.subTest(path=path):
                self.assertTrue(self.check_ignored(path), f"must be ignored: {path}")

    def test_reproduction_evidence_remains_trackable(self) -> None:
        trackable_examples = {
            "models/manifests/funasr.json",
            "corpus/source/zh-short-command.wav",
            "corpus/manifests/v1.json",
            "reports/run-001/summary.md",
        }

        for path in trackable_examples:
            with self.subTest(path=path):
                self.assertFalse(self.check_ignored(path), f"must remain trackable: {path}")

    def test_ignored_directories_keep_only_their_markers_trackable(self) -> None:
        for directory in ("models/cache", "corpus/derived", "tmp", "logs"):
            marker = f"{directory}/.gitkeep"
            with self.subTest(marker=marker):
                self.assertFalse(self.check_ignored(marker), f"marker must be trackable: {marker}")


if __name__ == "__main__":
    unittest.main()
