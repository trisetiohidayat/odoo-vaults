---
Module: spreadsheet_dashboard_sale_timesheet
Version: 18.0
Type: addon
Tags: #spreadsheet #dashboard #timesheet #sale
---

# spreadsheet_dashboard_sale_timesheet

Spreadsheet dashboard for time-tracking linked to sales (billable timesheets).

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `sale_timesheet`
**Auto-Install:** `sale_timesheet`
**License:** LGPL-3

## What It Does

Provides a `spreadsheet.dashboard` record named "Timesheets" for billable time tracking. Uses `account.analytic.line`, `project.project`, and `sale.order` as primary data models. Group-restricted to `hr_timesheet.group_hr_timesheet_approver`. Auto-installs when `sale_timesheet` is present.

## Extends

- [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md) — base dashboard framework
- `sale_timesheet` — time billed on sale orders

## Data

| File | Purpose |
|------|---------|
| `data/dashboards.xml` | Registers dashboard "Timesheets", group-restricted to `hr_timesheet.group_hr_timesheet_approver` |

## Key Details

- Dashboard group: `spreadsheet_dashboard_group_project`
- Sequence: 200
- Published by default

---

*See also: [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md)*
