"""End-to-end test for all common experiment tools with the synthetic provider."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from voice_asr_lab.corpus.manifest import load_corpus_manifest
from voice_asr_lab.corpus.preprocessing import preprocess_corpus
from voice_asr_lab.experiment.events import load_stream_events, validate_stream_events
from voice_asr_lab.experiment.pipeline import run_synthetic_experiment
from voice_asr_lab.experiment.report import load_sample_results_jsonl
from voice_asr_lab.experiment.resources import ResourceSampler, validate_resource_sample
from voice_asr_lab.experiment.sample_result import validate_sample_result
from voice_asr_lab.experiment.timing import ManualClock


class SyntheticPipelineTests(unittest.TestCase):
    lab_root = Path(__file__).parents[1]
    manifest_path = lab_root / "corpus" / "manifests" / "voice-asr-eval-v1.json"
    baseline_path = lab_root / "reports" / "baselines" / "environment-baseline-v1.json"

    def test_v1_end_to_end_retains_events_resources_results_metrics_and_reports(self) -> None:
        manifest = load_corpus_manifest(self.manifest_path)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            derived = root / "derived"
            preprocess_corpus(manifest, self.lab_root / "corpus", derived)
            clock = ManualClock(1_000_000_000)
            cpu_ns = 0

            def process_probe():
                nonlocal cpu_ns
                cpu_ns += 1_000_000
                return cpu_ns, 20_000_000 + cpu_ns

            sampler = ResourceSampler(clock, process_probe=process_probe, gpu_probe=lambda: [])
            output = root / "retained"
            artifacts = run_synthetic_experiment(
                self.manifest_path, derived, self.baseline_path, output,
                clock=clock, resource_sampler=sampler,
                run_id="run-20260816T120000000000Z-a1b2c3d4e5f6",
            )

            results = load_sample_results_jsonl(artifacts.sample_results_path)
            resources = [
                json.loads(line)
                for line in artifacts.resource_samples_path.read_text(encoding="utf-8").splitlines()
            ]
            report = json.loads(artifacts.report_json_path.read_text(encoding="utf-8"))

            self.assertEqual(len(results), 7)
            self.assertTrue(all(validate_sample_result(result) == [] for result in results))
            self.assertEqual(len(resources), 14)
            self.assertTrue(all(validate_resource_sample(sample) == [] for sample in resources))
            self.assertEqual(len(artifacts.event_paths), 7)
            self.assertTrue(
                all(validate_stream_events(load_stream_events(path)) == [] for path in artifacts.event_paths)
            )
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["summary"]["sample_count"], 7)
            self.assertEqual(report["summary"]["failed_count"], 0)
            self.assertEqual(report["accuracy"]["cer"]["rate"], 0.0)
            self.assertEqual(report["accuracy"]["wer"]["rate"], 0.0)
            self.assertEqual(report["accuracy"]["mixed_error"]["rate"], 0.0)
            self.assertEqual(report["accuracy"]["silence"]["false_recognition_samples"], 0)
            self.assertIn("只证明公共工具管线", artifacts.learning_path.read_text(encoding="utf-8"))

            with self.assertRaises(FileExistsError):
                run_synthetic_experiment(
                    self.manifest_path, derived, self.baseline_path, output,
                    clock=clock, resource_sampler=sampler,
                )


if __name__ == "__main__":
    unittest.main()
