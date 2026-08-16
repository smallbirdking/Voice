"""Corpus content fingerprints for immutable comparison boundaries."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from typing import Any


FINGERPRINT_PREFIX = "corpus-sha256-"
_NON_CONTENT_FIELDS = frozenset({"corpus_version", "created_at", "corpus_fingerprint"})


def compute_corpus_fingerprint(manifest: Mapping[str, Any]) -> str:
    """Hash all comparison-relevant manifest content in canonical JSON form."""

    content = {
        key: copy.deepcopy(value)
        for key, value in manifest.items()
        if key not in _NON_CONTENT_FIELDS
    }
    canonical = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return FINGERPRINT_PREFIX + hashlib.sha256(canonical).hexdigest()


def with_corpus_fingerprint(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copied manifest carrying its computed content fingerprint."""

    versioned = copy.deepcopy(dict(manifest))
    versioned["corpus_fingerprint"] = compute_corpus_fingerprint(versioned)
    return versioned
