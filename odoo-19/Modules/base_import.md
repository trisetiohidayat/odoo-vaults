---
uid: base_import
title: Base Import
type: module
category: Hidden/Tools
version: 2.0
created: 2026-04-06
modified: 2026-04-11
dependencies:
  - web
author: Odoo S.A.
license: LGPL-3
summary: Extensible server-side file import framework supporting CSV, Excel, and ODS formats with preview, auto-mapping, and batch execution
auto_install: true
tags:
  - odoo
  - odoo19
  - import
  - csv
  - excel
  - data-migration
---

# Base Import Module (base_import)

## Overview

The `base_import` module provides a **server-side, extensible file import framework** for Odoo. Unlike the legacy client-side import system, it centralizes all import logic on the server, making imports available via RPC, API, and the web UI without code duplication.

**Module Location:** `odoo/addons/base_import/`
**Manifest:** `__manifest__.py` (version 2.0, category Hidden/Tools, auto_install: True)
**Depends:** `web` (for ORM service access and the web client)
**Assets:** Web assets registered under `web.assets_backend` and `web.assets_unit_tests`

**Key architectural goals:**
- Move import logic server-side (previously client-dependent in legacy import)
- Provide an extensible architecture for custom file format imports
- Allow administrators to enable/disable import per installation via module dependency
- Support multi-sheet Excel files, batch imports with pause/resume, and per-field fallback values

**Module Structure:**
```
base_import/
├── __manifest__.py
├── models/
│   ├── __init__.py          → imports base_import (main.py)
│   └── base_import.py       → All model code (~1800 lines)
├── controllers/
│   ├── __init__.py          → imports main (ImportController)
│   └── main.py              → /base_import/set_file HTTP endpoint
├── security/
│   └── ir.model.access.csv  → ACLs for base_import.mapping and base_import.import
└── static/src/              → OWL-based import UI components
```

---

## Models

### 1. `base_import.mapping`

Stores column-to-field mapping preferences for repeated imports from the same third-party system.

```python
class Base_ImportMapping(models.Model):
    _name = 'base_import.mapping'
    _description = 'Base Import Mapping'

    res_model   = fields.Char(index=True)   # Target model e.g. 'res.partner'
    column_name = fields.Char()              # Original CSV column header (stored lowercased on lookup)
    field_name  = fields.Char()              # Mapped Odoo field path e.g. 'partner_id/id'
```

**Security:** `base.group_user` has full CRUD access (1,1,1,1). This is intentionally broad since all authenticated users need to save personal import mappings.

**Why `res_model` is indexed:** Repeated imports from the same third-party system (e.g., an external CRM) always target the same model. Indexing avoids sequential scans when loading user mappings during each `parse_preview()` call.

**L4 — Performance:** `parse_preview()` calls `base_import.mapping.search_read()` on every invocation (once per file load or option change). For users with many saved mappings (100+), this can become measurable. Consider a DB index on `(res_model, column_name)` for very large deployments.

**L4 — Security:** Mappings are per-model but not per-user — all authenticated users share the same saved mapping per model/column pair. This means a user can overwrite a mapping saved by another user for the same model. There is no audit trail of who created which mapping.

---

### 2. `base_import.import`

Transient wizard model (`_transient_max_hours = 12.0`) that orchestrates the entire import flow. Survives 12 hours to accommodate slow users who open the import UI and take their time configuring mappings.

```python
class Base_ImportImport(models.TransientModel):
    _name = 'base_import.import'
    _description = 'Base Import'
    _transient_max_hours = 12.0
    FUZZY_MATCH_DISTANCE = 0.2   # Max word distance for fuzzy matching

    res_model  = fields.Char('Model')                            # Target model name
    file       = fields.Binary('File', attachment=False)         # Raw bytes (NOT base64 on storage)
    file_name  = fields.Char('File Name')                        # Original filename
    file_type  = fields.Char('File Type')                        # MIME type string
```

**Security:** `base.group_user` has read/write/create (1,1,1,0) — notably `perm_unlink=0`. Transient records are cleaned up by the `_transient_max_hours` mechanism. Users cannot delete import records manually.

**Why `attachment=False` on `file`:** Storing import files as ir.attachment records would pollute the attachment store and create unnecessary rows in `ir_attachment`. Since the file is only needed during the import wizard session, it stays as a raw binary in the transient model's column. The database will reclaim the space when the record is purged.

**L4 — Transient Model Memory:** The `file` binary field stores raw file bytes directly in the PostgreSQL row. For very large files (approaching the PostgreSQL `work_mem` or row-wise TOAST limits), this can cause memory pressure during `parse_preview()` and `execute_import()`. Odoo handles this by streaming from the HTTP upload directly into the field, but a 50 MB CSV still occupies ~50 MB of PostgreSQL shared memory per import session.

**L4 — `_transient_max_hours = 12.0`:** This is unusually long compared to the standard 1-hour transient model cleanup. It accommodates enterprise deployments where users may open the import wizard in one tab and return hours later. The flip side: abandoned import sessions hold file binary data in the DB until the 12-hour window expires.

---

## Import Flow: End-to-End Sequence

```
User opens import action (action type "import")
    │
    ├─ ImportAction.setup()
    │      ├─ ORM call: base_import.import.create({ res_model })  → wizard ID = 1
    │      └─ ORM call: res_model.get_import_templates()          → optional template links
    │
User drops/selects file
    │
    ├─ HTTP POST /base_import/set_file
    │      └─ base_import.import(1).write({ file, file_name, file_type })
    │
    ├─ JS: ImportAction.handleFilesUpload()
    │      └─ ORM call: base_import.import(1).parse_preview(options)
    │             ├─ _read_file()            → detect format, parse rows
    │             ├─ _extract_header_types()  → infer column types from preview data
    │             ├─ _get_mapping_suggestions() → auto-map columns
    │             │      ├─ Check base_import.mapping records
    │             │      ├─ Exact match (technical name, label, translated label)
    │             │      └─ Fuzzy match (difflib.SequenceMatcher, threshold 0.2)
    │             └─ Returns: fields tree, matches, headers, preview, header_types
    │
User reviews/modifies mappings in UI
    │
    ├─ User clicks "Test Import" or "Import"
    │      └─ ORM call: base_import.import(1).execute_import(fields, columns, options, dryrun)
    │             ├─ _convert_import_data()       → extract mapped columns, strip headers
    │             ├─ _parse_import_data()         → parse dates, floats, binaries
    │             │      └─ _parse_import_data_recursive() → recursive for relational fields
    │             ├─ _handle_multi_mapping()       → merge columns mapped to same field
    │             ├─ _handle_fallback_values()     → apply fallbacks for bool/selection
    │             ├─ model.load()                 → ORM batch import
    │             ├─ SAVEPOINT rollback if dryrun
    │             └─ Save successful mappings to base_import.mapping
    │
    └─ On success: open newly created records in list/form view
```

---

## Core Methods Deep Dive

### `get_fields_tree(model, depth=3)`

Recursively builds a tree of all importable fields for a model. Called on every `parse_preview()`.

**L4 — Recursion depth limit (`FIELDS_RECURSION_LIMIT = 3`):** This prevents infinite recursion for models with circular Many2one back-references (e.g., `res.partner` has `parent_id` pointing back to `res.partner`). Depth 3 is a hard limit — it cannot be configured per-call except through the module constant.

**L4 — `properties` field handling (Odoo 18+):** Properties fields (`type = 'properties'`) are expanded inline at import time. For each active property definition record, the module generates synthetic field entries like `name.property_definition_name`. These are resolved via `definition_record` and `definition_record_field` attributes. Archived definition records are intentionally skipped since archived records are not typically imported.

**Returns tree structure:**
```python
[
    {'id': 'id', 'name': 'id', 'string': 'External ID', 'type': 'id', 'fields': [], 'model_name': 'res.partner', 'required': False},
    {'id': 'partner_id', 'name': 'partner_id', 'string': 'Customer',
     'type': 'many2one', 'comodel_name': 'res.partner',
     'fields': [
         {'name': 'id', 'string': 'External ID', 'type': 'id', ...},
         {'name': '.id', 'string': 'Database ID', 'type': 'id', ...},
     ]},
    {'id': 'order_line', 'name': 'order_line', 'string': 'Order Lines',
     'type': 'one2many', 'comodel_name': 'sale.order.line',
     'fields': [ /* recursive tree for sale.order.line at depth-1 */ ]},
]
```

**Blacklisted fields (`models.MAGIC_COLUMNS`):** Standard Odoo magic columns (`id`, `create_uid`, `create_date`, `write_uid`, `write_date`, `__last_update`) are excluded from the tree. `__last_update` is intentionally excluded even though it could theoretically be used for synchronization.

**L4 — Performance:** `fields_get()` is called for every `get_fields_tree()` invocation. On models with many fields (100+), this generates a large dictionary. Caching at the model/env level is not applied — each preview refresh re-fetches.

---

### `_read_file(options)`

Dispatches to the correct reader based on MIME type, file extension, or content sniffing (in priority order).

**L4 — Format detection priority:**
1. Guessed MIME type from file content via `guess_mimetype()` (uses python-magic)
2. User-provided MIME type from `file_type` field (set by browser on upload)
3. File extension from `file_name` (last resort fallback)

**L4 — Why extension is the fallback:** Browsers and file upload libraries sometimes send incorrect MIME types, especially for `.xlsx` files sent as `application/octet-stream`. The triple-detection strategy ensures that malformed MIME types don't prevent legitimate file imports.

**L4 — ImportError handling for Excel:** The code explicitly catches `ImportError` for `xlrd` when the installed version is 2.x (which dropped `.xlsx` support). In that case it falls through to `openpyxl`. The error message shown to users explicitly states: `"requires openpyxl or xlrd >= 1.0.0 < 2.0"`.

**Reader methods:**

| Method | Library | Notes |
|--------|---------|-------|
| `_read_csv(options)` | Python `csv` | chardet encoding detection, BOM stripping, auto-separator |
| `_read_xls(options)` | `xlrd` | Reads all sheets; returns sheet names in `options['sheets']` |
| `_read_xlsx(options)` | `openpyxl` | `data_only=True` to read cached cell values not formulas |
| `_read_ods(options)` | Custom `odf_ods_reader` (odfpy) | Handles column spans via `numbercolumnsspanned` |

---

### `_read_csv(options)` — Internal Details

```python
def _read_csv(self, options):
    # Step 1: Encoding detection
    encoding = options.get('encoding')
    if not encoding:
        encoding = options['encoding'] = chardet.detect(csv_data)['encoding'].lower()
        # Strip BOM marker for UTF-16/32 LE/BE if present
        bom = BOM_MAP.get(encoding)
        if bom and csv_data.startswith(bom):
            options['encoding'] = encoding[:-2]  # e.g. 'utf-16' → 'utf-16-le'

    # Step 2: Separator auto-detection
    # Tries: ',' → ';' → '\t' → ' ' → '|' → unit_separator
    # Criterion: all rows must have the same column count AND ≥2 columns
    separator = options.get('separator') or ','

    # Step 3: Quote char validation
    if len(options['quoting']) != 1:
        raise ImportValidationError("Text Delimiter should be a single character.")
```

**BOM_MAP constants:**
```python
BOM_MAP = {
    'utf-16le': codecs.BOM_UTF16_LE,
    'utf-16be': codecs.BOM_UTF16_BE,
    'utf-32le': codecs.BOM_UTF32_LE,
    'utf-32be': codecs.BOM_UTF32_BE,
}
```

**L4 — chardet limitations:** chardet can misdetect encodings for very short files (< 100 bytes) or files with mixed-language content. The `encoding_guessed` flag is used to customize the error message: if the encoding was auto-detected and fails to decode, the message says "This encoding was automatically detected" rather than blaming the user's manual selection.

**L4 — Empty row filtering:** The final step filters out rows where every cell is empty or whitespace-only: `if any(x for x in row if x.strip())`. This means completely blank rows in the CSV are silently dropped, which can cause row count mismatch errors if the user is manually tracking row numbers.

---

### `_read_xlsx(options)` — Internal Details

```python
def _read_xlsx(self, options):
    book = openpyxl.load_workbook(io.BytesIO(self.file), data_only=True)
    sheets = options['sheets'] = book.sheetnames
    sheet = options['sheet'] = options.get('sheet') or sheets[0]

    for rowx, row in enumerate(sheet.rows, 1):
        for colx, cell in enumerate(row, 1):
            if cell.data_type == types.TYPE_ERROR:
                raise ValueError("Invalid cell value...")
            elif isinstance(cell.value, float):
                # Strip trailing .0 for integers stored as float
                values.append(str(int(cell.value)) if cell.value % 1 == 0 else str(cell.value))
            elif cell.is_date:
                d_fmt = styles.is_datetime(cell.number_format)
                if d_fmt == "datetime": values.append(cell.value)
                elif d_fmt == "date":    values.append(cell.value.date())
                else: raise ValueError("Invalid cell format...")  # time-only not supported
            else:
                values.append(str(cell.value))
```

**L4 — `data_only=True`:** This is critical. Without it, `openpyxl` returns cached formula strings (e.g., `=SUM(A1:A10)`) rather than computed values. Setting `data_only=True` returns the last saved calculated values — but only if the file was saved by Excel/LibreOffice. Files created programmatically may have `None` for formula cells.

**L4 — `xlrd` vs `openpyxl` for XLSX:** The code first attempts `from xlrd import xlsx` (the xlrd 1.x plugin for `.xlsx`). If that fails (xlrd 2.x removed the plugin), it falls back to `openpyxl`. The xlrd path is tried first because xlrd is significantly faster for large files (10x+ on benchmarks). On xlrd 2.x systems, large XLSX imports will be slower.

---

### `_extract_header_types(preview_values, options)` — Type Inference Heuristics

**L4 — Type inference logic (in evaluation order):**

```python
# All values are empty strings → any field type matches
if values == {''}: return ['all']

# All start with __export__ → likely external IDs
if all(v.startswith('__export__') for v in values):
    return ['id', 'many2many', 'many2one', 'one2many']

# All are digits → could be integer IDs, floats, or booleans (if only 0/1)
if all(v.isdigit() for v in values if v):
    types = ['integer', 'float', 'monetary']
    if {'0', '1', ''}.issuperset(values):  # only 0, 1, or empty
        types.append('boolean')

# All are boolean strings → boolean only
if all(val.lower() in ('true','false','t','f','') for val in preview_values):
    return ['boolean']

# Try float parsing (currency symbols, () for negatives, separators)
try:
    # detect thousand/decimal separators from value patterns
    return ['float', 'monetary']
except ValueError:
    pass

# Try date/datetime parsing against known patterns
# (see _try_match_date_time below)

# Otherwise → text-based fields
return ['text', 'char', 'binary', 'selection', 'html', 'tags']
```

**L4 — Float separator inference from data:** The method dynamically infers the thousand and decimal separators by examining the character distribution in numeric values:
- Two non-numeric characters where the last one appears only once → first is grouping, second is decimal
- E.g., `"1.234,56"` → grouping=`.`, decimal=`,`
- E.g., `"1,234.56"` → grouping=`,`, decimal=`.`
- E.g., `"1234,56"` (only comma) → grouping=`,`, decimal=`.`

**L4 — Currency symbol removal (`_remove_currency_symbol`):** Currency symbols are detected by matching against `res.currency` table's `symbol` field (not `name`). This means `€100` works but `EUR 100` may not unless `EUR` is the symbol field. Symbols must match exactly. Parentheses `(100)` are interpreted as negative values.

**L4 — Date/datetime pattern matching:** The date format is inferred by matching preview values against a precomputed list of `DATE_PATTERNS` (generated from `_PATTERN_BASELINE` with all separator/year-length variants). If all preview values match a pattern, that pattern is stored in `options['date_format']` and reused during `_parse_date_from_data()`. If no pattern matches, no date format is stored and imports of date columns will fail with a parsing error.

---

### `_get_mapping_suggestion(header, fields_tree, header_types, mapping_fields)`

Maps a single column header to a field using a 3-tier strategy. This is the core algorithm behind the "Suggested fields" feature.

**Tier 1 — Saved Mappings (distance = -1):**
```python
mapping_field_name = mapping_fields.get(header.lower())
if mapping_field_name:
    return {'field_path': [name for name in mapping_field_name.split('/')], 'distance': -1}
```
Lowercased for case-insensitive matching. Stored distance `-1` forces this mapping to be kept during deduplication (see below).

**Tier 2 — Exact Match (distance = 0):**
```python
# Technical name match (case-insensitive)
if header.casefold() == fname.casefold(): break
# Translated label match
if header.casefold() == field['string'].casefold(): break
# English label match (from ir.model.fields get_field_string)
if header.casefold() == field_strings_en[fname].casefold(): break
```
`get_field_string()` reads from `ir.model.fields.field_description` in English (`lang='en_US'`), enabling matching against Odoo's canonical English field labels regardless of the current user's language.

**Tier 3 — Fuzzy Match (distance 0 < d < 0.2):**
```python
def _get_distance(self, a, b):
    return 1 - difflib.SequenceMatcher(None, a, b).ratio()
```
Only runs on type-filtered fields (from `_filter_fields_by_types`). If the minimum distance across all candidates is below `FUZZY_MATCH_DISTANCE = 0.2`, the closest match is returned. Otherwise, no suggestion is made.

**L4 — Why `FUZZY_MATCH_DISTANCE = 0.2`:** SequenceMatcher ratio is `0.0` for identical strings and `~1.0` for completely different strings. A threshold of `0.2` means a fuzzy match is only suggested when the similarity is at least 80%. This prevents spurious suggestions like "Customer" → "Category" (similarity ~60%). This value is a module constant and cannot be configured per-import.

**L4 — Hierarchical (relational) field paths:** Headers containing `/` are parsed as relational paths. For example, `partner_id/description` maps to the `description` subfield of the `partner_id` field. Each segment is matched independently using the same 3-tier strategy against the appropriate sub-fields tree. Any failure in the chain returns an empty dict (no suggestion).

---

### `_deduplicate_mapping_suggestions(mapping_suggestions)`

Prevents multiple columns from being matched to the same field, keeping only the closest match.

```python
def _deduplicate_mapping_suggestions(self, mapping_suggestions):
    min_dist_per_field = {}
    for header, suggestion in mapping_suggestions.items():
        if suggestion is None or len(suggestion['field_path']) > 1:
            headers_to_keep.append(header)  # Skip None and hierarchy mappings
            continue
        field_name = suggestion['field_path'][0]
        field_distance = suggestion['distance']
        best_distance, _best_header = min_dist_per_field.get(field_name, (1, None))
        if field_distance < best_distance:
            min_dist_per_field[field_name] = (field_distance, header)
```

**L4 — Why hierarchy mappings are excluded:** The deduplication loop explicitly skips fields with `len(suggestion['field_path']) > 1` (relational paths). This means two columns could both be mapped to `lead_id/description`. The rationale: relational field paths are "advanced" and users are expected to be deliberate when mapping them. Auto-deduplication of relational paths would be confusing since users may legitimately want to import into the same subfield from different sources.

---

### `parse_preview(options, count=10)`

Generates a preview and performs field-matching. Called whenever:
- A file is first uploaded
- Any import option changes (separator, encoding, date format, sheet selection, etc.)
- User toggles "Keep matches" or "Advanced mode"

```python
def parse_preview(self, options, count=10):
    fields_tree = self.get_fields_tree(self.res_model)
    file_length, data_rows = self._read_file(options)

    preview = data_rows[:count]
    if options.get('has_headers'):
        headers = preview.pop(0)  # Remove header row from preview
        header_types = self._extract_headers_types(headers, preview, options)
    else:
        headers, header_types = [], {}

    # If keep_matches: reuse user's manual field selections
    if options.get('keep_matches') and options.get('fields'):
        matches = {index: options['fields'][index].split('/') ...}
    elif options.get('has_headers'):
        matches = self._get_mapping_suggestions(headers, header_types, fields_tree)

    # Advanced mode: activates when relational paths are used in headers OR matches
    advanced_mode = (
        any(len(header.split('/')) > 1 for header in headers) or
        any(len(match) > 1 for match in matches.values() if match)
    )

    # Column examples: first 5 non-empty values per column (truncated to 50 chars)
    column_example = [...]
    return {
        'fields': fields_tree,
        'matches': matches,       # {column_index: ['field_path', ...]}
        'headers': headers,
        'header_types': list(header_types.values()),
        'preview': column_example,
        'options': options,
        'advanced_mode': advanced_mode,
        'debug': self.env.user.has_group('base.group_no_one'),
        'batch': batch,
        'num_rows': len(data_rows),
    }
```

**L4 — `count=10` vs `options['limit`]:** `count` controls how many rows are used for the preview (type inference + example values). `options['limit']` controls how many rows are actually imported per batch. These are independent. The preview always uses 10 rows regardless of batch size, which means type inference can be wrong if the first 10 rows are all empty or atypical.

**L4 — Batch detection:** Batch mode (multi-step import with pause/resume) is activated when `num_rows > 100` AND `limit < num_rows`. For files with ≤100 rows, batch mode is never shown even if `limit` is set low.

**L4 — Error fallback for preview:** On any exception during preview, if the file is CSV, the first `ERROR_PREVIEW_BYTES = 200` bytes are decoded as `iso-8859-1` and returned as the `preview` field. This ensures the user always sees something in the error state, even if the file is binary garbage.

---

### `execute_import(fields, columns, options, dryrun=False)`

The main execution method. Called twice per import session: once with `dryrun=True` (test) and once with `dryrun=False` (actual import).

```python
def execute_import(self, fields, columns, options, dryrun=False):
    self.ensure_one()

    # Step 1: Create a named PostgreSQL savepoint
    import_savepoint = self.env.cr.savepoint(flush=False)

    try:
        # Step 2: Extract mapped columns and re-read full file
        input_file_data, import_fields = self._convert_import_data(fields, options)

        # Step 3: Parse dates, floats, binaries (including remote URL download)
        input_file_data = self._parse_import_data(input_file_data, import_fields, options)
    except ImportValidationError as error:
        return {'messages': [error.__dict__]}

    # Step 4: Concatenate multiple columns mapped to the same text field
    import_fields, merged_data = self.with_context(
        import_options=options
    )._handle_multi_mapping(import_fields, input_file_data)

    # Step 5: Apply fallback values for boolean/selection mismatches
    if options.get('fallback_values'):
        merged_data = self._handle_fallback_values(
            import_fields, merged_data, options['fallback_values'])

    # Step 6: Extract binary filenames for later file attachment
    binary_filenames = self._extract_binary_filenames(import_fields, input_file_data)

    # Step 7: Call the target model's ORM load() method
    name_create_enabled_fields = options.pop('name_create_enabled_fields', {})
    import_limit = options.pop('limit', None)
    model = self.env[self.res_model].with_context(
        import_file=True,
        name_create_enabled_fields=name_create_enabled_fields,
        import_set_empty_fields=options.get('import_set_empty_fields', []),
        import_skip_records=options.get('import_skip_records', []),
        _import_limit=import_limit)
    import_result = model.load(import_fields, merged_data)

    # Step 8: Rollback or commit based on dryrun flag
    with contextlib.suppress(psycopg2.InternalError):
        import_savepoint.close(rollback=dryrun)

    if dryrun:
        self.pool.clear_all_caches()
        self.pool.reset_changes()

    # Step 9: Save successful column→field mappings
    if import_result['ids'] and options.get('has_headers'):
        self._save_mappings(columns, fields)

    return import_result
```

**L4 — Savepoint strategy:** A named savepoint is created before any parsing. If `dryrun=True`, the savepoint is rolled back, undoing all created/changed records. If `dryrun=False`, the savepoint is released (committed). The `contextlib.suppress(psycopg2.InternalError)` handles the edge case where a ROLLBACK is issued from within the ORM (e.g., from a constraint violation in a trigger) which would invalidate the savepoint name.

**L4 — Pool cache clearing on dryrun:** After a test import rollback, `self.pool.clear_all_caches()` and `self.pool.reset_changes()` are called. This is critical because the test import may have created ir.attachment records or updated cached values that would otherwise persist in the worker process's memory even after the DB rollback.

**L4 — `options.pop()` side effects:** `name_create_enabled_fields` and `limit` are `pop()`ed from options before passing to `model.load()`. This means if `execute_import()` is called twice (test + real), the second call must re-extract these from the original options. The JS layer handles this by passing the same options object each time, but RPC callers need to be aware.

**L4 — `binary_filenames` extraction:** This is done before `_handle_multi_mapping()` because multi-mapping changes the data structure. The filename extraction traverses the same relational field path structure as the import itself, recursively.

---

### `_parse_import_data(data, import_fields, options)` and `_parse_import_data_recursive()`

Recursive parser that handles date, datetime, float, and binary fields. The recursive approach is necessary because relational fields (`one2many`, `many2one` subfields) also need their typed fields parsed.

```python
def _parse_import_data_recursive(self, model, prefix, data, import_fields, options):
    all_fields = self.env[model].fields_get()
    for name, field in all_fields.items():
        name = prefix + name
        if field['type'] in ('date', 'datetime') and name in import_fields:
            self._parse_date_from_data(data, index, name, field['type'], options)
        elif any(name + '/' in f and name == f.split('/')[prefix.count('/')]
                 for f in import_fields):
            # Recurse into relational subfield
            self._parse_import_data_recursive(
                field['relation'], name + '/', data, import_fields, options)
        elif field['type'] in ('float', 'monetary') and name in import_fields:
            self._parse_float_from_data(data, index, name, options)
        elif field['type'] == 'binary' and field.get('attachment') and name in import_fields:
            # Handle URL imports, base64, or filenames
            for num, line in enumerate(data):
                if re.match(config.get("import_url_regex"), line[index]):
                    if not self.env.user._can_import_remote_urls():
                        raise ImportValidationError(...)
                    line[index] = self._import_file_by_url(line[index], session, name, num)
                elif '.' in line[index]:
                    # Detected filename → leave as string for binary_file_manager
                    pass
                else:
                    base64.b64decode(line[index], validate=True)
```

**L4 — Binary field URL security (`_can_import_remote_urls`):** By default, only admin (`_is_admin()`) can import files via URL. This is a deliberate DOS prevention measure — a malicious user could write an import that fetches large files from arbitrary URLs, consuming worker memory and bandwidth. The `import_url_regex` config option (`import_url_regex` in `odoo.conf`) restricts which URL patterns are allowed. The default is very permissive (`.*`); hardening it to specific domains is recommended.

**L4 — Binary field max size:** Remote URL imports are limited by two config values:
- `import_file_maxbytes`: max total file size (default: typically 100 MB)
- `import_file_timeout`: max time to wait for the remote server (default: 30s)

If the `Content-Length` header is present and exceeds `maxbytes`, the import fails immediately without downloading. If the stream exceeds `maxbytes` during chunked download, it fails mid-transfer.

**L4 — Image dimension check:** Images are validated for resolution before import: `w * h > 42e6` (42 million pixels, roughly Nokia Lumia 1020 resolution: 7152x5368). This prevents denial-of-service via extremely large images that would consume excessive CPU during PIL resizing or DB storage.

---

### `_handle_multi_mapping(import_fields, input_file_data)`

When multiple columns are mapped to the same target field, their values are concatenated.

```python
CONCAT_SEPARATOR_IMPORT = {
    'char':      ' ',    # "First Name" + "Last Name" → "First Name Last Name"
    'text':      '\n',   # Two text columns → newline-separated
    'html':      '<br>', # HTML fields → <br>-separated
    'many2many': ',',    # Multiple tags → comma-separated
}
```

For `char` fields, if `field.trim = True` (the default for most Char fields), trailing whitespaces are trimmed before joining.

**L4 — Why this matters for relational paths:** Multi-mapping also works for subfields of relational fields (e.g., two columns mapped to `order_line/product_id`). The method walks the field path to determine the target model and field type at each level.

---

### `_handle_fallback_values(import_fields, input_file_data, fallback_values)`

For `boolean` and `selection` fields where imported values don't match allowed values. Allows the user to specify what value to use as a fallback.

```python
# Example fallback_values structure:
{
    'active': {
        'fallback_value': 'true',
        'field_model': 'res.partner',
        'field_type': 'boolean'
    },
    'state': {
        'fallback_value': 'draft',
        'field_model': 'sale.order',
        'field_type': 'selection',
        'selection_values': ['draft', 'sent', 'sale', 'done', 'cancel']
    }
}
```

**L4 — Selection value lowercasing:** Selection values from the field definition are lowercased before comparison: `selection_values = [value.lower() for (_, value) in target_model.fields_get([target_field])[target_field]['selection']]`. This means "DRAFT", "Draft", and "draft" all match `draft`. Case-insensitive matching is applied during fallback value checking.

**L4 — `skip` as fallback for selection:** If `fallback_value == 'skip'`, the field value is set to `None` (not written), effectively leaving the field unchanged. This is useful when a column contains a mix of valid and invalid selection values and the user wants to skip the invalid ones.

---

### `_save_mappings(columns, fields)` (inline in `execute_import`)

After a successful import, column→field mappings are persisted to `base_import.mapping`.

```python
for index, column_name in enumerate(columns):
    if column_name:
        mapping_domain = [('res_model', '=', self.res_model), ('column_name', '=', column_name)]
        column_mapping = BaseImportMapping.search(mapping_domain, limit=1)
        if column_mapping:
            if column_mapping.field_name != fields[index]:
                column_mapping.write({'field_name': fields[index]})  # Update if changed
        else:
            BaseImportMapping.create({'res_model': ..., 'column_name': ..., 'field_name': ...})
```

**L4 — UPSERT behavior:** If a mapping already exists for `(res_model, column_name)`, the `field_name` is updated. This means the most recently successful mapping is always persisted. If no import succeeds (test mode canceled or all rows errored), no mappings are saved.

**L4 — `has_headers` gate:** Mappings are only saved if `options['has_headers']` is True. If headers are disabled, `column_name` is the empty string or generic positional index, which would create noisy mappings. The UI enforces `has_headers=True` for this reason.

---

## Special Field Handling

### External ID (`id` field)
```
id,name,partner_id/id
module__partner_1,Acme Corp,base.user_admin
module__partner_2,John Doe,base.user_demo
```
The `id` column (type `id`) enables update-instead-of-create. Records are matched by `external ID` (module.name format) or `xml_id`.

### Database ID (`.id` field)
```
.id,name,partner_id/.id
1,Acme Corp,2
```
Matches records by PostgreSQL row ID. Danger: IDs are database-instance-specific and will break when migrating between environments.

### parent_path for Hierarchical Data
```
name,parent_path
Root Category,1/
  Subcategory A,1/2/
  Subcategory B,1/3/
```
Odoo's `parent_path` field stores a materialized path for fast tree queries. Importing via `parent_path` is the fastest way to create deep category hierarchies in bulk, as it avoids the recursive `parent_id` lookups that `name_create` would trigger.

---

## Import Options Reference

These are passed from the JS client in the `options` dict:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `has_headers` | bool | `true` | Treat first row as column headers |
| `keep_matches` | bool | `false` | Reuse user's manual field selections on re-parse |
| `advanced` | bool | `false` | Show relational field path mapping UI |
| `encoding` | str | `''` (auto) | CSV character encoding |
| `separator` | str | `','` (auto) | CSV column separator |
| `quoting` | str | `'"'` | CSV text delimiter character |
| `date_format` | str | `''` (auto) | Date format pattern |
| `datetime_format` | str | `''` (auto) | Datetime format pattern |
| `float_thousand_separator` | str | `','` | Thousand grouping separator |
| `float_decimal_separator` | str | `'.'` | Decimal separator |
| `sheet` | str | first sheet | Which Excel/ODS sheet to import |
| `sheets` | list | — | Available sheet names (returned by parser) |
| `limit` | int | `2000` | Max rows per import batch |
| `skip` | int | `0` | Number of rows to skip at start |
| `fallback_values` | dict | `{}` | Per-field fallback for bool/selection |
| `name_create_enabled_fields` | dict | `{}` | Fields where name_create should auto-create |
| `import_set_empty_fields` | list | `[]` | Fields to explicitly set to False |
| `import_skip_records` | list | `[]` | Records to skip based on condition |
| `tracking_disable` | bool | `true` | Disable mail.tracking on imported records |
| `import_options` | dict | — | Nested context for multi-mapping |

**L4 — `limit` and batch mode:** When `limit < num_rows`, the import executes in multiple batches. After each batch, `execute_import()` returns `{'nextrow': skip + limit, 'ids': [...]}`. The JS client reads `nextrow`, updates `options['skip']`, and calls `execute_import()` again. This continues until `nextrow == 0` or an error occurs.

**L4 — `tracking_disable: true`:** Mail tracking ( chatter messages) is disabled by default during import. This prevents mass-mail notifications from being generated for bulk imports. Setting it to `false` will generate tracking messages for each record, significantly increasing import time and database writes.

---

## Batch Import and Pause/Resume

The import engine supports pausing mid-import and resuming from the last successful row. This is critical for large files that might exceed request timeouts or memory limits.

```python
# JS side (import_model.js)
for (let i = 1; i <= totalSteps; i++) {
    if (this.handleInterruption) {  // set by stopImport()
        if (importRes.hasError || isTest) {
            importRes.nextrow = startRow;
            this.setOption("skip", startRow);
        }
        break;
    }
    const error = await this._executeImportStep(isTest, importRes);
    if (error) { ... }
    if (importProgress) {
        importProgress.step = i;
        importProgress.value = Math.round((100 * (i - 1)) / totalSteps);
    }
}
```

**L4 — Interrupt handling:** `stopImport()` sets `handleInterruption = True`. The loop exits at the start of the next iteration, after the current batch completes. The recordset of already-imported IDs is preserved in `importRes.ids` across calls. The `nextrow` value allows the server to resume from the exact position.

**L4 — Memory management in batch mode:** Each batch is processed in its own savepoint and ORM transaction. The full file is not held in memory — only one batch's rows (up to `limit`) are in memory at any time. However, the `file` binary on the wizard record persists across batches, so the full file remains in the database row for the duration of the import session.

---

## Security Considerations (L4)

### ACL Summary

| Model | Access | Group |
|-------|--------|-------|
| `base_import.mapping` | read, write, create, unlink | `base.group_user` |
| `base_import.import` | read, write, create | `base.group_user` |

### Who Can Import What

The import wizard itself is accessible to all authenticated users via the `base.group_user` ACL. However, the actual ability to import into a specific model is governed by that model's own ACLs. When `model.load()` is called, it runs with the current user's permissions, so `perm_create`, `perm_write`, etc. are enforced on the target model.

### URL Import Security

```python
def _can_import_remote_urls(self):
    self.ensure_one()
    return self._is_admin()  # Only admin by default
```

The hook can be overridden in `res.users` subclasses to allow specific user groups to import binary files via URL. The `import_url_regex` config option in `odoo.conf` provides a secondary layer of URL restriction.

### DOS Vectors

1. **Large file upload:** Files are stored in the DB transient record. A user could upload a very large file and hold it for 12 hours. Mitigations: HTTP request size limits at the WSGI layer, `max_file_upload_size` in session.

2. **Remote URL fetches:** A malicious import could hammer external servers. Mitigation: `import_url_regex` config + `_can_import_remote_urls()` hook + `import_file_timeout` + `import_file_maxbytes`.

3. **Memory exhaustion:** Parsing very large files (millions of rows) in the preview phase loads `count=10` rows into memory but the full file is in the DB row. The batch mode prevents loading all rows at once during import.

---

## Odoo 18 → 19 Changes for base_import

Based on code analysis, the following notable differences exist in Odoo 19:

1. **OWL Rewrite (Full JS frontend):** The entire import UI was rewritten using OWL (Odoo's React-like component framework) replacing the legacy `web.import` action. This introduced `import_model.js`, `import_action.js`, and modular sub-components (`import_data_content`, `import_data_options`, `import_data_progress`, `import_data_sidepanel`).

2. **New batch import UI:** A dedicated progress panel (`import_data_progress`) shows step-by-step batch progress with a stop button. Resume is supported by tracking `nextrow`.

3. **New binary file manager:** `binary_file_manager.js` handles post-import file attachment for fields where the import contains a filename rather than base64 content. Files are uploaded in configurable batch sizes (`maxSizePerBatch` in MB).

4. **`_filter_fields_by_types` optimization:** Type-based field filtering before fuzzy matching reduces the candidate set and improves suggestion relevance.

5. **Properties field expansion:** Full support for importing into `properties` and `properties_definition` fields, with inline property definitions generated dynamically in `get_fields_tree()`.

6. **Error grouping on retry:** When an import fails and is retried with fallback values, errors are grouped by field and message type for cleaner display in the UI.

7. **`import_set_empty_fields` and `import_skip_records`:** New options to explicitly set fields to False or skip entire records based on conditions, providing more control over partial imports.

---

## Adding Import Support to a Custom Model

### 1. Implement `get_import_templates()` hook

```python
class MyModel(models.Model):
    _name = 'my.model'
    _inherit = 'base'

    @api.model
    def get_import_templates(self):
        return [{
            'label': _('Import Template for My Model'),
            'template': '/base_import/static/csv/mymodel_import.csv'
        }]
```

The CSV template is served as a static file download link in the import UI.

### 2. Customize field display for import

The import UI uses `fields_get()` attributes. Customizing `string`, `help`, or adding `import_compatible` metadata can improve the import experience without any explicit import hooks.

### 3. Handle relational field imports

When importing into `one2many` fields, the subfield names must exactly match the target model's field names (or the subfield's `id`/`.id` special fields). The import system handles the nested record creation automatically via `model.load()`.

### 4. Override for custom load behavior

```python
class MyModel(models.Model):
    _name = 'my.model'

    @api.model
    def _import_set_fields(self):
        # Called after field resolution during load
        super()._import_set_fields()
        # Custom field-level import logic
```

---

## File Format Reference

| Format | Extension | MIME Type | Reader | Key Limitation |
|--------|-----------|-----------|--------|----------------|
| CSV | `.csv` | `text/csv` | Python `csv` | Separator auto-detect can fail on ambiguous files |
| Excel 97-2003 | `.xls` | `application/vnd.ms-excel` | `xlrd` | xlrd 2.x drops .xls support |
| Excel 2007+ | `.xlsx` | `application/vnd.openxmlformats...` | `openpyxl` | `data_only=True` returns cached values, not formula results |
| OpenDocument | `.ods` | `application/vnd.oasis.opendocument.spreadsheet` | `odfpy` | Column spans handled via `numbercolumnsspanned` attribute |

**ODS Reader — Spanned columns:** The custom `ODSReader` class handles LibreOffice/Excel column spanning via the `numbercolumnsspanned` attribute. Spanned cells are replicated (cloned) the appropriate number of times so that the row array has the correct number of elements. Cells starting with `#` are treated as comments and skipped.

**ODS Reader — Text extraction:** Text is extracted from `text:span` nodes within `text:p` (paragraph) nodes. Nested structure: `Table → TableRow → TableCell → P → text:span`. The `textContent` accumulation pattern means that multi-span text in a single cell will be concatenated.

---

## Performance Notes

| Operation | Cost | Mitigation |
|-----------|------|------------|
| `parse_preview()` on large file | Reads entire file to count rows | File length returned from reader; only 10 rows parsed for preview |
| `get_fields_tree()` | Calls `fields_get()` for target model | Called once per preview load; not cached across requests |
| chardet encoding detection | Full file scan in Python | Only runs once; result stored in options |
| `base_import.mapping.search_read()` | One query per preview | Minimal cost for typical mapping counts |
| `model.load()` | Batch ORM writes | Batch size controlled by `limit` option |
| Image dimension check (PIL) | CPU-intensive for large images | 42MP pixel limit prevents worst cases |

---

## Related Documentation

- [Core/API](Core/API.md) — @api.model, @api.depends decorators, name_create context
- [Tools/ORM Operations](odoo-18/Tools/ORM Operations.md) — search(), browse(), load() methods
- [Patterns/Inheritance Patterns](odoo-18/Patterns/Inheritance Patterns.md) — Extending base_import for custom formats
- [New Features/What's New](odoo-18/New Features/What's New.md) — Odoo 19 OWL import UI changes

## Tags

#odoo #odoo19 #import #csv #excel #data-migration #batch-import #base_import
