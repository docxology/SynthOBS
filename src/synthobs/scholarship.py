"""Fail-closed validation for the scholarship source/claim ledger.

Pure logic: the ledger payload, bibliography text, and repo-relative path
existence are supplied by the caller. This module performs no I/O — the
engine stays side-effect free; ``scripts/audit_scholarship.py`` wires the
repository files in.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

LEDGER_SCHEMA = "synthobs.scholarship_sources.v1"

_BIB_KEY_RE = re.compile(r"@(?:article|book|misc|techreport)\{([^,]+),")


def _bib_keys(bib_text: str) -> set[str]:
    """BibTeX keys declared in ``bib_text`` for supported entry types."""
    return set(_BIB_KEY_RE.findall(bib_text))


def validate_scholarship_ledger(
    data: dict[str, Any],
    bib_text: str,
    path_exists: Callable[[str], bool],
) -> dict[str, Any]:
    """Return structured validation results; no check silently defaults to pass.

    ``data`` is the parsed ledger payload, ``bib_text`` the raw references.bib
    content, and ``path_exists`` maps a repo-relative path from the ledger to
    whether it exists in the audited checkout.
    """
    errors: list[str] = []
    if data.get("schema") != LEDGER_SCHEMA:
        errors.append("unexpected scholarship ledger schema")
    sources = data.get("sources")
    claims = data.get("claims")
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a non-empty list")
        sources = []
    if not isinstance(claims, list) or not claims:
        errors.append("claims must be a non-empty list")
        claims = []

    bib_keys = _bib_keys(bib_text)
    source_keys: set[str] = set()
    for source in sources:
        key = source.get("key") if isinstance(source, dict) else None
        if not isinstance(key, str) or not key or key in source_keys:
            errors.append(f"source key is missing or duplicated: {key!r}")
            continue
        source_keys.add(key)
        if source.get("bib_key") not in bib_keys:
            errors.append(f"source {key!r} has no bibliography entry")
        url = source.get("url")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            errors.append(f"source {key!r} has no absolute URL")
        elif url not in bib_text:
            errors.append(f"source {key!r} URL is not recorded in references.bib")
        if not isinstance(source.get("supports"), list) or not source["supports"]:
            errors.append(f"source {key!r} has no claim mapping")

    claim_ids: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("claim is not an object")
            continue
        claim_id = claim.get("id")
        if not isinstance(claim_id, str) or not claim_id or claim_id in claim_ids:
            errors.append(f"claim id is missing or duplicated: {claim_id!r}")
        else:
            claim_ids.add(claim_id)
        for source_key in claim.get("sources", []):
            if source_key not in source_keys:
                errors.append(f"claim {claim_id!r} references unknown source {source_key!r}")
        for field in ("source_of_truth", "tests", "artifacts"):
            paths = claim.get(field)
            if not isinstance(paths, list) or not paths:
                errors.append(f"claim {claim_id!r} has no {field}")
                continue
            for raw_path in paths:
                if not isinstance(raw_path, str) or not raw_path:
                    errors.append(f"claim {claim_id!r} has an invalid {field} path")
                    continue
                if not path_exists(raw_path):
                    errors.append(f"claim {claim_id!r} points to missing {field} path {raw_path!r}")

    mapped_ids = {claim_id for source in sources for claim_id in source.get("supports", [])}
    if mapped_ids != claim_ids:
        errors.append(f"source/claim mapping mismatch: unmapped={sorted(claim_ids - mapped_ids)}")

    return {
        "schema": data.get("schema"),
        "passed": not errors,
        "source_count": len(sources),
        "claim_count": len(claims),
        "bib_key_count": len(bib_keys),
        "errors": errors,
    }
