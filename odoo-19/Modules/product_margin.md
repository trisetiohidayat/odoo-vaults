---
type: module
module: product_margin
tags: [odoo, odoo19, product, margin, sales, reporting, accounting]
created: 2026-04-06
---

# Margins by Products

## Overview
| Property | Value |
|----------|-------|
| **Name** | Margins by Products |
| **Technical** | `product_margin` |
| **Category** | Sales/Sales |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. (original: CCI Connect asbl) |

## Description
Adds a product margin reporting view accessible from the Products menu. Computes sales, purchases, margins, and related indicators based on posted and/or paid invoices. Values are computed via direct SQL for performance.

## Dependencies
- `account`

## Key Models
| Model | Type | Description |
|-------|------|-------------|
| `product.product` | Extension | 16 computed margin fields; SQL-based computation |

## `product.product` (Extension)
### Computed Fields (all read-only, computed via `_compute_product_margin_fields_values`)
| Field | Type | Description |
|-------|------|-------------|
| `date_from` | Date | Report period start (default: Jan 1) |
| `date_to` | Date | Report period end (default: Dec 31) |
| `invoice_state` | Selection | `paid`, `open_paid`, `draft_open_paid` |
| `sale_avg_price` | Float | Average customer invoice unit price |
| `purchase_avg_price` | Float | Average vendor bill unit price |
| `sale_num_invoiced` | Float | Sum of quantities in customer invoices |
| `purchase_num_invoiced` | Float | Sum of quantities in vendor bills |
| `turnover` | Float | Revenue (out_invoice) minus credits (out_refund) |
| `total_cost` | Float | Sum of invoice price x qty for vendor bills |
| `sale_expected` | Float | Sum of list_price x qty for customer invoices |
| `normal_cost` | Float | standard_price x purchase_num_invoiced |
| `total_margin` | Float | turnover - total_cost |
| `expected_margin` | Float | sale_expected - normal_cost |
| `total_margin_rate` | Float | total_margin * 100 / turnover |
| `expected_margin_rate` | Float | expected_margin * 100 / sale_expected |
| `sales_gap` | Float | sale_expected - turnover |
| `purchase_gap` | Float | normal_cost - total_cost |

### Context Keys for Computation
| Key | Description |
|-----|-------------|
| `date_from` | Period start (default: current year Jan 1) |
| `date_to` | Period end (default: current year Dec 31) |
| `invoice_state` | `paid`, `open_paid` (default), `draft_open_paid` |
| `force_company` | Override company for multi-company |

### SQL Computation
The main query joins `account_move_line`, `account_move`, `product_product`, and `product_template` (for `list_price`). It uses currency rate conversion and applies the discount factor `(100 - discount) / 100`.

### Read Group Overrides
- `_read_group` — Custom handling for special aggregate fields that are not stored
- `_read_grouping_sets` — Same for modern grouping sets API
- `_read_group_select` — Returns `SQL("NULL")` for special aggregates to bypass default behavior

## Related
- [Modules/product](odoo-18/Modules/product.md)
- [Modules/account](odoo-18/Modules/account.md)
- [Modules/sale_margin](odoo-18/Modules/sale_margin.md)
