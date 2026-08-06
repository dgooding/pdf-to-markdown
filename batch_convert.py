from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from convert_to_md import ConversionContext, SUPPORTED_EXTENSIONS, convert_file_to_markdown, ensure_assets_folder, write_markdown

EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "artifacts",
    "previews",
    "logs",
    "mkdocs_preview",
    "__pycache__",
}


@dataclass
class BatchItemResult:
    source: str
    status: str
    output_markdown: str | None
    error: str | None


def _should_skip_path(path: Path, output_root: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if parts & {n.lower() for n in EXCLUDE_DIR_NAMES}:
        return True
    try:
        path.resolve().relative_to(output_root.resolve())
        return True
    except Exception:
        return False


def discover_inputs(root: Path, recursive: bool, output_root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in SUPPORTED_EXTENSIONS else []

    pattern = "**/*" if recursive else "*"
    found: list[Path] = []
    for p in root.glob(pattern):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if _should_skip_path(p, output_root):
            continue
        found.append(p)
    return sorted(found)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Safe batch converter for milestone 8.")
    p.add_argument("input_root", type=Path)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--recursive", action="store_true")
    p.add_argument("--pdf-mode", choices=["hybrid", "ocr", "visual", "layout"], default="hybrid")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--state-file", type=Path, default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    assets_dir = output_root / "assets"
    ensure_assets_folder(assets_dir)

    state_file = args.state_file or (output_root / "batch-state.json")
    previous_done: set[str] = set()
    if args.resume and state_file.exists():
        try:
            payload = json.loads(state_file.read_text(encoding="utf-8"))
            previous_done = {item["source"] for item in payload.get("results", []) if item.get("status") == "ok"}
        except Exception:
            previous_done = set()

    sources = discover_inputs(args.input_root, args.recursive, output_root)
    if args.dry_run:
        print(json.dumps({"mode": "dry_run", "count": len(sources), "sources": [str(s) for s in sources]}, indent=2))
        return 0

    ctx = ConversionContext(
        output_dir=output_root,
        assets_dir=assets_dir,
        overwrite=bool(args.force),
        pdf_mode=args.pdf_mode,
        tesseract_cmd=None,
        prefer_markitdown=True,
        improve_markdown=False,
        strict_validation=True,
    )

    results: list[BatchItemResult] = []
    for src in sources:
        src_key = str(src.resolve())
        if src_key in previous_done:
            results.append(BatchItemResult(source=src_key, status="skipped_resume", output_markdown=None, error=None))
            continue

        out_name = f"{src.stem}.md" if src.suffix.lower() == ".pdf" else f"{src.stem}_{src.suffix.lower().lstrip('.')}.md"
        out_path = output_root / out_name
        if args.skip_existing and out_path.exists() and not args.force:
            results.append(BatchItemResult(source=src_key, status="skipped_existing", output_markdown=str(out_path), error=None))
            continue

        try:
            md = convert_file_to_markdown(src, ctx)
            written = write_markdown(output_root, src, md, overwrite=bool(args.force or args.skip_existing))
            results.append(BatchItemResult(source=src_key, status="ok", output_markdown=str(written), error=None))
        except Exception as exc:  # noqa: BLE001
            results.append(BatchItemResult(source=src_key, status="failed", output_markdown=None, error=str(exc)))

    payload = {
        "input_root": str(args.input_root),
        "output_root": str(output_root),
        "recursive": bool(args.recursive),
        "pdf_mode": args.pdf_mode,
        "results": [asdict(r) for r in results],
        "summary": {
            "total": len(results),
            "ok": sum(1 for r in results if r.status == "ok"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "skipped": sum(1 for r in results if r.status.startswith("skipped_")),
        },
    }
    state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0 if payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
