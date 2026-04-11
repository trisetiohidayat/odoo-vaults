# sale_timesheet_margin — Sale Timesheet Margin

**Tags:** #odoo #odoo18 #sale #timesheet #margin
**Odoo Version:** 18.0
**Module Category:** Sale + Timesheet Integration / Margin
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_timesheet_margin` extends `sale_timesheet` and `sale_stock_margin` to compute purchase price (cost basis for margin calculation) on timesheet-delivered service lines using actual analytic line `amount` values, rather than the product's standard cost.

**Technical Name:** `sale_timesheet_margin`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_timesheet_margin/`
**Depends:** `sale_timesheet`, `sale_stock_margin`
**Inherits From:** `sale.order.line` (via `sale_timesheet` and `sale_stock_margin`)

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/sale_order_line.py` | `sale.order.line` | Timesheet-driven purchase price computation |

---

## Models Reference

### `sale.order.line` (models/sale_order_line.py)

#### Inheritance Chain

`sale.order.line` → `sale_timesheet.sale.order.line` (adds timesheet delivery) → `sale_timesheet_margin.sale.order.line` (overrides `_compute_purchase_price`)

#### Field Changes

No new fields added. Module only overrides `_compute_purchase_price()` method.

#### Methods

| Method | Decorators | Behavior |
|--------|-----------|----------|
| `_compute_purchase_price()` | `@api.depends('analytic_line_ids.amount', 'qty_delivered_method')` | Filters out timesheet SOLs before calling super, then manually computes purchase price for timesheet lines by reading analytic line sums |

#### Critical Override Logic

```python
# Lines to exclude from super() call (handled separately)
service_non_timesheet_sols = self.filtered(
    lambda sol: not sol.is_expense and sol.is_service and
    sol.product_id.service_policy == 'ordered_prepaid' and
    sol.state == 'sale' and sol.purchase_price != 0
)
timesheet_sols = self.filtered(
    lambda sol: sol.qty_delivered_method == 'timesheet' and not sol.product_id.standard_price
)
# Call super with these excluded
super(...)._compute_purchase_price()

# For timesheet lines: compute from analytic lines
group_amount = self.env['account.analytic.line']._read_group(
    [('so_line', 'in', timesheet_sols.ids), ('project_id', '!=', False)],
    ['so_line'],
    ['amount:sum', 'unit_amount:sum'])
# purchase_price = -sum(amount) / sum(unit_amount) per SOL
```

#### Key Behavior

1. **Filters out SOLs** where `qty_delivered_method == 'timesheet'` and product has no `standard_price`
2. **Calls super()** for non-timesheet SOLs to let other modules (e.g., `sale_stock_margin`) handle them
3. **Computes from analytic lines**: Groups `account.analytic.line` by `so_line`, sums `amount` and `unit_amount`, then sets `purchase_price = -amount_sum / unit_amount_sum`
4. **UOM conversion**: If the line's product_uom differs from company's project time mode, converts the price
5. **Currency conversion**: Converts to SOL currency via `_convert_to_sol_currency()`

---

## Security File

No security file (`security/` directory does not exist in this module).

---

## Data Files

No data file (`data/` directory does not exist in this module).

---

## Critical Behaviors

1. **Smart Filtering**: The override avoids calling super for its own lines to prevent re-computation loops with other `_compute_purchase_price()` overrides.

2. **Negative Amount Handling**: The formula `-amount_sum / unit_amount_sum` correctly inverts the analytic line sign convention (debit is negative in analytic accounting) to yield a positive cost for margin calculation.

3. **Conditional Activation**: Only applies when `qty_delivered_method == 'timesheet'` AND the product has no `standard_price`. If a product has a standard_price, the super() result is kept (allows manual override).

4. **UOM Conversion**: Handles time UOM differences between the product's uom_id and the company's project_time_mode_id (e.g., Hours vs. Days).

---

## v17→v18 Changes

No significant changes from v17 to v18 identified. Module structure and logic are consistent.

---

## Notes

- This is a lightweight module (1 file, ~46 lines of actual logic)
- The purchase_price computed here feeds directly into margin calculation on the SO
- The negative sign inverts analytic line convention where employee costs are typically negative (credit)
- Without this module, timesheet-delivered lines would use the product's standard_price (often zero for service products)
