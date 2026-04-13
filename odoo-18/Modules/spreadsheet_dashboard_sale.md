---
Module: spreadsheet_dashboard_sale
Version: 18.0
Type: addon
Tags: #spreadsheet #dashboard #sale
---

# spreadsheet_dashboard_sale

Spreadsheet dashboard for sales and product reporting.

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `sale`
**Auto-Install:** `sale`
**License:** LGPL-3

## What It Does

Provides two `spreadsheet.dashboard` records:

1. **Sales** — general sales KPIs (revenue, orders, quotes) using `sale.order`
2. **Product** — product-level sales analysis using `sale.order`

Both are group-restricted to `sales_team.group_sale_manager`. Auto-installs when `sale` is present.

## Extends

- [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — base dashboard framework
- `sale` — core sales management

## Data

| File | Purpose |
|------|---------|
| `data/dashboards.xml` | Registers two dashboards ("Sales" seq 100, "Product" seq 200) |

## Key Details

- Dashboard group: `spreadsheet_dashboard_group_sales`
- Both dashboards published by default

---

*See also: [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md), [Modules/sale](Modules/sale.md)*
