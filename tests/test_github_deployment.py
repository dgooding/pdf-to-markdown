from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib import request as urlrequest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class GitHubDeploymentTests(unittest.TestCase):
    def test_local_health_endpoint_returns_ok(self) -> None:
        import socket

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(60):
                try:
                    with urlrequest.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                        self.assertEqual(response.getcode(), 200)
                        break
                except Exception:
                    time.sleep(0.2)
            else:
                self.fail("/health did not return 200 within timeout")
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_local_environment_defaults_remain_supported(self) -> None:
        from app import _BIND_HOST, _BIND_PORT, MAX_UPLOAD_BYTES, STALE_JOB_SECONDS

        self.assertEqual(_BIND_HOST, os.getenv("HOST", "127.0.0.1"))
        self.assertEqual(_BIND_PORT, int(os.getenv("PORT", "8000")))
        self.assertEqual(STALE_JOB_SECONDS, int(os.getenv("STALE_JOB_SECONDS", str(60 * 60))))
        self.assertEqual(MAX_UPLOAD_BYTES, int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024)

    def test_github_workflows_exist_and_render_config_is_removed(self) -> None:
        self.assertTrue((WORKFLOWS / "convert-publish.yml").is_file())
        self.assertTrue((WORKFLOWS / "delete-published.yml").is_file())
        self.assertTrue((WORKFLOWS / "pages.yml").is_file())
        self.assertFalse((ROOT / "render.yaml").exists())
        self.assertTrue((ROOT / "incoming" / ".gitkeep").is_file())

    def test_pages_workflow_uses_official_actions_and_minimal_permissions(self) -> None:
        text = (WORKFLOWS / "pages.yml").read_text(encoding="utf-8")
        self.assertIn("actions/configure-pages@v5", text)
        self.assertIn("actions/upload-pages-artifact@v3", text)
        self.assertIn("actions/deploy-pages@v4", text)
        self.assertIn("enablement: true", text)
        self.assertIn("contents: read", text)
        self.assertIn("pages: write", text)
        self.assertIn("id-token: write", text)
        self.assertNotIn("contents: write", text)

    def test_convert_workflow_processes_incoming_and_commits_only_expected_paths(self) -> None:
        text = (WORKFLOWS / "convert-publish.yml").read_text(encoding="utf-8")
        self.assertIn('"incoming/**"', text)
        self.assertIn("github_document_ops.py process-incoming", text)
        self.assertIn("git add -A incoming mkdocs_preview/docs/published", text)
        self.assertIn("tesseract-ocr", text)
        self.assertIn("contents: write", text)
        self.assertIn("group: document-publishing", text)
        self.assertNotIn("PUBLISH_SECRET", text)

    def test_delete_workflow_checks_repository_permission(self) -> None:
        text = (WORKFLOWS / "delete-published.yml").read_text(encoding="utf-8")
        self.assertIn("getCollaboratorPermissionLevel", text)
        self.assertIn("['admin', 'maintain', 'write']", text)
        self.assertIn("github_document_ops.py delete", text)
        self.assertIn("[delete-published]", text)
        self.assertIn("group: document-publishing", text)
        self.assertNotIn("PUBLISH_SECRET", text)

    def test_mkdocs_is_configured_for_project_pages(self) -> None:
        config = (ROOT / "mkdocs_preview" / "mkdocs.yml").read_text(encoding="utf-8")
        guide = (ROOT / "mkdocs_preview" / "docs" / "converter.md").read_text(encoding="utf-8")
        self.assertIn("site_url: https://dgooding.github.io/pdf-to-markdown/", config)
        self.assertIn("repo_url: https://github.com/dgooding/pdf-to-markdown", config)
        self.assertIn("Converter: converter.md", config)
        self.assertNotIn("Converter: /editor", config)
        self.assertIn("upload/main/incoming", guide)
        self.assertIn("public and remains recoverable from Git history", guide)
        self.assertIn("repository write permission", guide)

    def test_pages_javascript_contains_no_credentials_or_runtime_api_calls(self) -> None:
        script = (ROOT / "mkdocs_preview" / "docs" / "javascripts" / "delete-published.js").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("/api/", script)
        self.assertNotIn("publish_secret", script)
        self.assertNotIn("localStorage", script)
        self.assertNotIn("sessionStorage", script)
        self.assertNotIn("123" + "456", script)


if __name__ == "__main__":
    unittest.main(verbosity=2)
