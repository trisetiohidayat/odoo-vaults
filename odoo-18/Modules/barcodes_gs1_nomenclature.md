---
Module: barcodes_gs1_nomenclature
Version: 18.0
Type: addon
Tags: #barcode, #gs1, #stock
---

# barcodes_gs1_nomenclature — GS1 Barcode Nomenclature

## Module Overview

**Category:** Hidden
**Depends:** `barcodes`, `uom`
**License:** LGPL-3
**Installable:** True

Extends the barcode nomenclature system to support GS1-128 barcode parsing. GS1 is a global standard for identifying trade items, locations, and other entities via barcodes. This module enables Odoo to interpret GS1-128 barcodes containing AI (Application Identifier) codes with structured data (dates, weights, lot numbers, etc.).

## Data Files

- `data/barcodes_gs1_rules.xml` — Predefined GS1 barcode rules
- `views/barcodes_view.xml` — Nomenclature form view

## Static Assets (web.assets_backend)

- `barcodes_gs1_nomenclature/static/src/js/barcode_parser.js` — JS-side GS1 barcode decomposition
- `barcodes_gs1_nomenclature/static/src/js/barcode_service.js` — barcode service integration

## Static Assets (web.qunit_suite_tests)

- `barcodes_gs1_nomenclature/static/src/js/tests/**/*` — QUnit tests

## Models

### `barcode.nomenclature` (`barcode.nomenclature`)

**Added Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `is_gs1_nomenclature` | Boolean | When True, uses GS1 specification (GS1-128 only) |
| `gs1_separator_fnc1` | Char | Regex delimiter for FNC1 separator (default: `r'(Alt029|#|\x1D)'`) |

**Methods:**

**`_check_pattern()`**
Validates that `gs1_separator_fnc1` is a valid regex.

**`gs1_date_to_date(gs1_date)`**
Converts a 6-character GS1 date (YYMMDD) to `datetime.date`. Handles century detection per GS1 spec Section 7.12 (years 50-99 = past century; 00-49 = current century). If day is `00`, returns last day of the month.

**`parse_gs1_rule_pattern(match, rule)`**
Parses a matched GS1 barcode segment. Returns a dict with:
- `rule`, `type`, `ai`, `string_value`
- `value` — cast according to `gs1_content_type`:
  - `measure`: applies decimal position from last digit of AI
  - `identifier`: validates check digit (GTIN/UPC/EAN)
  - `date`: converts via `gs1_date_to_date`
  - `alpha`: raw string

**`gs1_decompose_extanded(barcode)`**
Decomposes a GS1 barcode into ordered list of parsed segments. Iteratively finds matching rules (priority order), strips GS1 identifiers (`]C1`, `]e0`, etc.), and returns list of dicts. Returns `None` if decomposition fails.

**`parse_nomenclature_barcode(barcode)`**
Overrides parent. If `is_gs1_nomenclature`, delegates to `gs1_decompose_extanded`; otherwise calls `super()`.

**`_preprocess_gs1_search_args(args, barcode_types, field='barcode')`**
Preprocesses search domain args to strip GS1 padding (leading zeros) from barcode searches. Handles both full GS1 barcode parsing and simple unpadded barcode matching for GS1 nomenclatures.

### `barcode.rule` (`barcode.rule`)

**Added/Modified Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `encoding` | Selection | Added: `gs1-128` option |
| `type` | Selection | Added: `quantity`, `location`, `location_dest`, `lot`, `package`, `use_date`, `expiration_date`, `package_type`, `pack_date` |
| `is_gs1_nomenclature` | Boolean | Related from `barcode_nomenclature_id.is_gs1_nomenclature` |
| `gs1_content_type` | Selection | `date`, `measure`, `identifier`, `alpha` — how to parse the barcode value |
| `gs1_decimal_usage` | Boolean | If True, last digit of AI determines decimal position |
| `associated_uom_id` | Many2one (uom.uom) | Unit of measure for measure-type rules |

**Constraints:**

**`_check_pattern()`**
For GS1-128 rules, validates the regex has exactly 2 capture groups (AI + value). Raises `ValidationError` if pattern is invalid regex or wrong group count.

### `ir.http`

**`session_info()`**
Injects `gs1_group_separator_encodings` (the `gs1_separator_fnc1` value) into the session info when the company's nomenclature is a GS1 nomenclature. Used by the JS barcode scanner.

## What It Extends

- `barcode.nomenclature` — GS1-specific fields and parsing methods
- `barcode.rule` — GS1 encoding type and content type
- `ir.http.session_info` — GS1 separator config for frontend scanner

## Key Behavior

- GS1 barcodes use Application Identifiers (AIs) — fixed-length prefixes (2-4 digits) that encode meaning and format of the following data.
- Example: `(01)94012345678903(17)231200(10)LOT123` — GTIN + best-before date + lot number.
- The separator (FNC1) can be explicit (`\x1D`) or implied by fixed-length fields.
- Supports company-specific barcode nomenclature switching per-company.

## See Also

- [[Modules/Barcodes]] (`barcodes`) — base barcode module
- [[Modules/Stock]] — uses barcode scanning for inventory
