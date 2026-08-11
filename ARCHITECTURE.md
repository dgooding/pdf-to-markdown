# Architecture Summary

## Scope
This file records current repository architecture checkpoints for the document-to-MkDocs conversion platform.

## Core Product Surface
- Production site: GitHub Pages at `https://dgooding.github.io/pdf-to-markdown/`
- Production conversion/publishing: GitHub Actions workflows under `.github/workflows/`
- Local/offline application entrypoint: `app.py`
- Local user route: `/editor`
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
- Production MkDocs output is deployed by GitHub Pages.
- Local builds remain available at `mkdocs_preview/site/` and may be served by FastAPI at `/docs`.
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
- `github_document_ops.py` is the authoritative repository-safe publish/delete/index command layer shared by Actions and local FastAPI imports.
- `.github/workflows/convert-publish.yml` converts files committed under `incoming/`, commits generated Markdown/assets, and deploys Pages.
- `.github/workflows/delete-published.yml` verifies GitHub collaborator permission before deleting issue-requested paths; manual dispatch is restricted by repository Actions access.
- `.github/workflows/pages.yml` provides ordinary and recovery Pages deployment.
- A shared `document-publishing` concurrency group serializes mutation/deployment workflows.
- The upper-right Admin button opens the GitHub-native converter/admin guide. Delete controls create prefilled GitHub requests; Pages contains no passcode, token, or runtime API credential.
- Git commit history is the persistent source and audit trail for published content.

## MkDocs Positioning
- MkDocs is the production static-site generator for GitHub Pages.
- MkDocs is not auto-launched by normal application startup.
- The local FastAPI editor remains available for offline/developer conversion.

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

## Global Admin Control Removal (2026-08-11)
- The MkDocs site no longer injects or styles a global Admin button on any page.
- GitHub-native upload, workflow, and permission-checked deletion links remain available on the Converter and Documents surfaces.
- The FastAPI fallback scaffold matches the checked-in static assets so rebuilding cannot restore the removed control.
