---
type: module
module: attachment_indexation
tags: [odoo, odoo19, base, attachment, search, indexing]
created: 2026-04-06
updated: 2026-04-11
---

# Attachment Indexation (attachment_indexation)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Attachments List and Document Indexation |
| **Technical** | `attachment_indexation` |
| **Category** | Hidden |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `web` |
| **Source** | `odoo/addons/attachment_indexation/` |

## Description

Extends `ir.attachment` to enable full-text search of binary document files. When an attachment is created or updated, the module extracts readable text from supported formats (PDF, DOCX, PPTX, XLSX, OpenDocument) and stores it as `index_content` on the attachment record. The extracted text enables search via Odoo's standard attachment search. An LRU cache keyed by the attachment's checksum prevents redundant re-indexing of unchanged files. PDF extraction requires the `pdfminer.six` Python library.

## Architecture

```
attachment_indexation/
├── models/
│   └── ir_attachment.py    # _inherit='ir.attachment'; _index_* methods; copy() override
└── __init__.py
```

No views, no security files, no data files. Pure extension of the attachment indexing pipeline.

---

## L1: Module Purpose and Scope

The base `ir.attachment` model stores files but provides no content indexing for binary documents. This module overrides `_index()` to add support for structured document formats. The extracted text is stored in `ir.attachment.index_content` (inherited from base `ir.attachment`), making it searchable through Odoo's normal record search.

**Supported formats:**

| Format | Extension | Method | Library | Notes |
|--------|-----------|--------|--------|-------|
| PDF | `.pdf` | `pdfminer.high_level.extract_text` | `pdfminer.six` | Requires `pip install pdfminer.six` |
| Microsoft Word | `.docx` | XML parsing of `word/document.xml` | Built-in (`zipfile`, `xml.dom`) | — |
| Microsoft PowerPoint | `.pptx` | XML parsing of `ppt/slides/slideN.xml` | Built-in | — |
| Microsoft Excel | `.xlsx` | openpyxl `data_only=True` | `openpyxl` | Falls back gracefully if missing |
| OpenDocument | `.odt`, `.ods` | XML parsing of `content.xml` | Built-in (`lxml`) | Auto-detects spreadsheet vs. text via mimetype |

**Dependency:** `pdfminer.six` is optional. If not installed, PDF indexing silently returns empty string (no error, no crash). This is handled at module initialization:

```python
if not (importlib.util.find_spec('pdfminer') and importlib.util.find_spec('pdfminer.high_level')):
    _logger.warning("Attachment indexation of PDF documents is unavailable...")
```

---

## L2: Field Types, Defaults, Constraints

This module does not add fields to `ir.attachment`. It overrides methods on the existing model.

### Inherited Model: `ir.attachment`

**New fields on `ir.attachment` from base (not added by this module):**

| Field | Type | Description |
|-------|------|-------------|
| `index_content` | `Text` | Extracted text content for full-text search |
| `checksum` | `Char` | MD5/SHA hash of file content for deduplication |
| `mimetype` | `Char` | MIME type of the file |

### Module-Level Constants

```python
FTYPES = ['docx', 'pptx', 'xlsx', 'opendoc', 'pdf']
```

Defines the supported file types in dispatch order. The base `ir.attachment._index()` handles plain text, HTML, and XML natively before this module's dispatch runs.

### LRU Cache

```python
index_content_cache = LRU(1)
```

A single-entry LRU cache mapping `checksum → index_content`. This is a process-global cache (not per-request) that stores the last indexed content. It is used to avoid re-extracting text for identical files.

**Cache key:** The attachment's `checksum` (MD5/SHA hash of binary content).
**Cache miss:** File is extracted, result stored in cache.
**Cache hit:** Extracted text returned directly without re-reading the file.
**Cache size:** 1 entry — a deliberate design choice to minimize memory footprint while eliminating redundant extractions during bulk attachment operations.

### `copy()` Override

```python
def copy(self, default=None):
    for attachment in self:
        index_content_cache[attachment.checksum] = attachment.index_content
    return super().copy(default=default)
```

When an attachment is duplicated, the cache is manually updated to include the new attachment's content. This ensures that if the duplicated attachment is immediately accessed for its index content, the cache is warm for that checksum. This is the only ORM method overridden.

---

## L3: Cross-Model, Override Patterns, Workflow Triggers

### `_index` Override — Workflow Trigger

The main extension point is `ir.attachment._index()`. This method is called by the Odoo framework when attachment content needs to be indexed (on create, on write if `datas` changed, or on demand).

**Override chain:**
```
Framework calls ir_attachment._index(bin_data, mimetype, checksum)
  → attachment_indexation._index()
      → Check index_content_cache[checksum]     [cache lookup]
      → Loop over FTYPES, call _index_<ftype>()  [dispatch]
      → If any returns content: use it
      → Otherwise: super()._index()             [fallback to base handling]
      → Store result in cache
      → Return index_content string
```

**Base fallback:** The base `ir.attachment._index()` handles plain text, CSV, XML, and HTML files natively using `tools.file_open()` and basic text extraction. This module only handles the structured formats listed in `FTYPES`.

### Per-Format Extraction Methods

All extraction methods receive `bin_data` (bytes) and return a unicode string of extracted text (or empty string on failure). All are wrapped in `try/except Exception: pass` — any parsing error silently returns empty string, never crashes.

#### `_index_docx(bin_data)`

Extracts text from Microsoft Word `.docx` files. DOCX is a ZIP archive containing XML. Text is extracted from paragraph (`w:p`), heading (`w:h`), and list item (`text:list`) elements.

```python
def _index_docx(self, bin_data):
    buf = u""
    f = io.BytesIO(bin_data)
    if zipfile.is_zipfile(f):
        try:
            zf = zipfile.ZipFile(f)
            content = xml.dom.minidom.parseString(zf.read("word/document.xml"))
            for val in ["w:p", "w:h", "text:list"]:
                for element in content.getElementsByTagName(val):
                    buf += textToString(element) + "\n"
        except Exception:
            pass
    return buf
```

**Key points:**
- `xml.dom.minidom` is used (not `lxml`) — simple DOM parsing is sufficient
- Each element is followed by `\n` — preserves paragraph/slide boundaries
- Non-ZIP or malformed files return empty string

#### `_index_pptx(bin_data)`

Extracts text from Microsoft PowerPoint `.pptx` files. Slides are at `ppt/slides/slideN.xml` in the ZIP. Text is extracted from all `<a:t>` (anchor text) elements.

```python
def _index_pptx(self, bin_data):
    buf = u""
    f = io.BytesIO(bin_data)
    if zipfile.is_zipfile(f):
        try:
            zf = zipfile.ZipFile(f)
            zf_filelist = [x for x in zf.namelist() if x.startswith('ppt/slides/slide')]
            for i in range(1, len(zf_filelist) + 1):
                content = xml.dom.minidom.parseString(zf.read('ppt/slides/slide%s.xml' % i))
                for element in content.getElementsByTagName("a:t"):
                    buf += textToString(element) + "\n"
        except Exception:
            pass
    return buf
```

#### `_index_xlsx(bin_data)`

Extracts text from Microsoft Excel `.xlsx` files using `openpyxl`. Each sheet is converted to CSV-like rows, with the sheet name prepended to each row.

```python
def _index_xlsx(self, bin_data):
    workbook = load_workbook(f, data_only=True, read_only=True)
    for sheet in workbook.worksheets:
        sheet_name_escaped = _csv_escape(sheet_name)
        for row in sheet.iter_rows(values_only=True):
            if not any(row): continue
            row_cells = [sheet_name_escaped] + [_csv_escape(str(cell) if cell is not None else '') for cell in row]
            sheet_rows.append(','.join(row_cells))
        all_sheets.append('\n'.join(sheet_rows))
    return _clean_text_content('\n\n'.join(all_sheets))
```

**Key points:**
- `data_only=True` reads computed values, not formulas — correct for search
- `read_only=True` reduces memory for large files
- `warnings.catch_warnings()` suppresses openpyxl warnings
- `openpyxl` is an optional dependency — ImportError is caught and returns empty string

#### `_index_opendoc(bin_data)`

Extracts text from OpenDocument format files (`.odt`, `.ods`). Uses `lxml.etree` for XPath-based extraction. Auto-detects spreadsheet vs. text documents from the ZIP's `mimetype` file.

**Text extraction (`extract_text`):**
```python
def extract_text(content):
    lines = []
    for element in content.xpath('.//text:p | .//text:h | .//text:list-item', namespaces=...):
        text = ''.join(element.xpath('.//text()', namespaces=...)).strip()
        if text:
            lines.append(text)
    return lines
```

**Spreadsheet extraction (`extract_spreadsheet`):**
```python
# Parses table:table elements
# Handles number-columns-repeated and number-rows-repeated attributes
# Sheets are named and rows are CSV-formatted
```

**Key namespaces:**
```python
main_namespaces = {
    'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
    'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
    'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
    'manifest': 'urn:oasis:names:tc:opendocument:xmlns:manifest:1.0'
}
```

#### `_index_pdf(bin_data)`

Extracts text from PDF files using `pdfminer.high_level.extract_text`. Gracefully handles missing library and malformed PDFs.

```python
def _index_pdf(self, bin_data):
    if not bin_data.startswith(b'%PDF-'):
        return ""   # Not a PDF — bail early
    if not importlib.util.find_spec('pdfminer.high_level'):
        return ""   # Library not installed — bail early
    f = io.BytesIO(bin_data)
    resource_manager = PDFResourceManager()
    laparams = LAParams(detect_vertical=True)
    with io.StringIO() as content, TextConverter(resource_manager, content, laparams=laparams) as device:
        interpreter = PDFPageInterpreter(resource_manager, device)
        for page in PDFPage.get_pages(f):
            interpreter.process_page(page)
        buf = content.getvalue()
    return _clean_text_content(buf)
```

**Key points:**
- Magic byte check (`b'%PDF-'`) skips non-PDF files without error
- `detect_vertical=True` in LAParams handles vertical text (tables, Japanese/Chinese text)
- Both `pdfminer` absence and PDF parsing errors are silently caught

### Text Cleaning Utility

```python
def _clean_text_content(buf):
    # Remove NULs
    # Normalize CRLF/CR → LF
    # Replace tabs → spaces
    # Collapse runs of whitespace to max 2 consecutive newlines
    # Strip leading/trailing whitespace
    return buf.strip()
```

Applied to all extracted text (XLSX, ODP, PDF) before storage. Ensures consistent whitespace and removes binary control characters.

### CSV Escaping Utility

```python
def _csv_escape(value):
    if value is None: return ''
    value = str(value)
    if ',' in value or '"' in value or '\n' in value or '\r' in value:
        return '"' + value.replace('"', '""') + '"'
    return value
```

Used in XLSX and ODP spreadsheet indexing to properly format cell values in CSV output.

### XML Text Extraction

```python
def textToString(element):
    buff = u""
    for node in element.childNodes:
        if node.nodeType == xml.dom.Node.TEXT_NODE:
            buff += node.nodeValue
        elif node.nodeType == xml.dom.Node.ELEMENT_NODE:
            buff += textToString(node)
    return buff
```

Recursively collects all text from an XML DOM subtree. Used by DOCX and PPTX extractors.

---

## L4: Version Changes Odoo 18 → 19

### Module Version Bump

```
Odoo 18: version = '2.0'
Odoo 19: version = '2.1'
```

The version bump reflects the `copy()` override addition and/or minor refinements to the extraction pipeline.

### `copy()` Override — New in Odoo 19

The explicit cache population in `copy()` was likely added in Odoo 19:

```python
def copy(self, default=None):
    for attachment in self:
        index_content_cache[attachment.checksum] = attachment.index_content
    return super().copy(default=default)
```

Without this, duplicating an attachment in bulk would cause each copy to re-extract text from the same file content, defeating the LRU cache's purpose.

### `index_content_cache = LRU(1)` — Stability

The module uses `odoo.tools.lru.LRU`, Odoo's internal LRU cache wrapper. This is consistent across Odoo versions. The single-entry size is a deliberate memory trade-off: sufficient to handle the common case of repeated access to the same attachment without consuming significant memory.

### External Dependency: `pdfminer.six`

The optional dependency for PDF extraction is documented in the manifest:

```python
description = """
Attachments list and document indexation
========================================
* Show attachment on the top of the forms
* Document Indexation: odt, pdf, xlsx, docx

The `pdfminer.six` Python library has to be installed in order to index PDF files
"""
```

The warning is emitted at module load time (not install time), so administrators are notified in the server log if `pdfminer.six` is missing.

### Search Integration

The `index_content` field (inherited from base `ir.attachment`) is used by Odoo's standard `ir_attachment` search mechanism. Users can search for attachments by content through the standard search interface. This module populates the `index_content` field; the base model's search handlers use it.

### Error Handling Philosophy

All extraction methods silently catch all exceptions:

```python
try:
    # extraction logic
except Exception:  # noqa: BLE001
    pass
    return ""  # or return buf
```

This is intentional. Indexing failures should never block attachment creation or cause crashes. An attachment that cannot be indexed simply has empty `index_content` and is not searchable by content.

---

## Related

- [Modules/base](odoo-18/Modules/base.md)
- [Modules/web](odoo-18/Modules/web.md)
