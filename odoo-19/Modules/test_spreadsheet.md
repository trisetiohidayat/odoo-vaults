---
type: module
module: test_spreadsheet
tags: [odoo, odoo19, test, spreadsheet, o-spreadsheet, pivot, data-source]
created: 2026-04-06
---

# Test Spreadsheet

## Overview

| Property | Value |
|----------|-------|
| **Name** | Test Spreadsheet |
| **Technical** | `test_spreadsheet` |
| **Category** | Hidden (Test Module) |
| **Depends** | `spreadsheet` |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |

## Description

Test module for the `spreadsheet` app. Provides test data and models for testing spreadsheet-related functionality including o-spreadsheet formulas, pivot tables, data sources, and the `spreadsheet.mixin` behavior.

This module is **test-only** and is not installed in production databases. All tests live in the `tests/` directory and are run as part of the `spreadsheet` module's test suite.

## Module Structure

```
test_spreadsheet/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── spreadsheet_mixin_test.py   # Test model with spreadsheet.mixin
└── tests/
    ├── __init__.py
    └── test_spreadsheet.py          # Unit tests
```

## Models

### `spreadsheet.test`

A minimal test model that inherits from `spreadsheet.mixin`. Used to test the mixin's behavior in isolation, without coupling to any real business model.

**File:** `models/spreadsheet_mixin_test.py`

```python
class SpreadsheetTest(models.Model):
    """ A very simple model only inheriting from spreadsheet.mixin to test
    its model functioning."""
    _description = 'Dummy Spreadsheet'
    _name = 'spreadsheet.test'
    _inherit = ['spreadsheet.mixin']
```

**Design Notes:**

- The model has no custom fields — it inherits everything from `spreadsheet.mixin`
- `spreadsheet.mixin` provides:
  - `spreadsheet_binary_data` — stores the spreadsheet file as base64-encoded binary
  - `spreadsheet_data` — stores the spreadsheet as a plain JSON text field
  - `spreadsheet_file_name` — computed display name for export
  - `spreadsheet_revision_ids` — revision tracking for collaborative editing
  - `_check_json_data()` — `ValidationError` constraint if JSON is invalid
  - `_compute_spreadsheet_file_name()` — generates `"{display_name}.osheet.json"`
  - ORM overrides for `create`, `write`, `read` to handle binary data

### `spreadsheet.mixin`

The mixin being tested, provided by the `spreadsheet` module. Key behaviors:

| Feature | Behavior |
|---------|----------|
| Data storage | `spreadsheet_binary_data` (binary) or `spreadsheet_data` (JSON text) |
| JSON validation | `_check_json_data()` constrains binary data to valid JSON |
| File export | `spreadsheet_file_name` returns `{name}.osheet.json` |
| Revisions | `spreadsheet_revision_ids` tracks collaborative edit history |
| Display name | Inherits from `_rec_name` or `display_name` |

## Tests

**File:** `tests/test_spreadsheet.py`

### Test Cases

#### `test_onchange_json_data`

Tests that the mixin's `ValidationError` constraint correctly rejects invalid JSON in the spreadsheet binary data field.

```python
def test_onchange_json_data(self):
    spreadsheet_form = Form(self.env["spreadsheet.test"])

    # Valid JSON — assignment succeeds
    spreadsheet_form.spreadsheet_binary_data = base64.b64encode(
        json.dumps({'key': 'value'}).encode('utf-8')
    )

    # Invalid JSON — raises ValidationError
    with self.assertRaises(ValidationError, msg='Invalid JSON Data'):
        spreadsheet_form.spreadsheet_binary_data = base64.b64encode(
            'invalid json'.encode('utf-8')
        )
```

**Assertions verified:**
- Valid JSON (dictionary, list, string) is accepted
- Invalid JSON (plain text, truncated data, malformed) triggers `ValidationError`
- The constraint is enforced both in `create()` and `write()` (via Form)
- Error message: `'Invalid JSON Data'`

#### `test_spreadsheet_pivot`

Tests that a complete spreadsheet data structure including pivot definitions can be created and stored.

```python
def test_spreadsheet_pivot(self):
    data = {
        'sheets': [{'id': 'sheet1'}],
        'pivots': {
            '1': {
                'dataSet': {
                    'zone': {
                        'left': 6,
                        'right': 6,
                        'top': 5,
                        'bottom': 5
                    },
                    'sheetId': 'sheet1'
                },
                'columns': [],
                'rows': [],
                'measures': [],
                'name': 'New pivot',
                'type': 'SPREADSHEET',
                'formulaId': '1'
            }
        }
    }
    spreadsheet = self.env['spreadsheet.test'].create({
        'spreadsheet_data': json.dumps(data)
    })
    self.assertTrue(spreadsheet.exists())
```

**Assertions verified:**
- A `spreadsheet.test` record can be created with valid spreadsheet JSON
- The JSON is stored in `spreadsheet_data` as text
- Pivot definitions (with `dataSet`, `zone`, `columns`, `rows`, `measures`) are accepted
- `type: 'SPREADSHEET'` and `formulaId` fields are valid
- The record exists in the database after creation

#### `test_spreadsheet_file_name`

Tests that the computed `spreadsheet_file_name` field returns the expected export filename.

```python
def test_spreadsheet_file_name(self):
    spreadsheet = self.env['spreadsheet.test'].create({})
    self.assertEqual(
        spreadsheet.spreadsheet_file_name,
        f"{spreadsheet.display_name}.osheet.json"
    )
```

**Assertions verified:**
- `spreadsheet_file_name` is derived from `display_name` of the record
- The extension is always `.osheet.json` (o-spreadsheet format)
- Works even when `spreadsheet_data` is empty/None

## What Gets Tested

| Test Category | What Is Verified |
|--------------|-----------------|
| JSON validation | Invalid JSON raises `ValidationError` on `spreadsheet_binary_data` |
| JSON validation | Valid JSON structures (dict, list) are accepted |
| Pivot storage | Complete pivot definitions can be created and stored |
| Pivot structure | `dataSet.zone`, `type`, `formulaId` fields are valid |
| File name export | `spreadsheet_file_name` returns correct `.{name}.osheet.json` format |
| Record creation | Records can be created with empty or populated data |
| Record existence | `create()` properly inserts the record |

## o-Spreadsheet Architecture

The `spreadsheet` module uses **o-spreadsheet** (a JS spreadsheet engine similar to Excel/Google Sheets) for both:

1. **Standalone spreadsheets** — user-created documents stored via `spreadsheet.mixin`
2. **Embedded spreadsheets** — within reports, dashboards, and other Odoo views

### Data Model

```javascript
// Typical spreadsheet_data JSON structure
{
  "sheets": [
    { "id": "sheet1", "name": "Sheet 1" }
  ],
  "pivots": {
    "1": {
      "type": "SPREADSHEET",
      "dataSet": { "model": "sale.order", ... },
      "measures": ["amount_total:sum"],
      "rows": ["partner_id"],
      "columns": ["date_order:month"]
    }
  },
  "charts": { ... },
  "filters": [ ... ]
}
```

### Pivot Data Source

The pivot definition references an Odoo model and defines:
- `model` — the Odoo model to query (e.g., `sale.order`)
- `domain` — optional Odoo domain to filter records
- `measures` — aggregated fields (e.g., `amount_total:sum`, `id:count`)
- `rows` — group-by fields displayed as row headers
- `columns` — group-by fields displayed as column headers
- `zone` — the cell range in the spreadsheet where the pivot is rendered

The o-spreadsheet evaluates pivots by calling the `spreadsheet.pivot` model RPC method, which executes the aggregation via Odoo's ORM `read_group()`.

## Related

- [Modules/spreadsheet](spreadsheet.md) — o-spreadsheet engine and formula language
- [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md) — Dashboard with spreadsheet integration
- [Modules/spreadsheet_dashboard_pos_restaurant](spreadsheet_dashboard_pos_restaurant.md) — Restaurant KPI dashboard
