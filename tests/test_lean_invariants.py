"""Lean invariant scaffold checks.

The Python engine remains the runtime source of truth. These tests keep the optional
Lean scaffold buildable when Lake is present and reject proof placeholders.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEAN_ROOT = ROOT / "lean"


def _lean_files() -> list[Path]:
    return sorted(LEAN_ROOT.glob("**/*.lean"))


def test_lean_scaffold_has_no_sorry_or_axiom() -> None:
    assert (LEAN_ROOT / "lakefile.lean").is_file()
    assert (LEAN_ROOT / "SynthOBS" / "Invariants.lean").is_file()
    for path in _lean_files():
        text = path.read_text(encoding="utf-8")
        assert "sorry" not in text
        assert "axiom " not in text


def test_lean_scaffold_builds_when_lake_is_available() -> None:
    lake = shutil.which("lake")
    if lake is None:
        pytest.skip("Lake is not installed")

    result = subprocess.run(
        [lake, "build"],
        cwd=LEAN_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
