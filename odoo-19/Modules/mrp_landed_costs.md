---
type: module
module: mrp_landed_costs
tags: [odoo, odoo19, mrp, landed_costs, manufacturing, valuation]
created: 2026-04-06
---

# MRP Landed Costs

## Overview
| Property | Value |
|----------|-------|
| **Name** | MRP Landed Costs |
| **Technical** | `mrp_landed_costs` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Allows landed costs to be applied directly on Manufacturing Orders (MOs). Extra costs (freight, customs, insurance, etc.) can be added to an MO and the system splits those costs among the finished product's stock moves for accurate stock valuation.

## Dependencies
- `stock_landed_costs`
- `mrp`

## Key Changes

### stock.landed.cost
Adds `manufacturing` as a valid `target_model` value.

**Fields:**
- `target_model` (Selection) — Extended with `manufacturing` option
- `mrp_production_ids` (Many2many `mrp.production`) — MOs targeted by this landed cost

**Key Methods:**
- `_onchange_target_model()` — Clears `mrp_production_ids` when target changes away from manufacturing
- `_get_targeted_move_ids()` — Overridden: combines parent method's result with finished product moves from selected MOs, excluding byproduct moves

```python
def _get_targeted_move_ids(self):
    return (
        super()._get_targeted_move_ids()
        | self.mrp_production_ids.move_finished_ids
        - self.mrp_production_ids.move_byproduct_ids.filtered(lambda move: not move.cost_share)
    )
```

This ensures the landed cost split is applied only to the main finished product moves, not byproducts.

## How It Works
1. Create a `stock.landed.cost` record
2. Set **Target On** = `manufacturing`
3. Select one or more MOs in **Manufacturing Orders**
4. Add cost lines (e.g., freight, customs duty)
5. Add valuation adjustments
6. Click **Compute Landed Cost** — the system splits costs across finished product stock moves
7. Validate the landed cost — creates accounting entries and updates stock valuations

## Related
- [Modules/stock_landed_costs](odoo-18/Modules/stock_landed_costs.md) — Base landed cost model and logic
- [Modules/mrp_account](odoo-18/Modules/mrp_account.md) — Manufacturing cost accounting
