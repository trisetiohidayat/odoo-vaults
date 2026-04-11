# sale_stock_margin — Sale Stock Margin

**Tags:** #odoo #odoo18 #sale #stock #margin #anglo-saxon
**Odoo Version:** 18.0
**Module Category:** Sale + Stock / Margin Calculation
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_stock_margin` extends `sale_stock` to compute purchase price (cost basis for margin) on stock-delivered lines using the product's average cost from valued moves (`_compute_average_price`). It complements `sale_timesheet_margin` for the stock-delivery path.

**Technical Name:** `sale_stock_margin`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_stock_margin/`
**Depends:** `sale_stock`
**Inherits From:** `sale.order.line`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/sale_order_line.py` | `sale.order.line` | Stock-driven purchase price computation via average cost |

---

## Models Reference

### `sale.order.line` (models/sale_order_line.py)

#### Inheritance Chain

`sale.order.line` → `sale_stock.sale.order.line` (adds stock_move qty delivery) → `sale_stock_margin.sale.order.line` (overrides `_compute_purchase_price`)

#### Field Changes

No new fields added. Module only overrides `_compute_purchase_price()` method.

#### Methods

| Method | Decorators | Behavior |
|--------|-----------|----------|
| `_compute_purchase_price()` | `@api.depends('move_ids', 'move_ids.stock_valuation_layer_ids', 'move_ids.picking_id.state')` | Computes purchase price from valued stock moves using average costing |

#### Critical Override Logic

```python
for line in self:
    product = line.product_id.with_company(line.company_id)
    if not line.has_valued_move_ids():
        line_ids_to_pass.add(line.id)          # non-valued lines -> super()
    elif line.product_id and line.product_id.categ_id.property_cost_method != 'standard':
        # Non-standard cost method: compute from valued moves
        qty = line.qty_delivered if line.product_id.invoice_policy == 'order' else line.qty_to_invoice
        purch_price = product._compute_average_price(0, qty, line.move_ids)
        if line.product_uom != product.uom_id:
            purch_price = product.uom_id._compute_price(purch_price, line.product_uom)
        line.purchase_price = line._convert_to_sol_currency(purch_price, product.cost_currency_id)
    elif not line.product_uom_qty and line.qty_delivered:
        line_ids_to_pass.add(line.id)          # line from delivery + standard price -> super()
return super()._compute_purchase_price()       # pass selected lines to super
```

#### Key Behavior

1. **Three-branch logic**: Lines not yet valued → pass to super(); non-standard cost method → compute from moves; standard cost with no ordered qty → pass to super()
2. **Average costing**: Uses `product._compute_average_price()` which reads stock valuation layers to compute unit cost
3. **UOM handling**: Converts from product's default uom to line's product_uom if different
4. **Currency conversion**: Converts via `_convert_to_sol_currency()` to the SOL's sale currency
5. **Excludes from average**: Uses `qty_delivered` for `invoice_policy='delivery'`, `qty_to_invoice` for `invoice_policy='order'`

---

## Security File

No security file (`security/` directory does not exist in this module).

---

## Data Files

No data file (`data/` directory does not exist in this module).

---

## Critical Behaviors

1. **Non-Standard Cost Methods Only**: Only computes from moves when `property_cost_method` is 'average' or 'fifo'. For 'standard' cost method, delegates to super() (which typically uses `product.standard_price`).

2. **Average Price Source**: `_compute_average_price()` in `product.product` reads `stock_valuation_layer_ids` to compute weighted average cost.

3. **Lines Without Ordered Qty**: If `product_uom_qty == 0` but `qty_delivered > 0` (line created from delivery), passes to super() to use standard price — avoids zero-denominator issues.

4. **Chain with Other Modules**: This override is designed to compose with `sale_timesheet_margin` and `sale_mrp_margin` — all filter their lines out before calling super() to avoid duplicate processing.

---

## v17→v18 Changes

No significant changes from v17 to v18 identified. Module structure and logic remain consistent.

---

## Notes

- Complements `sale_timesheet_margin` for the stock-delivery path
- Together, `sale_timesheet_margin` + `sale_stock_margin` + `sale_mrp_margin` provide the three main delivery method cost sources
- The `has_valued_move_ids()` check ensures only lines with actual stock moves (done state) participate in average cost calculation
