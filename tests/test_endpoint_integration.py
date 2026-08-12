from __future__ import annotations

import hashlib
import io
import json
import re
import socket
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

import fitz

from urllib import error, request

from app import run_authoritative_conversion_service


class EndpointIntegrationTests(unittest.TestCase):
    @classmethod
    def _make_fixture_pdf(cls, path: Path) -> None:
        doc = fitz.open()
        p1 = doc.new_page()
        p1.insert_text((50, 60), "Endpoint Integration PDF", fontsize=20)
        p1.insert_text((50, 95), "This page validates multipart conversion endpoint.", fontsize=11)

        p2 = doc.new_page()
        p2.insert_text((50, 70), "Metric    Q1    Q2", fontsize=11, fontname="cour")
        p2.insert_text((50, 90), "Open      10    12", fontsize=11, fontname="cour")
        p2.insert_text((50, 110), "Closed    8     11", fontsize=11, fontname="cour")
        doc.save(path)
        doc.close()

    def _convert_via_endpoint(self, source_file: Path, *, download_zip: bool = True) -> tuple[str, bytes | None]:
        boundary = f"----Boundary{int(time.time() * 1000)}"
        parts = []

        def add_field(name: str, value: str) -> None:
            parts.append((f"--{boundary}\r\n").encode("utf-8"))
            parts.append((f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n").encode("utf-8"))
            parts.append(value.encode("utf-8"))
            parts.append(b"\r\n")

        def add_file(name: str, path: Path) -> None:
            parts.append((f"--{boundary}\r\n").encode("utf-8"))
            parts.append((f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{path.name}\"\r\n").encode("utf-8"))
            parts.append(b"Content-Type: application/pdf\r\n\r\n")
            parts.append(path.read_bytes())
            parts.append(b"\r\n")

        add_file("files", source_file)
        add_field("workflow", "convert")
        add_field("pdf_mode", "hybrid")
        parts.append((f"--{boundary}--\r\n").encode("utf-8"))
        body = b"".join(parts)

        req = request.Request(
            f"http://127.0.0.1:{self.server_port}/api/convert",
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with request.urlopen(req, timeout=90) as resp:
            self.assertEqual(resp.getcode(), 200)
            payload = json.loads(resp.read().decode("utf-8"))

        job_id = payload["job_id"]

        status_payload = None
        for _ in range(120):
            with request.urlopen(f"http://127.0.0.1:{self.server_port}/api/status/{job_id}", timeout=30) as sresp:
                status_payload = json.loads(sresp.read().decode("utf-8"))
            if status_payload.get("status") in {"completed", "failed"}:
                break
            time.sleep(0.1)

        self.assertIsNotNone(status_payload)
        self.assertEqual(status_payload.get("status"), "completed")

        zip_bytes: bytes | None = None
        if download_zip:
            with request.urlopen(f"http://127.0.0.1:{self.server_port}/api/download/{job_id}", timeout=120) as dresp:
                self.assertEqual(dresp.getcode(), 200)
                zip_bytes = dresp.read()

        return job_id, zip_bytes

    @classmethod
    def _free_port(cls) -> int:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        return int(port)

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_root = Path(tempfile.mkdtemp(prefix="endpoint-tests-"))
        cls.fixture_pdf = cls.temp_root / "endpoint_sample.pdf"
        cls._make_fixture_pdf(cls.fixture_pdf)
        cls.server_port = cls._free_port()
        cls.server_proc = subprocess.Popen(
            [
                "C:/Python39/python.exe",
                "-m",
                "uvicorn",
                "app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.server_port),
            ],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(80):
            try:
                with request.urlopen(f"http://127.0.0.1:{cls.server_port}/editor", timeout=1) as resp:
                    if resp.getcode() == 200:
                        break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("Endpoint test server did not start.")

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "server_proc", None) is not None:
            cls.server_proc.terminate()
            try:
                cls.server_proc.wait(timeout=5)
            except Exception:
                cls.server_proc.kill()

    def _extract_zip_bytes(self, payload: bytes) -> tuple[zipfile.ZipFile, list[str]]:
        zf = zipfile.ZipFile(io.BytesIO(payload), "r")
        names = sorted(zf.namelist())
        return zf, names

    @staticmethod
    def _norm_md(text: str) -> str:
        return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").strip().split("\n"))

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _normalize_manifest_core(payload: dict) -> dict:
        core = {
            "technical_status": payload.get("technical_status"),
            "fidelity_status": payload.get("fidelity_status"),
            "validation": payload.get("validation"),
            "pages": [
                {
                    "page_number": p.get("page_number"),
                    "selected_candidate": p.get("selected_candidate"),
                    "technical_status": p.get("technical_status"),
                    "fidelity_status": p.get("fidelity_status"),
                }
                for p in payload.get("document_result", {}).get("pages", [])
            ],
            "effective_configuration": payload.get("effective_configuration"),
        }
        return core

    @staticmethod
    def _normalize_quality_core(payload: dict) -> dict:
        return {
            "technical_status": payload.get("technical_status"),
            "fidelity_status": payload.get("fidelity_status"),
            "effective_configuration": payload.get("effective_configuration"),
            "pages": [
                {
                    "page_number": p.get("page_number"),
                    "selected_candidate": p.get("selected_candidate"),
                    "technical_status": p.get("technical_status"),
                    "fidelity_status": p.get("fidelity_status"),
                }
                for p in payload.get("page_summaries", [])
            ],
        }

    def test_endpoint_zip_contains_required_outputs(self) -> None:
        _, zip_bytes = self._convert_via_endpoint(self.fixture_pdf)
        zf, names = self._extract_zip_bytes(zip_bytes)

        self.assertIn("docs/index.md", names)
        self.assertTrue(any(n.startswith("docs/assets/") and not n.endswith("/") for n in names))
        self.assertTrue(any(n.endswith("-manifest.json") for n in names))
        self.assertTrue(any(n.endswith("-quality-report.json") for n in names))
        self.assertFalse(any(n.endswith("-review-record.json") for n in names))

        banned = {"verify_endpoint.py", "PROJECT_STATE.md", "baseline_verticalslice_20260730_224127"}
        joined = "\n".join(names)
        for token in banned:
            self.assertNotIn(token, joined)

        zf.close()

    def test_endpoint_matches_authoritative_service_output_core(self) -> None:
        direct_out = self.temp_root / "direct_service_output"
        if direct_out.exists():
            import shutil
            shutil.rmtree(direct_out)
        direct_out.mkdir(parents=True, exist_ok=True)

        direct = run_authoritative_conversion_service(
            source_file=self.fixture_pdf,
            output_dir=direct_out,
            pdf_mode="hybrid",
            tesseract_cmd=None,
            prefer_markitdown=True,
            improve_markdown=False,
            companion_files=[],
        )

        _, zip_bytes = self._convert_via_endpoint(self.fixture_pdf)
        zf, names = self._extract_zip_bytes(zip_bytes)

        endpoint_md = zf.read("docs/index.md").decode("utf-8")
        direct_md = Path(direct["output_file"]).read_text(encoding="utf-8")
        self.assertEqual(self._norm_md(endpoint_md), self._norm_md(direct_md))

        endpoint_assets = sorted(n.split("docs/assets/", 1)[1] for n in names if n.startswith("docs/assets/") and not n.endswith("/"))
        direct_assets = sorted(p.name for p in Path(direct["assets_dir"]).glob("*") if p.is_file())
        self.assertEqual(endpoint_assets, direct_assets)

        for name in endpoint_assets:
            self.assertEqual(
                self._sha256(zf.read(f"docs/assets/{name}")),
                self._sha256((Path(direct["assets_dir"]) / name).read_bytes()),
            )

        endpoint_manifest_name = next(n for n in names if n.endswith("-manifest.json"))
        endpoint_quality_name = next(n for n in names if n.endswith("-quality-report.json"))
        endpoint_manifest = json.loads(zf.read(endpoint_manifest_name).decode("utf-8"))
        endpoint_quality = json.loads(zf.read(endpoint_quality_name).decode("utf-8"))

        direct_manifest = json.loads(Path(direct["manifest_path"]).read_text(encoding="utf-8"))
        direct_quality = json.loads(Path(direct["quality_report_path"]).read_text(encoding="utf-8"))

        self.assertEqual(
            self._normalize_manifest_core(endpoint_manifest),
            self._normalize_manifest_core(direct_manifest),
        )
        self.assertEqual(
            self._normalize_quality_core(endpoint_quality),
            self._normalize_quality_core(direct_quality),
        )

        zf.close()

    def test_endpoint_markdown_references_resolve_inside_zip(self) -> None:
        _, zip_bytes = self._convert_via_endpoint(self.fixture_pdf)
        zf, names = self._extract_zip_bytes(zip_bytes)

        md = zf.read("docs/index.md").decode("utf-8")
        refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md)
        for ref in refs:
            cleaned = ref.strip().strip("<>").replace("\\", "/")
            if cleaned.startswith("assets/"):
                self.assertIn(f"docs/{cleaned}", names)

        self.assertFalse(bool(re.search(r"([A-Za-z]:\\\\|/tmp/|/var/|\\\\Users\\\\)", md)))
        zf.close()

    def test_endpoint_markdown_download_returns_md_file(self) -> None:
        job_id, _ = self._convert_via_endpoint(self.fixture_pdf, download_zip=False)

        with request.urlopen(f"http://127.0.0.1:{self.server_port}/api/download-md/{job_id}", timeout=120) as dresp:
            self.assertEqual(dresp.getcode(), 200)
            self.assertEqual(dresp.headers.get_content_type(), "text/markdown")
            self.assertIn("endpoint_sample_converted.md", dresp.headers.get("Content-Disposition", ""))
            md = dresp.read().decode("utf-8")

        self.assertIn("Endpoint Integration PDF", md)
        self.assertIn("## Page 1", md)

        # A download must not destroy the job; users may still preview, publish,
        # or retrieve the complete package afterward.
        with request.urlopen(f"http://127.0.0.1:{self.server_port}/api/status/{job_id}", timeout=30) as sresp:
            self.assertEqual(sresp.getcode(), 200)
        with request.urlopen(f"http://127.0.0.1:{self.server_port}/api/download/{job_id}", timeout=120) as zresp:
            self.assertEqual(zresp.getcode(), 200)
            self.assertTrue(zresp.read().startswith(b"PK"))

    def test_asset_path_traversal_is_rejected(self) -> None:
        job_id, _ = self._convert_via_endpoint(self.fixture_pdf, download_zip=False)
        url = f"http://127.0.0.1:{self.server_port}/api/assets/{job_id}/..%2F..%2Findex.md"
        with self.assertRaises(error.HTTPError) as denied:
            request.urlopen(url, timeout=30)
        self.assertIn(denied.exception.code, {400, 404})

    def test_authoritative_service_non_pdf_emits_manifest_and_quality(self) -> None:
        md_source = self.temp_root / "source.md"
        md_source.write_text("# Sample\n\nHello benchmark world.\n", encoding="utf-8")
        out_dir = self.temp_root / "direct_markdown_output"
        if out_dir.exists():
            import shutil
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        result = run_authoritative_conversion_service(
            source_file=md_source,
            output_dir=out_dir,
            pdf_mode="hybrid",
            tesseract_cmd=None,
            prefer_markitdown=True,
            improve_markdown=False,
            companion_files=[],
        )

        manifest = Path(result["manifest_path"])
        quality = Path(result["quality_report_path"])
        self.assertTrue(manifest.exists())
        self.assertTrue(quality.exists())

        manifest_obj = json.loads(manifest.read_text(encoding="utf-8"))
        quality_obj = json.loads(quality.read_text(encoding="utf-8"))

        self.assertIn(manifest_obj.get("technical_status"), {"passed", "failed"})
        self.assertIn(manifest_obj.get("fidelity_status"), {"high", "moderate", "low", "review_required"})
        self.assertIn("document_result", manifest_obj)
        self.assertIn("page_summaries", quality_obj)

    def test_non_pdf_manifest_allows_legitimate_windows_path_content(self) -> None:
        md_source = self.temp_root / "source_windows_path.md"
        md_source.write_text("# Path Sample\n\nWindows Path: C:\\\\Synthetic\\\\App\\\\logs\\\\today.txt\n", encoding="utf-8")
        out_dir = self.temp_root / "direct_markdown_windows_path_output"
        if out_dir.exists():
            import shutil
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        result = run_authoritative_conversion_service(
            source_file=md_source,
            output_dir=out_dir,
            pdf_mode="hybrid",
            tesseract_cmd=None,
            prefer_markitdown=True,
            improve_markdown=False,
            companion_files=[],
        )

        manifest = Path(result["manifest_path"])
        self.assertTrue(manifest.exists())
        manifest_obj = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest_obj.get("technical_status"), "passed")
        self.assertFalse(manifest_obj.get("validation", {}).get("has_absolute_paths", True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
