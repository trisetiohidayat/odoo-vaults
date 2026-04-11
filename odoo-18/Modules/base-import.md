---
Module: base_import
Version: Odoo 18
Type: Core Extension
Tags: #odoo18, #orm, #modules, #import, #csv
---

# base_import

CSV/XLS/XLSX/ODS file import wizard with smart column mapping, preview, encoding detection, and batch processing.

## Module Overview

- **Model:** `base_import.import` (TransientModel)
- **Model:** `base_import.mapping` (persistent column mapping storage)
- **Model:** `res.users` (extension for URL import permission)
- **Dependency:** `base`
- **Import formats:** CSV, XLS (xlrd), XLSX (openpyxl), ODS (odfpy)

---

## Models

### `base_import.import`

```python
class Import(models.TransientModel):
    _name = 'base_import.import'
    _description = 'Base Import'
    _transient_max_hours = 12.0  # survives for 12 hours

    res_model = fields.Char('Model')
    file = fields.Binary('File', attachment=False)  # raw binary, not base64 stored
    file_name = fields.Char('File Name')
    file_type = fields.Char('File Type')
```

Transient import wizard. The `file` is stored as raw binary (not base64-encoded in the ORM sense) and `attachment=False` ensures it bypasses the file storage mechanism.

**File type detection:**

```python
FILE_TYPE_DICT = {
    'text/csv': ('csv', True, None),
    'application/vnd.ms-excel': ('xls', xlrd, 'xlrd'),
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ('xlsx', ...),
    'application/vnd.oasis.opendocument.spreadsheet': ('ods', odf_ods_reader, 'odfpy')
}
EXTENSIONS = {'.csv': ..., '.xls': ..., '.xlsx': ..., '.ods': ...}
```

Detection order: mimetype -> user-provided mimetype -> file extension (fallback).

---

## Key Methods

### `get_fields_tree(model, depth=3)`

```python
@api.model
def get_fields_tree(self, model, depth=FIELDS_RECURSION_LIMIT):
```

Recursively builds the importable fields tree for a model. Returns a list of dicts with:
- `id`, `name`, `string`, `required`, `type`, `model_name`
- `fields` (sub-fields for relational types)

**Field type handling:**

| Field type | Sub-fields |
|-----------|-----------|
| `many2one` | `id` (External ID), `.id` (Database ID) |
| `many2many` | `id` (External ID), `.id` (Database ID) |
| `one2many` | Recursive tree + `.id` for admin |
| `properties` | Flattened into `model.fieldname.propertyname` entries |

Excludes: `MAGIC_COLUMNS` (`id`, `create_uid`, etc.), readonly fields.

### `_read_file(options)`

Dispatches to `_read_csv()`, `_read_xls()`, `_read_xlsx()`, or `_read_ods()` based on detected type. Auto-detects encoding for CSV using `chardet`.

### `_read_csv(options)`

- Auto-detects encoding via `chardet`
- Handles BOM stripping for UTF-16/32
- Auto-detects separator: tries `,`, `;`, `\t`, ` `, `|`, unit separator; picks the first where all rows have equal width and at least 2 columns
- Returns `(row_count, rows)` where rows are non-empty CSV lines

### `_read_xls(options)` / `_read_xlsx(options)`

- Converts numbers to strings (ints vs floats), dates to `DEFAULT_SERVER_DATETIME_FORMAT`
- For XLSX, uses `openpyxl` when xlrd 2.x is installed (xlrd 2.x dropped XLSX support)

### `_read_ods(options)`

Reads OpenDocument Spreadsheet format using `odf_ods_reader`.

---

## Column Mapping

### `_get_mapping_suggestion(header, fields_tree, header_types, mapping_fields)`

Three-tier matching for each column header:

1. **Saved mapping** (`base_import.mapping`): exact match on column name -> field name
2. **Exact match**: header string == field `name` OR field `string` (in user's language) OR field string in English
3. **Fuzzy match**: word distance (Levenshtein-like via `difflib.SequenceMatcher`) between header and field labels, filtered by extracted header type. Keeps matches with distance < 0.2.

```python
def _get_distance(self, a, b):
    return 1 - difflib.SequenceMatcher(None, a, b).ratio()
```

Distance 0 = exact match, 1 = completely different. Only matches with distance < `FUZZY_MATCH_DISTANCE` (0.2) are suggested.

### `_deduplicate_mapping_suggestions(mapping_suggestions)`

When multiple columns match the same field, keeps only the closest match. Hierarchy mappings (containing `/`) are excluded from deduplication.

---

## Type Extraction

### `_extract_header_types(preview_values, options)`

Heuristic to determine likely field types from 10 preview rows:

| Heuristic | Suggested types |
|-----------|----------------|
| All start with `__export__` | `id`, `many2many`, `many2one`, `one2many` |
| All are integers | `integer`, `float`, `monetary` (+ `boolean` if only 0/1) |
| All are True/False/t/f | `boolean` |
| All parse as floats | `float`, `monetary` |
| All parse as dates | `date`, `datetime` |
| None of the above | `text`, `char`, `binary`, `selection`, `html`, `tags` |

Separator inference for floats: if the value has two non-number characters and the last one appears only once, the duplicated one is the thousand separator and the unique one is the decimal separator.

### `parse_preview(options, count=10)`

Main preview method. Returns:
```python
{
    'fields': fields_tree,
    'matches': {col_index: [field_path]},      # suggested mapping
    'headers': [header_name, ...],
    'header_types': [[type1], [type2], ...],
    'preview': [[val1, val2, ...], ...],        # first 5 non-null values per column
    'options': options,
    'advanced_mode': bool,                      # True if relational headers/match
    'debug': bool,                             # True if user is admin
    'batch': bool,                             # True if file has more rows than limit
    'file_length': int,
}
```

---

## Data Import Pipeline

### `_convert_import_data(fields, options)`

Extracts indices for non-empty field mappings, slices rows to match, and returns `(data, import_fields)`.

### `_parse_import_data(data, import_fields, options)`

Recursively parses date, datetime, float, and binary fields:
- **Date/datetime:** Applies user-configured `date_format` / `datetime_format`, converts to Odoo's `Date.to_string()` or `Datetime.to_string()` format
- **Float:** Infers thousand/decimal separators, strips currency symbols, converts `()` for negatives
- **Binary/image:** Handles three cases: URL (fetches via HTTP), filename (placeholder), base64 (decoded directly). URL imports require `base.group_no_one` via `_can_import_remote_urls()`.

### `_handle_multi_mapping(import_fields, input_file_data)`

Concatenates multiple columns mapped to the same field:
- `char` / `text`: joined with space / newline
- `many2many`: joined with `,`

### `_handle_fallback_values(import_fields, input_file_data, fallback_values)`

Handles non-matching boolean/selection inputs by applying user-configured fallback mappings.

---

## `execute_import(fields, columns, options, dryrun=False)`

The main import executor:

```
1. Savepoint (cr.savepoint)
2. _convert_import_data → _parse_import_data
3. _handle_multi_mapping → _handle_fallback_values
4. model.load(import_fields, merged_data)
5. On success: save column mappings to base_import.mapping
6. On dryrun: rollback (pool.clear_all_caches + pool.reset_changes)
7. Return {ids, messages, name, nextrow, binary_filenames}
```

Uses `dryrun=True` for test mode (pre-import validation). Uses `dryrun=False` for actual import.

---

## `base_import.mapping`

```python
class ImportMapping(models.Model):
    _name = 'base_import.mapping'
    _description = 'Base Import Mapping'

    res_model = fields.Char(index=True)    # target model name
    column_name = fields.Char()           # original file column header
    field_name = fields.Char()            # matched field name
```

Persistent mapping table. On successful import with headers, existing mappings are updated; new ones are created. This enables "intelligent" re-import of the same third-party data format.

---

## L4 Notes

- **Encoding auto-detection:** Uses `chardet` for CSV. Handles BOM stripping for UTF-16/32 variants. Falls back to file extension for ambiguous cases.
- **Batch mode:** The import is not a single transaction for large files. `parse_preview` detects whether `batch = True` (file has more rows than the configured limit). The actual batching is controlled by `options['limit']`.
- **Test import (`dryrun=True`):** Opens a savepoint, performs the import, then rolls back. Clears all caches (`pool.clear_all_caches()`) to avoid polluting the registry with temporary record IDs.
- **Image import via URL:** Requires `_can_import_remote_urls()` returning True. Default allows only admin. This is a security measure — importing from arbitrary URLs allows SSRF attacks.
- **Image size limits:** `import_image_maxbytes` (default 10 MB), Nokia Lumia 1020 resolution limit (42 million pixels), chunked download with streaming.
- **`name_create_enabled_fields`:** Passed in context to `model.load()` to enable `name_create` on Many2one fields during import.
- **`import_set_empty_fields` / `import_skip_records`:** Context options for `model.load()` to control empty value handling and selective record skipping.
- **Multi-mapping concatenation:** The order of concatenation for text/char fields follows the column order left-to-right. For many2many, the `,` separator is used.
- **JSON serialization:** `base_import.mapping` records are stored per `res_model + column_name`. The model-level deduplication in `_deduplicate_mapping_suggestions` ensures one column matches one field before saving.
- **XLS vs XLSX:** When xlrd 2.x is installed, it cannot read `.xlsx` files, so `openpyxl` is used as the handler for `_read_xlsx`. The module accepts either handler.
