---
type: module
module: spreadsheet_dashboard_account
tags: [odoo, odoo19, spreadsheet, dashboard, account, kpi, invoicing, financial_reports]
created: 2026-04-14
related_links:
  - "[Modules/spreadsheet_dashboard](spreadsheet_dashboard.md)"
  - "[Modules/spreadsheet_account](spreadsheet_account.md)"
  - "[Modules/Account](Account.md)"
---

# Spreadsheet Dashboard for Accounting

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `spreadsheet_dashboard_account` |
| **Category** | Productivity/Dashboard |
| **Depends** | `spreadsheet_dashboard`, `account` |
| **Auto-install** | `['account']` (auto-installs when account module is present) |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |

## Purpose

`spreadsheet_dashboard_account` provides a pre-configured, data-rich **spreadsheet dashboard** tailored for accounting and finance teams. It is a **data-only module**: it contains no Python models or business logic. Its sole contribution is a `spreadsheet.dashboard` record (with ID `dashboard_invoicing`) whose binary data contains a fully-structured Odoo Spreadsheet document with live formulas that pull financial data directly from `account.move` and `account.move.line`.

The dashboard is immediately usable after installation -- finance teams see a spreadsheet-style view of their invoicing KPIs without needing to build reports from scratch.

## Module Type: Data-Only

This module follows the **data-only pattern** in Odoo. Key characteristics:

- **No Python models**: No `models/` directory, no custom business logic.
- **One data file**: `data/dashboards.xml` creates the dashboard record.
- **Binary spreadsheet data**: The actual content lives in `data/files/invoicing_dashboard.json` as a base64-encoded binary field.
- **Sample dashboard**: A separate file `data/files/invoicing_sample_dashboard.json` provides demo data for the Odoo Studio-style sample preview.

This pattern is common for Odoo's pre-built content modules (dashboards, templates, report layouts).

## Dashboard Record

```xml
<record id="dashboard_invoicing" model="spreadsheet.dashboard">
    <field name="name">Invoicing</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_account/data/files/invoicing_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('account.model_account_move'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_account/data/files/invoicing_sample_dashboard.json
    </field>
    <field name="dashboard_group_id"
            ref="spreadsheet_dashboard.spreadsheet_dashboard_group_finance"/>
    <field name="group_ids" eval="[
        Command.link(ref('account.group_account_readonly')),
        Command.link(ref('account.group_account_invoice'))
    ]"/>
    <field name="sequence">20</field>
    <field name="is_published">True</field>
</record>
```

### Record Fields Explained

| Field | Value | Purpose |
|-------|-------|---------|
| `name` | `"Invoicing"` | Display name in the dashboard picker |
| `spreadsheet_binary_data` | Base64 JSON file | The actual spreadsheet definition |
| `main_data_model_ids` | `account.model_account_move` | Primary data model -- allows Odoo to manage links between spreadsheet cells and account.move records |
| `sample_dashboard_file_path` | Sample JSON file | Used by the studio-style sample preview |
| `dashboard_group_id` | Finance dashboard group | Places this dashboard in the Finance section of the dashboard picker |
| `group_ids` | `group_account_readonly`, `group_account_invoice` | Access control: only accounting users can see this dashboard |
| `sequence` | `20` | Sort order within the dashboard group |
| `is_published` | `True` | Makes the dashboard visible in the dashboard picker |

## Spreadsheet Structure: Two-Sheet Layout

The `invoicing_dashboard.json` defines a spreadsheet with **two sheets**: a `Dashboard` sheet for visualization and a `Data` sheet for KPI computation.

### Sheet 1: "Dashboard"

The main dashboard sheet contains:

1. **Scorecard figures** (top row): Three KPI cards displayed as spreadsheet figures.
2. **Line chart** (row 7): Invoice trend over time (monthly totals).
3. **Top 10 invoices table** (rows 23-34): Reference, salesperson, status, customer, date, amount.
4. **Two pivot tables** (rows 37-47 and 50-60): Country breakdown and product category breakdown.
5. **Geographic/carousel** (rows 35-46): Map + top-10 bar chart for country data.
6. **Treemap carousel** (rows 50-60): Category treemap + top-10 list.

The scorecard figures use Odoo's custom `scorecard` chart type embedded in the spreadsheet:

```
┌──────────────────────────────────────────────────────────────┐
│  [Invoiced: $X]  [Avg Invoice: $Y]  [DSO: N days]          │
├──────────────────────────────────────────────────────────────┤
│  [Line Chart: Invoiced Amount by Month]                      │
├─────────────────────────────┬──────────────────────────────────┤
│  Top 10 Invoices Table    │  Country Pivot + Bar Chart       │
├───────────────────────────┴──────────────────────────────────┤
│  Top 10 Countries (Map + Bar) │ Top Categories (Treemap)     │
└──────────────────────────────────────────────────────────────┘
```

### Sheet 2: "Data"

A hidden-ish computation sheet with KPI formulas. This sheet uses Odoo's proprietary spreadsheet functions to pull live accounting data:

```javascript
A1: "KPI - Income"
A2: "KPI - Average Invoice"
A3: "KPI - Invoice Count"
A4: "Current year"
A5: "Receivable"
A6: "Income"
A7: "COGS"
A8: "Revenue"
A9: "# days"
A10: "KPI - DSO"
A11: "KPI - Unpaid Invoices"

B1: =PIVOT.VALUE(5,"price_subtotal")           // Total income from pivot 5
B2: =IFERROR(PIVOT.VALUE(6,"price_subtotal")/B3)  // Avg = total/count
B3: =PIVOT.VALUE(6,"move_id")                  // Invoice count
B4: =YEAR(TODAY())                             // Current year
B5: =ODOO.BALANCE(ODOO.ACCOUNT.GROUP("asset_receivable"),$B$4)
     // Receivable balance from account group
B6: =-ODOO.BALANCE(ODOO.ACCOUNT.GROUP("income"),$B$4)
     // Income (negated because expense accounts have debit balance)
B7: =ODOO.BALANCE(ODOO.ACCOUNT.GROUP("expense_direct_cost"),$B$4)
     // COGS
B8: =B6-B7                                     // Gross revenue
B9: 365                                        // Days in year
B10: =ROUND(IFERROR(B5/B8*B9))                  // DSO: Receivable/Revenue*365
B11: =PIVOT.VALUE(7,"price_subtotal")          // Unpaid invoice total
```

The Data sheet uses:
- `ODOO.BALANCE()`: Returns the balance of an account or account group.
- `ODOO.ACCOUNT.GROUP()`: Resolves account group codes (e.g., `asset_receivable`) to account IDs.
- `PIVOT.VALUE()`: Returns values from embedded Odoo pivot tables.
- `FORMAT.LARGE.NUMBER()`: Humanizes large numbers (e.g., $1,234,567 → $1.2M).

## Key Financial KPIs

### 1. Income (Total Revenue)

```javascript
B6: =-ODOO.BALANCE(ODOO.ACCOUNT.GROUP("income"), $B$4)
```

Uses the `income` account group (standard Odoo chart of accounts group). The negation is necessary because in standard accounting, income accounts have credit balances, which `ODOO.BALANCE` returns as negative values. Negating flips the sign to positive revenue.

**Account Group Reference** (from standard Odoo chart of accounts):
- `income` → 700000 - 699999 (Revenue accounts)
- `expense_direct_cost` → 600000 - 699999 (Cost of Goods Sold)
- `asset_receivable` → 110000 - 119999 (Accounts Receivable)

### 2. DSO (Days Sales Outstanding)

```javascript
DSO = (Receivable Balance / Revenue) × 365
```

```javascript
B10: =ROUND(IFERROR(B5/B8*B9))
```

**Interpretation**: DSO measures how many days it takes to collect payment after a sale. A DSO of 30 means the average invoice is paid 30 days after issuance. High DSO indicates collection problems.

### 3. Average Invoice

```javascript
B2: =IFERROR(PIVOT.VALUE(6,"price_subtotal") / PIVOT.VALUE(6,"move_id"))
```

Divides total invoiced amount by invoice count. The pivots use `account.invoice.report` (also known as `account.move` with invoice-type filtering) as their data model.

### 4. Unpaid Invoices

```javascript
B11: =PIVOT.VALUE(7, "price_subtotal")
```

Pivot 7 is defined with the domain `payment_state = 'not_paid'`, filtering for only outstanding invoices.

## Pivot Tables in the Dashboard

The dashboard defines **7 embedded pivot tables** (`pivots` object in the JSON), each backed by `account.invoice.report` (the denormalized invoice reporting model):

| Pivot ID | Name | Groups By | Domain |
|---------|------|-----------|--------|
| 1 | Top Categories | `product_categ_id` | Posted invoices, out_invoice + out_refund |
| 2 | Country | `country_id` | Posted invoices with country, out types |
| 3 | Product | `product_id` | Posted invoices with product, out types |
| 4 | Salesperson | `invoice_user_id` | Posted invoices with user, out types |
| 5 | KPI - Income | (no group) | Posted invoices, out types |
| 6 | KPI - Average Invoice | (no group) | Posted invoices, out types |
| 7 | KPI - Unpaid | (no group) | Posted, out types, `payment_state = 'not_paid'` |

Pivot 5, 6, and 7 are used exclusively for the KPI scorecards in the Data sheet. Pivots 1-4 are rendered as charts and tables in the Dashboard sheet.

## List Tables in the Dashboard

The "Top 10 Invoices" table uses Odoo's `ODOO.LIST` and `ODOO.LIST.HEADER` functions:

```javascript
A24: =ODOO.LIST.HEADER(1, "name", "Reference")
B24: =ODOO.LIST.HEADER(1, "user_id", "Salesperson")
C24: =ODOO.LIST.HEADER(1, "payment_state", "Status")
D24: =ODOO.LIST.HEADER(1, "partner_id", "Customer")
F24: =ODOO.LIST.HEADER(1, "invoice_date", "Date")
G24: =ODOO.LIST.HEADER(1, "amount_untaxed_signed", "Amount")
```

The list uses `account.move` (list ID `1` in the dashboard) as its data source, filtered to posted `out_invoice` moves, ordered by `amount_total_signed` descending.

## Global Filters

The dashboard defines **5 global filters** (Odoo spreadsheet global filters), allowing users to slice the entire dashboard by:

| Filter ID | Type | Label | Model |
|-----------|------|-------|-------|
| `757a1b4b...` | Date | "Period" | - |
| `8051b4be...` | Relation | "Country" | `res.country` |
| `17277380...` | Relation | "Product Category" | `product.category` |
| `accd0cbe...` | Relation | "Product" | `product.product` |
| `02acc7f7...` | Relation | "Salesperson" | `res.users` |

The Period filter defaults to `last_90_days`, giving an immediate view of recent invoicing activity.

When a global filter is changed, all `PIVOT()`, `ODOO.BALANCE()`, `ODOO.LIST()`, and chart data in the spreadsheet automatically re-fetches with the new filter context applied.

## Chart: Invoice Trend Line

The line chart uses:
- **Model**: `account.invoice.report`
- **Measure**: `price_subtotal`
- **Group By**: `invoice_date:month` (monthly aggregation)
- **Domain**: Posted invoices of type `out_invoice` and `out_refund`
- **Type**: `odoo_line` (Odoo's custom line chart)

This produces a time-series line chart showing monthly invoicing totals, which updates with the Period filter.

## Scorecard Figures

Three scorecard figures display KPIs at a glance:

| Scorecard | Key Value | Baseline | Description |
|-----------|---------|---------|-------------|
| Invoiced | Data!C1 | Data!C11 (unpaid) | Total income, vs. unpaid portion |
| Average Invoice | Data!C2 | Data!C3 (invoice count) | Average invoice value |
| DSO | Data!C10 | "in current year" | Days to collect payment |

The scorecard type (`"type": "scorecard"`) is Odoo's custom spreadsheet figure that renders a large number with a comparison baseline below it.

## Access Control

Only users in the following groups can access this dashboard:
- `account.group_account_readonly`: Read-only access to accounting data.
- `account.group_account_invoice`: Access to create and manage invoices.

This is enforced via the `group_ids` field on the dashboard record. Users not in either group will not see the "Invoicing" dashboard in the picker.

## How the Spreadsheet Connects to Odoo Data

Odoo spreadsheets connect to ORM data through **Odoo-specific spreadsheet functions**:

```
ODOO.BALANCE(account_spec, date)
  → Executes a read_group on account.move.line
  → Returns the sum of debit - credit for the given account

ODOO.ACCOUNT.GROUP(group_code)
  → Resolves an account group code to a list of account IDs
  → Used as input to ODOO.BALANCE

PIVOT(pivot_id, measure, [row_field, col_field])
  → Reads from an embedded Odoo pivot table
  → Pivot tables are defined in the JSON's "pivots" object
  → Each pivot has its own domain, model, and measures

ODOO.LIST(list_id, row, field_name)
  → Reads from an Odoo list/recordset
  → list_id references a "lists" entry in the JSON
  → Returns the field value for a specific row

ODOO.LIST.HEADER(list_id, field_name, label)
  → Renders the table header for a list
```

This is distinct from standard spreadsheet functions. Odoo functions communicate with the Odoo server, which executes the ORM queries, while standard functions operate only on cell data.

## Relationship to `spreadsheet_account`

`spreadsheet_dashboard_account` builds on top of `spreadsheet_account`, which provides the underlying accounting spreadsheet function implementations (`ODOO.BALANCE`, `ODOO.ACCOUNT.GROUP`, etc.). Without `spreadsheet_account`, the dashboard's formulas would return errors.

```
spreadsheet_account (function library)
  └─ provides: ODOO.BALANCE, ODOO.ACCOUNT.GROUP, etc.
spreadsheet_dashboard_account (pre-built dashboard)
  └─ uses functions from spreadsheet_account
      └─ connects to: account.move, account.move.line
```

## Sample Dashboard

The `invoicing_sample_dashboard.json` file contains a version of the spreadsheet pre-populated with sample/demo data (not live). This file is used:
1. When users create a **copy** of the dashboard through Odoo Studio.
2. For preview purposes in the dashboard creation interface.

The sample data makes the dashboard look populated even in a fresh database without real invoices.

## Related

- [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md) -- Dashboard framework, how to create dashboard records
- [Modules/spreadsheet_account](spreadsheet_account.md) -- Accounting spreadsheet functions (ODOO.BALANCE, etc.)
- [Modules/Account](Account.md) -- Base accounting module (account.move, account.move.line)
- [Modules/account_reports](account_reports.md) -- Financial reports built with the Odoo report engine
