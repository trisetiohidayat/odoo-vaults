# sale_margin - Margins in Sales Orders

**Module:** `sale_margin`
**Depends:** `sale_management`
**Category:** Sales/Sales

---

## Purpose

Adds margin and cost price visibility to sale orders. Computes per-line and per-order profit margins by comparing `price_subtotal` against the product's cost (purchase_price). Provides margin reporting via the sale report.

---

## Models

### sale.order Extension

**File:** `models/sale_order.py`

| Field | Type | Description |
|---|---|---|
| `margin` | `Monetary` | Sum of all line margins (computed) |
| `margin_percent` | `Float` | `margin / amount_untaxed` as percentage (computed) |

**Computation:**

```python
@api.depends('order_line.margin', 'amount_untaxed')
def _compute_margin(self):
    for order in self:
        order.margin = sum(order.order_line.mapped('margin'))
        order.margin_percent = order.amount_untaxed and order.margin / order.amount_untaxed
```

**Optimization:** When all `self._ids` are set (batch computation), uses a single `read_group` query for performance.

---

### sale.order.line Extension

**File:** `models/sale_order_line.py`

| Field | Type | Description |
|---|---|---|
| `margin` | `Float` | `price_subtotal - (purchase_price * product_uom_qty)` (stored, precompute) |
| `margin_percent` | `Float` | `price_subtotal and margin / price_subtotal` (stored, precompute) |
| `purchase_price` | `Float` | Cost price in company currency (stored, compute) |

**`purchase_price` Computation:**

```python
@api.depends('product_id', 'company_id', 'currency_id', 'product_uom')
def _compute_purchase_price(self):
    for line in self:
        if not line.product_id:
            line.purchase_price = 0.0
            continue
        line = line.with_company(line.company_id)
        # Convert product cost to line UoM
        product_cost = line.product_id.uom_id._compute_price(
            line.product_id.standard_price,
            line.product_uom,
        )
        # Convert to SOL currency
        line.purchase_price = line._convert_to_sol_currency(
            product_cost,
            line.product_id.cost_currency_id
        )
```

**`margin` Computation:**

```python
@api.depends('price_subtotal', 'product_uom_qty', 'purchase_price')
def _compute_margin(self):
    for line in self:
        # Handle delivery-based lines (inverse flow from delivery)
        if line.qty_delivered and not line.product_uom_qty:
            calculated_subtotal = line.price_unit * line.qty_delivered
            line.margin = calculated_subtotal - (line.purchase_price * line.qty_delivered)
            line.margin_percent = calculated_subtotal and line.margin / calculated_subtotal
        else:
            line.margin = line.price_subtotal - (line.purchase_price * line.product_uom_qty)
            line.margin_percent = line.price_subtotal and line.margin / line.price_subtotal
```

**Field Groups:** All three fields (`margin`, `margin_percent`, `purchase_price`) have `groups="base.group_user"` - visible only to internal users, not portal.

**Precompute:** Fields use `precompute=True` for performance.

---

## Purchase Price Sources

The `purchase_price` (cost) is sourced in priority order:

1. **Product standard_price** (`product.product.standard_price` / `product.template.standard_price`)
   - Converted from product's UoM to SOL's product_uom
   - Converted from product's cost_currency_id to SOL's currency_id

2. **No supplier price lookup** - unlike earlier versions, `sale_margin` does NOT look at `product.supplierinfo` for cost. The standard_price is used directly.

3. **Manual override** - the `purchase_price` field is `readonly=False`, so users can manually adjust cost per line.

---

## Margin Report

**File:** `report/sale_report.py`

Extends the base `sale.report` model (which is a read-only SQL view):

| Field | Type | Description |
|---|---|---|
| `margin` | `Float` | Sale order line margin in company currency |

**Override:**

```python
def _select_additional_fields(self):
    res = super()._select_additional_fields()
    res['margin'] = f"""SUM(l.margin
        / {self._case_value_or_one('s.currency_rate')}
        * {self._case_value_or_one('account_currency_table.rate')})
    """
    return res
```

The margin is aggregated from SOL lines, converted from SOL currency to company currency using rates.

---

## View Integration

**File:** `views/sale_order_views.xml`

The margin fields are displayed in:
- Sale order form view (header)
- Sale order line tree/form view
- Sale report (reporting)

---

## Limitations and Notes

1. **Stored fields** - `margin`, `margin_percent`, and `purchase_price` are stored in the database (`store=True` implied by precompute). This means they are computed once and stored, and must be recomputed when cost or price changes.

2. **No automatic recompute on price change** - the `precompute` flag means computation happens at write/create time. If `standard_price` changes after the SO is confirmed, existing lines retain their stored `purchase_price` unless manually updated.

3. **Delivery-based lines** - when `qty_delivered > 0` and `product_uom_qty = 0` (lines added from delivery), the margin uses `qty_delivered` instead of `product_uom_qty` to handle inverse flows.

4. **Currency conversion** - both `purchase_price` and `margin` are converted to the order's currency. The order-level `margin` is in the order's currency.

5. **Security** - all margin fields have `groups="base.group_user"` so they are hidden from portal users.

6. **Precompute** - these fields are precomputed, meaning they are computed in batch during create/write. They cannot depend on context-dependent values (like `self.env.company` changes).

---

## Dependencies

```
sale_management
  └── sale_margin
```

Auto-installed with `sale_management` in standard installations.

---

## Key Differences from Odoo 17

In Odoo 17 and earlier, `purchase_price` used `seller_ids` (supplierinfo) to look up cost from vendor prices. In Odoo 18, the cost is derived purely from `standard_price`. This makes the module simpler but means vendor-specific pricing requires separate configuration.