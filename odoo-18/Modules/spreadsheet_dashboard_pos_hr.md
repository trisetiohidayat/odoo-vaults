---
Module: spreadsheet_dashboard_pos_hr
Version: 18.0
Type: addon
Tags: #spreadsheet #dashboard #pos
---

# spreadsheet_dashboard_pos_hr

Spreadsheet dashboard for Point of Sale with HR/staff reporting.

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `pos_hr`
**Auto-Install:** `pos_hr`
**License:** LGPL-3

## What It Does

Provides a `spreadsheet.dashboard` record named "Point of Sale" for POS metrics. Uses `report.pos.order` and `pos.order` as primary data models. Group-restricted to `point_of_sale.group_pos_manager`. Auto-installs when `pos_hr` is present.

## Extends

- [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md) — base dashboard framework
- `pos_hr` — POS with employee management

## Data

| File | Purpose |
|------|---------|
| `data/dashboards.xml` | Registers dashboard "Point of Sale", group-restricted to `point_of_sale.group_pos_manager` |

## Key Details

- Dashboard group: `spreadsheet_dashboard_group_sales`
- Sequence: 300
- Published by default

---

*See also: [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md)*
