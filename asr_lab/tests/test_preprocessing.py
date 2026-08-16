"""Tests for deterministic, non-destructive corpus preprocessing."""

from __future__ import annotations

import copy
import tempfile
import unittest
import wave
from array import array
from pathlib import Path

from voice_asr_lab.corpus.manifest import load_corpus_manifest
from voice_asr_lab.corpus.fingerprint import with_corpus_fingerprint
from voice_asr_lab.corpus.preprocessing import (
    PREPROCESSING_ALGORITHM,
    _downmix_pcm16,
    _resample_linear_pcm16,
    preprocess_corpus,
    preprocess_pcm16_wave,
)


class PreprocessingTests(unittest.TestCase):
    lab_root = Path(__file__).parents[1]
    corpus_root = lab_root / "corpus"
    manifest_path = corpus_root / "manifests" / "voice-asr-eval-v1.json"

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_corpus_manifest(cls.manifest_path)

    def test_integer_downmix_and_linear_resampling_have_known_values(self) -> None:
        stereo = array("h", [1000, 3000, -1000, -2000, 32767, 32767])
        self.assertEqual(_downmix_pcm16(stereo, 2), [2000, -1500, 32767])
        self.assertEqual(_resample_linear_pcm16([0, 1000, 2000, 3000], 4, 2), [0, 2000])

    def test_mono_16khz_samples_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.wav"
            target = root / "target.wav"
            expected = array("h", [-32768, -1, 0, 1, 32767])
            _write_wave(source, expected, sample_rate=16_000, channels=1)

            record = preprocess_pcm16_wave("known", source, target)

            self.assertEqual(_read_wave_samples(target), expected.tolist())
            self.assertEqual(record["algorithm"], PREPROCESSING_ALGORITHM)
            self.assertEqual(record["output"]["format"]["sample_rate_hz"], 16_000)
            self.assertEqual(record["output"]["format"]["channels"], 1)

    def test_full_v1_run_is_repeatable_and_does_not_change_sources(self) -> None:
        source_hashes = [sample["audio"]["sha256"] for sample in self.manifest["samples"]]
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = preprocess_corpus(self.manifest, self.corpus_root, Path(first_dir))
            second = preprocess_corpus(self.manifest, self.corpus_root, Path(second_dir))

        self.assertEqual(first["sample_count"], 7)
        self.assertEqual(
            [sample["output"]["sha256"] for sample in first["samples"]],
            [sample["output"]["sha256"] for sample in second["samples"]],
        )
        self.assertTrue(
            all(sample["output"]["format"] == {
                "container": "wav",
                "codec": "pcm-s16le",
                "sample_rate_hz": 16_000,
                "channels": 1,
                "sample_width_bits": 16,
            } for sample in first["samples"])
        )
        self.assertEqual(
            source_hashes,
            [sample["source"]["sha256"] for sample in first["samples"]],
        )

    def test_existing_output_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            existing = output_root / f"{self.manifest['samples'][0]['sample_id']}.wav"
            existing.write_bytes(b"keep-me")

            with self.assertRaises(FileExistsError):
                preprocess_corpus(self.manifest, self.corpus_root, output_root)

            self.assertEqual(existing.read_bytes(), b"keep-me")

    def test_source_audio_cannot_be_selected_as_output(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["samples"] = [
            sample for sample in invalid["samples"]
            if sample["sample_id"] == "silence-001"
        ]
        invalid = with_corpus_fingerprint(invalid)
        with self.assertRaisesRegex(ValueError, "refusing to overwrite source audio"):
            preprocess_corpus(invalid, self.corpus_root, self.corpus_root / "source")


def _write_wave(path: Path, samples: array[int], sample_rate: int, channels: int) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(samples.tobytes())


def _read_wave_samples(path: Path) -> list[int]:
    with wave.open(str(path), "rb") as stream:
        values = array("h")
        values.frombytes(stream.readframes(stream.getnframes()))
    return values.tolist()


if __name__ == "__main__":
    unittest.main()
