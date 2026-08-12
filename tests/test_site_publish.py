from __future__ import annotations

import asyncio
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

import app as app_module

from app import (
    _EDITOR_HTML,
    delete_published_document,
    MKDOCS_CONFIG_FILE,
    MKDOCS_DOCS_DIR,
    normalize_site_path,
    publish_markdown_to_mkdocs_site,
    render_markdown_preview,
    update_published_index,
)


class SitePublishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="site-publish-tests-"))
        self.docs_root = self.tmp / "published"
        self.source_md = self.tmp / "sample.md"
        self.source_assets = self.tmp / "assets"
        self.source_assets.mkdir(parents=True, exist_ok=True)
        self.source_md.write_text("# Reset Password\n\n![img](assets/reset.png)\n", encoding="utf-8")
        (self.source_assets / "reset.png").write_bytes(b"png")

    def test_normalize_site_path_slugifies_segments(self) -> None:
        self.assertEqual(
            normalize_site_path("Troubleshooting/Password Reset.md", "fallback-name"),
            "troubleshooting/password-reset",
        )

    def test_publish_markdown_to_mkdocs_site_copies_content(self) -> None:
        result = publish_markdown_to_mkdocs_site(
            source_markdown=self.source_md,
            source_assets_dir=self.source_assets,
            docs_root=self.docs_root,
            site_path="Troubleshooting/Password Reset",
        )

        target_md = Path(result["target_markdown"])
        self.assertTrue(target_md.exists())
        self.assertIn("/docs/published/troubleshooting/password-reset/", result["published_url"])
        self.assertEqual(result["folder"], "troubleshooting")
        self.assertEqual(result["document_name"], "password-reset")
        self.assertTrue((target_md.parent / "assets" / "reset.png").exists())

    def test_publish_rejects_existing_document(self) -> None:
        publish_markdown_to_mkdocs_site(
            source_markdown=self.source_md,
            source_assets_dir=self.source_assets,
            docs_root=self.docs_root,
            site_path="reset-password",
        )

        with self.assertRaisesRegex(FileExistsError, "already published"):
            publish_markdown_to_mkdocs_site(
                source_markdown=self.source_md,
                source_assets_dir=self.source_assets,
                docs_root=self.docs_root,
                site_path="reset-password",
            )

    def test_delete_published_document_removes_document_and_empty_parent(self) -> None:
        publish_markdown_to_mkdocs_site(
            source_markdown=self.source_md,
            source_assets_dir=self.source_assets,
            docs_root=self.docs_root,
            site_path="guides/reset-password",
        )

        result = delete_published_document(
            docs_root=self.docs_root,
            site_path="guides/reset-password",
        )

        self.assertEqual(result["status"], "deleted")
        self.assertFalse((self.docs_root / "guides" / "reset-password").exists())
        self.assertFalse((self.docs_root / "guides").exists())

    def test_delete_published_document_rejects_unsafe_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid document path"):
            delete_published_document(docs_root=self.docs_root, site_path="../reset-password")

    def test_delete_endpoint_requires_publish_secret(self) -> None:
        publish_markdown_to_mkdocs_site(
            source_markdown=self.source_md,
            source_assets_dir=self.source_assets,
            docs_root=self.docs_root,
            site_path="reset-password",
        )

        with (
            patch.object(app_module, "_PUBLISH_SECRET", "required-secret"),
            patch.object(app_module, "PUBLISHED_DOCS_DIR", self.docs_root),
            patch.object(app_module, "build_itsd_site"),
        ):
            with self.assertRaises(HTTPException) as denied:
                asyncio.run(
                    app_module.delete_from_site(
                        site_path="reset-password",
                        publish_secret="wrong",
                    )
                )
            self.assertEqual(denied.exception.status_code, 403)
            self.assertTrue((self.docs_root / "reset-password" / "index.md").exists())

            deleted = asyncio.run(
                app_module.delete_from_site(
                    site_path="reset-password",
                    publish_secret="required-secret",
                )
            )
            self.assertEqual(deleted.status_code, 200)
            self.assertIn(b'"status":"deleted"', deleted.body)

    def test_publish_transaction_rolls_back_when_build_fails(self) -> None:
        with (
            patch.object(app_module, "PUBLISHED_DOCS_DIR", self.docs_root),
            patch.object(app_module, "build_itsd_site", side_effect=RuntimeError("build failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "build failed"):
                app_module.run_site_mutation_transaction(
                    lambda: publish_markdown_to_mkdocs_site(
                        source_markdown=self.source_md,
                        source_assets_dir=self.source_assets,
                        docs_root=self.docs_root,
                        site_path="rollback-publish",
                    )
                )
        self.assertFalse((self.docs_root / "rollback-publish").exists())

    def test_delete_transaction_rolls_back_when_build_fails(self) -> None:
        publish_markdown_to_mkdocs_site(
            source_markdown=self.source_md,
            source_assets_dir=self.source_assets,
            docs_root=self.docs_root,
            site_path="rollback-delete",
        )
        with (
            patch.object(app_module, "PUBLISHED_DOCS_DIR", self.docs_root),
            patch.object(app_module, "build_itsd_site", side_effect=RuntimeError("build failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "build failed"):
                app_module.run_site_mutation_transaction(
                    lambda: delete_published_document(
                        docs_root=self.docs_root,
                        site_path="rollback-delete",
                    )
                )
        self.assertTrue((self.docs_root / "rollback-delete" / "index.md").exists())

    def test_editor_uses_simplified_publish_workflow(self) -> None:
        self.assertIn("Document Converter", _EDITOR_HTML)
        self.assertIn("Publish to Documents", _EDITOR_HTML)
        self.assertNotIn('id="site-folder"', _EDITOR_HTML)
        self.assertNotIn("Create or manage folders", _EDITOR_HTML)
        self.assertNotIn('/docs/documentation/', _EDITOR_HTML)
        self.assertNotIn('/docs/contact/', _EDITOR_HTML)

    def test_site_navigation_stays_flat(self) -> None:
        config = MKDOCS_CONFIG_FILE.read_text(encoding="utf-8")
        css = (MKDOCS_DOCS_DIR / "stylesheets" / "extra.css").read_text(encoding="utf-8")
        delete_script = (MKDOCS_DOCS_DIR / "javascripts" / "delete-published.js").read_text(encoding="utf-8")

        self.assertIn("navigation_depth: 1", config)
        self.assertIn("titles_only: true", config)
        self.assertIn("prev_next_buttons_location: none", config)
        self.assertIn("site_name: ITSD Service Desk Docs", config)
        self.assertIn("javascripts/delete-published.js", config)
        self.assertIn(".wy-menu-vertical li.toctree-l1 > ul", css)
        self.assertIn(".rst-footer-buttons", css)
        self.assertIn(".rst-versions", css)
        self.assertNotIn(".admin-access-control", css)
        self.assertNotIn("#admin-access-button", css)
        self.assertIn("https://github.com/dgooding/pdf-to-markdown", delete_script)
        self.assertIn("[delete-published]", delete_script)
        self.assertIn("issues/new", delete_script)
        self.assertNotIn("admin-access-button", delete_script)
        self.assertNotIn("createAdminControls", delete_script)
        self.assertNotIn("/api/", delete_script)
        self.assertNotIn("publish_secret", delete_script)
        self.assertNotIn("localStorage", delete_script)
        self.assertNotIn("sessionStorage", delete_script)

    def test_update_published_index_lists_published_pages(self) -> None:
        publish_markdown_to_mkdocs_site(
            source_markdown=self.source_md,
            source_assets_dir=self.source_assets,
            docs_root=self.docs_root,
            site_path="guides/reset-password",
        )
        update_published_index(self.docs_root)

        index_text = (self.docs_root / "index.md").read_text(encoding="utf-8")
        self.assertIn("Reset Password", index_text)
        self.assertIn("guides/reset-password/", index_text)
        self.assertIn('class="delete-published-document"', index_text)
        self.assertIn('data-site-path="guides/reset-password"', index_text)
        self.assertNotIn("hidden disabled", index_text)
        self.assertNotIn("/api/delete-published", index_text)

    def test_render_markdown_preview_removes_active_content(self) -> None:
        rendered = render_markdown_preview(
            "# Safe\n\n<script>alert(1)</script><img src=x onerror=\"alert(2)\">"
            "[unsafe](javascript:alert(3))"
        )
        self.assertIn("<h1>Safe</h1>", rendered)
        self.assertNotIn("<script", rendered)
        self.assertNotIn("onerror", rendered)
        self.assertNotIn("javascript:", rendered)

    def test_published_index_escapes_heading_html(self) -> None:
        target = self.docs_root / "unsafe" / "index.md"
        target.parent.mkdir(parents=True)
        target.write_text("# <img src=x onerror=alert(1)>\n", encoding="utf-8")
        update_published_index(self.docs_root)
        index_text = (self.docs_root / "index.md").read_text(encoding="utf-8")
        self.assertNotIn("<img src=x", index_text)
        self.assertIn("&lt;img", index_text)

    def test_convert_rejects_multiple_source_documents(self) -> None:
        uploads = [
            UploadFile(io.BytesIO(b"one"), filename="one.txt"),
            UploadFile(io.BytesIO(b"# two"), filename="two.md"),
        ]
        with self.assertRaises(HTTPException) as denied:
            asyncio.run(app_module.convert(files=uploads, workflow="convert", pdf_mode="hybrid"))
        self.assertEqual(denied.exception.status_code, 400)
        self.assertIn("one source document", denied.exception.detail)

    def test_oversized_upload_removes_temporary_directory(self) -> None:
        upload_dir = self.tmp / "oversized-upload"
        upload_dir.mkdir()
        with (
            patch.object(app_module, "MAX_UPLOAD_BYTES", 4),
            patch.object(app_module.tempfile, "mkdtemp", return_value=str(upload_dir)),
        ):
            upload = UploadFile(io.BytesIO(b"too-large"), filename="large.txt")
            with self.assertRaises(HTTPException) as denied:
                asyncio.run(app_module.convert(files=[upload], workflow="convert", pdf_mode="hybrid"))
        self.assertEqual(denied.exception.status_code, 400)
        self.assertFalse(upload_dir.exists())

    def test_stale_cleanup_preserves_processing_job_and_removes_terminal_job(self) -> None:
        active_dir = Path(tempfile.mkdtemp(prefix="active-job-"))
        terminal_dir = Path(tempfile.mkdtemp(prefix="terminal-job-"))
        try:
            with app_module.jobs_lock:
                app_module.jobs["active-test"] = {
                    "status": "processing",
                    "created_at": 1.0,
                    "last_activity": 1.0,
                    "temp_dir": active_dir,
                }
                app_module.jobs["terminal-test"] = {
                    "status": "completed",
                    "created_at": 1.0,
                    "last_activity": 1.0,
                    "temp_dir": terminal_dir,
                }
            with (
                patch.object(app_module, "STALE_JOB_SECONDS", 10),
                patch.object(app_module, "now_ts", return_value=100.0),
            ):
                app_module.cleanup_stale_jobs()
            self.assertIn("active-test", app_module.jobs)
            self.assertNotIn("terminal-test", app_module.jobs)
            self.assertTrue(active_dir.exists())
            self.assertFalse(terminal_dir.exists())
        finally:
            app_module.cleanup_job("active-test")
            app_module.cleanup_job("terminal-test")
            shutil.rmtree(active_dir, ignore_errors=True)
            shutil.rmtree(terminal_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
