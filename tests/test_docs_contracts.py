"""Documentation contract tests.

These tests keep high-risk documentation claims tied to live project surfaces:
local links, generated figures, and the current suite baseline.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.generate_figures import FIGURE_FILES

ROOT = Path(__file__).resolve().parents[1]
CURRENT_TEST_COUNT = "1136"
CURRENT_COVERAGE = "98.37"


def _markdown_files() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "ROADMAP.md", ROOT / "ISA.md"]
    files.extend(sorted((ROOT / "docs").glob("*.md")))
    files.extend(sorted((ROOT / "manuscript").glob("*.md")))
    return files


def test_local_markdown_links_resolve() -> None:
    link_re = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8")
        for raw in link_re.findall(text):
            target = raw.split()[0].strip("<>")
            if (
                target.startswith(("http://", "https://", "mailto:"))
                or target.startswith("#")
                or target.startswith("../output/figures/")
            ):
                continue
            target_path = (path.parent / target.split("#", 1)[0]).resolve()
            assert target_path.exists(), f"{path.relative_to(ROOT)} links missing {raw}"


def test_figure_references_match_generator_manifest() -> None:
    manifest = set(FIGURE_FILES)
    manuscript_text = "\n".join(
        p.read_text(encoding="utf-8") for p in sorted((ROOT / "manuscript").glob("*.md"))
    )
    refs = set(re.findall(r"\.\./output/figures/([A-Za-z0-9_.-]+\.png)", manuscript_text))
    assert refs == manifest

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for figure in manifest:
        assert figure in readme


def test_current_status_docs_do_not_contain_legacy_baselines() -> None:
    stale = (
        "848 tests",
        "859 tests",
        "889 passed",
        "889-test",
        "1021 tests",
        "1021-test",
        "1021 passed",
        "1024 tests",
        "1024-test",
        "1024 passed",
        "1067 passing",
        "1067 tests",
        "1075 passed",
        "1101 tests",
        "1101-test",
        "1101 passed",
        "1101 passing",
        "1108 tests",
        "1108-test",
        "1108 passed",
        "1108 passing",
        "1115 tests",
        "1115-test",
        "1115 passed",
        "1115 passing",
        "1132 tests",
        "1132-test",
        "1132 passed",
        "1132 passing",
        "94.70",
        "94.85",
        "97.86",
        "97.88",
        "98.11",
        "98.13",
        "98.18",
        "96.95",
    )
    status_docs = [
        ROOT / "README.md",
        ROOT / "ROADMAP.md",
        ROOT / "docs" / "README.md",
        ROOT / "docs" / "testing.md",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "native-plugin.md",
        ROOT / "manuscript" / "07_implementation.md",
    ]
    for path in status_docs:
        text = path.read_text(encoding="utf-8")
        for token in stale:
            assert token not in text, f"{path.relative_to(ROOT)} still contains {token!r}"


def test_current_status_docs_pin_live_suite_baseline() -> None:
    status_docs = [
        ROOT / "README.md",
        ROOT / "docs" / "README.md",
        ROOT / "docs" / "testing.md",
        ROOT / "manuscript" / "07_implementation.md",
    ]
    for path in status_docs:
        text = path.read_text(encoding="utf-8")
        assert CURRENT_TEST_COUNT in text, f"{path.relative_to(ROOT)} missing current test count"
        assert CURRENT_COVERAGE in text, f"{path.relative_to(ROOT)} missing current coverage"
