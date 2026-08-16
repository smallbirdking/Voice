"""System boundary proving cached experiments can run without external network."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from voice_asr_lab.core.paths import LAB_ROOT

DEFAULT_CACHE_ROOT = LAB_ROOT / "models" / "cache"
DEFAULT_MANIFEST_PATH = LAB_ROOT / "models" / "manifests" / "synthetic-smoke.json"
NETWORK_POLICY_PATH = LAB_ROOT / "network-policy.json"
SYNTHETIC_MARKER_PATH = Path("synthetic-smoke/model.marker")
SYNTHETIC_MARKER_BYTES = b"voice-asr-lab synthetic cache marker v1\n"
SYNTHETIC_AUDIO_BYTES = b"\x00\x00" * 1600
_NETWORK_GUARD_LOCK = threading.RLock()


class ExternalNetworkBlocked(RuntimeError):
    """Raised before a non-loopback address can be resolved or connected."""


def prepare_synthetic_cache(cache_root: Path = DEFAULT_CACHE_ROOT) -> dict[str, Any]:
    """Create the deterministic tiny cache fixture used by the offline smoke test."""

    cache_file = (cache_root / SYNTHETIC_MARKER_PATH).resolve()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(SYNTHETIC_MARKER_BYTES)
    return {
        "status": "ready",
        "model_id": "synthetic-smoke-cache-v1",
        "cache_root": str(cache_root.resolve()),
        "file": str(cache_file),
        "size_bytes": len(SYNTHETIC_MARKER_BYTES),
        "sha256": hashlib.sha256(SYNTHETIC_MARKER_BYTES).hexdigest(),
        "network_used": False,
    }


def validate_model_cache(
    cache_root: Path = DEFAULT_CACHE_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> list[str]:
    """Verify every manifest file exists under the cache root with exact content."""

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"model cache manifest could not be loaded: {error}"]

    errors: list[str] = []
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        return ["model cache manifest must contain at least one file"]

    resolved_root = cache_root.resolve()
    for index, entry in enumerate(files):
        if not isinstance(entry, Mapping):
            errors.append(f"files[{index}] must be an object")
            continue
        relative_path = entry.get("path")
        if not isinstance(relative_path, str) or not relative_path:
            errors.append(f"files[{index}].path must be a non-empty string")
            continue

        candidate = (resolved_root / relative_path).resolve()
        try:
            candidate.relative_to(resolved_root)
        except ValueError:
            errors.append(f"files[{index}].path escapes the model cache root")
            continue
        if not candidate.is_file():
            errors.append(f"cached model file is missing: {relative_path}")
            continue

        content = candidate.read_bytes()
        if len(content) != entry.get("size_bytes"):
            errors.append(f"cached model file size does not match: {relative_path}")
        if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
            errors.append(f"cached model file SHA-256 does not match: {relative_path}")
    return errors


def run_offline_synthetic_smoke(
    cache_root: Path = DEFAULT_CACHE_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Read a verified cache and process synthetic PCM while external sockets are blocked."""

    cache_errors = validate_model_cache(cache_root, manifest_path)
    if cache_errors:
        return {
            "status": "cache-not-ready",
            "cache_ready": False,
            "errors": cache_errors,
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    marker = (cache_root.resolve() / manifest["files"][0]["path"]).read_bytes()
    external_block_verified = False

    with block_external_network():
        try:
            connection = socket.create_connection(("example.invalid", 443), timeout=0.01)
        except ExternalNetworkBlocked:
            external_block_verified = True
        else:  # pragma: no cover - a guard regression would make this branch fail the smoke test.
            connection.close()

        if not external_block_verified:
            return {
                "status": "network-guard-failed",
                "cache_ready": True,
                "errors": ["external connection was not blocked before DNS resolution"],
            }

        local_result_digest = hashlib.sha256(marker + SYNTHETIC_AUDIO_BYTES).hexdigest()

    return {
        "status": "passed",
        "cache_ready": True,
        "model_id": manifest["model_id"],
        "asr_inference_performed": False,
        "operation": "local-cache-read-and-synthetic-pcm-hash",
        "synthetic_audio": {
            "format": "16-bit-mono-pcm",
            "sample_rate_hz": 16000,
            "duration_ms": 100,
            "size_bytes": len(SYNTHETIC_AUDIO_BYTES),
            "sha256": hashlib.sha256(SYNTHETIC_AUDIO_BYTES).hexdigest(),
        },
        "network": {
            "policy_id": "local-asr-no-cloud-audio",
            "external_network": "blocked",
            "loopback_network": "allowed",
            "block_verified_before_dns": external_block_verified,
            "verification_destination": "example.invalid:443",
            "test_audio_bytes_sent_external": 0,
            "enforcement_scope": "current-python-process-socket-api",
        },
        "local_result_digest": local_result_digest,
        "errors": [],
    }


@contextmanager
def block_external_network() -> Iterator[None]:
    """Block non-loopback Python socket resolution and connection for this process."""

    with _NETWORK_GUARD_LOCK:
        original_create_connection = socket.create_connection
        original_getaddrinfo = socket.getaddrinfo
        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex

        def guarded_create_connection(address: tuple[str, int], *args: Any, **kwargs: Any) -> socket.socket:
            _require_loopback(address[0])
            return original_create_connection(address, *args, **kwargs)

        def guarded_getaddrinfo(host: str | bytes | None, *args: Any, **kwargs: Any) -> list[Any]:
            if host is not None:
                _require_loopback(host)
            return original_getaddrinfo(host, *args, **kwargs)

        def guarded_connect(sock: socket.socket, address: Any) -> Any:
            if sock.family != getattr(socket, "AF_UNIX", object()):
                _require_loopback(_address_host(address))
            return original_connect(sock, address)

        def guarded_connect_ex(sock: socket.socket, address: Any) -> Any:
            if sock.family != getattr(socket, "AF_UNIX", object()):
                _require_loopback(_address_host(address))
            return original_connect_ex(sock, address)

        socket.create_connection = guarded_create_connection
        socket.getaddrinfo = guarded_getaddrinfo
        socket.socket.connect = guarded_connect
        socket.socket.connect_ex = guarded_connect_ex
        try:
            yield
        finally:
            socket.create_connection = original_create_connection
            socket.getaddrinfo = original_getaddrinfo
            socket.socket.connect = original_connect
            socket.socket.connect_ex = original_connect_ex


def _address_host(address: Any) -> str | bytes:
    if not isinstance(address, tuple) or not address:
        raise ExternalNetworkBlocked(f"unsupported network address was blocked: {address!r}")
    return address[0]


def _require_loopback(host: str | bytes) -> None:
    normalized = host.decode("ascii", errors="strict") if isinstance(host, bytes) else host
    if normalized.lower().rstrip(".") == "localhost":
        return
    try:
        if ipaddress.ip_address(normalized).is_loopback:
            return
    except ValueError:
        pass
    raise ExternalNetworkBlocked(f"external network destination was blocked: {normalized}")
