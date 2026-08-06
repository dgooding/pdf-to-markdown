# PDF/DOCX/TXT to MkDocs Markdown Converter

This app converts uploaded documents into MkDocs-compatible markdown packages with extracted assets.

## Live App

- Converter: https://pdf-to-markdown-1gzl.onrender.com/editor
- Searchable documents: https://pdf-to-markdown-1gzl.onrender.com/docs/published/
- Health check: https://pdf-to-markdown-1gzl.onrender.com/health

The public demo runs on Render's free tier, so its first request after inactivity may take up to a minute while the service wakes. Conversion, Markdown downloads, and code-protected publish/delete controls are enabled. A private Render `PUBLISH_SECRET` can override the built-in demo code. Persistent disks require a paid Render plan and are not enabled.

## Run on Windows

1. Install 64-bit Python 3.9.
2. Run `LAUNCH.bat`.
3. Open `http://127.0.0.1:8000/editor` if the browser does not open automatically.

`LAUNCH.bat` installs all pinned dependencies from `wheelhouse/`, so first-run setup works without internet access.

## GitHub Repository Layout

The repository intentionally keeps:

- application source and tests
- the complete offline Python 3.9 wheelhouse
- deterministic generated test fixtures
- the validated benchmark used by manual review tooling
- the strict endpoint parity script and baseline
- MkDocs source and published documents

Generated site output, caches, repeated benchmark runs, analysis output, and temporary parity runs are excluded by `.gitignore`.

Run `cleanup_for_github.ps1 -WhatIf` to preview removable generated files. Run it without `-WhatIf` to return a working copy to the GitHub-ready footprint.

## Architecture Summary

Conversion entry flow:

1. `app.py` receives uploads at `POST /api/convert`
2. Background job creates `ConversionContext`
3. `convert_to_md.py` routes by extension:
   - `convert_pdf_to_markdown`
   - `convert_docx_to_markdown`
   - `convert_text_to_markdown`
   - markdown passthrough/polish
4. `app.py` builds an MkDocs-ready zip (`mkdocs.yml`, `docs/index.md`, `docs/assets/...`)

## Hybrid PDF Pipeline

`convert_pdf_to_markdown()` stages:

1. **PDF inspection** (metadata/pages/content objects)
2. **Page rendering** (deterministic full-page snapshots at configured DPI)
3. **Native extraction** (geometry-aware block ordering + style-aware line parsing)
4. **Table detection** (`page.find_tables()` with confidence heuristics)
   - markdown table when safe
   - HTML table when feasible
   - image fallback when complex/low confidence
5. **Embedded image extraction** with content-hash dedup
6. **Link extraction** from PDF link annotations
7. **OCR fallback** for low-quality or image-heavy pages (if Tesseract available)
8. **Markdown generation** with optional page markers
9. **Post-conversion validation**
10. **JSON manifest generation**

## PDF Modes

In UI/API and CLI:

- `hybrid` (default): best available text + selective visual fallback
- `ocr`: OCR-biased for low-quality native text pages
- `visual`: page-image-first, minimal text extraction

## Validation Guarantees

Validator checks include:

- output markdown exists and is non-empty
- page section coverage
- no unresolved image placeholders (`![][image_...]` patterns)
- local image references resolve to actual files
- no absolute temp/system path leakage in markdown
- heading jump sanity
- suspicious bullet glyph checks
- text coverage estimate

Manifest example location:

- `artifacts/after_hybrid_v2/file-sample_150kb-manifest.json`

## Tests

Test suite: `tests/`

Covers:

- native text PDF
- heading inference PDF
- custom bullet glyph normalization
- image-only PDF fallback
- visual mode behavior
- DOCX conversion with list structure
- TXT conversion
- filenames with spaces/special characters
- integration run for `file-sample_150kB.pdf` (if present)

Run:

- `C:/Python39/python.exe -m unittest discover -s tests -v`

## Key Artifacts

### Strict parity baseline

- baseline output: `artifacts/final_milestone/`
- live comparison script: `artifacts/endpoint_release_check_live/strict_compare_run.py`
- validated benchmark: `artifacts/benchmarks/benchmark_20260731_024647/`

### Diagnostics

- root-cause report: `artifacts/diagnostics/root_cause_report.md`
- page/object inspection: `artifacts/diagnostics/file-sample_150kB_inspection.json`

### Recursive corpus evaluation

`evaluate_corpus.py` regenerates local reports under `test_results/`. These reports are intentionally excluded from Git.

## Remaining Practical Limitations

- Markdown cannot fully preserve arbitrary page-positioned visual layout.
- Complex PDF charts/diagrams are often best represented via rendered region/page images.
- OCR quality depends on Tesseract availability and source image quality.
- Some PDFs contain noisy links/object overlays from authoring tools; link text may require filtering heuristics.
- The currently available `markitdown` package in this environment does not expose the modern `MarkItDown` API, so native deterministic pipeline is primary.
