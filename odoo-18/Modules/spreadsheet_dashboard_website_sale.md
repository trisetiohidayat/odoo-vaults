---
Module: spreadsheet_dashboard_website_sale
Version: 18.0
Type: addon
Tags: #spreadsheet #dashboard #ecommerce #website
---

# spreadsheet_dashboard_website_sale

Spreadsheet dashboard for eCommerce reporting.

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `website_sale`
**Auto-Install:** `website_sale`
**License:** LGPL-3

## What It Does

Provides a `spreadsheet.dashboard` record named "eCommerce" for online sales metrics. Uses `sale.order` as the primary data model. Group-restricted to `sales_team.group_sale_manager`. Auto-installs when `website_sale` is present.

## Extends

- [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md) — base dashboard framework
- `website_sale` — eCommerce platform

## Data

| File | Purpose |
|------|---------|
| `data/dashboards.xml` | Registers dashboard "eCommerce", group-restricted to `sales_team.group_sale_manager` |

## Key Details

- Dashboard group: `spreadsheet_dashboard_group_website`
- Sequence: 200
- Published by default

---

*See also: [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md), [Modules/website_sale](odoo-18/Modules/website_sale.md)*
