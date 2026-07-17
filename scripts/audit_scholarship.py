"""Fail-closed audit for the repository scholarship and claim ledger."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "scholarship_sources.json"
BIB = ROOT / "manuscript" / "references.bib"


def _bib_keys() -> set[str]:
    text = BIB.read_text(encoding="utf-8")
    return set(re.findall(r"@(?:article|book|misc|techreport)\{([^,]+),", text))


def validate_scholarship_ledger(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return structured validation results; no check silently defaults to pass."""

    data = payload if payload is not None else json.loads(LEDGER.read_text(encoding="utf-8"))
    errors: list[str] = []
    if data.get("schema") != "synthobs.scholarship_sources.v1":
        errors.append("unexpected scholarship ledger schema")
    sources = data.get("sources")
    claims = data.get("claims")
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a non-empty list")
        sources = []
    if not isinstance(claims, list) or not claims:
        errors.append("claims must be a non-empty list")
        claims = []

    bib_keys = _bib_keys()
    bib_text = BIB.read_text(encoding="utf-8")
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
                if not (ROOT / raw_path).exists():
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


def main() -> int:
    result = validate_scholarship_ledger()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
