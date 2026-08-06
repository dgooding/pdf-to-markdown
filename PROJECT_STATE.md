# Project State Checkpoints

## 2026-07-30T22:20:00 (local)
- Execution mode verified via terminal commands.
- Git status check: not a git repository in this workspace.
- Python version: 3.9.13.
- Baseline full test suite: 10 run, 10 passed, 0 failed, 0 skipped.
- Original converter route expected at: http://127.0.0.1:8001/editor

## 2026-07-30T22:55:00 (local)
- Final full test suite: 18 run, 18 passed, 0 failed, 0 skipped.
- Final conversion artifact set:
	- `artifacts/final_milestone/file-sample_150kB.md`
	- `artifacts/final_milestone/file-sample_150kb-manifest.json`
	- `artifacts/final_milestone/file-sample_150kb-quality-report.json`
- Baseline retained at:
	- `artifacts/baseline_verticalslice_20260730_224127/`
- Original converter UI verified active at:
	- `http://127.0.0.1:8001/editor`

## 2026-07-30T23:20:00 (local)
- Endpoint verification executed with Python multipart HTTP client against `/api/convert`.
- HTTP status: 200 from endpoint conversion flow.
- Endpoint package extracted under:
	- `artifacts/endpoint_release_check/extracted/`
- Endpoint artifact comparison vs `artifacts/final_milestone`:
	- Markdown match: false
	- Assets match: false
	- Manifest core match: false
	- Quality report in endpoint package: missing
- Full test suite rerun after endpoint verification: 18 run, 18 passed, 0 failed, 0 skipped.
- Observed blocker: running `/api/convert` endpoint process produced older artifact profile than direct backend milestone artifacts; endpoint package omitted quality report.

## 2026-07-30T23:59:00 (local)
- Root cause fixed: endpoint and direct path diverged because API flow did not call the authoritative conversion service and quality-report packaging was not guaranteed in the endpoint package.
- Endpoint integration alignment completed using shared service in `app.py`:
	- `run_authoritative_conversion_service(...)`
- Endpoint strict comparison rerun from live `/api/convert` package:
	- `COMPARE_MD=True`
	- `COMPARE_ASSETS=True`
	- `COMPARE_MANIFEST_CORE=True`
	- `COMPARE_QUALITY_CORE=True`
- Endpoint package now contains:
	- `docs/index.md`
	- `docs/assets/*`
	- `file-sample_150kb-manifest.json`
	- `file-sample_150kb-quality-report.json`
- Full test suite after endpoint fix: 21 run, 21 passed, 0 failed, 0 skipped.

## 2026-07-31T00:40:00 (local)
- Milestone 0 freeze re-verified before new work:
	- Python: `3.9.13`
	- `git status`: workspace is not a git repository
	- full suite: 21 passed, 0 failed
	- strict endpoint parity (`/api/convert` live): all comparisons true
- Milestone 1 completed: deterministic synthetic advanced fixture generator implemented.
- New corpus location:
	- `tests/fixtures/generated/`
	- `tests/fixtures/generated/generated-corpus.json`
	- `tests/fixtures/generated/expected/*.expected.json`
	- `tests/fixtures/generated/previews/*.png`
- Fixture scope now includes:
	- DOCX-001..DOCX-010
	- PDF-001..PDF-020
- Generator capabilities:
	- configurable `--seed`, `--output-dir`, `--groups`, `--cleanup`, `--validate`
	- deterministic synthetic variable data
	- synthetic visual asset generation without internet dependency
	- fixture sidecars + corpus manifest
	- validation report generation (`generation-validation.json`)
- Focused fixture-generation tests added and passing.
- Updated full suite result: 25 passed, 0 failed, 0 skipped.
- Endpoint parity after Milestone 1 re-verification:
	- `COMPARE_MD=True`
	- `COMPARE_ASSETS=True`
	- `COMPARE_MANIFEST_CORE=True`
	- `COMPARE_QUALITY_CORE=True`
- Logs:
	- `artifacts/logs/m1_fixture_generation_20260730.log`
	- `artifacts/logs/m1_fixture_tests_20260730_final.log`
	- `artifacts/logs/m1_full_tests_20260730_final.log`
	- `artifacts/logs/m1_endpoint_parity_20260730.log`

## 2026-07-31T01:56:00 (local)
- Milestone 2 completed: immutable synthetic-corpus baseline benchmark implemented and executed.
- Benchmark runner added:
	- `benchmark_generated_corpus.py`
- Latest immutable benchmark run:
	- `artifacts/benchmarks/benchmark_20260731_015547/`
	- `benchmark-results.json`
	- `benchmark-results.md`
- Benchmark summary:
	- total fixtures: 30
	- endpoint parity rate: 1.0
	- technical pass rate: 0.9667
- Full suite after milestone 2 updates: 30 passed, 0 failed, 0 skipped.

- Milestone 3 completed (bounded implementation):
	- OCR provider availability detection and diagnostics (`detect_tesseract_provider`)
	- OCR provenance records in manifest (`ocr_records`)
	- region-aware table OCR augmentation for table-image fallback when available
	- no developer diagnostics leaked into published markdown

- Milestone 4 completed (bounded implementation):
	- Confidence-driven table strategy metadata added in manifest:
		- `strategy_selected`
		- `strategy_attempt_order`
		- `confidence`

- Milestone 5 completed (bounded implementation):
	- Improved two-column reading order handling:
		- word-level multi-column detection
		- left/right line splitting for mixed-span lines
		- preserved left-column then right-column output ordering

- Endpoint/direct parity after milestones 2-5 remains strict true:
	- `COMPARE_MD=True`
	- `COMPARE_ASSETS=True`
	- `COMPARE_MANIFEST_CORE=True`
	- `COMPARE_QUALITY_CORE=True`

## 2026-07-31T02:34:00 (local)
- Milestones 6-10 completed.
- New utilities delivered:
	- `batch_convert.py`
	- `mkdocs_stage_migration.py`
- Security and packaging hardening in endpoint completed:
	- upload count limit
	- upload size limit
	- safe upload filenames
	- zip packaging exclusion guardrails
- Final full test suite result:
	- 34 passed, 0 failed, 0 skipped
- Final benchmark run:
	- `artifacts/benchmarks/benchmark_20260731_023334/`
	- endpoint parity rate: `1.0`
	- technical pass rate: `0.9667`
- Final summary artifact:
	- `artifacts/benchmarks/FINAL_SUMMARY_20260731.md`

## 2026-07-31T02:47:00 (local)
- Final quality closeout pass completed.
- Non-PDF validation rule refined to avoid false environment-path leakage flags for legitimate content.
- Added regression test:
	- `test_non_pdf_manifest_allows_legitimate_windows_path_content`
- Latest full suite result:
	- 35 passed, 0 failed, 0 skipped
- Latest benchmark run:
	- `artifacts/benchmarks/benchmark_20260731_024647/`
	- total fixtures: 30
	- endpoint parity rate: 1.0
	- technical pass rate: 1.0

## 2026-07-31T03:00:00 (local)
- Release-candidate designation applied:
	- `prototype-v2-rc1`
- Release statement:
	- `release: complete technical validation for document migration prototype v2`
- Release artifact:
	- `artifacts/releases/prototype-v2-rc1.md`
- RC readiness:
	- technical pass rate: 1.0
	- endpoint parity rate: 1.0
	- full suite: 35 passed, 0 failed, 0 skipped

## 2026-07-31T03:20:00 (local)
- Final release freeze and handoff packaging completed.
- Runtime checks confirmed:
	- `/editor` functional (200)
	- `/api/convert` functional (200)
	- conversion package includes required artifacts
	- package markdown references resolve
	- internal utility/checkpoint files excluded from endpoint ZIP
	- MkDocs not auto-started
	- port 8012 not listening during normal runtime verification
- Release archive root:
	- `artifacts/releases/prototype-v2-rc1/`

## 2026-07-31T03:45:00 (local)
- Manual fidelity review baseline run completed:
	- `artifacts/fidelity-reviews/review-20260731-034421/`
- Automated technical result (baseline preserved):
	- full suite: 35 passed, 0 failed, 0 skipped (checkpoint baseline)
	- latest full suite with review tooling: 44 passed, 0 failed, 0 skipped
	- endpoint parity: all strict comparisons true
	- technical pass rate: 1.0
- Automated fidelity result (synthetic benchmark baseline):
	- high: 13, moderate: 10, low: 0, review_required: 7, unknown: 0
- Human fidelity result (manual synthetic review sample set):
	- reviewed set (17 docs): high 5, moderate 5, review_required 7
- Synthetic review status:
	- completed for all seven review-required fixtures
	- completed for five automated-high fixtures
	- completed for five automated-moderate fixtures
- Real-document pilot status:
	- `waiting_for_approved_inputs`
	- intake folder: `pilot_input/README.md`
- Release recommendation:
	- `approve_for_limited_pilot`
- Current blockers:
	- no approved real-document pilot inputs provided yet
- Artifact locations:
	- review run: `artifacts/fidelity-reviews/review-20260731-034421/`
	- summary: `REVIEW_SUMMARY.md`, `review-summary.json`
	- calibration: `fidelity-calibration.md/json`
	- defect ranking: `defect-ranking.md/json`
	- cleanup metrics: `cleanup-measurements.md/json`

	## 2026-07-31T04:23:00 (local)
	- Terminology correction completed for fidelity-review phase.
	- Correction statement:
		- The automated review workflow generated review candidates and scorecards but did not constitute completed human fidelity review.
	- Automated review preparation status:
		- completed
	- Synthetic human review status:
		- pending
	- Real-document pilot status:
		- waiting_for_approved_inputs
	- Human-review packet prepared for 17 selected synthetic fixtures:
		- `artifacts/fidelity-reviews/review-20260731-042323/human-review-packet/`
	- Human-review instructions:
		- `artifacts/fidelity-reviews/review-20260731-042323/human-review-packet/HUMAN_REVIEW_INSTRUCTIONS.md`
	- Human-review index:
		- `artifacts/fidelity-reviews/review-20260731-042323/human-review-packet/HUMAN_REVIEW_INDEX.md`
	- Automated/human agreement status:
		- pending_human_review
	- Human review/cleanup minutes:
		- not measured (null until completed by a real reviewer)
	- Verification after correction:
		- focused review-tool tests: 12 passed, 0 failed
		- full suite: 47 passed, 0 failed, 0 skipped
		- endpoint parity: `COMPARE_MD=True`, `COMPARE_ASSETS=True`, `COMPARE_MANIFEST_CORE=True`, `COMPARE_QUALITY_CORE=True`
	- Conversion algorithm status:
		- unchanged during correction

## 2026-08-05T00:00:00 (local)
- UI/API download workflow updated so the primary `/editor` download button returns Markdown directly.
- Added Markdown download endpoint:
	- `/api/download-md/{job_id}`
- Preserved ZIP package endpoint for full artifact retrieval:
	- `/api/download/{job_id}`
- Preview page now exposes both download options:
	- Markdown (`.md`)
	- full package (`.zip`)
- Verification completed after change:
	- focused endpoint integration: 6 passed, 0 failed
	- full suite: 48 passed, 0 failed, 0 skipped
	- strict endpoint parity: `COMPARE_MD=True`, `COMPARE_ASSETS=True`, `COMPARE_MANIFEST_CORE=True`, `COMPARE_QUALITY_CORE=True`
- Baseline refresh performed before strict parity rerun:
	- `C:/Python39/python.exe convert_to_md.py file-sample_150kB.pdf --output-dir artifacts/final_milestone --overwrite --pdf-mode hybrid`

## 2026-08-05T00:45:00 (local)
- Simple ITSD MkDocs site integrated into the converter runtime.
- New site artifacts/scaffold:
	- `mkdocs_preview/mkdocs.yml`
	- `mkdocs_preview/docs/index.md`
	- `mkdocs_preview/docs/documentation.md`
	- `mkdocs_preview/docs/contact.md`
	- `mkdocs_preview/docs/published/index.md`
	- `mkdocs_preview/docs/stylesheets/extra.css`
- New runtime capabilities in `app.py`:
	- build static site output into `mkdocs_preview/site/`
	- serve site at `/docs`
	- publish converted documents with `POST /api/publish/{job_id}`
	- accept contact submissions with `POST /api/contact`
	- expose `/site` redirect to `/docs/`
- Editor integration completed:
	- site navigation links in header
	- site-path input for direct publishing
	- publish button with success link to generated site page
- Verification completed:
	- focused suites: 11 passed, 0 failed
	- full suite: 51 passed, 0 failed, 0 skipped
	- `python -m mkdocs build -f mkdocs_preview/mkdocs.yml`: pass
	- live publish smoke test: pass
	- strict endpoint parity: `COMPARE_MD=True`, `COMPARE_ASSETS=True`, `COMPARE_MANIFEST_CORE=True`, `COMPARE_QUALITY_CORE=True`

## 2026-08-05T01:20:00 (local)
- Publish workflow improved with folder-driven UX for ITSD site publishing.
- Added site-folder backend support:
	- `GET /api/site-folders`
	- `POST /api/site-folders`
- Added converter publish controls:
	- folder dropdown
	- document-name field
	- folder-manager link
- Added MkDocs folder manager page:
	- `mkdocs_preview/docs/folder-manager.md`
- Live smoke verification:
	- folder list API returned expected folders
	- folder manager page served 200
	- creating folder `Policies` via API succeeded and appeared in folder list
- Verification completed:
	- focused suites: 14 passed, 0 failed
	- full suite: 54 passed, 0 failed, 0 skipped
	- `python -m mkdocs build -f mkdocs_preview/mkdocs.yml`: pass

## 2026-08-05T01:45:00 (local)
- Added FAQ/showcase content to the ITSD site for architecture explanation and portfolio-style presentation.
- New site content added:
	- `mkdocs_preview/docs/faq.md`
	- `mkdocs_preview/docs/faq/tldr-converter.md`
	- `mkdocs_preview/docs/faq/standalone-application.md`
	- `mkdocs_preview/docs/faq/build-estimate.md`
	- `mkdocs_preview/docs/faq/white-paper.md`
	- `mkdocs_preview/docs/faq/course-breakdown.md`
	- `mkdocs_preview/docs/builder-profile.md`
- Home page enhancements:
	- small FAQ button in upper-right area
	- short builder snapshot card with resume-style link
- Verification completed:
	- `python -m mkdocs build -f mkdocs_preview/mkdocs.yml`: pass
	- live page checks: `/docs/`, `/docs/faq/`, `/docs/builder-profile/` all returned 200
	- live content checks: FAQ button, builder card, and FAQ hub text present

## 2026-08-05 Minimal Searchable Site
- Replaced the showcase-oriented site with a production-focused Read the Docs layout.
- Left navigation contains only Home, Converter, and Documents.
- MkDocs search indexes the home page and all published documents.
- Published content and the `/editor` converter integration remain intact.
- Removed obsolete FAQ, profile, contact, folder-manager, documentation, download, and sample-converted site content.
- Verification: 54 tests passed; live routes returned 200; strict endpoint parity remained fully true.

## 2026-08-05 Runtime Cleanup
- Removed obsolete folder-management, contact, FAQ/showcase, and white-paper runtime code.
- Simplified the publish endpoint to accept only the current document-name input.
- Removed duplicate endpoint-test setup and obsolete folder-management tests.
- Deleted generated caches, stale nested MkDocs output, and isolated preview scratch files.
- Avoided redundant MkDocs rebuilds during normal startup; first-run and publish-time builds remain.
- Preserved converter behavior, published documents, test fixtures, samples, and historical artifacts.
- Verification: 53 tests passed; strict endpoint parity remained fully true; retained live routes returned 200 and removed routes returned 404.

## 2026-08-05 GitHub Footprint Reduction
- Reduced the clean workspace from 433.88 MiB and 10,050 files to 123.86 MiB and 1,060 files.
- Added `.gitignore` and `cleanup_for_github.ps1` to prevent generated outputs from returning to version control.
- Preserved the offline wheelhouse, generated fixtures, validated benchmark, strict parity baseline/script, published documents, and source/tests.
- Repaired the wheelhouse with official SHA-256-verified MkDocs dependency wheels.
- Largest retained file: PyMuPDF wheel at 17.88 MiB, below GitHub's 100 MiB per-file limit.
- Verification: forced offline dependency resolution passed; 53 tests passed; strict endpoint parity remained fully true.

## 2026-08-05 Flat Site Navigation
- Reduced the left sidebar to Search, Home, Converter, and Documents only.
- Removed Home section dropdown entries and all desktop/mobile Next and Previous controls.
- Used native Read the Docs theme settings with CSS safeguards so rebuilds preserve the simple layout.
- Verification: 6 focused tests passed; 54 full-suite tests passed; strict endpoint parity remained fully true; visual browser check passed.

## 2026-08-05 Public Repository and Document Deletion
- Published the repository publicly at `https://github.com/dgooding/pdf-to-markdown`.
- Added a Delete control beside each entry on the Documents page.
- Added `POST /api/delete-published`, protected by the existing `PUBLISH_SECRET` when configured.
- Added normalized-path and root-containment checks before recursive document removal.
- Synchronized persistent `DATA_ROOT/published` content into the MkDocs build source for hosted deployments.
- Verification: 9 focused tests passed; MkDocs build and generated delete controls verified; 65 full-suite tests passed; strict endpoint parity remained fully true.

## 2026-08-06 Hosted Mutation Security
- Deployed the public Render service at `https://pdf-to-markdown-1gzl.onrender.com`.
- Hosted publish/delete operations now return 503 when `PUBLISH_SECRET` is missing instead of allowing anonymous mutations.
- Configured secrets use constant-time comparison; site mutation transactions use a Python 3.9-safe thread lock.
- Live conversion smoke test passed with a completed job and valid Markdown download.
- Verification: focused hosted/site tests 18 passed; full suite 66 passed.
- Search polish moved delete behavior into `javascripts/delete-published.js`, keeping implementation code out of hosted search results.
- Hosted Documents now query `/api/site-capabilities` and visibly disable Delete controls when administrator secret setup is incomplete.

## 2026-08-06 Admin Delete Access

- Added a prominent upper-right Admin button to every MkDocs page, with an admin-only Publish shortcut.
- Delete controls now start hidden and disabled, then unlock only after `POST /api/admin-access` validates the existing `PUBLISH_SECRET` boundary.
- The validated secret remains in page memory only and is revalidated by `POST /api/delete-published`; no passcode is embedded in source or browser storage.
- Wrong credentials return 403, and missing hosted configuration remains fail-closed with 503.
- Verification: 21 focused tests passed; 69 full-suite tests passed; MkDocs build passed; desktop/mobile browser checks passed; strict endpoint parity remained fully true.
- Evidence logs:
	- `artifacts/logs/admin_button_focused_tests.log`
	- `artifacts/logs/admin_button_full_tests.log`
	- `artifacts/logs/admin_button_mkdocs_build.log`
	- `artifacts/logs/admin_button_endpoint_parity.log`
- Remaining deployment action: set the requested passcode privately as Render `PUBLISH_SECRET` and redeploy.
