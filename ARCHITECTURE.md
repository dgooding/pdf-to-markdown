# Architecture Summary

## Scope
This file records current repository architecture checkpoints for the document-to-MkDocs conversion platform.

## Core Product Surface
- Primary application entrypoint: `app.py`
- Primary user route: `/editor`
- Redirect routes: `/` and `/converter` -> `/editor`
- Startup script: `LAUNCH.bat`

## Conversion Architecture
- Converter pipeline implementation: `convert_to_md.py`
- Authoritative conversion service: `run_authoritative_conversion_service(...)` in `app.py`
- API endpoint uses authoritative service:
  - `POST /api/convert`
  - `GET /api/status/{job_id}`
  - `GET /api/download/{job_id}`
  - `GET /api/download-md/{job_id}`
  - `POST /api/publish/{job_id}`
- Direct and endpoint conversion paths are parity-validated.

## Output Artifacts
- Primary markdown output (`index.md` for endpoint package; filename-based markdown for direct runs)
- `assets/` directory for extracted visuals
- Manifest JSON (`*-manifest.json`)
- Quality report JSON (`*-quality-report.json`)
- Technical status and content-fidelity status remain separate dimensions.

## Packaging Rules
- Endpoint packaging requires markdown, assets, manifest, and quality report.
- Endpoint package excludes internal utilities and unrelated workspace files.
- UI download defaults to Markdown-only via `/api/download-md/{job_id}` while ZIP packaging remains available for full artifact retrieval.
- Strict endpoint/direct normalized parity checks are maintained.
- `wheelhouse/` contains the complete Python 3.9 dependency closure for offline Windows installation.
- Reproducible runtime/build/benchmark outputs are excluded from Git and removable with `cleanup_for_github.ps1`.

## ITSD Site Integration
- MkDocs project root: `mkdocs_preview/`
- Built site output served by FastAPI: `mkdocs_preview/site/` mounted at `/docs`
- Application startup reuses an existing static build; missing sites and successful publishes trigger a rebuild.
- Read the Docs theme provides a persistent left navigation and search field.
- Site navigation is intentionally limited to Home, Converter, and Documents.
- Navigation is one level deep with no section dropdowns or previous/next controls.
- Search indexes the home page and every published document.
- Converter publishing derives the document path from the uploaded filename and publishes directly into the document library.
- Existing published paths are protected from silent overwrite.
- Published converter output is staged under:
  - `mkdocs_preview/docs/published/<site-path>/index.md`
  - `mkdocs_preview/docs/published/<site-path>/assets/*`
- Hosted deployments use `DATA_ROOT/published` as the authoritative persistent document source and synchronize it into `mkdocs_preview/docs/published/` before each MkDocs build.
- `POST /api/delete-published` removes a normalized, contained document directory and rebuilds the index/site.
- Publish and delete operations use the same optional `PUBLISH_SECRET` authorization boundary.
- On Render, mutations fail closed with HTTP 503 when `PUBLISH_SECRET` is not configured; local development retains the existing optional-secret behavior.
- Publish/delete index and build transactions are serialized with a worker-thread lock compatible with Python 3.9 module reloads.
- Documents-page deletion behavior is loaded through `javascripts/delete-published.js`; generated Markdown contains controls only so MkDocs search indexes content rather than implementation code.
- `GET /api/site-capabilities` exposes only a boolean mutation-availability flag so the static Documents UI can fail gracefully without revealing configuration details.
- `POST /api/admin-access` validates an administrator passcode through the same `require_mutation_secret(...)` boundary without returning secret material.
- A high-contrast Admin button is fixed in the upper-right on every MkDocs page; Delete controls and a Publish shortcut remain hidden until server validation succeeds.
- The validated secret is retained only in JavaScript memory for the current page and is sent again to the independently protected delete endpoint; browser storage is not used.
- Authorization failures clear the in-memory value and relock deletion controls.
- Admin mode intentionally exposes all currently supported document-management actions (Publish and Delete), not arbitrary filesystem or server access.

## MkDocs Positioning
- MkDocs remains developer-only validation/staging support.
- MkDocs is not auto-launched by normal application startup.
- Normal startup does not run a redundant MkDocs build when `site/index.html` exists.
- Primary runtime remains the converter UI at `/editor`.

## Fixture and Benchmark Architecture (Milestone 1)
- Deterministic synthetic corpus generator: `generate_test_corpus.py`
- Default generated corpus path: `tests/fixtures/generated/`
- Includes DOCX-001..DOCX-010 and PDF-001..PDF-020 synthetic fixtures
- Generates:
  - source fixtures
  - expected sidecars (`*.expected.json`)
  - corpus manifest (`generated-corpus.json`)
  - representative previews for PDFs
- Generator validation helper ensures basic package integrity and expected sidecar presence.

## Constraints Preserved
- Original UI and workflow unchanged.
- No automatic MkDocs startup.
- No endpoint-specific conversion logic divergence from authoritative service.
- Developer diagnostics remain outside published markdown.

## Release Freeze (`prototype-v2-rc1`)
- Technical validation frozen with:
  - full tests passing
  - endpoint/direct parity passing
  - technical pass benchmark passing
- Runtime checks verified at freeze:
  - `/editor` functional
  - `/api/convert` functional
  - required endpoint ZIP artifacts present
  - markdown references resolve within package
  - internal utility files excluded from ZIP
  - no automatic MkDocs startup
  - port `8012` not listening during normal converter runtime validation
- Fidelity remains review-aware and separate from technical success metrics.

## Manual Fidelity Review Tooling (baseline phase)
- Review tooling entrypoint: `run_manual_fidelity_review.py`
- Review utility module: `fidelity_review_tools.py`
- Output root: `artifacts/fidelity-reviews/review-<timestamp>/`
- Tooling responsibilities:
  - create immutable review-run manifest
  - generate schema-driven scorecards
  - generate calibration/cleanup/defect summaries
  - produce pilot intake status when real docs are not approved
  - produce a human-review packet with blank human fields and explicit reviewer instructions/index
- Terminology boundary:
  - Outputs in this phase are automated review preparation artifacts, not completed human-review outcomes.
  - `human_review_status` remains `not_reviewed` until a real reviewer completes scorecards.
- Production boundaries preserved:
  - no changes to converter endpoint route surface
  - no automatic MkDocs startup
  - no review controls added to `/editor`
  - review artifacts remain outside user conversion packages
