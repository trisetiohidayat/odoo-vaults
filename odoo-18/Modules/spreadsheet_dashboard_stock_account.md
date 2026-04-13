---
Module: spreadsheet_dashboard_stock_account
Version: 18.0
Type: addon
Tags: #spreadsheet #dashboard #stock #account
---

# spreadsheet_dashboard_stock_account

Spreadsheet dashboard for warehouse/inventory metrics.

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `stock_account`
**Auto-Install:** `stock_account`
**License:** LGPL-3

## What It Does

Provides a `spreadsheet.dashboard` record named "Warehouse Metrics" for stock operations. Uses `stock.quant` as the primary data model. Group-restricted to `stock.group_stock_manager`. Auto-installs when `stock_account` is present.

## Extends

- [Modules/spreadsheet_dashboard](modules/spreadsheet_dashboard.md) — base dashboard framework
- `stock_account` — inventory valuation accounting

## Data

| File | Purpose |
|------|---------|
| `data/dashboards.xml` | Registers dashboard "Warehouse Metrics", group-restricted to `stock.group_stock_manager` |

## Key Details

- Dashboard group: `spreadsheet_dashboard_group_logistics`
- Sequence: 300
- Published by default

---

*See also: [Modules/spreadsheet_dashboard](modules/spreadsheet_dashboard.md)*
