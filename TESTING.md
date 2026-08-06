# Testing Summary

## Latest Full Suite
- Command: `C:/Python39/python.exe -m unittest discover -s tests -v`
- Result: 25 tests passed, 0 failed, 0 skipped.

## Build/Compile Checks
- Command: `C:/Python39/python.exe -m py_compile convert_to_md.py tests/test_conversion_pipeline.py app.py`
- Result: pass.

## Conversion Verification
- Command: `C:/Python39/python.exe convert_to_md.py file-sample_150kB.pdf --output-dir artifacts/final_milestone --overwrite --pdf-mode hybrid`
- Result: pass.

## Endpoint Integration Verification
- Command: `C:/Python39/python.exe -m unittest tests.test_endpoint_integration -v`
- Result: 3 endpoint integration tests passed.

## Strict Endpoint Comparison (live `/api/convert`)
- Script: `artifacts/endpoint_release_check_live/strict_compare_run.py`
- Result:
	- `COMPARE_MD=True`
	- `COMPARE_ASSETS=True`
	- `COMPARE_MANIFEST_CORE=True`
	- `COMPARE_QUALITY_CORE=True`

## Milestone 1 Fixture Generator Validation
- Generator command:
	- `C:/Python39/python.exe generate_test_corpus.py --output-dir tests/fixtures/generated --seed 20260730 --groups docx,pdf --cleanup --validate`
- Focused fixture tests:
	- `C:/Python39/python.exe -m unittest tests.test_fixture_generation -v`
- Focused result:
	- 4 passed, 0 failed, 0 skipped.
- Full-suite result after fixture work:
	- 25 passed, 0 failed, 0 skipped.
- Endpoint parity rerun after fixture work:
	- `COMPARE_MD=True`
	- `COMPARE_ASSETS=True`
	- `COMPARE_MANIFEST_CORE=True`
	- `COMPARE_QUALITY_CORE=True`

## Saved Logs
- `artifacts/logs/m1_fixture_generation_20260730.log`
- `artifacts/logs/m1_fixture_tests_20260730_final.log`
- `artifacts/logs/m1_full_tests_20260730_final.log`
- `artifacts/logs/m1_endpoint_parity_20260730.log`

## Milestone 2 Benchmark Baseline
- Runner:
	- `C:/Python39/python.exe benchmark_generated_corpus.py --corpus-manifest tests/fixtures/generated/generated-corpus.json`
- Latest run directory:
	- `artifacts/benchmarks/benchmark_20260731_015547/`
- Latest summary:
	- total fixtures: 30
	- endpoint parity rate: 1.0
	- technical pass rate: 0.9667

## Milestones 3-5 Verification
- Focused:
	- `C:/Python39/python.exe -m unittest tests.test_conversion_pipeline tests.test_endpoint_integration tests.test_benchmark_runner -v`
- Full suite:
	- `C:/Python39/python.exe -m unittest discover -s tests -v`
- Result:
	- 30 passed, 0 failed, 0 skipped
- Endpoint/direct strict parity rerun in benchmark:
	- `COMPARE_MD=True`
	- `COMPARE_ASSETS=True`
	- `COMPARE_MANIFEST_CORE=True`
	- `COMPARE_QUALITY_CORE=True`

## Milestone 2-5 Logs
- `artifacts/logs/m2_benchmark_runner_tests.log`
- `artifacts/logs/m2_benchmark_run_after_fix.log`
- `artifacts/logs/m2_full_tests_after_fix.log`
- `artifacts/logs/m3_m5_focused_tests.log`
- `artifacts/logs/m5_full_tests_after_fix_v3.log`
- `artifacts/logs/m5_benchmark_after_fix_v3.log`

## Milestones 6-10 Final Validation
- Focused suites:
	- endpoint + staging migration + batch conversion tests passed
- Full suite:
	- 34 passed, 0 failed, 0 skipped
- Latest benchmark:
	- `artifacts/benchmarks/benchmark_20260731_024647/`
	- parity rate: 1.0
	- technical pass rate: 1.0

## Final Logs
- `artifacts/logs/m6_m8_focused.log`
- `artifacts/logs/m6_m8_full.log`
- `artifacts/logs/m6_m8_benchmark.log`
- `artifacts/logs/m9_m10_focused_rerun3.log`
- `artifacts/logs/m9_m10_full_rerun3.log`
- `artifacts/logs/m9_m10_benchmark_rerun3.log`

## Final Closeout Validation
- Focused:
	- `C:/Python39/python.exe -m unittest tests.test_endpoint_integration tests.test_benchmark_runner -v`
	- 7 passed, 0 failed
- Full suite:
	- `C:/Python39/python.exe -m unittest discover -s tests -v`
	- 35 passed, 0 failed, 0 skipped
- Benchmark:
	- `C:/Python39/python.exe benchmark_generated_corpus.py --corpus-manifest tests/fixtures/generated/generated-corpus.json`
	- run: `artifacts/benchmarks/benchmark_20260731_024647/`
	- parity rate: 1.0
	- technical pass rate: 1.0
- Closeout logs:
	- `artifacts/logs/final_focus_fix_tech_pass.log`
	- `artifacts/logs/final_full_fix_tech_pass.log`
	- `artifacts/logs/final_benchmark_fix_tech_pass.log`

## Release Freeze Validation (`prototype-v2-rc1`)
- Full-suite rerun:
	- `C:/Python39/python.exe -m unittest discover -s tests -v`
	- result: 35 passed, 0 failed, 0 skipped
	- log: `artifacts/releases/prototype-v2-rc1/final_full_test.log`
- Benchmark evidence verification (existing final run, no rerun required):
	- `artifacts/benchmarks/benchmark_20260731_024647/benchmark-results.json`
	- `TOTAL_FIXTURES=30`
	- `PARITY_RATE=1.0`
	- `TECH_PASS_RATE=1.0`
- Runtime/API/package checks:
	- `/editor` status: 200
	- `/api/convert` status: 200
	- conversion job completed and downloadable
	- ZIP contains index/assets/manifest/quality report
	- ZIP excludes internal utility files
	- markdown references resolve
	- port 8012 not listening
	- logs: `artifacts/releases/prototype-v2-rc1/release_freeze_audit.log`, `runtime_checks.json`

## Manual Fidelity Review Baseline Validation
- Review run command:
	- `C:/Python39/python.exe run_manual_fidelity_review.py`
- Review run output:
	- `artifacts/fidelity-reviews/review-20260731-034421/`

- Review-tool tests:
	- `C:/Python39/python.exe -m unittest tests.test_fidelity_review_tools tests.test_manual_fidelity_review_guardrails -v`
	- result: 9 passed, 0 failed

- Full suite after review tooling:
	- `C:/Python39/python.exe -m unittest discover -s tests -v`
	- result: 44 passed, 0 failed, 0 skipped

- Parity recheck after review tooling:
	- `C:/Python39/python.exe artifacts/endpoint_release_check_live/strict_compare_run.py`
	- `COMPARE_MD=True`
	- `COMPARE_ASSETS=True`
	- `COMPARE_MANIFEST_CORE=True`
	- `COMPARE_QUALITY_CORE=True`

- Runtime recheck:
	- `/editor` status 200
	- `/api/convert` status 200
	- port 8012 not listening
	- user ZIP references resolved
	- logs: `artifacts/logs/manual_fidelity_runtime_recheck.log`

## Fidelity Terminology Correction Validation
- Review-run command:
	- `C:/Python39/python.exe run_manual_fidelity_review.py`
- Corrected review run:
	- `artifacts/fidelity-reviews/review-20260731-042323/`
- Focused review tooling tests:
	- `C:/Python39/python.exe -m unittest tests.test_fidelity_review_tools tests.test_manual_fidelity_review_guardrails -v`
	- result: 12 passed, 0 failed
- Full test suite after correction:
	- `C:/Python39/python.exe -m unittest discover -s tests -v`
	- result: 47 passed, 0 failed, 0 skipped
- Endpoint/direct parity after correction:
	- `C:/Python39/python.exe artifacts/endpoint_release_check_live/strict_compare_run.py`
	- `COMPARE_MD=True`
	- `COMPARE_ASSETS=True`
	- `COMPARE_MANIFEST_CORE=True`
	- `COMPARE_QUALITY_CORE=True`

## 2026-08-05 Markdown Download Endpoint Validation

- Focused endpoint integration:
	- `C:/Python39/python.exe -m unittest tests.test_endpoint_integration -v`
	- result: 6 passed, 0 failed, 0 skipped
- Full suite:
	- `C:/Python39/python.exe -m unittest discover -s tests -v`
	- result: 48 passed, 0 failed, 0 skipped
- Baseline refresh before live strict compare:
	- `C:/Python39/python.exe convert_to_md.py file-sample_150kB.pdf --output-dir artifacts/final_milestone --overwrite --pdf-mode hybrid`
	- result: pass
- Strict endpoint comparison (live `/api/convert`):
	- `C:/Python39/python.exe artifacts/endpoint_release_check_live/strict_compare_run.py`
	- `COMPARE_MD=True`
	- `COMPARE_ASSETS=True`
	- `COMPARE_MANIFEST_CORE=True`
	- `COMPARE_QUALITY_CORE=True`

## 2026-08-05 ITSD Site Integration Validation

- Focused suites:
	- `C:/Python39/python.exe -m unittest tests.test_site_publish tests.test_endpoint_integration tests.test_mkdocs_stage_migration -v`
	- result: 11 passed, 0 failed, 0 skipped
- Full suite:
	- `C:/Python39/python.exe -m unittest discover -s tests -v`
	- result: 51 passed, 0 failed, 0 skipped
- MkDocs build:
	- `C:/Python39/python.exe -m mkdocs build -f mkdocs_preview/mkdocs.yml`
	- result: pass
- Live publish smoke test:
	- `C:/Python39/python.exe artifacts/logs/site_publish_smoke_20260805.py`
	- result:
		- `PAGE_HAS_TITLE=True`
		- `HOME_OK=True`
		- `CONTACT_FORM_OK=True`
- Strict endpoint parity rerun:
	- `C:/Python39/python.exe artifacts/endpoint_release_check_live/strict_compare_run.py`
	- `COMPARE_MD=True`
	- `COMPARE_ASSETS=True`
	- `COMPARE_MANIFEST_CORE=True`
	- `COMPARE_QUALITY_CORE=True`

## 2026-08-05 Folder Dropdown Publish Validation

- Focused suites:
	- `C:/Python39/python.exe -m unittest tests.test_site_publish tests.test_endpoint_integration tests.test_mkdocs_stage_migration -v`
	- result: 14 passed, 0 failed, 0 skipped
- Full suite:
	- `C:/Python39/python.exe -m unittest discover -s tests -v`
	- result: 54 passed, 0 failed, 0 skipped
- MkDocs rebuild:
	- `C:/Python39/python.exe -m mkdocs build -f mkdocs_preview/mkdocs.yml`
	- result: pass
- Live route checks:
	- `/editor` status 200
	- `/docs/folder-manager/` status 200
	- `/api/site-folders` returned folder list successfully
- Live folder create smoke:
	- POST `/api/site-folders` with `Policies`
	- result: success HTML returned and `policies` appeared in folder list

## 2026-08-05 FAQ and Showcase Content Validation

- MkDocs rebuild:
	- `C:/Python39/python.exe -m mkdocs build -f mkdocs_preview/mkdocs.yml`
	- result: pass
- Live content checks:
	- `C:/Python39/python.exe -c "from urllib import request; ..."`
	- result:
		- `FAQ_BUTTON=True`
		- `PROFILE_CARD=True`
		- `FAQ_SECTION=True`
- Live route checks:
	- `/docs/` => 200
	- `/docs/faq/` => 200
	- `/docs/builder-profile/` => 200

## 2026-08-05 Minimal Searchable Site Validation
- MkDocs build through `build_itsd_site()`: pass.
- Full suite: 54 passed, 0 failed, 0 skipped.
- Live routes `/docs/`, `/editor`, `/docs/published/`, and `/docs/search.html?q=converter`: 200.
- Search index contains only the home page and published documents; obsolete showcase pages are absent.
- Strict endpoint parity: Markdown, assets, manifest core, and quality core all true.

## 2026-08-05 Runtime Cleanup Validation
- Focused site/endpoint suites: 11 passed, 0 failed.
- Full suite: 53 passed, 0 failed, 0 skipped.
- Strict endpoint parity: Markdown, assets, manifest core, and quality core all true.
- Live retained routes `/editor`, `/docs/`, and `/docs/published/`: 200.
- Removed routes `/api/site-folders` and `/faq`: 404.
- Existing-site startup check: `SITE_REBUILT_ON_IMPORT=False`.
- Python diagnostics for edited files: no errors.

## 2026-08-05 GitHub Footprint Validation
- Clean workspace: 123.86 MiB, 1,060 files (previously 433.88 MiB, 10,050 files).
- Largest file: 17.88 MiB, below GitHub's 100 MiB per-file limit.
- Cleanup idempotence: 0 remaining targets after final cleanup.
- Forced offline resolution: `pip install --ignore-installed --no-index --find-links=wheelhouse -r requirements.txt --dry-run` passed.
- Full suite: 53 passed, 0 failed, 0 skipped.
- Strict parity: Markdown, assets, manifest core, and quality core all true.

## 2026-08-05 Flat Navigation Validation
- Focused site tests: 6 passed, 0 failed.
- Full suite: 54 passed, 0 failed, 0 skipped.
- Generated Home submenu: absent.
- Desktop footer navigation controls: absent.
- Mobile version navigation container: hidden.
- Browser visual check: sidebar contains only Search, Home, Converter, and Documents.
- Strict endpoint parity: all comparison fields true.
