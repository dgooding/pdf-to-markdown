from __future__ import annotations

import json
import re
import subprocess
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS_DIRS = [ROOT / "test_corpus" / "generated", ROOT / "test_corpus" / "downloaded"]
RESULTS_ROOT = ROOT / "test_results"


@dataclass
class EvalRecord:
    source: str
    mode: str
    output_md: str
    converted: bool
    line_count: int
    char_count: int
    image_refs: int
    link_refs: int
    bullet_lines: int
    checks: dict[str, bool]
    notes: list[str]


def _run_conversion(mode: str, source_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "C:/Python39/python.exe",
        str(ROOT / "convert_to_md.py"),
        str(source_dir),
        "--recursive",
        "--output-dir",
        str(out_dir),
        "--overwrite",
        "--pdf-mode",
        mode,
    ]
    subprocess.run(cmd, check=False, cwd=ROOT)


def _source_to_output(source: Path, out_dir: Path) -> Path:
    ext = source.suffix.lower()
    if ext == ".pdf":
        return out_dir / f"{source.stem}.md"
    if ext == ".docx":
        return out_dir / f"{source.stem}_docx.md"
    if ext == ".txt":
        return out_dir / f"{source.stem}_txt.md"
    raise ValueError(ext)


def _docx_hyperlink_count(path: Path) -> int:
    with zipfile.ZipFile(path) as zf:
        rels = zf.read("word/_rels/document.xml.rels").decode("utf-8", errors="ignore")
    return rels.count('Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"')


def _pdf_page_count(path: Path) -> int:
    import fitz

    with fitz.open(path) as doc:
        return doc.page_count


def evaluate_mode(mode: str, out_dir: Path) -> list[EvalRecord]:
    records: list[EvalRecord] = []
    source_files: list[Path] = []
    for base in CORPUS_DIRS:
        source_files.extend(sorted(base.glob("*.pdf")))
        source_files.extend(sorted(base.glob("*.docx")))
        source_files.extend(sorted(base.glob("*.txt")))

    for source in source_files:
        output_md = _source_to_output(source, out_dir)
        converted = output_md.exists()
        checks: dict[str, bool] = {}
        notes: list[str] = []

        text = output_md.read_text(encoding="utf-8", errors="ignore") if converted else ""
        lines = text.splitlines()

        image_refs = len(re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text))
        link_refs = len(re.findall(r"\[[^\]]+\]\((https?://[^)]+)\)", text))
        bullet_lines = sum(1 for line in lines if line.strip().startswith("- "))

        ext = source.suffix.lower()
        if ext == ".pdf":
            pages = _pdf_page_count(source)
            page_png_refs = len(re.findall(r"assets/[a-zA-Z0-9_-]+-page-\d+\.png", text))
            checks["has_page_images"] = page_png_refs >= pages
            checks["has_page_sections"] = text.count("## Page ") >= pages
            if mode == "visual":
                checks["visual_note"] = "Visual-first mode enabled" in text
            else:
                checks["has_text_or_warning"] = ("### Extracted Text" in text) or ("### OCR Text" in text) or ("quality was low" in text)
            notes.append(f"pdf_pages={pages}, png_refs={page_png_refs}")

        elif ext == ".docx":
            src_links = _docx_hyperlink_count(source)
            checks["link_preservation"] = (src_links == 0) or (link_refs >= min(1, src_links))
            checks["has_heading"] = text.startswith("# ")
            notes.append(f"docx_hyperlinks={src_links}, md_links={link_refs}")

        elif ext == ".txt":
            checks["has_heading"] = text.startswith("# ")
            checks["contains_body"] = len(text.strip()) > 40

        checks["converted"] = converted

        records.append(
            EvalRecord(
                source=str(source.relative_to(ROOT)),
                mode=mode,
                output_md=str(output_md.relative_to(ROOT)),
                converted=converted,
                line_count=len(lines),
                char_count=len(text),
                image_refs=image_refs,
                link_refs=link_refs,
                bullet_lines=bullet_lines,
                checks=checks,
                notes=notes,
            )
        )

    return records


def write_report(records: list[EvalRecord], path: Path) -> None:
    lines: list[str] = []
    lines.append("# Recursive Conversion Evaluation Report")
    lines.append("")
    lines.append(f"Total records: {len(records)}")
    lines.append("")

    by_mode: dict[str, list[EvalRecord]] = {}
    for rec in records:
        by_mode.setdefault(rec.mode, []).append(rec)

    for mode, recs in by_mode.items():
        lines.append(f"## Mode: {mode}")
        lines.append("")
        passed = 0
        for rec in recs:
            ok = all(rec.checks.values())
            if ok:
                passed += 1
            status = "✅" if ok else "⚠️"
            lines.append(f"### {status} `{rec.source}`")
            lines.append(f"- output: `{rec.output_md}`")
            lines.append(f"- chars: {rec.char_count}, lines: {rec.line_count}, images: {rec.image_refs}, links: {rec.link_refs}, bullets: {rec.bullet_lines}")
            lines.append(f"- checks: {json.dumps(rec.checks, ensure_ascii=False)}")
            if rec.notes:
                lines.append(f"- notes: {'; '.join(rec.notes)}")
            lines.append("")

        lines.append(f"**Mode summary:** {passed}/{len(recs)} records passed all checks.")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    mode_out = {
        "hybrid": RESULTS_ROOT / "hybrid",
        "visual": RESULTS_ROOT / "visual",
        "ocr": RESULTS_ROOT / "ocr",
    }

    for mode, out in mode_out.items():
        for src in CORPUS_DIRS:
            _run_conversion(mode, src, out)

    all_records: list[EvalRecord] = []
    for mode, out in mode_out.items():
        all_records.extend(evaluate_mode(mode, out))

    report_path = RESULTS_ROOT / "evaluation_report.md"
    json_path = RESULTS_ROOT / "evaluation_report.json"

    write_report(all_records, report_path)
    json_path.write_text(json.dumps([asdict(r) for r in all_records], indent=2), encoding="utf-8")

    print(f"Wrote report: {report_path}")
    print(f"Wrote report: {json_path}")


if __name__ == "__main__":
    main()
