# Barcode GS1 Nomenclature

## Overview
- **Name**: Barcode - GS1 Nomenclature
- **Category**: Supply Chain/Inventory
- **Summary**: Parse barcodes according to GS1-128 specifications
- **Depends**: `barcodes`, `uom`
- **License**: LGPL-3

## Description

This module extends Odoo's barcode nomenclature system with full support for the **GS1-128 (EAN-128)** barcode standard. GS1 barcodes encode structured data using Application Identifiers (AIs) — variable-length codes that prefix data elements (e.g., batch number, expiration date, weight, GTIN).

The module is used in warehouse operations, inventory tracking, and product labeling workflows where GS1-compliant barcodes need to be scanned and decoded.

## Models

### `barcode.nomenclature` (Barcode Nomenclature)
Extends `barcode.nomenclature` with GS1-specific fields and methods.

**Additional Fields:**
- `is_gs1_nomenclature` — Boolean; marks this nomenclature as using GS1 specification. Only GS1-128 encoding rules are accepted in this mode.
- `gs1_separator_fnc1` — Char; regex pattern for the FNC1 separator delimiter (default: `r'(Alt029|#|\x1D)'`). Used to split barcode segments.

**Key Methods:**
- `gs1_date_to_date(gs1_date)` — Converts a GS1 6-character date (`yymmdd`) to a `datetime.date`. Handles century detection (GS1 spec 7.12 rules) and handles missing-day (defaults to last day of month).

- `parse_gs1_rule_pattern(match, rule)` — Parses a matched GS1 AI value according to `gs1_content_type`:
  - `measure` — Numeric with decimal (last digit of AI determines decimal position)
  - `identifier` — Numeric with check digit (GTIN, etc.)
  - `date` — 6-char GS1 date
  - `alpha` — Alphanumeric string

- `gs1_decompose_extended(barcode)` — Core decomposition engine. Strips GS1 mode identifiers (`]C1`, etc.), then iteratively matches GS1-128 rules using the configured FNC1 separator. Returns an ordered list of `{rule, type, ai, string_value, value}` dicts.

- `parse_nomenclature_barcode(barcode)` — Entry point. If `is_gs1_nomenclature` is True, delegates to `gs1_decompose_extended()`. Otherwise falls back to standard nomenclature parsing.

- `_preprocess_gs1_search_args(domain, barcode_types, field)` — Pre-processes Odoo search domains to handle GS1 barcode padding removal. Strips leading zeros from GTIN/barcode fields when searching using GS1-encoded values. Handles `in`, `not in`, `ilike`, `=`, `!=` operators.

### `barcode.rule` (Barcode Rule)
Extends `barcode.rule` with GS1-specific fields.

**Additional Fields:**
- `encoding` — Adds `gs1-128` to the selection (default for GS1 nomenclature rules).
- `gs1_content_type` — Selection: `date`, `measure`, `identifier`, `alpha`. Defines how the rule's captured value is parsed.
- `gs1_decimal_usage` — Boolean; if True, the last digit of the AI determines the decimal position for measure values.
- `associated_uom_id` — UoM linked to the rule (for quantity/weight rules).

**Additional Barcode Types (GS1-specific):**
`quantity`, `location`, `location_dest`, `lot`, `package`, `use_date`, `expiration_date`, `package_type`, `pack_date`

**Constraints:**
- `_check_pattern()` — Validates that GS1-128 rule patterns are valid regex with exactly 2 capture groups (AI and value).

## GS1 Application Identifiers Supported
The module ships with standard GS1 rules in `data/barcodes_gs1_rules.xml`, covering common AIs such as:
- `(01)` GTIN — Global Trade Item Number
- `(10)` Batch/Lot Number
- `(17)` Expiration Date
- `(21)` Serial Number
- `(30)` Variable Count
- `(37)` Number of units contained
- `(310n)` Net weight (kg)
- And many more

## Related
- [Modules/barcodes](odoo-18/Modules/barcodes.md) — Base barcode nomenclature framework
