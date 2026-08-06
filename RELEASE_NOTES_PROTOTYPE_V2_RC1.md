# RELEASE NOTES — prototype-v2-rc1

## Release purpose
Adaptive document-to-MkDocs conversion prototype with technical validation and review-aware fidelity reporting.

This release freeze packages the verified technical state of the document migration prototype as `prototype-v2-rc1`.

## Prototype-v1 history (context)
- Prototype-v1 established endpoint/direct conversion parity foundations.
- Root divergence issue was resolved by routing both paths through the authoritative conversion service.
- Packaging was hardened to require manifest + quality report artifacts.

## Major capabilities
- Multi-format conversion support: PDF, DOCX, TXT, and Markdown workflows.
- Authoritative conversion service (`run_authoritative_conversion_service(...)`) used by API and direct flows.
- JSON outputs for technical validation and review workflow:
  - manifest (`*-manifest.json`)
  - quality report (`*-quality-report.json`)
  - review record (`*-review-record.json` for PDF conversions)

## Authoritative conversion service
- API conversion and direct conversion are aligned to one core execution path.
- Endpoint package generation is gated on required artifacts.

## Endpoint/direct parity
- Verified parity is maintained at release freeze:
  - `COMPARE_MD=True`
  - `COMPARE_ASSETS=True`
  - `COMPARE_MANIFEST_CORE=True`
  - `COMPARE_QUALITY_CORE=True`

## Synthetic corpus
- Corpus size: 30 synthetic fixtures.
- Benchmark evidence run: `artifacts/benchmarks/benchmark_20260731_024647/`.

## Fixture coverage
- DOCX coverage: `DOCX-001..DOCX-010`
- PDF coverage: `PDF-001..PDF-020`

## Batch conversion
- Safe batch utility: `batch_convert.py`
- Supports recursive runs, dry-run, resume state, skip-existing, and force modes.

## Staged MkDocs migration
- Utility: `mkdocs_stage_migration.py`
- Conflict strategies:
  - `fail`
  - `skip`
  - `versioned_copy`
  - `overwrite_with_backup`

## OCR behavior
- OCR provider availability is detected and recorded.
- OCR provenance is recorded for reviewable traceability.
- OCR remains fallback/conditional; no claim of universal OCR correctness.

## Table behavior
- Semantic table output is attempted first when confidence allows.
- Visual table fallback is used for complex/low-confidence table extraction.
- Strategy metadata (`strategy_selected`, `strategy_attempt_order`, `confidence`) is preserved in artifacts.

## Image-placement behavior
- Asset identity and placement records are preserved separately.
- Cross-page placement mismatch regressions are covered by tests.

## Validation behavior
- Strict technical validation remains active.
- False positive for legitimate Windows path content in non-PDF validation was fixed.
- Regression test added:
  - `test_non_pdf_manifest_allows_legitimate_windows_path_content`

## Security guards
- Upload size limit and file-count limit in API flow.
- Upload filename sanitization.
- ZIP packaging exclusion guards for internal utilities/checkpoint files.

## Test evidence
- Final full test suite:
  - `35 passed, 0 failed, 0 skipped`
- Log:
  - `artifacts/logs/release_freeze_full_tests.log`

## Benchmark evidence
- Final benchmark run:
  - `artifacts/benchmarks/benchmark_20260731_024647/`
- Metrics:
  - `TOTAL_FIXTURES = 30`
  - `PARITY_RATE = 1.0`
  - `TECH_PASS_RATE = 1.0`

## Known limitations
- Technical success does not imply perfect document fidelity.
- Complex visual semantics (charts, diagrams, layout-heavy scans) may still require human review.
- Content-fidelity decisions remain review-aware and context-sensitive.

## Rollback instructions
1. Preserve current release evidence in `artifacts/releases/prototype-v2-rc1/`.
2. Restore previous stable checkpoint artifacts and documents from your archived release directory.
3. Re-run full tests and benchmark to confirm rollback integrity.
4. Re-verify `/editor`, `/api/convert`, ZIP package structure, and parity metrics before re-promoting.

## Release status
- RC identifier: `prototype-v2-rc1`
- Technical release freeze: complete
