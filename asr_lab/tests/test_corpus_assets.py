"""Tests for deterministic project-owned corpus audio assets."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
import wave
from pathlib import Path

from voice_asr_lab.corpus.assets import (
    concatenate_pcm16_waves,
    write_noise_wave,
    write_silence_wave,
)


class CorpusAssetTests(unittest.TestCase):
    def test_silence_is_exact_duration_and_contains_only_zero_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "silence.wav"
            write_silence_wave(output, duration_ms=1_250, sample_rate=16_000, channels=1)

            with wave.open(str(output), "rb") as stream:
                frames = stream.readframes(stream.getnframes())
                self.assertEqual(stream.getnframes(), 20_000)
                self.assertEqual(stream.getframerate(), 16_000)
                self.assertEqual(stream.getnchannels(), 1)
                self.assertEqual(set(frames), {0})

    def test_noise_is_deterministic_and_non_silent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.wav"
            second = Path(temp_dir) / "second.wav"
            write_noise_wave(first, duration_ms=500)
            write_noise_wave(second, duration_ms=500)

            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            with wave.open(str(first), "rb") as stream:
                self.assertNotEqual(set(stream.readframes(stream.getnframes())), {0})

    def test_concatenation_preserves_components_and_inserts_exact_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.wav"
            second = root / "second.wav"
            output = root / "mixed.wav"
            write_noise_wave(first, duration_ms=100, sample_rate=16_000, channels=1, seed=1)
            write_noise_wave(second, duration_ms=200, sample_rate=16_000, channels=1, seed=2)

            concatenate_pcm16_waves([first, second], output, gap_ms=250)

            with wave.open(str(output), "rb") as stream:
                self.assertEqual(stream.getnframes(), 8_800)
                stream.setpos(1_600)
                self.assertEqual(set(stream.readframes(4_000)), {0})

    def test_asset_writers_refuse_to_overwrite_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "source.wav"
            write_silence_wave(output, duration_ms=100)

            with self.assertRaises(FileExistsError):
                write_silence_wave(output, duration_ms=100)


if __name__ == "__main__":
    unittest.main()
