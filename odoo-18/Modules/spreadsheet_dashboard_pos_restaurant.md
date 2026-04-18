---
Module: spreadsheet_dashboard_pos_restaurant
Version: 18.0
Type: addon
Tags: #spreadsheet #dashboard #pos #restaurant
---

# spreadsheet_dashboard_pos_restaurant

Spreadsheet dashboard for POS restaurant reporting.

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `pos_hr`, `pos_restaurant`
**Auto-Install:** `pos_hr`, `pos_restaurant`
**License:** LGPL-3

## What It Does

Provides a `spreadsheet.dashboard` record named "POS - Restaurant" for restaurant POS metrics. Uses `pos.order` as the primary data model. Group-restricted to `point_of_sale.group_pos_manager`. Auto-installs when both `pos_hr` and `pos_restaurant` are present.

## Extends

- [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — base dashboard framework
- `pos_hr` — POS with employee management
- `pos_restaurant` — restaurant floor/table management

## Data

| File | Purpose |
|------|---------|
| `data/dashboards.xml` | Registers dashboard "POS - Restaurant", group-restricted to `point_of_sale.group_pos_manager` |

## Key Details

- Dashboard group: `spreadsheet_dashboard_group_sales`
- Sequence: 350
- Published by default

---

*See also: [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md)*
