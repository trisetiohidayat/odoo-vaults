---
tags:
  - #odoo19
  - #modules
  - #sale
  - #margin
---

# sale_margin — Margins in Sales Orders

**Module:** `sale_margin`
**Technical Name:** `sale_margin`
**Category:** Sales/Sales
**Depends:** `sale_management`
**License:** LGPL-3
**Odoo Version:** 19.0

## Overview

The `sale_margin` module adds profitability analysis to Sales Orders by computing and storing the **margin** (profit) and **margin percentage** on both `sale.order` and `sale.order.line` records. It provides immediate visibility into profitability during the sales process by calculating the difference between the selling price and the purchase/cost price at the line level, then aggregating to the order level.

The module follows a **classical inheritance pattern** (`_inherit`) to extend three existing Odoo models:

| Model Extended | File | Purpose |
|---|---|---|
| `sale.order` | `models/sale_order.py` | Aggregate order-level margin (`margin`, `margin_percent`) |
| `sale.order.line` | `models/sale_order_line.py` | Line-level margin and cost (`margin`, `margin_percent`, `purchase_price`) |
| `sale.report` | `report/sale_report.py` | Sales analysis report with `margin` field for pivot/graph views |

---

## Module Structure

```
sale_margin/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── sale_order.py         # Extends sale.order — margin, margin_percent
│   └── sale_order_line.py    # Extends sale.order.line — margin, margin_percent, purchase_price
├── report/
│   ├── __init__.py
│   └── sale_report.py         # Extends sale.report — adds margin to SQL view
├── views/
│   └── sale_order_views.xml   # Form, pivot, graph view extensions
├── data/
│   └── sale_margin_demo.xml   # Demo data: sets purchase_price on existing demo SOLs
├── tests/
│   ├── __init__.py
│   └── test_sale_margin.py   # 5 test cases covering core scenarios
└── i18n/                      # Translations (38 languages + .pot)
```

---

## Model: sale.order.line

**File:** `models/sale_order_line.py`
**Inheritance:** `_inherit = "sale.order.line"` (classical extension — no new table, adds fields only)

### All Fields

#### `purchase_price` — Cost (Editable Cost Price)

```python
purchase_price = fields.Float(
    string="Cost",
    compute="_compute_purchase_price",
    min_display_digits='Product Price',
    store=True,
    readonly=False,
    copy=False,
    precompute=True,
    groups="base.group_user"
)
```

| Attribute | Value | Purpose |
|---|---|---|
| Type | `fields.Float` | Raw float; cost expressed in SOL currency, not Monetary |
| Compute | `_compute_purchase_price` | Automatically populated from product cost |
| Store | `True` | Persisted — critical for margin accuracy even if product cost changes later |
| Readonly | `False` | **User-editable** — allows manual override of product cost on the line |
| Copy | `False` | Cost is **not copied** when duplicating a line (cost may differ on new order) |
| Precompute | `True` | Computed eagerly at record creation before DB write |
| Groups | `base.group_user` | All internal users can view/edit |
| String | `"Cost"` | Displayed as "Cost" in the UI |

#### `margin` — Line Margin

```python
margin = fields.Float(
    "Margin",
    compute='_compute_margin',
    min_display_digits='Product Price',
    store=True,
    groups="base.group_user",
    precompute=True
)
```

| Attribute | Value | Purpose |
|---|---|---|
| Type | `fields.Float` | Absolute profit amount in SOL currency |
| Compute | `_compute_margin` | `price_subtotal - (purchase_price * qty)` |
| Store | `True` | Persisted for fast list view / reporting |
| Precompute | `True` | Eagerly computed at creation |
| Groups | `base.group_user` | Visible to all internal users |

#### `margin_percent` — Line Margin Percentage

```python
margin_percent = fields.Float(
    "Margin (%)",
    compute='_compute_margin',
    store=True,
    groups="base.group_user",
    precompute=True
)
```

| Attribute | Value | Purpose |
|---|---|---|
| Type | `fields.Float` | Decimal ratio (e.g., `0.30` = 30%); **not stored as percentage integer** |
| Compute | `_compute_margin` | `margin / price_subtotal` |
| Store | `True` | Persisted for reporting |
| Precompute | `True` | Eagerly computed |

---

### Method: `_compute_purchase_price`

```python
@api.depends('product_id', 'company_id', 'currency_id', 'product_uom_id')
def _compute_purchase_price(self):
    for line in self:
        if not line.product_id:
            line.purchase_price = 0.0
            continue
        line = line.with_company(line.company_id)

        # Convert the cost to the line UoM
        product_cost = line.product_id.uom_id._compute_price(
            line.product_id.standard_price,
            line.product_uom_id,
        )

        line.purchase_price = line._convert_to_sol_currency(
            product_cost,
            line.product_id.cost_currency_id)
```

#### Purchase Price Source (L4: Source Analysis)

The `purchase_price` is sourced from a **strict cascade** — there is **no supplierinfo fallback** in `sale_margin` CE:

```
purchase_price (field value)
  │
  ├── If user has manually overridden it on the line (field is not readonly)
  │   → Use manually entered value (persisted as-is)
  │   → Will be overwritten if product_id changes (triggers recompute)
  │
  └── If empty or product_id changes → Compute from product:
          1. product.standard_price  (variant-level cost, stored on product.product)
          │
          2. UoM conversion:
          │   product.uom_id (product's default UoM)
          │     → _compute_price(to=line.product_uom_id)
          │   Example: product cost in "Units" (uom_id), line in "Dozens" (product_uom_id)
          │
          3. Currency conversion:
          │   product.cost_currency_id (currency in which standard_price is stored)
          │     → _convert_to_sol_currency(to=line.currency_id)
          │   Handles multi-currency SOs where product costs are in a different currency
          │
          4. Company context (with_company)
              → Ensures correct multi-company cost reading
```

**Key insight on `standard_price` vs supplier info:** `sale_margin` CE only reads `product.standard_price`. It does **not** check `product.seller_ids` (supplierinfo) for a vendor-specific cost. The `purchase_price` therefore reflects the product's internal/standard cost, not the best vendor price. This is the **primary cost** for margin calculation in the base module. Extensions like `sale_purchase` or custom modules can override `_compute_purchase_price` to pull from supplierinfo when the SO has a specific vendor.

**`with_company` call:** Ensures that `standard_price` is read in the correct company context — relevant in multi-company setups where product costs may differ per company (via `product.company_id` restrictions).

#### `_convert_to_sol_currency` Method (parent model)

Defined in `sale_order_line.py` (line ~1703 of the `sale` module):

```python
def _convert_to_sol_currency(self, amount, currency):
    self.ensure_one()
    to_currency = self.currency_id or self.order_id.currency_id
    if currency and to_currency and currency != to_currency:
        conversion_date = self.order_id.date_order or fields.Date.context_today(self)
        company = self.company_id or self.order_id.company_id or self.env.company
        return currency._convert(
            from_amount=amount,
            to_currency=to_currency,
            company=company,
            date=conversion_date,
        )
    return amount
```

Uses `date_order` as the conversion date (the SO date), not today's date, ensuring historical consistency.

---

### Method: `_compute_margin`

```python
@api.depends('price_subtotal', 'product_uom_qty', 'purchase_price')
def _compute_margin(self):
    for line in self:
        # Find alternative calculation when line is added to order from delivery
        if line.qty_delivered and not line.product_uom_qty:
            calculated_subtotal = line.price_unit * line.qty_delivered
            line.margin = calculated_subtotal - (line.purchase_price * line.qty_delivered)
            line.margin_percent = calculated_subtotal and line.margin / calculated_subtotal
        else:
            line.margin = line.price_subtotal - (line.purchase_price * line.product_uom_qty)
            line.margin_percent = line.price_subtotal and line.margin / line.price_subtotal
```

#### Dual Calculation Path (L3: Workflow Trigger / Failure Mode)

**Dependency chain:**
```
order_line.margin
  └── price_subtotal  — tax-excluded subtotal (price_unit * qty * (1 - discount/100))
  └── product_uom_qty — ordered quantity
  └── purchase_price   — cost per unit (possibly manually overridden)
       └── product_id.standard_price
       └── product_id.cost_currency_id
       └── product_uom_id (UoM conversion)
       └── currency_id (FX conversion)
```

**Path A — Normal path** (`product_uom_qty` is non-zero):
```
margin = price_subtotal - (purchase_price * product_uom_qty)
margin_percent = price_subtotal and margin / price_subtotal
```

**Path B — Delivered-only path** (`qty_delivered > 0` AND `product_uom_qty == 0`):
```
calculated_subtotal = price_unit * qty_delivered
margin = calculated_subtotal - (purchase_price * qty_delivered)
margin_percent = calculated_subtotal and margin / calculated_subtotal
```
- Triggered when a line is added to a confirmed sale order **from stock delivery** (e.g., via `stock.move` creating a `sale.order.line` on an existing SO)
- `product_uom_qty` can be `0` while `qty_delivered` is non-zero (downshipment or manual stock move scenario)
- The denominator switches to `calculated_subtotal` since `price_subtotal` would be `0` in this case

#### Line-Level Edge Cases (L3: Failure Mode)

| Scenario | margin | margin_percent | Notes |
|---|---|---|---|
| No product (`product_id = False`) | `purchase_price = 0`, margin = `price_subtotal` | `1.0` if subtotal != 0 | Section/notes lines |
| `purchase_price = 0` | Equal to `price_subtotal` | `1.0` (100%) | Free/zero-cost product |
| Negative `purchase_price` | Margin can exceed `price_subtotal` | `> 1.0` | Rare vendor rebate scenario |
| Negative `price_unit` (credit) | Deeply negative margin | Deeply negative | Credit note / return line |
| `price_subtotal = 0`, `purchase_price > 0` | Negative (cost with no revenue) | `False` (guarded) | Free/discount lines |
| `qty_delivered > 0, product_uom_qty = 0` | Uses delivered qty | Uses calculated subtotal | Delivery-added lines |

---

## Model: sale.order

**File:** `models/sale_order.py`
**Inheritance:** `_inherit = "sale.order"` (classical extension)

### All Fields

#### `margin` — Order Margin

```python
margin = fields.Monetary("Margin", compute='_compute_margin', store=True)
```

| Attribute | Value | Purpose |
|---|---|---|
| Type | `fields.Monetary` | Currency-aware float using `currency_id` from the order |
| Compute | `_compute_margin` | Sum of all line margins |
| Store | `True` | Persisted to database |
| String | `"Margin"` | Display label |

Uses `fields.Monetary` (not `fields.Float`) so the margin is formatted with the correct currency symbol and decimal precision matching the order's currency.

#### `margin_percent` — Order Margin Percentage

```python
margin_percent = fields.Float(
    "Margin (%)",
    compute='_compute_margin',
    store=True,
    aggregator="avg"
)
```

| Attribute | Value | Purpose |
|---|---|---|
| Type | `fields.Float` | Decimal ratio (e.g., `0.30` for 30%) |
| Compute | `_compute_margin` | Same method as `margin` |
| Store | `True` | Persisted |
| Aggregator | `"avg"` | Enables pivot view to compute average margin % across order lines |

The `aggregator="avg"` is specifically for the pivot view's `read_group` mechanism — it allows the pivot to compute the average `margin_percent` when grouping orders together.

---

### Method: `_compute_margin`

```python
@api.depends('order_line.margin', 'amount_untaxed')
def _compute_margin(self):
    if not all(self._ids):
        for order in self:
            order.margin = sum(order.order_line.mapped('margin'))
            order.margin_percent = order.amount_untaxed and order.margin / order.amount_untaxed
    else:
        # On batch records recomputation (e.g. at install), compute the margins
        # with a single read_group query for better performance.
        grouped_order_lines_data = self.env['sale.order.line']._read_group(
            [('order_id', 'in', self.ids)],
            ['order_id'], ['margin:sum'])
        mapped_data = {order.id: margin for order, margin in grouped_order_lines_data}
        for order in self:
            order.margin = mapped_data.get(order.id, 0.0)
            order.margin_percent = order.amount_untaxed and order.margin / order.amount_untaxed
```

**Dependencies:** `@api.depends('order_line.margin', 'amount_untaxed')`

- `order_line.margin` — triggers recompute when any line's margin changes
- `amount_untaxed` — denominator for margin percentage; `0 and ...` short-circuit prevents division by zero

#### Dual-Path Computation Strategy (L3: Performance / Override Pattern)

The method implements **two distinct code paths** based on whether all records in `self` have persisted database IDs:

**Path 1 — Unsaved / Single-Record / Onchange (`not all(self._ids)`):**
- Iterates order-by-order using `mapped()`
- Safe for new records not yet persisted to the database
- Used in onchange contexts where data may not be committed
- `order_line.mapped('margin')` triggers ORM to compute each line's margin individually

**Path 2 — Batch / Existing Records (`all(self._ids)`):**
- Uses `_read_group` (SQL `GROUP BY`) with a single database query to aggregate all line margins at once
- Reduces N queries to 1 query when computing margins for many orders simultaneously
- Used at module install, during pivot/report generation, or when loading list views with many orders
- Example: Computing margins for 100 orders triggers 1 SQL query instead of 100 `mapped()` calls

#### Order-Level Edge Cases (L3: Failure Mode)

| Scenario | margin | margin_percent | Notes |
|---|---|---|---|
| No order lines | `0.0` | `0.0` or `False` | `sum([]) = 0`, short-circuit guards |
| `amount_untaxed = 0` | Numeric (sum of negative costs) | `False` | Short-circuit `0 and ...` prevents division |
| All lines with `price_subtotal = 0` | Based on `purchase_price * qty` | `False` or extreme | Zero-revenue order |
| Negative total (credit note style) | Numeric; can be negative | Can exceed 1.0 or be negative | Returns/credits |
| Foreign currency SO | Expressed in order's currency | Ratio is currency-independent | Both numerator and denominator in same currency |

---

## Model: sale.report

**File:** `report/sale_report.py`
**Inheritance:** `_inherit = 'sale.report'` (adds margin to the auto-generated SQL report table)

### Field: `margin`

```python
margin = fields.Float('Margin')
```

**Non-stored field.** Added to the `sale.report` model (a `._auto = False` SQL view) by overriding `_select_additional_fields` to append margin to the `SELECT` clause.

### Method: `_select_additional_fields` (Override)

```python
def _select_additional_fields(self):
    res = super()._select_additional_fields()
    res['margin'] = f"""SUM(l.margin
        / {self._case_value_or_one('s.currency_rate')}
        * {self._case_value_or_one('account_currency_table.rate')})
    """
    return res
```

The margin is aggregated with **currency normalization** — dividing by the sale order's `currency_rate` and multiplying by the company currency's rate ensures the margin is expressed in the **company's reporting currency** regardless of the SO's currency.

### `_case_value_or_one` Helper

```python
def _case_value_or_one(self, value):
    return f"""CASE COALESCE({value}, 0) WHEN 0 THEN 1.0 ELSE {value} END"""
```

Prevents division by zero when `currency_rate` or account currency `rate` is NULL. If NULL, the divisor is treated as `1.0`, effectively skipping the conversion.

---

## Views

**File:** `views/sale_order_views.xml`

### Form View Extension (`sale_margin_sale_order`)

Inherits `sale.view_order_form` with `priority="15"` (lower than default so it loads after the parent):

```xml
<!-- Inserts margin display block after tax_totals (tax summary) -->
<field name="tax_totals" position="after">
    <div class="d-flex float-end" colspan="2">
        <label for="margin"/>
        <div>
            <field name="margin" class="oe_inline"/>
            <field name="amount_untaxed" invisible="1"/>
            <span class="oe_inline" invisible="amount_untaxed == 0">
                (<field name="margin_percent" nolabel="1" class="oe_inline" widget="percentage"/>)
            </span>
        </div>
    </div>
</field>

<!-- Adds purchase_price field inside line form (after price_unit) -->
<xpath expr="//field[@name='order_line']//form//field[@name='price_unit']" position="after">
    <field name="purchase_price" groups="base.group_user"/>
</xpath>

<!-- Adds purchase_price, margin, margin_percent to line list view -->
<xpath expr="//field[@name='order_line']//list//field[@name='price_unit']" position="after">
    <field name="purchase_price" optional="hide"/>
    <field name="margin" optional="hide"/>
    <field name="margin_percent"
        invisible="price_subtotal == 0"
        optional="hide" widget="percentage"/>
</xpath>
```

**Key UI decisions:**
- `purchase_price`, `margin`, `margin_percent` are all `optional="hide"` in list view — hidden by default, user can show via column selector
- `margin_percent` is `invisible="price_subtotal == 0"` — hides % when no revenue (avoids showing 100% or infinite % on zero-value lines)
- `widget="percentage"` renders `0.30` as `30%` in the UI
- `amount_untaxed` is made invisible but referenced to control the `invisible` attribute on the % span

### Pivot View Extension (`sale_margin_sale_order_pivot`)

```xml
<record id="sale_margin_sale_order_pivot" model="ir.ui.view">
    <field name="name">sale.order.margin.view.pivot</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_sale_order_pivot"/>
    <field name="arch" type="xml">
        <pivot position="inside">
            <field name="margin_percent" invisible="1"/>
        </pivot>
    </field>
</record>
```

Makes `margin_percent` available in the pivot's "Measures" dropdown without showing it as a default column.

### Graph View Extension (`sale_margin_sale_order_graph`)

Same pattern as pivot — `margin_percent` added to field list but hidden by default for use as a graph measure.

---

## Demo Data

**File:** `data/sale_margin_demo.xml` (loaded with `noupdate="1"` on `<odoo>` root)

Sets `purchase_price` on **existing** sale order lines from the `sale` module's demo data (external IDs like `sale.sale_order_line_1`, etc.):

```xml
<record id="sale.sale_order_line_1" model="sale.order.line">
    <field name="purchase_price">2870.00</field>
</record>
<record id="sale.sale_order_line_2" model="sale.order.line">
    <field name="purchase_price">126.00</field>
</record>
<!-- ... 7 more lines ... -->
```

This overrides the computed `purchase_price` for demo records with hardcoded cost values, ensuring demo sale orders show meaningful, realistic margin figures when `sale_margin` is installed in demo mode. The `noupdate="1"` ensures demo data is loaded at install but not overwritten on subsequent upgrades.

---

## Tests

**File:** `tests/test_sale_margin.py`

Five test cases covering the full range of margin scenarios:

### `test_sale_margin`
Sets product cost to 700, order line at 1000/unit x 10 units. After `action_confirm`, expects:
- `order.margin = 3000.00` (300 per unit x 10)
- `order.margin_percent = 0.3` (30%)

### `test_negative_margin`
Tests both a negative per-unit margin and a zero-cost negative revenue line:
- Service product: cost 40, price 20 → margin = -20, margin_percent = -1 (-100%)
- Product line: cost 0, price -100 → margin = -100, margin_percent = 1 (100% — full revenue is loss)
- Order total: margin = -120, margin_percent = 1.5 (150% — total revenue deficit)

### `test_margin_no_cost`
When cost is 0 (product not yet costed), margin equals full subtotal and margin_percent = 100%:
- `purchase_price = 0`, price = 70, qty = 1
- margin = 70, margin_percent = 1.0

### `test_margin_considering_product_qty`
Tests multi-quantity lines with mixed positive/negative margins:
- 3 units at 100 price, 50 cost → margin = 150, percent = 0.5 (50%)
- 1 unit at -50 price, 0 cost → margin = -50, percent = 1.0 (100% of negative revenue)
- Order total: margin = 100, percent = 0.4 (40%)

### `test_sale_margin_order_copy`
Verifies that when a sale order is copied, the `purchase_price` is **recomputed** from the product's current cost (not copied from the original):
- Original: cost 500, price 1000 x 10 → margin = 5000, percent = 50%
- Product cost changes to 750
- Copied order: cost = 750 (recomputed), price 1000 x 10 → margin = 2500, percent = 25%

---

## L3 Escalation: Cross-Module Integration Points

### Integration with `sale` Module

- `sale.order` already provides `amount_untaxed` computed from line `price_subtotal` values
- `sale.order.line` provides `price_subtotal` (tax-excluded: `price_unit * qty * (1 - discount/100)`)
- `sale.report` is an auto-generated SQL view (`_auto = False`); `sale_margin` extends its `SELECT` clause

### Integration with `sale_management` Module

The module depends on `sale_management` (not just `sale`), which provides the standard sale order form with `order_line` one2many. This ensures the XPath targets in `sale_order_views.xml` are present.

### Integration with `stock` / Delivery Orders

The alternate calculation path in `_compute_margin` (lines 42-45) handles lines added to SOs **from stock delivery**:
- When a `stock.move` is confirmed and creates a `sale.order.line` on an existing SO, `product_uom_qty` may be `0` while `qty_delivered` is set
- The formula gracefully switches to `qty_delivered`-based calculation using `price_unit * qty_delivered` as the subtotal

### Invoice Update Triggers

Margin recomputation is triggered automatically via `@api.depends` whenever:
1. **`price_subtotal` changes** — on write to `price_unit`, `discount`, `product_uom_qty`, or tax configuration
2. **`purchase_price` changes** — on write to `product_id`, `company_id`, `currency_id`, `product_uom_id`, or when product `standard_price` changes (for non-overridden lines)
3. **`amount_untaxed` changes** — order-level when any line subtotal changes

There is **no special invoice hook**. Margin tracks the **ordered/selling price vs. purchase cost**, not the invoiced amounts. If invoicing differs from ordering (partial invoicing, discounts applied at invoice level), margin remains based on the order line values.

---

## L4: Performance Implications

### Batch Computation Optimization in `_compute_margin` (sale.order)

The dual-path design is a deliberate **performance optimization**:

| Scenario | Mechanism | Query Count |
|---|---|---|
| Single order / onchange | `for order in self: sum(order.order_line.mapped('margin'))` | N+1 (1 per order) |
| Batch (module install, list view) | `_read_group` with SQL `GROUP BY` | 1 SQL query for all orders |

The `_read_group` path uses a single `SELECT order_id, SUM(margin) FROM sale_order_line WHERE order_id IN (...) GROUP BY order_id` query instead of N separate ORM reads.

### `precompute=True` on Line Fields

Both `purchase_price`, `margin`, and `margin_percent` on `sale.order.line` use `precompute=True`:
- Fields are computed **at record creation** (during `create()` or `new()`), not lazily on first read
- Reduces on-demand compute overhead when creating orders programmatically (e.g., via `Command.create`)
- Particularly important in the test suite and when importing orders via `Command` batches

### Stored Fields on Order Level

`margin` and `margin_percent` on `sale.order` are stored (`store=True`):
- Allows sorting and filtering in list views without recomputing
- Enables the pivot view to aggregate without hitting live computed values
- Trade-off: must recompute when any line changes (dependency on `order_line.margin`)

### `aggregator="avg"` on `margin_percent`

This enables the pivot view's `read_group` to compute **average margin %** across groups (orders, salespeople, dates). Without it, the pivot would either fail to aggregate or produce incorrect results when grouping by multiple orders.

---

## L4: Currency Handling

### Three-Currency Problem

The margin computation handles **three potentially different currencies**:

```
Product standard_price
  └── Stored in product.cost_currency_id
  └── Typically = company currency, but can differ

Sale Order Line
  └── currency_id = SO's pricelist currency (or line-specific currency)
  └── product_uom_id may differ from product's uom_id

Sale Order
  └── currency_id = SO's currency for display
```

### Conversion Flow in `_compute_purchase_price`

```
product.standard_price (in product.cost_currency_id)
  │
  ├── Step 1: UoM Conversion
  │   product.uom_id → line.product_uom_id
  │   product_cost = product.uom_id._compute_price(standard_price, line.product_uom_id)
  │
  └── Step 2: Currency Conversion
      product.cost_currency_id → line.currency_id (SOL currency)
      purchase_price = _convert_to_sol_currency(product_cost, product.cost_currency_id)
```

### Currency in `sale.report`

The `sale.report`'s margin SQL normalizes to **company currency**:
```sql
SUM(l.margin / s.currency_rate * account_currency_table.rate)
```
This divides by the SO's currency rate (to normalize to company's base currency unit) and multiplies by the company's currency rate. Enables reporting across SOs in different currencies on a single pivot/graph.

---

## L4: Historical Changes (Odoo 18 to 19)

### Changes in Odoo 19

1. **`purchase_price` gained `precompute=True`:**
   - In Odoo 18, `purchase_price` may not have had `precompute=True`
   - In Odoo 19, it uses `precompute=True` for eager computation at record creation, aligning with Odoo's general push toward precomputing stored computed fields

2. **`aggregator="avg"` added to `margin_percent` on `sale.order`:**
   - Enables pivot view to compute average margin % across order lines
   - Used by the pivot view extensions in `sale_order_views.xml`

3. **`min_display_digits='Product Price'` added:**
   - Controls minimum significant digits displayed, inheriting from the `Product Price` decimal precision configuration

4. **`groups="base.group_user"` consistently applied:**
   - All three fields on `sale.order.line` explicitly set `groups="base.group_user"`
   - `margin` and `margin_percent` on `sale.order` have no groups restriction — visible to anyone with SO access

5. **`copy=False` on `purchase_price`:**
   - Explicitly prevents copying cost when duplicating a line
   - Ensures the new line recomputes its cost from the product (which may have changed)

6. **Demo data (`sale_margin_demo.xml`) now uses `noupdate="1`:**
   - Demo data is loaded at install but not overwritten on subsequent upgrades

### About Supplier Info as Cost Source

In Odoo 19 CE `sale_margin`, **`purchase_price` does not automatically use supplierinfo**. The only cost source is `product.standard_price`. To use vendor-specific costs (e.g., the price from `product.seller_ids` based on the order's vendor), a custom module must override `_compute_purchase_price`. The `purchase_price` field is explicitly `readonly=False`, allowing users to manually enter a vendor-specific cost per line, but the CE module does not automate this from `seller_ids`.

---

## L4: Security Considerations

### Field-Level Security

All three fields on `sale.order.line` use `groups="base.group_user"`:

```python
margin = fields.Float(..., groups="base.group_user")
margin_percent = fields.Float(..., groups="base.group_user")
purchase_price = fields.Float(..., groups="base.group_user")
```

- `base.group_user` = all internal employees
- **Portal and public users cannot see cost/margin data** by default
- **`sale.order` level fields (`margin`, `margin_percent`) have no `groups` restriction** — they are visible to anyone who can access the sale order (subject to standard record rules)
- `purchase_price` is restricted because revealing cost exposes supplier pricing

### ACL Notes

`sale_margin` does **not** ship its own `security/ir.model.access.csv`. Access rights are inherited from the `sale` module's ACLs for `sale.order` and `sale.order.line`.

### Sensitive Data Exposure Risk

- `purchase_price` is commercially sensitive — the cost of goods
- Can be further restricted to sales managers by changing to: `groups="sales_team.group_sale_manager"`
- The view XML uses `groups="base.group_user"` by default, easily changed in a custom module

---

## Limitations

1. **Standard Price Only**: Uses `standard_price`, not actual purchase order cost or supplierinfo
2. **No Landed Costs**: Does not include shipping, duties, insurance, or other landed costs
3. **Ordered Quantity Basis**: Margin calculated on ordered qty, not invoiced or delivered qty (unless line was added from delivery with `product_uom_qty = 0`)
4. **No Historical Cost Tracking**: If product cost changes after order creation, margins on existing orders are unaffected (stored values)
5. **Invoice vs. Order Divergence**: If invoice-level discounts are applied that differ from the order line, margin on the order does not reflect invoice adjustments
6. **No Margin by Salesperson**: `sale_margin` does not allocate margin to salespeople for commission calculations

---

## See Also

- [Modules/Sale](Modules/Sale.md) — Parent `sale.order` and `sale.order.line` models
- [Modules/Product](Modules/Product.md) — `standard_price`, `cost_currency_id`, `uom_id` fields used in cost computation
- [Patterns/Inheritance Patterns](Patterns/Inheritance Patterns.md) — Classical `_inherit` extension pattern
- [Core/Fields](Core/Fields.md) — `fields.Monetary`, `fields.Float` with `precompute`, `store`, `aggregator` attributes
- [Core/API](Core/API.md) — `@api.depends`, computed field patterns
- [Patterns/Security Patterns](Patterns/Security Patterns.md) — Field-level `groups` security
- [New Features/What's New](New Features/What's New.md) — Odoo 19 new features overview
