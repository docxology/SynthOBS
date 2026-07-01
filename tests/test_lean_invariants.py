"""Lean invariant scaffold checks.

The Python engine remains the runtime source of truth. These tests keep the optional
Lean scaffold buildable when Lake is present and reject proof placeholders.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from synthobs.constants import EGS_GATEWAY_KEY_C_LITERAL, PHI_C_LITERAL

ROOT = Path(__file__).resolve().parents[1]
LEAN_ROOT = ROOT / "lean"
INVARIANTS = LEAN_ROOT / "SynthOBS" / "Invariants.lean"


def _lean_files() -> list[Path]:
    return sorted(LEAN_ROOT.glob("**/*.lean"))


def _lean_string_def(name: str, text: str) -> str:
    """Extract the body of `def <name> : String := "..."` from Lean source."""
    m = re.search(rf'def\s+{re.escape(name)}\s*:\s*String\s*:=\s*"([^"]*)"', text)
    if m is None:
        raise AssertionError(f"Lean def {name} : String not found in Invariants.lean")
    return m.group(1)


def test_lean_literal_pins_bind_to_python_constants() -> None:
    # The Lean phiLiteral / egsGatewayKeyLiteral are otherwise self-referential
    # (`rfl` against a hardcoded copy), so Lean could silently drift from the engine.
    # Bind them to the SAME single-source constants the C plugin is pinned against,
    # so a Lean edit that diverges from synthobs.constants fails this gate.
    text = INVARIANTS.read_text(encoding="utf-8")
    assert _lean_string_def("phiLiteral", text) == PHI_C_LITERAL
    assert _lean_string_def("egsGatewayKeyLiteral", text) == EGS_GATEWAY_KEY_C_LITERAL


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
