"""Documentation contract tests.

These tests keep high-risk documentation claims tied to live project surfaces:
local links, generated figures, and the current suite baseline.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from scripts.generate_figures import FIGURE_FILES

ROOT = Path(__file__).resolve().parents[1]
CURRENT_TEST_COUNT = "1167"
CURRENT_COVERAGE = "98.51"


def test_engine_is_stdlib_only() -> None:
    # Load-bearing guard for the packaging claim ("the tested engine is the single
    # source of truth, with zero third-party runtime dependencies", pyproject core
    # `dependencies = []`). The normal green gate runs with numpy/matplotlib INSTALLED
    # (the `figures`/`dev` extras), so it would NOT catch a stray `import numpy` slipping
    # into src/synthobs and breaking a clean base install. This AST scan does.
    engine = ROOT / "src" / "synthobs"
    stdlib = set(sys.stdlib_module_names)
    allowed = stdlib | {"synthobs"}
    offenders: list[tuple[str, str]] = []
    for py in sorted(engine.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in allowed:
                        offenders.append((py.name, alias.name))
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                top = node.module.split(".")[0]
                if top not in allowed:
                    offenders.append((py.name, node.module))
    assert not offenders, (
        "src/synthobs must import only the stdlib + intra-package (engine is dependency-free "
        f"by packaging contract); found third-party imports: {offenders}"
    )


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
        ROOT / "tests" / "README.md",
        ROOT / "manuscript" / "07_implementation.md",
    ]
    for path in status_docs:
        text = path.read_text(encoding="utf-8")
        assert CURRENT_TEST_COUNT in text, f"{path.relative_to(ROOT)} missing current test count"
        assert CURRENT_COVERAGE in text, f"{path.relative_to(ROOT)} missing current coverage"


def test_documented_test_count_matches_real_collection() -> None:
    # Load-bearing: a presence check (`"1136" in text`) silently agrees with a stale
    # constant. Measure the ACTUAL collected count via a real collect-only subprocess
    # (invocation-independent — does not depend on how THIS session was selected) and
    # require CURRENT_TEST_COUNT to equal it, so adding tests without bumping the
    # baseline (and the docs) fails the gate.
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(ROOT / "tests"), "--collect-only", "-q",
         "-p", "no:cacheprovider"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    m = re.search(r"(\d+)\s+tests?\s+collected", proc.stdout)
    assert m is not None, f"could not parse collected count:\n{proc.stdout[-400:]}"
    measured = m.group(1)
    assert measured == CURRENT_TEST_COUNT, (
        f"CURRENT_TEST_COUNT={CURRENT_TEST_COUNT!r} but the suite actually collects "
        f"{measured!r} tests — update the baseline constant AND the status docs together."
    )
