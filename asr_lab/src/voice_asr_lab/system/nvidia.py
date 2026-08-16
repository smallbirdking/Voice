"""NVIDIA system, driver, visibility, and CUDA toolkit probes."""

from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from voice_asr_lab.system.host import LAB_ROOT, _decode_command_output
from voice_asr_lab.core.schema_validation import load_schema, validate_json_schema


NVIDIA_ENVIRONMENT_SCHEMA_VERSION = "1.0.0"
NVIDIA_ENVIRONMENT_SCHEMA_PATH = LAB_ROOT / "schemas" / "nvidia-environment.schema.json"
NVIDIA_QUERY_FIELDS = (
    "index",
    "uuid",
    "name",
    "driver_version",
    "memory.total",
    "memory.free",
)


def collect_nvidia_snapshot() -> dict[str, Any]:
    """Collect NVIDIA visibility without requiring a Python CUDA framework."""

    errors: list[str] = []
    toolkit = _probe_nvcc()
    executable = _find_nvidia_smi()

    if executable is None:
        errors.append("nvidia-smi executable was not found.")
        return _snapshot(
            status="not-installed",
            executable=None,
            return_code=None,
            driver_supported_cuda_version=None,
            toolkit=toolkit,
            gpus=[],
            errors=errors,
        )

    query = f"--query-gpu={','.join(NVIDIA_QUERY_FIELDS)}"
    try:
        result = subprocess.run(
            [executable, query, "--format=csv,noheader,nounits"],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        errors.append("nvidia-smi GPU query exceeded the 10 second timeout.")
        return _snapshot(
            status="timeout",
            executable=executable,
            return_code=None,
            driver_supported_cuda_version=None,
            toolkit=toolkit,
            gpus=[],
            errors=errors,
        )
    except OSError as error:
        errors.append(f"nvidia-smi GPU query could not start: {error}")
        return _snapshot(
            status="error",
            executable=executable,
            return_code=None,
            driver_supported_cuda_version=None,
            toolkit=toolkit,
            gpus=[],
            errors=errors,
        )

    query_output = _decode_command_output(result.stdout)
    query_error = _decode_command_output(result.stderr)
    if result.returncode != 0:
        errors.append(query_error or query_output or f"nvidia-smi exited with code {result.returncode}.")
        return _snapshot(
            status="error",
            executable=executable,
            return_code=result.returncode,
            driver_supported_cuda_version=None,
            toolkit=toolkit,
            gpus=[],
            errors=errors,
        )

    try:
        gpus = _parse_gpu_rows(query_output)
    except ValueError as error:
        errors.append(f"nvidia-smi output could not be parsed: {error}")
        return _snapshot(
            status="error",
            executable=executable,
            return_code=result.returncode,
            driver_supported_cuda_version=None,
            toolkit=toolkit,
            gpus=[],
            errors=errors,
        )

    driver_supported_cuda_version = _probe_driver_supported_cuda_version(executable, errors)
    return _snapshot(
        status="available" if gpus else "no-gpu",
        executable=executable,
        return_code=result.returncode,
        driver_supported_cuda_version=driver_supported_cuda_version,
        toolkit=toolkit,
        gpus=gpus,
        errors=errors,
    )


def validate_nvidia_snapshot(snapshot: dict[str, Any]) -> list[str]:
    """Return schema errors for an NVIDIA snapshot."""

    schema = load_schema(NVIDIA_ENVIRONMENT_SCHEMA_PATH)
    return validate_json_schema(snapshot, schema)


def _snapshot(
    *,
    status: str,
    executable: str | None,
    return_code: int | None,
    driver_supported_cuda_version: str | None,
    toolkit: dict[str, Any],
    gpus: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": NVIDIA_ENVIRONMENT_SCHEMA_VERSION,
        "collected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "nvidia_smi": {
            "executable": executable,
            "return_code": return_code,
            "driver_supported_cuda_version": driver_supported_cuda_version,
        },
        "visibility": {
            "nvidia_smi_visible": bool(gpus),
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "gpu_count": len(gpus),
        },
        "cuda": {"toolkit": toolkit},
        "gpus": gpus,
        "errors": errors,
    }


def _find_nvidia_smi() -> str | None:
    executable = shutil.which("nvidia-smi.exe") or shutil.which("nvidia-smi")
    if executable is not None:
        return executable

    system_root = os.environ.get("SystemRoot")
    if system_root:
        candidate = Path(system_root) / "System32" / "nvidia-smi.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def _parse_gpu_rows(output: str) -> list[dict[str, Any]]:
    if not output.strip():
        return []

    gpus: list[dict[str, Any]] = []
    for row_number, row in enumerate(csv.reader(io.StringIO(output)), start=1):
        if len(row) != len(NVIDIA_QUERY_FIELDS):
            raise ValueError(f"row {row_number} has {len(row)} fields; expected {len(NVIDIA_QUERY_FIELDS)}")

        values = [value.strip() for value in row]
        try:
            index = int(values[0])
            memory_total = int(values[4])
            memory_free = int(values[5])
        except ValueError as error:
            raise ValueError(f"row {row_number} contains a non-integer numeric field") from error

        gpus.append(
            {
                "index": index,
                "uuid": values[1],
                "name": values[2],
                "driver_version": values[3],
                "memory_total_mib": memory_total,
                "memory_free_mib": memory_free,
            }
        )
    return gpus


def _probe_driver_supported_cuda_version(executable: str, errors: list[str]) -> str | None:
    try:
        result = subprocess.run(
            [executable],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        errors.append("nvidia-smi summary exceeded the 10 second timeout.")
        return None
    except OSError as error:
        errors.append(f"nvidia-smi summary could not start: {error}")
        return None

    output = _decode_command_output(result.stdout + result.stderr)
    if result.returncode != 0:
        errors.append(output or f"nvidia-smi summary exited with code {result.returncode}.")
        return None

    match = re.search(r"CUDA Version:\s*([0-9]+(?:\.[0-9]+)*)", output)
    if match is None:
        errors.append("nvidia-smi summary did not contain a CUDA Version field.")
        return None
    return match.group(1)


def _probe_nvcc() -> dict[str, Any]:
    executable = _find_nvcc()
    if executable is None:
        return {
            "status": "not-installed",
            "executable": None,
            "version": None,
            "details": "nvcc was not found on PATH or under CUDA_PATH.",
        }

    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "executable": executable,
            "version": None,
            "details": "nvcc --version exceeded the 10 second timeout.",
        }
    except OSError as error:
        return {
            "status": "error",
            "executable": executable,
            "version": None,
            "details": str(error),
        }

    output = _decode_command_output(result.stdout + result.stderr)
    match = re.search(r"release\s+([0-9]+(?:\.[0-9]+)*)", output, re.IGNORECASE)
    return {
        "status": "available" if result.returncode == 0 else "error",
        "executable": executable,
        "version": match.group(1) if match else None,
        "details": output or None,
    }


def _find_nvcc() -> str | None:
    executable = shutil.which("nvcc.exe") or shutil.which("nvcc")
    if executable is not None:
        return executable

    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        candidate_names = ("nvcc.exe", "nvcc")
        for name in candidate_names:
            candidate = Path(cuda_path) / "bin" / name
            if candidate.is_file():
                return str(candidate)
    return None
