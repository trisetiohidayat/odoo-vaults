---
tags: [odoo, odoo17, module, spreadsheet]
---

# Spreadsheet Module

**Source:** `addons/spreadsheet/models/`

## Overview

Odoo 17 includes a built-in collaborative spreadsheet engine, based on O-spreadsheet (Odoo's JavaScript library). Spreadsheets can be created standalone, embedded in dashboards, or used for financial reporting.

## Key Models

| Model | File | Description |
|-------|------|-------------|
| `spreadsheet.spreadsheet` | `spreadsheet.py` | Spreadsheet documents |
| `spreadsheet.spreadsheet.share` | `spreadsheet.py` | Shared spreadsheet links |
| `spreadsheet.mixin` | `spreadsheet_mixin.py` | Mixin for embedding spreadsheets in models |
| `res.currency` | `res_currency.py` | Currency data for spreadsheet formulas |
| `res.currency.rate` | `res_currency_rate.py` | Historical exchange rates |
| `res.lang` | `res_lang.py` | Languages for number formatting |

## spreadsheet.spreadsheet

### Key Fields

- `name` — Spreadsheet name
- `spreadsheet_data` — JSON blob containing cell data, format, and metadata
- `favorite_user_ids` — Users who have favorited the spreadsheet
- `owner_id` — `res.users` who created the spreadsheet
- `is_published` — Public visibility flag
- `download_access_mode` — `view` / `download` / `edit`

### Key Methods

- `_get_spreadsheet_available_colors` — Returns predefined color palette
- `action_view_spreadsheet` — Open spreadsheet in full-screen editor
- `_extract_spreadsheet_template_fields` — Extracts template data from spreadsheet

## spreadsheet.share

Manages share links for spreadsheets.

### Key Fields

- `spreadsheet_id` — The shared spreadsheet
- `full_url` — Public share URL
- `access_token` — Token for access control
- `access_mode` — `edit` / `read` (view-only)
- `date_open` — When the link was first accessed
- `access_count` — Number of accesses

## spreadsheet.mixin

Mixins a spreadsheet data field into any model, enabling embedded spreadsheets.

```python
class MyModel(models.Model):
    _inherit = 'spreadsheet.mixin'
    # Adds spreadsheet_snapshot field automatically
```

## Dashboard Spreadsheets

Sub-modules provide pre-built spreadsheet templates:
- `spreadsheet_account` — Financial reporting
- `spreadsheet_dashboard_account` — Account dashboard
- `spreadsheet_dashboard_purchase` — Purchase dashboard
- `spreadsheet_dashboard_sale` — Sales dashboard
- `spreadsheet_dashboard_stock_account` — Stock valuation dashboard
- `spreadsheet_dashboard_pos_hr` — POS HR dashboard

## See Also

- [Modules/account](modules/account.md) — Financial reports in spreadsheets
- [Modules/dashboard](modules/dashboard.md) — Dashboard integration
