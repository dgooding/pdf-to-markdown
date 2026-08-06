from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib import request as urlrequest


class CloudConfigTests(unittest.TestCase):
    """Verify env-driven configuration and cloud-safe behaviour."""

    def test_health_endpoint_returns_ok(self) -> None:
        import socket
        sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(60):
                try:
                    with urlrequest.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                        if r.getcode() == 200:
                            import json
                            self.assertEqual(json.loads(r.read())["status"], "ok")
                            break
                except Exception:
                    time.sleep(0.2)
            else:
                self.fail("/health did not return 200 within timeout")
        finally:
            proc.terminate(); proc.wait(timeout=5)

    def test_env_defaults_preserved(self) -> None:
        """Default values must not change so local LAUNCH.bat continues to work."""
        from app import _BIND_HOST, _BIND_PORT, STALE_JOB_SECONDS, MAX_UPLOAD_BYTES
        self.assertEqual(_BIND_HOST, os.getenv("HOST", "127.0.0.1"))
        self.assertEqual(_BIND_PORT, int(os.getenv("PORT", "8000")))
        self.assertEqual(STALE_JOB_SECONDS, int(os.getenv("STALE_JOB_SECONDS", str(60 * 60))))
        self.assertEqual(MAX_UPLOAD_BYTES, int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024)

    def test_publish_secret_env_respected(self) -> None:
        """PUBLISH_SECRET env var must be loaded by app module."""
        original = os.environ.get("PUBLISH_SECRET", "")
        try:
            os.environ["PUBLISH_SECRET"] = "test-secret-xyz"
            import importlib
            import app as app_mod
            importlib.reload(app_mod)
            self.assertEqual(app_mod._PUBLISH_SECRET, "test-secret-xyz")
        finally:
            if original:
                os.environ["PUBLISH_SECRET"] = original
            else:
                os.environ.pop("PUBLISH_SECRET", None)

    def test_data_root_defaults_to_base_dir(self) -> None:
        """Without DATA_ROOT, published docs fall inside the repository."""
        from app import _DATA_ROOT, BASE_DIR
        if not os.environ.get("DATA_ROOT"):
            self.assertEqual(_DATA_ROOT, BASE_DIR)

    def test_publish_secret_field_in_editor_html(self) -> None:
        """Editor must contain the publish-secret input for hosted deployments."""
        from app import _EDITOR_HTML
        self.assertIn('id="publish-secret"', _EDITOR_HTML)

    def test_health_route_exists_in_app(self) -> None:
        """health_check route must be registered on the FastAPI app."""
        from app import app as fastapi_app
        routes = {r.path for r in fastapi_app.routes}
        self.assertIn("/health", routes)

    def test_docker_files_exist(self) -> None:
        base = Path(__file__).resolve().parents[1]
        self.assertTrue((base / "Dockerfile").exists())
        self.assertTrue((base / ".dockerignore").exists())
        self.assertTrue((base / "render.yaml").exists())
        self.assertTrue((base / ".env.example").exists())

    def test_render_yaml_contains_required_fields(self) -> None:
        base = Path(__file__).resolve().parents[1]
        text = (base / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("healthCheckPath: /health", text)
        self.assertIn("PUBLISH_SECRET", text)
        self.assertRegex(text, r"(?s)- key: PUBLISH_SECRET\s+sync: false")
        self.assertNotIn("123" + "456", text)
        self.assertIn("DATA_ROOT", text)
        self.assertIn("mountPath:", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
