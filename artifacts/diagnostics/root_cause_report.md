# Root-Cause Report: PDF → Markdown Fidelity

## Current conversion entry point

- API entry point: `POST /api/convert` in `app.py`
- Background worker: `process_conversion()` in `app.py`
- Conversion call: `convert_file_to_markdown(source_file, context)` from `convert_to_md.py`
- PDF branch: `convert_pdf_to_markdown()` in `convert_to_md.py`

## Libraries currently used in pipeline

- `PyMuPDF` (`fitz`) for PDF inspection/extraction/rendering
- `python-docx` for DOCX extraction
- `pytesseract`/`Pillow` for OCR fallback (when available)
- Optional `markitdown` supplemental extraction (auto-detected)

## Baseline failure modes reproduced

Baseline artifact:
- `artifacts/before_after/file-sample_150kB_before.md`

Observed baseline issues:

1. Layout flattening and reading-order loss
   - Text runs/lines merged without robust geometric ordering.
2. Table misrepresentation
   - Large page regions were flattened into malformed markdown tables.
3. Image/chart fidelity gaps
   - Embedded image references were not consistently tied to deterministic asset naming + validation.
4. OCR fallback was not page-quality-aware
   - OCR behavior was not explicitly governed by text quality confidence.
5. Output validation was insufficient
   - No strict end-of-pipeline checks for unresolved refs, missing assets, heading sanity, and page coverage.

## Page-by-page PDF composition (file-sample_150kB.pdf)

Diagnostic artifact:
- `artifacts/diagnostics/file-sample_150kB_inspection.json`

Summary:
- Page 1: native text + embedded image content
- Page 2: mixed text/image/vector-heavy page; extraction quality can degrade
- Page 3: dense native text + visual content
- Page 4: effectively image-only for text extraction purposes

From diagnostics this file is mixed-content (native text + raster/vector), so strict text-only extraction is not sufficient.

## Exact failure points in old pipeline

- Heading inference used weak signals and often over-promoted lines.
- Table detection accepted low-confidence table structures.
- List glyph normalization missed some symbols (e.g., middle dot variants).
- Unresolved image identifier patterns were not actively blocked by strict validation.

## What content was lost or misrepresented before

- Reading-order coherence on mixed-layout pages
- Table semantics (or at minimum explicit image fallback)
- Reliable chart/diagram handling (vector-heavy content)
- Clear fallback signaling for low-confidence extraction pages

## Reading order vs PDF object order

- Raw PDF object order is not guaranteed to match visual reading order.
- Improved pipeline now sorts text blocks by geometry (`y`, then `x`) and tracks table regions to prevent mis-merges.

## Bullet glyph and encoding issues

- PDF bullet glyphs can appear as ``, `•`, `·`, `▪`, etc.
- Improved normalization maps these to markdown list items (`- item`).

## Embedded image extraction viability

- The sample PDF includes embedded images (`page.get_images(full=True)` returns data).
- Improved pipeline extracts supported embedded images and deduplicates by content hash.

## MarkItDown-specific note

- In this Python 3.9 environment, installed `markitdown` resolves to `0.0.1a1` without usable `MarkItDown` class API.
- Pipeline therefore uses deterministic native extraction path and treats MarkItDown as optional supplemental source only when available.
