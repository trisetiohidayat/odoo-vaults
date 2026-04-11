# mrp_subcontracting_landed_costs — MRP Subcontracting Landed Costs

**Tags:** #odoo #odoo18 #mrp #subcontracting #landed-costs #stock-account
**Odoo Version:** 18.0
**Module Category:** MRP Subcontracting + Stock Accounting / Landed Costs
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`mrp_subcontracting_landed_costs` extends `mrp_subcontracting` and `stock_landed_costs` to allow landed costs (like freight, insurance, customs duties) to be allocated to subcontracted products. When a subcontract production is received, its landed costs can be split among the subcontracted components using the landed costs mechanism from `stock_landed_costs`.

**Technical Name:** `mrp_subcontracting_landed_costs`
**Python Path:** `~/odoo/odoo18/odoo/addons/mrp_subcontracting_landed_costs/`
**Depends:** `mrp_subcontracting`, `stock_landed_costs`
**Inherits From:** `stock.move`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/stock_move.py` | `stock.move` | Overrides SVL retrieval to include subcontracting production SVLs |

---

## Models Reference

### `stock.move` (models/stock_move.py)

#### Methods

| Method | Decorators | Behavior |
|--------|-----------|----------|
| `_get_stock_valuation_layer_ids()` | `@api.one` | For subcontracted moves: returns SVL from `move_finished_ids` of the subcontract production; otherwise delegates to super |

#### Critical Override Logic

```python
def _get_stock_valuation_layer_ids(self):
    self.ensure_one()
    stock_valuation_layer_ids = super()._get_stock_valuation_layer_ids()
    subcontracted_productions = self._get_subcontract_production()
    if self.is_subcontract and subcontracted_productions:
        return subcontracted_productions.move_finished_ids.stock_valuation_layer_ids
    return stock_valuation_layer_ids
```

**Key behavior:**
- For a subcontracted stock move (receiving finished product from subcontractor), the SVL of the **finished product** (from the subcontract production's `move_finished_ids`) is returned, not the SVL of the component moves.
- This allows `stock_landed_costs` to allocate landed costs across the components using the correct finished-goods valuation layer as the basis.
- `subcontracted_productions = self._get_subcontract_production()` retrieves the `mrp.production` linked to this move via the subcontracting mechanism.

---

## Security File

No security file (`security/` directory does not exist in this module).

---

## Data Files

No data file (`data/` directory does not exist in this module).

---

## Critical Behaviors

1. **Subcontract Valuation Layer Override**: When a subcontracting receipt is processed, the stock move for the finished product is marked `is_subcontract = True`. The standard `_get_stock_valuation_layer_ids()` would return the component SVLs (from the subcontractor's internal moves). The override redirects to the finished product's SVLs from the subcontracting production order.

2. **Landed Cost Allocation**: With the correct SVL as the basis, `stock_landed_costs` can then split the landed cost among the different component lines based on their value proportions, updating each component's `standard_price` accordingly.

3. **Chain with `stock_landed_costs`**: This module is designed to work with `stock_landed_costs`. The `stock_landed_costs` module's logic for splitting costs across product lines uses `_get_stock_valuation_layer_ids()` to find the relevant SVLs for the picking's moves.

4. **No New Fields/Models**: The module adds zero fields and defines no new models — only a single method override. The entire value is in redirecting the SVL lookup for subcontracted moves.

---

## v17→v18 Changes

No significant changes from v17 to v18 identified. Module structure and logic remain consistent.

---

## Notes

- This module is the smallest of the batch (1 file, ~14 lines of actual code)
- Its purpose is to make the `stock_landed_costs` module work correctly with subcontracting by providing the right SVL reference point for the finished product
- Without this module, landed cost allocation on subcontracted products would use component-level SVLs (which may not exist or be accurate) instead of the finished product's SVL
