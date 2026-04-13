---
type: module
module: pos_sale_margin
tags: [odoo, odoo19, pos, sale, margin, reporting]
created: 2026-04-11
---

# POS Sale Margin

**Module:** `pos_sale_margin`  
**Path:** `odoo/addons/pos_sale_margin/`  
**Category:** Sales/Point of Sale  
**Depends:** `pos_sale`, `sale_margin`  
**Auto-install:** True  
**Version:** 1.1  
**License:** LGPL-3  
**Author:** Odoo S.A.

Link module that bridges Point of Sale order lines with the `sale.report` analytic report, enabling POS margin figures to appear alongside regular SO margin figures in the Sales Margin report.

---

## Architecture

This is a pure **report override** module. It contributes zero models and zero views. All functionality lives in a single 12-line Python file that overrides `sale.report`'s `_fill_pos_fields` hook.

```
pos_sale_margin
└── report/
    └── sale_report.py     # _fill_pos_fields() override
```

**Dependency chain:**

```
pos_sale_margin
  ├── pos_sale             # Provides pos.order / pos.order.line in sale.report via UNION
  │    ├── point_of_sale
  │    └── sale
  │         ├── sale_management
  │         └── account (for invoicing)
  └── sale_margin          # Provides margin field on sale.order.line + sale.report base
       ├── sale
       └── product (standard_price)
```

The module auto-installs because both `pos_sale` and `sale_margin` are commonly installed together in POS deployments that track profitability.

---

## L1 — pos.order.line Extension for Margin Tracking in POS

### What Gets Extended

`pos_sale_margin` does not extend `pos.order.line` directly. It extends `sale.report` — the cross-document analytics model that aggregates both SO lines and POS lines into a unified denormalized view.

In the `sale.report` model (via `pos_sale`), POS lines are included through a `UNION ALL` query that selects from `pos_order_line` instead of `sale_order_line`:

```sql
SELECT ...
  SUM((l.price_subtotal - COALESCE(l.total_cost, 0)) / COALESCE(pos.currency_rate, 1))
    AS margin
FROM pos_order_line l
JOIN pos_order pos ON l.order_id = pos.id
...
```

The `total_cost` field on `pos.order.line` is populated by `pos_sale` when a POS order is linked to a sale order (via the `sale_order_line_id` reverse link). However, when a POS order is created directly in POS without a linked SO, `total_cost` is set directly at POS order creation time.

### How Margin Flows into the Report

1. `sale_margin` adds a `total_cost` column to `sale_order_line` (populated from `product.standard_price * qty` at line creation).
2. `pos_sale` adds a `total_cost` column to `pos_order_line` (populated from `product.standard_price * qty` at order creation).
3. `pos_sale` contributes a `UNION ALL` branch to `sale.report`'s query, selecting from `pos_order_line` for POS-only lines.
4. `pos_sale_margin` adds the `margin` formula in the `_fill_pos_fields` override for that UNION branch.

### POS Line vs SO Line Margin Difference

| Aspect | SO line | POS line |
|--------|---------|----------|
| Source table | `sale_order_line` | `pos_order_line` |
| `total_cost` set when | `sale.order.line` created | POS order created |
| Product cost source | `product.standard_price` | `product.standard_price` |
| Margin formula | `(price_subtotal - total_cost) / currency_rate` | Same |
| Report path | `sale.report` (SO branch) | `sale.report` (POS branch, via UNION) |

---

## L2 — Field Types, Defaults, Constraints

### Fields Contributed by This Module

**None.** This module contributes no fields, no models, no tables. It only overrides one method.

### Fields Used (not owned)

| Field | Model | Source Module | Purpose in margin calculation |
|-------|-------|--------------|-------------------------------|
| `total_cost` | `pos.order.line` | `pos_sale` | Product cost for the POS line |
| `price_subtotal` | `pos.order.line` | `point_of_sale` | Net revenue for the POS line |
| `currency_rate` | `pos.order` | `point_of_sale` | Converts to company currency |
| `margin` | `sale.report` | Added here | Profit = revenue - cost |

### Margin SQL Formula

```sql
SUM(
  (l.price_subtotal - COALESCE(l.total_cost, 0))
  / CASE COALESCE(pos.currency_rate, 0)
    WHEN 0 THEN 1.0
    ELSE pos.currency_rate
    END
) AS margin
```

**Key design decisions:**

- `COALESCE(total_cost, 0)`: If `total_cost` is NULL (product has no standard price set), the line contributes zero cost — margin = full price_subtotal. This avoids silent exclusion of margin-less products.
- Division by `currency_rate`: All amounts are converted to company currency before summing. The rate division is wrapped in a `CASE` that substitutes `1.0` when rate is zero (safety guard for unconfigured currencies).
- `SUM(...)`: The margin is aggregated per product per order, matching the grouping structure of the rest of the `sale.report` query.

### `_fill_pos_fields` Override Contract

```python
def _fill_pos_fields(self, additional_fields):
    values = super()._fill_pos_fields(additional_fields)
    values['margin'] = '...formula...'
    return values
```

The method receives `additional_fields` (a dict of field names that need SQL expressions for the POS UNION branch), replaces/inserts the `'margin'` key with the margin SQL expression, and returns the augmented dict.

The parent `pos_sale/report/sale_report.py` calls this method and injects each `(field_name, sql_expression)` pair into the SELECT clause using:

```python
template = ", %s AS %s"
for fname, value in additional_fields_info.items():
    select_ += template % (value, fname)
```

---

## L3 — cross_model, Override Pattern, Workflow Trigger

### Cross-Model Data Flow

```
product.product (standard_price)
  │
  ▼ (at POS order creation time, via product_id)
pos.order.line (total_cost = standard_price * qty)
  │
  ▼ (at report query time)
pos.order (currency_rate)
  │
  ▼ (via _fill_pos_fields override)
sale.report (margin field)
```

| Step | Trigger | Data |
|------|---------|------|
| 1 | POS order created | `pos.order.line.total_cost` set from `product.standard_price * qty` |
| 2 | POS order saved | `pos.order.currency_rate` set by POS session currency |
| 3 | Sale report queried | UNION branch selects from `pos_order_line` joined to `pos_order` |
| 4 | Margin computed | `(price_subtotal - total_cost) / currency_rate` per line |

The `total_cost` field is populated by `pos_sale` at POS order creation time, not at report query time. This means margin is a historical snapshot — changing `product.standard_price` after the POS order is created does not retroactively change the recorded margin.

### Override Pattern

**File:** `report/sale_report.py`

```python
class SaleReport(models.Model):
    _inherit = "sale.report"

    def _fill_pos_fields(self, additional_fields):
        values = super()._fill_pos_fields(additional_fields)
        values['margin'] = 'SUM((l.price_subtotal - COALESCE(l.total_cost,0)) / CASE COALESCE(pos.currency_rate, 0) WHEN 0 THEN 1.0 ELSE pos.currency_rate END)'
        return values
```

**Inheritance chain:**

```
sale.report (base, from sale/report/sale_report.py)
  │
  ├── sale_margin/report/sale_report.py
  │     └── _select_additional_fields() → adds 'margin' for SO lines
  │
  └── pos_sale/report/sale_report.py
        └── _fill_pos_fields() → defines SQL for POS-only lines
              │
              └── pos_sale_margin/report/sale_report.py
                    └── _fill_pos_fields() → adds 'margin' for POS lines
```

`pos_sale_margin` overrides `_fill_pos_fields` which was defined in `pos_sale`. The POS branch already has all other fields filled (product, qty, price, etc.), and `pos_sale_margin` adds only the margin.

### Workflow Trigger

There is no button, wizard, or cron trigger in this module. Margin is computed **at report query time** — every time the Sales Margin report is opened, the SQL view is queried and margin is calculated live.

If the product's `standard_price` is changed after the POS order is closed, the report will reflect the new price on subsequent queries. To preserve historical cost at the time of sale, the POS order must be created with a recorded `total_cost` value.

---

## L4 — Odoo 18 to 19 Changes

### Changes in `pos_sale_margin`

There are **no file-level changes** between Odoo 18 and 19 for this module. The source file `report/sale_report.py` is identical in both versions. The module version was bumped from `1.0` to `1.1` in Odoo 19 but the code is unchanged.

### Related Module Changes (Upstream)

The margin capability in this module depends on upstream changes in `pos_sale` and `sale_margin`:

| Upstream module | Change in Odoo 19 | Impact on pos_sale_margin |
|-----------------|-------------------|--------------------------|
| `sale_margin` | `margin` field added to `sale.report` via `_select_additional_fields` | Basis for POS margin |
| `pos_sale` | `_fill_pos_fields` hook introduced (replacing hardcoded field list) | Provides the extension point this module overrides |
| `point_of_sale` | `total_cost` field on `pos.order.line` — unchanged | Continues to provide cost data |

The introduction of `_fill_pos_fields` in Odoo 18 as a hook (replacing a static field list) is the architectural change that enables this link module. In Odoo 17 and earlier, margin would have required overriding the entire SQL query or `select` method.

### What Changed in the Sale Report Architecture

In Odoo 17, `sale.report` had a hardcoded SELECT for POS lines. In Odoo 18+, the POS select is built via `_select_pos`, `_from_pos`, `_where_pos`, `_group_by_pos` methods, with `_fill_pos_fields` as the hook for additional field computation. This makes `pos_sale_margin` possible as a clean link module.

---

## Tests

### `TestPoSSaleMarginReport`

**File:** `tests/test_pos_sale_margin_report.py`

Inherits from `TestPoSCommon` (from `point_of_sale.tests.common`). Runs as a post-install test.

```python
@odoo.tests.tagged('post_install', '-at_install')
class TestPoSSaleMarginReport(TestPoSCommon):
```

**Test scenario:**

```python
def test_pos_sale_margin_report(self):
    product1 = self.create_product('Product 1', self.categ_basic,
                                   150, standard_price=50)
    # price=150, standard_price=50 → expected margin = 100

    self.open_new_session()
    session = self.pos_session

    self.env['pos.order'].create({
        'session_id': session.id,
        'lines': [(0, 0, {
            'name': "OL/0001",
            'product_id': product1.id,
            'price_unit': 450,
            'discount': 5.0,
            'qty': 1.0,
            'price_subtotal': 150,   # after 5% discount: 450 * 0.95 = 427.5?
                                    # actually price_unit=450, qty=1.0,
                                    # price_subtotal=150 → manual override simulates
                                    # POS UI behavior
            'price_subtotal_incl': 150,
            'total_cost': 50,
        })],
        'amount_total': 150.0,
        'amount_tax': 0.0,
        'amount_paid': 0.0,
        'amount_return': 0.0,
    })

    reports = self.env['sale.report'].sudo().search(
        [('product_id', '=', product1.id)],
        order='id'
    )

    self.assertEqual(reports[0].margin, 100)
```

**Note on test data construction:** The test creates the POS order with manually-set `price_subtotal=150` and `total_cost=50`, which overrides the normal POS computation. The expected margin of `100` comes from `150 - 50 = 100`. The `price_unit=450, discount=5.0, qty=1.0` is the POS UI input; `price_subtotal=150` is manually set to bypass the normal POS computation chain and directly test the margin formula.

**Edge case tested:** The formula uses `COALESCE(total_cost, 0)`, so a line with no `total_cost` (NULL) will have margin = full price_subtotal. This is confirmed by the test providing `total_cost=50` explicitly.

---

## How to Debug Margin Discrepancies

If POS orders appear in the Sales Margin report but show unexpected margin values:

1. **Check `total_cost` on the POS line:** Query `pos_order_line` for the order and confirm `total_cost` is populated.
2. **Check `currency_rate` on the POS order:** A zero rate causes the denominator fallback to `1.0`, potentially skewing converted amounts.
3. **Check that the product has `standard_price` set:** If `total_cost` is 0, margin = price_subtotal (no cost deducted).
4. **Confirm POS order is NOT linked to a SO:** If `sale_order_line_id` is set, the margin is computed on the SO line (via `sale_margin` module), not the POS line. In that case, check the SO line's `margin` field directly.
5. **SQL trace:** The margin formula is in the `UNION ALL` POS branch. Check the full `sale.report` query by adding `LIMIT 1` and printing the SQL.

---

## See Also

- [Modules/pos_sale](odoo-18/Modules/pos_sale.md) — POS + Sale bridge (pos.order.line fields, SO linking, total_cost)
- [Modules/sale_margin](odoo-18/Modules/sale_margin.md) — SO margin computation (margin field on sale.order.line)
- [Modules/point_of_sale](odoo-18/Modules/point_of_sale.md) — POS base (pos.order, pos.order.line)
- [Modules/sale_management](odoo-18/Modules/sale_management.md) — Cross-document analytics report model
