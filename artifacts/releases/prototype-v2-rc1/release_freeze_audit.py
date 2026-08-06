from __future__ import annotations

import io
import json
import re
import socket
import time
import uuid
import zipfile
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = ROOT / "artifacts" / "benchmarks" / "benchmark_20260731_024647"
BENCH_JSON = BENCH_DIR / "benchmark-results.json"
OUT_DIR = ROOT / "artifacts" / "releases" / "prototype-v2-rc1"


def port_listening(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def endpoint_runtime_checks() -> dict:
    base = "http://127.0.0.1:8001"
    source_pdf = ROOT / "tests" / "fixtures" / "generated" / "documents" / "PDF-001 native text.pdf"

    with request.urlopen(base + "/editor", timeout=30) as resp:
        editor_status = resp.getcode()

    boundary = "----Boundary" + uuid.uuid4().hex
    chunks: list[bytes] = []

    def field(name: str, value: str) -> None:
        chunks.append((f"--{boundary}\r\n").encode())
        chunks.append((f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n").encode())
        chunks.append(value.encode())
        chunks.append(b"\r\n")

    def filepart(name: str, path: Path) -> None:
        chunks.append((f"--{boundary}\r\n").encode())
        chunks.append((f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{path.name}\"\r\n").encode())
        chunks.append(b"Content-Type: application/pdf\r\n\r\n")
        chunks.append(path.read_bytes())
        chunks.append(b"\r\n")

    filepart("files", source_pdf)
    field("workflow", "convert")
    field("pdf_mode", "hybrid")
    chunks.append((f"--{boundary}--\r\n").encode())

    req = request.Request(
        base + "/api/convert",
        data=b"".join(chunks),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    with request.urlopen(req, timeout=90) as resp:
        convert_status = resp.getcode()
        payload = json.loads(resp.read().decode("utf-8"))

    job_id = payload["job_id"]
    status_payload = None
    for _ in range(200):
        with request.urlopen(base + f"/api/status/{job_id}", timeout=30) as sresp:
            status_payload = json.loads(sresp.read().decode("utf-8"))
        if status_payload.get("status") in {"completed", "failed"}:
            break
        time.sleep(0.2)

    with request.urlopen(base + f"/api/download/{job_id}", timeout=120) as dresp:
        download_status = dresp.getcode()
        zip_bytes = dresp.read()

    zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
    names = sorted(zf.namelist())
    md = zf.read("docs/index.md").decode("utf-8", errors="ignore") if "docs/index.md" in names else ""

    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md)
    md_refs_ok = True
    for ref in refs:
        c = ref.strip().strip("<>").replace("\\", "/")
        if c.startswith(("http://", "https://", "mailto:", "data:", "#")):
            continue
        if c.startswith("assets/") and ("docs/" + c) not in names:
            md_refs_ok = False
            break

    banned = [
        "verify_endpoint.py",
        "strict_compare_run.py",
        "PROJECT_STATE.md",
        "ARCHITECTURE.md",
        "DECISIONS.md",
        "TESTING.md",
        "NEXT_MILESTONE.md",
        "AGENTS.md",
    ]
    joined = "\n".join(names)

    zf.close()

    return {
        "editor_status": editor_status,
        "api_convert_status": convert_status,
        "job_status": status_payload.get("status") if status_payload else None,
        "download_status": download_status,
        "zip_has_index": "docs/index.md" in names,
        "zip_has_asset_file": any(n.startswith("docs/assets/") and not n.endswith("/") for n in names),
        "zip_has_manifest": any(n.endswith("-manifest.json") for n in names),
        "zip_has_quality": any(n.endswith("-quality-report.json") for n in names),
        "zip_has_banned_internal_utilities": any(b in joined for b in banned),
        "zip_markdown_refs_resolve": md_refs_ok,
        "mkdocs_auto_started": port_listening(8012),
        "port_8012_listening": port_listening(8012),
    }


def summarize_fidelity() -> dict:
    payload = json.loads(BENCH_JSON.read_text(encoding="utf-8"))
    results = payload.get("results", [])

    review_required = sum(1 for r in results if r.get("fidelity_status_direct") == "review_required")

    manifests = list((BENCH_DIR / "fixtures").glob("**/direct/*-manifest.json"))
    visual_only = 0
    ocr_unavailable_or_review = 0
    semantic_table_count = 0
    visual_table_fallback_count = 0
    full_page_fallback_count = 0
    targeted_fallback_count = 0

    for mf in manifests:
        m = json.loads(mf.read_text(encoding="utf-8"))
        pages = m.get("document_result", {}).get("pages", [])
        for p in pages:
            sem = float(p.get("semantic_coverage", 0.0) or 0.0)
            vis = float(p.get("visual_coverage", 0.0) or 0.0)
            if sem == 0.0 and vis >= 0.95:
                visual_only += 1

            for fr in p.get("fallback_records", []) or []:
                ftype = fr.get("fallback_type")
                if ftype == "full_page":
                    full_page_fallback_count += 1
                else:
                    targeted_fallback_count += 1
                if ftype == "table_crop":
                    visual_table_fallback_count += 1

        for t in m.get("tables_detected", []) or []:
            kind = t.get("kind", "")
            if kind in {"table_markdown", "table_html"}:
                semantic_table_count += 1

        warnings = [str(w).lower() for w in (m.get("warnings", []) or [])]
        if any("ocr recommended but unavailable" in w for w in warnings):
            ocr_unavailable_or_review += 1

    return {
        "technical_pass_rate": payload.get("technical_pass_rate"),
        "endpoint_parity_rate": payload.get("endpoint_parity_rate"),
        "content_fidelity_distribution": payload.get("fidelity_distribution"),
        "review_required_fixture_count": review_required,
        "visual_only_fallback_count": visual_only,
        "ocr_unavailable_or_ocr_review_count": ocr_unavailable_or_review,
        "semantic_table_count": semantic_table_count,
        "visual_table_fallback_count": visual_table_fallback_count,
        "full_page_fallback_count": full_page_fallback_count,
        "targeted_fallback_count": targeted_fallback_count,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fidelity = summarize_fidelity()
    runtime = endpoint_runtime_checks()

    (OUT_DIR / "fidelity_metrics.json").write_text(json.dumps(fidelity, indent=2), encoding="utf-8")
    (OUT_DIR / "runtime_checks.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")

    print("FROZEN_TECH_PASS_RATE", fidelity.get("technical_pass_rate"))
    print("FROZEN_PARITY_RATE", fidelity.get("endpoint_parity_rate"))
    print("REVIEW_REQUIRED_FIXTURES", fidelity.get("review_required_fixture_count"))
    print("RUNTIME_EDITOR_STATUS", runtime.get("editor_status"))
    print("RUNTIME_API_CONVERT_STATUS", runtime.get("api_convert_status"))
    print("RUNTIME_JOB_STATUS", runtime.get("job_status"))
    print("RUNTIME_PORT_8012_LISTENING", runtime.get("port_8012_listening"))


if __name__ == "__main__":
    main()
