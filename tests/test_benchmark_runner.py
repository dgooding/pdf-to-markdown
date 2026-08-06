from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from benchmark_generated_corpus import _normalize_manifest_core, _normalize_quality_core


class BenchmarkRunnerTests(unittest.TestCase):
    def test_normalize_manifest_core_keeps_required_fields(self) -> None:
        payload = {
            "technical_status": "passed",
            "fidelity_status": "moderate",
            "validation": {"passed": True},
            "effective_configuration": {"pdf_mode": "hybrid"},
            "document_result": {
                "pages": [
                    {
                        "page_number": 1,
                        "selected_candidate": "p1-hybrid",
                        "technical_status": "passed",
                        "fidelity_status": "moderate",
                        "volatile": "ignore-me",
                    }
                ]
            },
        }
        core = _normalize_manifest_core(payload)
        self.assertEqual(core["technical_status"], "passed")
        self.assertEqual(core["fidelity_status"], "moderate")
        self.assertEqual(core["validation"], {"passed": True})
        self.assertEqual(core["effective_configuration"], {"pdf_mode": "hybrid"})
        self.assertEqual(len(core["pages"]), 1)
        self.assertEqual(core["pages"][0]["selected_candidate"], "p1-hybrid")

    def test_normalize_quality_core_keeps_required_fields(self) -> None:
        payload = {
            "technical_status": "passed",
            "fidelity_status": "review_required",
            "effective_configuration": {"pdf_mode": "hybrid"},
            "page_summaries": [
                {
                    "page_number": 2,
                    "selected_candidate": "p2-native",
                    "technical_status": "passed",
                    "fidelity_status": "low",
                    "runtime": 1.23,
                }
            ],
        }
        core = _normalize_quality_core(payload)
        self.assertEqual(core["technical_status"], "passed")
        self.assertEqual(core["fidelity_status"], "review_required")
        self.assertEqual(core["effective_configuration"], {"pdf_mode": "hybrid"})
        self.assertEqual(core["pages"][0]["page_number"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
