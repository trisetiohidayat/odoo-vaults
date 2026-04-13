---
Module: spreadsheet_dashboard
Version: 18.0
Type: addon
Tags: #spreadsheet, #dashboard, #readsheet, #productivity
---

# spreadsheet_dashboard — Spreadsheet Dashboard

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet`
**License:** LGPL-3
**Installable:** True

Provides the spreadsheet-based dashboard feature for Odoo. Extends the `spreadsheet` module with dashboard-specific views, sharing, and group-based access control. Dashboards are spreadsheet files linked to menu items, accessible from the Odoo backend. Also supports public and portal sharing with access tokens.

## Data Files

- `data/spreadsheet_dashboard_data.xml` — Default dashboard group definitions
- `security/ir.model.access.csv` — ACL for dashboard models

## Static Assets (web.assets_backend)

| Bundle | Path | Purpose |
|--------|------|---------|
| `spreadsheet_dashboard.spreadsheet_dashboard` | `src/**/*` | Full dashboard bundle |
| `spreadsheet_dashboard.spreadsheet_dashboard_assets` | `assets/**/*` | Dashboard-specific JS assets |
| `spreadsheet_dashboard.spreadsheet_dashboard_export` | `export/**/*` | Export functionality JS |
| `spreadsheet_dashboard.spreadsheet_dashboard_print` | `print_assets/**/*` | Print/export print styles |

## Models

### `spreadsheet.dashboard` (`spreadsheet_dashboard.models.spreadsheet_dashboard`)

**Inheritance:** `spreadsheet.spreadsheet.abstract` (abstract mixin), `mail.thread`, `mail.activity.mixin`

**Fields:**

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Dashboard name (required) |
| `dashboard_file` | Binary | No | `.xlsx` or spreadsheet data file upload |
| `data` | Json | Yes | Spreadsheet JSON snapshot (the actual spreadsheet data) |
| `group_ids` | Many2many `res.groups` | Yes | Access control — only these groups can access the dashboard |
| `sequence` | Integer | Yes | Order within the dashboard group |
| `dashboard_group_id` | Many2one `spreadsheet.dashboard.group` | Yes | Parent group/folder |
| `name_export` | Char | No | Filename for export (no store) |

**Methods:**

**`_normalize_spreadsheet_data()`** `@api.onchange('data')`
Normalizes spreadsheet JSON before saving. Called onchange to ensure data consistency.

**`action_export_xlsx()`**
Exports the dashboard as an `.xlsx` file. Returns a file download response.

**`get_users_access()`** `@api.model`
Returns list of user IDs who have access to this dashboard (union of `group_ids` members and admin).

---

### `spreadsheet.dashboard.group` (`spreadsheet_dashboard.models.spreadsheet_dashboard_group`)

**Inheritance:** `base`

**Fields:**

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Group/folder name |
| `sequence` | Integer | Yes | Order in the sidebar |
| `dashboard_ids` | One2many `spreadsheet.dashboard` | Yes | Child dashboards; `cascade` delete |

---

### `spreadsheet.dashboard.share` (`spreadsheet_dashboard.models.spreadsheet_dashboard_share`)

**Inheritance:** `spreadsheet.share.spreadsheet_share_abstract` (abstract mixin)

Extends the generic spreadsheet sharing model for dashboard-specific sharing.

**Fields:**

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `spreadsheet_dashboard_id` | Many2one `spreadsheet.dashboard` | Yes | Dashboard being shared |

**Methods:**

**`_check_date_validity()`**
Ensures the share link has not expired (checks `date_deadline`).

---

## Controllers

### `SpreadsheetDashboard` (`spreadsheet_dashboard.controllers.spreadsheet_dashboard`)

**Routes:**

| Route | Auth | Methods | Description |
|-------|------|---------|-------------|
| `/dashboard/list` | user | GET | Returns all dashboards accessible to the current user |
| `/dashboard/<int:dashboard_id>` | user | GET | Returns the dashboard data JSON |
| `/dashboard/create` | user | POST | Creates a new dashboard |
| `/dashboard/<int:dashboard_id>/copy` | user | POST | Duplicates a dashboard |
| `/dashboard/<int:dashboard_id>/unlink` | user | POST | Deletes a dashboard |

### `SpreadsheetDashboardShare` (`spreadsheet_dashboard.controllers.share`)

Extends `spreadsheet.SpreadsheetShare` for dashboard sharing with access tokens.

**Routes:**

| Route | Auth | Methods | Description |
|-------|------|---------|-------------|
| `/dashboard/share/<int:share_id>` | public | GET | Renders the shared dashboard via access token |
| `/dashboard/share/data/<int:share_id>` | public | GET | Returns dashboard JSON for the shared view |
| `/dashboard/share/export/<int:share_id>/<doc_type>` | public | GET | Exports shared dashboard as PDF/XLSX |

**`get_shared_dashboard(share)`**
Returns the dashboard data for a public share link.

---

## What It Extends

- `spreadsheet.spreadsheet.abstract` — spreadsheet data fields (data JSON, file)
- `spreadsheet.share.spreadsheet_share_abstract` — sharing with access tokens
- `mail.thread` — dashboard notifications and chatter
- `mail.activity.mixin` — activity tracking on dashboards

---

## Key Behavior

- Dashboards are spreadsheet files stored as JSON in the `data` Json field.
- Access control via `group_ids` — only users in allowed groups can see the dashboard in the menu and access it.
- Public sharing via `spreadsheet.dashboard.share` generates an access token URL that can be shared without authentication.
- The dashboard JSON contains the full spreadsheet state including cells, sheets, figures, and Odoo data source references.
- `_normalize_spreadsheet_data()` is called onchange to ensure data integrity before saving.
- Dashboard groups provide folder-like organization in the sidebar.
- The export functionality generates `.xlsx` files via `action_export_xlsx()`.
- v17 to v18: No significant architectural changes.

---

## See Also

- [Modules/Spreadsheet](Modules/Spreadsheet.md) (`spreadsheet`) — Base spreadsheet module
- [Modules/Spreadsheet Account](Modules/Spreadsheet-Account.md) (`spreadsheet_account`) — Accounting formula functions
- [Modules/Spreadsheet Dashboard Account](Modules/Spreadsheet-Dashboard-Account.md) (`spreadsheet_dashboard_account`) — Pre-built accounting dashboard
