---
Module: project_stock_landed_costs
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_stock_landed_costs #project #stock
---

## Overview

**Module:** `project_stock_landed_costs`
**Depends:** `project_stock_account`, `stock_landed_costs` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_stock_landed_costs/`
**License:** LGPL-3
**Summary:** Technical Bridge
**Purpose:** Applies project analytic distribution to landed costs originating from stock pickings. When a landed cost is created on a picking with a project, the cost lines get the project's analytic distribution applied.

---

## Models

### `stock.valuation.adjustment.lines` (models/stock_landed_costs.py, 1–13)

Inherits: `stock.valuation.adjustment.lines`

| Method | Line | Description |
|---|---|---|
| `_prepare_account_move_line_values()` | 9 | If `cost_id.target_model == 'picking'`: sets `analytic_distribution` from `move_id.picking_id.project_id._get_analytic_distribution()`. Falls back to `super()` for non-picking landed costs (e.g., manufacturing). |

---

## Architecture

`stock.valuation.adjustment.lines` represents individual cost line items within a landed cost document. The `target_model` field on the parent `stock.landed.cost` distinguishes picking-origin costs from manufacturing-origin costs.

When `target_model == 'picking'`:
- The adjustment line's stock move originates from a stock picking (`move_id.picking_id`)
- The picking's `project_id` provides the analytic distribution
- Journal entry lines get `analytic_distribution` applied so landed cost hits the project's analytic account

This mirrors `project_mrp_stock_landed_costs` but for picking operations instead of manufacturing orders.

---

## Security / Data

No `ir.model.access.csv`. No data XML files.

---

## Critical Notes

- Only applies analytic distribution when `target_model == 'picking'`. Manufacturing-based landed costs use `project_mrp_stock_landed_costs` instead.
- `target_model` is a field on `stock.landed.cost` (parent document), not on the adjustment line itself.
- v17→v18: No breaking changes.