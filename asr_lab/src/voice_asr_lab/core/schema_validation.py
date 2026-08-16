"""Core JSON Schema subset used while the lab has no runtime dependencies."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def load_schema(path: Path) -> dict[str, Any]:
    """Load a JSON schema from disk."""

    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def validate_json_schema(instance: Any, schema: Mapping[str, Any], path: str = "$") -> list[str]:
    """Validate the JSON Schema features used by the lab's versioned contracts."""

    errors: list[str] = []
    expected_type = schema.get("type")

    if expected_type is not None and not _matches_type(instance, expected_type):
        errors.append(f"{path}: expected type {expected_type!r}, got {type(instance).__name__}")
        return errors

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}, got {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}, got {instance!r}")

    if isinstance(instance, str):
        minimum_length = schema.get("minLength")
        if minimum_length is not None and len(instance) < minimum_length:
            errors.append(f"{path}: string is shorter than {minimum_length}")

        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, instance) is None:
            errors.append(f"{path}: string does not match pattern {pattern!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            errors.append(f"{path}: value {instance!r} is less than {minimum!r}")

    if isinstance(instance, Mapping):
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for name in required:
            if name not in instance:
                errors.append(f"{path}: missing required property {name!r}")

        if schema.get("additionalProperties") is False:
            for name in instance:
                if name not in properties:
                    errors.append(f"{path}: unexpected property {name!r}")

        for name, value in instance.items():
            if name in properties:
                errors.extend(validate_json_schema(value, properties[name], f"{path}.{name}"))

    if isinstance(instance, list):
        minimum_items = schema.get("minItems")
        if minimum_items is not None and len(instance) < minimum_items:
            errors.append(f"{path}: array has fewer than {minimum_items} items")

        if "items" in schema:
            for index, value in enumerate(instance):
                errors.extend(validate_json_schema(value, schema["items"], f"{path}[{index}]"))

    return errors


def _matches_type(instance: Any, expected: str | list[str]) -> bool:
    expected_types = [expected] if isinstance(expected, str) else expected
    return any(_matches_single_type(instance, item) for item in expected_types)


def _matches_single_type(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, Mapping)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    raise ValueError(f"unsupported JSON Schema type: {expected}")
