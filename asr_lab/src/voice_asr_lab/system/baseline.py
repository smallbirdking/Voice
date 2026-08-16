"""Collect, validate, and preserve complete ASR lab system baselines."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from voice_asr_lab import __version__
from voice_asr_lab.system.host import collect_host_snapshot, validate_host_snapshot
from voice_asr_lab.core.identifiers import create_environment_snapshot_id
from voice_asr_lab.system.nvidia import collect_nvidia_snapshot, validate_nvidia_snapshot
from voice_asr_lab.core.schema_validation import load_schema, validate_json_schema


BASELINE_SCHEMA_VERSION = "1.0.0"
LAB_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = LAB_ROOT.parent
BASELINE_SCHEMA_PATH = LAB_ROOT / "schemas" / "environment-baseline.schema.json"
DEFAULT_BASELINE_OUTPUT = LAB_ROOT / "reports" / "baselines" / "environment-baseline-v1.json"
NETWORK_POLICY_PATH = LAB_ROOT / "network-policy.json"
STORAGE_LAYOUT_PATH = LAB_ROOT / "storage-layout.json"
DEPENDENCY_LOCK_PATH = LAB_ROOT / "uv.lock"


def collect_environment_baseline(
    workspace: Path = REPOSITORY_ROOT,
    *,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """Collect one content-addressed baseline from all established probes and policies."""

    instant = captured_at or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("baseline timestamp must include timezone information")

    errors: list[str] = []
    network_policy = _load_json_file(NETWORK_POLICY_PATH, "network policy", errors)
    storage_layout = _load_json_file(STORAGE_LAYOUT_PATH, "storage layout", errors)
    host_snapshot = collect_host_snapshot(workspace)
    nvidia_snapshot = collect_nvidia_snapshot()

    baseline_content: dict[str, Any] = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "captured_at": instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "host": host_snapshot,
        "nvidia": nvidia_snapshot,
        "project": {
            "name": "voice-asr-lab",
            "version": __version__,
            "dependency_lock": {
                "path": "uv.lock",
                "sha256": _file_sha256(DEPENDENCY_LOCK_PATH, "dependency lock", errors),
            },
        },
        "policies": {
            "network": {
                "path": "network-policy.json",
                "policy_id": network_policy.get("policy_id") if network_policy else None,
                "sha256": _file_sha256(NETWORK_POLICY_PATH, "network policy", errors),
            },
            "storage": {
                "path": "storage-layout.json",
                "schema_version": storage_layout.get("schema_version") if storage_layout else None,
                "sha256": _file_sha256(STORAGE_LAYOUT_PATH, "storage layout", errors),
            },
        },
        "source_control": _probe_source_control(workspace),
        "errors": errors,
    }
    return {
        "environment_snapshot_id": create_environment_snapshot_id(baseline_content),
        **baseline_content,
    }


def validate_environment_baseline(baseline: Mapping[str, Any]) -> list[str]:
    """Validate the baseline Schema, nested probes, and content-addressed identifier."""

    errors = validate_json_schema(baseline, load_schema(BASELINE_SCHEMA_PATH))
    host = baseline.get("host")
    nvidia = baseline.get("nvidia")
    if isinstance(host, dict):
        errors.extend(f"$.host: {error}" for error in validate_host_snapshot(host))
    if isinstance(nvidia, dict):
        errors.extend(f"$.nvidia: {error}" for error in validate_nvidia_snapshot(nvidia))

    content = {key: value for key, value in baseline.items() if key != "environment_snapshot_id"}
    expected_id = create_environment_snapshot_id(content)
    if baseline.get("environment_snapshot_id") != expected_id:
        errors.append("$.environment_snapshot_id: does not match baseline content")
    return errors


def write_environment_baseline(baseline: Mapping[str, Any], output_path: Path) -> Path:
    """Save a valid baseline once; refuse to overwrite existing evidence."""

    errors = validate_environment_baseline(baseline)
    if errors:
        raise ValueError("environment baseline is invalid: " + "; ".join(errors))

    resolved_output = output_path.resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    with resolved_output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(baseline, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return resolved_output


def _load_json_file(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{label} could not be loaded: {error}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} must contain a JSON object")
        return {}
    return value


def _file_sha256(path: Path, label: str, errors: list[str]) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        errors.append(f"{label} could not be hashed: {error}")
        return None


def _probe_source_control(workspace: Path) -> dict[str, Any]:
    root = _run_git(workspace, "rev-parse", "--show-toplevel")
    if root["error"] is not None:
        return {
            "repository_root": None,
            "head_commit": None,
            "dirty": None,
            "error": root["error"],
        }

    repository_root = Path(root["output"])
    head = _run_git(repository_root, "rev-parse", "HEAD")
    status = _run_git(repository_root, "status", "--porcelain", "--untracked-files=normal")
    errors = [item["error"] for item in (head, status) if item["error"] is not None]
    return {
        "repository_root": str(repository_root.resolve()),
        "head_commit": head["output"] or None,
        "dirty": bool(status["output"]) if status["error"] is None else None,
        "error": "; ".join(errors) if errors else None,
    }


def _run_git(workspace: Path, *arguments: str) -> dict[str, str | None]:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=workspace,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"output": "", "error": str(error)}

    output = result.stdout.strip()
    error_output = result.stderr.strip()
    if result.returncode != 0:
        return {
            "output": output,
            "error": error_output or f"git exited with code {result.returncode}",
        }
    return {"output": output, "error": None}
