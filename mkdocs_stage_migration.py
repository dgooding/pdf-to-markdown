from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ConflictStrategy = Literal["fail", "skip", "versioned_copy", "overwrite_with_backup"]


@dataclass
class MigrationResult:
    source_markdown: str
    target_markdown: str
    status: str
    conflict_strategy: str
    backup_path: str | None
    rewritten_links: int
    notes: list[str]


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    value = re.sub(r"-+", "-", value)
    return value.strip("-").lower() or "item"


def sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._ -]+", "_", name)
    return safe.strip().replace("  ", " ")


def rewrite_internal_links(md_text: str) -> tuple[str, int]:
    pattern = re.compile(r"(\[[^\]]+\]\()([^)]+)(\))")
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        target = m.group(2).strip()
        if target.startswith(("http://", "https://", "mailto:", "#", "data:")):
            return m.group(0)
        norm = target.replace("\\", "/")
        if norm.startswith("assets/"):
            return m.group(0)
        if norm.endswith(".md"):
            count += 1
            return f"{m.group(1)}{norm[:-3]}/{m.group(3)}"
        return m.group(0)

    out = pattern.sub(repl, md_text)
    return out, count


def migrate_markdown(
    source_markdown: Path,
    source_assets_dir: Path | None,
    docs_root: Path,
    conflict_strategy: ConflictStrategy,
) -> MigrationResult:
    docs_root.mkdir(parents=True, exist_ok=True)

    slug = slugify(source_markdown.stem)
    target_dir = docs_root / slug
    target_md = target_dir / "index.md"
    backup_path: Path | None = None
    notes: list[str] = []

    if target_md.exists():
        if conflict_strategy == "fail":
            return MigrationResult(
                source_markdown=str(source_markdown),
                target_markdown=str(target_md),
                status="failed_conflict",
                conflict_strategy=conflict_strategy,
                backup_path=None,
                rewritten_links=0,
                notes=["target exists"],
            )
        if conflict_strategy == "skip":
            return MigrationResult(
                source_markdown=str(source_markdown),
                target_markdown=str(target_md),
                status="skipped_conflict",
                conflict_strategy=conflict_strategy,
                backup_path=None,
                rewritten_links=0,
                notes=["target exists"],
            )
        if conflict_strategy == "versioned_copy":
            stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            target_dir = docs_root / f"{slug}-{stamp}"
            target_md = target_dir / "index.md"
            notes.append("versioned_copy_created")
        if conflict_strategy == "overwrite_with_backup":
            stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            backup_path = target_md.with_name(f"index.backup.{stamp}.md")
            shutil.copy2(target_md, backup_path)
            notes.append("existing_backed_up")

    target_dir.mkdir(parents=True, exist_ok=True)
    target_assets = target_dir / "assets"
    target_assets.mkdir(parents=True, exist_ok=True)

    md_text = source_markdown.read_text(encoding="utf-8", errors="ignore")
    rewritten, rewritten_links = rewrite_internal_links(md_text)
    target_md.write_text(rewritten, encoding="utf-8")

    if source_assets_dir and source_assets_dir.exists():
        for src in source_assets_dir.glob("*"):
            if not src.is_file():
                continue
            dst = target_assets / sanitize_filename(src.name)
            shutil.copy2(src, dst)

    return MigrationResult(
        source_markdown=str(source_markdown),
        target_markdown=str(target_md),
        status="migrated",
        conflict_strategy=conflict_strategy,
        backup_path=str(backup_path) if backup_path else None,
        rewritten_links=rewritten_links,
        notes=notes,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage converted markdown into MkDocs docs root safely.")
    p.add_argument("source_markdown", type=Path)
    p.add_argument("--source-assets-dir", type=Path, default=None)
    p.add_argument("--docs-root", type=Path, required=True)
    p.add_argument("--conflict-strategy", choices=["fail", "skip", "versioned_copy", "overwrite_with_backup"], default="fail")
    p.add_argument("--report", type=Path, default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.source_markdown.exists():
        print(f"Source markdown not found: {args.source_markdown}")
        return 1

    result = migrate_markdown(
        source_markdown=args.source_markdown,
        source_assets_dir=args.source_assets_dir,
        docs_root=args.docs_root,
        conflict_strategy=args.conflict_strategy,
    )

    payload = asdict(result)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if result.status in {"migrated", "skipped_conflict"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
