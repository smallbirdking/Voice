"""Identifiers that connect all evidence produced by one experiment run."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from voice_asr_lab.schema_validation import load_schema, validate_json_schema


RUN_IDENTITY_SCHEMA_VERSION = "1.0.0"
LAB_ROOT = Path(__file__).resolve().parents[2]
RUN_CONTEXT_SCHEMA_PATH = LAB_ROOT / "schemas" / "run-context.schema.json"
LINKED_RECORD_SCHEMA_PATH = LAB_ROOT / "schemas" / "run-linked-record.schema.json"
RUN_ID_PATTERN = re.compile(r"^run-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{12}$")
ENTROPY_PATTERN = re.compile(r"^[0-9a-f]{12}$")
REQUIRED_RECORD_TYPES = frozenset({"sample_result", "resource_sample", "report"})


def create_environment_snapshot_id(snapshot: Mapping[str, Any]) -> str:
    """Return a content-addressed identifier for one exact environment snapshot."""

    canonical_json = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"env-sha256-{hashlib.sha256(canonical_json).hexdigest()}"


def create_run_id(*, now: datetime | None = None, entropy: str | None = None) -> str:
    """Create a readable, unique run identifier using UTC and 48 random bits."""

    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("run timestamp must include timezone information")

    suffix = entropy or secrets.token_hex(6)
    if ENTROPY_PATTERN.fullmatch(suffix) is None:
        raise ValueError("run entropy must contain exactly 12 lowercase hexadecimal characters")

    utc_instant = instant.astimezone(timezone.utc)
    timestamp = utc_instant.strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"run-{timestamp}-{suffix}"
    if RUN_ID_PATTERN.fullmatch(run_id) is None:  # Defensive check for future format edits.
        raise ValueError(f"generated run id has an invalid format: {run_id}")
    return run_id


def create_run_context(
    environment_snapshot: Mapping[str, Any],
    *,
    now: datetime | None = None,
    entropy: str | None = None,
) -> dict[str, str]:
    """Create the two identifiers that every record in a run must carry."""

    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("run timestamp must include timezone information")

    return {
        "schema_version": RUN_IDENTITY_SCHEMA_VERSION,
        "run_id": create_run_id(now=instant, entropy=entropy),
        "environment_snapshot_id": create_environment_snapshot_id(environment_snapshot),
        "created_at": instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def link_record(
    record_type: str,
    payload: Mapping[str, Any],
    context: Mapping[str, str],
) -> dict[str, Any]:
    """Wrap a future result, resource sample, or report in the common linkage fields."""

    return {
        "schema_version": RUN_IDENTITY_SCHEMA_VERSION,
        "record_type": record_type,
        "run_id": context["run_id"],
        "environment_snapshot_id": context["environment_snapshot_id"],
        "payload": dict(payload),
    }


def validate_run_context(context: Mapping[str, Any]) -> list[str]:
    """Return Schema errors for a run context."""

    return validate_json_schema(context, load_schema(RUN_CONTEXT_SCHEMA_PATH))


def validate_linked_record(record: Mapping[str, Any]) -> list[str]:
    """Return Schema errors for one linked record envelope."""

    return validate_json_schema(record, load_schema(LINKED_RECORD_SCHEMA_PATH))


def validate_run_linkage(
    context: Mapping[str, Any],
    environment_snapshot: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Verify that all required evidence refers to one run and one exact snapshot."""

    errors = [f"run_context: {error}" for error in validate_run_context(context)]
    expected_environment_id = create_environment_snapshot_id(environment_snapshot)
    if context.get("environment_snapshot_id") != expected_environment_id:
        errors.append(
            "run_context.environment_snapshot_id does not match the supplied environment snapshot"
        )

    observed_record_types: set[str] = set()
    for index, record in enumerate(records):
        errors.extend(
            f"records[{index}]: {error}" for error in validate_linked_record(record)
        )
        if record.get("run_id") != context.get("run_id"):
            errors.append(f"records[{index}].run_id does not match the run context")
        if record.get("environment_snapshot_id") != context.get("environment_snapshot_id"):
            errors.append(
                f"records[{index}].environment_snapshot_id does not match the run context"
            )
        record_type = record.get("record_type")
        if isinstance(record_type, str):
            observed_record_types.add(record_type)

    missing_types = sorted(REQUIRED_RECORD_TYPES - observed_record_types)
    if missing_types:
        errors.append(f"linked records are missing required types: {', '.join(missing_types)}")
    return errors
