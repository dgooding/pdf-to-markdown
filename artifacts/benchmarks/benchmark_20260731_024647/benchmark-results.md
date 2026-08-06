# Synthetic Corpus Baseline Benchmark

- Total fixtures: 30
- Endpoint parity rate: 1.0
- Technical pass rate: 1.0
- Fidelity distribution: {"high": 13, "moderate": 10, "low": 0, "review_required": 7, "unknown": 0}

## Fixture Results

### ✅ DOCX-001
- source: `tests\fixtures\generated\documents\DOCX-001 simple semantic document.docx`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `moderate`
- endpoint technical/fidelity: `passed` / `moderate`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=0.6492, endpoint=1.1832
- notes: none

### ✅ DOCX-002
- source: `tests\fixtures\generated\documents\DOCX-002 advanced lists.docx`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `moderate`
- endpoint technical/fidelity: `passed` / `moderate`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=0.1007, endpoint=0.5283
- notes: none

### ✅ DOCX-003
- source: `tests\fixtures\generated\documents\DOCX-003 advanced tables.docx`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `moderate`
- endpoint technical/fidelity: `passed` / `moderate`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=0.1965, endpoint=0.4978
- notes: none

### ✅ DOCX-004
- source: `tests\fixtures\generated\documents\DOCX-004 images and captions.docx`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `moderate`
- endpoint technical/fidelity: `passed` / `moderate`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=0.2572, endpoint=0.5161
- notes: none

### ✅ DOCX-005
- source: `tests\fixtures\generated\documents\DOCX-005 charts and business data.docx`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `moderate`
- endpoint technical/fidelity: `passed` / `moderate`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=0.2106, endpoint=0.5168
- notes: none

### ✅ DOCX-006
- source: `tests\fixtures\generated\documents\DOCX-006 complex page layout.docx`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `moderate`
- endpoint technical/fidelity: `passed` / `moderate`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=0.4674, endpoint=0.5151
- notes: none

### ✅ DOCX-007
- source: `tests\fixtures\generated\documents\DOCX-007 code and technical content.docx`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `moderate`
- endpoint technical/fidelity: `passed` / `moderate`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=0.2043, endpoint=0.5038
- notes: none

### ✅ DOCX-008
- source: `tests\fixtures\generated\documents\DOCX-008 accessibility and structure.docx`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `moderate`
- endpoint technical/fidelity: `passed` / `moderate`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=0.334, endpoint=0.5535
- notes: none

### ✅ DOCX-009
- source: `tests\fixtures\generated\documents\DOCX-009 unicode and special characters.docx`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `moderate`
- endpoint technical/fidelity: `passed` / `moderate`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=0.2644, endpoint=0.5129
- notes: none

### ✅ DOCX-010
- source: `tests\fixtures\generated\documents\DOCX-010 large synthetic document.docx`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `moderate`
- endpoint technical/fidelity: `passed` / `moderate`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.1004, endpoint=1.2516
- notes: none

### ✅ PDF-001
- source: `tests\fixtures\generated\documents\PDF-001 native text.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.2834, endpoint=1.483
- notes: none

### ✅ PDF-002
- source: `tests\fixtures\generated\documents\PDF-002 custom bullets.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=0.6076, endpoint=0.8505
- notes: none

### ✅ PDF-003
- source: `tests\fixtures\generated\documents\PDF-003 ruled table.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `review_required`
- endpoint technical/fidelity: `passed` / `review_required`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.5128, endpoint=1.183
- notes: none

### ✅ PDF-004
- source: `tests\fixtures\generated\documents\PDF-004 borderless table.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=0.9595, endpoint=1.1666
- notes: none

### ✅ PDF-005
- source: `tests\fixtures\generated\documents\PDF-005 complex table.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `review_required`
- endpoint technical/fidelity: `passed` / `review_required`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.6161, endpoint=1.5331
- notes: none

### ✅ PDF-006
- source: `tests\fixtures\generated\documents\PDF-006 vector chart.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.0134, endpoint=1.1947
- notes: none

### ✅ PDF-007
- source: `tests\fixtures\generated\documents\PDF-007 multiple visuals.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.891, endpoint=2.083
- notes: none

### ✅ PDF-008
- source: `tests\fixtures\generated\documents\PDF-008 decorative vectors.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `review_required`
- endpoint technical/fidelity: `passed` / `review_required`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.0131, endpoint=0.8566
- notes: none

### ✅ PDF-009
- source: `tests\fixtures\generated\documents\PDF-009 two column.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.425, endpoint=1.7191
- notes: none

### ✅ PDF-010
- source: `tests\fixtures\generated\documents\PDF-010 mixed orientation.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.8658, endpoint=2.1396
- notes: none

### ✅ PDF-011
- source: `tests\fixtures\generated\documents\PDF-011 image-only scan.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `review_required`
- endpoint technical/fidelity: `passed` / `review_required`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.5905, endpoint=2.3684
- notes: none

### ✅ PDF-012
- source: `tests\fixtures\generated\documents\PDF-012 mixed native scanned.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `review_required`
- endpoint technical/fidelity: `passed` / `review_required`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=4.6694, endpoint=4.413
- notes: none

### ✅ PDF-013
- source: `tests\fixtures\generated\documents\PDF-013 image-only illustration.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.3, endpoint=1.3151
- notes: none

### ✅ PDF-014
- source: `tests\fixtures\generated\documents\PDF-014 screenshot procedure.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=2.0092, endpoint=2.6264
- notes: none

### ✅ PDF-015
- source: `tests\fixtures\generated\documents\PDF-015 diagram flowchart.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=2.0002, endpoint=1.7025
- notes: none

### ✅ PDF-016
- source: `tests\fixtures\generated\documents\PDF-016 links and annotations.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.4431, endpoint=1.4037
- notes: none

### ✅ PDF-017
- source: `tests\fixtures\generated\documents\PDF-017 repeated asset.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=3.3384, endpoint=3.078
- notes: none

### ✅ PDF-018
- source: `tests\fixtures\generated\documents\PDF-018 malformed and edge cases.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `review_required`
- endpoint technical/fidelity: `passed` / `review_required`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=1.5538, endpoint=1.3048
- notes: none

### ✅ PDF-019
- source: `tests\fixtures\generated\documents\PDF-019 large synthetic.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `high`
- endpoint technical/fidelity: `passed` / `high`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=43.6225, endpoint=26.1328
- notes: none

### ✅ PDF-020
- source: `tests\fixtures\generated\documents\PDF-020 original regression sample.pdf`
- direct status: `ok`
- endpoint status: `ok`
- compare: md=True, assets=True, manifest=True, quality=True
- direct technical/fidelity: `passed` / `review_required`
- endpoint technical/fidelity: `passed` / `review_required`
- markdown refs valid: `True`
- mkdocs build ok: `None`
- runtime seconds: direct=3.5127, endpoint=4.2335
- notes: none
