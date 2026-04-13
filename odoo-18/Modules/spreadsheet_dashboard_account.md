---
Module: spreadsheet_dashboard_account
Version: 18.0
Type: addon
Tags: #spreadsheet, #dashboard, #account, #finance
---

# spreadsheet_dashboard_account — Accounting Spreadsheet Dashboard

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `account`
**License:** LGPL-3
**Installable:** True
**Auto-install:** True

Provides a pre-configured spreadsheet dashboard for the Accounting module. Adds an "Invoicing" dashboard with invoice-related data (journal entries, account moves) to the spreadsheet dashboard group. Automatically installs when `account` is present.

## Data Files

- `data/dashboards.xml` — Dashboard record definitions
- `data/files/invoicing_dashboard.json` — Pre-built spreadsheet JSON (base64 binary)
- `data/files/invoicing_sample_dashboard.json` — Sample dashboard JSON for "Try Sample" feature

## Static Assets

None — pure data/seed module.

## Models

No Python model files — pure data/seed module that registers `spreadsheet.dashboard` records.

---

## Data

### Dashboard: `dashboard_invoicing`

**File:** `data/dashboards.xml`

| Property | Value |
|----------|-------|
| `spreadsheet.dashboard.name` | `Invoicing` |
| `dashboard_file` | `spreadsheet_dashboard_account/data/files/invoicing_dashboard.json` (base64 binary) |
| `data` | Invoicing spreadsheet JSON |
| `dashboard_group_id` | `spreadsheet_dashboard.spreadsheet_dashboard_group_finance` (Finance) |
| `main_data_model_ids` | `[account.move]` |
| `group_ids` | `account.group_account_readonly`, `account.group_account_invoice` (read-only for both) |
| `sequence` | `20` |
| `published` | `True` |

### Sample Dashboard

`data/files/invoicing_sample_dashboard.json` enables the "Try Sample" button in the spreadsheet UI, allowing users to preview the dashboard before installing.

---

## Security

No dedicated security XML. Relies on:
- `spreadsheet_dashboard` group restrictions (`group_ids` on the dashboard record)
- `account` module group restrictions (`group_account_readonly`, `group_account_invoice`)

Users must be members of at least one of the specified account groups to access this dashboard.

---

## What It Extends

- `spreadsheet.dashboard` — registers the `dashboard_invoicing` record
- `spreadsheet.dashboard.group` — uses `spreadsheet_dashboard_group_finance` group

---

## Key Behavior

- **Pure data/seed module** — no Python models. Registers a `spreadsheet.dashboard` record with pre-built spreadsheet JSON data.
- `main_data_model_ids = [account.move]` — the spreadsheet's main data source is journal entries/account moves.
- The `data` field contains the full spreadsheet JSON including Odoo spreadsheet formula references to `account.move`.
- Automatically installed when `account` is installed (via `auto_install: ['account']`).
- Sample dashboard file (`invoicing_sample_dashboard.json`) is separate from the main dashboard data and is used only for preview.
- The dashboard is visible under the Finance dashboard group in the spreadsheet sidebar.
- Access is read-only (`read_group_ids` implied by no write permissions on the record for those groups).
- Category: `Hidden` — not shown in the apps list.
- v17 to v18: No significant changes.

---

## See Also

- [Modules/Spreadsheet Dashboard](Modules/Spreadsheet-Dashboard.md) (`spreadsheet_dashboard`) — dashboard framework
- [Modules/Spreadsheet Account](Modules/Spreadsheet-Account.md) (`spreadsheet_account`) — accounting formula functions
- [Modules/Account](odoo-18/Modules/account.md) (`account`) — accounting data source
