# Render and validate the blueprint

This workflow generates the analytical figures from the tested engine and
checks the retained OBS captures against the versioned manifest. It requires
no running OBS instance, stream, provider credential, or live telemetry request.
For the separate operator procedure, see [OBS usage](usage.md).

## Prepare the renderer and source

Install uv, Pandoc 3.14, pandoc-crossref 0.3.26, XeLaTeX, BibTeX, and Mermaid CLI
12.2.0 with a Chromium or Chrome Headless Shell executable. Put `mmdc` on
`PATH` and set `PUPPETEER_EXECUTABLE_PATH` to the browser executable if Mermaid
cannot discover it. Clear any inherited Node module overrides before the
shared renderer launches Mermaid.

```bash
git clone https://github.com/docxology/template.git
cd template
git checkout --detach 87704feae0a4490ef7dad9c931d268e8c30273c2
uv sync --locked --no-dev --python 3.14
renderer="$PWD"
mkdir -p projects/working
git clone https://github.com/docxology/SynthOBS.git projects/working/SynthOBS
cd projects/working/SynthOBS
uv sync --locked --extra dev --python 3.15
```

The [manuscript configuration](manuscript/config.yaml) enables PDF and HTML.
The retained scene capture under [manuscript assets](manuscript/assets/obs/)
supplies the cover. The [bibliography](manuscript/references.bib) supplies
citation keys for the ordered sections.

## Generate and check the evidence

```bash
uv run --no-sync python scripts/generate_figures.py
uv run --no-sync python scripts/audit_scholarship.py
uv run --no-sync python -m pytest tests/ --cov=synthobs --cov-fail-under=90
mkdir -p output/manuscript
cp -a docs/manuscript/. output/manuscript/
```

`output/figures/figure_manifest.json` records the analytical figures and retained
captures. `output/figures/figure_registry.json` supplies publication labels and
alternative text, including an operator-context image. That contextual image
has no gate result in the retained scenario manifest.

## Run the pinned stages

```bash
cd "$renderer"
unset NODE_PATH NODE_OPTIONS
uv run --no-sync python scripts/pipeline/stage_03_render.py --project working/SynthOBS
uv run --no-sync python scripts/pipeline/stage_04_validate.py --project working/SynthOBS
```

The staged copy gives the pinned inline Mermaid renderer a writable location
under `output/`. Edit the canonical sources under `docs/manuscript/`.

Look under `projects/working/SynthOBS/output/` for the combined PDF in `pdf/`,
`web/index.html`, and the validation and render provenance reports in `reports/`.
For additional checks see [testing](testing.md) and the [release guide](RELEASE.md).
