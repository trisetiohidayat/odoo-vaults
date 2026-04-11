---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #sale
  - #expense
  - #margin
module: sale_expense_margin
description: When re-invoicing an expense on a Sales Order, sets the cost on the SOL to the total untaxed amount of the expense, giving accurate margin computation.
odoo_version: "19"
depends:
  - sale_expense
  - sale_margin
auto_install: true
category: Sales/Sales
license: LGPL-3
---

# Sale Expense Margin

## L1: How Expense Affects Sale Margin

### Core Business Logic

`sale_expense_margin` is a **bridge module** that connects two independently useful modules — `sale_expense` and `sale_margin` — to produce accurate margin figures when expenses are re-invoiced through a Sales Order.

The chain of events without this module:

```
HR Expense posted (linked to SO)
  → sale_expense creates new SOL for each expense line
  → SOL.purchase_price = 0.0 (or product.standard_price)
  → margin = price_subtotal - (qty * 0) = INFLATED margin
```

The chain with this module:

```
HR Expense posted (linked to SO)
  → sale_expense creates new SOL for each expense line
  → sale_expense_margin._compute_purchase_price()
      extracts expense.untaxed_amount_currency / quantity
  → SOL.purchase_price = real expense unit cost
  → margin = price_subtotal - (qty * real_cost) = ACCURATE margin
```

### What "Margin" Means Here

Margin on a `sale.order.line` is defined as:

```
margin = price_subtotal - (qty_delivered * purchase_price)
```

When an expense is re-invoiced:
- `price_subtotal` = what the customer pays (from expense product's sales price or the amount entered on the expense)
- `purchase_price` = what the company spent (the expense's untaxed amount)
- `qty_delivered` = the expense quantity

### Expense Re-invoice Flow (Full Picture)

```
1. Employee submits expense with sale_order_id set
   (hr_expense, sale_expense modules)

2. Manager approves expense (hr_expense workflow)

3. expense.action_post() is called
   → Creates a vendor bill (account.move in 'in_invoice' state)
   → Calls _create_sale_order_line() for each expense line
   → sale_expense creates SOL(s) linked via expense_id

4. sale_expense_margin._compute_purchase_price() fires
   → Computes unit cost = expense.untaxed_amount_currency / expense.quantity
   → Converts to SOL's currency via _convert_to_sol_currency()
   → Sets SOL.purchase_price

5. margin and margin_percent compute correctly on the SO
```

### Two Types of Expense Lines on the SOL

When an expense is re-invoiced, the SOL contains **two kinds of lines**:

| Line | `is_expense` | `expense_id` | `purchase_price` source |
|------|-------------|--------------|----------------------|
| Original product line (e.g., product with `expense_policy='sales_price'`) | `False` | `False` | `product.standard_price` |
| Expense-specific lines created by `sale_expense` | `True` | Set | `expense.untaxed_amount_currency / quantity` |

### Tax Handling

The module uses `untaxed_amount_currency` (not `total_amount_currency`). This is intentional: margin should reflect the pre-tax cost, matching how `price_subtotal` is the pre-tax selling price. If tax were included, the margin would appear lower than it truly is at the transaction level.

---

## L2: Field Types, Defaults, Constraints

### Extended Model: `sale.order.line`

**File:** `models/sale_order_line.py`

#### Field: `expense_id`

```python
expense_id = fields.Many2one('hr.expense', string='Expense')
```

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `comodel` | `hr.expense` | Links back to the originating expense record |
| `string` | `'Expense'` | Display label in the form view |
| Type | `Many2one` | Many expense lines can exist; each SOL expense line points to exactly one expense |

This field is the **anchor** for the entire module. It is set by `sale_expense` when it creates the SOL, and `sale_expense_margin` uses it to find the expense's cost.

#### Method: `_compute_purchase_price()`

```python
@api.depends('is_expense')
def _compute_purchase_price(self):
    expense_lines = self.filtered('expense_id')
    for line in expense_lines:
        expense = line.expense_id
        product_cost = expense.untaxed_amount_currency / (expense.quantity or 1.0)
        line.purchase_price = line._convert_to_sol_currency(
            product_cost, expense.currency_id
        )

    return super(SaleOrderLine, self - expense_lines)._compute_purchase_price()
```

| Aspect | Detail |
|--------|--------|
| `@api.depends` | `'is_expense'` — fires when `is_expense` toggles or when expense lines are created |
| Filter | `self.filtered('expense_id')` — only processes SOLs with an expense link |
| Division guard | `expense.quantity or 1.0` — prevents ZeroDivisionError if quantity is 0 |
| Currency conversion | `_convert_to_sol_currency()` — handles multi-currency; expense may be in EUR while SOL is in USD |
| super() call | Passes remaining SOLs (non-expense) to `sale_margin`'s `_compute_purchase_price` |

#### `is_expense` Field (from `sale_expense`)

This boolean on `sale.order.line` (set by `sale_expense`) is the trigger for the `@api.depends`. It is `True` for lines created from expense re-invoicing.

### Extended Model: `account.move.line`

**File:** `models/account_move_line.py`

#### Method: `_sale_prepare_sale_line_values()`

```python
def _sale_prepare_sale_line_values(self, order, price):
    res = super()._sale_prepare_sale_line_values(order, price)
    if self.expense_id:
        res['expense_id'] = self.expense_id.id
    return res
```

| Aspect | Detail |
|--------|--------|
| Purpose | Propagates `expense_id` from the vendor bill line to the newly created SOL |
| Trigger | Called when creating a SOL from an invoice line (via `sale_expense` or `sale_timesheet`) |
| `super()` result | Base values from parent (product, quantity, price, tax, etc.) |
| Conditional | Only sets `expense_id` if the invoice line is linked to an expense |

This method ensures the chain `expense → vendor bill → SOL` carries the `expense_id` reference through to the SOL, which is then used by `sale_expense_margin._compute_purchase_price()`.

### Default Behavior Without This Module

| Field/Behavior | Without module | With module |
|----------------|----------------|-------------|
| `SOL.purchase_price` | `product.standard_price` (may be 0) | `expense.untaxed_amount_currency / expense.quantity` |
| `margin_percent` | Inflated (cost = 0) | Accurate |
| `expense_id` on SOL | Set by `sale_expense` | Set by `sale_expense` |
| `is_expense` on SOL | Set by `sale_expense` | Set by `sale_expense` |

---

## L3: Cross-Model Relationships, Override Patterns, and Workflow Triggers

### Cross-Model Chain

```
hr_expense
    │
    ├── expense_id: links to expense
    ├── untaxed_amount_currency: cost used for margin
    ├── quantity: divisor for unit cost
    └── currency_id: for currency conversion
            │
            ▼ (sale_expense creates SOL from expense)
sale.order.line
    │
    ├── expense_id: Many2one → hr_expense (set here)
    ├── is_expense: True for expense-derived lines
    ├── purchase_price: computed by sale_expense_margin
    └── qty_delivered: equals expense.quantity
            │
            ▼ (sale_margin computes)
    margin = price_subtotal - (qty_delivered * purchase_price)
```

### Override Pattern: `_compute_purchase_price()`

`sale_expense_margin` **intercepts** the `_compute_purchase_price()` method that belongs to `sale_margin`. The inheritance chain:

```
Base: sale.order.line (no _compute_purchase_price)
  └── sale_margin.sale_order_line
          defines: _compute_purchase_price() — sets purchase_price = product.standard_price
              │
              └── sale_expense_margin.sale_order_line
                      overrides: _compute_purchase_price()
                      special-cases expense lines first,
                      then delegates remaining lines back to sale_margin
```

**Override strategy:** Process expense lines first (early return with correct value), then call `super()` for all other lines. This is the recommended pattern for extending a compute: handle your special case, then delegate to the parent for the general case.

```python
# sale_expense_margin pattern (simplified):
def _compute_purchase_price(self):
    expense_lines = self.filtered('expense_id')
    # ... compute for expense lines ...
    return super()._compute_purchase_price()  # handles non-expense lines
```

### Workflow Trigger Sequence

```
Employee        Manager         System
    │               │               │
    ├─ Submit ──────►               │
    │               ├─ Approve ────►│
    │               │               ├─ action_post()
    │               │               │    │
    │               │               │    ├── Creates vendor bill (account.move)
    │               │               │    │
    │               │               │    └── _create_sale_order_line()
    │               │               │         │
    │               │               │         ├── sale_expense creates SOL
    │               │               │         │    sets: expense_id, is_expense=True
    │               │               │         │
    │               │               │         └── sale_expense_margin._compute_purchase_price()
    │               │               │              computes: untaxed_amount / quantity
    │               │               │              sets: SOL.purchase_price
    │               │               │
    │               │               ├─ sale_margin recomputes: margin, margin_percent
```

### `_sale_prepare_sale_line_values()` Cross-Module Bridge

This method in `account.move.line` is called by `sale_expense` when converting expense lines to SOLs. By extending it here, `sale_expense_margin` ensures `expense_id` is carried through even if `sale_expense` does not explicitly set it.

### Test Coverage

**File:** `tests/test_so_expense_purchase_price.py`

The test `test_expense_reinvoice_purchase_price` validates four scenarios:

| Scenario | Expense amount | Tax | Expected purchase_price |
|----------|---------------|-----|------------------------|
| Product with `standard_price=1000`, `expense_policy='sales_price'` | Qty=3, 15% tax | 15% | `1000.0` (product cost, not expense) |
| Product with no cost, `expense_policy='sales_price'` | 100, 15% tax | 15% | `86.96` (100/1.15) |
| Product with no cost, `expense_policy='sales_price'` | 100, no tax | none | `100.0` |
| Product with `standard_price=1000`, `expense_policy='sales_price'` | Qty=5, no tax | none | `1000.0` |

Key assertions:
```python
# Original product line (is_expense=False) uses product standard_price
self.assertAlmostEqual(sale_order.order_line[0].purchase_price, 1000.0)
self.assertFalse(sale_order.order_line[0].is_expense)

# Expense lines (is_expense=True) use expense cost
for line, expected_purchase_price in zip(sale_order.order_line[1:], [86.96, 100.0, 869.5666667, 1000.0]):
    self.assertAlmostEqual(line.purchase_price, expected_purchase_price)
    self.assertTrue(line.is_expense)
```

---

## L4: Version Changes — Odoo 18 to Odoo 19

### Summary of Changes

`sale_expense_margin` has **minimal changes** between Odoo 18 and Odoo 19. The module is thin by design — its logic is a single override and a single field extension.

### No Significant API Changes

The following are confirmed **unchanged** between Odoo 18 and Odoo 19:

| Aspect | Odoo 18 | Odoo 19 | Status |
|--------|---------|---------|--------|
| `expense_id` field on `sale.order.line` | Present | Present | No change |
| `_compute_purchase_price()` signature | `self` only | `self` only | No change |
| `@api.depends` on `_compute_purchase_price` | `'is_expense'` | `'is_expense'` | No change |
| `_sale_prepare_sale_line_values()` signature | `(self, order, price)` | `(self, order, price)` | No change |
| Division guard `expense.quantity or 1.0` | Present | Present | No change |
| `sale_expense` module behavior | Creates SOL | Creates SOL | No change |
| `sale_margin._compute_purchase_price()` API | Same | Same | No change |

### Currency Conversion Call

The call to `_convert_to_sol_currency()` is from the base `sale.order.line` model. This method handles currency conversion between the expense's currency and the SOL's currency (which defaults to the company's currency). This method signature and behavior is unchanged in Odoo 19.

### No Deprecations

No deprecated decorators (`@api.one`, `@api.multi`) are used in this module. The code is already fully compliant with the Odoo 17+ API style.

### Dependency Compatibility

| Dependency | Odoo 18 | Odoo 19 | Notes |
|-----------|---------|---------|-------|
| `sale_expense` | Required | Required | No API changes |
| `sale_margin` | Required | Required | No API changes |
| `hr_expense` | Indirect | Indirect | Via `sale_expense` |

### Code Volume

| Metric | Value |
|--------|-------|
| Model files | 2 (`account_move_line.py`, `sale_order_line.py`) |
| Python lines (models) | ~35 lines total |
| Test file | 1 (`test_so_expense_purchase_price.py`) |
| XML files | None |
| Manifest changes | None |

### Overall Assessment

`sale_expense_margin` is **stable across Odoo 18→19**. No migration work is required. The module's simplicity — one field, one method override, one cross-model bridge — means it is highly resistant to version breakage.
