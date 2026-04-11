---
Module: product_margin
Version: 18.0.0
Type: addon
Tags: #odoo18 #product #margin #account #report
---

## Overview

Computes margin and profitability metrics on `product.product` records by analyzing sale and purchase invoices. All fields are computed via raw SQL over `account.move.line` with currency rate CTEs.

**Depends:** `product`, `account`

**Key Behavior:** Margin is computed by comparing average sale price vs. average purchase price invoiced within a configurable date range and invoice state. Uses SQL `UNION ALL` + `_read_group` pattern for multi-aggregate computation.

---

## Models

### `product.product` (Inherited)

**Inherited from:** `product.product`

| Field | Type | Note |
|-------|------|------|
| `date_from` | Date | Start of analysis period (filter) |
| `date_to` | Date | End of analysis period (filter) |
| `invoice_state` | Selection | `'paid'` or `'all'` filter for invoices |
| `sale_avg_price` | Float (compute) | Average sale unit price |
| `purchase_avg_price` | Float (compute) | Average purchase unit price |
| `sale_num_invoiced` | Float (compute) | Total quantity sold |
| `purchase_num_invoiced` | Float (compute) | Total quantity purchased |
| `sales_gap` | Float (compute) | `sale_avg_price - product.standard_price` |
| `purchase_gap` | Float (compute) | `purchase_avg_price - product.standard_price` |
| `turnover` | Float (compute) | Total sale revenue |
| `total_cost` | Float (compute) | Total purchase cost |
| `sale_expected` | Float (compute) | Expected sale revenue at standard cost |
| `normal_cost` | Float (compute) | Standard price as normal cost reference |
| `total_margin` | Float (compute) | `turnover - total_cost` |
| `expected_margin` | Float (compute) | `sale_expected - total_cost` |
| `total_margin_rate` | Float (compute) | `(total_margin / turnover) * 100` if turnover != 0 |
| `expected_margin_rate` | Float (compute) | `(expected_margin / sale_expected) * 100` if sale_expected != 0 |

| Method | Returns | Note |
|--------|---------|------|
| `_read_group_select(self, groupby, select)` | SQL/float | Bypasses `SUM(field)` aggregation error for special fields |
| `_read_group` | — | Custom read_group returning SQL-aggregated values for margin fields |
| `_compute_product_margin_fields_values()` | — | Dual SQL query: sale invoices then purchase invoices; sets all margin fields |

---

## Critical Notes

- **`_SPECIAL_SUM_AGGREGATES`:** Set containing fields that cannot be aggregated by SUM in read_group — triggers `_read_group_select` bypass.
- **Currency Rate CTE:** The SQL uses a Common Table Expression for `currency_rate` to convert all amounts to the user's company currency before aggregation.
- **Invoice Filtering:** Only `out_invoice` lines affect sale metrics; only `in_invoice` lines affect purchase metrics. Draft/invalid invoices excluded by state.
- **`_compute_product_margin_fields_values`:** Executes two SQL queries (sale, then purchase) against `account_move_line` joined with `product_product` and `res_currency_rate`. Results are stored in a `vals` dict keyed by product ID.
