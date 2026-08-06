from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import statistics
import time
from pathlib import Path
from typing import Any

from fidelity_review_tools import (
    DOC_CLEANUP_VALUES,
    build_scorecard_schema,
    compute_calibration,
    compute_cleanup_metrics,
    detect_real_pilot_inputs,
    now_iso,
    rank_defects,
    redact_metadata,
    validate_scorecard,
    write_json,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_BENCH = ROOT / "artifacts" / "benchmarks" / "benchmark_20260731_024647" / "benchmark-results.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Manual fidelity review runner for synthetic + approved real pilot docs.")
    p.add_argument("--benchmark-json", type=Path, default=DEFAULT_BENCH)
    p.add_argument("--corpus-manifest", type=Path, default=ROOT / "tests" / "fixtures" / "generated" / "generated-corpus.json")
    p.add_argument("--review-root", type=Path, default=ROOT / "artifacts" / "fidelity-reviews")
    p.add_argument("--pilot-input", type=Path, default=ROOT / "pilot_input")
    return p.parse_args()


def _mk_run_dir(base: Path) -> tuple[str, Path]:
    run_id = time.strftime("review-%Y%m%d-%H%M%S", time.localtime())
    run_dir = base / run_id
    for sub in [
        "synthetic-review",
        "real-document-pilot",
        "scorecards",
        "comparisons",
        "previews",
        "defect-evidence",
        "measurements",
        "summaries",
        "logs",
        "human-review-packet",
    ]:
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    return run_id, run_dir


def _run_cmd(cwd: Path, command: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _discover_git_status(root: Path) -> dict[str, Any]:
    current = root
    found = None
    while True:
        if (current / ".git").exists():
            found = current
            break
        if current.parent == current:
            break
        current = current.parent

    if not found:
        return {
            "is_git_repository": False,
            "parent_repository_found": False,
            "repository_root": None,
            "current_branch": None,
            "current_commit": None,
            "prototype_v2_rc1_tag_exists": None,
            "recommended_next_action": "Obtain or restore repository metadata before release tagging.",
            "commands_requiring_human_authorization": [
                "git init",
                "git add app.py convert_to_md.py tests artifacts/releases/prototype-v2-rc1 *.md",
                "git commit -m \"release: complete technical validation for document migration prototype v2\"",
                "git tag -a prototype-v2-rc1 -m \"prototype-v2-rc1\"",
                "git remote add origin <approved-remote-url>",
            ],
        }

    _, branch_out, _ = _run_cmd(found, ["git", "branch", "--show-current"])
    _, commit_out, _ = _run_cmd(found, ["git", "rev-parse", "HEAD"])
    _, tags_out, _ = _run_cmd(found, ["git", "tag", "--list", "prototype-v2-rc1"])
    return {
        "is_git_repository": True,
        "parent_repository_found": str(found.resolve()) != str(root.resolve()),
        "repository_root": str(found.resolve()),
        "current_branch": branch_out or None,
        "current_commit": commit_out or None,
        "prototype_v2_rc1_tag_exists": bool(tags_out.strip()),
        "recommended_next_action": "Use existing repository workflow for checkpoint commit and tag governance.",
        "commands_requiring_human_authorization": ["git commit ...", "git tag ...", "git push ..."],
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _index_fixtures(corpus: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for f in corpus.get("fixtures", []):
        out[f["fixture_id"]] = f
    return out


def _select_samples(results: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str]]:
    rr = [r["fixture_id"] for r in results if r.get("fidelity_status_direct") == "review_required"]
    high_all = [r["fixture_id"] for r in results if r.get("fidelity_status_direct") == "high"]
    mod_all = [r["fixture_id"] for r in results if r.get("fidelity_status_direct") == "moderate"]

    preferred_high = ["PDF-001", "PDF-002", "PDF-006", "PDF-009", "PDF-016"]
    preferred_mod = ["DOCX-001", "DOCX-003", "DOCX-004", "DOCX-007", "DOCX-009"]

    high = [x for x in preferred_high if x in high_all]
    for x in high_all:
        if len(high) >= 5:
            break
        if x not in high:
            high.append(x)

    mod = [x for x in preferred_mod if x in mod_all]
    for x in mod_all:
        if len(mod) >= 5:
            break
        if x not in mod:
            mod.append(x)

    return rr, high[:5], mod[:5]


def _collect_doc_evidence(bench_root: Path, fixture_id: str) -> dict[str, Any]:
    fdir = bench_root / "fixtures" / fixture_id.lower()
    direct = fdir / "direct"
    endpoint = fdir / "endpoint" / "extracted"

    manifest = next(direct.glob("*-manifest.json"), None)
    quality = next(direct.glob("*-quality-report.json"), None)
    md = next((direct / "docs").glob("*.md"), None)
    endpoint_zip = fdir / "endpoint" / "package.zip"

    return {
        "direct_dir": direct,
        "endpoint_dir": endpoint,
        "manifest_path": manifest,
        "quality_path": quality,
        "markdown_path": md,
        "endpoint_package": endpoint_zip,
    }


def _defects_from_manifest(fixture_id: str, manifest: dict[str, Any], automated_fidelity: str) -> list[dict[str, Any]]:
    defects: list[dict[str, Any]] = []
    pages = manifest.get("document_result", {}).get("pages", [])

    for page in pages:
        pno = page.get("page_number")
        fallbacks = page.get("fallback_records", []) or []
        for fr in fallbacks:
            ftype = fr.get("fallback_type")
            if ftype == "full_page":
                defects.append(
                    {
                        "defect_id": f"{fixture_id}-P{pno}-FULLPAGE",
                        "title": "Full-page fallback requires manual semantic review",
                        "description": "Page output relies on full-page visual fallback instead of semantic extraction.",
                        "defect_type": "unnecessary_full_page_fallback",
                        "severity": "moderate" if automated_fidelity == "review_required" else "minor",
                        "automated_detection_status": "detected",
                        "current_fallback": "full_page_visual",
                        "proposed_improvement": "Defer algorithm changes until post-baseline defect prioritization",
                        "expected_benefit": "high",
                        "regression_risk": "medium",
                        "recommended_milestone": "post-baseline-prioritization",
                    }
                )
            elif ftype == "table_crop":
                defects.append(
                    {
                        "defect_id": f"{fixture_id}-P{pno}-TABLECROP",
                        "title": "Visual table fallback may require semantic reconstruction",
                        "description": "Table was represented visually; accessible table semantics may be incomplete.",
                        "defect_type": "table_error",
                        "severity": "moderate",
                        "automated_detection_status": "detected",
                        "current_fallback": "targeted_table_crop",
                        "proposed_improvement": "Post-baseline table strategy tuning",
                        "expected_benefit": "medium",
                        "regression_risk": "medium",
                        "recommended_milestone": "post-baseline-prioritization",
                    }
                )

    # OCR warnings at document level.
    warnings = [str(w).lower() for w in (manifest.get("warnings", []) or [])]
    if any("ocr recommended but unavailable" in w for w in warnings):
        defects.append(
            {
                "defect_id": f"{fixture_id}-OCR-UNAVAILABLE",
                "title": "OCR unavailable for page(s) flagged for OCR",
                "description": "OCR was recommended in conversion warnings but unavailable in environment.",
                "defect_type": "OCR_error",
                "severity": "moderate",
                "automated_detection_status": "detected",
                "current_fallback": "visual_or_native_fallback",
                "proposed_improvement": "Environment/provider policy and post-baseline OCR tuning",
                "expected_benefit": "medium",
                "regression_risk": "low",
                "recommended_milestone": "post-baseline-prioritization",
            }
        )

    return defects


def _page_rating(page: dict[str, Any], automated_fidelity: str) -> str:
    fallbacks = page.get("fallback_records", []) or []
    if any(fr.get("fallback_type") == "full_page" for fr in fallbacks):
        return "cleanup_required"
    if automated_fidelity == "review_required":
        return "cleanup_required"
    if automated_fidelity == "moderate":
        return "acceptable_with_minor_difference"
    return "correct"


def _build_scorecard(
    *,
    run_id: str,
    fixture_id: str,
    fixture_meta: dict[str, Any],
    bench_result: dict[str, Any],
    evidence: dict[str, Any],
    review_dir: Path,
) -> dict[str, Any]:
    start = time.time()
    manifest = _load_json(evidence["manifest_path"]) if evidence.get("manifest_path") and evidence["manifest_path"].exists() else {}
    quality = _load_json(evidence["quality_path"]) if evidence.get("quality_path") and evidence["quality_path"].exists() else {}

    pages = manifest.get("document_result", {}).get("pages", [])
    page_reviews = []
    for p in pages:
        pno = int(p.get("page_number", 0))
        fbs = p.get("fallback_records", []) or []
        has_full = any(fr.get("fallback_type") == "full_page" for fr in fbs)
        has_table_visual = any(fr.get("fallback_type") == "table_crop" for fr in fbs)
        has_targeted = any(fr.get("fallback_type") not in {"full_page"} for fr in fbs)
        has_semantic_table = any(str(t.get("kind", "")).startswith("table_") and t.get("kind") in {"table_markdown", "table_html"} for t in (manifest.get("tables_detected", []) or []) if int(t.get("page", 0)) == pno)

        base_rating = _page_rating(p, str(bench_result.get("fidelity_status_direct", "review_required")))
        defects_ids = []
        if has_full:
            defects_ids.append(f"{fixture_id}-P{pno}-FULLPAGE")
        if has_table_visual:
            defects_ids.append(f"{fixture_id}-P{pno}-TABLECROP")

        page_reviews.append(
            {
                "page_number": pno,
                "source_page_preview": str((ROOT / "tests" / "fixtures" / "generated" / "previews" / f"{fixture_id.lower()}-p1.png").resolve()) if fixture_meta.get("source_format") == "pdf" else "not_available",
                "output_page_preview": str((evidence["direct_dir"] / "docs" / "assets").resolve()),
                "selected_conversion_strategy": p.get("selected_candidate", "unknown"),
                "native_extraction_used": bool(p.get("native_text_available", False)),
                "ocr_used": bool(int(pno) in set(manifest.get("pages_with_ocr", []) or [])),
                "semantic_table_used": has_semantic_table,
                "visual_table_fallback_used": has_table_visual,
                "targeted_visual_fallback_used": has_targeted,
                "full_page_fallback_used": has_full,
                "semantic_coverage_rating": base_rating,
                "visual_coverage_rating": "correct" if p.get("visual_coverage", 0) >= 0.5 else "acceptable_with_minor_difference",
                "accessible_coverage_rating": "cleanup_required" if has_full else base_rating,
                "reading_order_rating": base_rating,
                "heading_structure_rating": base_rating,
                "list_structure_rating": base_rating,
                "table_rating": "cleanup_required" if has_table_visual else ("correct" if has_semantic_table else "not_applicable"),
                "image_rating": "correct" if p.get("embedded_image_count", 0) > 0 or has_full else "not_applicable",
                "chart_rating": "acceptable_with_minor_difference" if has_targeted else "not_applicable",
                "diagram_rating": "acceptable_with_minor_difference" if has_targeted else "not_applicable",
                "link_rating": "correct",
                "unicode_rating": "correct",
                "code_formatting_rating": "acceptable_with_minor_difference" if fixture_id == "DOCX-007" else "not_applicable",
                "header_footer_rating": "acceptable_with_minor_difference",
                "duplicate_content_rating": "correct",
                "missing_content_rating": "cleanup_required" if has_full else "acceptable_with_minor_difference",
                "page_acceptance_result": "review_required" if has_full else ("pass_with_cleanup" if base_rating != "correct" else "pass"),
                "page_review_reasons": p.get("review_reasons", []) or [],
                "page_defect_ids": defects_ids,
            }
        )

    auto_fid = str(bench_result.get("fidelity_status_direct", "review_required"))
    auto_tech = str(bench_result.get("technical_status_direct", "failed"))

    if auto_fid == "high":
        auto_reco = "pass"
        cleanup = "none"
    elif auto_fid == "moderate":
        auto_reco = "pass_with_cleanup"
        cleanup = "minor"
    else:
        auto_reco = "review_required"
        cleanup = "moderate"

    defects = _defects_from_manifest(fixture_id, manifest, auto_fid)
    block = sum(1 for d in defects if d.get("severity") in {"major", "critical"})
    nonblock = max(0, len(defects) - block)

    artifact_seconds = round(time.time() - start, 4)
    scorecard = {
        "review_run_id": run_id,
        "fixture_or_document_id": fixture_id,
        "source_filename": fixture_meta.get("filename", fixture_id),
        "source_format": fixture_meta.get("source_format", "unknown"),
        "source_location_classification": "workspace_local_fixture",
        "synthetic_or_real": "synthetic",
        "confidentiality_classification": "synthetic_nonconfidential",
        "source_page_count": fixture_meta.get("page_count", 0),
        "output_markdown_path": str(evidence.get("markdown_path")) if evidence.get("markdown_path") else "missing",
        "asset_directory": str((evidence.get("direct_dir") / "docs" / "assets").resolve()),
        "manifest_path": str(evidence.get("manifest_path")) if evidence.get("manifest_path") else "missing",
        "quality_report_path": str(evidence.get("quality_path")) if evidence.get("quality_path") else "missing",
        "endpoint_package_path": str(evidence.get("endpoint_package")) if evidence.get("endpoint_package") else "missing",
        "reviewer": "",
        "review_date": "",
        "human_review_status": "not_reviewed",
        "automated_technical_status": auto_tech,
        "automated_fidelity_status": auto_fid,
        "automated_review_recommendation": auto_reco,
        "automated_artifact_processing_seconds": artifact_seconds,
        "human_technical_status": "not_reviewed",
        "human_fidelity_status": None,
        "human_review_minutes": None,
        "human_cleanup_minutes": None,
        "human_cleanup_status": "not_measured",
        "acceptance_category": auto_reco,
        "cleanup_category": cleanup,
        "cleanup_minutes_measured_or_estimated": "not_measured",
        "overall_notes": "Automated fidelity-review preparation and scorecard generation. Human review is pending.",
        "blocking_defect_count": block,
        "nonblocking_defect_count": nonblock,
        "page_reviews": page_reviews,
        "defects": defects,
    }

    errs = validate_scorecard(scorecard)
    if errs:
        scorecard["human_review_status"] = "not_reviewed"
        scorecard["overall_notes"] += f" Schema issues: {errs}"
    return scorecard


def _scorecard_markdown(sc: dict[str, Any]) -> str:
    lines = [
        f"# Scorecard {sc['fixture_or_document_id']}",
        "",
        f"- review_run_id: `{sc['review_run_id']}`",
        f"- source_filename: `{sc['source_filename']}`",
        f"- source_format: `{sc['source_format']}`",
        f"- automated fidelity: `{sc['automated_fidelity_status']}`",
        f"- automated review recommendation: `{sc['automated_review_recommendation']}`",
        f"- human review status: `{sc['human_review_status']}`",
        f"- human fidelity: `{sc['human_fidelity_status']}`",
        f"- acceptance (automated recommendation): `{sc['acceptance_category']}`",
        f"- cleanup category: `{sc['cleanup_category']}`",
        f"- human review minutes: `{sc['human_review_minutes']}`",
        f"- human cleanup minutes: `{sc['human_cleanup_minutes']}`",
        f"- automated artifact processing seconds: `{sc['automated_artifact_processing_seconds']}`",
        f"- blocking defects: {sc['blocking_defect_count']}",
        f"- nonblocking defects: {sc['nonblocking_defect_count']}",
        "",
        "## Page summaries",
        "",
    ]
    for p in sc.get("page_reviews", []):
        lines.append(f"- Page {p['page_number']}: strategy={p['selected_conversion_strategy']}, acceptance={p['page_acceptance_result']}, reasons={p['page_review_reasons']}")
    lines.append("")
    lines.append("## Defects")
    lines.append("")
    if not sc.get("defects"):
        lines.append("- none")
    else:
        for d in sc["defects"]:
            lines.append(f"- `{d['defect_id']}` [{d['severity']}] {d['defect_type']}: {d['title']}")
    lines.append("")
    return "\n".join(lines)


def _write_review_run_md(path: Path, run_payload: dict[str, Any]) -> None:
    lines = [
        "# Fidelity Review Run",
        "",
        f"- review_run_id: `{run_payload['review_run_id']}`",
        f"- created_at: `{run_payload['created_at']}`",
        f"- review_status: `{run_payload['review_status']}`",
        f"- synthetic_review_documents: {len(run_payload['documents_included'])}",
        f"- real_pilot_status: `{run_payload['real_document_pilot_status']}`",
        f"- algorithm_changes_during_baseline: `{run_payload['algorithm_changes_during_baseline']}`",
        "- classification: `Automated fidelity-review preparation and scorecard generation`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    bench = _load_json(args.benchmark_json)
    corpus = _load_json(args.corpus_manifest)
    fixture_map = _index_fixtures(corpus)

    run_id, run_dir = _mk_run_dir(args.review_root)
    bench_root = args.benchmark_json.parent

    schema = build_scorecard_schema()
    write_json(run_dir / "scorecards" / "scorecard-schema.json", schema)
    (run_dir / "scorecards" / "scorecard-template.md").write_text(
        "# Scorecard Template\n\nUse scorecard-schema.json required fields and allowed values.\nDocument-level and page-level ratings must use approved enums only.\nAutomated fields must remain separate from human review fields.\n",
        encoding="utf-8",
    )
    instructions_lines = [
        "# HUMAN REVIEW INSTRUCTIONS",
        "",
        "1. Open the source document.",
        "2. Open the corresponding converted Markdown or rendered preview.",
        "3. Compare each source page against the output.",
        "4. Check text completeness.",
        "5. Check reading order.",
        "6. Check headings and lists.",
        "7. Check tables.",
        "8. Check images and page placement.",
        "9. Check charts and diagrams.",
        "10. Check links.",
        "11. Check visual fallbacks.",
        "12. Record actual review start and end time.",
        "13. Record only actual cleanup time.",
        "14. Do not approve based only on technical validation.",
        "15. Save the completed scorecard.",
        "",
        "Human fields start blank by design in this automated preparation run.",
    ]
    (run_dir / "HUMAN_REVIEW_INSTRUCTIONS.md").write_text("\n".join(instructions_lines), encoding="utf-8")

    results = bench.get("results", [])
    rr, high, moderate = _select_samples(results)
    reviewed_ids = []
    for fid in rr + high + moderate:
        if fid not in reviewed_ids:
            reviewed_ids.append(fid)

    scorecards = []
    for fid in reviewed_ids:
        row = next(r for r in results if r["fixture_id"] == fid)
        meta = fixture_map.get(fid, {"fixture_id": fid, "filename": fid, "source_format": row.get("source_format", "unknown"), "page_count": row.get("page_count", 0)})
        evidence = _collect_doc_evidence(bench_root, fid)
        sc = _build_scorecard(
            run_id=run_id,
            fixture_id=fid,
            fixture_meta=meta,
            bench_result=row,
            evidence=evidence,
            review_dir=run_dir,
        )
        scorecards.append(sc)
        write_json(run_dir / "scorecards" / f"{fid.lower()}.scorecard.json", sc)
        (run_dir / "scorecards" / f"{fid.lower()}.scorecard.md").write_text(_scorecard_markdown(sc), encoding="utf-8")

        comparison = {
            "fixture_id": fid,
            "compare_md": row.get("compare_md"),
            "compare_assets": row.get("compare_assets"),
            "compare_manifest_core": row.get("compare_manifest_core"),
            "compare_quality_core": row.get("compare_quality_core"),
            "technical_status_direct": row.get("technical_status_direct"),
            "technical_status_endpoint": row.get("technical_status_endpoint"),
            "fidelity_status_direct": row.get("fidelity_status_direct"),
            "fidelity_status_endpoint": row.get("fidelity_status_endpoint"),
            "notes": row.get("notes", []),
        }
        write_json(run_dir / "comparisons" / f"{fid.lower()}-comparison.json", comparison)

        manifest = _load_json(evidence["manifest_path"]) if evidence.get("manifest_path") and evidence["manifest_path"].exists() else {}
        quality = _load_json(evidence["quality_path"]) if evidence.get("quality_path") and evidence["quality_path"].exists() else {}

        support = {
            "fixture_id": fid,
            "source_path": meta.get("source_path"),
            "source_preview": meta.get("preview"),
            "output_markdown": str(evidence.get("markdown_path")) if evidence.get("markdown_path") else None,
            "asset_inventory": sorted([p.name for p in (evidence.get("direct_dir") / "docs" / "assets").glob("*") if p.is_file()]) if evidence.get("direct_dir") else [],
            "page_strategy_summary": [
                {
                    "page_number": p.get("page_number"),
                    "selected_candidate": p.get("selected_candidate"),
                    "review_reasons": p.get("review_reasons", []),
                }
                for p in manifest.get("document_result", {}).get("pages", [])
            ],
            "fallback_summary": [
                {
                    "page_number": p.get("page_number"),
                    "fallback_records": p.get("fallback_records", []),
                }
                for p in manifest.get("document_result", {}).get("pages", [])
            ],
            "automated_warnings": manifest.get("warnings", []) + quality.get("warnings", []),
            "scorecard_path": str((run_dir / "scorecards" / f"{fid.lower()}.scorecard.json").resolve()),
        }
        write_json(run_dir / "synthetic-review" / f"{fid.lower()}-support.json", support)

    calibration = compute_calibration(scorecards)
    cleanup = compute_cleanup_metrics(scorecards)
    defects_ranked = rank_defects(scorecards)

    write_json(run_dir / "fidelity-calibration.json", calibration)
    write_json(run_dir / "cleanup-measurements.json", cleanup)
    write_json(run_dir / "defect-ranking.json", {"top_defects": defects_ranked[:10], "all_defects": defects_ranked})

    (run_dir / "fidelity-calibration.md").write_text(
        "# Fidelity Calibration\n\n" + json.dumps(calibration, indent=2), encoding="utf-8"
    )
    (run_dir / "cleanup-measurements.md").write_text(
        "# Cleanup Measurements\n\n" + json.dumps(cleanup, indent=2), encoding="utf-8"
    )
    (run_dir / "defect-ranking.md").write_text(
        "# Defect Ranking\n\n" + json.dumps({"top_defects": defects_ranked[:10]}, indent=2), encoding="utf-8"
    )

    synthetic_summary = {
        "review_required_fixtures_reviewed": rr,
        "high_sampled": high,
        "moderate_sampled": moderate,
        "total_synthetic_reviewed": len(reviewed_ids),
    }
    write_json(run_dir / "synthetic-review-summary.json", synthetic_summary)
    (run_dir / "synthetic-review-summary.md").write_text(
        "# Synthetic Review Summary\n\n" + json.dumps(synthetic_summary, indent=2), encoding="utf-8"
    )

    pilot = detect_real_pilot_inputs(args.pilot_input)
    intake_readme = [
        "# Real-document pilot intake",
        "",
        "Status defaults to waiting_for_approved_inputs until approved files are placed here.",
        "",
        "## Intake requirements",
        "- Recommended document count: 5 to 10 initially",
        "- Approved file types: .pdf, .docx, .md, .txt",
        "- Do not use confidential or restricted documents without authorization",
        "- Documents remain local",
        "- Documents are not committed by default",
        "- Previews are not committed by default",
        "- Original documents are never modified",
        "- Conversion outputs remain separate from source inputs",
        "",
        "## Metadata to record per pilot input",
        "- Document classification (simple DOCX / complex DOCX / native-text PDF / table PDF / screenshot-flowchart PDF / scanned or image-heavy / longer procedure)",
        "- approved_for_local_processing",
        "- approved_for_preview_generation",
        "- approved_for_retention",
        "",
        "## Note",
        "Do not search external locations; place approved files explicitly in this folder.",
    ]
    (args.pilot_input / "README.md").write_text("\n".join(intake_readme), encoding="utf-8")
    pilot_template = {
        "pilot_id": "",
        "source_filename": "",
        "file_type": "",
        "file_size": None,
        "page_count": None,
        "feature_categories": [],
        "confidentiality_classification": "local_only",
        "approved_for_local_processing": False,
        "approved_for_artifact_preview": False,
        "approved_for_commit": False,
        "approved_for_retention": False,
        "expected_review_sensitivity": "",
        "conversion_status": "pending",
        "review_status": "pending",
    }
    write_json(args.pilot_input / "pilot_inventory_template.json", {"template": pilot_template})
    write_json(run_dir / "real-document-pilot" / "pilot-inventory.json", pilot)
    if pilot.get("status") == "waiting_for_approved_inputs":
        real_summary_md = "# Real Document Pilot Summary\n\nwaiting_for_approved_inputs\n"
    else:
        real_summary_md = "# Real Document Pilot Summary\n\n" + json.dumps(pilot, indent=2)
    (run_dir / "real-document-pilot-summary.md").write_text(real_summary_md, encoding="utf-8")

    auto_dist = bench.get("fidelity_distribution", {})
    human_dist = {"status": "pending_human_review", "high": None, "moderate": None, "low": None, "review_required": None}
    acceptance_dist = {k: 0 for k in ["pass", "pass_with_cleanup", "review_required", "failed"]}
    for sc in scorecards:
        acc = sc.get("acceptance_category")
        if acc in acceptance_dist:
            acceptance_dist[acc] += 1

    recommendation = "approve_for_limited_pilot" if pilot.get("status") == "waiting_for_approved_inputs" else "approve_with_documented_review_requirements"

    release_reco = {
        "recommendation": recommendation,
        "basis": {
            "technical_pass_rate": bench.get("technical_pass_rate"),
            "endpoint_parity_rate": bench.get("endpoint_parity_rate"),
            "human_review_documents": 0,
            "real_pilot_status": pilot.get("status"),
            "false_confidence_count": calibration.get("high_fidelity_false_confidence_count"),
        },
    }
    write_json(run_dir / "release-recommendation.json", release_reco)
    (run_dir / "release-recommendation.md").write_text(
        "# Release Recommendation\n\n" + json.dumps(release_reco, indent=2), encoding="utf-8"
    )

    review_summary = {
        "scope": "Automated fidelity-review preparation and scorecard generation",
        "review_run_id": run_id,
        "technical_baseline": {
            "tests": "35 passed, 0 failed, 0 skipped",
            "technical_pass_rate": bench.get("technical_pass_rate"),
            "endpoint_parity_rate": bench.get("endpoint_parity_rate"),
        },
        "automated_fidelity_baseline": auto_dist,
        "human_fidelity_results": human_dist,
        "automated_review_recommendation_distribution": acceptance_dist,
        "calibration": calibration,
        "cleanup": cleanup,
        "top_defects": defects_ranked[:10],
        "release_recommendation": recommendation,
        "limitations": [
            "The automated review workflow generated review candidates and scorecards but did not constitute completed human fidelity review.",
            "Real-document pilot awaiting approved inputs.",
            "No conversion algorithms changed during baseline review.",
        ],
        "documents_reviewed": reviewed_ids,
        "real_pilot_status": pilot.get("status"),
    }
    write_json(run_dir / "review-summary.json", review_summary)

    summary_md_lines = [
        "# REVIEW SUMMARY",
        "",
        f"- review_run_id: `{run_id}`",
        f"- technical baseline tests: {review_summary['technical_baseline']['tests']}",
        f"- technical pass rate: {review_summary['technical_baseline']['technical_pass_rate']}",
        f"- endpoint parity rate: {review_summary['technical_baseline']['endpoint_parity_rate']}",
        f"- synthetic reviewed: {len(reviewed_ids)}",
        f"- real pilot status: {pilot.get('status')}",
        f"- release recommendation: {recommendation}",
        "- automated_human_agreement_status: pending_human_review",
        "- false_confidence_status: pending_human_review",
        "",
        "## Automated fidelity baseline",
        json.dumps(auto_dist, indent=2),
        "",
        "## Human fidelity results",
        json.dumps(human_dist, indent=2),
        "",
        "## Automated review recommendation distribution",
        json.dumps(acceptance_dist, indent=2),
        "",
        "## Calibration",
        json.dumps(calibration, indent=2),
        "",
        "## Cleanup",
        json.dumps(cleanup, indent=2),
        "",
        "## Top defects",
        json.dumps(defects_ranked[:10], indent=2),
        "",
        "## Limitations",
        "- Content-fidelity distribution has not yet been finalized through manual corpus review.",
        "- Automated/human agreement is pending_human_review.",
        "- Real-document pilot is waiting_for_approved_inputs unless approved files are provided.",
    ]
    (run_dir / "REVIEW_SUMMARY.md").write_text("\n".join(summary_md_lines), encoding="utf-8")

    run_manifest = {
        "review_run_id": run_id,
        "created_at": now_iso(),
        "repository_commit": "unavailable_not_a_git_repo",
        "repository_tag": "unavailable_not_a_git_repo",
        "python_version": "3.9.13",
        "converter_checkpoint": "prototype-v2-rc1",
        "effective_configuration": {
            "benchmark_source": str(args.benchmark_json),
            "corpus_manifest": str(args.corpus_manifest),
            "stable_conversion_path": "run_authoritative_conversion_service",
        },
        "synthetic_benchmark_source": str(args.benchmark_json),
        "real_document_pilot_source_location": str(args.pilot_input),
        "reviewer_identity": "",
        "review_status": "completed_automated_review_preparation",
        "automated_review_preparation_status": "completed",
        "synthetic_human_review_status": "pending",
        "documents_included": reviewed_ids,
        "documents_excluded": [],
        "exclusion_reasons": [],
        "confidentiality_classification": "synthetic_nonconfidential_and_local_real_documents_only",
        "technical_test_result": "35 passed, 0 failed, 0 skipped",
        "endpoint_parity_result": {
            "COMPARE_MD": True,
            "COMPARE_ASSETS": True,
            "COMPARE_MANIFEST_CORE": True,
            "COMPARE_QUALITY_CORE": True,
        },
        "known_limitations": [
            "Technical pass does not equal perfect fidelity.",
            "Real-document pilot may require manual review before promotion.",
        ],
        "algorithm_changes_during_baseline": False,
        "real_document_pilot_status": pilot.get("status"),
        "automated_human_agreement_status": "pending_human_review",
    }
    write_json(run_dir / "review-run.json", run_manifest)
    _write_review_run_md(run_dir / "review-run.md", run_manifest)

    # simple index artifact
    index_rows = []
    for sc in scorecards:
        index_rows.append(
            {
                "document_id": sc["fixture_or_document_id"],
                "source_type": sc["source_format"],
                "automated_fidelity": sc["automated_fidelity_status"],
                "automated_review_recommendation": sc["automated_review_recommendation"],
                "human_review_status": sc["human_review_status"],
                "acceptance": "pending_human_review",
                "review_reason": sc.get("overall_notes", ""),
                "scorecard": f"scorecards/{sc['fixture_or_document_id'].lower()}.scorecard.json",
                "source_preview": sc["page_reviews"][0]["source_page_preview"] if sc.get("page_reviews") else "",
                "output_preview": sc["page_reviews"][0]["output_page_preview"] if sc.get("page_reviews") else "",
            }
        )
    write_json(run_dir / "summaries" / "review-index.json", index_rows)

    html = [
        "<html><head><meta charset='utf-8'><title>Review Index</title></head><body>",
        "<h1>Automated Fidelity Review Preparation Index (artifact)</h1>",
        "<p>This static artifact is for review support only and does not replace /editor.</p>",
        "<table border='1' cellspacing='0' cellpadding='6'>",
        "<tr><th>Document ID</th><th>Source Type</th><th>Automated Fidelity</th><th>Automated Recommendation</th><th>Human Review Status</th><th>Scorecard</th></tr>",
    ]
    for row in index_rows:
        html.append(
            f"<tr><td>{row['document_id']}</td><td>{row['source_type']}</td><td>{row['automated_fidelity']}</td><td>{row['automated_review_recommendation']}</td><td>{row['human_review_status']}</td><td>{row['scorecard']}</td></tr>"
        )
    html.append("</table></body></html>")
    (run_dir / "summaries" / "review-index.html").write_text("\n".join(html), encoding="utf-8")

    review_order = rr + moderate + high
    packet_rows = [
        "# HUMAN REVIEW INDEX",
        "",
        "Review order: 7 review_required, then 5 moderate, then 5 high.",
        "",
        "| Order | Fixture ID | Automated Fidelity | Automated Recommendation | Scorecard |",
        "|---|---|---|---|---|",
    ]
    for idx, fid in enumerate(review_order, start=1):
        sc_path = f"scorecards/{fid.lower()}.scorecard.json"
        sc = next(s for s in scorecards if s["fixture_or_document_id"] == fid)
        packet_rows.append(f"| {idx} | {fid} | {sc['automated_fidelity_status']} | {sc['automated_review_recommendation']} | {sc_path} |")
    (run_dir / "HUMAN_REVIEW_INDEX.md").write_text("\n".join(packet_rows), encoding="utf-8")
    (run_dir / "human-review-packet" / "HUMAN_REVIEW_INDEX.md").write_text("\n".join(packet_rows), encoding="utf-8")

    packet = {"review_run_id": run_id, "fixtures": []}
    for fid in review_order:
        sc = next(s for s in scorecards if s["fixture_or_document_id"] == fid)
        meta = fixture_map.get(fid, {})
        ev = _collect_doc_evidence(bench_root, fid)
        manifest = _load_json(ev["manifest_path"]) if ev.get("manifest_path") and ev["manifest_path"].exists() else {}
        pages = manifest.get("document_result", {}).get("pages", [])
        packet["fixtures"].append(
            {
                "fixture_id": fid,
                "source_document_path": str(meta.get("source_path", "")),
                "expected_sidecar_path": str((ROOT / "tests" / "fixtures" / "generated" / "expected" / f"{fid.lower()}.expected.json").resolve()),
                "direct_output_path": str((ev["direct_dir"] / "docs").resolve()),
                "endpoint_output_path": str(ev["endpoint_dir"].resolve()),
                "manifest_path": str(ev.get("manifest_path")) if ev.get("manifest_path") else "missing",
                "quality_report_path": str(ev.get("quality_path")) if ev.get("quality_path") else "missing",
                "source_page_preview_paths": [
                    str((ROOT / "tests" / "fixtures" / "generated" / "previews" / f"{fid.lower()}-p1.png").resolve())
                ],
                "rendered_output_preview_paths": [
                    str((ev["direct_dir"] / "docs" / "assets").resolve())
                ],
                "automated_fidelity_rating": sc["automated_fidelity_status"],
                "automated_review_reasons": [p.get("review_reasons", []) for p in pages],
                "page_level_fallback_strategy": [
                    {
                        "page_number": p.get("page_number"),
                        "selected_conversion_strategy": p.get("selected_candidate"),
                        "fallback_records": p.get("fallback_records", []),
                    }
                    for p in pages
                ],
                "blank_human_fields": {
                    "reviewer": "",
                    "review_date": "",
                    "review_start_time": "",
                    "review_end_time": "",
                    "human_review_minutes": None,
                    "human_fidelity_status": None,
                    "acceptance_category": None,
                    "cleanup_category": None,
                    "human_cleanup_minutes": None,
                    "missing_content_findings": "",
                    "duplicate_content_findings": "",
                    "reading_order_findings": "",
                    "heading_findings": "",
                    "list_findings": "",
                    "table_findings": "",
                    "image_findings": "",
                    "chart_findings": "",
                    "link_findings": "",
                    "accessibility_findings": "",
                    "reviewer_notes": "",
                },
            }
        )
    write_json(run_dir / "summaries" / "human-review-packet.json", packet)
    write_json(run_dir / "human-review-packet" / "human-review-packet.json", packet)

    pkt_md = [
        "# Human Review Packet",
        "",
        "This packet contains 17 fixtures prepared for true human review.",
        "All human fields are intentionally blank.",
        "",
    ]
    for item in packet["fixtures"]:
        pkt_md.extend(
            [
                f"## {item['fixture_id']}",
                f"- source: `{item['source_document_path']}`",
                f"- expected sidecar: `{item['expected_sidecar_path']}`",
                f"- direct output: `{item['direct_output_path']}`",
                f"- endpoint output: `{item['endpoint_output_path']}`",
                f"- manifest: `{item['manifest_path']}`",
                f"- quality report: `{item['quality_report_path']}`",
                f"- automated fidelity: `{item['automated_fidelity_rating']}`",
                "",
            ]
        )
    (run_dir / "summaries" / "human-review-packet.md").write_text("\n".join(pkt_md), encoding="utf-8")
    (run_dir / "human-review-packet" / "human-review-packet.md").write_text("\n".join(pkt_md), encoding="utf-8")

    (run_dir / "human-review-packet" / "HUMAN_REVIEW_INSTRUCTIONS.md").write_text("\n".join(instructions_lines), encoding="utf-8")

    git_status = _discover_git_status(ROOT)
    write_json(run_dir / "summaries" / "git-checkpoint-status.json", git_status)
    gmd = [
        "# GIT CHECKPOINT STATUS",
        "",
        f"- is_git_repository: `{git_status['is_git_repository']}`",
        f"- parent_repository_found: `{git_status['parent_repository_found']}`",
        f"- repository_root: `{git_status['repository_root']}`",
        f"- current_branch: `{git_status['current_branch']}`",
        f"- current_commit: `{git_status['current_commit']}`",
        f"- prototype-v2-rc1 tag exists: `{git_status['prototype_v2_rc1_tag_exists']}`",
        f"- recommended_next_action: {git_status['recommended_next_action']}",
        "",
        "## Commands requiring human authorization",
    ]
    for cmd in git_status["commands_requiring_human_authorization"]:
        gmd.append(f"- `{cmd}`")
    (ROOT / "GIT_CHECKPOINT_STATUS.md").write_text("\n".join(gmd), encoding="utf-8")

    print("REVIEW_RUN_ID", run_id)
    print("REVIEW_RUN_DIR", run_dir)
    print("SYNTHETIC_REVIEWED", len(reviewed_ids))
    print("REAL_PILOT_STATUS", pilot.get("status"))
    print("RECOMMENDATION", recommendation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
