---
Module: attachment_indexation
Version: Odoo 18
Type: Extension
Tags: #attachments #search #fulltext #PDF #docx #xlsx
---

# Attachment Indexation (`attachment_indexation`)

> **Note:** The module is named `attachment_indexation` (with an **a**), not `attachment_indexing`. This is an intentional Odoo naming choice.

**Module Path:** `~/odoo/odoo18/odoo/addons/attachment_indexation/`

**Depends:** `web`

**Manifest Version:** `2.1`

**License:** LGPL-3

## Overview

The `attachment_indexation` module extends `ir.attachment` to extract and index the full-text content of binary document files. This enables Odoo's search infrastructure to find attachments by their internal text content — not just by filename.

For example, a PDF contract containing the phrase "Service Level Agreement" becomes searchable in Odoo's global search even though no field on the record explicitly contains that phrase.

### Supported File Types

| Format | Extensions | Method | Library | Notes |
|--------|------------|--------|---------|-------|
| Microsoft Word | `.docx` | `_index_docx()` | `zipfile`, `xml.dom.minidom` | Reads `word/document.xml` |
| Microsoft PowerPoint | `.pptx` | `_index_pptx()` | `zipfile`, `xml.dom.minidom` | Reads all `ppt/slides/slide*.xml` |
| Microsoft Excel | `.xlsx` | `_index_xlsx()` | `zipfile`, `xml.dom.minidom` | Reads `xl/sharedStrings.xml` |
| OpenDocument | `.odt`, `.ods`, `.odp`, etc. | `_index_opendoc()` | `zipfile`, `xml.dom.minidom` | Reads `content.xml` |
| PDF | `.pdf` | `_index_pdf()` | `pdfminer.six` | Page-by-page text extraction |

### What Is NOT Indexed

- `.doc` (legacy binary Word format) — requires `antiword` or `catdoc` external binaries, not bundled
- `.xls` (legacy binary Excel format)
- `.ppt` (legacy binary PowerPoint format)
- Images embedded in PDFs (OCR is not performed)
- Password-protected or encrypted documents
- Corrupt or malformed files (silently skipped)

---

## Model: `ir.attachment` — Extended

**File:** `~/odoo/odoo18/odoo/addons/attachment_indexation/models/ir_attachment.py`

Inherits from `ir.attachment` (base ORM model). Overrides the `_index()` classmethod and adds per-format extraction methods.

### Internal Constants

```python
FTYPES = ['docx', 'pptx', 'xlsx', 'opendoc', 'pdf']
index_content_cache = LRU(1)
```

- `FTYPES` — ordered list of supported file types; iteration order determines precedence if multiple handlers could match.
- `index_content_cache` — a thread-safe LRU cache with capacity 1, keyed by file checksum. Holds the last extracted text to avoid re-parsing the same file in concurrent requests. Uses the attachment's `checksum` as the key.

### Indexing Methods

#### `_index_docx(bin_data)`

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

Extracts text from `.docx` (Office Open XML). DOCX files are ZIP archives containing XML. This method:
1. Opens the binary as a `BytesIO` stream.
2. Verifies it is a valid ZIP (`zipfile.is_zipfile`).
3. Reads `word/document.xml` — the main document body.
4. Extracts text from `<w:p>` (paragraphs), `<w:h>` (headings), and `<text:list>` (list items).
5. Returns extracted text joined by newlines; returns empty string on any error.

#### `_index_pptx(bin_data)`

```python
def _index_pptx(self, bin_data):
    buf = u""
    f = io.BytesIO(bin_data)
    if zipfile.is_zipfile(f):
        try:
            zf = zipfile.ZipFile(f)
            zf_filelist = [x for x in zf.namelist() if x.startswith('ppt/slides/slide')]
            for i in range(1, len(zf_filelist) + 1):
                content = xml.dom.minidom.parseString(
                    zf.read('ppt/slides/slide%s.xml' % i))
                for val in ["a:t"]:  # a:t = text runs in PPTX
                    for element in content.getElementsByTagName(val):
                        buf += textToString(element) + "\n"
        except Exception:
            pass
    return buf
```

Extracts text from `.pptx`. Iterates all slide XML files in the ZIP. Text runs in PPTX use the `<a:t>` element tag (different from DOCX).

#### `_index_xlsx(bin_data)`

```python
def _index_xlsx(self, bin_data):
    buf = u""
    f = io.BytesIO(bin_data)
    if zipfile.is_zipfile(f):
        try:
            zf = zipfile.ZipFile(f)
            content = xml.dom.minidom.parseString(zf.read("xl/sharedStrings.xml"))
            for val in ["t"]:  # <t> is the text element in sharedStrings
                for element in content.getElementsByTagName(val):
                    buf += textToString(element) + "\n"
        except Exception:
            pass
    return buf
```

Extracts text from `.xlsx`. XLSX stores all cell text in a dedicated file `xl/sharedStrings.xml`. Each cell's text is a `<t>` element. Note: formula results (computed values) are not extracted — only the literal string values stored in the shared strings table.

#### `_index_opendoc(bin_data)`

```python
def _index_opendoc(self, bin_data):
    buf = u""
    f = io.BytesIO(bin_data)
    if zipfile.is_zipfile(f):
        try:
            zf = zipfile.ZipFile(f)
            content = xml.dom.minidom.parseString(zf.read("content.xml"))
            for val in ["text:p", "text:h", "text:list"]:
                for element in content.getElementsByTagName(val):
                    buf += textToString(element) + "\n"
        except Exception:
            pass
    return buf
```

Extracts text from OpenDocument formats (`.odt`, `.ods`, `.odp`, etc.). All ODF documents store body content in `content.xml`. Extracts paragraphs (`text:p`), headings (`text:h`), and list items (`text:list`).

#### `_index_pdf(bin_data)`

```python
def _index_pdf(self, bin_data):
    if PDFResourceManager is None:
        return  # pdfminer.six not installed
    buf = u""
    if bin_data.startswith(b'%PDF-'):
        f = io.BytesIO(bin_data)
        try:
            resource_manager = PDFResourceManager()
            with io.StringIO() as content, TextConverter(resource_manager, content) as device:
                logging.getLogger("pdfminer").setLevel(logging.CRITICAL)
                interpreter = PDFPageInterpreter(resource_manager, device)
                for page in PDFPage.get_pages(f):
                    interpreter.process_page(page)
                buf = content.getvalue()
        except Exception:
            pass
    return buf
```

Extracts text from PDF using `pdfminer.six`:
1. Checks PDF magic bytes (`%PDF-`) before processing.
2. Creates a `PDFResourceManager` and `StringIO` output buffer.
3. Uses `PDFPageInterpreter` to process each page.
4. Suppresses pdfminer's verbose logging via `logging.getLogger("pdfminer").setLevel(logging.CRITICAL)`.
5. Returns empty string if `pdfminer.six` is not installed (logged warning at import time).

**Optional dependency:** `pdfminer.six` is not a hard dependency. Install with `pip3 install pdfminer.six`.

### Helper: `textToString(element)`

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

Recursive DOM traversal. Extracts all text from an XML element and its descendants, including nested elements. Handles multi-level element nesting (e.g., text within bold/italic spans within paragraphs).

### Core Method: `_index(bin_data, mimetype, checksum=None)` — Override

```python
@api.model
def _index(self, bin_data, mimetype, checksum=None):
    # LRU cache lookup by checksum
    if checksum:
        cached_content = index_content_cache.get(checksum)
        if cached_content:
            return cached_content

    res = False
    for ftype in FTYPES:
        buf = getattr(self, '_index_%s' % ftype)(bin_data)
        if buf:
            res = buf.replace('\x00', '')  # strip null bytes
            break

    # Fall back to parent (handles plain text, HTML, etc.)
    res = res or super(IrAttachment, self)._index(bin_data, mimetype, checksum=checksum)

    if checksum:
        index_content_cache[checksum] = res
    return res
```

**Execution flow:**
1. Check the 1-entry LRU cache using the file's SHA1/MD5 checksum. If found, return cached text immediately.
2. Iterate supported `FTYPES` in order. For each, call the corresponding `_index_<ftype>()` method. Stop at the first non-empty result.
3. Strip null bytes from extracted text (`\x00` chars can appear in binary-encoded XML).
4. Fall back to the parent `_index()` for mimetypes not covered here (plain text, HTML, etc.).
5. Cache the result by checksum for subsequent lookups.

### `copy(default=None)` — Override

```python
def copy(self, default=None):
    for attachment in self:
        index_content_cache[attachment.checksum] = attachment.index_content
    return super().copy(default=default)
```

When an attachment is duplicated, the new copy gets the same binary content and thus the same checksum. By pre-seeding the cache with `{checksum: index_content}`, the new record's `_index()` call hits the cache immediately rather than re-parsing.

---

## How Full-Text Search Works

### Attachment Search Flow

```
User searches: "Service Level Agreement"
        │
        ▼
ir.attachment._search(['index_content', 'ilike', 'service level agreement'])
        │
        ▼
PostgreSQL: SELECT id FROM ir_attachment
            WHERE index_content ILIKE '%service level agreement%'
        │
        ▼
Matching attachment records returned
        │
        ▼
Record(s) containing the document displayed
```

The `index_content` field is stored as `text` in PostgreSQL (not a full-text search vector). Simple `ILIKE` pattern matching is used. This means:
- Searches are case-insensitive.
- Phrases are matched as substrings.
- No stemming or tokenization (searching "running" will NOT match "run").
- Performance degrades linearly with the number/size of indexed attachments.

### `index_content` Field (Base Model)

The `index_content` field is defined in the base `ir.attachment` model. It is a `text` field that stores the extracted content. The base model's `_index()` method returns `False` by default for binary files without an extension handler. The `attachment_indexation` module extends this to return actual extracted text.

```python
# Simplified base model (for reference)
index_content = fields.Text('Indexed Content', readonly=True,
    help='Text content of the attachment for full-text search')
```

The field is `readonly=True` — it is populated automatically by `_index()` when the attachment is created or when `IRAttachment._index()` is called explicitly.

---

## Performance Considerations

### LRU Cache — Size 1

```python
index_content_cache = LRU(1)
```

The cache holds exactly **one** entry. Design rationale: the most common scenario is uploading one file at a time. The cache avoids re-parsing the same file across multiple `read()` calls within a single request or during batch operations. With a larger cache, memory usage would grow unboundedly with large indexed files.

**Limitation:** In concurrent request scenarios, the cache provides no benefit — each worker process maintains its own LRU. For true caching across workers, use Redis or PostgreSQL-based caching.

### PDF Processing

PDF text extraction is the most CPU-intensive operation. Key notes:
- Each page is processed sequentially by `PDFPageInterpreter`.
- Image-based PDFs (scanned documents) return empty strings.
- `pdfminer.six` must be installed separately — if absent, PDFs silently return no content.
- Memory usage scales with PDF page count and content complexity.

### Large File Impact

- The entire binary content is loaded into memory for text extraction.
- Very large files (> 100 MB) can cause memory pressure.
- No streaming extraction is performed — `bin_data` is the full binary.

### When Indexing Runs

1. **On attachment create:** The base `ir.attachment.create()` calls `_index()` to populate `index_content`.
2. **On explicit re-index:** Can be triggered by calling `_index()` directly on an attachment record.
3. **Cache warming on copy:** `copy()` pre-seeds the cache so the new record hits the cache on its first read.

### GDPR Note

The extracted `index_content` is stored in the `ir_attachment` database table. If a document contains personal data (PII), the indexed text also contains that PII. For GDPR compliance:
- `data_recycle` module can be used to clean old attachments.
- The `index_content` field must be included in any data export/deletion requests.

---

## Tests

**File:** `~/odoo/odoo18/odoo/addons/attachment_indexation/tests/test_indexation.py`

```python
@tagged('post_install', '-at_install')
class TestCaseIndexation(TransactionCase):

    @skipIf(PDFResourceManager is None, "pdfminer not installed")
    def test_attachment_pdf_indexation(self):
        with file_open(os.path.join(directory, 'files', 'test_content.pdf'), 'rb') as file:
            pdf = file.read()
            text = self.env['ir.attachment']._index(pdf, 'application/pdf')
            self.assertEqual(text, 'TestContent!!\x0c',
                             'the index content should be correct')
```

Single test: reads a bundled test PDF and verifies that `_index()` extracts the string `'TestContent!!'` (plus a form-feed `\x0c` character that pdfminer preserves).

---

## Navigation

Menu: The module does not add menus — it extends the existing attachment infrastructure. The attachment list in any form view automatically gains full-text search capability for supported file types.

Access: All users benefit from indexing; no special permissions required.

Related: [Core/Fields](Core/Fields.md) (binary/file fields), [Tools/ORM Operations](odoo-18/Tools/ORM Operations.md) (ir.attachment CRUD), [Modules/data-recycle](Modules/data-recycle.md) (cleanup)
