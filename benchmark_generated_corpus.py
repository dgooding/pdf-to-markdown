from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import socket
import subprocess
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib import request

from app import run_authoritative_conversion_service

ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS = ROOT / "tests" / "fixtures" / "generated" / "generated-corpus.json"
BENCH_ROOT = ROOT / "artifacts" / "benchmarks"


@dataclass
class FixtureResult:
    fixture_id: str
    source_path: str
    source_format: str
    page_count: int | None
    direct_status: str
    endpoint_status: str
    compare_md: bool
    compare_assets: bool
    compare_manifest_core: bool
    compare_quality_core: bool
    markdown_ref_check: bool
    mkdocs_build_ok: bool | None
    technical_status_direct: str | None
    technical_status_endpoint: str | None
    fidelity_status_direct: str | None
    fidelity_status_endpoint: str | None
    runtime_seconds_direct: float
    runtime_seconds_endpoint: float
    notes: list[str]


def _now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def _norm_md(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").strip().split("\n"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_manifest_core(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "technical_status": payload.get("technical_status"),
        "fidelity_status": payload.get("fidelity_status"),
        "validation": payload.get("validation"),
        "effective_configuration": payload.get("effective_configuration"),
        "pages": [
            {
                "page_number": p.get("page_number"),
                "selected_candidate": p.get("selected_candidate"),
                "technical_status": p.get("technical_status"),
                "fidelity_status": p.get("fidelity_status"),
            }
            for p in payload.get("document_result", {}).get("pages", [])
        ],
    }


def _normalize_quality_core(payload: dict[str, Any]) -> dict[str, Any]:
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


def _extract_zip(payload: bytes, extract_dir: Path) -> list[str]:
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
        zf.extractall(extract_dir)
        return sorted(zf.namelist())


def _check_markdown_asset_refs(md_text: str, extracted_root: Path) -> bool:
    import re

    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md_text)
    for ref in refs:
        cleaned = ref.strip().strip("<>").replace("\\", "/")
        if cleaned.startswith(("http://", "https://", "mailto:", "data:", "#")):
            continue
        if cleaned.startswith("assets/"):
            if not (extracted_root / "docs" / cleaned).exists():
                return False
    return True


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _start_server() -> tuple[subprocess.Popen, int]:
    port = _free_port()
    proc = subprocess.Popen(
        [
            "C:/Python39/python.exe",
            "-m",
            "uvicorn",
            "app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(120):
        try:
            with request.urlopen(f"http://127.0.0.1:{port}/editor", timeout=1) as resp:
                if resp.getcode() == 200:
                    return proc, port
        except Exception:
            time.sleep(0.1)
    proc.terminate()
    raise RuntimeError("Could not start local uvicorn server for benchmark run.")


def _stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except Exception:
        proc.kill()


def _multipart_convert_via_endpoint(source_file: Path, port: int, pdf_mode: str = "hybrid") -> tuple[int, bytes, dict[str, Any]]:
    boundary = f"----Boundary{uuid.uuid4().hex}"
    parts: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        parts.append((f"--{boundary}\r\n").encode("utf-8"))
        parts.append((f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n").encode("utf-8"))
        parts.append(value.encode("utf-8"))
        parts.append(b"\r\n")

    def add_file(name: str, path: Path) -> None:
        parts.append((f"--{boundary}\r\n").encode("utf-8"))
        parts.append((f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{path.name}\"\r\n").encode("utf-8"))
        ctype = "application/pdf" if path.suffix.lower() == ".pdf" else "application/octet-stream"
        parts.append((f"Content-Type: {ctype}\r\n\r\n").encode("utf-8"))
        parts.append(path.read_bytes())
        parts.append(b"\r\n")

    add_file("files", source_file)
    add_field("workflow", "convert")
    add_field("pdf_mode", pdf_mode)
    parts.append((f"--{boundary}--\r\n").encode("utf-8"))
    body = b"".join(parts)

    req = request.Request(
        f"http://127.0.0.1:{port}/api/convert",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with request.urlopen(req, timeout=180) as resp:
        status = resp.getcode()
        payload = json.loads(resp.read().decode("utf-8"))

    job_id = payload["job_id"]
    status_payload = None
    for _ in range(800):
        with request.urlopen(f"http://127.0.0.1:{port}/api/status/{job_id}", timeout=45) as sresp:
            status_payload = json.loads(sresp.read().decode("utf-8"))
        if status_payload.get("status") in {"completed", "failed"}:
            break
        time.sleep(0.2)

    if not status_payload or status_payload.get("status") != "completed":
        raise RuntimeError(f"Endpoint job failed or timed out: {status_payload}")

    with request.urlopen(f"http://127.0.0.1:{port}/api/download/{job_id}", timeout=240) as dresp:
        zip_payload = dresp.read()

    return status, zip_payload, status_payload


def _run_mkdocs_build_if_available(extracted_root: Path) -> bool | None:
    mkdocs = shutil.which("mkdocs")
    if not mkdocs:
        return None
    cfg = extracted_root / "mkdocs.yml"
    if not cfg.exists():
        return False
    cmd = [mkdocs, "build", "-f", str(cfg), "-q"]
    proc = subprocess.run(cmd, cwd=str(extracted_root), capture_output=True, text=True)
    return proc.returncode == 0


def run_benchmark(corpus_manifest: Path, out_root: Path) -> dict[str, Any]:
    payload = json.loads(corpus_manifest.read_text(encoding="utf-8"))
    fixtures = payload.get("fixtures", [])

    run_dir = out_root / f"benchmark_{_now_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "fixtures").mkdir(parents=True, exist_ok=True)

    server_proc, port = _start_server()
    results: list[FixtureResult] = []

    try:
        for fixture in fixtures:
            fixture_id = fixture["fixture_id"]
            src = corpus_manifest.parent / fixture["source_path"]
            source_format = fixture.get("source_format", src.suffix.lower().lstrip("."))
            page_count = fixture.get("page_count")
            notes: list[str] = []

            fixture_dir = run_dir / "fixtures" / fixture_id.lower()
            direct_dir = fixture_dir / "direct"
            endpoint_dir = fixture_dir / "endpoint"
            endpoint_extract = endpoint_dir / "extracted"
            direct_dir.mkdir(parents=True, exist_ok=True)
            endpoint_dir.mkdir(parents=True, exist_ok=True)

            direct_status = "ok"
            endpoint_status = "ok"
            compare_md = False
            compare_assets = False
            compare_manifest_core = False
            compare_quality_core = False
            markdown_ref_check = False
            mkdocs_build_ok: bool | None = None
            technical_status_direct = None
            technical_status_endpoint = None
            fidelity_status_direct = None
            fidelity_status_endpoint = None
            runtime_direct = 0.0
            runtime_endpoint = 0.0

            try:
                t0 = time.time()
                direct = run_authoritative_conversion_service(
                    source_file=src,
                    output_dir=direct_dir,
                    pdf_mode="hybrid",
                    tesseract_cmd=None,
                    prefer_markitdown=True,
                    improve_markdown=False,
                    companion_files=[],
                )
                runtime_direct = round(time.time() - t0, 4)
            except Exception as exc:  # noqa: BLE001
                direct_status = f"failed: {exc}"
                notes.append(f"direct_error={exc}")
                results.append(
                    FixtureResult(
                        fixture_id=fixture_id,
                        source_path=str(src),
                        source_format=source_format,
                        page_count=page_count,
                        direct_status=direct_status,
                        endpoint_status="not_run",
                        compare_md=False,
                        compare_assets=False,
                        compare_manifest_core=False,
                        compare_quality_core=False,
                        markdown_ref_check=False,
                        mkdocs_build_ok=None,
                        technical_status_direct=None,
                        technical_status_endpoint=None,
                        fidelity_status_direct=None,
                        fidelity_status_endpoint=None,
                        runtime_seconds_direct=runtime_direct,
                        runtime_seconds_endpoint=0.0,
                        notes=notes,
                    )
                )
                continue

            try:
                t1 = time.time()
                http_status, endpoint_zip, endpoint_job = _multipart_convert_via_endpoint(src, port=port, pdf_mode="hybrid")
                runtime_endpoint = round(time.time() - t1, 4)
                if http_status != 200:
                    endpoint_status = f"failed_http_{http_status}"
                    notes.append(f"endpoint_http={http_status}")
            except Exception as exc:  # noqa: BLE001
                endpoint_status = f"failed: {exc}"
                notes.append(f"endpoint_error={exc}")
                results.append(
                    FixtureResult(
                        fixture_id=fixture_id,
                        source_path=str(src),
                        source_format=source_format,
                        page_count=page_count,
                        direct_status=direct_status,
                        endpoint_status=endpoint_status,
                        compare_md=False,
                        compare_assets=False,
                        compare_manifest_core=False,
                        compare_quality_core=False,
                        markdown_ref_check=False,
                        mkdocs_build_ok=None,
                        technical_status_direct=None,
                        technical_status_endpoint=None,
                        fidelity_status_direct=None,
                        fidelity_status_endpoint=None,
                        runtime_seconds_direct=runtime_direct,
                        runtime_seconds_endpoint=runtime_endpoint,
                        notes=notes,
                    )
                )
                continue

            zip_path = endpoint_dir / "package.zip"
            zip_path.write_bytes(endpoint_zip)
            zip_names = _extract_zip(endpoint_zip, endpoint_extract)

            direct_md_path = Path(direct["output_file"])
            direct_assets_dir = Path(direct["assets_dir"])
            direct_manifest_path = Path(direct["manifest_path"])
            direct_quality_path = Path(direct["quality_report_path"])

            endpoint_md_path = endpoint_extract / "docs" / "index.md"
            endpoint_manifest_path = next(endpoint_extract.glob("*-manifest.json"), None)
            endpoint_quality_path = next(endpoint_extract.glob("*-quality-report.json"), None)
            endpoint_assets_dir = endpoint_extract / "docs" / "assets"

            if not endpoint_md_path.exists() or endpoint_manifest_path is None or endpoint_quality_path is None:
                endpoint_status = "failed: missing required endpoint artifacts"
                notes.append("missing endpoint artifacts")

            if endpoint_status == "ok":
                direct_md = direct_md_path.read_text(encoding="utf-8")
                endpoint_md = endpoint_md_path.read_text(encoding="utf-8")
                compare_md = _norm_md(direct_md) == _norm_md(endpoint_md)

                direct_assets = sorted(p.name for p in direct_assets_dir.glob("*") if p.is_file())
                endpoint_assets = sorted(p.name for p in endpoint_assets_dir.glob("*") if p.is_file())
                compare_assets = direct_assets == endpoint_assets
                if compare_assets:
                    for name in direct_assets:
                        h1 = _sha256((direct_assets_dir / name).read_bytes())
                        h2 = _sha256((endpoint_assets_dir / name).read_bytes())
                        if h1 != h2:
                            compare_assets = False
                            notes.append(f"asset_hash_mismatch={name}")
                            break

                direct_manifest = json.loads(direct_manifest_path.read_text(encoding="utf-8"))
                endpoint_manifest = json.loads(endpoint_manifest_path.read_text(encoding="utf-8"))
                compare_manifest_core = _normalize_manifest_core(direct_manifest) == _normalize_manifest_core(endpoint_manifest)

                direct_quality = json.loads(direct_quality_path.read_text(encoding="utf-8"))
                endpoint_quality = json.loads(endpoint_quality_path.read_text(encoding="utf-8"))
                compare_quality_core = _normalize_quality_core(direct_quality) == _normalize_quality_core(endpoint_quality)

                technical_status_direct = direct_manifest.get("technical_status")
                technical_status_endpoint = endpoint_manifest.get("technical_status")
                fidelity_status_direct = direct_manifest.get("fidelity_status")
                fidelity_status_endpoint = endpoint_manifest.get("fidelity_status")

                markdown_ref_check = _check_markdown_asset_refs(endpoint_md, endpoint_extract)
                mkdocs_build_ok = _run_mkdocs_build_if_available(endpoint_extract)

                if not compare_md:
                    notes.append("md_mismatch")
                if not compare_assets:
                    notes.append("asset_mismatch")
                if not compare_manifest_core:
                    notes.append("manifest_core_mismatch")
                if not compare_quality_core:
                    notes.append("quality_core_mismatch")
                if not markdown_ref_check:
                    notes.append("broken_markdown_asset_reference")

            results.append(
                FixtureResult(
                    fixture_id=fixture_id,
                    source_path=str(src),
                    source_format=source_format,
                    page_count=page_count,
                    direct_status=direct_status,
                    endpoint_status=endpoint_status,
                    compare_md=compare_md,
                    compare_assets=compare_assets,
                    compare_manifest_core=compare_manifest_core,
                    compare_quality_core=compare_quality_core,
                    markdown_ref_check=markdown_ref_check,
                    mkdocs_build_ok=mkdocs_build_ok,
                    technical_status_direct=technical_status_direct,
                    technical_status_endpoint=technical_status_endpoint,
                    fidelity_status_direct=fidelity_status_direct,
                    fidelity_status_endpoint=fidelity_status_endpoint,
                    runtime_seconds_direct=runtime_direct,
                    runtime_seconds_endpoint=runtime_endpoint,
                    notes=notes,
                )
            )

    finally:
        _stop_server(server_proc)

    total = len(results)
    parity_ok = sum(
        1
        for r in results
        if r.compare_md and r.compare_assets and r.compare_manifest_core and r.compare_quality_core
    )
    technical_pass = sum(1 for r in results if r.technical_status_direct == "passed")
    fidelity_dist: dict[str, int] = {"high": 0, "moderate": 0, "low": 0, "review_required": 0, "unknown": 0}
    for r in results:
        key = r.fidelity_status_direct or "unknown"
        if key not in fidelity_dist:
            key = "unknown"
        fidelity_dist[key] += 1

    aggregate = {
        "generated_at": _now_stamp(),
        "corpus_manifest": str(corpus_manifest),
        "total_fixtures": total,
        "endpoint_parity_rate": round(parity_ok / max(1, total), 4),
        "technical_pass_rate": round(technical_pass / max(1, total), 4),
        "fidelity_distribution": fidelity_dist,
        "results": [asdict(r) for r in results],
    }

    (run_dir / "benchmark-results.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    md_lines = [
        "# Synthetic Corpus Baseline Benchmark",
        "",
        f"- Total fixtures: {total}",
        f"- Endpoint parity rate: {aggregate['endpoint_parity_rate']}",
        f"- Technical pass rate: {aggregate['technical_pass_rate']}",
        f"- Fidelity distribution: {json.dumps(fidelity_dist)}",
        "",
        "## Fixture Results",
        "",
    ]
    for r in results:
        ok = r.compare_md and r.compare_assets and r.compare_manifest_core and r.compare_quality_core
        icon = "✅" if ok else "⚠️"
        md_lines.extend(
            [
                f"### {icon} {r.fixture_id}",
                f"- source: `{r.source_path}`",
                f"- direct status: `{r.direct_status}`",
                f"- endpoint status: `{r.endpoint_status}`",
                f"- compare: md={r.compare_md}, assets={r.compare_assets}, manifest={r.compare_manifest_core}, quality={r.compare_quality_core}",
                f"- direct technical/fidelity: `{r.technical_status_direct}` / `{r.fidelity_status_direct}`",
                f"- endpoint technical/fidelity: `{r.technical_status_endpoint}` / `{r.fidelity_status_endpoint}`",
                f"- markdown refs valid: `{r.markdown_ref_check}`",
                f"- mkdocs build ok: `{r.mkdocs_build_ok}`",
                f"- runtime seconds: direct={r.runtime_seconds_direct}, endpoint={r.runtime_seconds_endpoint}",
                (f"- notes: {', '.join(r.notes)}" if r.notes else "- notes: none"),
                "",
            ]
        )

    (run_dir / "benchmark-results.md").write_text("\n".join(md_lines), encoding="utf-8")
    return {"run_dir": str(run_dir), "summary": aggregate}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Milestone 2: baseline generated corpus with direct+endpoint parity checks.")
    p.add_argument("--corpus-manifest", type=Path, default=DEFAULT_CORPUS)
    p.add_argument("--out-root", type=Path, default=BENCH_ROOT)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.corpus_manifest.exists():
        print(f"Corpus manifest not found: {args.corpus_manifest}")
        return 1
    args.out_root.mkdir(parents=True, exist_ok=True)
    res = run_benchmark(args.corpus_manifest, args.out_root)
    print("Benchmark complete")
    print(f"RUN_DIR {res['run_dir']}")
    print(f"TOTAL_FIXTURES {res['summary']['total_fixtures']}")
    print(f"PARITY_RATE {res['summary']['endpoint_parity_rate']}")
    print(f"TECH_PASS_RATE {res['summary']['technical_pass_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
