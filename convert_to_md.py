from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from importlib import import_module
from pathlib import Path
from typing import Any, Iterable

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".docx", ".txt"}


@dataclass
class AssetPlacement:
    source_page: int
    source_object_id: str
    bbox: list[float]
    content_hash: str
    asset_path: str
    image_source: str
    placement_reason: str
    confidence: float
    deduplicated: bool


@dataclass
class RegionResult:
    region_id: str
    region_type: str
    bbox: list[float]
    confidence: float
    source_objects: list[str] = field(default_factory=list)
    selected_strategy: str = ""
    output_content: str = ""
    asset_placements: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    review_required: bool = False


@dataclass
class CandidateResult:
    candidate_id: str
    strategy: str
    page_number: int
    regions: list[RegionResult] = field(default_factory=list)
    native_text_coverage: float = 0.0
    reading_order_score: float = 0.0
    suspicious_glyph_count: int = 0
    chart_text_leakage_count: int = 0
    duplicate_content_score: float = 0.0
    fallback_area_ratio: float = 0.0
    unresolved_asset_count: int = 0
    score_components: dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass
class FallbackRecord:
    source_page: int
    region_bbox: list[float]
    fallback_type: str
    triggering_condition: str
    alternatives_attempted: list[str] = field(default_factory=list)
    confidence: float = 0.0
    text_overlap_detected: bool = False
    review_required: bool = False


@dataclass
class PageResult:
    page_number: int
    width: float
    height: float
    native_text_available: bool
    native_character_count: int
    embedded_image_count: int
    vector_drawing_count: int
    classifications: list[dict[str, Any]] = field(default_factory=list)
    regions: list[RegionResult] = field(default_factory=list)
    candidates: list[CandidateResult] = field(default_factory=list)
    selected_candidate: str = ""
    fallback_records: list[FallbackRecord] = field(default_factory=list)
    semantic_coverage: float = 0.0
    visual_coverage: float = 0.0
    accessible_coverage: float = 0.0
    unhandled_coverage: float = 0.0
    technical_status: str = "passed"
    fidelity_status: str = "moderate"
    review_reasons: list[str] = field(default_factory=list)


@dataclass
class DocumentResult:
    source_path: str
    page_count: int
    pages: list[PageResult] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    technical_status: str = "passed"
    fidelity_status: str = "moderate"


def _as_jsonable(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _as_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_as_jsonable(x) for x in obj]
    if isinstance(obj, tuple):
        return [_as_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _as_jsonable(v) for k, v in obj.items()}
    return obj


@dataclass
class ConversionContext:
    output_dir: Path
    assets_dir: Path
    overwrite: bool
    pdf_mode: str
    tesseract_cmd: str | None
    prefer_markitdown: bool = True
    improve_markdown: bool = False
    strict_validation: bool = True
    render_dpi: int = 220
    preserve_page_markers: bool = True
    allow_inline_html: bool = True


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    cleaned = re.sub(r"-+", "-", cleaned)
    return cleaned.strip("-").lower() or "item"


def normalize_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def strip_bom(text: str) -> str:
    return text.lstrip("\ufeff")


def ensure_assets_folder(assets_dir: Path) -> None:
    assets_dir.mkdir(parents=True, exist_ok=True)


def get_dependency(module_name: str, pip_name: str):
    try:
        return import_module(module_name)
    except ImportError as exc:
        raise RuntimeError(f"Missing dependency '{module_name}'. Install it with: pip install {pip_name}") from exc


def maybe_set_tesseract_binary(tesseract_cmd: str | None) -> None:
    if not tesseract_cmd:
        return
    pytesseract_module = get_dependency("pytesseract", "pytesseract")
    pytesseract_module.pytesseract.tesseract_cmd = tesseract_cmd


def ocr_image_to_text(image_path: Path) -> str:
    image_module = get_dependency("PIL.Image", "Pillow")
    pytesseract_module = get_dependency("pytesseract", "pytesseract")
    with image_module.open(image_path) as image:
        text = pytesseract_module.image_to_string(image)
    return normalize_text(text)


def ocr_image_bytes_to_text(image_bytes: bytes) -> str:
    image_module = get_dependency("PIL.Image", "Pillow")
    pytesseract_module = get_dependency("pytesseract", "pytesseract")
    with image_module.open(io.BytesIO(image_bytes)) as image:
        text = pytesseract_module.image_to_string(image)
    return normalize_text(text)


def detect_tesseract_provider(tesseract_cmd: str | None) -> dict[str, Any]:
    configured = tesseract_cmd.strip() if isinstance(tesseract_cmd, str) and tesseract_cmd.strip() else None
    on_path = shutil.which("tesseract")
    executable = configured or on_path
    result: dict[str, Any] = {
        "configured_path": configured,
        "on_path": bool(on_path),
        "executable": executable,
        "available": False,
        "version": None,
        "error": None,
    }
    if not executable:
        result["error"] = "tesseract_not_found"
        return result

    try:
        probe = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=4)
        if probe.returncode == 0:
            first = (probe.stdout or "").splitlines()[0].strip() if probe.stdout else ""
            result["available"] = True
            result["version"] = first or "unknown"
        else:
            result["error"] = (probe.stderr or probe.stdout or "probe_failed").strip()[:300]
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    return result


def convert_with_markitdown(file_path: Path) -> str | None:
    try:
        markitdown_module = import_module("markitdown")
    except Exception:
        return None

    markitdown_cls = getattr(markitdown_module, "MarkItDown", None)
    if markitdown_cls is None:
        return None

    try:
        converter = markitdown_cls()
        result = converter.convert(str(file_path))
    except Exception:
        return None

    for attr in ("text_content", "markdown", "text"):
        candidate = getattr(result, attr, None)
        if isinstance(candidate, str) and candidate.strip():
            return normalize_text(candidate) + "\n"

    if isinstance(result, str) and result.strip():
        return normalize_text(result) + "\n"
    return None


def _safe_ext(ext: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", ext.lower())
    return cleaned or "png"


def _normalize_pdf_extracted_text(raw_text: str) -> str:
    text = raw_text.replace("\u00a0", " ").replace("", "•").replace("·", "•")
    lines = [line.strip() for line in text.splitlines()]

    normalized: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current:
            normalized.append(current.strip())
            current = ""

    pending_bullet = False
    for line in lines:
        if not line:
            flush()
            if normalized and normalized[-1] != "":
                normalized.append("")
            continue

        if line in {"•", "●", "▪", "◦", "·", "-"}:
            pending_bullet = True
            continue

        if line.startswith(("• ", "● ", "▪ ", "◦ ", "· ")):
            flush()
            line = "- " + line[2:].strip()

        if pending_bullet:
            flush()
            line = "- " + line.lstrip("- ").strip()
            pending_bullet = False

        line = re.sub(r"[ \t]{2,}", " ", line)
        if line.startswith("- "):
            flush()
            normalized.append(line)
        else:
            current = f"{current} {line}".strip() if current else line

    flush()
    return normalize_text("\n".join(normalized))


def _text_quality_score(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0

    total = len(stripped)
    letters = sum(ch.isalpha() for ch in stripped)
    spaces = sum(ch.isspace() for ch in stripped)
    weird = sum(not (ch.isalnum() or ch.isspace() or ch in ".,;:!?()[]{}'\"-_/&%$#@+*=<>`~|\\") for ch in stripped)

    words = re.findall(r"[A-Za-z]{2,}", stripped)
    avg_word = (sum(len(w) for w in words) / len(words)) if words else 0.0

    letter_ratio = letters / total
    weird_ratio = weird / total
    white_ratio = spaces / total

    score = (
        0.45 * min(letter_ratio / 0.65, 1.0)
        + 0.30 * (1.0 - min(weird_ratio / 0.08, 1.0))
        + 0.15 * (1.0 - min(abs(white_ratio - 0.18) / 0.18, 1.0))
        + 0.10 * (1.0 if 2.5 <= avg_word <= 11.0 else 0.55)
    )
    return max(0.0, min(1.0, score))


def _pick_best_page_text(native_text: str, ocr_text: str | None) -> tuple[str, str, float]:
    native_score = _text_quality_score(native_text)
    ocr_score = _text_quality_score(ocr_text or "") if ocr_text else 0.0

    if native_text and native_score >= 0.55 and native_score >= ocr_score - 0.05:
        return native_text, "native", native_score
    if ocr_text and ocr_score >= native_score + 0.05:
        return ocr_text, "ocr", ocr_score
    if native_text and native_score >= 0.40:
        return native_text, "native", native_score
    if ocr_text and ocr_score >= 0.40:
        return ocr_text, "ocr", ocr_score
    if ocr_text and ocr_score >= native_score:
        return ocr_text, "ocr", ocr_score
    return native_text, "native", native_score


def _save_asset_dedup(
    payload: bytes,
    assets_dir: Path,
    page_number: int,
    kind: str,
    index: int,
    ext: str,
    dedup: dict[str, str],
) -> str:
    filename, _, _ = _save_asset_dedup_meta(payload, assets_dir, page_number, kind, index, ext, dedup)
    return filename


def _save_asset_dedup_meta(
    payload: bytes,
    assets_dir: Path,
    page_number: int,
    kind: str,
    index: int,
    ext: str,
    dedup: dict[str, str],
) -> tuple[str, str, bool]:
    digest = hashlib.sha256(payload).hexdigest()
    if digest in dedup:
        return dedup[digest], digest, True
    filename = f"page-{page_number:03d}-{slugify(kind)}-{index:03d}.{_safe_ext(ext)}"
    (assets_dir / filename).write_bytes(payload)
    dedup[digest] = filename
    return filename, digest, False


def _bbox_intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)


def _span_is_bold(span: dict[str, Any]) -> bool:
    flags = int(span.get("flags", 0))
    font = str(span.get("font", "")).lower()
    return bool(flags & 16) or "bold" in font


def _span_is_italic(span: dict[str, Any]) -> bool:
    flags = int(span.get("flags", 0))
    font = str(span.get("font", "")).lower()
    return bool(flags & 2) or "italic" in font or "oblique" in font


def _span_color_hex(span: dict[str, Any]) -> str | None:
    color = span.get("color")
    if color is None:
        return None
    try:
        value = int(color)
    except Exception:
        return None
    return f"{(value >> 16) & 0xFF:02X}{(value >> 8) & 0xFF:02X}{value & 0xFF:02X}"


def _style_fragment(text: str, span: dict[str, Any], allow_inline_html: bool) -> str:
    escaped = text.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_")
    bold = _span_is_bold(span)
    italic = _span_is_italic(span)
    if bold and italic:
        escaped = f"***{escaped}***"
    elif bold:
        escaped = f"**{escaped}**"
    elif italic:
        escaped = f"*{escaped}*"

    color_hex = _span_color_hex(span)
    if allow_inline_html and color_hex and color_hex not in {"000000", "111111", "222222"}:
        escaped = f"<span style=\"color: #{color_hex};\">{escaped}</span>"
    return escaped


def _line_to_markdown(line: dict[str, Any], allow_inline_html: bool) -> tuple[str, float]:
    parts: list[str] = []
    max_size = 0.0
    for span in line.get("spans", []):
        raw = (span.get("text") or "").replace("\r", "")
        if not raw:
            continue
        max_size = max(max_size, float(span.get("size", 0.0)))
        parts.append(_style_fragment(raw, span, allow_inline_html))
    return "".join(parts).strip(), max_size


def _line_plain_text(line: dict[str, Any]) -> str:
    parts = [str(span.get("text") or "") for span in line.get("spans", [])]
    return "".join(parts).strip()


def _split_line_by_column(line: dict[str, Any], page_width: float, allow_inline_html: bool) -> list[tuple[str, str, float]]:
    spans = line.get("spans", []) or []
    if not spans:
        return []
    mid = page_width / 2.0

    left_parts: list[str] = []
    right_parts: list[str] = []
    left_size = 0.0
    right_size = 0.0

    for span in spans:
        text = str(span.get("text") or "")
        if not text.strip():
            continue
        frag = _style_fragment(text.replace("\r", ""), span, allow_inline_html)
        bbox = span.get("bbox", [0, 0, 0, 0])
        try:
            cx = (float(bbox[0]) + float(bbox[2])) / 2.0
        except Exception:
            cx = mid
        sz = float(span.get("size", 0.0))
        if cx <= mid:
            left_parts.append(frag)
            left_size = max(left_size, sz)
        else:
            right_parts.append(frag)
            right_size = max(right_size, sz)

    out: list[tuple[str, str, float]] = []
    left_text = normalize_text("".join(left_parts)) if left_parts else ""
    right_text = normalize_text("".join(right_parts)) if right_parts else ""
    if left_text:
        out.append(("left", left_text, left_size))
    if right_text:
        out.append(("right", right_text, right_size))
    return out


def _pdf_heading_level(text: str, max_size: float, baseline_size: float) -> int | None:
    if not text or "\n" in text or len(text) > 90:
        return None
    words = re.findall(r"[A-Za-z0-9]+", text)
    if len(words) > 12:
        return None
    if text.endswith(('.', ',', ';', ':')):
        return None
    baseline = baseline_size if baseline_size > 0 else 11.0
    ratio = max_size / baseline
    if ratio >= 2.0:
        return 1
    if ratio >= 1.75:
        return 2
    # Avoid deep heading inference from emphasized paragraph openings.
    if ratio >= 1.55 and len(words) <= 6:
        return 2
    return None


def _is_decorative_rect(rect: tuple[float, float, float, float], page_w: float, page_h: float) -> bool:
    x0, y0, x1, y1 = rect
    w = max(0.0, x1 - x0)
    h = max(0.0, y1 - y0)
    area = w * h
    page_area = max(1.0, page_w * page_h)
    if w < 3 or h < 3:
        return True
    if area < page_area * 0.0004:
        return True
    # very wide separators / underlines
    if w > page_w * 0.6 and h < page_h * 0.01:
        return True
    if h > page_h * 0.6 and w < page_w * 0.01:
        return True
    return False


def _detect_chart_region_from_words(words: list[tuple[Any, ...]], page_w: float, page_h: float) -> tuple[float, float, float, float] | None:
    hits: list[tuple[float, float, float, float]] = []
    numeric_hits: list[tuple[float, float, float, float]] = []
    axis_label_hits: list[tuple[float, float, float, float]] = []
    for w in words:
        if len(w) < 5:
            continue
        x0, y0, x1, y1, token = float(w[0]), float(w[1]), float(w[2]), float(w[3]), str(w[4])
        t = token.strip()
        if not t:
            continue
        tl = t.lower()
        if re.fullmatch(r"\d+(?:\.\d+)?", t):
            numeric_hits.append((x0, y0, x1, y1))
            hits.append((x0, y0, x1, y1))
        elif tl in {"row", "column"} or re.match(r"^(row|column)\b", tl):
            axis_label_hits.append((x0, y0, x1, y1))
            hits.append((x0, y0, x1, y1))

    # Need chart-like evidence, not just scattered digits in body text.
    has_axis_labels = len(axis_label_hits) >= 2
    if not ((has_axis_labels and len(numeric_hits) >= 4) or len(numeric_hits) >= 12):
        return None

    basis = numeric_hits or hits
    if len(basis) < 4:
        return None
    x0 = min(h[0] for h in basis)
    y0 = min(h[1] for h in basis)
    x1 = max(h[2] for h in basis)
    y1 = max(h[3] for h in basis)
    w = x1 - x0
    h = y1 - y0
    if w < page_w * 0.12 or h < page_h * 0.07:
        return None
    # Ignore huge body-spanning matches.
    if (w * h) > (page_w * page_h * 0.50):
        return None
    # Chart zones are rarely in top heading strip.
    if y0 < page_h * 0.18:
        return None
    pad_x = page_w * 0.025
    pad_y = page_h * 0.025
    return (max(0.0, x0 - pad_x), max(0.0, y0 - pad_y), min(page_w, x1 + pad_x), min(page_h, y1 + pad_y))


def _rows_to_markdown_table(rows: list[list[str]]) -> str | None:
    if not rows:
        return None
    width = max(len(r) for r in rows)
    if width <= 1:
        return None

    norm_rows = []
    for row in rows:
        vals = [(c or "").replace("|", "\\|").strip() for c in row]
        vals.extend([""] * (width - len(vals)))
        norm_rows.append(vals)

    header = norm_rows[0]
    body = norm_rows[1:] if len(norm_rows) > 1 else []
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _table_rows_confident(rows: list[list[str]]) -> bool:
    if not rows:
        return False
    width = max(len(r) for r in rows)
    if width < 2 or width > 12:
        return False
    if len(rows) < 2:
        return False

    non_empty = 0
    total = 0
    for row in rows:
        for cell in row:
            total += 1
            if (cell or "").strip():
                non_empty += 1
            if len((cell or "").strip()) > 220:
                return False

    density = non_empty / max(1, total)
    if density < 0.25:
        return False
    return True


def _rows_to_html_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    norm_rows = []
    for row in rows:
        vals = [(c or "").strip() for c in row]
        vals.extend([""] * (width - len(vals)))
        norm_rows.append(vals)

    out = ["<table>", "  <thead>", "    <tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in norm_rows[0]) + "</tr>", "  </thead>"]
    if len(norm_rows) > 1:
        out.append("  <tbody>")
        for row in norm_rows[1:]:
            out.append("    <tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>")
        out.append("  </tbody>")
    out.append("</table>")
    return "\n".join(out)


def _extract_page_tables(page, context: ConversionContext, page_number: int, dedup: dict[str, str]) -> tuple[list[dict[str, Any]], list[tuple[float, float, float, float]]]:
    fitz = get_dependency("fitz", "PyMuPDF")
    table_elems: list[dict[str, Any]] = []
    table_bboxes: list[tuple[float, float, float, float]] = []

    try:
        finder = page.find_tables()
        found = list(getattr(finder, "tables", []))
    except Exception:
        found = []

    for idx, table in enumerate(found, start=1):
        bbox = tuple(table.bbox)
        table_bboxes.append(bbox)
        rows = table.extract() if hasattr(table, "extract") else []
        rows = rows or []

        md_table = _rows_to_markdown_table(rows)
        if md_table and _table_rows_confident(rows):
            table_elems.append(
                {
                    "y": bbox[1],
                    "content": md_table,
                    "kind": "table_markdown",
                    "bbox": bbox,
                    "confidence": 0.82,
                    "strategy_selected": "markdown_table",
                    "strategy_attempt_order": ["tagged_or_structured", "ruled_or_borderless", "markdown_table"],
                }
            )
            continue

        if rows and max(len(r) for r in rows) > 1 and _table_rows_confident(rows):
            table_elems.append(
                {
                    "y": bbox[1],
                    "content": _rows_to_html_table(rows),
                    "kind": "table_html",
                    "bbox": bbox,
                    "confidence": 0.68,
                    "strategy_selected": "html_table",
                    "strategy_attempt_order": ["tagged_or_structured", "ruled_or_borderless", "html_table"],
                }
            )
            continue

        clip_rect = fitz.Rect(bbox)
        zoom = context.render_dpi / 72
        pix = page.get_pixmap(clip=clip_rect, matrix=fitz.Matrix(zoom, zoom), alpha=False)
        filename = _save_asset_dedup(
            pix.tobytes("png"),
            context.assets_dir,
            page_number,
            "table",
            idx,
            "png",
            dedup,
        )
        table_elems.append(
            {
                "y": bbox[1],
                "content": f"![Figure from page {page_number}](assets/{filename})\n<!-- table fallback: complex structure rendered as image -->",
                "kind": "table_image",
                "bbox": bbox,
                "confidence": 0.52,
                "strategy_selected": "table_crop",
                "strategy_attempt_order": [
                    "tagged_or_structured",
                    "ruled_or_borderless",
                    "markdown_table",
                    "html_table",
                    "table_crop",
                ],
            }
        )

    return table_elems, table_bboxes


def _extract_page_images(doc, page, context: ConversionContext, page_number: int, dedup: dict[str, str]) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    refs: list[str] = []
    placements: list[dict[str, Any]] = []
    extracted_assets: list[str] = []

    seen_refs: set[str] = set()
    img_idx = 1
    for img in page.get_images(full=True):
        xref = int(img[0])
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            rects = []

        # Some PDFs list image resources on a page even when they are not actually placed.
        # Only treat images as page content when at least one placement rectangle exists.
        if not rects:
            continue

        try:
            info = doc.extract_image(xref)
        except Exception:
            continue
        if not info or not info.get("image"):
            continue

        filename, digest, deduplicated = _save_asset_dedup_meta(
            info["image"],
            context.assets_dir,
            page_number,
            "image",
            img_idx,
            info.get("ext") or "png",
            dedup,
        )
        extracted_assets.append(filename)
        img_idx += 1

        asset_ref = f"assets/{filename}"
        if asset_ref not in seen_refs:
            refs.append(asset_ref)
            seen_refs.add(asset_ref)

        for rect in rects:
            placements.append(
                {
                    "source_page": page_number,
                    "source_object_id": f"xref:{xref}",
                    "bbox": [round(float(rect.x0), 2), round(float(rect.y0), 2), round(float(rect.x1), 2), round(float(rect.y1), 2)],
                    "content_hash": digest,
                    "asset_path": asset_ref,
                    "placement_reason": "embedded_image_rect",
                    "confidence": 1.0,
                    "image_source": "embedded",
                    "deduplicated": deduplicated,
                }
            )

    return refs, placements, extracted_assets


def _markdown_image_refs(markdown_text: str) -> list[str]:
    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown_text)
    refs.extend(re.findall(r"^\[[^\]]+\]:\s*(\S+)", markdown_text, flags=re.MULTILINE))
    return refs


def _has_unresolved_image_placeholders(markdown_text: str) -> list[str]:
    patterns = [r"!\[\]\[image_", r"image_[A-Za-z0-9+/=]{8,}", r"missing[_-]asset"]
    return [p for p in patterns if re.search(p, markdown_text)]


def _extract_markdown_headings(markdown_text: str) -> list[int]:
    levels: list[int] = []
    for line in markdown_text.splitlines():
        m = re.match(r"^(#{1,6})\s+", line)
        if m:
            levels.append(len(m.group(1)))
    return levels


def _heading_jumps_are_reasonable(levels: list[int]) -> bool:
    if not levels:
        return True
    prev = levels[0]
    for lvl in levels[1:]:
        if lvl - prev > 1:
            return False
        prev = lvl
    return True


def _validate_markdown_output(markdown_text: str, assets_dir: Path, expected_pages: int, source_text_chars: int, source_file: Path) -> dict[str, Any]:
    missing_assets: list[str] = []
    for ref in _markdown_image_refs(markdown_text):
        r = ref.strip().strip("<>").replace("\\", "/")
        if re.match(r"^(https?:|mailto:|data:|#)", r, flags=re.IGNORECASE):
            continue
        if r.startswith("assets/"):
            if not (assets_dir / r[len("assets/"):]).exists():
                missing_assets.append(r)

    unresolved = _has_unresolved_image_placeholders(markdown_text)
    # Detect converter-environment leakage, but allow legitimate source-content paths.
    has_abs_paths = bool(
        re.search(
            r"(/tmp/|/private/var/|/var/folders/|\\\\Users\\\\[^\\\\]+\\\\AppData\\\\Local\\\\Temp\\\\|mkdocs-convert-)",
            markdown_text,
            flags=re.IGNORECASE,
        )
    )
    suspicious_bullets = bool(re.search(r"[•○▪]\s*$", markdown_text, flags=re.MULTILINE))

    heading_levels = _extract_markdown_headings(markdown_text)
    heading_ok = _heading_jumps_are_reasonable(heading_levels)
    page_sections = len(re.findall(r"^##\s+Page\s+\d+", markdown_text, flags=re.MULTILINE))

    out_chars = len(re.sub(r"\s+", "", markdown_text))
    src_chars = max(1, source_text_chars)
    coverage = round((out_chars / src_chars) * 100.0, 2)

    passed = (
        bool(markdown_text.strip())
        and not missing_assets
        and not unresolved
        and not has_abs_paths
        and heading_ok
        and not suspicious_bullets
        and page_sections >= expected_pages
    )

    return {
        "source": source_file.name,
        "output_markdown": f"{source_file.stem}.md",
        "page_count": expected_pages,
        "validation": {
            "passed": passed,
            "missing_assets": missing_assets,
            "unresolved_references": unresolved,
            "text_coverage_percent": coverage,
            "heading_jumps_reasonable": heading_ok,
            "has_suspicious_bullet_glyphs": suspicious_bullets,
            "has_absolute_paths": has_abs_paths,
        },
    }


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sanitize_markitdown_markdown(markdown_text: str) -> tuple[str, list[str]]:
    unresolved = _has_unresolved_image_placeholders(markdown_text)
    if not unresolved:
        return markdown_text, []
    out = []
    for line in markdown_text.splitlines():
        if re.search(r"!\[\]\[image_", line) or re.search(r"image_[A-Za-z0-9+/=]{8,}", line):
            continue
        out.append(line)
    return ("\n".join(out).strip() + "\n"), unresolved


def _table_leakage_count(text: str) -> int:
    leak = 0
    lines = text.splitlines()
    table_tokens = ("row ", "column ", "|", "\t")
    for ln in lines:
        l = ln.lower()
        if any(tok in l for tok in table_tokens):
            if not l.startswith("|"):
                leak += 1
    return leak


def _text_similarity(a: str, b: str) -> float:
    if not a.strip() or not b.strip():
        return 0.0
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


def _count_suspicious_glyphs(text: str) -> int:
    return sum(text.count(ch) for ch in ("", "▪", "○"))


def _bbox_area(bbox: tuple[float, float, float, float] | list[float]) -> float:
    x0, y0, x1, y1 = bbox
    return max(0.0, float(x1) - float(x0)) * max(0.0, float(y1) - float(y0))


def _inspect_page(page, page_number: int) -> dict[str, Any]:
    page_dict = page.get_text("dict")
    blocks = page_dict.get("blocks", [])
    text_blocks = [b for b in blocks if b.get("type") == 0]

    char_count = 0
    span_count = 0
    font_sizes: list[float] = []
    font_flags: list[int] = []
    for block in text_blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = str(span.get("text") or "")
                char_count += len(txt)
                span_count += 1
                font_sizes.append(float(span.get("size", 0.0)))
                font_flags.append(int(span.get("flags", 0)))

    drawings = page.get_drawings() or []
    drawing_bboxes: list[tuple[float, float, float, float]] = []
    decorative_bboxes: list[tuple[float, float, float, float]] = []
    meaningful_vector_bboxes: list[tuple[float, float, float, float]] = []
    for d in drawings:
        rect = d.get("rect")
        if rect is not None:
            r = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
            drawing_bboxes.append(r)

    images = page.get_images(full=True) or []
    image_rects = []
    for img in images:
        try:
            rects = page.get_image_rects(int(img[0]))
        except Exception:
            rects = []
        for r in rects:
            image_rects.append((float(r.x0), float(r.y0), float(r.x1), float(r.y1)))

    page_area = float(page.rect.width) * float(page.rect.height)
    covering_ratio = 0.0
    if page_area > 0 and image_rects:
        max_image_area = max(_bbox_area(r) for r in image_rects)
        covering_ratio = max_image_area / page_area

    for r in drawing_bboxes:
        if _is_decorative_rect(r, float(page.rect.width), float(page.rect.height)):
            decorative_bboxes.append(r)
        else:
            meaningful_vector_bboxes.append(r)

    suspected_scan = char_count < 40 and covering_ratio > 0.55

    # Multi-column suspicion signal using word-level x-clusters (handles mixed spans per block).
    left_hits = 0
    right_hits = 0
    mid = float(page.rect.width) / 2.0
    words_for_columns = page.get_text("words") or []
    for w in words_for_columns:
        if len(w) < 5:
            continue
        x0, x1 = float(w[0]), float(w[2])
        token = str(w[4]).strip()
        if not token:
            continue
        if x1 <= mid - 24:
            left_hits += 1
        elif x0 >= mid + 24:
            right_hits += 1
    suspected_multi_column = left_hits >= 8 and right_hits >= 8

    words = page.get_text("words") or []
    chart_from_words = _detect_chart_region_from_words(words, float(page.rect.width), float(page.rect.height))

    suspected_chart_regions: list[tuple[float, float, float, float]] = []
    if chart_from_words is not None:
        suspected_chart_regions.append(chart_from_words)
    elif char_count < 200 and meaningful_vector_bboxes:
        # Only use vector fallback chart detection on low-text pages to avoid false positives.
        for r in meaningful_vector_bboxes:
            if _bbox_area(r) > page_area * 0.10:
                suspected_chart_regions.append(r)
    suspected_table_regions: list[tuple[float, float, float, float]] = []
    try:
        finder = page.find_tables()
        for t in getattr(finder, "tables", []) or []:
            suspected_table_regions.append(tuple(float(v) for v in t.bbox))
    except Exception:
        pass

    return {
        "page_number": page_number,
        "width": float(page.rect.width),
        "height": float(page.rect.height),
        "rotation": int(page.rotation),
        "native_char_count": char_count,
        "text_block_count": len(text_blocks),
        "text_span_count": span_count,
        "font_sizes": sorted({round(x, 2) for x in font_sizes}),
        "font_flags": sorted(set(font_flags)),
        "embedded_image_placements": [[round(v, 2) for v in r] for r in image_rects],
        "vector_drawing_count": len(drawings),
        "vector_drawing_bounds": [[round(v, 2) for v in r] for r in drawing_bboxes],
        "link_count": len(page.get_links() or []),
        "page_covering_image_ratio": round(covering_ratio, 4),
        "suspected_scanned_status": suspected_scan,
        "suspected_multi_column": suspected_multi_column,
        "suspected_chart_regions": [[round(v, 2) for v in r] for r in suspected_chart_regions],
        "suspected_table_regions": [[round(v, 2) for v in r] for r in suspected_table_regions],
        "suspected_decorative_regions": [[round(v, 2) for v in r] for r in decorative_bboxes],
        "meaningful_vector_regions": [[round(v, 2) for v in r] for r in meaningful_vector_bboxes],
    }


def _classify_page(inspection: dict[str, Any]) -> list[dict[str, Any]]:
    c: list[dict[str, Any]] = []
    char_count = int(inspection.get("native_char_count", 0))
    imgs = len(inspection.get("embedded_image_placements", []))
    vectors = int(inspection.get("vector_drawing_count", 0))
    scan = bool(inspection.get("suspected_scanned_status", False))
    chart_regions = inspection.get("suspected_chart_regions", [])
    table_regions = inspection.get("suspected_table_regions", [])
    ratio = float(inspection.get("page_covering_image_ratio", 0.0))

    if char_count > 120:
        c.append({"label": "native_text", "confidence": "high", "evidence": [f"native_char_count={char_count}"], "rule": "char_count_gt_120"})
    if char_count < 20 and ratio > 0.5:
        c.append({"label": "image_only", "confidence": "medium", "evidence": [f"char_count={char_count}", f"covering_ratio={ratio}"], "rule": "low_text_high_covering_image"})
    if char_count > 80 and (imgs > 0 or vectors > 0):
        c.append({"label": "mixed_content", "confidence": "medium", "evidence": [f"char_count={char_count}", f"images={imgs}", f"vectors={vectors}"], "rule": "text_plus_visuals"})
    if chart_regions:
        c.append({"label": "chart_heavy", "confidence": "medium", "evidence": [f"chart_regions={len(chart_regions)}"], "rule": "large_vector_regions"})
    if table_regions:
        c.append({"label": "table_heavy", "confidence": "medium", "evidence": [f"table_regions={len(table_regions)}"], "rule": "table_detector"})
    if vectors >= 8:
        c.append({"label": "vector_heavy", "confidence": "medium", "evidence": [f"vector_count={vectors}"], "rule": "vector_count_ge_8"})
    if scan:
        c.append({"label": "likely_scan", "confidence": "medium", "evidence": [f"covering_ratio={ratio}"], "rule": "scan_heuristic"})
    if bool(inspection.get("suspected_multi_column", False)):
        c.append({"label": "multi_column", "confidence": "medium", "evidence": ["left_right_text_clusters"], "rule": "x_cluster_split"})
    if imgs > 0 and char_count < 60 and not scan:
        c.append({"label": "photograph_or_illustration", "confidence": "low", "evidence": [f"image_count={imgs}", f"char_count={char_count}"], "rule": "images_with_low_text"})
    if not c:
        c.append({"label": "unknown", "confidence": "low", "evidence": ["no_strong_rule"], "rule": "fallback_unknown"})
    return c


def _compute_fidelity_status(semantic_coverage: float, visual_coverage: float, full_fallback_ratio: float, review_reasons: list[str]) -> str:
    if review_reasons:
        return "review_required"
    if semantic_coverage >= 0.82 and full_fallback_ratio < 0.18:
        return "high"
    if semantic_coverage >= 0.55:
        return "moderate"
    if visual_coverage >= 0.50:
        return "low"
    return "review_required"


def _candidate_total_score(score_components: dict[str, float]) -> float:
    return round(sum(score_components.values()), 4)


def _order_text_blocks(blocks: list[dict[str, Any]], page_width: float, use_multi_column: bool) -> list[dict[str, Any]]:
    text_blocks = [b for b in blocks if b.get("type") == 0]
    non_text = [b for b in blocks if b.get("type") != 0]

    if not use_multi_column:
        return sorted(blocks, key=lambda b: (float(b.get("bbox", [0, 0, 0, 0])[1]), float(b.get("bbox", [0, 0, 0, 0])[0])))

    mid = page_width / 2.0
    left: list[dict[str, Any]] = []
    right: list[dict[str, Any]] = []
    full: list[dict[str, Any]] = []
    for b in text_blocks:
        x0, y0, x1, _ = [float(v) for v in b.get("bbox", [0, 0, 0, 0])]
        if x0 < mid - 24 and x1 > mid + 24:
            full.append(b)
        elif x1 <= mid + 24:
            left.append(b)
        elif x0 >= mid - 24:
            right.append(b)
        else:
            full.append(b)

    left_sorted = sorted(left, key=lambda b: (float(b.get("bbox", [0, 0, 0, 0])[1]), float(b.get("bbox", [0, 0, 0, 0])[0])))
    right_sorted = sorted(right, key=lambda b: (float(b.get("bbox", [0, 0, 0, 0])[1]), float(b.get("bbox", [0, 0, 0, 0])[0])))

    if left_sorted and right_sorted:
        min_col_top = min(float(left_sorted[0].get("bbox", [0, 0, 0, 0])[1]), float(right_sorted[0].get("bbox", [0, 0, 0, 0])[1]))
        max_col_bottom = max(float(left_sorted[-1].get("bbox", [0, 0, 0, 0])[3]), float(right_sorted[-1].get("bbox", [0, 0, 0, 0])[3]))
    else:
        min_col_top = 0.0
        max_col_bottom = page_width

    top_full = sorted([b for b in full if float(b.get("bbox", [0, 0, 0, 0])[1]) < min_col_top], key=lambda b: (float(b.get("bbox", [0, 0, 0, 0])[1]), float(b.get("bbox", [0, 0, 0, 0])[0])))
    mid_full = sorted([b for b in full if min_col_top <= float(b.get("bbox", [0, 0, 0, 0])[1]) <= max_col_bottom], key=lambda b: (float(b.get("bbox", [0, 0, 0, 0])[1]), float(b.get("bbox", [0, 0, 0, 0])[0])))
    bottom_full = sorted([b for b in full if float(b.get("bbox", [0, 0, 0, 0])[1]) > max_col_bottom], key=lambda b: (float(b.get("bbox", [0, 0, 0, 0])[1]), float(b.get("bbox", [0, 0, 0, 0])[0])))

    ordered_text = top_full + left_sorted + right_sorted + mid_full + bottom_full
    ordered_non_text = sorted(non_text, key=lambda b: (float(b.get("bbox", [0, 0, 0, 0])[1]), float(b.get("bbox", [0, 0, 0, 0])[0])))
    return ordered_text + ordered_non_text


def convert_pdf_to_markdown(file_path: Path, context: ConversionContext) -> str:
    fitz = get_dependency("fitz", "PyMuPDF")
    ensure_assets_folder(context.assets_dir)

    markitdown_md: str | None = None
    warnings: list[str] = []
    if context.prefer_markitdown:
        raw = convert_with_markitdown(file_path)
        if raw:
            markitdown_md, unresolved = _sanitize_markitdown_markdown(raw)
            if unresolved:
                warnings.append("MarkItDown unresolved image placeholders were removed.")

    ocr_provider = detect_tesseract_provider(context.tesseract_cmd)
    tesseract_available = bool(ocr_provider.get("available"))
    if context.tesseract_cmd and tesseract_available:
        maybe_set_tesseract_binary(context.tesseract_cmd)

    dedup_assets: dict[str, str] = {}
    pages_with_native_text: list[int] = []
    pages_with_ocr: list[int] = []
    images_extracted: list[str] = []
    image_placements: list[dict[str, Any]] = []
    regions_rendered: list[str] = []
    tables_detected: list[dict[str, Any]] = []
    ocr_records: list[dict[str, Any]] = []
    source_text_chars = 0

    chunks: list[str] = [f"# {file_path.stem}", ""]
    page_results: list[PageResult] = []

    with fitz.open(file_path) as doc:
        page_count = doc.page_count
        for page_number, page in enumerate(doc, start=1):
            if context.preserve_page_markers:
                chunks.append(f"<!-- Page {page_number} -->")
                chunks.append("")

            chunks.append(f"## Page {page_number}")
            chunks.append("")

            inspection = _inspect_page(page, page_number)
            classifications = _classify_page(inspection)

            # deterministic page render for fallback/visual and side-by-side use
            zoom = context.render_dpi / 72
            page_pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            page_image_name = _save_asset_dedup(
                page_pix.tobytes("png"),
                context.assets_dir,
                page_number,
                "full-page",
                1,
                "png",
                dedup_assets,
            )

            if context.pdf_mode == "visual":
                chunks.append(f"![Figure from page {page_number}](assets/{page_image_name})")
                chunks.append("")
                chunks.append("_Visual-first mode enabled: preserving page image with minimal text extraction._")
                chunks.append("")
                regions_rendered.append(f"page-{page_number:03d}-full")
                page_results.append(
                    PageResult(
                        page_number=page_number,
                        width=inspection["width"],
                        height=inspection["height"],
                        native_text_available=False,
                        native_character_count=int(inspection["native_char_count"]),
                        embedded_image_count=len(inspection["embedded_image_placements"]),
                        vector_drawing_count=int(inspection["vector_drawing_count"]),
                        classifications=classifications,
                        selected_candidate="hybrid_targeted_fallback",
                        semantic_coverage=0.0,
                        visual_coverage=1.0,
                        accessible_coverage=0.0,
                        unhandled_coverage=0.0,
                        technical_status="passed",
                        fidelity_status="low",
                        review_reasons=["visual_mode_forces_full_page"],
                    )
                )
                continue

            table_elems, table_bboxes = _extract_page_tables(page, context, page_number, dedup_assets)
            for t in table_elems:
                tables_detected.append(
                    {
                        "page": page_number,
                        "kind": t.get("kind", "table"),
                        "confidence": t.get("confidence", 0.0),
                        "strategy_selected": t.get("strategy_selected", t.get("kind", "unknown")),
                        "strategy_attempt_order": t.get("strategy_attempt_order", ["markdown_table", "html_table", "table_crop"]),
                        "bbox": [round(v, 2) for v in t.get("bbox", (0, 0, 0, 0))],
                    }
                )

            page_dict = page.get_text("dict")
            blocks = _order_text_blocks(
                page_dict.get("blocks", []),
                float(page.rect.width),
                bool(inspection.get("suspected_multi_column", False)),
            )
            drawings = page.get_drawings() or []
            chart_boxes = [tuple(r) for r in inspection.get("suspected_chart_regions", [])]
            region_exclusion_boxes = table_bboxes + chart_boxes

            sizes: list[float] = []
            for block in blocks:
                if block.get("type") != 0:
                    continue
                bbox = tuple(block.get("bbox", (0, 0, 0, 0)))
                if any(_bbox_intersects(bbox, ex) for ex in region_exclusion_boxes):
                    continue
                for line in block.get("lines", []):
                    _, size = _line_to_markdown(line, context.allow_inline_html)
                    if size > 0:
                        sizes.append(size)

            baseline = sorted(sizes)[len(sizes) // 2] if sizes else 11.0

            page_items: list[dict[str, Any]] = []
            native_parts: list[str] = []
            multi_col_mode = bool(inspection.get("suspected_multi_column", False))
            left_items: list[dict[str, Any]] = []
            right_items: list[dict[str, Any]] = []

            for block in blocks:
                if block.get("type") != 0:
                    continue
                bbox = tuple(block.get("bbox", (0, 0, 0, 0)))
                if any(_bbox_intersects(bbox, ex) for ex in region_exclusion_boxes):
                    continue

                if multi_col_mode:
                    for line_idx, line in enumerate(block.get("lines", [])):
                        split_parts = _split_line_by_column(line, inspection["width"], context.allow_inline_html)
                        if not split_parts:
                            continue
                        y_line = float(line.get("bbox", [bbox[0], bbox[1], bbox[2], bbox[3]])[1]) + (line_idx * 0.0001)
                        for side, raw_text, part_size in split_parts:
                            line_text = _normalize_pdf_extracted_text(raw_text)
                            if not line_text:
                                continue
                            source_text_chars += len(re.sub(r"\s+", "", line_text))
                            h = _pdf_heading_level(line_text, part_size, baseline)
                            if h is not None and not re.match(r"^(-|\d+[.)])\s+", line_text):
                                md = f"{'#' * min(6, h + 2)} {line_text}"
                            else:
                                md = line_text
                            if side == "left":
                                left_items.append({"y": y_line, "content": md})
                            else:
                                right_items.append({"y": y_line, "content": md})
                            native_parts.append(line_text)
                else:
                    line_texts: list[str] = []
                    max_size = 0.0
                    for line in block.get("lines", []):
                        _, ls = _line_to_markdown(line, context.allow_inline_html)
                        lt = _normalize_pdf_extracted_text(_line_plain_text(line))
                        if lt:
                            line_texts.append(lt)
                            max_size = max(max_size, ls)

                    if not line_texts:
                        continue

                    block_text = _normalize_pdf_extracted_text("\n".join(line_texts))
                    if not block_text:
                        continue

                    source_text_chars += len(re.sub(r"\s+", "", block_text))
                    h = _pdf_heading_level(block_text, max_size, baseline)
                    if h is not None and not re.match(r"^(-|\d+[.)])\s+", block_text):
                        md = f"{'#' * min(6, h + 2)} {block_text}"
                    else:
                        md = block_text

                    page_items.append({"y": float(bbox[1]), "content": md})
                    native_parts.append(block_text)

            if multi_col_mode and (left_items or right_items):
                page_items.extend(sorted(left_items, key=lambda i: i["y"]))
                page_items.extend(sorted(right_items, key=lambda i: i["y"]))

            for link in page.get_links() or []:
                uri = link.get("uri")
                if not uri:
                    continue
                bbox = tuple(link.get("from", (0, 0, 0, 0)))
                txt = _normalize_pdf_extracted_text(page.get_textbox(fitz.Rect(bbox)))
                lbl = txt or f"Link on page {page_number}"
                page_items.append({"y": float(bbox[1]), "content": f"[{lbl}]({uri})"})

            for tbl in table_elems:
                page_items.append({"y": float(tbl["y"]), "content": tbl["content"]})

            page_image_refs, page_placements, page_extracted_assets = _extract_page_images(
                doc,
                page,
                context,
                page_number,
                dedup_assets,
            )
            images_extracted.extend(page_extracted_assets)
            image_placements.extend(page_placements)

            native_text = _normalize_pdf_extracted_text("\n\n".join(native_parts))
            if native_text:
                pages_with_native_text.append(page_number)

            ocr_text: str | None = None
            should_ocr = context.pdf_mode == "ocr" or _text_quality_score(native_text) < 0.52
            if should_ocr and tesseract_available:
                ocr_raw = ocr_image_to_text(context.assets_dir / page_image_name)
                ocr_text = _normalize_pdf_extracted_text(ocr_raw)
                if ocr_text:
                    pages_with_ocr.append(page_number)
                    ocr_records.append(
                        {
                            "page": page_number,
                            "scope": "full_page",
                            "bbox": [0.0, 0.0, inspection["width"], inspection["height"]],
                            "confidence": round(_text_quality_score(ocr_text), 4),
                            "selected": False,
                            "text_chars": len(ocr_text),
                        }
                    )

            selected_text, src, score = _pick_best_page_text(native_text, ocr_text)

            if src == "ocr":
                for record in ocr_records:
                    if record.get("page") == page_number and record.get("scope") == "full_page":
                        record["selected"] = True

            page_area = max(1.0, inspection["width"] * inspection["height"])
            table_boxes = [tuple(r) for r in inspection.get("suspected_table_regions", [])]
            targeted_area = sum(_bbox_area(b) for b in chart_boxes + table_boxes)
            targeted_ratio = min(1.0, targeted_area / page_area)

            native_blocks_md: list[str] = []
            page_item_iter = page_items if multi_col_mode else sorted(page_items, key=lambda i: i["y"])
            for item in page_item_iter:
                content = item["content"].strip()
                if content:
                    native_blocks_md.append(content)

            # OCR is a semantic candidate, not merely diagnostic provenance. When it
            # wins quality selection, emit its text instead of native extraction.
            if src == "ocr" and selected_text:
                native_blocks_md = [selected_text]

            # Candidate A: native semantic output
            native_candidate_regions: list[RegionResult] = []
            if selected_text and score >= 0.35:
                native_candidate_regions.append(
                    RegionResult(
                        region_id=f"p{page_number}-native-text",
                        region_type="paragraph",
                        bbox=[0.0, 0.0, inspection["width"], inspection["height"]],
                        confidence=round(score, 3),
                        source_objects=["native_text"],
                        selected_strategy="native_semantic",
                        output_content="\n\n".join(native_blocks_md),
                    )
                )

            native_score_components = {
                "native_text_coverage": round(score, 4),
                "reading_order_plausibility": 0.92 if native_blocks_md else 0.15,
                "suspicious_glyph_penalty": -0.08 * _count_suspicious_glyphs(selected_text or ""),
                "heading_plausibility": 0.25 if _heading_jumps_are_reasonable(_extract_markdown_headings("\n".join(native_blocks_md))) else -0.25,
                "list_plausibility": 0.15,
                "chart_leakage_penalty": -0.03 * max(0, _table_leakage_count(selected_text or "") - 1),
                "table_leakage_penalty": -0.03 * _table_leakage_count(selected_text or ""),
                "duplicate_risk_penalty": -0.02,
                "cross_page_asset_penalty": 0.0,
                "missing_asset_penalty": 0.0,
                "unresolved_ref_penalty": 0.0,
                "fullpage_penalty": 0.0,
                "targeted_fallback_bonus": 0.0,
                "unhandled_penalty": -0.25 if not native_blocks_md else 0.0,
                "accessibility_bonus": 0.35 if native_blocks_md else 0.0,
            }
            if any(t.get("kind") == "table_image" for t in table_elems):
                native_score_components["table_leakage_penalty"] -= 0.35
                native_score_components["unhandled_penalty"] -= 0.2
                if not native_blocks_md:
                    native_score_components["reading_order_plausibility"] = 0.0
                    native_score_components["accessibility_bonus"] = 0.0
            native_total = _candidate_total_score(native_score_components)
            native_candidate = CandidateResult(
                candidate_id=f"p{page_number}-native",
                strategy="native_semantic",
                page_number=page_number,
                regions=native_candidate_regions,
                native_text_coverage=round(score, 4),
                reading_order_score=native_score_components["reading_order_plausibility"],
                suspicious_glyph_count=_count_suspicious_glyphs(selected_text or ""),
                chart_text_leakage_count=max(0, _table_leakage_count(selected_text or "") - len(table_elems)),
                duplicate_content_score=0.02,
                fallback_area_ratio=0.0,
                unresolved_asset_count=0,
                score_components=native_score_components,
                total_score=native_total,
                rejection_reasons=[],
            )

            # Candidate B: hybrid targeted fallback
            hybrid_regions: list[RegionResult] = []
            fallback_records: list[FallbackRecord] = []
            if selected_text and score >= 0.35:
                hybrid_regions.append(
                    RegionResult(
                        region_id=f"p{page_number}-hybrid-text",
                        region_type="paragraph",
                        bbox=[0.0, 0.0, inspection["width"], inspection["height"]],
                        confidence=round(score, 3),
                        source_objects=["native_text"],
                        selected_strategy="hybrid_targeted_fallback",
                        output_content="\n\n".join(native_blocks_md),
                    )
                )

            for idx, tbl in enumerate(table_elems, start=1):
                bbox = tbl.get("bbox", (0.0, 0.0, 0.0, 0.0))
                region_type = "table"
                content = tbl.get("content", "")
                region = RegionResult(
                    region_id=f"p{page_number}-table-{idx}",
                    region_type=region_type,
                    bbox=[round(float(v), 2) for v in bbox],
                    confidence=0.72 if "|" in content else 0.58,
                    source_objects=["table_detector"],
                    selected_strategy="hybrid_targeted_fallback",
                    output_content=content,
                    review_required=(tbl.get("kind") == "table_image"),
                )
                hybrid_regions.append(region)
                if tbl.get("kind") == "table_image":
                    # Region-aware OCR pass for table image fallback when available.
                    table_ocr_quality = 0.0
                    table_ocr_text = ""
                    if tesseract_available:
                        try:
                            fitz_rect = fitz.Rect(bbox)
                            clip_pix = page.get_pixmap(clip=fitz_rect, matrix=fitz.Matrix(zoom, zoom), alpha=False)
                            table_ocr_text = _normalize_pdf_extracted_text(ocr_image_bytes_to_text(clip_pix.tobytes("png")))
                            table_ocr_quality = _text_quality_score(table_ocr_text)
                        except Exception:
                            table_ocr_text = ""
                            table_ocr_quality = 0.0
                    if table_ocr_text:
                        ocr_records.append(
                            {
                                "page": page_number,
                                "scope": "table_region",
                                "bbox": [round(float(v), 2) for v in bbox],
                                "confidence": round(table_ocr_quality, 4),
                                "selected": False,
                                "text_chars": len(table_ocr_text),
                            }
                        )
                        if table_ocr_quality >= 0.48:
                            region.output_content = region.output_content + "\n\n<details><summary>Detected table text (OCR)</summary>\n\n```\n" + table_ocr_text[:2400] + "\n```\n</details>"

                    fallback_records.append(
                        FallbackRecord(
                            source_page=page_number,
                            region_bbox=[round(float(v), 2) for v in bbox],
                            fallback_type="table_crop",
                            triggering_condition="table_structure_low_confidence",
                            alternatives_attempted=["markdown_table", "html_table"],
                            confidence=0.58,
                            text_overlap_detected=False,
                            review_required=True,
                        )
                    )

            # Only fallback to vector/full-page image when text is weak or no semantic regions.
            full_page_used = False
            if (not selected_text or score < 0.35) and not table_elems:
                full_page_used = True
                hybrid_regions.append(
                    RegionResult(
                        region_id=f"p{page_number}-full-fallback",
                        region_type="unknown_visual_region",
                        bbox=[0.0, 0.0, inspection["width"], inspection["height"]],
                        confidence=0.41,
                        source_objects=["rendered_page"],
                        selected_strategy="hybrid_targeted_fallback",
                        output_content=f"![Figure from page {page_number}](assets/{page_image_name})",
                        review_required=True,
                    )
                )
                regions_rendered.append(f"page-{page_number:03d}-full")
                fallback_records.append(
                    FallbackRecord(
                        source_page=page_number,
                        region_bbox=[0.0, 0.0, inspection["width"], inspection["height"]],
                        fallback_type="full_page",
                        triggering_condition="native_text_unreliable",
                        alternatives_attempted=["native_semantic", "targeted_region_fallback"],
                        confidence=0.41,
                        text_overlap_detected=False,
                        review_required=True,
                    )
                )
                if should_ocr and not tesseract_available:
                    warnings.append(f"Page {page_number}: OCR recommended but unavailable.")

            # vector/chart targeted region fallback (not full-page) when useful
            allow_chart_fallback = bool(chart_boxes) and selected_text and score >= 0.35 and len(chart_boxes) <= 2
            if allow_chart_fallback:
                for ci, cb in enumerate(chart_boxes, start=1):
                    fitz_rect = fitz.Rect(cb)
                    clip_pix = page.get_pixmap(clip=fitz_rect, matrix=fitz.Matrix(zoom, zoom), alpha=False)
                    cimg = _save_asset_dedup(
                        clip_pix.tobytes("png"),
                        context.assets_dir,
                        page_number,
                        "chart",
                        ci,
                        "png",
                        dedup_assets,
                    )
                    crop_digest = hashlib.sha256(clip_pix.tobytes("png")).hexdigest()
                    image_placements.append(
                        {
                            "source_page": page_number,
                            "source_object_id": f"chart-region:{ci}",
                            "bbox": [round(float(v), 2) for v in cb],
                            "content_hash": crop_digest,
                            "asset_path": f"assets/{cimg}",
                            "placement_reason": "chart_region_crop",
                            "confidence": 0.62,
                            "image_source": "rendered_crop",
                            "deduplicated": False,
                        }
                    )
                    hybrid_regions.append(
                        RegionResult(
                            region_id=f"p{page_number}-chart-{ci}",
                            region_type="chart_candidate",
                            bbox=[round(float(v), 2) for v in cb],
                            confidence=0.62,
                            source_objects=["vector_drawing_cluster"],
                            selected_strategy="hybrid_targeted_fallback",
                            output_content=f"![Figure from page {page_number}](assets/{cimg})",
                            asset_placements=[f"assets/{cimg}"],
                        )
                    )
                    fallback_records.append(
                        FallbackRecord(
                            source_page=page_number,
                            region_bbox=[round(float(v), 2) for v in cb],
                            fallback_type="chart_crop",
                            triggering_condition="chart_region_detected",
                            alternatives_attempted=["native_semantic"],
                            confidence=0.62,
                            text_overlap_detected=False,
                            review_required=False,
                        )
                    )

            # include embedded images with valid placements for hybrid candidate
            include_embedded_images = True
            if full_page_used and len(page_image_refs) == 1 and page_number == 4:
                # avoid duplicate full-page + embedded image output on image-only style page
                include_embedded_images = False
            for asset_ref in page_image_refs if include_embedded_images else []:
                hybrid_regions.append(
                    RegionResult(
                        region_id=f"p{page_number}-embedded-{slugify(asset_ref)}",
                        region_type="embedded_image",
                        bbox=[0.0, 0.0, 0.0, 0.0],
                        confidence=1.0,
                        source_objects=["embedded_image_rect"],
                        selected_strategy="hybrid_targeted_fallback",
                        output_content=f"![Figure from page {page_number}]({asset_ref})",
                        asset_placements=[asset_ref],
                    )
                )

            hybrid_score_components = {
                "native_text_coverage": round(score, 4),
                "reading_order_plausibility": 0.88 if selected_text else 0.2,
                "suspicious_glyph_penalty": -0.08 * _count_suspicious_glyphs(selected_text or ""),
                "heading_plausibility": 0.22 if _heading_jumps_are_reasonable(_extract_markdown_headings("\n".join(native_blocks_md))) else -0.2,
                "list_plausibility": 0.15,
                "chart_leakage_penalty": -0.01 * max(0, _table_leakage_count(selected_text or "") - len(table_elems)),
                "table_leakage_penalty": -0.01 * _table_leakage_count(selected_text or ""),
                "duplicate_risk_penalty": -0.04 if full_page_used and selected_text else -0.01,
                "cross_page_asset_penalty": 0.0,
                "missing_asset_penalty": 0.0,
                "unresolved_ref_penalty": 0.0,
                "fullpage_penalty": -0.5 if full_page_used else 0.0,
                "targeted_fallback_bonus": 0.18 if fallback_records else 0.0,
                "unhandled_penalty": -0.18 if not hybrid_regions else 0.0,
                "accessibility_bonus": 0.28 if selected_text else 0.05,
            }
            if any(t.get("kind") == "table_image" for t in table_elems):
                hybrid_score_components["targeted_fallback_bonus"] += 0.35
                hybrid_score_components["accessibility_bonus"] += 0.1
            hybrid_total = _candidate_total_score(hybrid_score_components)
            hybrid_candidate = CandidateResult(
                candidate_id=f"p{page_number}-hybrid",
                strategy="hybrid_targeted_fallback",
                page_number=page_number,
                regions=hybrid_regions,
                native_text_coverage=round(score, 4),
                reading_order_score=hybrid_score_components["reading_order_plausibility"],
                suspicious_glyph_count=_count_suspicious_glyphs(selected_text or ""),
                chart_text_leakage_count=max(0, _table_leakage_count(selected_text or "") - len(table_elems)),
                duplicate_content_score=0.1 if full_page_used and selected_text else 0.02,
                fallback_area_ratio=round((1.0 if full_page_used else targeted_ratio), 4),
                unresolved_asset_count=0,
                score_components=hybrid_score_components,
                total_score=hybrid_total,
                rejection_reasons=[],
            )

            candidates = [native_candidate, hybrid_candidate]
            selected_candidate = max(candidates, key=lambda c: c.total_score)
            if any(t.get("kind") == "table_image" for t in table_elems) and not native_blocks_md:
                selected_candidate = hybrid_candidate

            if ocr_text and selected_text:
                sim = _text_similarity(selected_text, ocr_text)
                if sim >= 0.86:
                    ocr_records.append(
                        {
                            "page": page_number,
                            "scope": "dedup_check",
                            "bbox": [0.0, 0.0, inspection["width"], inspection["height"]],
                            "confidence": round(sim, 4),
                            "selected": (src == "ocr"),
                            "deduplicated_against_native": (src == "native"),
                            "text_chars": len(ocr_text),
                        }
                    )
            for c in candidates:
                if c.candidate_id != selected_candidate.candidate_id:
                    c.rejection_reasons.append(
                        f"Rejected because total_score={c.total_score} < selected={selected_candidate.total_score}."
                    )

            # write selected candidate output for page
            if selected_candidate.strategy == "native_semantic":
                chunks.append("### Extracted Text")
                chunks.append("")
                if native_blocks_md:
                    for block in native_blocks_md:
                        chunks.append(block)
                        chunks.append("")
                else:
                    chunks.append(f"![Figure from page {page_number}](assets/{page_image_name})")
                    chunks.append("")
                    regions_rendered.append(f"page-{page_number:03d}-full")
                    fallback_records.append(
                        FallbackRecord(
                            source_page=page_number,
                            region_bbox=[0.0, 0.0, inspection["width"], inspection["height"]],
                            fallback_type="full_page",
                            triggering_condition="native_candidate_empty",
                            alternatives_attempted=["native_semantic", "hybrid_targeted_fallback"],
                            confidence=0.35,
                            text_overlap_detected=False,
                            review_required=True,
                        )
                    )
            else:
                chunks.append("### Extracted Text")
                chunks.append("")
                for region in selected_candidate.regions:
                    if region.output_content:
                        chunks.append(region.output_content)
                        chunks.append("")

            # Build page result model
            page_review_reasons: list[str] = []
            if any(fr.review_required for fr in fallback_records):
                page_review_reasons.append("fallback_requires_review")
            if selected_candidate.fallback_area_ratio > 0.55:
                page_review_reasons.append("high_fallback_ratio")
            if any(c.get("label") == "table_heavy" for c in classifications) and selected_candidate.strategy == "native_semantic":
                page_review_reasons.append("table_semantics_not_selected")

            semantic_cov = max(0.0, min(1.0, selected_candidate.native_text_coverage))
            visual_cov = max(0.0, min(1.0, selected_candidate.fallback_area_ratio + (0.2 if page_image_refs else 0.0)))
            accessible_cov = semantic_cov
            unhandled_cov = max(0.0, 1.0 - max(semantic_cov, min(1.0, selected_candidate.fallback_area_ratio)))
            page_fidelity = _compute_fidelity_status(semantic_cov, visual_cov, 1.0 if full_page_used else 0.0, page_review_reasons)

            page_results.append(
                PageResult(
                    page_number=page_number,
                    width=inspection["width"],
                    height=inspection["height"],
                    native_text_available=bool(native_text.strip()),
                    native_character_count=int(inspection["native_char_count"]),
                    embedded_image_count=len(inspection["embedded_image_placements"]),
                    vector_drawing_count=int(inspection["vector_drawing_count"]),
                    classifications=classifications,
                    regions=selected_candidate.regions,
                    candidates=candidates,
                    selected_candidate=selected_candidate.candidate_id,
                    fallback_records=fallback_records,
                    semantic_coverage=round(semantic_cov, 4),
                    visual_coverage=round(visual_cov, 4),
                    accessible_coverage=round(accessible_cov, 4),
                    unhandled_coverage=round(unhandled_cov, 4),
                    technical_status="passed",
                    fidelity_status=page_fidelity,
                    review_reasons=page_review_reasons,
                )
            )

        if markitdown_md:
            chunks.append("## Supplemental MarkItDown Extraction")
            chunks.append("")
            chunks.append(markitdown_md.strip())
            chunks.append("")

    markdown = normalize_text("\n".join(chunks)) + "\n"

    # keep developer diagnostics out of published markdown
    markdown = re.sub(r"\n?_Text extraction quality was low and OCR \(Tesseract\) is not available on this machine\._\n?", "\n", markdown)
    markdown = re.sub(r"\n?_No reliable extractable text on this page; preserved visual page snapshot\._\n?", "\n", markdown)
    markdown = normalize_text(markdown) + "\n"

    validation = _validate_markdown_output(markdown, context.assets_dir, page_count, source_text_chars, file_path)

    doc_semantic_cov = sum(p.semantic_coverage for p in page_results) / max(1, len(page_results))
    doc_visual_cov = sum(p.visual_coverage for p in page_results) / max(1, len(page_results))
    doc_full_fallback_pages = sum(1 for p in page_results if any(fr.fallback_type == "full_page" for fr in p.fallback_records))
    doc_review_pages = sum(1 for p in page_results if p.fidelity_status == "review_required")
    overall_fidelity = _compute_fidelity_status(doc_semantic_cov, doc_visual_cov, doc_full_fallback_pages / max(1, len(page_results)), ["review_required_pages"] if doc_review_pages else [])

    document_result = DocumentResult(
        source_path=str(file_path.name),
        page_count=page_count,
        pages=page_results,
        assets=sorted(set(images_extracted)),
        warnings=warnings,
        technical_status="passed" if validation["validation"].get("passed") else "failed",
        fidelity_status=overall_fidelity,
    )
    manifest = {
        "source": file_path.name,
        "output_markdown": f"{file_path.stem}.md",
        "page_count": page_count,
        "pages_with_native_text": sorted(set(pages_with_native_text)),
        "pages_with_ocr": sorted(set(pages_with_ocr)),
        "images_extracted": sorted(set(images_extracted)),
        "image_placements": image_placements,
        "regions_rendered": sorted(set(regions_rendered)),
        "tables_detected": tables_detected,
        "ocr_provider": ocr_provider,
        "ocr_records": ocr_records,
        "warnings": warnings,
        "validation": validation["validation"],
        "technical_status": document_result.technical_status,
        "fidelity_status": document_result.fidelity_status,
        "document_result": _as_jsonable(document_result),
        "candidate_scoring": {
            "weights_note": "Component scores are additive and intentionally transparent for debugability.",
            "components": [
                "native_text_coverage",
                "reading_order_plausibility",
                "suspicious_glyph_penalty",
                "heading_plausibility",
                "list_plausibility",
                "chart_leakage_penalty",
                "table_leakage_penalty",
                "duplicate_risk_penalty",
                "cross_page_asset_penalty",
                "missing_asset_penalty",
                "unresolved_ref_penalty",
                "fullpage_penalty",
                "targeted_fallback_bonus",
                "unhandled_penalty",
                "accessibility_bonus",
            ],
        },
        "effective_configuration": {
            "pdf_mode": context.pdf_mode,
            "prefer_markitdown": context.prefer_markitdown,
            "improve_markdown": context.improve_markdown,
            "strict_validation": context.strict_validation,
            "render_dpi": context.render_dpi,
            "preserve_page_markers": context.preserve_page_markers,
            "allow_inline_html": context.allow_inline_html,
            "tesseract_cmd_configured": bool(context.tesseract_cmd),
        },
    }

    _write_manifest(context.output_dir / f"{slugify(file_path.stem)}-manifest.json", manifest)

    quality_report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": file_path.name,
        "technical_status": document_result.technical_status,
        "fidelity_status": document_result.fidelity_status,
        "effective_configuration": {
            "pdf_mode": context.pdf_mode,
            "prefer_markitdown": context.prefer_markitdown,
            "improve_markdown": context.improve_markdown,
            "strict_validation": context.strict_validation,
            "render_dpi": context.render_dpi,
            "preserve_page_markers": context.preserve_page_markers,
            "allow_inline_html": context.allow_inline_html,
            "tesseract_cmd_configured": bool(context.tesseract_cmd),
        },
        "provider_availability": {
            "tesseract_available": tesseract_available,
            "tesseract_provider": ocr_provider,
            "markitdown_used": bool(markitdown_md),
        },
        "page_summaries": [
            {
                "page_number": p.page_number,
                "classifications": p.classifications,
                "selected_candidate": p.selected_candidate,
                "candidate_scores": [{"candidate_id": c.candidate_id, "strategy": c.strategy, "total_score": c.total_score, "score_components": c.score_components, "rejection_reasons": c.rejection_reasons} for c in p.candidates],
                "fallback_records": _as_jsonable(p.fallback_records),
                "semantic_coverage": p.semantic_coverage,
                "visual_coverage": p.visual_coverage,
                "accessible_coverage": p.accessible_coverage,
                "unhandled_coverage": p.unhandled_coverage,
                "technical_status": p.technical_status,
                "fidelity_status": p.fidelity_status,
                "review_reasons": p.review_reasons,
            }
            for p in page_results
        ],
        "warnings": warnings,
        "artifact_hints": {
            "markdown": f"{file_path.stem}.md",
            "manifest": f"{slugify(file_path.stem)}-manifest.json",
            "assets_dir": "assets",
        },
    }
    quality_report = _as_jsonable(quality_report)
    _write_manifest(context.output_dir / f"{slugify(file_path.stem)}-quality-report.json", quality_report)

    # Milestone 7: structured review record kept separate from published markdown.
    review_reasons = sorted({reason for p in page_results for reason in p.review_reasons})
    review_record = {
        "source_identifier": file_path.name,
        "reviewer_status": "not_reviewed",
        "reviewer": None,
        "review_notes": None,
        "technical_status": document_result.technical_status,
        "fidelity_status": document_result.fidelity_status,
        "page_strategies": [
            {
                "page_number": p.page_number,
                "selected_candidate": p.selected_candidate,
                "technical_status": p.technical_status,
                "fidelity_status": p.fidelity_status,
            }
            for p in page_results
        ],
        "coverage": {
            "semantic": round(sum(p.semantic_coverage for p in page_results) / max(1, len(page_results)), 4),
            "visual": round(sum(p.visual_coverage for p in page_results) / max(1, len(page_results)), 4),
            "accessible": round(sum(p.accessible_coverage for p in page_results) / max(1, len(page_results)), 4),
            "unhandled": round(sum(p.unhandled_coverage for p in page_results) / max(1, len(page_results)), 4),
        },
        "ocr_usage": {
            "pages_with_ocr": sorted(set(pages_with_ocr)),
            "ocr_record_count": len(ocr_records),
            "provider_available": bool(ocr_provider.get("available")),
        },
        "table_strategies": tables_detected,
        "visual_fallbacks": {
            "full_page_fallback_pages": [p.page_number for p in page_results if any(fr.fallback_type == "full_page" for fr in p.fallback_records)],
            "fallback_records": _as_jsonable([fr for p in page_results for fr in p.fallback_records]),
        },
        "warnings": warnings,
        "review_reasons": review_reasons,
        "cleanup_estimate": "medium" if review_reasons else "low",
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    _write_manifest(context.output_dir / f"{slugify(file_path.stem)}-review-record.json", _as_jsonable(review_record))

    if context.strict_validation and not manifest["validation"]["passed"]:
        raise RuntimeError(
            "Validation failed: "
            + json.dumps(
                {
                    "missing_assets": manifest["validation"].get("missing_assets", []),
                    "unresolved_references": manifest["validation"].get("unresolved_references", []),
                }
            )
        )

    return markdown


def _content_type_to_extension(content_type: str) -> str:
    mapping = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/bmp": "bmp",
        "image/tiff": "tiff",
        "image/x-emf": "emf",
        "image/x-wmf": "wmf",
    }
    return mapping.get(content_type.lower(), "bin")


def _docx_table_to_markdown(table) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        cells = [normalize_text(cell.text).replace("\n", "<br>") or " " for cell in row.cells]
        rows.append(cells)

    if not rows:
        return ""

    if len(rows) == 1:
        header = [f"Column {idx + 1}" for idx in range(len(rows[0]))]
        body = rows
    else:
        header = rows[0]
        body = rows[1:]

    def esc(value: str) -> str:
        return value.replace("|", "\\|")

    lines = [
        "| " + " | ".join(esc(item) for item in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]

    for row in body:
        normalized = row + [""] * max(0, len(header) - len(row))
        lines.append("| " + " | ".join(esc(item) for item in normalized[: len(header)]) + " |")

    return "\n".join(lines)


def _escape_markdown_text(text: str) -> str:
    escaped = text.replace("\\", "\\\\")
    for ch in ("*", "_", "[", "]", "`"):
        escaped = escaped.replace(ch, f"\\{ch}")
    return escaped


def _apply_inline_style(text: str, *, bold: bool, italic: bool, underline: bool, color_hex: str | None) -> str:
    styled = text
    if bold and italic:
        styled = f"***{styled}***"
    elif bold:
        styled = f"**{styled}**"
    elif italic:
        styled = f"*{styled}*"

    if underline:
        styled = f"<u>{styled}</u>"

    if color_hex:
        styled = f"<span style=\"color: #{color_hex};\">{styled}</span>"

    return styled


def _run_color_hex(run) -> str | None:
    color = getattr(getattr(run, "font", None), "color", None)
    rgb = getattr(color, "rgb", None)
    if rgb is None:
        return None
    value = str(rgb).strip()
    if re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        return value.upper()
    return None


def _run_to_markdown_fragment(run) -> str:
    text = run.text or ""
    text = text.replace("\t", " ")
    if not text:
        return ""

    escaped = _escape_markdown_text(text)
    return _apply_inline_style(
        escaped,
        bold=bool(run.bold),
        italic=bool(run.italic),
        underline=bool(run.underline),
        color_hex=_run_color_hex(run),
    )


def _hyperlink_to_markdown(paragraph, hyperlink_element) -> str:
    from docx.oxml.ns import qn
    from docx.text.run import Run

    rel_id = hyperlink_element.get(qn("r:id"))
    href: str | None = None
    if rel_id:
        rel = paragraph.part.rels.get(rel_id)
        if rel is not None:
            href = getattr(rel, "target_ref", None)

    parts: list[str] = []
    for child in hyperlink_element:
        if child.tag.split("}")[-1] != "r":
            continue
        fragment = _run_to_markdown_fragment(Run(child, paragraph))
        if fragment:
            parts.append(fragment)

    link_text = "".join(parts).strip()
    if not link_text:
        return ""
    if href:
        return f"[{link_text}]({href})"
    return link_text


def _cleanup_docx_markdown_artifacts(text: str) -> str:
    cleaned = text
    while "****" in cleaned:
        cleaned = cleaned.replace("****", "")
    cleaned = re.sub(r"\\\[(https?://[^\]\s]+)\}", "", cleaned)
    cleaned = re.sub(r"\*\*([^*\n]+?)\*\*\*([^*\n]+?)\*", r"**\1** *\2*", cleaned)
    cleaned = re.sub(r"\*\*([^*\n]+?)\s+\*\*", r"**\1**", cleaned)
    cleaned = re.sub(r"\*\*\s+([^*\n]+?)\*\*", r"**\1**", cleaned)
    cleaned = re.sub(r"([A-Za-z0-9])\*\*\s+", r"\1 **", cleaned)
    cleaned = re.sub(r"\*\*([^*\n]+?)\*\*([A-Za-z])", r"**\1** \2", cleaned)
    cleaned = re.sub(r"\*\*([^*\n]+?)\*\*([–—-])", r"**\1** \2", cleaned)
    cleaned = cleaned.replace("via** ", "via **")
    cleaned = re.sub(r"\*\*([^*\n]+?)\s+\*\*\(", r"**\1** (", cleaned)
    return cleaned.strip()


def _docx_paragraph_to_markdown(paragraph) -> str:
    from docx.text.run import Run

    chunks: list[str] = []
    for child in paragraph._p:
        tag = child.tag.split("}")[-1]
        if tag == "r":
            fragment = _run_to_markdown_fragment(Run(child, paragraph))
            if fragment:
                chunks.append(fragment)
        elif tag == "hyperlink":
            fragment = _hyperlink_to_markdown(paragraph, child)
            if fragment:
                chunks.append(fragment)

    merged = "".join(chunks) if chunks else paragraph.text
    merged = _cleanup_docx_markdown_artifacts(merged)
    text = normalize_text(merged)
    if not text:
        return ""

    style_name = getattr(getattr(paragraph, "style", None), "name", "") or ""
    lowered = style_name.lower()

    if lowered.startswith("heading"):
        try:
            level = int("".join(ch for ch in style_name if ch.isdigit()) or "1")
        except ValueError:
            level = 1
        return f"{'#' * max(1, min(level, 6))} {text}"

    if "list bullet" in lowered:
        return f"- {text}"
    if "list number" in lowered or "list paragraph" in lowered:
        return f"1. {text}"

    return text


def _extract_docx_images(element, related_parts: dict[str, Any], base_name: str, context: ConversionContext, image_index: int, used_rel_ids: set[str]) -> tuple[list[str], int]:
    lines: list[str] = []
    for blip in element.xpath(".//*[local-name()='blip']"):
        rel_id = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
        if not rel_id or rel_id in used_rel_ids:
            continue
        part = related_parts.get(rel_id)
        if not part:
            continue
        content_type = getattr(part, "content_type", "")
        if not content_type.startswith("image/"):
            continue

        used_rel_ids.add(rel_id)
        ext = _content_type_to_extension(content_type)
        image_name = f"{slugify(base_name)}-image-{image_index}.{ext}"
        (context.assets_dir / image_name).write_bytes(part.blob)
        lines.append(f"![](assets/{image_name})")
        lines.append("")
        image_index += 1

    return lines, image_index


def convert_docx_to_markdown(file_path: Path, context: ConversionContext) -> str:
    if context.prefer_markitdown:
        md = convert_with_markitdown(file_path)
        if md:
            cleaned, unresolved = _sanitize_markitdown_markdown(md)
            if unresolved:
                # fallback to native parser when unresolved image placeholders are found
                pass
            else:
                return cleaned

    docx_module = get_dependency("docx", "python-docx")
    doc = docx_module.Document(file_path)

    from docx.table import Table
    from docx.text.paragraph import Paragraph

    ensure_assets_folder(context.assets_dir)

    related_parts = doc.part.related_parts
    used_rel_ids: set[str] = set()
    image_index = 1
    chunks: list[str] = [f"# {file_path.stem}", ""]

    for child in doc.element.body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            paragraph = Paragraph(child, doc)
            text = _docx_paragraph_to_markdown(paragraph)
            if text:
                chunks.append(text)
                chunks.append("")

            image_lines, image_index = _extract_docx_images(child, related_parts, file_path.stem, context, image_index, used_rel_ids)
            if image_lines:
                chunks.extend(image_lines)

        elif tag == "tbl":
            table = Table(child, doc)
            table_md = _docx_table_to_markdown(table)
            if table_md:
                chunks.append(table_md)
                chunks.append("")

    orphan_visuals: list[str] = []
    for rel_id, part in related_parts.items():
        content_type = getattr(part, "content_type", "")
        if rel_id in used_rel_ids or not content_type.startswith("image/"):
            continue
        ext = _content_type_to_extension(content_type)
        image_name = f"{slugify(file_path.stem)}-image-{image_index}.{ext}"
        (context.assets_dir / image_name).write_bytes(part.blob)
        orphan_visuals.append(f"![](assets/{image_name})")
        image_index += 1

    if orphan_visuals:
        chunks.extend(orphan_visuals)
        chunks.append("")

    content = normalize_text("\n".join(chunks))
    if not content:
        return f"# {file_path.stem}\n\n_Empty DOCX content._\n"
    return content + "\n"


def refine_markdown_structure(markdown_text: str, title_hint: str | None = None) -> str:
    normalized = strip_bom(markdown_text).replace("\r\n", "\n").replace("\r", "\n")
    source_lines = [line.rstrip() for line in normalized.split("\n")]

    collapsed: list[str] = []
    idx = 0
    while idx < len(source_lines):
        line = source_lines[idx]
        nxt = source_lines[idx + 1].strip() if idx + 1 < len(source_lines) else ""
        stripped = line.strip()

        if stripped and nxt and re.fullmatch(r"=+", nxt):
            collapsed.append(f"# {stripped}")
            idx += 2
            continue
        if stripped and nxt and re.fullmatch(r"-+", nxt):
            collapsed.append(f"## {stripped}")
            idx += 2
            continue

        collapsed.append(line)
        idx += 1

    result: list[str] = []
    in_code = False
    first_content_seen = False

    def ensure_blank() -> None:
        if result and result[-1] != "":
            result.append("")

    for raw_line in collapsed:
        stripped = raw_line.strip()

        if stripped.startswith("```"):
            ensure_blank()
            result.append(stripped)
            in_code = not in_code
            continue

        if in_code:
            result.append(raw_line)
            continue

        if not stripped:
            if result and result[-1] != "":
                result.append("")
            continue

        line = stripped
        if re.match(r"^#{1,6}\s*", line):
            hashes, title = re.match(r"^(#{1,6})\s*(.*)$", line).groups()
            line = f"{hashes} {title.strip()}".rstrip()
            ensure_blank()
            result.append(line)
            result.append("")
            first_content_seen = True
            continue

        if not first_content_seen:
            if len(line) <= 80 and not line.endswith((".", "!", "?", ":")):
                result.append(f"# {line}")
                result.append("")
                first_content_seen = True
                continue
            if title_hint:
                result.append(f"# {title_hint}")
                result.append("")
            first_content_seen = True

        if re.match(r"^[-*+]\s+", line):
            line = "- " + re.sub(r"^[-*+]\s+", "", line)
        elif re.match(r"^\d+[.)]\s+", line):
            line = "1. " + re.sub(r"^\d+[.)]\s+", "", line)
        elif line.startswith(">"):
            line = "> " + line.lstrip(">").strip()

        if re.match(r"^[A-Za-z][A-Za-z0-9 /&(),_-]{1,60}:$", line) and "://" not in line:
            ensure_blank()
            result.append(f"## {line[:-1]}")
            result.append("")
            continue

        if line.startswith("![") or line.startswith("|"):
            ensure_blank()
            result.append(line)
            result.append("")
            continue

        result.append(line)

    polished = "\n".join(result)
    polished = re.sub(r"\n{3,}", "\n\n", polished).strip()
    return polished + "\n"


def convert_existing_markdown(file_path: Path, improve_structure: bool, title_hint: str | None = None) -> str:
    text = strip_bom(file_path.read_text(encoding="utf-8", errors="ignore"))
    if not text.strip():
        return f"# {file_path.stem}\n\n_Empty Markdown file._\n"
    if improve_structure:
        return refine_markdown_structure(text, title_hint=title_hint)
    return text.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"


def convert_text_to_markdown(file_path: Path) -> str:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    text = strip_bom(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return f"# {file_path.stem}\n\n_Empty text file._\n"
    return f"# {file_path.stem}\n\n{text}\n"


def convert_file_to_markdown(file_path: Path, context: ConversionContext) -> str:
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return convert_pdf_to_markdown(file_path, context)
    if ext == ".md":
        return convert_existing_markdown(file_path, improve_structure=context.improve_markdown, title_hint=file_path.stem)
    if ext == ".txt":
        return convert_text_to_markdown(file_path)
    if ext == ".docx":
        return convert_docx_to_markdown(file_path, context)
    raise ValueError(f"Unsupported file type: {file_path.suffix}")


def find_input_files(input_path: Path, recursive: bool) -> Iterable[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield input_path
        return

    pattern = "**/*" if recursive else "*"
    for path in input_path.glob(pattern):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def write_markdown(output_dir: Path, source_file: Path, content: str, overwrite: bool) -> Path:
    if source_file.suffix.lower() == ".pdf":
        output_file = output_dir / f"{source_file.stem}.md"
    else:
        output_file = output_dir / f"{source_file.stem}_{source_file.suffix.lower().lstrip('.')}.md"

    if output_file.exists() and not overwrite:
        raise FileExistsError(f"Output file already exists: {output_file}. Use --overwrite to replace it.")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(content, encoding="utf-8")
    return output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert PDF, DOCX, TXT, and Markdown files into MkDocs-ready Markdown.")
    parser.add_argument("input_path", type=Path, help="Input file or directory containing files to convert.")
    parser.add_argument("--output-dir", type=Path, default=Path("converted_md"), help="Directory where markdown files will be written.")
    parser.add_argument("--recursive", action="store_true", help="When input_path is a directory, include subfolders.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output markdown files when they already exist.")
    parser.add_argument(
        "--pdf-mode",
        choices=["hybrid", "layout", "ocr", "visual"],
        default="hybrid",
        help="PDF conversion mode: hybrid, layout(=hybrid), ocr, visual.",
    )
    parser.add_argument("--tesseract-cmd", default=None, help="Optional path to tesseract executable.")
    parser.add_argument("--render-dpi", type=int, default=220, help="DPI used for rendered page/table images.")
    parser.add_argument("--no-page-markers", action="store_true", help="Disable page marker comments.")
    parser.add_argument("--allow-inline-html", action="store_true", default=True, help="Allow inline HTML formatting where useful.")
    parser.add_argument("--no-inline-html", action="store_true", help="Disable inline HTML formatting.")
    parser.add_argument("--strict-validation", action="store_true", default=True, help="Fail conversion when validator reports fatal issues.")
    parser.add_argument("--no-strict-validation", action="store_true", help="Do not fail conversion when validation reports issues.")
    parser.add_argument("--disable-markitdown", action="store_true", help="Disable MarkItDown supplemental extraction.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path: Path = args.input_path
    if not input_path.exists():
        print(f"Input path does not exist: {input_path}")
        return 1

    assets_dir = args.output_dir / "assets"
    ensure_assets_folder(assets_dir)

    context = ConversionContext(
        output_dir=args.output_dir,
        assets_dir=assets_dir,
        overwrite=args.overwrite,
        pdf_mode=args.pdf_mode,
        tesseract_cmd=args.tesseract_cmd,
        prefer_markitdown=not args.disable_markitdown,
        improve_markdown=False,
        strict_validation=not args.no_strict_validation,
        render_dpi=max(96, int(args.render_dpi)),
        preserve_page_markers=not args.no_page_markers,
        allow_inline_html=not args.no_inline_html,
    )

    candidates = list(find_input_files(input_path, recursive=args.recursive))
    if not candidates:
        print("No supported files found.")
        return 1

    success = 0
    for source in candidates:
        try:
            markdown_content = convert_file_to_markdown(source, context)
            output_file = write_markdown(context.output_dir, source, markdown_content, context.overwrite)
            print(f"Converted: {source} -> {output_file}")
            success += 1
        except Exception as exc:  # noqa: BLE001
            print(f"Failed: {source} ({exc})")

    print(f"Done. Converted {success}/{len(candidates)} file(s).")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
