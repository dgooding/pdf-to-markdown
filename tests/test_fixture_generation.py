from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import fitz
from docx import Document

from generate_test_corpus import CorpusGenerator, validate_generated_corpus


class FixtureGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="fixture-gen-tests-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_gen(self, seed: int, rel: str) -> Path:
        out = self.temp_dir / rel
        gen = CorpusGenerator(out_dir=out, seed=seed, groups=["docx", "pdf"], cleanup=True)
        manifest = gen.run()
        self.assertTrue(manifest.exists())
        return manifest

    def test_generation_is_deterministic_for_same_seed(self) -> None:
        m1 = self._run_gen(42, "run_a")
        m2 = self._run_gen(42, "run_b")

        j1 = json.loads(m1.read_text(encoding="utf-8"))
        j2 = json.loads(m2.read_text(encoding="utf-8"))

        self.assertEqual(j1["seed"], j2["seed"])
        self.assertEqual(j1["total_fixtures"], j2["total_fixtures"])

        # Binary hashes can differ due container metadata (e.g. DOCX/PDF internal timestamps),
        # so determinism is validated on semantic fixture structure and expected sidecars.
        f1 = sorted((f["fixture_id"], f["filename"], f["source_format"], f.get("page_count")) for f in j1["fixtures"])
        f2 = sorted((f["fixture_id"], f["filename"], f["source_format"], f.get("page_count")) for f in j2["fixtures"])
        self.assertEqual(f1, f2)

        by_id_1 = {f["fixture_id"]: f for f in j1["fixtures"]}
        by_id_2 = {f["fixture_id"]: f for f in j2["fixtures"]}
        self.assertEqual(set(by_id_1.keys()), set(by_id_2.keys()))

        for fid in by_id_1:
            s1 = m1.parent / by_id_1[fid]["expected_sidecar"]
            s2 = m2.parent / by_id_2[fid]["expected_sidecar"]
            p1 = json.loads(s1.read_text(encoding="utf-8"))
            p2 = json.loads(s2.read_text(encoding="utf-8"))
            self.assertEqual(p1, p2, f"Expected sidecar mismatch for {fid}")

    def test_generation_changes_values_for_different_seed(self) -> None:
        m1 = self._run_gen(101, "seed_101")
        m2 = self._run_gen(202, "seed_202")

        j1 = json.loads(m1.read_text(encoding="utf-8"))
        j2 = json.loads(m2.read_text(encoding="utf-8"))

        self.assertEqual(j1["total_fixtures"], j2["total_fixtures"])
        self.assertNotEqual(j1["seed"], j2["seed"])

        # structure must remain stable across seeds
        ids1 = sorted(f["fixture_id"] for f in j1["fixtures"])
        ids2 = sorted(f["fixture_id"] for f in j2["fixtures"])
        self.assertEqual(ids1, ids2)

        hashes1 = sorted(f["sha256"] for f in j1["fixtures"])
        hashes2 = sorted(f["sha256"] for f in j2["fixtures"])
        self.assertNotEqual(hashes1, hashes2)

    def test_generated_docx_and_pdf_are_openable_and_validated(self) -> None:
        manifest = self._run_gen(20260730, "validate")
        payload = json.loads(manifest.read_text(encoding="utf-8"))

        # basic integrity/open checks for all generated sources
        for item in payload["fixtures"]:
            src = manifest.parent / item["source_path"]
            self.assertTrue(src.exists(), src)
            self.assertTrue((manifest.parent / item["expected_sidecar"]).exists())
            if src.suffix.lower() == ".docx":
                doc = Document(src)
                self.assertGreater(len(doc.paragraphs), 0)
            elif src.suffix.lower() == ".pdf":
                pdf = fitz.open(src)
                self.assertGreaterEqual(pdf.page_count, 1)
                pdf.close()

        report = validate_generated_corpus(manifest)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["total_fixtures"], payload["total_fixtures"])
        self.assertEqual(report["expected_sidecars_present"], payload["total_fixtures"])
        self.assertEqual(len(report["filename_issues"]), 0)
        self.assertEqual(len(report["missing_files"]), 0)

    def test_no_confidential_patterns_in_generated_sidecars(self) -> None:
        manifest = self._run_gen(77, "pii_check")
        payload = json.loads(manifest.read_text(encoding="utf-8"))

        banned_tokens = [
            "@gmail.com",
            "@yahoo.com",
            "@hotmail.com",
            "password",
            "secret",
            "api_key",
            "ssn",
        ]

        for item in payload["fixtures"]:
            sidecar = manifest.parent / item["expected_sidecar"]
            text = sidecar.read_text(encoding="utf-8").lower()
            for token in banned_tokens:
                self.assertNotIn(token, text, f"Found banned token {token} in {sidecar}")


if __name__ == "__main__":
    unittest.main()
