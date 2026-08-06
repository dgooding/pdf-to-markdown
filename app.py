from __future__ import annotations

import asyncio
import hmac
import os
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Optional

import markdown
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.background import BackgroundTask

from convert_to_md import ConversionContext, convert_file_to_markdown, ensure_assets_folder, slugify

BASE_DIR = Path(__file__).resolve().parent

# --- cloud / hosting configuration read from environment ---
_BIND_HOST = os.getenv("HOST", "127.0.0.1")
_BIND_PORT = int(os.getenv("PORT", "8000"))
# Secret required for POST /api/publish; empty string leaves publishing open (local default)
_PUBLISH_SECRET = os.getenv("PUBLISH_SECRET", "")
_IS_HOSTED = os.getenv("RENDER", "").lower() == "true"
# Persistent data root; use env DATA_ROOT on hosted deployments so a mounted volume is used
_DATA_ROOT = Path(os.getenv("DATA_ROOT", str(BASE_DIR)))
_DATA_ROOT_CONFIGURED = bool(os.getenv("DATA_ROOT", "").strip())

MKDOCS_PROJECT_DIR = BASE_DIR / "mkdocs_preview"
MKDOCS_DOCS_DIR = MKDOCS_PROJECT_DIR / "docs"
MKDOCS_CONFIG_FILE = MKDOCS_PROJECT_DIR / "mkdocs.yml"
PUBLISHED_DOCS_DIR = _DATA_ROOT / "published" if _DATA_ROOT_CONFIGURED else MKDOCS_DOCS_DIR / "published"
SITE_DIR = MKDOCS_PROJECT_DIR / "site"

SUPPORTED_UPLOADS = {".pdf", ".docx", ".md", ".txt"}
DEFAULT_PDF_MODE = "hybrid"
SUPPORTED_PDF_MODES = {"hybrid", "ocr", "visual"}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024
MAX_FILES_PER_REQUEST = 50

app = FastAPI(title="MkDocs File Converter API", version="1.0.0")

jobs: dict[str, dict[str, Any]] = {}
site_mutation_lock = threading.Lock()
STALE_JOB_SECONDS = int(os.getenv("STALE_JOB_SECONDS", str(60 * 60)))


@app.middleware("http")
async def add_security_headers(request: Any, call_next: Any) -> Any:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


class StatusPayload(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    preview_url: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None
    suggestion: Optional[str] = None


def now_ts() -> float:
    return time.time()


def require_mutation_secret(provided_secret: str, action: str) -> None:
  if _IS_HOSTED and not _PUBLISH_SECRET:
    raise HTTPException(
      status_code=503,
      detail=f"{action} is disabled until PUBLISH_SECRET is configured.",
    )
  if _PUBLISH_SECRET and not hmac.compare_digest(provided_secret, _PUBLISH_SECRET):
    raise HTTPException(status_code=403, detail=f"{action} is restricted. Provide the correct publish secret.")


def cleanup_job(job_id: str) -> None:
    job = jobs.get(job_id)
    if not job:
        return

    temp_dir = job.get("temp_dir")
    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)

    jobs.pop(job_id, None)


def cleanup_stale_jobs() -> None:
    cutoff = now_ts() - STALE_JOB_SECONDS
    stale_ids: list[str] = []
    for job_id, job in jobs.items():
        created_at = float(job.get("created_at", now_ts()))
        if created_at < cutoff:
            stale_ids.append(job_id)

    for job_id in stale_ids:
        cleanup_job(job_id)


def build_zip(output_dir: Path, zip_path: Path) -> None:
    banned_names = {
        "verify_endpoint.py",
        "strict_compare.py",
        "strict_compare_run.py",
        "PROJECT_STATE.md",
        "ARCHITECTURE.md",
        "DECISIONS.md",
        "TESTING.md",
        "NEXT_MILESTONE.md",
        "AGENTS.md",
    }
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in output_dir.rglob("*"):
            if item.is_file() and item != zip_path:
                rel = str(item.relative_to(output_dir)).replace("\\", "/")
                if any(part in banned_names for part in Path(rel).parts):
                    continue
                if rel.startswith(("artifacts/", "tests/", "__pycache__/")):
                    continue
                archive.write(item, arcname=rel)


def _safe_upload_name(name: str) -> str:
    base = Path(name or "upload").name
    cleaned = re.sub(r"[^a-zA-Z0-9._ -]+", "_", base).strip()
    return cleaned or "upload"


def build_mkdocs_project(output_dir: Path, markdown_content: str) -> Path:
    docs_dir = output_dir / "docs"
    styles_dir = docs_dir / "stylesheets"
    docs_dir.mkdir(parents=True, exist_ok=True)
    styles_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "mkdocs.yml").write_text(
        """site_name: Converted Document Preview
site_description: Auto-generated MkDocs-ready document package
theme:
  name: mkdocs
markdown_extensions:
  - tables
  - fenced_code
extra_css:
  - stylesheets/extra.css
nav:
  - Home: index.md
""",
        encoding="utf-8",
    )

    (styles_dir / "extra.css").write_text(
        """body { font-family: Inter, Segoe UI, Arial, sans-serif; }
.md-content img {
  display: block;
  max-width: 100%;
  border-radius: 14px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.18);
  margin: 1.25rem auto;
}
.md-content h1, .md-content h2, .md-content h3 { letter-spacing: -0.02em; }
.md-content table { border-radius: 12px; overflow: hidden; }
.md-content details {
  border: 1px solid #d7deea;
  border-radius: 12px;
  padding: 0.75rem 1rem;
  background: #f8fafc;
  margin: 1rem 0;
}
.md-content details summary { cursor: pointer; font-weight: 600; }
""",
        encoding="utf-8",
    )

    output_file = docs_dir / "index.md"
    output_file.write_text(markdown_content, encoding="utf-8")
    return output_file


def suggest_fix(error_message: str) -> str:
  text = error_message.lower()
  if "unsupported file type" in text:
    return "Use a supported file type: PDF, DOCX, or Markdown."
  if "tesseract" in text:
    return "OCR is optional in this build. Use a standard PDF or DOCX file and retry."
  if "missing dependency" in text:
    return "Install requirements first, then retry conversion."
  return "Check the file and try again."


def normalize_site_path(site_path: str, fallback_stem: str) -> str:
  raw = (site_path or "").strip().replace("\\", "/")
  if raw.lower().endswith(".md"):
    raw = raw[:-3]

  parts: list[str] = []
  for chunk in raw.split("/"):
    chunk = chunk.strip()
    if not chunk or chunk in {".", ".."}:
      continue
    parts.append(slugify(chunk))

  if not parts:
    parts = [slugify(fallback_stem)]

  return "/".join(parts)


def publish_markdown_to_mkdocs_site(
  *,
  source_markdown: Path,
  source_assets_dir: Path | None,
  docs_root: Path,
  site_path: str,
) -> dict[str, str]:
  normalized = normalize_site_path(site_path, source_markdown.stem)
  target_dir = docs_root / Path(normalized)
  target_markdown = target_dir / "index.md"
  if target_markdown.exists():
    raise FileExistsError(f'A document named "{normalized}" is already published.')

  target_dir.mkdir(parents=True, exist_ok=True)
  target_markdown.write_text(source_markdown.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")

  target_assets_dir = target_dir / "assets"
  if target_assets_dir.exists():
    shutil.rmtree(target_assets_dir, ignore_errors=True)

  if source_assets_dir and source_assets_dir.exists():
    for item in source_assets_dir.rglob("*"):
      if not item.is_file():
        continue
      destination = target_assets_dir / item.relative_to(source_assets_dir)
      destination.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(item, destination)

  return {
    "site_path": normalized,
    "folder": normalized.rsplit("/", 1)[0] if "/" in normalized else "",
    "document_name": normalized.rsplit("/", 1)[-1],
    "target_markdown": str(target_markdown),
    "published_url": f"/docs/published/{normalized}/",
  }


def delete_published_document(*, docs_root: Path, site_path: str) -> dict[str, str]:
  requested = site_path.strip().replace("\\", "/").strip("/")
  if not requested:
    raise ValueError("Document path is required.")

  normalized = normalize_site_path(requested, "")
  if normalized != requested:
    raise ValueError("Invalid document path.")

  resolved_root = docs_root.resolve()
  target_dir = (docs_root / normalized).resolve()
  try:
    target_dir.relative_to(resolved_root)
  except ValueError as exc:
    raise ValueError("Invalid document path.") from exc

  target_markdown = target_dir / "index.md"
  if target_dir == resolved_root or not target_markdown.is_file():
    raise FileNotFoundError(f'Document "{normalized}" was not found.')

  shutil.rmtree(target_dir)
  parent = target_dir.parent
  while parent != resolved_root and parent.is_dir() and not any(parent.iterdir()):
    parent.rmdir()
    parent = parent.parent

  return {"site_path": normalized, "status": "deleted"}


def _read_first_heading(markdown_file: Path) -> str:
  for line in markdown_file.read_text(encoding="utf-8", errors="ignore").splitlines():
    stripped = line.strip()
    if stripped.startswith("#"):
      return stripped.lstrip("#").strip() or markdown_file.parent.name.replace("-", " ").title()
  return markdown_file.parent.name.replace("-", " ").title()


def update_published_index(docs_root: Path) -> None:
  docs_root.mkdir(parents=True, exist_ok=True)
  entries: list[tuple[str, str]] = []
  for markdown_file in sorted(docs_root.rglob("index.md")):
    if markdown_file == docs_root / "index.md":
      continue
    rel_dir = markdown_file.parent.relative_to(docs_root).as_posix()
    entries.append((rel_dir, _read_first_heading(markdown_file)))

  lines = [
    "# Published Documents",
    "",
    "Documents published from the ITSD converter appear here.",
    "",
    "Use the **Converter** item in the site navigation to publish a new document directly into this site.",
    "",
  ]

  if entries:
    lines.extend(["## Available Documents", ""])
    for rel_dir, title in entries:
      lines.append(
        f'- [{title}]({rel_dir}/index.md) — `{rel_dir}` '
        f'<button type="button" class="delete-published-document" data-site-path="{rel_dir}">Delete</button>'
      )
  else:
    lines.extend([
      "## Available Documents",
      "",
      "No documents have been published yet.",
    ])

  (docs_root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def sync_published_docs_to_mkdocs() -> None:
  destination = MKDOCS_DOCS_DIR / "published"
  if PUBLISHED_DOCS_DIR.resolve() == destination.resolve():
    return
  if destination.exists():
    shutil.rmtree(destination)
  shutil.copytree(PUBLISHED_DOCS_DIR, destination)


def ensure_itsd_site_scaffold() -> None:
  MKDOCS_DOCS_DIR.mkdir(parents=True, exist_ok=True)
  (MKDOCS_DOCS_DIR / "stylesheets").mkdir(parents=True, exist_ok=True)
  (MKDOCS_DOCS_DIR / "javascripts").mkdir(parents=True, exist_ok=True)
  PUBLISHED_DOCS_DIR.mkdir(parents=True, exist_ok=True)

  def remove_readonly(function: Any, path: str, _: Any) -> None:
    Path(path).chmod(0o700)
    function(path)

  obsolete_paths = [
    MKDOCS_DOCS_DIR / "builder-profile.md",
    MKDOCS_DOCS_DIR / "contact.md",
    MKDOCS_DOCS_DIR / "converted",
    MKDOCS_DOCS_DIR / "documentation.md",
    MKDOCS_DOCS_DIR / "folder-manager.md",
    MKDOCS_DOCS_DIR / "faq.md",
    MKDOCS_DOCS_DIR / "faq",
    MKDOCS_DOCS_DIR / "downloads",
  ]
  for obsolete in obsolete_paths:
    if obsolete.is_dir():
      shutil.rmtree(obsolete, onerror=remove_readonly)
    elif obsolete.exists():
      obsolete.chmod(0o600)
      obsolete.unlink()

  MKDOCS_CONFIG_FILE.write_text(
    """site_name: ITSD Service Desk
site_description: Searchable IT support documentation and document conversion
theme:
  name: readthedocs
  highlightjs: false
  navigation_depth: 1
  titles_only: true
  prev_next_buttons_location: none
plugins:
  - search
markdown_extensions:
  - tables
  - fenced_code
extra_css:
  - stylesheets/extra.css
extra_javascript:
  - javascripts/delete-published.js
nav:
  - Home: index.md
  - Converter: /editor
  - Documents: published/index.md
""",
    encoding="utf-8",
  )

  (MKDOCS_DOCS_DIR / "index.md").write_text(
    """# ITSD Service Desk

This site provides a simple, searchable home for IT support documents.

## Services

- Convert PDF, DOCX, Markdown, and text files into Markdown.
- Preview converted content before publishing.
- Publish approved documents to the searchable documentation library.
- Browse and search published procedures, guides, and reference material.

## Get Started

[Open the document converter](/editor)

[Browse published documents](published/index.md)
""",
    encoding="utf-8",
  )

  (MKDOCS_DOCS_DIR / "stylesheets" / "extra.css").write_text(
    """body {
  color: #20252b;
  font-family: "Segoe UI", Arial, sans-serif;
}

.wy-nav-side {
  background: #263238;
}

.wy-side-nav-search {
  background: #1f5f78;
}

.wy-nav-content {
  max-width: 1040px;
}

.rst-content a {
  color: #176b87;
}

.rst-content h1,
.rst-content h2 {
  color: #172027;
}

.wy-menu-vertical li.toctree-l1 > ul,
.wy-menu-vertical .toctree-expand,
.rst-footer-buttons,
.rst-versions {
  display: none !important;
}

.delete-published-document {
  margin-left: 0.5rem;
  padding: 0.2rem 0.55rem;
  border: 1px solid #b91c1c;
  border-radius: 4px;
  background: #fff;
  color: #b91c1c;
  cursor: pointer;
}

.delete-published-document:hover {
  background: #b91c1c;
  color: #fff;
}
""",
    encoding="utf-8",
  )

  (MKDOCS_DOCS_DIR / "javascripts" / "delete-published.js").write_text(
    """document.addEventListener("click", async function (event) {
  const button = event.target.closest(".delete-published-document");
  if (!button) return;
  const sitePath = button.dataset.sitePath;
  if (!window.confirm("Delete " + sitePath + "? This cannot be undone.")) return;
  const publishSecret = window.prompt("Enter the publish secret to delete this document:");
  if (publishSecret === null) return;
  button.disabled = true;
  const form = new FormData();
  form.append("site_path", sitePath);
  form.append("publish_secret", publishSecret);
  const response = await fetch("/api/delete-published", { method: "POST", body: form });
  const result = await response.json().catch(function () { return {}; });
  if (!response.ok) {
    window.alert(result.detail || "Unable to delete the document.");
    button.disabled = false;
    return;
  }
  window.location.reload();
});
""",
    encoding="utf-8",
  )

  update_published_index(PUBLISHED_DOCS_DIR)
  sync_published_docs_to_mkdocs()


def build_itsd_site() -> None:
  ensure_itsd_site_scaffold()
  result = subprocess.run(
    [sys.executable, "-m", "mkdocs", "build", "-f", str(MKDOCS_CONFIG_FILE)],
    cwd=str(BASE_DIR),
    capture_output=True,
    text=True,
    check=False,
  )
  if result.returncode != 0:
    message = (result.stderr or result.stdout or "MkDocs build failed.").strip()
    raise RuntimeError(message)


def _is_external_link(target: str) -> bool:
  lowered = target.lower()
  return lowered.startswith(("http://", "https://", "mailto:", "data:", "#"))


def rewrite_assets_for_preview(markdown_text: str, job_id: str) -> str:
  pattern = re.compile(r"(!?\[[^\]]*\]\()([^\)\s]+)(\))")

  def repl(match: re.Match[str]) -> str:
    prefix, target, suffix = match.groups()
    clean_target = target.strip().strip("<>")
    if _is_external_link(clean_target):
      return match.group(0)

    normalized = clean_target.replace("\\", "/")
    while normalized.startswith("./"):
      normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    if not normalized or normalized.startswith("../"):
      return match.group(0)

    return f"{prefix}/api/docs-file/{job_id}/{normalized}{suffix}"

  return pattern.sub(repl, markdown_text)


def copy_markdown_companion_files(markdown_text: str, docs_dir: Path, companion_files: list[Path]) -> None:
  pattern = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
  referenced_paths: set[str] = set()

  for match in pattern.finditer(markdown_text):
    target = match.group(1).strip().strip("<>")
    if _is_external_link(target):
      continue
    normalized = target.replace("\\", "/")
    while normalized.startswith("./"):
      normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    if not normalized or normalized.startswith("../"):
      continue
    referenced_paths.add(normalized)

  companion_by_name = {path.name.lower(): path for path in companion_files}
  for relative_ref in referenced_paths:
    destination = (docs_dir / relative_ref).resolve()
    try:
      destination.relative_to(docs_dir.resolve())
    except ValueError:
      continue

    source = companion_by_name.get(Path(relative_ref).name.lower())
    if not source or not source.exists():
      continue

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def render_markdown_preview(markdown_text: str) -> str:
  return markdown.markdown(
    markdown_text,
    extensions=[
      "extra",
      "admonition",
      "attr_list",
      "md_in_html",
      "sane_lists",
      "tables",
      "fenced_code",
    ],
  )


def _markdown_asset_refs(md_text: str) -> list[str]:
  refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md_text)
  cleaned: list[str] = []
  for ref in refs:
    target = ref.strip().strip("<>").replace("\\", "/")
    if target.startswith(("http://", "https://", "mailto:", "data:", "#")):
      continue
    cleaned.append(target)
  return cleaned


def _validate_basic_markdown_output(markdown_text: str, docs_dir: Path) -> dict[str, Any]:
  missing_assets: list[str] = []
  for ref in _markdown_asset_refs(markdown_text):
    if ref.startswith("assets/"):
      if not (docs_dir / ref).exists():
        missing_assets.append(ref)

  unresolved = bool(re.search(r"!\[\]\[image_|missing[_-]asset|unresolved", markdown_text, flags=re.IGNORECASE))
  # Detect converter-environment leakage while allowing legitimate user content paths.
  has_abs_paths = bool(
    re.search(
      r"(/tmp/|/private/var/|/var/folders/|\\\\Users\\\\[^\\\\]+\\\\AppData\\\\Local\\\\Temp\\\\|mkdocs-convert-)",
      markdown_text,
      flags=re.IGNORECASE,
    )
  )

  passed = bool(markdown_text.strip()) and not missing_assets and not unresolved and not has_abs_paths
  return {
    "passed": passed,
    "missing_assets": missing_assets,
    "unresolved_references": ["placeholder"] if unresolved else [],
    "has_absolute_paths": has_abs_paths,
  }


def _create_non_pdf_manifest_and_quality(
  *,
  source_file: Path,
  output_dir: Path,
  markdown_content: str,
  effective_config: dict[str, Any],
) -> tuple[Path, Path]:
  slug = slugify(source_file.stem)
  manifest_path = output_dir / f"{slug}-manifest.json"
  quality_path = output_dir / f"{slug}-quality-report.json"

  docs_dir = output_dir / "docs"
  validation = _validate_basic_markdown_output(markdown_content, docs_dir)

  strategy = {
    ".docx": "docx_native",
    ".md": "markdown_passthrough",
    ".txt": "text_native",
  }.get(source_file.suffix.lower(), "generic_text")

  fidelity = "moderate" if validation["passed"] else "review_required"
  technical = "passed" if validation["passed"] else "failed"

  manifest = {
    "source": source_file.name,
    "output_markdown": "index.md",
    "page_count": 1,
    "pages_with_native_text": [1],
    "pages_with_ocr": [],
    "images_extracted": sorted(p.name for p in (docs_dir / "assets").glob("*") if p.is_file()) if (docs_dir / "assets").exists() else [],
    "image_placements": [],
    "regions_rendered": [],
    "tables_detected": [],
    "warnings": [],
    "validation": validation,
    "technical_status": technical,
    "fidelity_status": fidelity,
    "document_result": {
      "source_path": source_file.name,
      "page_count": 1,
      "pages": [
        {
          "page_number": 1,
          "width": 0,
          "height": 0,
          "native_text_available": bool(markdown_content.strip()),
          "native_character_count": len(markdown_content),
          "embedded_image_count": len(_markdown_asset_refs(markdown_content)),
          "vector_drawing_count": 0,
          "classifications": [{"label": "native_text", "confidence": "medium", "evidence": ["non_pdf_source"], "rule": "format_dispatch"}],
          "regions": [],
          "candidates": [
            {
              "candidate_id": "p1-native",
              "strategy": strategy,
              "page_number": 1,
              "regions": [],
              "native_text_coverage": 1.0 if markdown_content.strip() else 0.0,
              "reading_order_score": 0.9,
              "suspicious_glyph_count": 0,
              "chart_text_leakage_count": 0,
              "duplicate_content_score": 0.0,
              "fallback_area_ratio": 0.0,
              "unresolved_asset_count": len(validation["missing_assets"]),
              "score_components": {"native_text_coverage": 1.0 if markdown_content.strip() else 0.0},
              "total_score": 1.0 if markdown_content.strip() else 0.0,
              "rejection_reasons": [],
            }
          ],
          "selected_candidate": "p1-native",
          "fallback_records": [],
          "semantic_coverage": 1.0 if markdown_content.strip() else 0.0,
          "visual_coverage": 0.0,
          "accessible_coverage": 1.0 if markdown_content.strip() else 0.0,
          "unhandled_coverage": 0.0 if markdown_content.strip() else 1.0,
          "technical_status": technical,
          "fidelity_status": fidelity,
          "review_reasons": [] if validation["passed"] else ["non_pdf_validation_failed"],
        }
      ],
      "assets": sorted(p.name for p in (docs_dir / "assets").glob("*") if p.is_file()) if (docs_dir / "assets").exists() else [],
      "warnings": [],
      "technical_status": technical,
      "fidelity_status": fidelity,
    },
    "candidate_scoring": {
      "weights_note": "Non-PDF normalized manifest uses deterministic single-candidate scoring.",
      "components": ["native_text_coverage"],
    },
    "effective_configuration": effective_config,
  }

  quality = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "source": source_file.name,
    "technical_status": technical,
    "fidelity_status": fidelity,
    "effective_configuration": effective_config,
    "provider_availability": {
      "tesseract_available": bool(shutil.which("tesseract")),
      "markitdown_used": bool(effective_config.get("prefer_markitdown", False)),
    },
    "page_summaries": [
      {
        "page_number": 1,
        "classifications": [{"label": "native_text", "confidence": "medium", "evidence": ["non_pdf_source"], "rule": "format_dispatch"}],
        "selected_candidate": "p1-native",
        "candidate_scores": [
          {
            "candidate_id": "p1-native",
            "strategy": strategy,
            "total_score": 1.0 if markdown_content.strip() else 0.0,
            "score_components": {"native_text_coverage": 1.0 if markdown_content.strip() else 0.0},
            "rejection_reasons": [],
          }
        ],
        "fallback_records": [],
        "semantic_coverage": 1.0 if markdown_content.strip() else 0.0,
        "visual_coverage": 0.0,
        "accessible_coverage": 1.0 if markdown_content.strip() else 0.0,
        "unhandled_coverage": 0.0 if markdown_content.strip() else 1.0,
        "technical_status": technical,
        "fidelity_status": fidelity,
        "review_reasons": [] if validation["passed"] else ["non_pdf_validation_failed"],
      }
    ],
    "warnings": [],
    "artifact_hints": {
      "markdown": "index.md",
      "manifest": manifest_path.name,
      "assets_dir": "assets",
    },
  }

  manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
  quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")
  return manifest_path, quality_path


def run_authoritative_conversion_service(
  *,
  source_file: Path,
  output_dir: Path,
  pdf_mode: str,
  tesseract_cmd: str | None,
  prefer_markitdown: bool,
  improve_markdown: bool,
  companion_files: list[Path],
) -> dict[str, Any]:
  """Single authoritative conversion path used by API and direct service callers."""
  assets_dir = output_dir / "docs" / "assets"
  ensure_assets_folder(assets_dir)

  context = ConversionContext(
    output_dir=output_dir,
    assets_dir=assets_dir,
    overwrite=True,
    pdf_mode=pdf_mode,
    tesseract_cmd=tesseract_cmd,
    prefer_markitdown=prefer_markitdown,
    improve_markdown=improve_markdown,
  )

  markdown_content = convert_file_to_markdown(source_file, context)
  output_file = build_mkdocs_project(output_dir, markdown_content)

  if source_file.suffix.lower() == ".md":
    copy_markdown_companion_files(markdown_content, output_dir / "docs", companion_files)

  manifest_path = output_dir / f"{slugify(source_file.stem)}-manifest.json"
  quality_report_path = output_dir / f"{slugify(source_file.stem)}-quality-report.json"

  # Record effective configuration for deterministic endpoint/direct comparisons.
  effective_config = {
    "pdf_mode": pdf_mode,
    "prefer_markitdown": prefer_markitdown,
    "improve_markdown": improve_markdown,
    "strict_validation": True,
    "render_dpi": context.render_dpi,
    "preserve_page_markers": context.preserve_page_markers,
    "allow_inline_html": context.allow_inline_html,
    "tesseract_cmd_configured": bool(tesseract_cmd),
  }

  if manifest_path.exists():
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["effective_configuration"] = effective_config
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

  if quality_report_path.exists():
    q = json.loads(quality_report_path.read_text(encoding="utf-8"))
    q["effective_configuration"] = effective_config
    quality_report_path.write_text(json.dumps(q, indent=2), encoding="utf-8")

  if not manifest_path.exists() or not quality_report_path.exists():
    manifest_path, quality_report_path = _create_non_pdf_manifest_and_quality(
      source_file=source_file,
      output_dir=output_dir,
      markdown_content=markdown_content,
      effective_config=effective_config,
    )

  manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
  return {
    "output_file": output_file,
    "assets_dir": assets_dir,
    "manifest_path": manifest_path,
    "quality_report_path": quality_report_path,
    "technical_status": manifest_payload.get("technical_status"),
    "fidelity_status": manifest_payload.get("fidelity_status"),
  }


async def process_conversion(job_id: str) -> None:
    cleanup_stale_jobs()
    job = jobs[job_id]

    try:
        job["status"] = "processing"
        job["progress"] = 20
        job["message"] = "Preparing conversion…"

        source_file: Path = job["source_file"]
        output_dir: Path = job["output_dir"]

        job["progress"] = 55
        job["message"] = "Converting file…"

        service_result = await asyncio.to_thread(
            run_authoritative_conversion_service,
            source_file=source_file,
            output_dir=output_dir,
            pdf_mode=job["pdf_mode"],
            tesseract_cmd=job.get("tesseract_cmd"),
            prefer_markitdown=job.get("prefer_markitdown", True),
            improve_markdown=job.get("improve_markdown", False),
            companion_files=job.get("companion_files", []),
        )

        output_file = Path(service_result["output_file"])

        manifest_path = Path(service_result["manifest_path"])
        quality_path = Path(service_result["quality_report_path"])
        if not manifest_path.exists():
            raise RuntimeError("Expected manifest file missing after conversion.")
        if not quality_path.exists():
            raise RuntimeError("Expected quality report missing after conversion.")

        job["progress"] = 80
        job["message"] = "Packaging files…"

        zip_path = output_dir / f"{source_file.stem}_converted.zip"
        await asyncio.to_thread(build_zip, output_dir, zip_path)

        preview_markdown = output_file.read_text(encoding="utf-8", errors="ignore")
        preview_markdown = rewrite_assets_for_preview(preview_markdown, job_id)
        preview_html = render_markdown_preview(preview_markdown)

        job["output_file"] = output_file
        job["zip_path"] = zip_path
        job["manifest_path"] = manifest_path
        job["quality_report_path"] = quality_path
        job["preview_html"] = preview_html
        job["status"] = "completed"
        job["progress"] = 100
        job["message"] = "Conversion complete."
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        job["status"] = "failed"
        job["progress"] = 100
        job["message"] = "Conversion failed."
        job["error"] = message
        job["suggestion"] = suggest_fix(message)


@app.post("/api/convert")
async def convert(
    files: list[UploadFile] = File(...),
    workflow: str = Form("convert"),
    pdf_mode: str = Form(DEFAULT_PDF_MODE),
) -> JSONResponse:
  cleanup_stale_jobs()
  if not files:
    raise HTTPException(status_code=400, detail="No files uploaded.")
  if len(files) > MAX_FILES_PER_REQUEST:
    raise HTTPException(status_code=400, detail=f"Too many files. Maximum is {MAX_FILES_PER_REQUEST}.")

  primary_upload: UploadFile | None = None
  companion_uploads: list[UploadFile] = []

  markdown_uploads = [upload for upload in files if Path(upload.filename or "").suffix.lower() == ".md"]
  if markdown_uploads:
    primary_upload = markdown_uploads[0]
    companion_uploads = [upload for upload in files if upload is not primary_upload]
  else:
    primary_upload = files[0]
    companion_uploads = files[1:]

  suffix = Path(primary_upload.filename or "").suffix.lower()
  if suffix not in SUPPORTED_UPLOADS:
    raise HTTPException(status_code=400, detail="Unsupported file format. Use PDF, DOCX, TXT, or Markdown.")

  if workflow not in {"convert", "polish_markdown"}:
    raise HTTPException(status_code=400, detail="Invalid workflow requested.")

  if pdf_mode not in SUPPORTED_PDF_MODES:
    raise HTTPException(status_code=400, detail="Invalid PDF mode requested.")

  if suffix != ".md" and workflow == "polish_markdown":
    raise HTTPException(status_code=400, detail="Markdown polishing is only available for .md files.")

  temp_dir = Path(tempfile.mkdtemp(prefix="mkdocs-convert-"))
  safe_name = _safe_upload_name(primary_upload.filename or f"upload{suffix}")
  source_file = temp_dir / safe_name
  companion_files: list[Path] = []

  raw = await primary_upload.read()
  if len(raw) > MAX_UPLOAD_BYTES:
    raise HTTPException(
      status_code=400,
      detail=f"File too large. Maximum allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
    )
  source_file.write_bytes(raw)

  for upload in companion_uploads:
    upload_name = _safe_upload_name(upload.filename or "")
    if not upload_name:
      continue
    companion_path = temp_dir / upload_name
    blob = await upload.read()
    if len(blob) > MAX_UPLOAD_BYTES:
      raise HTTPException(
        status_code=400,
        detail=f"Companion file too large. Maximum allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
      )
    companion_path.write_bytes(blob)
    companion_files.append(companion_path)

  job_id = uuid.uuid4().hex
  jobs[job_id] = {
    "job_id": job_id,
    "created_at": now_ts(),
    "status": "queued",
    "progress": 10,
    "message": "File uploaded. Waiting for conversion…",
    "temp_dir": temp_dir,
    "source_file": source_file,
    "pdf_mode": pdf_mode if suffix == ".pdf" else DEFAULT_PDF_MODE,
    "tesseract_cmd": None,
    "prefer_markitdown": True,
    "improve_markdown": workflow == "polish_markdown",
    "companion_files": companion_files,
    "output_dir": temp_dir / "output",
    "output_file": None,
    "zip_path": None,
    "preview_html": None,
    "error": None,
    "suggestion": None,
  }

  asyncio.create_task(process_conversion(job_id))

  return JSONResponse(
    {
      "job_id": job_id,
      "status_url": f"/api/status/{job_id}",
      "preview_url": f"/preview/{job_id}",
      "download_url": f"/api/download/{job_id}",
    }
  )


@app.get("/api/status/{job_id}", response_model=StatusPayload)
async def status(job_id: str) -> StatusPayload:
    cleanup_stale_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already cleaned up.")

    return StatusPayload(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        preview_url=f"/preview/{job_id}" if job["status"] == "completed" else None,
        download_url=f"/api/download/{job_id}" if job["status"] == "completed" else None,
        error=job.get("error"),
        suggestion=job.get("suggestion"),
    )


@app.get("/preview/{job_id}", response_class=HTMLResponse)
async def preview(job_id: str) -> HTMLResponse:
    cleanup_stale_jobs()
    job = jobs.get(job_id)
    if not job:
        return HTMLResponse("<h2>Preview not found</h2><p>Job was cleaned up or does not exist.</p>", status_code=404)

    if job["status"] != "completed":
        return HTMLResponse("<h2>Preview not ready</h2><p>Conversion is still in progress.</p>", status_code=425)

    html_body = job.get("preview_html") or "<p>No preview available.</p>"
    page = f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Converted Markdown Preview</title>
  <style>
    body {{ font-family: "Segoe UI", Arial, sans-serif; max-width: 960px; margin: 0 auto; padding: 2rem 1.25rem 4rem; line-height: 1.65; background: #ffffff; color: #1f2937; }}
    a {{ color: #0f4c81; }}
    img {{ max-width: 100%; height: auto; border: 1px solid #d1d5db; border-radius: 6px; margin: 1rem 0 1.5rem; }}
    pre {{ background: #f8fafc; padding: 14px; border-radius: 6px; overflow: auto; border: 1px solid #d1d5db; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    details {{ border: 1px solid #d1d5db; border-radius: 6px; padding: .85rem 1rem; background: #f8fafc; margin: 1rem 0; }}
    summary {{ cursor: pointer; font-weight: 700; }}
    .topbar {{ margin-bottom: 20px; display: flex; gap: 1rem; flex-wrap: wrap; align-items: center; padding: 0 0 1rem; border-bottom: 1px solid #d1d5db; background: #ffffff; position: sticky; top: 0; }}
  </style>
</head>
<body>
  <div class=\"topbar\">
    <a href=\"/editor\">← Back to converter</a>
    <span>•</span>
    <a href=\"/api/download-md/{job_id}\">Download Markdown (.md)</a>
    <span>•</span>
    <a href=\"/api/download/{job_id}\">Download full package (.zip)</a>
  </div>
  {html_body}
</body>
</html>
"""
    return HTMLResponse(page)


@app.get("/api/download/{job_id}")
async def download(job_id: str) -> Response:
    cleanup_stale_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already cleaned up.")

    if job["status"] != "completed":
        raise HTTPException(status_code=425, detail="Conversion not completed yet.")

    zip_path: Optional[Path] = job.get("zip_path")
    if not zip_path or not zip_path.exists():
        raise HTTPException(status_code=404, detail="Converted file package not available.")

    payload = zip_path.read_bytes()
    filename = zip_path.name

    background = BackgroundTask(cleanup_job, job_id)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        background=background,
    )


@app.get("/api/download-md/{job_id}")
async def download_markdown(job_id: str) -> Response:
    cleanup_stale_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already cleaned up.")

    if job["status"] != "completed":
        raise HTTPException(status_code=425, detail="Conversion not completed yet.")

    output_file: Optional[Path] = job.get("output_file")
    if not output_file or not output_file.exists():
        raise HTTPException(status_code=404, detail="Converted markdown file not available.")

    payload = output_file.read_bytes()
    source_file: Path = job["source_file"]
    filename = f"{source_file.stem}_converted.md"

    background = BackgroundTask(cleanup_job, job_id)
    return Response(
        content=payload,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        background=background,
    )


@app.get("/api/assets/{job_id}/{asset_name:path}")
async def preview_asset(job_id: str, asset_name: str) -> Response:
    cleanup_stale_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already cleaned up.")

    output_dir: Path = job["output_dir"]
    asset_path = output_dir / "docs" / "assets" / asset_name
    if not asset_path.exists() or not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found.")

    media_type = "application/octet-stream"
    suffix = asset_path.suffix.lower()
    if suffix == ".png":
        media_type = "image/png"
    elif suffix in {".jpg", ".jpeg"}:
        media_type = "image/jpeg"
    elif suffix == ".gif":
        media_type = "image/gif"
    elif suffix == ".webp":
        media_type = "image/webp"

    return Response(content=asset_path.read_bytes(), media_type=media_type)

@app.get("/api/docs-file/{job_id}/{file_path:path}")
async def docs_file(job_id: str, file_path: str) -> Response:
    cleanup_stale_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already cleaned up.")

    docs_dir = (Path(job["output_dir"]) / "docs").resolve()
    target_path = (docs_dir / file_path).resolve()
    try:
        target_path.relative_to(docs_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid docs file path.") from exc

    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="Referenced docs file not found.")

    media_type = "application/octet-stream"
    suffix = target_path.suffix.lower()
    if suffix == ".png":
        media_type = "image/png"
    elif suffix in {".jpg", ".jpeg"}:
        media_type = "image/jpeg"
    elif suffix == ".gif":
        media_type = "image/gif"
    elif suffix == ".webp":
        media_type = "image/webp"
    elif suffix == ".svg":
        media_type = "image/svg+xml"

    return Response(content=target_path.read_bytes(), media_type=media_type)


@app.get("/api/preview-content/{job_id}")
async def preview_content(job_id: str) -> JSONResponse:
    """Return the rendered HTML and raw Markdown for the split-pane editor."""
    cleanup_stale_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already cleaned up.")
    if job["status"] != "completed":
        raise HTTPException(status_code=425, detail="Conversion not completed yet.")

    html_body = job.get("preview_html") or "<p>No preview available.</p>"
    raw_md = ""
    output_file: Optional[Path] = job.get("output_file")
    if output_file and output_file.exists():
        raw_md = output_file.read_text(encoding="utf-8", errors="ignore")

    return JSONResponse({"html": html_body, "markdown": raw_md})


@app.post("/api/publish/{job_id}")
async def publish_to_site(
  job_id: str,
  publish_secret: str = Form(""),
  document_name: str = Form(""),
) -> JSONResponse:
  require_mutation_secret(publish_secret, "Publishing")
  cleanup_stale_jobs()
  job = jobs.get(job_id)
  if not job:
    raise HTTPException(status_code=404, detail="Job not found or already cleaned up.")
  if job["status"] != "completed":
    raise HTTPException(status_code=425, detail="Conversion not completed yet.")

  output_file: Optional[Path] = job.get("output_file")
  if not output_file or not output_file.exists():
    raise HTTPException(status_code=404, detail="Converted markdown file not available.")

  source_assets_dir = Path(job["output_dir"]) / "docs" / "assets"
  normalized_doc = slugify(document_name) if document_name.strip() else slugify(Path(job["source_file"]).stem)

  def publish_and_build() -> dict[str, str]:
    with site_mutation_lock:
      result = publish_markdown_to_mkdocs_site(
        source_markdown=output_file,
        source_assets_dir=source_assets_dir,
        docs_root=PUBLISHED_DOCS_DIR,
        site_path=normalized_doc,
      )
      update_published_index(PUBLISHED_DOCS_DIR)
      build_itsd_site()
      return result

  try:
    published = await asyncio.to_thread(publish_and_build)
  except FileExistsError as exc:
    raise HTTPException(status_code=409, detail=str(exc)) from exc
  except Exception as exc:  # noqa: BLE001
    raise HTTPException(status_code=500, detail=f"Failed to publish to site: {exc}") from exc

  job["published_url"] = published["published_url"]
  return JSONResponse(
    {
      "status": "published",
      "message": "Document published to the ITSD site.",
      **published,
    }
  )


@app.post("/api/delete-published")
async def delete_from_site(
  site_path: str = Form(""),
  publish_secret: str = Form(""),
) -> JSONResponse:
  require_mutation_secret(publish_secret, "Deletion")

  def delete_and_build() -> dict[str, str]:
    with site_mutation_lock:
      result = delete_published_document(
        docs_root=PUBLISHED_DOCS_DIR,
        site_path=site_path,
      )
      update_published_index(PUBLISHED_DOCS_DIR)
      build_itsd_site()
      return result

  try:
    deleted = await asyncio.to_thread(delete_and_build)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  except FileNotFoundError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
  except Exception as exc:  # noqa: BLE001
    raise HTTPException(status_code=500, detail=f"Failed to delete document: {exc}") from exc

  return JSONResponse({**deleted, "message": "Document deleted from the ITSD site."})


_EDITOR_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Document Converter</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #ffffff;
    --panel: #ffffff;
    --border: #d1d5db;
    --accent: #0f4c81;
    --accent-hover: #0b3a62;
    --text: #1f2937;
    --muted: #6b7280;
    --success: #0f4c81;
    --warn: #b45309;
    --danger: #b91c1c;
    --radius: 6px;
  }
  html, body { height: 100%; overflow: hidden; background: var(--bg); color: var(--text); font-family: "Segoe UI", Arial, sans-serif; font-size: 14px; }

  /* Layout */
  #root { display: flex; flex-direction: column; height: 100%; max-width: 1180px; margin: 0 auto; }
  header { flex: 0 0 auto; display: flex; align-items: center; gap: 12px; padding: 16px 20px 14px; background: var(--panel); border-bottom: 1px solid var(--border); }
  header h1 { font-size: 16px; font-weight: 600; color: #111827; }
  header nav { display: flex; gap: 14px; align-items: center; }
  header nav a { color: var(--accent); text-decoration: none; font-size: 12px; }
  header nav a:hover { text-decoration: underline; }
  header .spacer { flex: 1; }
  #main { flex: 1 1 0; display: flex; min-height: 0; }

  /* Left panel */
  #left { flex: 0 0 340px; display: flex; flex-direction: column; gap: 16px; padding: 24px 20px; border-right: 1px solid var(--border); overflow-y: auto; background: #fcfcfd; }

  /* Drop zone */
  #dropzone {
    border: 1px dashed var(--border);
    border-radius: var(--radius);
    padding: 32px 20px;
    text-align: center;
    cursor: pointer;
    transition: border-color .2s, background .2s;
    background: #f8fafc;
    position: relative;
  }
  #dropzone.hover { border-color: var(--accent); background: #eef4f8; }
  #dropzone input[type=file] { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
  #dropzone .icon { font-size: 36px; margin-bottom: 10px; }
  #dropzone p { color: var(--muted); line-height: 1.5; }
  #dropzone p strong { color: var(--text); }
  #file-info { font-size: 12px; color: var(--muted); }
  #file-info span { color: var(--text); font-weight: 600; }

  .section-label { font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
  .info-card { border: 1px solid var(--border); border-radius: var(--radius); padding: 14px; background: #ffffff; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); }
  .info-card p { color: var(--muted); line-height: 1.55; font-size: 13px; }
  .format-badges { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
  .format-badge { padding: 5px 10px; border-radius: 999px; border: 1px solid #cbd5e1; background: #f8fafc; color: #334155; font-size: 12px; font-weight: 700; }

  /* Convert button */
  #convert-btn {
    width: 100%; padding: 10px; border-radius: var(--radius); border: none;
    background: var(--accent); color: #fff; font-size: 14px; font-weight: 600;
    cursor: pointer; transition: background .15s;
  }
  #convert-btn:hover:not(:disabled) { background: var(--accent-hover); }
  #convert-btn:disabled { opacity: .45; cursor: not-allowed; }

  /* Progress */
  #progress-wrap { display: none; flex-direction: column; gap: 8px; }
  #progress-wrap.visible { display: flex; }
  #progress-bar-bg { height: 6px; background: #e5e7eb; border-radius: 999px; overflow: hidden; }
  #progress-bar { height: 100%; width: 0%; background: var(--accent); border-radius: 999px; transition: width .3s; }
  #status-msg { font-size: 12px; color: var(--muted); }

  /* Download */
  #download-btn {
    display: block; width: 100%; padding: 9px; border-radius: var(--radius); border: 1px solid var(--success);
    background: transparent; color: var(--success); font-size: 13px; font-weight: 600; cursor: pointer;
    transition: background .15s;
  }
  #download-btn:hover { background: #eef4f8; }

  #pdf-mode:focus { outline: 2px solid rgba(15, 76, 129, 0.15); outline-offset: 1px; border-color: var(--accent); }
  #result-actions { display: none; }
  #result-actions.visible { display: block; }
  .action-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  #publish-btn {
    width: 100%; padding: 9px; border-radius: var(--radius); border: none;
    background: var(--accent); color: #ffffff; font-size: 13px; font-weight: 600; cursor: pointer;
    transition: background .15s;
  }
  #publish-btn:hover:not(:disabled) { background: var(--accent-hover); }
  #publish-btn:disabled { opacity: .45; cursor: not-allowed; }
  #publish-status { font-size: 12px; line-height: 1.5; color: var(--muted); margin-top: 10px; }
  #publish-status a { color: var(--accent); }
  #error-box { display: none; background: #fef2f2; border: 1px solid #fecaca; border-radius: var(--radius); padding: 10px 12px; font-size: 12px; color: var(--danger); line-height: 1.5; }
  #error-box.visible { display: block; }

  /* Right panel */
  #right { flex: 1 1 0; display: flex; flex-direction: column; min-width: 0; background: #ffffff; }
  #view-tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border); background: var(--panel); }
  .tab-btn {
    padding: 10px 18px; border: none; background: transparent; color: var(--muted);
    font-size: 13px; cursor: pointer; border-bottom: 2px solid transparent;
    transition: color .15s;
  }
  .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
  #preview-pane, #raw-pane { flex: 1 1 0; overflow: auto; padding: 30px 40px; display: none; }
  #preview-pane.active, #raw-pane.active { display: block; }
  #preview-content { line-height: 1.7; max-width: 960px; }
  #preview-content h1,h2,h3,h4 { margin: 1.4em 0 .5em; font-weight: 700; }
  #preview-content h1 { font-size: 1.8em; border-bottom: 1px solid var(--border); padding-bottom: .3em; }
  #preview-content h2 { font-size: 1.4em; border-bottom: 1px solid var(--border); padding-bottom: .2em; }
  #preview-content p { margin: .7em 0; }
  #preview-content img { max-width: 100%; border-radius: 6px; border: 1px solid var(--border); margin: 8px 0; }
  #preview-content table { border-collapse: collapse; width: 100%; margin: 1em 0; }
  #preview-content th, #preview-content td { border: 1px solid var(--border); padding: 7px 12px; text-align: left; }
  #preview-content th { background: #f3f4f6; font-weight: 700; }
  #preview-content code { background: #f8fafc; border: 1px solid var(--border); border-radius: 4px; padding: 1px 5px; font-size: .9em; }
  #preview-content pre { background: #f8fafc; border: 1px solid var(--border); border-radius: 6px; padding: 14px 16px; overflow: auto; margin: 1em 0; }
  #preview-content pre code { background: none; border: none; padding: 0; }
  #preview-content blockquote { border-left: 3px solid var(--accent); padding-left: 14px; color: var(--muted); margin: 1em 0; }
  #raw-pane textarea { width: 100%; height: 100%; max-width: 960px; background: #ffffff; border: none; color: var(--text); font-family: 'Fira Code', 'Cascadia Code', monospace; font-size: 13px; resize: none; outline: none; line-height: 1.6; }
  #pdf-mode { width:100%; background:#ffffff; color:var(--text); border:1px solid var(--border); border-radius:6px; padding:8px; margin-bottom:8px; }

  @media (max-width: 980px) {
    #main { flex-direction: column; }
    #left { flex: 0 0 auto; border-right: none; border-bottom: 1px solid var(--border); }
    #preview-pane, #raw-pane { padding: 20px; }
  }
  #empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--muted); text-align: center; gap: 12px; }
  #empty-state .big { font-size: 48px; color: #94a3b8; }
</style>
</head>
<body>
<div id="root">
  <header>
    <h1>Document Converter</h1>
    <div class="spacer"></div>
    <nav>
      <a href="/docs/">Site Home</a>
      <a href="/docs/published/">Documents</a>
    </nav>
  </header>
  <div id="main">
    <!-- LEFT: controls -->
    <div id="left">
      <div id="dropzone" id="dz">
        <input type="file" id="file-input" accept=".pdf,.docx,.txt,.md,image/*" multiple />
        <div class="icon">⬆️</div>
        <p><strong>Drop a file here</strong><br/>or click to browse<br/><small>PDF · DOCX · TXT · MD · companion images</small></p>
      </div>
      <div id="file-info" style="display:none">File: <span id="fname"></span></div>

      <button id="convert-btn" disabled>Convert</button>

      <div id="pdf-mode-wrap" class="info-card" style="display:none; padding:10px 12px;">
        <div class="section-label" style="margin-bottom:6px;">PDF Mode</div>
        <select id="pdf-mode" style="width:100%; background:#0f1420; color:var(--text); border:1px solid var(--border); border-radius:8px; padding:8px; margin-bottom:8px;">
          <option value="hybrid" selected>Balanced (image + best available text)</option>
          <option value="ocr">OCR-first (best for scanned/gibberish PDFs)</option>
          <option value="visual">Visual-first (image pages, minimal text noise)</option>
        </select>
        <p style="font-size:12px; color:var(--muted); line-height:1.4;">
          Use OCR-first for messy extracted text. Use Visual-first when you mostly want faithful page snapshots.
        </p>
      </div>

      <div id="progress-wrap">
        <div id="progress-bar-bg"><div id="progress-bar"></div></div>
        <div id="status-msg">Waiting…</div>
      </div>

      <div id="result-actions" class="info-card">
        <div class="section-label">Document Ready</div>
        <p style="font-size:12px; color:var(--muted); margin-bottom:10px;">Review the preview, then download the Markdown or publish it to Documents.</p>
        <div class="action-row">
          <button id="download-btn">Download Markdown</button>
          <button id="publish-btn" disabled>Publish to Documents</button>
        </div>
        <input id="publish-secret" type="password" placeholder="Publish secret (if required)" style="display:none; width:100%; padding:8px 10px; border-radius:var(--radius); border:1px solid var(--border); margin-top:8px; background:#fff; color:var(--text); font-size:12px;" />
        <div id="publish-status"></div>
      </div>

      <div id="error-box"></div>
    </div>

    <!-- RIGHT: preview -->
    <div id="right">
      <div id="view-tabs">
        <button class="tab-btn active" data-tab="preview">Rendered Preview</button>
        <button class="tab-btn" data-tab="raw">Raw Markdown</button>
      </div>
      <div id="preview-pane" class="active">
        <div id="empty-state">
          <div class="big">📋</div>
          <div>Converted or polished Markdown preview will appear here</div>
        </div>
        <div id="preview-content" style="display:none"></div>
      </div>
      <div id="raw-pane">
        <textarea id="raw-md" readonly placeholder="Raw Markdown will appear here after conversion…"></textarea>
      </div>
    </div>
  </div>
</div>

<script>
(function () {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const fileInfo = document.getElementById('file-info');
  const fnameEl = document.getElementById('fname');
  const convertBtn = document.getElementById('convert-btn');
  const progressWrap = document.getElementById('progress-wrap');
  const progressBar = document.getElementById('progress-bar');
  const statusMsg = document.getElementById('status-msg');
  const errorBox = document.getElementById('error-box');
  const downloadBtn = document.getElementById('download-btn');
  const resultActions = document.getElementById('result-actions');
  const publishBtn = document.getElementById('publish-btn');
  const publishSecret = document.getElementById('publish-secret');
  const publishStatus = document.getElementById('publish-status');
  const pdfModeWrap = document.getElementById('pdf-mode-wrap');
  const pdfModeSelect = document.getElementById('pdf-mode');
  const previewContent = document.getElementById('preview-content');
  const emptyState = document.getElementById('empty-state');
  const rawMd = document.getElementById('raw-md');
  const tabBtns = document.querySelectorAll('.tab-btn[data-tab]');
  const previewPane = document.getElementById('preview-pane');
  const rawPane = document.getElementById('raw-pane');

  let selectedFiles = [];
  let pollInterval = null;
  let currentJobId = null;
  let publishName = '';

  function slugifySitePath(value) {
    return (value || '')
      .toLowerCase()
      .replace(/\.md$/i, '')
      .replace(/[^a-z0-9/_ -]+/g, '')
      .split(/[\\/]+/)
      .map(part => part.trim().replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^[-]+|[-]+$/g, ''))
      .filter(Boolean)
      .join('/');
  }

  // --- Drag/drop ---
  dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('hover'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('hover'));
  dropzone.addEventListener('drop', e => {
    e.preventDefault();
    dropzone.classList.remove('hover');
    const files = Array.from(e.dataTransfer.files || []);
    if (files.length) setFiles(files);
  });
  fileInput.addEventListener('change', () => {
    const files = Array.from(fileInput.files || []);
    if (files.length) setFiles(files);
  });

  function setFiles(files) {
    selectedFiles = files;
    const primary = files.find(f => /\.(pdf|docx|txt|md)$/i.test(f.name)) || files[0];
    const isMarkdown = !!primary && primary.name.toLowerCase().endsWith('.md');
    const isPdf = !!primary && primary.name.toLowerCase().endsWith('.pdf');
    const extras = Math.max(0, files.length - 1);
    fnameEl.textContent = primary.name + '  (' + (primary.size / 1024).toFixed(1) + ' KB)' + (extras ? `  + ${extras} companion file${extras > 1 ? 's' : ''}` : '');
    fileInfo.style.display = 'block';
    convertBtn.disabled = false;
    convertBtn.textContent = isMarkdown ? 'Preview Markdown' : 'Convert';
    pdfModeWrap.style.display = isPdf ? 'block' : 'none';
    publishName = slugifySitePath(primary.name.replace(/\.[^.]+$/, '')).split('/').pop();
    clearResult();
  }

  // --- Tabs ---
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (btn.dataset.tab === 'preview') {
        previewPane.classList.add('active'); rawPane.classList.remove('active');
      } else {
        rawPane.classList.add('active'); previewPane.classList.remove('active');
      }
    });
  });

  // --- Convert ---
  async function startConversion() {
    if (!selectedFiles.length) return;
    clearResult();
    convertBtn.disabled = true;
    publishBtn.disabled = true;
    progressWrap.classList.add('visible');
    setProgress(10, 'Uploading…');

    const fd = new FormData();
    selectedFiles.forEach(file => fd.append('files', file));
    fd.append('workflow', 'convert');
    fd.append('pdf_mode', pdfModeSelect.value || 'hybrid');

    try {
      const res = await fetch('/api/convert', { method: 'POST', body: fd });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed.' }));
        showError(err.detail || 'Upload failed.');
        convertBtn.disabled = false;
        return;
      }
      const data = await res.json();
      currentJobId = data.job_id;
      pollStatus(data.job_id);
    } catch (e) {
      showError('Network error: ' + e.message);
      convertBtn.disabled = false;
    }
  }

  convertBtn.addEventListener('click', startConversion);

  function pollStatus(jobId) {
    clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
      try {
        const res = await fetch('/api/status/' + jobId);
        if (!res.ok) { clearInterval(pollInterval); showError('Status check failed.'); return; }
        const data = await res.json();
        setProgress(data.progress, data.message);
        if (data.status === 'completed') {
          clearInterval(pollInterval);
          await loadPreview(jobId);
          resultActions.classList.add('visible');
          downloadBtn.onclick = () => { window.location.href = '/api/download-md/' + jobId; };
          publishBtn.disabled = false;
          convertBtn.disabled = false;
        } else if (data.status === 'failed') {
          clearInterval(pollInterval);
          showError((data.error || 'Conversion failed.') + (data.suggestion ? '\n\nSuggestion: ' + data.suggestion : ''));
          publishBtn.disabled = true;
          convertBtn.disabled = false;
        }
      } catch (e) {
        clearInterval(pollInterval);
        showError('Poll error: ' + e.message);
        publishBtn.disabled = true;
        convertBtn.disabled = false;
      }
    }, 700);
  }

  async function publishCurrentDocument() {
    if (!currentJobId) return;
    publishBtn.disabled = true;
    publishStatus.innerHTML = 'Publishing to site…';
    const fd = new FormData();
    fd.append('document_name', publishName || 'published-document');
    fd.append('publish_secret', publishSecret.value || '');

    try {
      const res = await fetch('/api/publish/' + currentJobId, { method: 'POST', body: fd });
      const data = await res.json().catch(() => ({}));
      if (res.status === 403) {
        publishSecret.style.display = 'block';
        publishStatus.textContent = 'Enter the publish secret above and try again.';
        publishBtn.disabled = false;
        return;
      }
      if (!res.ok) {
        publishStatus.textContent = data.detail || 'Failed to publish document.';
        publishBtn.disabled = false;
        return;
      }
      publishStatus.innerHTML = 'Published. <a href="' + data.published_url + '" target="_blank" rel="noopener noreferrer">Open document</a> · <a href="/docs/published/" target="_blank" rel="noopener noreferrer">View all documents</a>';
    } catch (e) {
      publishStatus.textContent = 'Publish error: ' + e.message;
    } finally {
      publishBtn.disabled = false;
    }
  }

  publishBtn.addEventListener('click', publishCurrentDocument);

  async function loadPreview(jobId) {
    try {
      const res = await fetch('/api/preview-content/' + jobId);
      if (!res.ok) return;
      const data = await res.json();
      emptyState.style.display = 'none';
      previewContent.style.display = 'block';
      previewContent.innerHTML = data.html || '';
      rawMd.value = data.markdown || '';
    } catch (e) {
      showError('Could not load preview: ' + e.message);
    }
  }

  function setProgress(pct, msg) {
    progressBar.style.width = pct + '%';
    statusMsg.textContent = msg;
  }

  function showError(msg) {
    progressWrap.classList.remove('visible');
    errorBox.textContent = msg;
    errorBox.classList.add('visible');
  }

  function clearResult() {
    clearInterval(pollInterval);
    progressWrap.classList.remove('visible');
    progressBar.style.width = '0%';
    statusMsg.textContent = '';
    errorBox.classList.remove('visible');
    errorBox.textContent = '';
    resultActions.classList.remove('visible');
    publishStatus.innerHTML = '';
    publishBtn.disabled = true;
    previewContent.innerHTML = '';
    previewContent.style.display = 'none';
    emptyState.style.display = 'flex';
    rawMd.value = '';
    currentJobId = null;
  }
})();
</script>
</body>
</html>"""


@app.get("/editor", response_class=HTMLResponse)
async def editor() -> HTMLResponse:
    return HTMLResponse(_EDITOR_HTML)


@app.get("/")
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/editor", status_code=307)


@app.get("/converter")
async def converter_redirect() -> RedirectResponse:
    return RedirectResponse(url="/editor", status_code=307)


@app.get("/site")
async def site_redirect() -> RedirectResponse:
  return RedirectResponse(url="/docs/", status_code=307)


if not (SITE_DIR / "index.html").exists():
  try:
    build_itsd_site()
  except Exception as _site_err:
    import sys as _sys
    print(f"WARNING: Initial MkDocs site build failed: {_site_err}", file=_sys.stderr)


@app.get("/health")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok"})


if SITE_DIR.exists():
    app.mount("/docs", StaticFiles(directory=SITE_DIR, html=True), name="site")
