from __future__ import annotations

import re
import zipfile
from pathlib import Path

DOCX_PATH = Path("Promotion Forecast Power App (2).docx")
MD_PATH = Path("analysis_output/Promotion Forecast Power App (2)_docx.md")


def main() -> int:
    if not DOCX_PATH.exists():
        print(f"Missing DOCX: {DOCX_PATH}")
        return 1
    if not MD_PATH.exists():
        print(f"Missing converted markdown: {MD_PATH}")
        return 1

    with zipfile.ZipFile(DOCX_PATH) as archive:
        names = archive.namelist()
        doc_xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
        rels_xml = archive.read("word/_rels/document.xml.rels").decode("utf-8", errors="ignore")

    media_files = [n for n in names if n.startswith("word/media/")]
    chart_parts = [n for n in names if n.startswith("word/charts/")]

    hyperlink_rel_count = rels_xml.count(
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"'
    )
    hyperlink_elem_count = doc_xml.count("<w:hyperlink")

    bold_count = doc_xml.count("<w:b")
    italic_count = doc_xml.count("<w:i")
    underline_count = doc_xml.count("<w:u")
    color_hexes = re.findall(r'<w:color[^>]*w:val="([0-9A-Fa-f]{6})"', doc_xml)

    md_text = MD_PATH.read_text(encoding="utf-8", errors="ignore")
    md_lines = md_text.splitlines()

    md_links = re.findall(r"\[[^\]]+\]\((https?://[^)]+)\)", md_text)
    md_color_spans = re.findall(r"<span style=\"color:\s*#([0-9A-Fa-f]{6})", md_text)
    md_image_refs = re.findall(r"!\[[^\]]*\]\((assets/[^)]+)\)", md_text)

    print("DOCX SUMMARY")
    print(f"- media files: {len(media_files)}")
    print(f"- chart parts: {len(chart_parts)}")
    print(f"- hyperlink rels: {hyperlink_rel_count}")
    print(f"- hyperlink elements: {hyperlink_elem_count}")
    print(f"- bold tags: {bold_count}")
    print(f"- italic tags: {italic_count}")
    print(f"- underline tags: {underline_count}")
    print(f"- color tags: {len(color_hexes)}")
    print(f"- unique colors: {sorted(set(c.upper() for c in color_hexes))[:20]}")

    print("\nMARKDOWN SUMMARY")
    print(f"- md links: {len(md_links)}")
    print(f"- md color spans: {len(md_color_spans)}")
    print(f"- md image refs: {len(md_image_refs)}")
    print(f"- md chars: {len(md_text)}")

    print("\nFIRST 120 LINES")
    for i, line in enumerate(md_lines[:120], start=1):
        print(f"{i:03}: {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
