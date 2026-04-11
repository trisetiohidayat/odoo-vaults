---
Module: project_mrp_stock_landed_costs
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_mrp_stock_landed_costs #project #mrp #stock
---

## Overview

**Module:** `project_mrp_stock_landed_costs`
**Depends:** `project_mrp_account`, `mrp_landed_costs` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_mrp_stock_landed_costs/`
**License:** LGPL-3
**Purpose:** Applies project analytic distribution to landed costs originating from manufacturing operations. When a landed cost is created on a manufacturing order, the cost is distributed to the project's analytic accounts.

---

## Models

### `stock.valuation.adjustment.lines` (models/stock_landed_costs.py, 1–13)

Inherits: `stock.valuation.adjustment.lines`

| Method | Line | Description |
|---|---|---|
| `_prepare_account_move_line_values()` | 9 | If `cost_id.target_model == 'manufacturing'`: sets `analytic_distribution` from `move_id.production_id.project_id._get_analytic_distribution()`. Falls back to `super()` for non-manufacturing landed costs (e.g., stock picking landed costs). |

---

## Architecture

The `stock.valuation.adjustment.lines` model represents individual cost line items within a landed cost document. The `target_model` field on the parent `stock.landed.cost` distinguishes manufacturing-origin costs from picking-origin costs.

When `target_model == 'manufacturing'`:
- The adjustment line's stock move originates from an MO (`move_id.raw_material_production_id`)
- The MO's `project_id` provides the analytic distribution
- Journal entry lines get the `analytic_distribution` applied so landed cost hits the project's analytic account

---

## Security / Data

No `ir.model.access.csv`. No data XML files.

---

## Critical Notes

- Only applies analytic distribution when `target_model == 'manufacturing'`. Picking-based landed costs use the default behavior.
- `target_model` is a field on `stock.landed.cost` (the parent document), not on the adjustment line itself.
- v17→v18: No breaking changes.