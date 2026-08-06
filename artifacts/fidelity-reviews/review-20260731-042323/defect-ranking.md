# Defect Ranking

{
  "top_defects": [
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
}