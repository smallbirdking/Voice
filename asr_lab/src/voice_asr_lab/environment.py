"""Host environment probes for reproducible local ASR experiments."""

from __future__ import annotations

import ctypes
import locale
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from voice_asr_lab.schema_validation import load_schema, validate_json_schema


HOST_ENVIRONMENT_SCHEMA_VERSION = "1.0.0"
LAB_ROOT = Path(__file__).resolve().parents[2]
HOST_ENVIRONMENT_SCHEMA_PATH = LAB_ROOT / "schemas" / "host-environment.schema.json"


def collect_host_snapshot(workspace: Path) -> dict[str, Any]:
    """Collect a JSON-serializable snapshot without requiring third-party packages."""

    resolved_workspace = workspace.resolve()
    errors: list[str] = []

    memory = _probe_memory(errors)
    disk = _probe_disk(resolved_workspace, errors)

    return {
        "schema_version": HOST_ENVIRONMENT_SCHEMA_VERSION,
        "collected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "architecture": platform.architecture()[0],
        },
        "wsl": _probe_wsl(),
        "cpu": {
            "logical_cores": os.cpu_count(),
            "processor": platform.processor(),
            "identifier": os.environ.get("PROCESSOR_IDENTIFIER"),
            "architecture": os.environ.get("PROCESSOR_ARCHITECTURE"),
        },
        "memory": memory,
        "disk": disk,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
            "is_virtual_environment": sys.prefix != sys.base_prefix,
        },
        "errors": errors,
    }


def validate_host_snapshot(snapshot: dict[str, Any]) -> list[str]:
    """Return schema errors for a host snapshot; an empty list means valid."""

    schema = load_schema(HOST_ENVIRONMENT_SCHEMA_PATH)
    return validate_json_schema(snapshot, schema)


def _probe_wsl() -> dict[str, Any]:
    if platform.system() != "Windows":
        return {
            "executable": None,
            "status": "not-applicable",
            "wsl2_detected": None,
            "details": "Host operating system is not Windows.",
        }

    executable = shutil.which("wsl.exe") or shutil.which("wsl")
    if executable is None:
        return {
            "executable": None,
            "status": "not-installed",
            "wsl2_detected": None,
            "details": "WSL executable was not found on PATH.",
        }

    try:
        result = subprocess.run(
            [executable, "--list", "--verbose"],
            capture_output=True,
            check=False,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return {
            "executable": executable,
            "status": "timeout",
            "wsl2_detected": None,
            "details": "wsl --list --verbose exceeded the 5 second timeout.",
        }
    except OSError as error:
        return {
            "executable": executable,
            "status": "error",
            "wsl2_detected": None,
            "details": str(error),
        }

    details = _decode_command_output(result.stdout + result.stderr)
    versions = [
        int(match.group(1))
        for line in details.splitlines()
        if (match := re.search(r"\s([12])\s*$", line)) is not None
    ]
    detected = 2 in versions if versions else None

    return {
        "executable": executable,
        "status": "available" if result.returncode == 0 else "error",
        "wsl2_detected": detected,
        "details": details or None,
    }


def _probe_memory(errors: list[str]) -> dict[str, Any]:
    try:
        if platform.system() == "Windows":
            return _probe_windows_memory()
        return _probe_posix_memory()
    except (AttributeError, OSError, ValueError) as error:
        errors.append(f"memory probe failed: {error}")
        return {
            "total_bytes": None,
            "available_bytes": None,
            "probe": "unavailable",
        }


def _probe_windows_memory() -> dict[str, Any]:
    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.length = ctypes.sizeof(MemoryStatusEx)

    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError(ctypes.get_last_error(), "GlobalMemoryStatusEx failed")

    return {
        "total_bytes": int(status.total_physical),
        "available_bytes": int(status.available_physical),
        "probe": "windows-global-memory-status",
    }


def _probe_posix_memory() -> dict[str, Any]:
    page_size = os.sysconf("SC_PAGE_SIZE")
    physical_pages = os.sysconf("SC_PHYS_PAGES")
    available_pages = os.sysconf("SC_AVPHYS_PAGES")

    return {
        "total_bytes": int(page_size * physical_pages),
        "available_bytes": int(page_size * available_pages),
        "probe": "posix-sysconf",
    }


def _probe_disk(workspace: Path, errors: list[str]) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(workspace)
        return {
            "path": str(workspace),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        }
    except OSError as error:
        errors.append(f"disk probe failed for {workspace}: {error}")
        return {
            "path": str(workspace),
            "total_bytes": 0,
            "used_bytes": 0,
            "free_bytes": 0,
        }


def _decode_command_output(raw: bytes) -> str:
    if not raw:
        return ""

    encodings: list[str] = []
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw:
        encodings.append("utf-16")
    encodings.extend(["utf-8-sig", locale.getpreferredencoding(False)])

    for encoding in dict.fromkeys(encodings):
        try:
            return raw.decode(encoding).replace("\x00", "").strip()
        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace").replace("\x00", "").strip()

