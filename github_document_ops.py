from __future__ import annotations

import argparse
import html
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

from convert_to_md import ConversionContext, convert_file_to_markdown, ensure_assets_folder, slugify

SUPPORTED_INCOMING_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


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
        if not fallback_stem.strip():
            raise ValueError("Document path is required.")
        fallback = slugify(fallback_stem)
        parts = [fallback]

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
    target_markdown.write_text(
        source_markdown.read_text(encoding="utf-8", errors="ignore"),
        encoding="utf-8",
    )

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
        "Documents published by the GitHub Actions converter appear here.",
        "",
        "Repository administrators can use **Converter** to upload and publish documents.",
        "",
        "## Available Documents",
        "",
    ]

    if entries:
        for rel_dir, title in entries:
            safe_title = html.escape(title, quote=False)
            safe_rel_dir = html.escape(rel_dir, quote=True)
            lines.append(
                f'- [{safe_title}]({safe_rel_dir}/index.md) — `{safe_rel_dir}` '
                f'<button type="button" class="delete-published-document" '
                f'data-site-path="{safe_rel_dir}">Delete</button>'
            )
    else:
        lines.append("No documents have been published yet.")

    (docs_root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_incoming_files(incoming_dir: Path) -> Iterable[Path]:
    if not incoming_dir.exists():
        return []
    return sorted(
        path
        for path in incoming_dir.rglob("*")
        if path.is_file()
        and path.name != ".gitkeep"
        and path.suffix.lower() in SUPPORTED_INCOMING_EXTENSIONS
    )


def _convert_incoming_file(source: Path, work_dir: Path, pdf_mode: str) -> tuple[Path, Path]:
    assets_dir = work_dir / "assets"
    ensure_assets_folder(assets_dir)
    context = ConversionContext(
        output_dir=work_dir,
        assets_dir=assets_dir,
        overwrite=True,
        pdf_mode=pdf_mode,
        tesseract_cmd=None,
        prefer_markitdown=True,
        improve_markdown=False,
        strict_validation=True,
    )
    markdown_content = convert_file_to_markdown(source, context)
    output_file = work_dir / "index.md"
    output_file.write_text(markdown_content, encoding="utf-8")
    return output_file, assets_dir


def process_incoming_documents(
    *,
    incoming_dir: Path,
    published_root: Path,
    diagnostics_dir: Path,
    pdf_mode: str = "hybrid",
) -> list[dict[str, Any]]:
    if pdf_mode not in {"hybrid", "ocr", "visual"}:
        raise ValueError(f"Unsupported PDF mode: {pdf_mode}")

    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for source in find_incoming_files(incoming_dir):
        site_path = normalize_site_path(source.stem, source.stem)
        with tempfile.TemporaryDirectory(prefix="github-convert-") as temp_name:
            work_dir = Path(temp_name)
            markdown_file, assets_dir = _convert_incoming_file(source, work_dir, pdf_mode)
            published = publish_markdown_to_mkdocs_site(
                source_markdown=markdown_file,
                source_assets_dir=assets_dir,
                docs_root=published_root,
                site_path=site_path,
            )

            document_diagnostics = diagnostics_dir / site_path
            document_diagnostics.mkdir(parents=True, exist_ok=True)
            for artifact in work_dir.glob("*.json"):
                shutil.copy2(artifact, document_diagnostics / artifact.name)

        source.unlink()
        results.append(
            {
                "source": source.name,
                "site_path": published["site_path"],
                "target_markdown": published["target_markdown"],
                "status": "published",
            }
        )

    update_published_index(published_root)
    summary = {
        "processed": len(results),
        "pdf_mode": pdf_mode,
        "results": results,
    }
    (diagnostics_dir / "conversion-summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GitHub Actions document publishing operations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    process = subparsers.add_parser("process-incoming", help="Convert and publish supported files from incoming/.")
    process.add_argument("--incoming-dir", type=Path, default=Path("incoming"))
    process.add_argument("--published-root", type=Path, default=Path("mkdocs_preview/docs/published"))
    process.add_argument("--diagnostics-dir", type=Path, default=Path("artifacts/github-actions/current"))
    process.add_argument("--pdf-mode", choices=["hybrid", "ocr", "visual"], default="hybrid")

    delete = subparsers.add_parser("delete", help="Delete a normalized published-document path.")
    delete.add_argument("--published-root", type=Path, default=Path("mkdocs_preview/docs/published"))
    delete.add_argument("--site-path", required=True)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "process-incoming":
        results = process_incoming_documents(
            incoming_dir=args.incoming_dir,
            published_root=args.published_root,
            diagnostics_dir=args.diagnostics_dir,
            pdf_mode=args.pdf_mode,
        )
        print(f"Processed {len(results)} incoming document(s).")
        return 0

    result = delete_published_document(
        docs_root=args.published_root,
        site_path=args.site_path,
    )
    update_published_index(args.published_root)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
