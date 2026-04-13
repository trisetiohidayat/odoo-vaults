---
Module: sale_margin
Version: Odoo 18
Type: Extension
Tags: #odoo #odoo18 #sale #margin #profitability
Related Modules: [sale_management](odoo-18/Modules/sale_management.md), [sale](odoo-18/Modules/sale.md)
---

# sale_margin — Sales Order Margins

> Tracks profitability of sale order lines by computing the difference between sale price and cost (purchase price).

**Module:** `sale_margin`
**Depends:** `sale_management`
**Models Extended:** `sale.order.line`, `sale.order`, `sale.report`
**Source Path:** `~/odoo/odoo18/odoo/addons/sale_margin/`

---

## Overview

The `sale_margin` module adds margin computation to `sale.order.line` and aggregates those margins up to the `sale.order` level. Margin is defined as:

```
margin = sale_price_subtotal - (purchase_price × quantity)
margin_percent = margin / sale_price_subtotal × 100
```

---

## Models

### `sale.order.line` — EXTENDED

Added fields on `sale.order.line` for per-line profitability.

#### Fields

| Field | Type | Compute/Store | Description |
|-------|------|---------------|-------------|
| `margin` | `Float` | Compute + Store + Precompute | Absolute margin in the line's currency (sale_price - cost). Group: `base.group_user`. |
| `margin_percent` | `Float` | Compute + Store + Precompute | Margin percentage = `margin / price_subtotal`. Group: `base.group_user`. |
| `purchase_price` | `Float` | Compute + Store + Precompute | Cost used for margin calculation, expressed in the line's UoM and currency. Group: `base.group_user`. |

#### `_compute_purchase_price()`

```python
@api.depends('product_id', 'company_id', 'currency_id', 'product_uom')
def _compute_purchase_price(self):
    for line in self:
        if not line.product_id:
            line.purchase_price = 0.0
            continue
        line = line.with_company(line.company_id)
        # Convert cost from product's UoM to line's UoM
        product_cost = line.product_id.uom_id._compute_price(
            line.product_id.standard_price,
            line.product_uom,
        )
        line.purchase_price = line._convert_to_sol_currency(
            product_cost,
            line.product_id.cost_currency_id)
```

**Key behavior:**
- Uses `product.standard_price` as the cost basis — NOT `product.supplierinfo` vendor prices.
- UoM conversion: cost is first converted from the product's UoM to the line's `product_uom`.
- Currency conversion: converted from the product's `cost_currency_id` to the line's currency.
- `purchase_price` is `store=True, readonly=False, copy=False` — it CAN be manually overridden on the line.
- `precompute=True` means the value is computed at insertion time and stored; resave triggers recomputation.

**L4 — How `purchase_price` is determined:**
The module does NOT use `product.supplierinfo` for the default `purchase_price`. It strictly uses `product.standard_price` (the product's cost field on the Accounting tab). To use vendor-specific pricing, a user must manually enter a `purchase_price` override on the sale order line. This is a notable design choice — the margin is based on what the company pays internally, not supplier-specific contract pricing, unless manually overridden.

#### `_compute_margin()`

```python
@api.depends('price_subtotal', 'product_uom_qty', 'purchase_price')
def _compute_margin(self):
    for line in self:
        if line.qty_delivered and not line.product_uom_qty:
            # Line added from delivery (e.g., partially shipped backorder)
            calculated_subtotal = line.price_unit * line.qty_delivered
            line.margin = calculated_subtotal - (line.purchase_price * line.qty_delivered)
            line.margin_percent = calculated_subtotal and line.margin / calculated_subtotal
        else:
            line.margin = line.price_subtotal - (line.purchase_price * line.product_uom_qty)
            line.margin_percent = line.price_subtotal and line.margin / line.price_subtotal
```

**Key behavior:**
- Normal case: uses `product_uom_qty` (ordered quantity) × `purchase_price`.
- Special case: when `qty_delivered > 0` but `product_uom_qty == 0` (backordered partial delivery line), uses `qty_delivered` instead.
- `margin_percent` guards against division by zero (returns `False`/0 when `price_subtotal` is 0).
- Negative margins are fully supported.

---

### `sale.order` — EXTENDED

Aggregates line-level margins up to the order.

#### Fields

| Field | Type | Compute/Store | Description |
|-------|------|---------------|-------------|
| `margin` | `Monetary` | Compute + Store | Sum of all `order_line.margin` values. |
| `margin_percent` | `Float` | Compute + Store | `margin / amount_untaxed`. Aggregator: `avg`. |

#### `_compute_margin()`

```python
@api.depends('order_line.margin', 'amount_untaxed')
def _compute_margin(self):
    if not all(self._ids):
        for order in self:
            order.margin = sum(order.order_line.mapped('margin'))
            order.margin_percent = order.amount_untaxed and order.margin/order.amount_untaxed
    else:
        # Batch mode: single read_group for performance
        grouped_order_lines_data = self.env['sale.order.line']._read_group(
            [('order_id', 'in', self.ids)], ['order_id'], ['margin:sum'])
        mapped_data = {order.id: margin for order, margin in grouped_order_lines_data}
        for order in self:
            order.margin = mapped_data.get(order.id, 0.0)
            order.margin_percent = order.amount_untaxed and order.margin/order.amount_untaxed
```

**Performance optimization:** On single-record context (UI), iterates normally. On batch computation (e.g., at module install), uses `_read_group` for a single SQL query.

---

### `sale.report` — EXTENDED

Exposes margin in the Sales Analysis report.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `margin` | `Float` | Line margin, converted to company currency via `currency_rate`. |

#### `_select_additional_fields()`

```python
def _select_additional_fields(self):
    res = super()._select_additional_fields()
    res['margin'] = f"""SUM(l.margin
        / {self._case_value_or_one('s.currency_rate')}
        * {self._case_value_or_one('account_currency_table.rate')})
    """
    return res
```

Margin from `sale_order_line` is normalized to the report's currency via currency rate fields.

---

## L4: Margin at Confirmation vs. Order Time

### Order of Evaluation

`purchase_price` is computed when the line is created or when the product changes:

```
Line created → _compute_purchase_price() runs (precompute)
            → _compute_margin() runs (precompute)
```

`margin` and `margin_percent` are **precomputed** (stored at insert time) and **recomputed on any relevant field change** (`price_subtotal`, `product_uom_qty`, `purchase_price`).

### Margin Drift After Confirmation

Once a sale order is confirmed (`state = 'sale'`), margin is NOT automatically recalculated when `product.standard_price` changes. The stored `purchase_price` on each line reflects the cost at the time the line was last saved.

**To update margins after cost changes:**
1. Resave the sale order line (triggers `_compute_purchase_price` and `_compute_margin`).
2. Or manually set `purchase_price` on each line.

The test `test_sale_margin_order_copy` demonstrates this behavior — copying an order recomputes `purchase_price` from the current `standard_price`.

### Negative Margin

Fully supported. If `sale_price < purchase_price`, margin is negative. The test suite (`test_negative_margin`) verifies:
- Negative line margin: `-20.00` when sold at 20, cost at 40.
- `margin_percent` is then `-1.0` (-100%).
- Order-level aggregation sums negative values.

### Zero Cost

When `purchase_price = 0` (no cost set), `margin_percent = 1.0` (100%), meaning all revenue is profit. The test `test_margin_no_cost` confirms this edge case.

---

## L4: purchase_price Determination Deep Dive

The `_compute_purchase_price` method has a deliberate design: it uses `product.standard_price` exclusively. This is Odoo's internal cost, not the supplier cost.

### Flow

```
product.standard_price (in product's cost_currency_id, product's UoM)
        ↓
uom_id._compute_price(standard_price, line.product_uom)  [UoM conversion]
        ↓
_convert_to_sol_currency(cost, product.cost_currency_id)  [currency conversion]
        ↓
purchase_price (in line currency, line UoM)
```

### UoM Conversion Example

If a product's `standard_price = 100` (in `uom_unit = 1 unit`) and the sale order line uses `uom_dozen = 12 units`:

```
purchase_price = 100 × 12 = 1200  (cost per dozen)
```

### Currency Conversion Example

If a product's `cost_currency_id = USD` and the sale order's currency is `EUR`:

```
purchase_price_EUR = purchase_price_USD × (1 / currency_rate_USD_to_EUR)
```

### Manual Override

`purchase_price` is `store=True, readonly=False` — users CAN manually override it. This is critical for scenarios where:
- Vendor-specific pricing applies (not stored in `standard_price`)
- Internal transfer pricing differs from standard cost
- Consignment stock with different cost basis

---

## Constraints & Edge Cases

- Division by zero: `margin_percent` returns 0 when `price_subtotal` is zero.
- Negative `price_unit`: Supported (e.g., negative pricing lines), propagates to margin.
- Unstored lines (new records in UI): Precompute ensures store, but on unsaved records computation is skipped in batch mode.
- Lines from delivery with `product_uom_qty = 0`: Falls back to `qty_delivered` for margin calculation.
- `sale.report` margin is always in company currency after rate normalization.

---

## Relations

```python
sale.order.line (margin, margin_percent, purchase_price)
    ↑ aggregated by
sale.order (margin, margin_percent)
    ↑ source for
sale.report (margin)
```

No new relational fields added — only computed monetary and float fields on existing models.
