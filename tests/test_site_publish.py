from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import app as app_module

from app import (
    _EDITOR_HTML,
    delete_published_document,
    MKDOCS_CONFIG_FILE,
    MKDOCS_DOCS_DIR,
    normalize_site_path,
    publish_markdown_to_mkdocs_site,
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

    def test_hosted_delete_fails_closed_without_publish_secret(self) -> None:
        with (
            patch.object(app_module, "_IS_HOSTED", True),
            patch.object(app_module, "_PUBLISH_SECRET", ""),
        ):
            with self.assertRaises(HTTPException) as denied:
                asyncio.run(
                    app_module.delete_from_site(
                        site_path="reset-password",
                        publish_secret="",
                    )
                )

        self.assertEqual(denied.exception.status_code, 503)
        self.assertIn("PUBLISH_SECRET is configured", denied.exception.detail)

    def test_hosted_capabilities_report_disabled_without_publish_secret(self) -> None:
        with (
            patch.object(app_module, "_IS_HOSTED", True),
            patch.object(app_module, "_PUBLISH_SECRET", ""),
        ):
            response = asyncio.run(app_module.site_capabilities())

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"mutations_enabled":false', response.body)

    def test_admin_access_requires_correct_publish_secret(self) -> None:
        with patch.object(app_module, "_PUBLISH_SECRET", "required-secret"):
            with self.assertRaises(HTTPException) as denied:
                asyncio.run(app_module.admin_access(publish_secret="wrong"))

            self.assertEqual(denied.exception.status_code, 403)
            allowed = asyncio.run(app_module.admin_access(publish_secret="required-secret"))

        self.assertEqual(allowed.status_code, 200)
        self.assertIn(b'"authorized":true', allowed.body)

    def test_hosted_admin_access_fails_closed_without_publish_secret(self) -> None:
        with (
            patch.object(app_module, "_IS_HOSTED", True),
            patch.object(app_module, "_PUBLISH_SECRET", ""),
        ):
            with self.assertRaises(HTTPException) as denied:
                asyncio.run(app_module.admin_access(publish_secret="anything"))

        self.assertEqual(denied.exception.status_code, 503)
        self.assertIn("PUBLISH_SECRET is configured", denied.exception.detail)

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
        self.assertIn("javascripts/delete-published.js", config)
        self.assertIn(".wy-menu-vertical li.toctree-l1 > ul", css)
        self.assertIn(".rst-footer-buttons", css)
        self.assertIn(".rst-versions", css)
        self.assertIn(".admin-access-control", css)
        self.assertIn("position: fixed", css)
        self.assertIn("top: 1rem", css)
        self.assertIn("right: 1rem", css)
        self.assertIn("#admin-access-button", css)
        self.assertIn("#admin-publish-link[hidden]", css)
        self.assertIn("display: none !important", css)
        self.assertIn("/api/delete-published", delete_script)
        self.assertIn("/api/admin-access", delete_script)
        self.assertIn("/api/site-capabilities", delete_script)
        self.assertIn('button.textContent = "Admin"', delete_script)
        self.assertIn('publishLink.href = "/editor"', delete_script)
        self.assertIn('publishLink.textContent = "Publish"', delete_script)
        self.assertIn("document.body.appendChild(control)", delete_script)
        self.assertIn("adminPublishSecret", delete_script)
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
        self.assertIn("hidden disabled", index_text)
        self.assertNotIn("/api/delete-published", index_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
