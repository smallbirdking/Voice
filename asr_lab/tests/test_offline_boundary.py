"""Tests for the no-cloud-audio boundary and cached offline smoke path."""

from __future__ import annotations

import io
import json
import socket
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from voice_asr_lab.cli import main
from voice_asr_lab.system.offline_boundary import (
    DEFAULT_MANIFEST_PATH,
    NETWORK_POLICY_PATH,
    ExternalNetworkBlocked,
    block_external_network,
    prepare_synthetic_cache,
    run_offline_synthetic_smoke,
    validate_model_cache,
)


class OfflineBoundaryTests(unittest.TestCase):
    def test_policy_allows_model_downloads_but_never_external_test_audio(self) -> None:
        policy = json.loads(NETWORK_POLICY_PATH.read_text(encoding="utf-8"))

        self.assertEqual(policy["phases"]["model_preparation"]["external_network"], "allowed")
        for phase_name, phase in policy["phases"].items():
            with self.subTest(phase=phase_name):
                self.assertIn("test_audio", phase["forbidden_external_payloads"])
        self.assertEqual(policy["phases"]["inference"]["external_network"], "blocked")

    def test_prepared_cache_matches_the_retained_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)

            prepared = prepare_synthetic_cache(cache_root)

            self.assertEqual(prepared["status"], "ready")
            self.assertFalse(prepared["network_used"])
            self.assertEqual(validate_model_cache(cache_root, DEFAULT_MANIFEST_PATH), [])

    def test_cache_tampering_is_rejected_before_the_smoke_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)
            prepared = prepare_synthetic_cache(cache_root)
            Path(prepared["file"]).write_bytes(b"tampered")

            result = run_offline_synthetic_smoke(cache_root, DEFAULT_MANIFEST_PATH)

            self.assertEqual(result["status"], "cache-not-ready")
            self.assertTrue(any("does not match" in error for error in result["errors"]))

    def test_external_destination_is_blocked_before_dns_resolution(self) -> None:
        with patch.object(socket, "getaddrinfo") as resolver:
            with block_external_network():
                with self.assertRaises(ExternalNetworkBlocked):
                    socket.create_connection(("example.invalid", 443), timeout=0.01)

        resolver.assert_not_called()

    def test_loopback_connection_remains_available_for_local_services(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            with block_external_network():
                with socket.create_connection(server.getsockname(), timeout=1) as client:
                    accepted, _ = server.accept()
                    with accepted:
                        client.sendall(b"local")
                        self.assertEqual(accepted.recv(5), b"local")

    def test_cached_synthetic_smoke_completes_with_external_network_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)
            prepare_synthetic_cache(cache_root)

            result = run_offline_synthetic_smoke(cache_root, DEFAULT_MANIFEST_PATH)

            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["cache_ready"])
            self.assertTrue(result["network"]["block_verified_before_dns"])
            self.assertEqual(result["network"]["test_audio_bytes_sent_external"], 0)
            self.assertFalse(result["asr_inference_performed"])

    def test_cli_prepares_then_runs_the_offline_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)
            prepare_output = io.StringIO()
            smoke_output = io.StringIO()

            with redirect_stdout(prepare_output):
                prepare_exit_code = main(
                    ["prepare-synthetic-cache", "--cache-root", str(cache_root)]
                )
            with redirect_stdout(smoke_output):
                smoke_exit_code = main(
                    ["offline-smoke", "--cache-root", str(cache_root)]
                )

            self.assertEqual(prepare_exit_code, 0)
            self.assertEqual(json.loads(prepare_output.getvalue())["status"], "ready")
            self.assertEqual(smoke_exit_code, 0)
            self.assertEqual(json.loads(smoke_output.getvalue())["status"], "passed")


if __name__ == "__main__":
    unittest.main()
