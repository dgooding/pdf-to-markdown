# Decisions Log

## Milestone Decisions

1. Keep original converter UI and route (`/editor`) as the primary product surface.
2. Keep MkDocs tooling developer-only; do not auto-start any MkDocs server.
3. Use two real candidate strategies per page (`native_semantic`, `hybrid_targeted_fallback`) and select by explainable component scores.
4. Preserve placement-aware image model and prevent cross-page placement inference from deduplication.
5. Keep developer/environment diagnostics out of published Markdown; place diagnostics in manifest and quality report.
6. Keep technical validation and content fidelity as separate statuses.
7. Prefer targeted region fallbacks over full-page images whenever possible.
8. Use one authoritative conversion service for both direct and API conversion paths:
	- `run_authoritative_conversion_service(...)` in `app.py`.
9. Endpoint packaging must include both manifest and quality report, and conversion is considered failed if either is missing.
10. Comparison normalization removes only documented volatile fields; substantive core fields and selected strategies must match.
11. Milestone 1 fixture corpus is synthetic-only and generated deterministically from configurable seed values.
12. Determinism validation for fixtures is semantic-structure based (stable sidecars + fixture metadata), not raw binary hash equality, because DOCX/PDF container metadata can vary despite equivalent content.
13. Fixture-generation includes no internet dependency and uses locally generated visual assets only.
14. Maintain endpoint parity checks after each milestone to prevent conversion-path drift.
15. Milestone 2 baseline benchmark uses both direct authoritative conversion and live `/api/convert` endpoint for every generated fixture.
16. Non-PDF authoritative conversions now emit normalized manifest and quality-report artifacts to maintain cross-format endpoint/direct parity and complete packaging guarantees.
17. OCR provider diagnostics are explicit (`detect_tesseract_provider`) and recorded in manifest/quality artifacts; missing OCR remains graceful and non-fatal for non-OCR-required paths.
18. Table strategy reporting now includes selected strategy, attempt order, and confidence for auditability.
19. Two-column reading-order logic uses word-level column detection and left/right line splitting to avoid line-by-line alternation in mixed-span layouts.
20. Publish structured review-record artifacts separate from public markdown to preserve clean docs while retaining operator traceability.
21. Introduce safe batch conversion path with resumable state and strict excluded-directory rules for large corpus operations.
22. Keep MkDocs migration as staged utility with explicit conflict strategies instead of mutating the main converter runtime.
23. Enforce upload guardrails (count/size/filename sanitization) and zip package exclusion filters in API flow.
24. Absolute-path validation should detect converter-environment leakage only (temp/runtime paths), not legitimate user/source-content path literals.
25. End-state success criteria achieved: full suite green and synthetic corpus benchmark parity + technical pass both at 1.0.
26. Release freeze for `prototype-v2-rc1` is documentation/evidence packaging only; no new conversion algorithms/providers/UI redesign are introduced in freeze scope.
27. Technical success metrics (test pass, parity rate, technical pass rate) must remain explicitly separate from fidelity-review conclusions.
28. Human review evidence is required before any final fidelity claim beyond automated classifications.
29. Real pilot documents are local-only by default and noncommitted unless explicitly authorized.
30. Algorithm changes are deferred until baseline manual review + pilot measurement are complete and defects are prioritized.
31. Automated review preparation outputs must not be labeled as completed human fidelity review; human fields remain blank/pending until real reviewer input.
32. Automated/human agreement, false-confidence counts, and human review/cleanup times remain `pending_human_review` or null when no real human ratings exist.
33. Default user download action should return the generated Markdown file directly, while the ZIP package remains available as a secondary artifact-preserving endpoint.
34. Published site documents should land under `mkdocs_preview/docs/published/` using sanitized relative site paths rather than writing arbitrarily into the docs root.
35. The MkDocs site remains a static build served by FastAPI; no standalone MkDocs dev server is auto-started for user runtime.
36. Portfolio/showcase content for the site should be delivered as plain Markdown pages inside the MkDocs project, keeping the brag/demo layer maintainable and easy to review.
37. Replace showcase content with a minimal industrial site: persistent left navigation, built-in search, direct converter access, and a searchable published-document library.
38. Remove obsolete CMS-style folder management, contact, FAQ/showcase, and white-paper runtime surfaces; keep publishing as a single document-name-based action with duplicate protection.
39. Reuse an existing static MkDocs build at application startup; build only when missing or after a successful publish.
40. Keep the GitHub repository self-contained for offline Windows installation while excluding repeated generated evidence; retain one validated benchmark and strict parity baseline.
41. Keep site navigation flat: one-level Home, Converter, and Documents links with search; do not expose page-section dropdowns or previous/next controls.
42. Keep the source repository public while protecting hosted document mutations with `PUBLISH_SECRET` rather than repository visibility.
43. Expose document deletion on the Documents page, require confirmation and the publish secret, and enforce normalized path containment on the server.
44. Treat `DATA_ROOT/published` as the hosted persistent source and synchronize it into the MkDocs source tree before static builds.
45. Hosted document mutations must fail closed when `PUBLISH_SECRET` is absent; never treat a missing production secret as anonymous authorization.
46. Serialize publish/delete rebuild transactions with a thread lock inside worker threads for Python 3.9 event-loop compatibility.
47. Keep interactive Documents-page behavior in a static JavaScript asset so MkDocs search results remain content-focused.
48. Expose a non-sensitive hosted capability flag and disable unavailable mutation controls instead of allowing users to discover missing setup through failed requests.
49. Provide administrator controls through an always-visible upper-right Admin button that validates against the server before revealing Delete and Publish controls; never treat client-side visibility as authorization.
50. Keep the administrator passcode out of tracked source and browser storage. Configure it only as hosted `PUBLISH_SECRET`, retain a successful entry in page memory, and revalidate every destructive request at the API boundary.
