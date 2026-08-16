"""Tests for PCM file input and single-stream replay rhythm."""

from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from voice_asr_lab.experiment.replay import AudioChunk, load_wave_audio, replay_wave
from voice_asr_lab.experiment.timing import ManualClock


class ReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "input.wav"
        self.pcm = bytes(index % 251 for index in range(8_000))
        with wave.open(str(self.path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16_000)
            output.writeframes(self.pcm)

    def test_file_input_preserves_pcm_and_media_duration(self) -> None:
        audio = load_wave_audio(self.path)

        self.assertEqual(audio.pcm_bytes, self.pcm)
        self.assertEqual(audio.frame_count, 4_000)
        self.assertEqual(audio.duration_ms, 250.0)
        self.assertEqual((audio.sample_rate_hz, audio.channels, audio.sample_width_bits), (16_000, 1, 16))

    def test_realtime_replay_uses_actual_last_chunk_duration_and_offsets(self) -> None:
        audio = load_wave_audio(self.path)
        clock = ManualClock(1_000_000_000)
        chunks: list[AudioChunk] = []

        summary = replay_wave(audio, chunk_ms=100, mode="realtime", clock=clock, sink=chunks.append)

        self.assertEqual([chunk.duration_ms for chunk in chunks], [100.0, 100.0, 50.0])
        self.assertEqual([chunk.audio_offset_ms for chunk in chunks], [100.0, 200.0, 250.0])
        self.assertEqual(
            [chunk.available_monotonic_ns for chunk in chunks],
            [1_100_000_000, 1_200_000_000, 1_250_000_000],
        )
        self.assertEqual(summary.elapsed_ms, audio.duration_ms)
        self.assertEqual(b"".join(chunk.pcm_bytes for chunk in chunks), self.pcm)

    def test_offline_replay_emits_same_audio_without_advancing_time(self) -> None:
        audio = load_wave_audio(self.path)
        clock = ManualClock(7_000_000_000)
        chunks: list[AudioChunk] = []

        summary = replay_wave(audio, chunk_ms=100, mode="offline", clock=clock, sink=chunks.append)

        self.assertEqual(summary.elapsed_ms, 0.0)
        self.assertEqual(summary.chunk_count, 3)
        self.assertEqual(summary.emitted_bytes, len(self.pcm))
        self.assertTrue(all(chunk.available_monotonic_ns == 7_000_000_000 for chunk in chunks))

    def test_invalid_chunk_duration_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            replay_wave(
                load_wave_audio(self.path),
                chunk_ms=0,
                mode="offline",
                clock=ManualClock(),
                sink=lambda _: None,
            )


if __name__ == "__main__":
    unittest.main()
