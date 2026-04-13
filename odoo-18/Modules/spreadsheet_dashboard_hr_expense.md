---
Module: spreadsheet_dashboard_hr_expense
Version: 18.0
Type: addon
Tags: #spreadsheet #dashboard #expense
---

# spreadsheet_dashboard_hr_expense

Spreadsheet dashboard for HR expense reporting.

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `sale_expense`
**Auto-Install:** `sale_expense`
**License:** LGPL-3

## What It Does

Provides a `spreadsheet.dashboard` record with a pre-built expense spreadsheet. Uses `hr_expense` as the primary data model. Auto-installs when `sale_expense` is present.

## Extends

- [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — base dashboard framework
- `sale_expense` — expense-linked sales workflow

## Data

| File | Purpose |
|------|---------|
| `data/dashboards.xml` | Registers dashboard "Expenses", group-restricted to `hr_expense.group_hr_expense_manager` |

## Key Details

- Dashboard group: `spreadsheet_dashboard_group_finance`
- Sequence: 40
- Published by default

---

*See also: [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md)*
