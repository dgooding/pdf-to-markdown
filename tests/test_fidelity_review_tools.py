from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fidelity_review_tools import (
    build_scorecard_schema,
    compute_calibration,
    compute_cleanup_metrics,
    detect_real_pilot_inputs,
    rank_defects,
    validate_scorecard,
)


class FidelityReviewToolsTests(unittest.TestCase):
    def test_schema_contains_required_sets(self) -> None:
        schema = build_scorecard_schema()
        self.assertIn("document_required_fields", schema)
        self.assertIn("page_required_fields", schema)
        self.assertIn("allowed_values", schema)

    def test_validate_scorecard_required_fields(self) -> None:
        scorecard = {
            "review_run_id": "r1",
            "fixture_or_document_id": "PDF-001",
            "source_filename": "f.pdf",
            "source_format": "pdf",
            "source_location_classification": "workspace_local_fixture",
            "synthetic_or_real": "synthetic",
            "confidentiality_classification": "synthetic_nonconfidential",
            "source_page_count": 1,
            "output_markdown_path": "out.md",
            "asset_directory": "assets",
            "manifest_path": "m.json",
            "quality_report_path": "q.json",
            "endpoint_package_path": "p.zip",
            "reviewer": "",
            "review_date": "2026-01-01",
            "human_review_status": "not_reviewed",
            "automated_technical_status": "passed",
            "automated_fidelity_status": "high",
            "automated_review_recommendation": "pass",
            "automated_artifact_processing_seconds": 0.25,
            "human_technical_status": "not_reviewed",
            "human_fidelity_status": None,
            "human_review_minutes": None,
            "human_cleanup_minutes": None,
            "human_cleanup_status": "not_measured",
            "acceptance_category": "pass",
            "cleanup_category": "none",
            "cleanup_minutes_measured_or_estimated": "not_measured",
            "overall_notes": "ok",
            "blocking_defect_count": 0,
            "nonblocking_defect_count": 0,
            "page_reviews": [
                {
                    "page_number": 1,
                    "source_page_preview": "a.png",
                    "output_page_preview": "b.png",
                    "selected_conversion_strategy": "native",
                    "native_extraction_used": True,
                    "ocr_used": False,
                    "semantic_table_used": False,
                    "visual_table_fallback_used": False,
                    "targeted_visual_fallback_used": False,
                    "full_page_fallback_used": False,
                    "semantic_coverage_rating": "correct",
                    "visual_coverage_rating": "correct",
                    "accessible_coverage_rating": "correct",
                    "reading_order_rating": "correct",
                    "heading_structure_rating": "correct",
                    "list_structure_rating": "correct",
                    "table_rating": "not_applicable",
                    "image_rating": "not_applicable",
                    "chart_rating": "not_applicable",
                    "diagram_rating": "not_applicable",
                    "link_rating": "correct",
                    "unicode_rating": "correct",
                    "code_formatting_rating": "not_applicable",
                    "header_footer_rating": "correct",
                    "duplicate_content_rating": "correct",
                    "missing_content_rating": "correct",
                    "page_acceptance_result": "pass",
                    "page_review_reasons": [],
                    "page_defect_ids": [],
                }
            ],
            "defects": [],
        }
        errs = validate_scorecard(scorecard)
        self.assertEqual(errs, [])

    def test_calibration_computation(self) -> None:
        cards = [
            {"automated_fidelity_status": "high", "human_fidelity_status": None, "human_review_status": "not_reviewed"},
            {"automated_fidelity_status": "moderate", "human_fidelity_status": None, "human_review_status": "not_reviewed"},
            {"automated_fidelity_status": "review_required", "human_fidelity_status": None, "human_review_status": "not_reviewed"},
        ]
        c = compute_calibration(cards)
        self.assertEqual(c["sample_size"], 3)
        self.assertEqual(c["agreement_status"], "pending_human_review")
        self.assertEqual(c["high_fidelity_false_confidence_count"], None)

    def test_cleanup_measurements(self) -> None:
        cards = [
            {"human_review_minutes": None, "human_cleanup_minutes": None, "cleanup_category": "none"},
            {"human_review_minutes": None, "human_cleanup_minutes": None, "cleanup_category": "major"},
        ]
        m = compute_cleanup_metrics(cards)
        self.assertEqual(m["status"], "pending_human_review")
        self.assertIsNone(m["average_human_review_time_minutes"])
        self.assertEqual(m["human_cleanup_distribution"]["not_measured"], 1.0)

    def test_human_defaults_enforced(self) -> None:
        scorecard = {
            "review_run_id": "r1",
            "fixture_or_document_id": "PDF-001",
            "source_filename": "f.pdf",
            "source_format": "pdf",
            "source_location_classification": "workspace_local_fixture",
            "synthetic_or_real": "synthetic",
            "confidentiality_classification": "synthetic_nonconfidential",
            "source_page_count": 1,
            "output_markdown_path": "out.md",
            "asset_directory": "assets",
            "manifest_path": "m.json",
            "quality_report_path": "q.json",
            "endpoint_package_path": "p.zip",
            "reviewer": "",
            "review_date": "",
            "human_review_status": "not_reviewed",
            "automated_technical_status": "passed",
            "automated_fidelity_status": "high",
            "automated_review_recommendation": "pass",
            "automated_artifact_processing_seconds": 0.15,
            "human_technical_status": "not_reviewed",
            "human_fidelity_status": None,
            "human_review_minutes": 1.0,
            "human_cleanup_minutes": None,
            "human_cleanup_status": "not_measured",
            "acceptance_category": "pass",
            "cleanup_category": "none",
            "cleanup_minutes_measured_or_estimated": "not_measured",
            "overall_notes": "ok",
            "blocking_defect_count": 0,
            "nonblocking_defect_count": 0,
            "page_reviews": [
                {
                    "page_number": 1,
                    "source_page_preview": "a.png",
                    "output_page_preview": "b.png",
                    "selected_conversion_strategy": "native",
                    "native_extraction_used": True,
                    "ocr_used": False,
                    "semantic_table_used": False,
                    "visual_table_fallback_used": False,
                    "targeted_visual_fallback_used": False,
                    "full_page_fallback_used": False,
                    "semantic_coverage_rating": "correct",
                    "visual_coverage_rating": "correct",
                    "accessible_coverage_rating": "correct",
                    "reading_order_rating": "correct",
                    "heading_structure_rating": "correct",
                    "list_structure_rating": "correct",
                    "table_rating": "not_applicable",
                    "image_rating": "not_applicable",
                    "chart_rating": "not_applicable",
                    "diagram_rating": "not_applicable",
                    "link_rating": "correct",
                    "unicode_rating": "correct",
                    "code_formatting_rating": "not_applicable",
                    "header_footer_rating": "correct",
                    "duplicate_content_rating": "correct",
                    "missing_content_rating": "correct",
                    "page_acceptance_result": "pass",
                    "page_review_reasons": [],
                    "page_defect_ids": [],
                }
            ],
            "defects": [],
        }
        errs = validate_scorecard(scorecard)
        self.assertIn("human_review_minutes_must_be_null_when_not_reviewed", errs)

    def test_defect_ranking(self) -> None:
        cards = [
            {
                "fixture_or_document_id": "PDF-001",
                "cleanup_category": "major",
                "defects": [
                    {
                        "defect_id": "D1",
                        "title": "x",
                        "description": "y",
                        "defect_type": "table_error",
                        "severity": "major",
                    }
                ],
            }
        ]
        ranked = rank_defects(cards)
        self.assertEqual(ranked[0]["defect_id"], "D1")

    def test_missing_real_pilot_folder_waiting(self) -> None:
        temp = Path(tempfile.mkdtemp(prefix="pilot-test-")) / "pilot_input"
        res = detect_real_pilot_inputs(temp)
        self.assertEqual(res["status"], "waiting_for_approved_inputs")
        self.assertTrue((temp / "README.md").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
