# REVIEW SUMMARY

- review_run_id: `review-20260731-042323`
- technical baseline tests: 35 passed, 0 failed, 0 skipped
- technical pass rate: 1.0
- endpoint parity rate: 1.0
- synthetic reviewed: 17
- real pilot status: waiting_for_approved_inputs
- release recommendation: approve_for_limited_pilot
- automated_human_agreement_status: pending_human_review
- false_confidence_status: pending_human_review

## Automated fidelity baseline
{
  "high": 13,
  "moderate": 10,
  "low": 0,
  "review_required": 7,
  "unknown": 0
}

## Human fidelity results
{
  "status": "pending_human_review",
  "high": null,
  "moderate": null,
  "low": null,
  "review_required": null
}

## Automated review recommendation distribution
{
  "pass": 5,
  "pass_with_cleanup": 5,
  "review_required": 7,
  "failed": 0
}

## Calibration
{
  "agreement_status": "pending_human_review",
  "sample_size": 17,
  "human_reviewed_sample_size": 0,
  "matrix": {},
  "exact_agreement_count": null,
  "exact_agreement_percent": null,
  "automated_overrating_count": null,
  "automated_underrating_count": null,
  "review_required_precision": null,
  "review_required_recall": null,
  "high_fidelity_precision": null,
  "high_fidelity_false_confidence_count": null,
  "false_confidence_status": "pending_human_review"
}

## Cleanup
{
  "status": "pending_human_review",
  "documents": 17,
  "average_human_review_time_minutes": null,
  "median_human_review_time_minutes": null,
  "average_human_cleanup_time_minutes": null,
  "median_human_cleanup_time_minutes": null,
  "human_cleanup_distribution": {
    "none": null,
    "minor": null,
    "moderate": null,
    "major": null,
    "complete_manual_rework": null,
    "not_measured": 1.0
  },
  "automated_review_recommendation_distribution": {
    "pass": 0.2941,
    "pass_with_cleanup": 0.2941,
    "review_required": 0.4118,
    "failed": 0.0
  }
}

## Top defects
[
  {
    "defect_id": "PDF-008-P1-FULLPAGE",
    "title": "Full-page fallback requires manual semantic review",
    "description": "Page output relies on full-page visual fallback instead of semantic extraction.",
    "defect_type": "unnecessary_full_page_fallback",
    "severity": "moderate",
    "frequency": 1,
    "affected_fixtures": [
      "PDF-008"
    ],
    "cleanup_burden_mentions": 1,
    "automated_detection_status": "detected",
    "current_fallback": "full_page_visual",
    "proposed_improvement": "Defer algorithm changes until post-baseline defect prioritization",
    "expected_benefit": "high",
    "regression_risk": "medium",
    "recommended_milestone": "post-baseline-prioritization"
  },
  {
    "defect_id": "PDF-008-OCR-UNAVAILABLE",
    "title": "OCR unavailable for page(s) flagged for OCR",
    "description": "OCR was recommended in conversion warnings but unavailable in environment.",
    "defect_type": "OCR_error",
    "severity": "moderate",
    "frequency": 1,
    "affected_fixtures": [
      "PDF-008"
    ],
    "cleanup_burden_mentions": 1,
    "automated_detection_status": "detected",
    "current_fallback": "visual_or_native_fallback",
    "proposed_improvement": "Environment/provider policy and post-baseline OCR tuning",
    "expected_benefit": "medium",
    "regression_risk": "low",
    "recommended_milestone": "post-baseline-prioritization"
  },
  {
    "defect_id": "PDF-011-P1-FULLPAGE",
    "title": "Full-page fallback requires manual semantic review",
    "description": "Page output relies on full-page visual fallback instead of semantic extraction.",
    "defect_type": "unnecessary_full_page_fallback",
    "severity": "moderate",
    "frequency": 1,
    "affected_fixtures": [
      "PDF-011"
    ],
    "cleanup_burden_mentions": 1,
    "automated_detection_status": "detected",
    "current_fallback": "full_page_visual",
    "proposed_improvement": "Defer algorithm changes until post-baseline defect prioritization",
    "expected_benefit": "high",
    "regression_risk": "medium",
    "recommended_milestone": "post-baseline-prioritization"
  },
  {
    "defect_id": "PDF-011-OCR-UNAVAILABLE",
    "title": "OCR unavailable for page(s) flagged for OCR",
    "description": "OCR was recommended in conversion warnings but unavailable in environment.",
    "defect_type": "OCR_error",
    "severity": "moderate",
    "frequency": 1,
    "affected_fixtures": [
      "PDF-011"
    ],
    "cleanup_burden_mentions": 1,
    "automated_detection_status": "detected",
    "current_fallback": "visual_or_native_fallback",
    "proposed_improvement": "Environment/provider policy and post-baseline OCR tuning",
    "expected_benefit": "medium",
    "regression_risk": "low",
    "recommended_milestone": "post-baseline-prioritization"
  },
  {
    "defect_id": "PDF-012-P2-FULLPAGE",
    "title": "Full-page fallback requires manual semantic review",
    "description": "Page output relies on full-page visual fallback instead of semantic extraction.",
    "defect_type": "unnecessary_full_page_fallback",
    "severity": "moderate",
    "frequency": 1,
    "affected_fixtures": [
      "PDF-012"
    ],
    "cleanup_burden_mentions": 1,
    "automated_detection_status": "detected",
    "current_fallback": "full_page_visual",
    "proposed_improvement": "Defer algorithm changes until post-baseline defect prioritization",
    "expected_benefit": "high",
    "regression_risk": "medium",
    "recommended_milestone": "post-baseline-prioritization"
  },
  {
    "defect_id": "PDF-012-OCR-UNAVAILABLE",
    "title": "OCR unavailable for page(s) flagged for OCR",
    "description": "OCR was recommended in conversion warnings but unavailable in environment.",
    "defect_type": "OCR_error",
    "severity": "moderate",
    "frequency": 1,
    "affected_fixtures": [
      "PDF-012"
    ],
    "cleanup_burden_mentions": 1,
    "automated_detection_status": "detected",
    "current_fallback": "visual_or_native_fallback",
    "proposed_improvement": "Environment/provider policy and post-baseline OCR tuning",
    "expected_benefit": "medium",
    "regression_risk": "low",
    "recommended_milestone": "post-baseline-prioritization"
  },
  {
    "defect_id": "PDF-018-P2-FULLPAGE",
    "title": "Full-page fallback requires manual semantic review",
    "description": "Page output relies on full-page visual fallback instead of semantic extraction.",
    "defect_type": "unnecessary_full_page_fallback",
    "severity": "moderate",
    "frequency": 1,
    "affected_fixtures": [
      "PDF-018"
    ],
    "cleanup_burden_mentions": 1,
    "automated_detection_status": "detected",
    "current_fallback": "full_page_visual",
    "proposed_improvement": "Defer algorithm changes until post-baseline defect prioritization",
    "expected_benefit": "high",
    "regression_risk": "medium",
    "recommended_milestone": "post-baseline-prioritization"
  },
  {
    "defect_id": "PDF-018-OCR-UNAVAILABLE",
    "title": "OCR unavailable for page(s) flagged for OCR",
    "description": "OCR was recommended in conversion warnings but unavailable in environment.",
    "defect_type": "OCR_error",
    "severity": "moderate",
    "frequency": 1,
    "affected_fixtures": [
      "PDF-018"
    ],
    "cleanup_burden_mentions": 1,
    "automated_detection_status": "detected",
    "current_fallback": "visual_or_native_fallback",
    "proposed_improvement": "Environment/provider policy and post-baseline OCR tuning",
    "expected_benefit": "medium",
    "regression_risk": "low",
    "recommended_milestone": "post-baseline-prioritization"
  },
  {
    "defect_id": "PDF-020-P2-TABLECROP",
    "title": "Visual table fallback may require semantic reconstruction",
    "description": "Table was represented visually; accessible table semantics may be incomplete.",
    "defect_type": "table_error",
    "severity": "moderate",
    "frequency": 1,
    "affected_fixtures": [
      "PDF-020"
    ],
    "cleanup_burden_mentions": 1,
    "automated_detection_status": "detected",
    "current_fallback": "targeted_table_crop",
    "proposed_improvement": "Post-baseline table strategy tuning",
    "expected_benefit": "medium",
    "regression_risk": "medium",
    "recommended_milestone": "post-baseline-prioritization"
  },
  {
    "defect_id": "PDF-020-P4-FULLPAGE",
    "title": "Full-page fallback requires manual semantic review",
    "description": "Page output relies on full-page visual fallback instead of semantic extraction.",
    "defect_type": "unnecessary_full_page_fallback",
    "severity": "moderate",
    "frequency": 1,
    "affected_fixtures": [
      "PDF-020"
    ],
    "cleanup_burden_mentions": 1,
    "automated_detection_status": "detected",
    "current_fallback": "full_page_visual",
    "proposed_improvement": "Defer algorithm changes until post-baseline defect prioritization",
    "expected_benefit": "high",
    "regression_risk": "medium",
    "recommended_milestone": "post-baseline-prioritization"
  }
]

## Limitations
- Content-fidelity distribution has not yet been finalized through manual corpus review.
- Automated/human agreement is pending_human_review.
- Real-document pilot is waiting_for_approved_inputs unless approved files are provided.