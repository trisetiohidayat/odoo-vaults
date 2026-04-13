---
Module: spreadsheet + spreadsheet_dashboard
Version: Odoo 18
Type: Core
Tags: #odoo, #odoo18, #spreadsheet, #dashboard
---

# Spreadsheet Engine

**Addons:** `spreadsheet` (base engine), `spreadsheet_dashboard` (dashboard wrapper)
**Source:** `~/odoo/odoo18/odoo/addons/spreadsheet/`, `~/odoo/odoo18/odoo/addons/spreadsheet_dashboard/`
**Depends:** `spreadsheet` → `bus`, `web`, `portal` | `spreadsheet_dashboard` → `spreadsheet`, `spreadsheet`

## Overview

Odoo 18's spreadsheet engine is a **client-side JavaScript spreadsheet** (`o_spreadsheet`) that stores workbook data as **JSON in a Binary field**. There are no `spreadsheet.document`, `spreadsheet.sheet`, `spreadsheet.cell.error`, or `spreadsheet.revision` ORM models — those concepts are entirely handled in the JavaScript client.

The Python side provides:
1. **`spreadsheet.mixin`** — Abstract mixin that adds JSON/Binary storage to any model
2. **`spreadsheet.dashboard`** — Concrete model inheriting the mixin (dashboard with spreadsheet UI)
3. **`spreadsheet.dashboard.group`** — Grouping for dashboard menus
4. **`spreadsheet.dashboard.share`** — Public sharing copy of a dashboard
5. **`res.currency`** and **`res.lang`** extensions for spreadsheet locale support

---

## Data Architecture

### Storage Model (L4)

Spreadsheet data is stored as **JSON in a Binary field**, not as individual ORM records:

```
spreadsheet_binary_data (Binary)
  ↕ (inverse)
spreadsheet_data (Text)
  ↕ (decoded)
Full JSON workbook object
```

The JSON is stored as `ir.attachment` records linked to the model via `res_model`/`res_field`/`res_id`. This architecture:
- Allows large JSON blobs (up to the Binary field limit)
- Enables efficient streaming for export
- Shares storage infrastructure with the attachment system

### JSON Workbook Structure

```python
{
    "version": 1,
    "sheets": [
        {
            "id": "sheet1",
            "name": "Sheet1"
        }
    ],
    "settings": {
        "locale": "en_US"
    },
    "revisionId": "START_REVISION"
}
```

Inside the client-side `o_spreadsheet` engine, this JSON is parsed into an in-memory model with:
- **Cells:** stored as a `ZoneDate` mapping, not individual records
- **Sheets:** managed as an array in the JSON, not as ORM rows
- **Revisions:** tracked client-side; server stores only the current snapshot

---

## `spreadsheet.mixin` (Abstract)

**File:** `spreadsheet/models/spreadsheet_mixin.py`

Abstract mixin (`_auto = False`, no table created). Inherited by `spreadsheet.dashboard` and `spreadsheet.dashboard.share`.

```python
class SpreadsheetMixin(models.AbstractModel):
    _name = "spreadsheet.mixin"
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `spreadsheet_binary_data` | Binary | Raw JSON/xlsx data (stored as ir.attachment) |
| `spreadsheet_data` | Text | Decoded JSON text (compute inverse pair) |
| `spreadsheet_file_name` | Char | Suggested download name (computed: `{display_name}.osheet.json`) |
| `thumbnail` | Binary | Preview thumbnail image |

### Compute: `spreadsheet_data` / `_inverse_spreadsheet_data`

```python
@api.depends("spreadsheet_binary_data")
def _compute_spreadsheet_data(self):
    # Searches ir.attachment for raw data matching (res_model, res_field, res_id)
    # Returns decoded UTF-8 text

def _inverse_spreadsheet_data(self):
    # Encodes text as base64 → stores in spreadsheet_binary_data
    # If data is empty → clears binary field
```

### Validation: `_check_spreadsheet_data`

```python
@api.constrains("spreadsheet_binary_data")
def _check_spreadsheet_data(self):
    # 1. Decodes and parses JSON
    # 2. If not in test mode: skips deep validation
    # 3. Extracts all Odoo model references via fields_in_spreadsheet()
    # 4. Validates each model exists in registry
    # 5. For each field chain (e.g., product_id.channel_ids):
    #    - Validates each field exists on the model
    #    - Follows relational fields to validate full chain
    # 6. Validates menu XML IDs referenced in spreadsheet exist and have actions
    # 7. Raises ValidationError with full error list if any check fails
```

**L4 Note:** Field validation only runs in test mode (`tools.config['test_enable']` or `tools.config['test_file']`). In production, invalid field references silently fail — the client handles formula errors.

### Empty Spreadsheet Template

```python
def _empty_spreadsheet_data_base64(self):
    data = json.dumps(self._empty_spreadsheet_data())
    return base64.b64encode(data.encode())

def _empty_spreadsheet_data(self):
    return {
        "version": 1,
        "sheets": [{"id": "sheet1", "name": _("Sheet1")}],
        "settings": {"locale": locale},
        "revisionId": "START_REVISION",
    }
```

### Export: `_zip_xslx_files()`

```python
def _zip_xslx_files(self, files):
    # files: list of {path, content} or {path, imageSrc}
    # If imageSrc is a data: URL → base64 decodes content
    # If imageSrc is /web/image/{id} → fetches ir.attachment binary
    # Creates ZIP archive in memory, returns bytes
```

---

## `spreadsheet.dashboard`

**File:** `spreadsheet_dashboard/models/spreadsheet_dashboard.py`

```python
class SpreadsheetDashboard(models.Model):
    _name = 'spreadsheet.dashboard'
    _inherit = "spreadsheet.mixin"
    _order = 'sequence'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Dashboard name (required, translateable) |
| `dashboard_group_id` | Many2one(`spreadsheet.dashboard.group`) | Parent group (required) |
| `sequence` | Integer | Display order within group |
| `sample_dashboard_file_path` | Char | Path to sample JSON file (e.g., `spreadsheet_dashboard_account/data/partner_followup_report.json`) |
| `is_published` | Boolean | Visible to all users with group access (default True) |
| `company_id` | Many2one(`res.company`) | Company filter |
| `group_ids` | Many2many(`res.groups`) | Allowed groups (default: `base.group_user`) |
| `main_data_model_ids` | Many2many(`ir.model`) | Models used to detect "empty" state |

### `get_readonly_dashboard()`

```python
def get_readonly_dashboard(self):
    snapshot = json.loads(self.spreadsheet_data)
    if self._dashboard_is_empty() and self.sample_dashboard_file_path:
        sample_data = self._get_sample_dashboard()
        return {"snapshot": sample_data, "is_sample": True}
    snapshot.setdefault('settings', {})['locale'] = user_locale
    return {
        'snapshot': snapshot,
        'revisions': [],
        'default_currency': default_currency,
    }
```

- If dashboard has no real data (`_dashboard_is_empty()`) and a sample file exists → load sample
- Otherwise → return current JSON snapshot with user locale merged in
- `revisions: []` — revision history not stored server-side in this model

### Sample Dashboard Detection

```python
def _dashboard_is_empty(self):
    # Returns True if all models in main_data_model_ids have zero records
    # Used to decide whether to show sample data instead of blank dashboard

def _get_sample_dashboard(self):
    # Opens sample JSON file via file_open()
    # Returns parsed JSON or None if file missing
```

---

## `spreadsheet.dashboard.group`

**File:** `spreadsheet_dashboard/models/spreadsheet_dashboard_group.py`

```python
class SpreadsheetDashboardGroup(models.Model):
    _name = 'spreadsheet.dashboard.group'
    _order = 'sequence'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Group name (required, translateable) |
| `dashboard_ids` | One2many | All dashboards in this group |
| `published_dashboard_ids` | One2many | Filtered to `is_published = True` |
| `sequence` | Integer | Display order |

### Unlink Protection

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_spreadsheet_data(self):
    # Prevents deletion of non-exported groups (those with a module external ID)
    # Allows deletion of user-created (__export__) groups
```

---

## `spreadsheet.dashboard.share`

**File:** `spreadsheet_dashboard/models/spreadsheet_dashboard_share.py`

A **frozen copy** of a shared dashboard. Created when a user generates a public share link.

```python
class SpreadsheetDashboardShare(models.Model):
    _name = 'spreadsheet.dashboard.share'
    _inherit = 'spreadsheet.mixin'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `dashboard_id` | Many2one | Original dashboard |
| `excel_export` | Binary | Pre-generated Excel export file |
| `access_token` | Char | Cryptographically secure unique token |
| `full_url` | Char | Computed public share URL |
| `name` | Char | Related from dashboard_id.name |

### Share URL Generation

```python
@api.model
def action_get_share_url(self, vals):
    # Creates dashboard share record
    # If excel_files in vals → generates ZIP export before saving
    # Returns full_url

def _zip_xslx_files(vals["excel_files"]):
    # Creates ZIP of Excel files for download
```

### Token Validation

```python
def _check_dashboard_access(self, access_token):
    # Validates: token matches AND user has read access to dashboard
    # Raises Forbidden() if either check fails
```

---

## `res.currency` Extension

**File:** `spreadsheet/models/res_currency.py`

```python
class ResCurrency(models.Model):
    _inherit = 'res.currency'
```

Added method for spreadsheet integration:

```python
def get_company_currency_for_spreadsheet(self):
    # Returns the company's main currency record
    # Used to set default_currency in dashboard snapshot
```

---

## `res.lang` Extension

**File:** `spreadsheet/models/res_lang.py`

```python
class Lang(models.Model):
    _inherit = 'res.lang'
```

### Locale Conversion

```python
def _odoo_lang_to_spreadsheet_locale(self):
    # Maps Odoo lang code (e.g., fr_FR) to spreadsheet locale identifier
    # Used when creating new spreadsheets

def _get_user_spreadsheet_locale(self):
    # Returns locale from current user's language setting
    # Used when rendering dashboard snapshot for a specific user
```

---

## Formula Language and Odoo-Specific Functions

**Note:** Formula evaluation is entirely **client-side** in the `o_spreadsheet` JavaScript engine. The Python ORM has no formula evaluation logic.

### Odoo-Specific Functions (JS)

These functions are defined in the JavaScript `odoo_functions_helpers.js` and execute within the spreadsheet's client-side evaluation context:

```
=odooRecordCount(model, domain)        → search_count
=odooRecord(model, id, field)          → read one field
=odooSearch(model, domain, field)      → search_read first record
=odooSum(model, domain, field)         → sum aggregated field
=PIVOT(model, row_dim, col_dim, measure, field)  → pivot aggregation
```

### How Odoo Data Flows into Spreadsheets

1. User inserts an Odoo function in a cell (e.g., `=odooRecordCount("project.task", ["state", "=", "done"]("state",-"=",-"done".md))`)
2. JavaScript evaluates the function using Odoo's RPC `call` mechanism
3. The RPC call hits a controller (not a model method) that queries the ORM
4. The result is cached in the spreadsheet model
5. When the spreadsheet saves, the formula + last cached value are stored in the JSON

**L4 Note:** The `_check_spreadsheet_data` Python validation only checks that the **model exists** — it does NOT validate domains, field accessibility, or record-level permissions. Access control is enforced at RPC call time.

---

## External Data Sources

### Pivot Table Integration

Spreadsheets can embed **pivot tables** that query Odoo models. The pivot data is:
1. Fetched via `spreadsheet/pivot/check` and `spreadsheet/pivot/read` controllers
2. Serialized into the spreadsheet JSON as figure data
3. Re-evaluated on refresh

### Graph View Integration

`spreadsheet/static/src/views/graph/` and `spreadsheet/static/src/views/pivot/` are bundled separately (`web.assets_backend_lazy`) to allow lazy loading on dashboards.

---

## Revision System

The `revisionId` in the JSON tracks the current revision. **Server-side**, revisions are **not stored** as records — only the latest snapshot is persisted in `spreadsheet_binary_data`.

Client-side, the `o_spreadsheet` engine maintains a revision history:
- Each user action creates a revision (client-side delta)
- Revisions are sent to the server via `spreadsheet.cell/update` controller
- The server only stores the latest merged snapshot

**L4 Note:** `spreadsheet.revision` does not exist as an ORM model. `get_readonly_dashboard()` returns `'revisions': []` because revision history is not persisted server-side in the base module.

---

## Key Differences from Excel

| Aspect | Odoo Spreadsheet | Excel |
|--------|-----------------|-------|
| Storage | JSON in Binary field | `.xlsx` file |
| Sheets | JSON array in workbook | OOXML worksheets |
| Formulas | Client-side JS engine | VBA/com server |
| Odoo integration | Native via `odooRecord*` functions | Via COM/OLE |
| Revision history | Client-side only | VBA or VSS |
| Cell errors | Client-side computed `#ERROR` etc. | Static error values |

### `spreadsheet.cell.error` Concept

`spreadsheet.cell.error` does **not exist as an ORM model**. In the `o_spreadsheet` client engine, cell errors are represented as **string constants** in the JSON cell values (e.g., `#ERROR: Division by zero`). The `CellError` concept is purely a client-side JavaScript class.

---

## See Also

- [Modules/Account](account.md) — `spreadsheet_dashboard_account` for accounting-specific dashboards
- [Core/API](API.md) — `@api.constrains` used in `_check_spreadsheet_data`
- [Web](web.md) — `o_spreadsheet` JavaScript engine architecture
