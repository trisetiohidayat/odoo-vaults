---
type: module
module: barcodes
tags: [odoo, odoo19, barcodes, nomenclature, parsing, gs1, epc, rfid]
created: 2026-04-06
updated: 2026-04-11
---

# Barcode

## Overview

| Property | Value |
|----------|-------|
| **Name** | Barcode |
| **Technical** | `barcodes` |
| **Category** | Supply Chain/Inventory |
| **Version** | `2.0` |
| **Depends** | `web` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Post-init hook** | `_assign_default_nomeclature_id` |

## Module Purpose

Provides the core barcode parsing engine used by [Modules/stock](Modules/stock.md), [Modules/point_of_sale](Modules/point_of_sale.md), and other inventory/nomenclature modules. It defines barcode nomenclatures (sets of ordered rules), individual barcode rules, a form-level barcode event mixin, and GS1 / EPC RFID URI parsing support.

## Data Files

| File | Purpose |
|------|---------|
| `data/barcodes_data.xml` | Default `barcode.nomenclature` + one catch-all `product` rule at sequence 90 |
| `views/barcodes_view.xml` | Form/list views for nomenclature and rule models |
| `security/ir.model.access.csv` | Read ACL for `base.group_user`; full ACL for `base.group_erp_manager` |

## Post-init Hook

```python
post_init_hook: '_assign_default_nomenclature_id'
```

On first install, assigns the default `barcode.nomenclature` to all companies that do not yet have one set. Named with the original typo `nomeclature` in the manifest.

---

# L1 — Model Field Signatures, Method Declarations, and Inheritance

## Models at a Glance

| Model | File | Inherits | Kind |
|-------|------|----------|------|
| `barcode.nomenclature` | `models/barcode_nomenclature.py` | None | Standalone BaseModel |
| `barcode.rule` | `models/barcode_rule.py` | None | Standalone BaseModel |
| `barcodes.barcode_events_mixin` | `models/barcode_events_mixin.py` | None | Abstract mixin |
| `res.company` | `models/res_company.py` | `res.company` | Extension |
| `ir.http` | `models/ir_http.py` | `ir.http` | Extension |

---

## `barcode.nomenclature`

**File:** `models/barcode_nomenclature.py`
**Access:** `base.group_user` (read-only); `base.group_erp_manager` (full)

### Fields

| Field | Type | Required | Default | Help |
|-------|------|----------|---------|------|
| `name` | `Char` | Yes | — | Internal identification string shown in UI. No uniqueness constraint. |
| `rule_ids` | `One2many` → `barcode.rule` | No | — | Ordered list of rules. Deleted rules cascade. |
| `upc_ean_conv` | `Selection` | Yes | `'always'` | Controls automatic UPC↔EAN-13 conversion before rule matching. |

### `upc_ean_conv` — Selection Values

```python
UPC_EAN_CONVERSIONS = [
    ('none',   'Never'),
    ('ean2upc', 'EAN-13 to UPC-A'),   # 13-digit EAN-13 with leading 0 stripped to 12-digit UPC-A
    ('upc2ean', 'UPC-A to EAN-13'),   # 12-digit UPC-A prefixed with 0 to form 13-digit EAN-13
    ('always',  'Always'),            # Both directions applied
]
```

**Rationale:** UPC-A barcodes (12 digits) are a subset of EAN-13 (13 digits). A UPC-A barcode `012345678905` is equivalent to EAN-13 `0012345678905`. Some scanners emit one format while the system expects the other. Setting `upc_ean_conv` to `'always'` (the default) makes both formats interchangeable without requiring separate rules for each encoding.

### Methods

#### `sanitize_ean(ean)` — `@api.model`

```
params:  ean: str (up to 13 chars)
return:  str (13 chars, zero-padded, valid GTIN checksum)
```

Takes a partial EAN string (up to 13 chars), left-zero-pads it to 13 characters, then recomputes the check digit using the GTIN algorithm. Used to normalize EAN-13 barcodes after numeric value extraction.

**Example:** `sanitize_ean('401234512345')` returns `'4012345123456'` (last digit recomputed).

#### `sanitize_upc(upc)` — `@api.model`

```
params:  upc: str (up to 12 chars)
return:  str (12 chars, zero-padded, valid UPC-A checksum)
```

Converts to EAN-13 via `sanitize_ean('0' + upc)`, then strips the leading `0` to return a valid UPC-A. Ensures check digit consistency for both encodings.

#### `match_pattern(barcode, pattern)` — record method

```
params:  barcode: str,  pattern: str
return:  dict { 'value': float, 'base_code': str, 'match': bool }
```

Core pattern-matching engine. Escapes the barcode for regex meta-characters, then:

1. Searches for a `{N* D*}` capture group in the pattern (the only supported numeric encoding syntax).
2. Extracts the whole-number and decimal portions from the barcode.
3. Replaces the captured digits with zeros in `base_code` and in the pattern itself.
4. Runs `re.match(pattern, base_code[:len(pattern)])` — a **prefix match**, not a full match.

Returns `{'value': 0, 'base_code': barcode, 'match': False}` on failure.

**Pattern syntax:**
- `{N}` — integer value (e.g., `{N}` matches 1 digit, `{NN}` matches 2)
- `{D}` — single decimal digit after the integer part
- `{ND}` — whole digits + 1 decimal (e.g., `{NND}` = 2 whole digits, 1 decimal)
- `{NNDD}` — 2 whole digits, 2 decimal digits
- `{NNNDDDD}` — weighted product barcode: 3 whole digits = price/weight, 4 decimals = fractional part
- Literal `.` in pattern must be escaped in the barcode (the method replaces `.` with `\.` in the regex)
- The barcode must match the pattern **prefix** — `re.match` is used, not `re.search`

#### `parse_barcode(barcode)` — record method

```
params:  barcode: str
return:  dict | list[dict]
```

Top-level dispatcher. Checks if the barcode starts with `urn:` — if so, delegates to `parse_uri()`. Otherwise calls `parse_nomenclature_barcode()`.

#### `parse_nomenclature_barcode(barcode)` — record method

```
params:  barcode: str
return:  dict { 'encoding', 'type', 'code', 'base_code', 'value' }
```

Full parsing pipeline:

1. Initializes error result: `{'encoding': '', 'type': 'error', 'code': barcode, 'base_code': barcode, 'value': 0}`.
2. Iterates `rule_ids` **in sequence order** (lowest first).
3. For each rule, applies UPC↔EAN conversion if configured (`cur_barcode` may differ from original).
4. Calls `check_barcode_encoding()` — rejects if barcode length/checksum wrong for the rule's encoding.
5. Calls `match_pattern()` — rejects if regex does not match.
6. If `rule.type == 'alias'`: sets `parsed_result['code'] = rule.alias` and **continues the loop** (alias resolution is recursive; if the alias matches another rule it will be re-parsed).
7. If `rule.type == 'product'`: fills encoding, type, value, code, base_code; sanitizes check digit for EAN/UPC; **returns immediately** (first match wins).
8. If no rule matches: returns error dict.

#### `parse_uri(barcode)` — `@api.model`

```
params:  barcode: str (e.g., 'urn:epc:class:lgtin : 4012345.012345.998')
return:  list[dict] | dict
```

Handles EPC (Electronic Product Code) URIs conforming to the GS1 EPC Tag URI standard. Dispatches based on identifier:

| Identifier | Method called | Return type |
|-----------|---------------|-------------|
| `lgtin` | `_convert_uri_gtin_data_into_tracking_number` | `list[product, lot]` |
| `sgtin` | `_convert_uri_gtin_data_into_tracking_number` | `list[product, lot]` |
| `sgtin-96` | `_convert_uri_gtin_data_into_tracking_number(data[1:])` | `list[product, lot]` |
| `sgtin-198` | `_convert_uri_gtin_data_into_tracking_number(data[1:])` | `list[product, lot]` |
| `sscc` | `_convert_uri_sscc_data_into_package` | `list[package]` |
| `sscc-96` | `_convert_uri_sscc_data_into_package(data[1:])` | `list[package]` |

The `-96` and `-198` variants strip the filter/partition byte (first element after splitting) before processing.

#### `_convert_uri_gtin_data_into_tracking_number(base_code, data)` — `@api.model`

```
params:  base_code: str,  data: list[str] (split by '.')
return:  list[dict, dict]
```

Splits GS1 company prefix + item-reference-and-indicator + lot serial number. Computes the full GTIN-14 product barcode from components, appends check digit, returns two-entry list:

```python
[
    {'base_code': base_code, 'code': product_barcode, 'encoding': '',
     'type': 'product', 'value': product_barcode},
    {'base_code': base_code, 'code': tracking_number, 'encoding': '',
     'type': 'lot',     'value': tracking_number},
]
```

**GS1 structure:** The input URI `urn:epc:class:lgtin: 4012345.012345.998` means:
- Company prefix: `4012345` (7 digits, variable length in GS1)
- Item reference + indicator: `012345` (first digit = indicator, remaining = item ref)
- Lot/serial: `998`

GTIN is built as: `indicator + company_prefix + item_ref + check_digit`.

#### `_convert_uri_sscc_data_into_package(base_code, data)` — `@api.model`

```
params:  base_code: str,  data: list[str]
return:  list[dict]
```

Similar to GTIN conversion, but builds an 18-digit SSCC (Serial Shipping Container Code):
- Extension digit (0-9) from first char of serial reference
- GS1 company prefix
- Serial reference (excluding extension digit)
- Computed check digit

Returns `{'type': 'package'}`.

#### `_unlink_except_default()` — `@api.ondelete(at_uninstall=False)`

Prevents deletion of the record referenced by `barcodes.default_barcode_nomenclature` (external ID). Raises `UserError` if deletion is attempted. The `at_uninstall=False` ensures this protection persists even when upgrading/uninstalling the module.

---

## `barcode.rule`

**File:** `models/barcode_rule.py`
**Order:** `sequence asc, id`
**Access:** `base.group_user` (read-only); `base.group_erp_manager` (full)

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | `Char` | Yes | — | Internal rule label, shown in rule list. |
| `barcode_nomenclature_id` | `Many2one` → `barcode.nomenclature` | No | `False` | Parent nomenclature. Indexed `btree_not_null`. |
| `sequence` | `Integer` | No | — | Rule evaluation order. Lower = checked first. |
| `encoding` | `Selection` | Yes | `'any'` | Required barcode encoding: `any`, `ean13`, `ean8`, `upca`. |
| `type` | `Selection` | Yes | `'product'` | Semantic type: `alias` or `product`. |
| `pattern` | `Char` | Yes | `'.*'` | Regex-like pattern with `{N}` / `{ND}` capture groups. |
| `alias` | `Char` | Yes | `'0'` | Target barcode when `type == 'alias'`. |

### Field Details

#### `barcode_nomenclature_id` — `Many2one`, `index='btree_not_null'`

```python
barcode_nomenclature_id = fields.Many2one(
    'barcode.nomenclature',
    string='Barcode Nomenclature',
    index='btree_not_null',
)
```

The `index='btree_not_null'` creates a PostgreSQL partial-index B-tree index only on rows where `barcode_nomenclature_id IS NOT NULL`. This avoids indexing NULL rows and speeds up `search([('barcode_nomenclature_id', '=', id)])` in the JS `BarcodeParser.fetchNomenclature()`.

#### `encoding` — `Selection`

| Value | Description | Valid barcode sizes |
|-------|-------------|-------------------|
| `'any'` | No encoding restriction | Any length, any characters |
| `'ean13'` | EAN-13 / GTIN-13 | 13 numeric digits, valid check digit |
| `'ean8'` | EAN-8 | 8 numeric digits, valid check digit |
| `'upca'` | UPC-A | 12 numeric digits, valid check digit |

Validation is performed by `check_barcode_encoding()` in `odoo/tools/barcode.py`, which calls `get_barcode_check_digit()`.

#### `pattern` — `Char`

**Pattern syntax (GS1-inspired):**

```
pattern ::= literal_char | escaped_char | capture_group
literal_char ::= any regex char except . { }
escaped_char ::= \\ | \{ | \} | \.
capture_group ::= '{' num_part [decimal_part] '}'
num_part ::= 'N'+
decimal_part ::= 'D'+
```

- `{N}` through `{NNNN...}` — integer capture (all N's are replaced by 0 in `base_code`)
- `{D}` — single decimal digit appended after integer part
- `{ND}`, `{NND}`, `{NNND}`, `{NNDD}`, `{NNNDD}` — integer + decimal capture
- Literal `.` is **required** in the pattern where a literal `.` appears in the barcode (escaped in regex as `\.`)

**Examples:**

| Pattern | Matches | `base_code` | `value` |
|---------|---------|-------------|---------|
| `.*` | Anything | unchanged | 0 |
| `........` | Exactly 8 digits | unchanged | 0 |
| `{NNNNNNNN}` | All 8 digits as integer | `00000000` | `12345678.0` |
| `1........{NND}.` | EAN-13: prefix `1`, 8 middle, 2-digit value, check digit | `1000000000009` | `12.5` |
| `.....{NNNDDDD}.` | 5 prefix, 3-digit whole, 4-digit decimal, check | varies | e.g., `456.1025` |

#### `alias` — `Char`

Only active when `type == 'alias'`. When a barcode matches this rule's pattern, the parser **replaces** the scanned barcode with the alias value and continues rule evaluation. This enables short-code barcodes (e.g., store internal codes) to map to standard product barcodes.

### Constraints

#### `_check_pattern()` — `@api.constrains('pattern')`

Validates pattern syntax at write time:

1. Unescapes `\\`, `\{`, `\}` to `X` for analysis purposes.
2. Counts brace pairs `{` and `}` — must be exactly 0 or 1 pair.
3. If 1 pair exists: must match `[{][N]*[D]*[}]` (N's then D's, no `D` before `N`).
4. Empty braces `{ }` raise `ValidationError`.
5. Pattern `'*'` is rejected (use `'.*'`).
6. The pattern after removing `{N+D*}` groups must be a valid Python regex.

---

## `barcodes.barcode_events_mixin`

**File:** `models/barcode_events_mixin.py`
**Kind:** Abstract mixin
**Model name:** `barcodes.barcode_events_mixin`

An abstract mixin for models that handle barcode scans in form views via the `barcode_handler` widget.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `_barcode_scanned` | `Char` | `False` | Transient storage for the last scanned barcode value. `store=False` — not persisted. |

### Methods

#### `_on_barcode_scanned()` — `@api.onchange('_barcode_scanned')`

```python
@api.onchange('_barcode_scanned')
def _on_barcode_scanned(self):
    barcode = self._barcode_scanned
    if barcode:
        self._barcode_scanned = ""   # reset immediately
        return self.on_barcode_scanned(barcode)
```

This method fires whenever `_barcode_scanned` is written (typically by the `barcode_handler` widget). It clears the field immediately and delegates to `on_barcode_scanned(barcode)`.

#### `on_barcode_scanned(barcode)` — abstract

```python
def on_barcode_scanned(self, barcode):
    raise NotImplementedError(...)
```

Consumers of this mixin must override `on_barcode_scanned()`. The method receives the raw barcode string and returns a dict with form commands (e.g., `{'type': 'action', 'name': '...'}`, field updates, or a `warning` dict). Returning `None` or `{}` performs no action.

**Mixin consumers in Odoo 19:**
- `stock.picking` (via `stock.py` inheriting this mixin)
- `stock.inventory` (via `stock.py`)
- `pos.order` (via `point_of_sale`)
- Custom models in industry-specific addons

---

## `res.company` Extension

**File:** `models/res_company.py`

### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `nomenclature_id` | `Many2one` → `barcode.nomenclature` | Per-company barcode nomenclature. Default = `barcodes.default_barcode_nomenclature`. |

```python
nomenclature_id = fields.Many2one(
    'barcode.nomenclature',
    string="Nomenclature",
    default=lambda self: self.env.ref('barcodes.default_barcode_nomenclature', raise_if_not_found=False),
)
```

**Design note:** `default=lambda self: self.env.ref(...)` is evaluated at record-creation time, so each new company automatically gets the default nomenclature. The post-init hook handles existing companies created before the module was installed.

**Multi-company behavior:** Each company can assign a different `barcode.nomenclature`. When a user scans a barcode, the system uses `env.company.nomenclature_id`. This allows multinational deployments to use region-specific barcode standards.

---

## `ir.http` Extension

**File:** `models/ir_http.py`

### Methods Added

#### `session_info()` — overrides `ir.http.session_info()`

Appends `max_time_between_keys_in_ms` to the web session info JSON sent to the client:

```python
def session_info(self):
    res = super().session_info()
    if self.env.user._is_internal():
        res['max_time_between_keys_in_ms'] = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'barcode.max_time_between_keys_in_ms',
                default='150'
            )
        )
    return res
```

**Purpose:** The web client uses this value to debounce keyboard events when emulating a barcode scanner. If the gap between keypresses exceeds `max_time_between_keys_in_ms`, the client resets the scan buffer. The `sudo()` call reads `ir.config_parameter` as admin (system-wide). Excluded for portal users (`_is_internal() == False`).

---

# L2 — Field Types, Defaults, Constraints, and Encoding Rules

## barcode.nomenclature — Encoding and Conversion

### UPC ↔ EAN Conversion Logic

The `upc_ean_conv` field controls a pre-processing step in `parse_nomenclature_barcode()`:

```python
for rule in self.rule_ids:
    cur_barcode = barcode
    if rule.encoding == 'ean13' and check_barcode_encoding(barcode, 'upca') and self.upc_ean_conv in ['upc2ean', 'always']:
        cur_barcode = '0' + cur_barcode          # 12-digit UPC-A → 13-digit EAN-13
    elif rule.encoding == 'upca' and check_barcode_encoding(barcode, 'ean13') and barcode[0] == '0' and self.upc_ean_conv in ['ean2upc', 'always']:
        cur_barcode = cur_barcode[1:]            # 13-digit EAN-13 → 12-digit UPC-A
```

Key design points:
- Conversion only applies when `check_barcode_encoding()` confirms the barcode could be the other format
- EAN-13 with leading `0` is treated as UPC-A (the leading `0` is a UPC-A zero-padding, not a valid EAN-13 digit)
- After conversion, `check_barcode_encoding()` is called again against the converted barcode for the rule's encoding

### Sequence Padding in Default Rule

The default rule in `barcodes_data.xml` has `sequence=90`. This is deliberate: specialized rules with lower sequence numbers (e.g., weighted product rules at sequence 10, lot-specific rules at sequence 20) will match first. Sequence 90 is high enough that most custom rules take precedence.

### `btree_not_null` Index — PostgreSQL Partial Index

```python
barcode_nomenclature_id = fields.Many2one(..., index='btree_not_null')
```

This translates to:
```sql
CREATE INDEX idx_barcode_rule_nomenclature_not_null
ON barcode_rule (barcode_nomenclature_id)
WHERE barcode_nomenclature_id IS NOT NULL;
```

Rules with `barcode_nomenclature_id = NULL` are not indexed. This is optimal because rules without a nomenclature are typically orphaned or legacy rules.

---

# L3 — Cross-Model Integration, Override Patterns, and Workflow Triggers

## Cross-Model: GS1 Barcode Encoding

`stock.quant._get_gs1_barcode()` (in `stock` module) appends GS1 Application Identifier codes:
- **AI `17`**: Expiration date (`'YYMMDD'` format) — from `q.lot_id.expiration_date`
- **AI `15`**: Best-before date (`'YYMMDD'` format) — from `q.lot_id.use_date`

These codes are embedded in the datamatrix barcode on lot labels for scanning by warehouse logistics systems. The `product_expiry` module adds this via `StockQuant._get_gs1_barcode()` override.

## Cross-Model: `barcode_events_mixin` Usage Chain

```
Hardware scanner emits keystrokes
  ↓
Web client receives keypress burst (< max_time_between_keys_in_ms)
  ↓
JS BarcodeParser.parseBarcode() runs client-side parsing
  ↓
If JS parser returns type='product' → triggers RPC to server
  ↓
Server (stock.picking) calls:
    product = env['product.product'].search([('barcode', '=', barcode)])
  ↓
If no product found, tries lot:
    lot = env['stock.lot'].search([('name', '=', barcode), ('product_id', '=', ...)])
  ↓
If found: updates form field / moves to next line
If not found: returns {'warning': {'title': ..., 'message': ...}}
```

## Cross-Model: `stock` Module Integration

`stock.picking` and `stock.inventory` in the `stock` module inherit `barcodes.barcode_events_mixin` via their own model definitions. The mixin's `on_barcode_scanned()` handler does product/lot/package lookups.

## Override Pattern: `res.company` Extension

The `nomenclature_id` field on `res.company` allows per-company barcode standards. When a user scans a barcode, the system uses `request.env.company.nomenclature_id`. This is resolved in the web client context.

## `ir.config_parameter` — max_time_between_keys_in_ms

This system-wide parameter (key: `barcode.max_time_between_keys_in_ms`, default: `150`) controls the keyboard debounce interval. It is read via `ir.config_parameter.sudo().get_param(...)` in `ir.http.session_info()` and exposed to the JS client in the session info JSON.

---

# L4 — Performance, Odoo 18 to 19 Changes, Security, and Edge Cases

## Performance

### Client-Side Parsing vs Server-Side

Hardware barcode scanners emit keyboard events. The web client must:
- Detect that a rapid burst of keystrokes is a barcode scan (not manual typing) using `max_time_between_keys_in_ms`.
- Parse the barcode immediately in JavaScript to determine the action type (`product`, `lot`, `package`, `alias`) before making an RPC call.
- Avoid a server round-trip for every scan in high-throughput scenarios (POS, stock operations).

The JavaScript `BarcodeParser` class in `static/src/js/barcode_parser.js` is a near-complete mirror of the Python `barcode.nomenclature` model. It:
1. Fetches the `barcode.nomenclature` record and its sorted rules via `orm.read()` and `orm.searchRead()`.
2. Implements `get_barcode_check_digit()`, `check_encoding()`, `sanitize_ean()`, `sanitize_upc()` identically to Python.
3. Implements `match_pattern()`, `parse_barcode()`, `parseBarcodeNomenclature()`, `parseURI()`, and the URI conversion methods.

The Python backend is the source of truth for rule validation and canonical `base_code` computation (especially check digit sanitization).

### No DB Caching in Python

`parse_nomenclature_barcode()` re-reads `rule_ids` from DB each call. In a tight scanning loop, this adds repeated SQL queries. The JS client avoids this by loading nomenclature once per session.

### Rule Ordering

Rules are evaluated in sequence on every scan. Keep the number of rules low (under ~20 per nomenclature). Put the most specific rules first (lowest sequence).

### Thread-Safety in Report Rendering

`odoo/tools/barcode.py` uses a `RLock` and `functools.lru_cache` to lazily initialize ReportLab's barcode font cache, making it safe to call `createBarcodeDrawing()` from multiple threads (used in QWeb PDF reports).

## Odoo 18 to 19 Changes

1. **`parse_uri` method signature:** In Odoo 18, `parse_uri` accepted `lgtin`, `sgtin`, `sgtin-96`, `sscc`, `sscc-96`. Odoo 19 added `sgtin-198` support.

2. **`match_pattern` regex behavior:** The Python `re.match()` behavior (prefix match) is preserved. The JS client added `^` prefix anchoring for `|`-split alternatives in the pattern matching step.

3. **Post-init hook typo:** The hook `_assign_default_nomenclature_id` (original code has a typo `nomeclature` vs `nomenclature` in the manifest) assigns the default nomenclature to all companies created before the module was installed.

4. **GS1 URI handling:** Support for `sgtin-198` (198-bit EPC binary encoding converted to URI) was added in the 18→19 cycle for RFID tag compatibility.

## Security

### ACL Design

| ID | Name | Model | Group | R | W | C | D |
|----|------|-------|-------|---|---|---|---|
| `access_barcode_nomenclature_user` | Nomenclature (User) | `model_barcode_nomenclature` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_barcode_nomenclature_manager` | Nomenclature (Manager) | `model_barcode_nomenclature` | `base.group_erp_manager` | 1 | 1 | 1 | 1 |
| `access_barcode_rule_user` | Rule (User) | `model_barcode_rule` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_barcode_rule_manager` | Rule (Manager) | `model_barcode_rule` | `base.group_erp_manager` | 1 | 1 | 1 | 1 |

Regular users can read nomenclatures and rules but cannot modify them. Only ERP Managers can create/edit/delete. This is intentional — barcode rule changes affect all scanners and can silently break barcode scanning across the system.

### Information Disclosure

Reading a `barcode.rule` record reveals its `pattern` and `alias`. Users with read-only ACL can see which barcode patterns are configured. This is generally non-sensitive but could reveal internal product coding schemes.

## Edge Cases

### Pattern with Two Brace Groups

A pattern with two `{...}` groups (e.g., `{NN}{DD}`) raises `ValidationError` in `_check_pattern`. Only one capture group is allowed per rule.

### `{DN}` is Invalid

The pattern `{DN}` (decimal before whole) is syntactically invalid — `D` may not appear before `N`. The `_check_pattern` constraint catches this.

### UPC-A Barcode as EAN-13

`check_barcode_encoding('012345678905', 'ean13')` returns `False` because:
- Length is 13 → passes size check
- `barcode[0] == '0'` → fails the `encoding != 'ean13' or barcode[0] != '0'` condition

This prevents a UPC-A barcode (already 12 digits) from being accidentally validated as EAN-13. The `parse_nomenclature_barcode()` handles this conversion explicitly via `upc_ean_conv` before calling `check_barcode_encoding`.

### Alias Recursion

When `rule.type == 'alias'`, the parser replaces the barcode with `rule.alias` and **continues the rule loop**. If the alias matches another rule, it will be re-parsed. There is no explicit recursion guard; circular aliases would cause an infinite loop in the rule search. However, the default rules are simple enough that this is not a practical concern.

### GS1 URI Returns List

When `parse_uri` handles GTIN types (`lgtin`, `sgtin`, etc.), it returns a **list** of two dicts: one for the product barcode and one for the lot/serial number. Callers (e.g., stock picking line scanner) must handle both entries.

### Empty Pattern `.*`

The default catch-all rule uses `pattern='.*'` which is a valid regex matching any string. This ensures any barcode that fails all explicit rules still returns a `product` type rather than an `error`.

---

## Core Barcode Check Digit Algorithm

**File:** `odoo/odoo/tools/barcode.py`

Both the Python backend and the JavaScript client implement the same GTIN check digit algorithm:

```python
def get_barcode_check_digit(numeric_barcode: str) -> int:
    oddsum = evensum = 0
    code = numeric_barcode[-2::-1]   # reverse, drop last char (check digit)
    for i, digit in enumerate(code):
        if i % 2 == 0:
            evensum += int(digit)    # positions 1,3,5... (0-indexed even after reverse)
        else:
            oddsum += int(digit)     # positions 2,4,6...
    total = evensum * 3 + oddsum
    return (10 - total % 10) % 10
```

**GS1 specification:** Multiply positions 1-17 by `x3, x1, x3...` alternating. The check digit makes `(evensum * 3 + oddsum) % 10 == 0`.

**Used by:**
- `barcode_nomenclature.sanitize_ean()` and `sanitize_upc()` — recompute check digit after zero-padding
- `barcode_nomenclature.parse_nomenclature_barcode()` — verify barcode before accepting a rule match
- `barcode_nomenclature._convert_uri_gtin_data_into_tracking_number()` — compute final check digit when constructing GTIN from GS1 URI components
- `barcode_nomenclature._convert_uri_sscc_data_into_package()` — same for SSCC
- `check_barcode_encoding()` — validates that a barcode's check digit is correct for its declared encoding

```python
def check_barcode_encoding(barcode: str, encoding: str) -> bool:
    encoding = encoding.lower()
    if encoding == "any":
        return True
    barcode_sizes = {'ean8': 8, 'ean13': 13, 'gtin14': 14, 'upca': 12, 'sscc': 18}
    barcode_size = barcode_sizes[encoding]
    return (encoding != 'ean13' or barcode[0] != '0') \
           and len(barcode) == barcode_size \
           and re.match(r"^\d+$", barcode) \
           and get_barcode_check_digit(barcode) == int(barcode[-1])
```

---

## Related Modules

- [Modules/stock](Modules/stock.md) — `stock.picking`, `stock.inventory` inherit the barcode event mixin
- [Modules/point_of_sale](Modules/point_of_sale.md) — POS uses `BarcodeParser` in JavaScript for product identification
- [Modules/product](Modules/product.md) — Product `barcode` field is the primary lookup target
- [Core/Fields](Core/Fields.md) — Barcode field type in Odoo
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — State machine usage in picking confirmation

## See Also

- [Modules/stock](Modules/stock.md)
- [Modules/point_of_sale](Modules/point_of_sale.md)
- [Modules/stock_account](Modules/stock_account.md) (inventory valuation via stock.quant)
- [Core/Fields](Core/Fields.md) (barcode field type in Odoo)
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) (state machine usage in picking confirmation)
