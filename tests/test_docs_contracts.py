"""Documentation contract tests.

These tests keep high-risk documentation claims tied to live project surfaces:
local links, generated figures, and the current suite baseline.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

from scripts.generate_figures import CONTEXTUAL_ASSETS, FIGURE_FILES, FIGURE_SOURCES
from scripts.obs_scenario_probe import _image_content_gate, _png_to_rgba_bytes
from scripts.verify_provenance_strip import record_summary, verify_png
from synthobs.scholarship import validate_scholarship_ledger
from synthobs.verification import score_audio_meter_delta

ROOT = Path(__file__).resolve().parents[1]
CURRENT_TEST_COUNT = "1217"
CURRENT_COVERAGE = "96.09"


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


def test_documented_public_symbols_are_reachable_from_package_root() -> None:
    import synthobs

    for name in (
        "COMMON_BUTTONS",
        "DEFAULT_REGIONS_MAX_AGE_S",
        "parse_noaa_plasma_series",
        "parse_noaa_xray_flux",
        "parse_noaa_kp_index",
    ):
        assert name in synthobs.__all__
        assert hasattr(synthobs, name)


def test_todo_is_the_canonical_scoped_backlog() -> None:
    todo = (ROOT / "TODO.md").read_text(encoding="utf-8")
    active_ids = (
        "SYNTHOBS-OBS-CI",
        "SYNTHOBS-OBS-INTERACTION",
        "SYNTHOBS-LIVE-MATRIX",
        "SYNTHOBS-FILTER-VISUALS",
    )
    completed_ids = (
        "SYNTHOBS-C-PARITY",
        "SYNTHOBS-PROV-HMAC",
        "SYNTHOBS-PACKAGE-REPRO",
        "SYNTHOBS-PUBLIC-V1",
        "SYNTHOBS-ARCHIVE-DOI",
    )
    priority = todo.split("## Recently completed", 1)[0]
    completed = todo.split("## Recently completed", 1)[1]
    assert all(item in priority for item in active_ids)
    assert all(item in completed for item in completed_ids)
    for path in (ROOT / "README.md", ROOT / "ROADMAP.md", ROOT / "docs" / "README.md"):
        assert "TODO.md" in path.read_text(encoding="utf-8")


def _markdown_files() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "ROADMAP.md", ROOT / "ISA.md", ROOT / "RELEASE.md"]
    files.extend(sorted((ROOT / "docs").glob("*.md")))
    # preamble.md is renderer input, not a manuscript section; its LaTeX macro
    # arguments use ``{#1}``, which must not be interpreted as a document label.
    files.extend(
        path for path in sorted((ROOT / "manuscript").glob("*.md"))
        if path.name != "preamble.md"
    )
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
    docs_text = "\n".join(
        p.read_text(encoding="utf-8")
        for directory in (ROOT / "docs", ROOT / "manuscript")
        for p in sorted(directory.glob("*.md"))
    )
    refs = set(re.findall(r"\.\./output/figures/([A-Za-z0-9_.-]+\.png)", docs_text))
    assert refs <= manifest, f"documentation references unregistered figures: {refs - manifest}"
    assert set(FIGURE_SOURCES) == manifest

    generated = ROOT / "output" / "figures" / "figure_manifest.json"
    if generated.exists():
        data = json.loads(generated.read_text(encoding="utf-8"))
        assert data["schema"] == "synthobs.figure_manifest.v1"
        assert {item["file"] for item in data["figures"]} == manifest
        assert data["analytical_count"] == 13
        assert data["live_capture_count"] == 3
        assert data["deterministic"] is False
        for item in data["figures"]:
            path = ROOT / "output" / "figures" / item["file"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
            assert tuple(struct.unpack(">II", path.read_bytes()[16:24])) == (
                item["width"],
                item["height"],
            )

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for figure in manifest:
        assert figure in readme


def test_contextual_manuscript_assets_are_not_promoted_figures() -> None:
    asset_dir = ROOT / "manuscript" / "assets" / "obs"
    figure_dir = ROOT / "output" / "figures"
    for name in CONTEXTUAL_ASSETS:
        assert (asset_dir / name).is_file()
        assert name not in FIGURE_FILES
        assert (figure_dir / name).is_file()
        assert name not in {item["file"] for item in json.loads(
            (figure_dir / "figure_manifest.json").read_text(encoding="utf-8")
        )["figures"]}


def test_manuscript_and_docs_contain_no_box_drawing_diagrams() -> None:
    box_chars = "┌┐└┘├┤┬┴┼─│━┃╭╮╰╯═║╔╗╚╝"
    offenders = []
    for directory in (ROOT / "docs", ROOT / "manuscript"):
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if any(char in text for char in box_chars):
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"diagrammatic box-drawing remains in: {offenders}"


def test_versioned_live_obs_evidence_is_schema_valid_and_hashed() -> None:
    asset_dir = ROOT / "manuscript" / "assets" / "obs"
    manifest_path = asset_dir / "obs_manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["schema"] == "synthobs.live_scenario.v2"
    assert data["obs"]["obs_version"] == "32.1.2"
    assert data["obs"]["websocket_version"] == "5.7.3"
    assert data["capture_size"] == {"width": 1280, "height": 720}
    required = data["required_gates"]
    assert len(required) == 6
    assert all(data["gates"][gate]["status"] == "pass" for gate in required)
    assert {"connection", "dashboard_fit_to_canvas", "interaction_model", "render_content", "audio_reactivity", "provenance_lsb"} == set(required)
    for name, record in data["assets"].items():
        path = asset_dir / record["path"]
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record["sha256"]
        if record["media_type"] == "image/png":
            assert raw[:8] == b"\x89PNG\r\n\x1a\n"
            width, height = struct.unpack(">II", raw[16:24])
            assert (width, height) == (1280, 720)
        elif record["media_type"] == "audio/wav":
            assert raw[:4] == b"RIFF" and raw[8:12] == b"WAVE"
        else:
            raise AssertionError(f"unknown evidence media type: {record['media_type']}")

    render = _image_content_gate(asset_dir / "obs_scene_render.png").to_dict()
    assert render["metrics"] == data["gates"]["render_content"]["metrics"]
    silent, sw, sh = _png_to_rgba_bytes(asset_dir / "obs_audio_silent.png")
    tone, tw, th = _png_to_rgba_bytes(asset_dir / "obs_audio_tone.png")
    assert (sw, sh) == (tw, th) == (1280, 720)
    delta = score_audio_meter_delta(silent, tone, sw, sh, channels=4)
    assert delta.to_dict()["mean_abs_delta"] == data["gates"]["audio_reactivity"]["metrics"]["mean_abs_delta"]
    assert delta.to_dict()["max_abs_delta"] == data["gates"]["audio_reactivity"]["metrics"]["max_abs_delta"]
    assert record_summary(verify_png(asset_dir / "obs_telemetry_hud.png")) == {
        key: data["gates"]["provenance_lsb"]["metrics"][key]
        for key in ("flux", "sunspots", "solar_wind_kms", "lock_strength", "phase_bias_rad", "observed_unix", "signature")
    }
    assert data["gates"]["interaction_model"]["metrics"]["live_obs_click"] is False
    assert data["promotion"]["method"] == "scripts/promote_obs_evidence.py"
    assert not data["promotion"]["source_directory"].startswith("/")
    assert (ROOT / "scripts" / "promote_obs_evidence.py").is_file()


def test_cover_uses_the_versioned_real_obs_scene_capture() -> None:
    config = (ROOT / "manuscript" / "config.yaml").read_text(encoding="utf-8")
    assert 'image: "assets/obs/obs_scene_render.png"' in config
    assert "cover_height_fraction: 0.58" in config
    assert (ROOT / "manuscript" / "assets" / "obs" / "obs_scene_render.png").exists()


def test_manuscript_citations_resolve_to_bibliography_keys() -> None:
    bib = (ROOT / "manuscript" / "references.bib").read_text(encoding="utf-8")
    entries = re.findall(r"@(?!(?:comment|string)\b)(\w+)\{([A-Za-z][A-Za-z0-9_-]*),", bib)
    keys = {key for _, key in entries}
    assert len(keys) == len(entries), "duplicate bibliography keys or unsupported entry parsing"
    used: set[str] = set()
    for path in sorted((ROOT / "manuscript").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        used.update(re.findall(r"@([A-Za-z][A-Za-z0-9_-]*)(?![A-Za-z0-9_:-])", text))
    assert used <= keys, f"undefined manuscript citations: {sorted(used - keys)}"
    assert {"obsmodules", "obswebsocket", "noaaswpc", "noaaf107", "noaasunspot", "noaartsw", "libcurl", "nisthalpha", "nasem2019", "wilson2014", "sandve2013", "wilkinson2016fair", "smith2016softwarecitation", "cffschema", "prov2013", "hunter2007matplotlib"} <= used


def test_referenceable_labels_are_unique_and_references_resolve() -> None:
    files = _markdown_files()
    labels: dict[str, list[str]] = {}
    for path in files:
        for match in re.finditer(r"\{#([^}\s]+)", path.read_text(encoding="utf-8")):
            labels.setdefault(match.group(1), []).append(str(path.relative_to(ROOT)))
    duplicates = {label: owners for label, owners in labels.items() if len(owners) > 1}
    assert not duplicates, f"duplicate reference labels: {duplicates}"

    reference_re = re.compile(r"@((?:fig|eq|sec|tbl|lst|def|thm):[A-Za-z0-9_.-]+)")
    missing: list[tuple[str, str]] = []
    for path in files:
        for match in reference_re.finditer(path.read_text(encoding="utf-8")):
            reference = match.group(1).rstrip(".,;:!?\")'")
            if reference not in labels:
                missing.append((str(path.relative_to(ROOT)), reference))
    assert not missing, f"unresolved reference labels: {missing}"


def test_scholarship_ledger_and_repository_citation_metadata_are_contracts() -> None:
    ledger_path = ROOT / "docs" / "scholarship_sources.json"
    bib = (ROOT / "manuscript" / "references.bib").read_text(encoding="utf-8")

    def path_exists(raw_path: str) -> bool:
        return (ROOT / raw_path).exists()

    result = validate_scholarship_ledger(
        json.loads(ledger_path.read_text(encoding="utf-8")), bib, path_exists
    )
    assert result["passed"], result["errors"]
    assert result["source_count"] == 19
    assert result["claim_count"] == 10
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    for token in ("cff-version: 1.2.0", "type: software", "version: \"1.618.0\"", "repository-code:", "license: MIT"):
        assert token in cff
    assert cff.count("doi:") >= 3

    mutant = json.loads(ledger_path.read_text(encoding="utf-8"))
    mutant["sources"][0]["url"] = "https://example.invalid/fabricated"
    assert validate_scholarship_ledger(mutant, bib, path_exists)["passed"] is False


def test_public_distribution_metadata_and_install_contract_are_complete() -> None:
    public_url = "https://github.com/docxology/SynthOBS"
    public_surfaces = (
        ROOT / "README.md",
        ROOT / "docs" / "README.md",
        ROOT / "docs" / "build-and-install.md",
        ROOT / "docs" / "usage.md",
        ROOT / "manuscript" / "00_abstract.md",
        ROOT / "manuscript" / "08_evaluation_reproducibility.md",
        ROOT / "RELEASE.md",
    )
    for path in public_surfaces:
        assert public_url in path.read_text(encoding="utf-8"), (
            f"{path.relative_to(ROOT)} must identify the canonical public repository"
        )

    for path in (ROOT / "CITATION.cff", ROOT / "manuscript" / "config.yaml", ROOT / "manuscript" / "00_abstract.md"):
        assert "FractiAI" in path.read_text(encoding="utf-8"), (
            f"{path.relative_to(ROOT)} must carry the FractiAI affiliation"
        )

    install = (ROOT / "docs" / "build-and-install.md").read_text(encoding="utf-8")
    usage = (ROOT / "docs" / "usage.md").read_text(encoding="utf-8")
    release = (ROOT / "RELEASE.md").read_text(encoding="utf-8")
    assert "git clone https://github.com/docxology/SynthOBS.git" in install
    assert "./build.sh --install" in install
    assert "synthobs_console.py" in release
    assert "Tools → Scripts" in release
    assert "Tools → Scripts" in usage


def test_command_documentation_lists_all_implemented_verbs_and_types() -> None:
    text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "docs/command-grammar.md",
            "manuscript/06_command_grammar.md",
            "manuscript/06b_command_telemetry_parse_pipeline_and_summary.md",
        )
    )
    for token in ("/mode", "/transducer", "/swo", "/dashboard", "DashboardCommand"):
        assert token in text
    assert "There is no fourth branch" not in text


def test_native_live_gate_documentation_matches_manifest() -> None:
    text = (ROOT / "docs" / "native-plugin.md").read_text(encoding="utf-8")
    assert "all six required gates" in text
    assert "render content" in text
    assert "not a claim about click transport" in text


def test_current_status_docs_do_not_contain_stale_baselines() -> None:
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
        ROOT / "docs" / "native-plugin.md",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "scholarship.md",
        ROOT / "manuscript" / "07_implementation.md",
        ROOT / "manuscript" / "02_architecture.md",
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
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "native-plugin.md",
        ROOT / "docs" / "scholarship.md",
        ROOT / "manuscript" / "07_implementation.md",
        ROOT / "manuscript" / "02_architecture.md",
    ]
    for path in status_docs:
        text = path.read_text(encoding="utf-8")
        assert CURRENT_TEST_COUNT in text, f"{path.relative_to(ROOT)} missing current test count"
        assert CURRENT_COVERAGE in text, f"{path.relative_to(ROOT)} missing current coverage"


def test_documented_test_count_matches_real_collection() -> None:
    # Load-bearing: a presence check for an old count silently agrees with a stale
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
