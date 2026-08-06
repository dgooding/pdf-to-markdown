from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DOC_ACCEPTANCE_VALUES = {"pass", "pass_with_cleanup", "review_required", "failed"}
DOC_CLEANUP_VALUES = {"none", "minor", "moderate", "major", "complete_manual_rework", "not_measured"}
HUMAN_FIDELITY_VALUES = {"high", "moderate", "low", "review_required"}
HUMAN_REVIEW_STATUS_VALUES = {"not_reviewed", "in_progress", "completed"}
AGREEMENT_STATUS_VALUES = {"pending_human_review", "calculated"}
PAGE_RATING_VALUES = {
    "correct",
    "acceptable_with_minor_difference",
    "cleanup_required",
    "materially_incorrect",
    "not_applicable",
    "unable_to_verify",
}
DEFECT_SEVERITY_VALUES = {"informational", "minor", "moderate", "major", "critical"}
DEFECT_TYPE_VALUES = {
    "missing_text",
    "duplicated_text",
    "incorrect_reading_order",
    "heading_error",
    "list_error",
    "table_error",
    "image_missing",
    "image_misplaced",
    "cross_page_asset_error",
    "chart_error",
    "chart_label_leakage",
    "diagram_error",
    "link_error",
    "broken_asset_reference",
    "OCR_error",
    "Unicode_error",
    "code_formatting_error",
    "header_footer_pollution",
    "page_rotation_error",
    "excessive_visual_fallback",
    "unnecessary_full_page_fallback",
    "inaccessible_visual_content",
    "Markdown_rendering_error",
    "MkDocs_build_error",
    "packaging_error",
    "unsupported_content",
    "performance_issue",
    "other",
}


REQUIRED_DOCUMENT_FIELDS = {
    "review_run_id",
    "fixture_or_document_id",
    "source_filename",
    "source_format",
    "source_location_classification",
    "synthetic_or_real",
    "confidentiality_classification",
    "source_page_count",
    "output_markdown_path",
    "asset_directory",
    "manifest_path",
    "quality_report_path",
    "endpoint_package_path",
    "reviewer",
    "review_date",
    "human_review_status",
    "automated_technical_status",
    "automated_fidelity_status",
    "automated_review_recommendation",
    "automated_artifact_processing_seconds",
    "human_technical_status",
    "human_fidelity_status",
    "human_review_minutes",
    "human_cleanup_minutes",
    "human_cleanup_status",
    "acceptance_category",
    "cleanup_category",
    "cleanup_minutes_measured_or_estimated",
    "overall_notes",
    "blocking_defect_count",
    "nonblocking_defect_count",
    "page_reviews",
    "defects",
}


REQUIRED_PAGE_FIELDS = {
    "page_number",
    "source_page_preview",
    "output_page_preview",
    "selected_conversion_strategy",
    "native_extraction_used",
    "ocr_used",
    "semantic_table_used",
    "visual_table_fallback_used",
    "targeted_visual_fallback_used",
    "full_page_fallback_used",
    "semantic_coverage_rating",
    "visual_coverage_rating",
    "accessible_coverage_rating",
    "reading_order_rating",
    "heading_structure_rating",
    "list_structure_rating",
    "table_rating",
    "image_rating",
    "chart_rating",
    "diagram_rating",
    "link_rating",
    "unicode_rating",
    "code_formatting_rating",
    "header_footer_rating",
    "duplicate_content_rating",
    "missing_content_rating",
    "page_acceptance_result",
    "page_review_reasons",
    "page_defect_ids",
}


def build_scorecard_schema() -> dict[str, Any]:
    return {
        "document_required_fields": sorted(REQUIRED_DOCUMENT_FIELDS),
        "page_required_fields": sorted(REQUIRED_PAGE_FIELDS),
        "allowed_values": {
            "human_fidelity": sorted(HUMAN_FIDELITY_VALUES),
            "human_review_status": sorted(HUMAN_REVIEW_STATUS_VALUES),
            "agreement_status": sorted(AGREEMENT_STATUS_VALUES),
            "acceptance_category": sorted(DOC_ACCEPTANCE_VALUES),
            "cleanup_category": sorted(DOC_CLEANUP_VALUES),
            "page_rating": sorted(PAGE_RATING_VALUES),
            "defect_severity": sorted(DEFECT_SEVERITY_VALUES),
            "defect_type": sorted(DEFECT_TYPE_VALUES),
        },
    }


def redact_metadata(value: str) -> str:
    # Keep IDs and extensions, collapse suspicious path components.
    value = value.replace("\\", "/")
    parts = [p for p in value.split("/") if p and p not in {".", ".."}]
    if not parts:
        return "unknown"
    return parts[-1]


def validate_scorecard(scorecard: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_DOCUMENT_FIELDS - set(scorecard.keys())
    if missing:
        errors.append(f"missing_document_fields:{sorted(missing)}")

    if scorecard.get("human_review_status") not in HUMAN_REVIEW_STATUS_VALUES:
        errors.append("invalid_human_review_status")

    hf = scorecard.get("human_fidelity_status")
    if hf is not None and hf != "not_reviewed" and hf not in HUMAN_FIDELITY_VALUES:
        errors.append("invalid_human_fidelity_status")
    if scorecard.get("acceptance_category") not in DOC_ACCEPTANCE_VALUES:
        errors.append("invalid_acceptance_category")
    if scorecard.get("cleanup_category") not in DOC_CLEANUP_VALUES:
        errors.append("invalid_cleanup_category")
    if scorecard.get("human_cleanup_status") not in {"not_measured", "measured"}:
        errors.append("invalid_human_cleanup_status")

    if scorecard.get("human_review_status") == "not_reviewed":
        if scorecard.get("human_review_minutes") is not None:
            errors.append("human_review_minutes_must_be_null_when_not_reviewed")
        if scorecard.get("human_cleanup_minutes") is not None:
            errors.append("human_cleanup_minutes_must_be_null_when_not_reviewed")
        if scorecard.get("human_cleanup_status") != "not_measured":
            errors.append("human_cleanup_status_must_be_not_measured_when_not_reviewed")

    pages = scorecard.get("page_reviews", []) or []
    for idx, page in enumerate(pages):
        pmiss = REQUIRED_PAGE_FIELDS - set(page.keys())
        if pmiss:
            errors.append(f"page_{idx}_missing_fields:{sorted(pmiss)}")
        for key in [
            "semantic_coverage_rating",
            "visual_coverage_rating",
            "accessible_coverage_rating",
            "reading_order_rating",
            "heading_structure_rating",
            "list_structure_rating",
            "table_rating",
            "image_rating",
            "chart_rating",
            "diagram_rating",
            "link_rating",
            "unicode_rating",
            "code_formatting_rating",
            "header_footer_rating",
            "duplicate_content_rating",
            "missing_content_rating",
        ]:
            if page.get(key) not in PAGE_RATING_VALUES:
                errors.append(f"page_{idx}_invalid_rating_{key}")
    return errors


def _fidelity_rank(value: str) -> int:
    order = {"review_required": 0, "low": 1, "moderate": 2, "high": 3}
    return order.get(value, -1)


def compute_calibration(scorecards: list[dict[str, Any]]) -> dict[str, Any]:
    if not any(sc.get("human_review_status") == "completed" for sc in scorecards):
        return {
            "agreement_status": "pending_human_review",
            "sample_size": len(scorecards),
            "human_reviewed_sample_size": 0,
            "matrix": {},
            "exact_agreement_count": None,
            "exact_agreement_percent": None,
            "automated_overrating_count": None,
            "automated_underrating_count": None,
            "review_required_precision": None,
            "review_required_recall": None,
            "high_fidelity_precision": None,
            "high_fidelity_false_confidence_count": None,
            "false_confidence_status": "pending_human_review",
        }

    matrix: dict[str, int] = {}
    exact = 0
    over = 0
    under = 0
    rr_tp = rr_fp = rr_fn = 0
    hi_tp = hi_fp = hi_fn = 0

    for sc in scorecards:
        auto = str(sc.get("automated_fidelity_status", "unknown"))
        if sc.get("human_review_status") != "completed":
            continue
        human = str(sc.get("human_fidelity_status", "review_required"))
        key = f"{auto}->{human}"
        matrix[key] = matrix.get(key, 0) + 1
        if auto == human:
            exact += 1

        ar = _fidelity_rank(auto)
        hr = _fidelity_rank(human)
        if ar > hr:
            over += 1
        elif ar < hr:
            under += 1

        auto_rr = auto == "review_required"
        human_rr = human == "review_required"
        if auto_rr and human_rr:
            rr_tp += 1
        elif auto_rr and not human_rr:
            rr_fp += 1
        elif (not auto_rr) and human_rr:
            rr_fn += 1

        auto_hi = auto == "high"
        human_hi = human == "high"
        if auto_hi and human_hi:
            hi_tp += 1
        elif auto_hi and not human_hi:
            hi_fp += 1
        elif (not auto_hi) and human_hi:
            hi_fn += 1

    total = sum(1 for sc in scorecards if sc.get("human_review_status") == "completed")
    agreement_pct = (exact / total) if total else 0.0
    rr_precision = (rr_tp / (rr_tp + rr_fp)) if (rr_tp + rr_fp) else 0.0
    rr_recall = (rr_tp / (rr_tp + rr_fn)) if (rr_tp + rr_fn) else 0.0
    hi_precision = (hi_tp / (hi_tp + hi_fp)) if (hi_tp + hi_fp) else 0.0
    false_confidence = sum(1 for sc in scorecards if sc.get("automated_fidelity_status") in {"high", "moderate"} and sc.get("human_fidelity_status") == "review_required")

    return {
        "agreement_status": "calculated",
        "sample_size": total,
        "human_reviewed_sample_size": total,
        "matrix": matrix,
        "exact_agreement_count": exact,
        "exact_agreement_percent": round(agreement_pct, 4),
        "automated_overrating_count": over,
        "automated_underrating_count": under,
        "review_required_precision": round(rr_precision, 4),
        "review_required_recall": round(rr_recall, 4),
        "high_fidelity_precision": round(hi_precision, 4),
        "high_fidelity_false_confidence_count": false_confidence,
        "false_confidence_status": "calculated",
    }


def compute_cleanup_metrics(scorecards: list[dict[str, Any]]) -> dict[str, Any]:
    review_times = [float(sc["human_review_minutes"]) for sc in scorecards if isinstance(sc.get("human_review_minutes"), (int, float))]
    cleanup_times = [float(sc["human_cleanup_minutes"]) for sc in scorecards if isinstance(sc.get("human_cleanup_minutes"), (int, float))]

    def pct(cat: str) -> float:
        total = len(scorecards) or 1
        return round(sum(1 for s in scorecards if s.get("cleanup_category") == cat) / total, 4)

    def reco_pct(cat: str) -> float:
        total = len(scorecards) or 1
        return round(sum(1 for s in scorecards if s.get("acceptance_category") == cat) / total, 4)

    if not review_times and not cleanup_times:
        return {
            "status": "pending_human_review",
            "documents": len(scorecards),
            "average_human_review_time_minutes": None,
            "median_human_review_time_minutes": None,
            "average_human_cleanup_time_minutes": None,
            "median_human_cleanup_time_minutes": None,
            "human_cleanup_distribution": {
                "none": None,
                "minor": None,
                "moderate": None,
                "major": None,
                "complete_manual_rework": None,
                "not_measured": 1.0,
            },
            "automated_review_recommendation_distribution": {
                "pass": reco_pct("pass"),
                "pass_with_cleanup": reco_pct("pass_with_cleanup"),
                "review_required": reco_pct("review_required"),
                "failed": reco_pct("failed"),
            },
        }

    return {
        "status": "calculated",
        "documents": len(scorecards),
        "average_human_review_time_minutes": round(sum(review_times) / len(review_times), 4) if review_times else None,
        "median_human_review_time_minutes": round(statistics.median(review_times), 4) if review_times else None,
        "average_human_cleanup_time_minutes": round(sum(cleanup_times) / len(cleanup_times), 4) if cleanup_times else None,
        "median_human_cleanup_time_minutes": round(statistics.median(cleanup_times), 4) if cleanup_times else None,
        "human_cleanup_distribution": {
            "none": pct("none"),
            "minor": pct("minor"),
            "moderate": pct("moderate"),
            "major": pct("major"),
            "complete_manual_rework": pct("complete_manual_rework"),
            "not_measured": pct("not_measured"),
        },
        "automated_review_recommendation_distribution": {
            "pass": reco_pct("pass"),
            "pass_with_cleanup": reco_pct("pass_with_cleanup"),
            "review_required": reco_pct("review_required"),
            "failed": reco_pct("failed"),
        },
    }


def rank_defects(scorecards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    sev_weight = {"critical": 5, "major": 4, "moderate": 3, "minor": 2, "informational": 1}

    for sc in scorecards:
        for defect in sc.get("defects", []) or []:
            did = defect.get("defect_id") or defect.get("title") or "unknown"
            row = buckets.setdefault(
                did,
                {
                    "defect_id": did,
                    "title": defect.get("title", did),
                    "description": defect.get("description", ""),
                    "defect_type": defect.get("defect_type", "other"),
                    "severity": defect.get("severity", "minor"),
                    "frequency": 0,
                    "affected_fixtures": set(),
                    "cleanup_burden_mentions": 0,
                    "automated_detection_status": defect.get("automated_detection_status", "partial"),
                    "current_fallback": defect.get("current_fallback", "n/a"),
                    "proposed_improvement": defect.get("proposed_improvement", "defer"),
                    "expected_benefit": defect.get("expected_benefit", "medium"),
                    "regression_risk": defect.get("regression_risk", "medium"),
                    "recommended_milestone": defect.get("recommended_milestone", "post-baseline-prioritization"),
                    "_score": 0,
                },
            )
            row["frequency"] += 1
            row["affected_fixtures"].add(sc.get("fixture_or_document_id"))
            if sc.get("cleanup_category") in {"moderate", "major", "complete_manual_rework"}:
                row["cleanup_burden_mentions"] += 1
            row["_score"] += sev_weight.get(row["severity"], 1)

    ranked = list(buckets.values())
    ranked.sort(key=lambda d: (d["_score"], d["frequency"], d["cleanup_burden_mentions"]), reverse=True)
    for r in ranked:
        r["affected_fixtures"] = sorted(r["affected_fixtures"])
        r.pop("_score", None)
    return ranked


def detect_real_pilot_inputs(pilot_input_dir: Path) -> dict[str, Any]:
    if not pilot_input_dir.exists():
        pilot_input_dir.mkdir(parents=True, exist_ok=True)
        (pilot_input_dir / "README.md").write_text(
            "# pilot_input\n\nPlace approved real pilot documents here for local-only review.\nDefault policy: approved_for_commit = false.\n",
            encoding="utf-8",
        )
        return {"status": "waiting_for_approved_inputs", "documents": []}

    allowed_input_ext = {".pdf", ".docx", ".md", ".txt"}
    excluded_names = {"readme.md", "pilot_inventory_template.json", "pilot_inventory.json"}
    docs = [
        p
        for p in pilot_input_dir.iterdir()
        if p.is_file()
        and p.name.lower() not in excluded_names
        and p.suffix.lower() in allowed_input_ext
    ]
    if not docs:
        readme = pilot_input_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                "# pilot_input\n\nPlace approved real pilot documents here for local-only review.\nDefault policy: approved_for_commit = false.\n",
                encoding="utf-8",
            )
        return {"status": "waiting_for_approved_inputs", "documents": []}

    inventory = []
    for p in sorted(docs):
        inventory.append(
            {
                "pilot_id": p.stem,
                "source_filename": p.name,
                "file_type": p.suffix.lower().lstrip("."),
                "file_size": p.stat().st_size,
                "feature_categories": [],
                "confidentiality_classification": "local_only",
                "approved_for_local_processing": True,
                "approved_for_artifact_preview": False,
                "approved_for_commit": False,
                "expected_review_sensitivity": "unknown",
                "conversion_status": "pending",
                "review_status": "pending",
            }
        )
    return {"status": "ready", "documents": inventory}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
