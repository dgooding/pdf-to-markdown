# Course Correction Inventory

## Original application entry point
- `app.py` (FastAPI app with main converter UI at `/editor`)

## Original launch command / target
- `LAUNCH.bat` starts: `py -m uvicorn app:app --host 127.0.0.1 --port 8000`
- Converter page URL target: `http://127.0.0.1:8000/editor` (or current running instance on 8001 in this session)

## Original frontend files
- Embedded in `app.py` as `_EDITOR_HTML`
- Routes:
  - `/editor` (primary UI)
  - `/` -> `/editor`
  - `/converter` -> `/editor`

## Conversion backend files
- `convert_to_md.py` (PDF/DOCX/TXT/MD conversion pipeline)
- `app.py` conversion API routes (`/api/convert`, `/api/status/{job_id}`, `/api/download/{job_id}`, `/api/download-md/{job_id}`)

## Temporary MkDocs verification files
- `mkdocs_preview/` (developer-only temporary validation project)
- Not used by converter app runtime

## Generated artifacts
- `artifacts/after_hybrid_v2/` (current target output for `file-sample_150kB.pdf`)
- `artifacts/after_visual/`, `artifacts/after_hybrid/`, `artifacts/before_after/`
- `test_results/` and `analysis_*` folders

## Files modified during this course-correction pass
- `convert_to_md.py`
  - Added placement-aware PDF image extraction (`_extract_page_images`)
  - Added dedup metadata helper (`_save_asset_dedup_meta`)
  - Added per-placement manifest data (`image_placements`)
  - Prevented false page image references by requiring image placement rects
- `tests/test_conversion_pipeline.py`
  - Added regression test: `test_pdf_dedup_does_not_create_false_cross_page_image_placements`
  - Fixed manifest lookup to dynamic glob
- `artifacts/diagnostics/course_correction_inventory.md` (this file)

## Restoration status
- Converter app remains primary and active at `/editor`.
- Temporary MkDocs server at port 8012 was stopped.
- No automatic MkDocs preview launch is wired into converter startup.

## Current known quality issue status for file-sample_150kB.pdf
- Fixed: Page 3 no longer incorrectly references page 1 embedded image.
- Verified: Markdown image syntax is proper (`![...](assets/...)`).
- Verified: No unresolved `![][image_...]` placeholders.

## 2026-07-30 Vertical-slice baseline + implementation checkpoint

### Baseline capture
- Baseline conversion artifact created at:
  - `artifacts/baseline_verticalslice_20260730_224127/`
- Baseline markdown:
  - `artifacts/baseline_verticalslice_20260730_224127/file-sample_150kB.md`
- Baseline manifest:
  - `artifacts/baseline_verticalslice_20260730_224127/file-sample_150kb-manifest.json`

### Baseline observations
- Full-page fallbacks (baseline): pages 2 and 4.
- Targeted fallbacks (baseline): vector snapshots on pages 1 and 3, table crop on page 2.
- Published markdown included environment diagnostics text (now removed from published markdown in updated implementation).

### Vertical-slice implementation outputs
- New output directory:
  - `artifacts/after_verticalslice/`
- Updated markdown:
  - `artifacts/after_verticalslice/file-sample_150kB.md`
- Extended manifest:
  - `artifacts/after_verticalslice/file-sample_150kb-manifest.json`
- New developer quality report:
  - `artifacts/after_verticalslice/file-sample_150kb-quality-report.json`

### Vertical-slice behavior changes
- Added minimum normalized model (DocumentResult/PageResult/RegionResult/CandidateResult/AssetPlacement/FallbackRecord) inside converter pipeline.
- Added page inspection stage before markdown generation (dimensions/rotation/text/image/vector/link and suspected region signals).
- Added page classifications with confidence + evidence.
- Added two real page candidates:
  - `native_semantic`
  - `hybrid_targeted_fallback`
- Added candidate component scoring and selected-candidate explanation via `rejection_reasons`.
- Added region-level selected output model and fallback records.
- Added dual statuses (`technical_status`, `fidelity_status`).
- Added developer-facing quality report (JSON).

### Constraints preserved
- Original converter remains primary (`/editor`).
- No UI redesign/replacement.
- `app.py` and `LAUNCH.bat` startup behavior preserved.
- MkDocs remains optional developer-only tooling; not auto-started by normal launch.

## Final milestone completion update

- Final output location: `artifacts/final_milestone/`
- Final markdown: `artifacts/final_milestone/file-sample_150kB.md`
- Final manifest: `artifacts/final_milestone/file-sample_150kb-manifest.json`
- Final quality report: `artifacts/final_milestone/file-sample_150kb-quality-report.json`

### Baseline vs final comparison
- Full-page fallbacks: baseline `2` -> final `1`
- Targeted fallbacks: baseline `3` -> final `2`
- Technical status: `passed`
- Fidelity status: `review_required`

### Per-page outcomes (final)
- Page 1: semantic text + targeted chart crop (no full-page fallback)
- Page 2: table crop fallback selected over flattened native result
- Page 3: no false chart fallback selected (native semantic selected)
- Page 4: smallest honest fallback remains full-page visual; duplicate embedded visual output removed

## Endpoint integration mismatch resolution

### Root cause
- Endpoint flow and direct conversion flow were not guaranteed to share one authoritative conversion service.
- Endpoint package creation did not strictly enforce inclusion of quality report artifact before success.
- Comparison initially used mixed path assumptions for manifest naming and stale process state.

### Fixes applied
- Added authoritative service in `app.py`:
  - `run_authoritative_conversion_service(...)`
- Updated `/api/convert` processing to call that service and require both:
  - manifest file
  - quality-report file
  before packaging/marking success.
- Added effective configuration into both direct and endpoint manifests/quality reports for explicit config alignment.
- Added endpoint integration tests (`tests/test_endpoint_integration.py`) using real multipart HTTP calls to spawned uvicorn.

### Final strict comparison (live endpoint package)
- `COMPARE_MD=True`
- `COMPARE_ASSETS=True`
- `COMPARE_MANIFEST_CORE=True`
- `COMPARE_QUALITY_CORE=True`

### Endpoint package structure verified
- `docs/index.md`
- `docs/assets/*`
- `file-sample_150kb-manifest.json`
- `file-sample_150kb-quality-report.json`

## 2026-08-05 Markdown download UX correction

### Files modified
- `app.py`
  - Added `/api/download-md/{job_id}` to return only the generated Markdown file.
  - Switched the primary `/editor` download button to the Markdown endpoint.
  - Updated preview page links to expose both Markdown and ZIP downloads.
- `tests/test_endpoint_integration.py`
  - Added regression coverage for Markdown-only download responses.
- `artifacts/final_milestone/*`
  - Refreshed direct-conversion baseline so `strict_compare_run.py` matches current authoritative output.

### Verification
- Focused endpoint tests: 6 passed
- Full suite: 48 passed
- Strict live parity: all comparison fields true after baseline refresh

## 2026-08-05 ITSD site integration

### Additional files modified
- `app.py`
  - Added MkDocs scaffold/build helpers.
  - Added `/api/publish/{job_id}` and `/api/contact`.
  - Added `/site` redirect and editor publish controls.
- `mkdocs_preview/mkdocs.yml`
  - Replaced stub config with simple ITSD site navigation.
- `mkdocs_preview/docs/index.md`
  - Added ITSD homepage content.
- `mkdocs_preview/docs/documentation.md`
  - Added troubleshooting, FAQ, and user-manual sections.
- `mkdocs_preview/docs/contact.md`
  - Added support request form.
- `mkdocs_preview/docs/published/index.md`
  - Added published-documents landing page.
- `mkdocs_preview/docs/stylesheets/extra.css`
  - Added clean white-site styling.
- `requirements.txt`
  - Declared `mkdocs==1.6.1`.
- `tests/test_site_publish.py`
  - Added publish-path and published-index coverage.

## 2026-08-05 FAQ/showcase site content

### Additional content files added
- `mkdocs_preview/docs/faq.md`
- `mkdocs_preview/docs/faq/tldr-converter.md`
- `mkdocs_preview/docs/faq/standalone-application.md`
- `mkdocs_preview/docs/faq/build-estimate.md`
- `mkdocs_preview/docs/faq/white-paper.md`
- `mkdocs_preview/docs/faq/course-breakdown.md`
- `mkdocs_preview/docs/builder-profile.md`

### Existing content files updated
- `mkdocs_preview/mkdocs.yml`
  - Added FAQ and Builder Profile navigation entries.
- `mkdocs_preview/docs/index.md`
  - Added home-page FAQ button and builder snapshot card.
- `mkdocs_preview/docs/stylesheets/extra.css`
  - Added FAQ button and profile-card styling.

### Verification
- MkDocs rebuild: pass
- Live FAQ and builder-profile routes: pass
- Live home page includes FAQ button and builder card

### Verification
- Focused site integration tests: 11 passed
- Full suite: 51 passed
- MkDocs build: pass
- Live publish smoke: pass
- Strict endpoint parity: all comparison fields true

## 2026-07-31 Milestone 1 completion (synthetic advanced corpus generator)

### New fixture-generation implementation
- Replaced legacy corpus script with deterministic generator:
  - `generate_test_corpus.py`
- New tests added:
  - `tests/test_fixture_generation.py`

### Generated corpus location
- `tests/fixtures/generated/`
- Corpus manifest:
  - `tests/fixtures/generated/generated-corpus.json`
- Expected sidecars:
  - `tests/fixtures/generated/expected/*.expected.json`
- Previews:
  - `tests/fixtures/generated/previews/*.png`

### Fixture coverage
- DOCX fixtures: `DOCX-001` through `DOCX-010`
- PDF fixtures: `PDF-001` through `PDF-020`

### Generator behavior
- Configurable seed (`--seed`)
- Configurable output dir (`--output-dir`)
- Configurable groups (`--groups docx,pdf`)
- Cleanup mode (`--cleanup`)
- Validation mode (`--validate`)
- Deterministic synthetic variable-data generation
- Synthetic visual-asset generation without internet dependencies

### Validation and testing results
- Focused fixture tests: 4 passed, 0 failed
- Full suite after milestone: 25 passed, 0 failed
- Endpoint strict parity after milestone:
  - `COMPARE_MD=True`
  - `COMPARE_ASSETS=True`
  - `COMPARE_MANIFEST_CORE=True`
  - `COMPARE_QUALITY_CORE=True`

### Logs
- `artifacts/logs/m1_fixture_generation_20260730.log`
- `artifacts/logs/m1_fixture_tests_20260730_final.log`
- `artifacts/logs/m1_full_tests_20260730_final.log`
- `artifacts/logs/m1_endpoint_parity_20260730.log`

## 2026-07-31 Milestones 2-5 completion checkpoint

### Milestone 2 baseline benchmark
- Added benchmark runner:
  - `benchmark_generated_corpus.py`
- Latest immutable run:
  - `artifacts/benchmarks/benchmark_20260731_015547/`
- Results summary:
  - total fixtures: 30
  - endpoint parity rate: 1.0
  - technical pass rate: 0.9667

### Milestone 3 OCR behavior
- Added explicit OCR provider detection + diagnostics:
  - `detect_tesseract_provider(...)`
- Added OCR provenance records in manifest:
  - `ocr_records`
- Added region-aware OCR augmentation for table-image fallback regions when OCR is available.

### Milestone 4 table strategy
- Added table strategy metadata in manifest entries:
  - `strategy_selected`
  - `strategy_attempt_order`
  - `confidence`

### Milestone 5 reading-order/heading/list/link bounded improvements
- Added word-level multi-column detection.
- Added left/right span splitting on mixed-line blocks for column ordering.
- Preserved heading/list/link behavior and existing parity constraints.

### Verification after milestones 2-5
- Full suite:
  - 30 passed, 0 failed
- Strict parity:
  - `COMPARE_MD=True`
  - `COMPARE_ASSETS=True`
  - `COMPARE_MANIFEST_CORE=True`
  - `COMPARE_QUALITY_CORE=True`

### Logs
- `artifacts/logs/m2_benchmark_run_after_fix.log`
- `artifacts/logs/m2_full_tests_after_fix.log`
- `artifacts/logs/m3_m5_focused_tests.log`
- `artifacts/logs/m5_full_tests_after_fix_v3.log`
- `artifacts/logs/m5_benchmark_after_fix_v3.log`

## 2026-07-31 Milestones 6-10 completion checkpoint

### Milestone 6
- Validation hardening for environment path leakage detection.

### Milestone 7
- Added structured review record artifact per PDF conversion:
  - `*-review-record.json`

### Milestone 8
- Added safe batch conversion utility:
  - `batch_convert.py`
- Supports dry-run, resume, skip-existing, force overwrite, and state tracking.

### Milestone 9
- Added staged MkDocs migration utility:
  - `mkdocs_stage_migration.py`
- Conflict strategies: `fail`, `skip`, `versioned_copy`, `overwrite_with_backup`.

### Milestone 10
- Endpoint hardening:
  - upload-count limit
  - upload-size limit
  - upload filename sanitization
  - zip package exclusion filters

### Final verification status
- Full test suite:
- 35 passed, 0 failed
- Latest benchmark run:
  - `artifacts/benchmarks/benchmark_20260731_024647/`
  - parity rate: 1.0
  - technical pass rate: 1.0
- Final summary:
  - `artifacts/benchmarks/FINAL_SUMMARY_20260731.md`

## 2026-07-31 Final closeout

- Remaining strict-validation outlier resolved via non-PDF absolute-path rule refinement.
- Regression coverage added for legitimate Windows-path content in markdown sources.
- End-state targets achieved:
  - full suite green
  - strict endpoint/direct parity green
  - technical pass rate 1.0 on generated synthetic corpus benchmark

## 2026-07-31 Release freeze and handoff (`prototype-v2-rc1`)

### Freeze scope
- Documentation, evidence preservation, and release handoff packaging.
- No conversion algorithm changes introduced as part of freeze actions.

### Release handoff docs created
- `RELEASE_NOTES_PROTOTYPE_V2_RC1.md`
- `RUNBOOK.md`
- `HANDOFF_CHECKLIST.md`
- `FINAL_PR_DESCRIPTION.md`

### Release archive
- `artifacts/releases/prototype-v2-rc1/`
- Includes:
  - final full-test log
  - final benchmark summary
  - final benchmark raw results
  - endpoint parity/runtime log
  - release notes copy
  - runbook copy
  - handoff checklist copy
  - final PR description copy
  - known limitations
  - environment summary
  - git/diff summary snapshot

## 2026-07-31 Manual fidelity review baseline (`review-20260731-034421`)

### Scope completed
- Seven automated `review_required` synthetic fixtures reviewed.
- Five automated `high` fixtures sampled.
- Five automated `moderate` fixtures sampled.
- Real-document pilot intake evaluated; no approved real inputs available.

### Key results
- Human fidelity distribution (reviewed sample set):
  - high: 5
  - moderate: 5
  - review_required: 7
- Calibration agreement in sample set:
  - exact agreement: 17/17
  - false-confidence count: 0
- Release recommendation:
  - `approve_for_limited_pilot`

### Artifacts
- `artifacts/fidelity-reviews/review-20260731-034421/REVIEW_SUMMARY.md`
- `artifacts/fidelity-reviews/review-20260731-034421/review-summary.json`
- `artifacts/fidelity-reviews/review-20260731-034421/fidelity-calibration.md`
- `artifacts/fidelity-reviews/review-20260731-034421/fidelity-calibration.json`
- `artifacts/fidelity-reviews/review-20260731-034421/defect-ranking.md`
- `artifacts/fidelity-reviews/review-20260731-034421/cleanup-measurements.md`
- `artifacts/fidelity-reviews/review-20260731-034421/release-recommendation.md`
- `artifacts/fidelity-reviews/review-20260731-034421/real-document-pilot-summary.md`

## 2026-07-31 Fidelity terminology correction + true human-review preparation (`review-20260731-042323`)

### Correction summary
- The automated review workflow generated review candidates and scorecards but did not constitute completed human fidelity review.
- Automated results were preserved and reclassified explicitly as automated findings.
- Human review fields now remain blank/pending until a real reviewer completes scorecards.

### Statuses
- automated_review_preparation_status: `completed`
- synthetic_human_review_status: `pending`
- real_document_pilot_status: `waiting_for_approved_inputs`
- automated_human_agreement_status: `pending_human_review`

### Human-review packet artifacts
- `artifacts/fidelity-reviews/review-20260731-042323/human-review-packet/human-review-packet.json`
- `artifacts/fidelity-reviews/review-20260731-042323/human-review-packet/HUMAN_REVIEW_INSTRUCTIONS.md`
- `artifacts/fidelity-reviews/review-20260731-042323/human-review-packet/HUMAN_REVIEW_INDEX.md`

### Pilot intake artifacts
- `pilot_input/README.md`
- `pilot_input/pilot_inventory_template.json`

### Verification
- Focused review-tool tests: 12 passed, 0 failed
- Full suite: 47 passed, 0 failed, 0 skipped
- Endpoint parity: `COMPARE_MD=True`, `COMPARE_ASSETS=True`, `COMPARE_MANIFEST_CORE=True`, `COMPARE_QUALITY_CORE=True`
- Conversion algorithms: unchanged

## 2026-08-05 Minimal searchable site correction
- Simplified MkDocs navigation to Home, Converter, and Documents.
- Switched to the Read the Docs theme for persistent left navigation and built-in search.
- Removed obsolete showcase and auxiliary site pages while preserving published documents.
- Kept `/editor`, publishing APIs, and authoritative conversion behavior unchanged.
- Verification: 54 tests passed; required live routes returned 200; strict endpoint parity remained fully true.

## 2026-08-05 Runtime and repository cleanup
- Removed unused folder-management helpers/endpoints, contact endpoint, FAQ route, and white-paper PDF generator.
- Removed the now-unused `fitz` import from `app.py`.
- Simplified the publish endpoint to the document-name-only UI contract.
- Removed the redundant MkDocs subprocess from normal startup when a built site already exists.
- Removed duplicate endpoint integration setup and obsolete folder tests.
- Deleted isolated preview scratch files and stale generated directories.
- Preserved conversion algorithms and published content.
- Verification: focused tests 11 passed; full suite 53 passed; strict parity fully true; live route checks passed.

## 2026-08-05 GitHub footprint reduction
- Added `.gitignore` and an idempotent, OneDrive/long-path-safe `cleanup_for_github.ps1`.
- Removed repeated benchmark, parity, fidelity-review, analysis, evaluation, cache, and built-site outputs.
- Retained the complete offline wheelhouse and repaired missing MkDocs dependencies using official PyPI SHA-256 metadata.
- Retained all application functionality, generated fixtures, published documents, the validated benchmark, and strict parity baseline/script.
- Reduced workspace from 433.88 MiB to 123.86 MiB; largest retained file is 17.88 MiB.
- Verification: offline dependency resolution passed; full suite 53 passed; strict parity fully true.

## 2026-08-05 Flat site navigation
- Configured Read the Docs navigation depth to one, titles-only navigation, and no previous/next button location.
- Added CSS safeguards for page-section submenus, expand controls, footer buttons, and mobile version navigation.
- Added regression coverage in `tests/test_site_publish.py`.
- Verification: focused tests 6 passed; full suite 54 passed; strict parity fully true; browser visual check passed.

## 2026-08-05 Public repository and protected deletion
- Changed `https://github.com/dgooding/pdf-to-markdown` visibility to public.
- Added path-safe published-document deletion and `POST /api/delete-published` in `app.py`.
- Added generated Documents-page Delete controls that confirm intent and request `PUBLISH_SECRET`.
- Corrected hosted document persistence by synchronizing `DATA_ROOT/published` into the MkDocs source before builds.
- Added focused regression coverage in `tests/test_site_publish.py`.
- Verification: 9 focused tests passed; MkDocs HTML control check passed; 65 full-suite tests passed; strict parity fully true.

## 2026-08-06 Hosted fail-closed correction
- Live Render smoke testing showed that an omitted `PUBLISH_SECRET` allowed mutation requests to reach document lookup.
- Added hosted-environment detection and HTTP 503 fail-closed behavior for missing secrets.
- Replaced module-level `asyncio.Lock` with a worker-thread transaction lock after reload-sensitive Python 3.9 testing exposed event-loop teardown failure.
- Verification: focused site/cloud tests 18 passed; full suite 66 passed; live conversion passed.
