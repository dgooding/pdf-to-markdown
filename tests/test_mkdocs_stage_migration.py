from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mkdocs_stage_migration import migrate_markdown


class MkdocsStageMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mkdocs-stage-tests-"))
        self.docs_root = self.tmp / "docs"
        self.src_md = self.tmp / "sample.md"
        self.assets_src = self.tmp / "assets"
        self.assets_src.mkdir(parents=True, exist_ok=True)

        self.src_md.write_text("# T\n\n[Local](other.md)\n\n![img](assets/a.png)\n", encoding="utf-8")
        (self.assets_src / "a.png").write_bytes(b"fake")

    def test_stage_basic(self) -> None:
        res = migrate_markdown(
            source_markdown=self.src_md,
            source_assets_dir=self.assets_src,
            docs_root=self.docs_root,
            conflict_strategy="fail",
        )
        self.assertEqual(res.status, "migrated")
        out = Path(res.target_markdown)
        self.assertTrue(out.exists())
        text = out.read_text(encoding="utf-8")
        self.assertIn("(other/)", text)
        self.assertTrue((out.parent / "assets" / "a.png").exists())

    def test_stage_conflict_skip(self) -> None:
        first = migrate_markdown(self.src_md, self.assets_src, self.docs_root, "fail")
        self.assertEqual(first.status, "migrated")
        second = migrate_markdown(self.src_md, self.assets_src, self.docs_root, "skip")
        self.assertEqual(second.status, "skipped_conflict")


if __name__ == "__main__":
    unittest.main(verbosity=2)
