from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from github_document_ops import (
    delete_published_document,
    normalize_site_path,
    process_incoming_documents,
    publish_markdown_to_mkdocs_site,
    update_published_index,
)


class GitHubDocumentOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="github-document-ops-"))
        self.incoming = self.tmp / "incoming"
        self.published = self.tmp / "published"
        self.diagnostics = self.tmp / "diagnostics"
        self.incoming.mkdir(parents=True)

    def test_normalize_site_path_rejects_empty_without_fallback(self) -> None:
        with self.assertRaisesRegex(ValueError, "Document path is required"):
            normalize_site_path("../", "")

    def test_process_incoming_text_publishes_and_removes_source(self) -> None:
        source = self.incoming / "Password Reset.txt"
        source.write_text("Reset the password from account settings.", encoding="utf-8")

        results = process_incoming_documents(
            incoming_dir=self.incoming,
            published_root=self.published,
            diagnostics_dir=self.diagnostics,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["site_path"], "password-reset")
        self.assertFalse(source.exists())
        published_markdown = self.published / "password-reset" / "index.md"
        self.assertTrue(published_markdown.exists())
        self.assertIn("Reset the password", published_markdown.read_text(encoding="utf-8"))
        index_text = (self.published / "index.md").read_text(encoding="utf-8")
        self.assertIn("password-reset/index.md", index_text)
        self.assertIn('data-site-path="password-reset"', index_text)
        summary = json.loads((self.diagnostics / "conversion-summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["processed"], 1)

    def test_process_incoming_rejects_duplicate_without_removing_source(self) -> None:
        source = self.incoming / "Existing.txt"
        source.write_text("New content", encoding="utf-8")
        existing = self.published / "existing"
        existing.mkdir(parents=True)
        (existing / "index.md").write_text("# Existing\n", encoding="utf-8")

        with self.assertRaisesRegex(FileExistsError, "already published"):
            process_incoming_documents(
                incoming_dir=self.incoming,
                published_root=self.published,
                diagnostics_dir=self.diagnostics,
            )

        self.assertTrue(source.exists())
        self.assertEqual((existing / "index.md").read_text(encoding="utf-8"), "# Existing\n")

    def test_delete_removes_only_normalized_contained_document(self) -> None:
        source_markdown = self.tmp / "sample.md"
        source_markdown.write_text("# Sample\n", encoding="utf-8")
        publish_markdown_to_mkdocs_site(
            source_markdown=source_markdown,
            source_assets_dir=None,
            docs_root=self.published,
            site_path="guides/sample",
        )

        result = delete_published_document(docs_root=self.published, site_path="guides/sample")
        update_published_index(self.published)

        self.assertEqual(result["status"], "deleted")
        self.assertFalse((self.published / "guides").exists())
        with self.assertRaisesRegex(ValueError, "Invalid document path"):
            delete_published_document(docs_root=self.published, site_path="../outside")

    def test_empty_incoming_is_successful_noop_with_summary(self) -> None:
        results = process_incoming_documents(
            incoming_dir=self.incoming,
            published_root=self.published,
            diagnostics_dir=self.diagnostics,
        )

        self.assertEqual(results, [])
        summary = json.loads((self.diagnostics / "conversion-summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["processed"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
