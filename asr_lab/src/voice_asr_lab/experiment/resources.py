"""Failure-tolerant CPU, process memory, and NVIDIA GPU resource sampling."""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from voice_asr_lab.core.paths import LAB_ROOT
from voice_asr_lab.core.schema_validation import load_schema, validate_json_schema
from voice_asr_lab.experiment.timing import Clock, format_utc


RESOURCE_SAMPLE_SCHEMA = LAB_ROOT / "schemas" / "resource-sample.schema.json"
ProcessProbe = Callable[[], tuple[int, int]]
GpuProbe = Callable[[], list[dict[str, Any]]]


class ResourceSampler:
    def __init__(
        self,
        clock: Clock,
        *,
        process_probe: ProcessProbe | None = None,
        gpu_probe: GpuProbe | None = None,
    ) -> None:
        self.clock = clock
        self.process_probe = process_probe or probe_current_process
        self.gpu_probe = gpu_probe or probe_nvidia_gpus
        self._sequence = 0
        self._previous_ns: int | None = None
        self._previous_cpu_ns: int | None = None

    def sample(self, context: Mapping[str, str]) -> dict[str, Any]:
        point_ns = self.clock.monotonic_ns()
        errors: list[dict[str, str]] = []
        cpu_time_ns: int | None = None
        memory_rss_bytes: int | None = None
        try:
            cpu_time_ns, memory_rss_bytes = self.process_probe()
        except Exception as error:  # Sampling evidence must never stop inference.
            errors.append(_error("process", error))

        gpu_status = "available"
        gpu_devices: list[dict[str, Any]] = []
        try:
            gpu_devices = self.gpu_probe()
            if not gpu_devices:
                gpu_status = "unavailable"
        except FileNotFoundError as error:
            gpu_status = "unavailable"
            errors.append(_error("gpu", error))
        except Exception as error:  # Sampling evidence must never stop inference.
            gpu_status = "error"
            errors.append(_error("gpu", error))

        cpu_percent = self._cpu_percent(point_ns, cpu_time_ns)
        sequence = self._sequence
        result = {
            "schema_version": "1.0.0",
            "record_type": "resource_sample",
            "run_id": context["run_id"],
            "environment_snapshot_id": context["environment_snapshot_id"],
            "provider_id": context["provider_id"],
            "session_id": context["session_id"],
            "sample_id": context["sample_id"],
            "resource_sample_id": f"resource-sample-{sequence + 1:06d}",
            "sequence": sequence,
            "monotonic_ns": point_ns,
            "wall_time": format_utc(self.clock.utc_now()),
            "cpu": {
                "process_time_ms": cpu_time_ns / 1_000_000 if cpu_time_ns is not None else None,
                "percent_since_previous": cpu_percent,
            },
            "process": {"memory_rss_bytes": memory_rss_bytes},
            "gpu": {"status": gpu_status, "devices": gpu_devices},
            "errors": errors,
        }
        self._sequence += 1
        self._previous_ns = point_ns
        self._previous_cpu_ns = cpu_time_ns
        return result

    def _cpu_percent(self, point_ns: int, cpu_time_ns: int | None) -> float | None:
        if self._previous_ns is None or self._previous_cpu_ns is None or cpu_time_ns is None:
            return None
        elapsed_ns = point_ns - self._previous_ns
        cpu_elapsed_ns = cpu_time_ns - self._previous_cpu_ns
        if elapsed_ns <= 0 or cpu_elapsed_ns < 0:
            return None
        return cpu_elapsed_ns * 100 / elapsed_ns


def validate_resource_sample(sample: Any) -> list[str]:
    errors = validate_json_schema(sample, load_schema(RESOURCE_SAMPLE_SCHEMA))
    if isinstance(sample, Mapping):
        gpu = sample.get("gpu")
        if isinstance(gpu, Mapping):
            status = gpu.get("status")
            devices = gpu.get("devices")
            if status == "available" and isinstance(devices, list) and not devices:
                errors.append("$.gpu.devices: available status requires at least one device")
            if status != "available" and isinstance(devices, list) and devices:
                errors.append("$.gpu.devices: unavailable or error status must not contain devices")
    return errors


def probe_current_process() -> tuple[int, int]:
    return time.process_time_ns(), _memory_rss_bytes()


def probe_nvidia_gpus() -> list[dict[str, Any]]:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,utilization.gpu,memory.used,memory.free",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or f"nvidia-smi exited with {completed.returncode}"
        raise RuntimeError(message)
    devices: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 5:
            raise ValueError(f"unexpected nvidia-smi row: {line!r}")
        devices.append(
            {
                "index": int(fields[0]),
                "uuid": fields[1],
                "utilization_percent": _number_or_none(fields[2]),
                "memory_used_mib": _number_or_none(fields[3]),
                "memory_free_mib": _number_or_none(fields[4]),
            }
        )
    return devices


def _memory_rss_bytes() -> int:
    if platform.system() == "Windows":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ProcessMemoryCounters),
            ctypes.c_ulong,
        ]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        handle = kernel32.GetCurrentProcess()
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(counters.WorkingSetSize)
    statm = Path("/proc/self/statm")
    if statm.exists():
        resident_pages = int(statm.read_text(encoding="ascii").split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if platform.system() == "Darwin" else value * 1024)


def _number_or_none(value: str) -> float | None:
    return None if value in {"N/A", "[Not Supported]"} else float(value)


def _error(collector: str, error: Exception) -> dict[str, str]:
    return {"collector": collector, "type": type(error).__name__, "message": str(error) or repr(error)}
