"""Fail-closed audit for the repository scholarship and claim ledger.

Thin orchestrator: reads the ledger and bibliography from the repository and
delegates validation to the tested engine (``synthobs.scholarship``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from synthobs.scholarship import validate_scholarship_ledger  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "scholarship_sources.json"
BIB = ROOT / "manuscript" / "references.bib"


def main() -> int:
    result = validate_scholarship_ledger(
        json.loads(LEDGER.read_text(encoding="utf-8")),
        BIB.read_text(encoding="utf-8"),
        path_exists=lambda raw_path: (ROOT / raw_path).exists(),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
