# Barcodes Module (Odoo 18)

## Overview

The Barcodes module provides barcode scanning, parsing, and nomenclature management. It supports standard barcodes (EAN-13, UPC-A, GS1-128) and custom barcode rules.

**Module Path:** `barcodes/`
**Key Models:** `barcodes.barcode_events_mixin`, `barcode.nomenclature`, `barcode.rule`
**Dependencies:** None (standalone)
**Extension Modules:** `barcodes_gs1_nomenclature` (extends nomenclature with GS1 support)

---

## Architecture

```
barcode.nomenclature
    └── barcode.rule  (One2many, ordered by sequence)

barcodes.barcode_events_mixin (abstract mixin)
    └── any model using barcode scanning

product.product (barcodes extension)
    └── barcode field (standard product.barcode)

stock.lot (barcodes_gs1 extension)
    └── barcode field

stock.quant (barcodes_gs1 extension)
    └── barcode lookup by scanned barcode
```

---

## barcode.nomenclature

Defines the barcode encoding rules and parsing logic for a set of barcodes.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Nomenclature name |
| `rule_ids` | One2many | Barcode rules (ordered by sequence) |
| `upc_ean_conv` | Selection | UPC/EAN conversion rule |

### UPC/EAN Conversion Options

| Option | Description |
|--------|-------------|
| `never` | Never convert |
| `ean2upc` | EAN-13 to UPC-A automatically |
| `upc2ean` | UPC-A to EAN-13 automatically |
| `always` | Always convert both ways |

### Key Methods

#### `sanitize_ean(ean)`
Returns a valid zero-padded EAN-13 from an EAN prefix.

```python
def sanitize_ean(self, ean):
    ean = ean[0:13].zfill(13)
    return ean[0:-1] + str(get_barcode_check_digit(ean))
```

#### `sanitize_upc(upc)`
Returns a valid zero-padded UPC-A from a UPC-A prefix.

#### `match_pattern(barcode, pattern)`
Checks if a barcode matches a regex pattern and extracts encoded values.

Pattern syntax:
- `{N}` - Single digit
- `{NN}` - Two digits
- `{ND}` - Digit with 1 decimal place
- `{NND}` - Two digits whole + 1 decimal
- `.` - Match any character
- `{pattern}D` - Decimal digits

```python
def match_pattern(self, barcode, pattern):
    # Returns dict with:
    # - match: boolean
    # - value: extracted numeric value
    # - base_code: barcode with numerics replaced by 0s
```

Example pattern: `20{NNNNND}0` matches:
- Fixed "20" prefix
- 6 digits of weight
- Fixed "0" suffix
- Extraction: `{NNNNND}` -> 6-digit weight value

#### `parse_barcode(barcode)`
Entry point for barcode parsing. Routes to appropriate parser.

```python
def parse_barcode(self, barcode):
    if re.match(r'^urn:', barcode):
        return self.parse_uri(barcode)  # GS1 URN format
    return self.parse_nomenclature_barcode(barcode)
```

#### `parse_nomenclature_barcode(barcode)`
Attempts to interpret a barcode against all rules in priority order.

```python
def parse_nomenclature_barcode(self, barcode):
    # For each rule (in sequence order):
    # 1. Check encoding compatibility
    # 2. Check UPC/EAN conversion if needed
    # 3. Match pattern
    # 4. If alias: replace barcode with alias value and re-parse
    # 5. If match: return parsed result with type, value, base_code
    # Returns dict: {encoding, type, code, base_code, value}
```

#### `parse_uri(barcode)`
Parses GS1 URN formats for RFID/tracking.

Supported URNs:
- `urn:lgtin:...` - GTIN lot number
- `urn:sgtin:...` / `urn:sgtin-96:...` / `urn:sgtin-198:...` - Serial GTIN
- `urn:sscc:...` / `urn:sscc-96:...` - SSCC package code

#### GS1 URI Parsing

```python
def _convert_uri_gtin_data_into_tracking_number(self, base_code, data):
    # Parses: urn:sgtin:companyPrefix.itemRef.serial
    # Returns: [{type: 'product', ...}, {type: 'lot', ...}]

def _convert_uri_sscc_data_into_package(self, base_code, data):
    # Parses: urn:sscc:companyPrefix.serialRef
    # Returns: [{type: 'package', ...}]
```

### Return Structure

```python
{
    'encoding': 'ean13',     # or 'upca', 'any', etc.
    'type': 'product',       # rule type (product, lot, package, alias, error)
    'code': '5901234123457', # original barcode
    'base_code': '5901234000002', # with encoded value zeroed out
    'value': 12345.0,        # extracted numeric value (if any)
}
```

---

## barcode.rule

Defines a single matching rule within a nomenclature.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Rule name |
| `barcode_nomenclature_id` | Many2one | Parent nomenclature |
| `sequence` | Integer | Priority order (lower = checked first) |
| `encoding` | Selection | Required barcode encoding |
| `type` | Selection | Rule type |
| `pattern` | Char | Regex pattern to match |
| `alias` | Char | Replacement barcode if type=`alias` |

### Encoding Options

| Value | Description |
|-------|-------------|
| `any` | Any encoding |
| `ean13` | EAN-13 (13 digits) |
| `ean8` | EAN-8 (8 digits) |
| `upca` | UPC-A (12 digits) |

### Rule Types

| Type | Description |
|------|-------------|
| `alias` | Matched barcode is replaced by alias value and re-parsed |
| `product` | Product lookup (standard retail) |

### Pattern Syntax

Patterns are regular expressions with special placeholders:

| Placeholder | Matches |
|-------------|---------|
| `.` | Any single character |
| `{N}` | Single digit |
| `{ND}` | Single digit with 1 decimal |
| `{NN}` | Two digits |
| `{NND}` | Two digits with 1 decimal |
| `{NNNNND}` | Six digits with 1 decimal |
| `*` | NOT VALID (escape as `.*`) |

Examples:
- `.*` - Match anything (catchall, use with caution)
- `5901234{NNNNND}` - Internal reference 7 digits + 6-digit weight
- `20{NNNND}0` - Variable weight item (4 digits + 1 decimal)
- `01{NNNNNNNNNNNNND}21{NNNNNNNN}` - GS1 batch/lot AI (01=GTIN, 21=serial)

### Pattern Validation

```python
@api.constrains('pattern')
def _check_pattern(self):
    # Ensures exactly one {N*D*} placeholder for value extraction
    # Validates regex compilation
    # Rejects bare '*' as pattern (must use '.*')
```

---

## barcodes.barcode_events_mixin

Abstract mixin for models that respond to barcode scans in form views.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `_barcode_scanned` | Char | Holds last scanned barcode value (not stored) |

### How It Works

The mixin works with the `barcode_handler` widget in form views:

```xml
<field name="_barcode_scanned" widget="barcode_handler"/>
```

When a barcode is scanned:
1. The widget sets `_barcode_scanned` to the scanned value
2. The `@api.onchange` on `_barcode_scanned` is triggered
3. `on_barcode_scanned()` is called with the barcode value
4. `_barcode_scanned` is cleared immediately

### Key Methods

#### `_on_barcode_scanned()`
Internal onchange handler. Clears the field and calls `on_barcode_scanned()`.

```python
@api.onchange('_barcode_scanned')
def _on_barcode_scanned(self):
    barcode = self._barcode_scanned
    if barcode:
        self._barcode_scanned = ""
        return self.on_barcode_scanned(barcode)
```

#### `on_barcode_scanned(barcode)`
**Must be implemented** by the using model.

```python
def on_barcode_scanned(self, barcode):
    # Handle the scanned barcode
    # Return: dict with notification or False
    raise NotImplementedError()
```

---

## GS1 Barcode Processing (barcodes_gs1_nomenclature)

Extends `barcode.nomenclature` with full GS1 AI (Application Identifier) support.

### GS1 Application Identifiers

| AI | Name | Format | Description |
|----|------|--------|-------------|
| `01` | GTIN | N14 | Global Trade Item Number |
| `10` | Batch/Lot | X20 | Batch or lot number |
| `11` | Production Date | N6 | Production date (YYMMDD) |
| `13` | Packaging Date | N6 | Packaging date |
| `15` | Best Before | N6 | Best before date |
| `17` | Expiry Date | N6 | Expiry date |
| `21` | Serial Number | X20 | Serial number |
| `30` | Var. Count | N..8 | Variable count |
| `37` | Count | N..8 | Trade item count |
| `310{n}` | Net Weight (kg) | N6+n | Weight in kg |
| `320{n}` | Net Weight (lb) | N6+n | Weight in pounds |

### GS1 Date Format

GS1 dates are 6-digit strings (YYMMDD):
- `210331` = March 31, 2021
- `211230` = December 30, 2021
- `99000` = Last day of September 2021 (day=00 means last day)

### GS1 Barcode Structure

```
]C1 01 00012345678902 10 ABC123 21 4567890123
]C1   AI   GTIN           AI   Batch    AI Serial
```

- `]C1` - GS1-128 symbology identifier
- Group separator (`\x1D`) separates AIs

### gs1_parse_barcode()

The GS1 nomenclature adds this method to parse GS1 barcodes:

```python
def gs1_parse_barcode(self, barcode):
    # Parses GS1 AI into dict:
    # {
    #     '01': '00012345678902',  # GTIN
    #     '10': 'ABC123',          # Batch
    #     '21': '4567890123',      # Serial
    #     '3100': '1.5',           # Weight in kg (two implied decimals)
    # }
    # Handles FNC1 delimiters
    # Respects GS1 separator function
```

---

## Stock Integration

### product.product

Extended by `stock_barcode` and `barcodes` modules:
- `barcode` field stores the product's standard barcode
- Lookup: scanned barcode matches this field

### stock.lot (barcodes_gs1 Extension)

- `barcode` field for lot-level GS1 identification
- Supports `urn:sgtin:...` format for serialized lots

### stock.quant (barcodes_gs1 Extension)

- `barcode` field on quant for package-level scanning
- Supports `urn:sscc:...` format for logistic units

### Barcode Scan Flow

```
1. User scans barcode in stock picking form
2. barcode_handler widget triggers _on_barcode_scanned
3. on_barcode_scanned() identifies barcode type:
   - Product barcode -> find product.product by barcode
   - Lot barcode -> find stock.lot by barcode
   - SSCC barcode -> find stock.quant.package by SSCC
   - GS1 barcode -> parse AIs, find product + lot + serial
4. Action depends on model:
   - Product: add to move lines or update quantities
   - Lot: assign lot to move line
   - Package: assign package to picking
```

---

## Check Digit Validation

The `get_barcode_check_digit()` utility validates and generates check digits:

```python
from odoo.tools.barcode import get_barcode_check_digit

# EAN-13: multiply alternating positions by 1 and 3, sum must be divisible by 10
# UPC-A: similar but starts with multiplier 3
# Check digit is the amount needed to reach next multiple of 10
```

The `check_barcode_encoding()` utility checks if a barcode matches a specific encoding:

```python
def check_barcode_encoding(barcode, encoding):
    # Returns True if barcode matches encoding:
    # - 'ean13': exactly 13 digits
    # - 'ean8': exactly 8 digits
    # - 'upca': exactly 12 digits
```
