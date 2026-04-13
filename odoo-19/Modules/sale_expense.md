---
tags: [odoo, odoo19, sale_expense, hr_expense, reinvoicing, expense_policy, sale_management]
description: "sale_expense: bridge module that reinvoices posted employee expenses to customer sales orders via the analytic-account reinvoice mechanism."
---

# sale_expense

> Reinvoice employee expenses to customers via Sales Order.

| Property | Value |
|---|---|
| **Module** | `sale_expense` |
| **Version** | 1.0 |
| **Category** | Sales/Sales |
| **Depends** | `sale_management`, `hr_expense` |
| **Auto-install** | `True` (installed automatically when both dependencies are present) |
| **License** | LGPL-3 |
| **Location** | `odoo/addons/sale_expense/` |

## Overview

`sale_expense` bridges **hr_expense** and **sale_management**, allowing employee expenses with a reinvoice policy to be charged directly to a customer sales order. When an expense is posted and linked to a confirmed SO, Odoo creates a `sale.order.line` on that SO — the cost is then recovered by invoicing the customer.

Two reinvoice policies exist:
- **`cost`** — the SOL is created at the product's standard cost.
- **`sales_price`** — the SOL is created at the product's list price or pricelist-adjusted price.

The expense itself is still approved and paid to the employee through the normal `hr_expense` flow (vendor bill + payment). The reinvoice creates a **separate customer invoice** that recovers the cost, effectively converting the company expense into a billable line item.

---

## Architecture

```
hr.expense (draft)
    └── user selects sale_order_id (only state='sale' SOs selectable)
    └── expense approved and posted
         │
         ▼
account.move (vendor bill created)
    └── account.move.line generated with analytic distribution
         │
         ▼
    expense.action_post():
        if sale_order_id and no analytic_distribution:
            → create analytic account from SO data
            → assign {analytic_account_id: 100} to expense
         │
         ▼
    analytic line creation → _prepare_analytic_lines()
         │
         ▼
    account.move.line._sale_can_be_reinvoice()
        → expense_id present + expense_policy in {cost, sales_price} + display_type='product'
         │
         ▼
    account.move.line._sale_determine_order()
        → returns {move_line_id: expense.sale_order_id}
         │
         ▼
    account.move.line._sale_create_reinvoice_sale_line()
        → force_split_lines: True (each expense gets its own SOL)
         │
         ▼
    account.move.line._sale_prepare_sale_line_values()
        → name = expense.name (description, not product name)
        → expense_ids = [expense.id]
        → product_uom_qty = expense.quantity
        → analytic_distribution = move_line.analytic_distribution
         │
         ▼
sale.order.line created (expense_ids = expense)
    └── expense.sale_order_line_id set
         │
         ▼
Customer invoice from SO → recovers the expense cost
```

### Key Design Decision: Per-Expense SOL Split

Each reinvoiced expense gets its **own SOL** via the `force_split_lines` context. Without this, multiple expenses with the same product on the same SO would collapse into a single aggregated SOL. Manual edits to one expense's quantity would bleed into the aggregated line. The split ensures every expense can be individually managed on the SO.

---

## Dependencies

```
sale_expense
├── sale_management
│   ├── sale
│   │   └── account.move.line (reinvoice engine: _sale_* methods)
│   └── product
└── hr_expense
    ├── hr.expense (base model)
    └── product (expense products: meal, mileage, travel, communication)
```

---

## Models

### `hr.expense` — Extended

File: `models/hr_expense.py`

Primary model. Extends the base `hr.expense` defined in `hr_expense`.

#### New Fields

| Field | Type | Notes |
|---|---|---|
| `sale_order_id` | `Many2one(sale.order)` | Customer to reinvoice. Domain: `state = 'sale'`. Compute with write-back store. Index: `btree_not_null`. Tracking enabled. |
| `sale_order_line_id` | `Many2one(sale.order.line)` | Computed alongside `sale_order_id`. Points to the generated SOL. Index: `btree_not_null`. Readonly. |
| `can_be_reinvoiced` | `Boolean` | `True` when `product_id.expense_policy in {'sales_price', 'cost'}`. Compute, not stored. |

```python
sale_order_id = fields.Many2one(
    'sale.order',
    string='Customer to Reinvoice',
    compute='_compute_sale_order_id',
    store=True,
    readonly=False,
    index='btree_not_null',
    tracking=True,
    # Domain activated via name search with sale_expense_all_order context.
    # The field-level domain is not the one actually applied.
    domain="[('state', '=', 'sale')]",
    check_company=True,
    help="If the category has an expense policy, it will be reinvoiced on this sales order"
)
sale_order_line_id = fields.Many2one(
    comodel_name='sale.order.line',
    compute='_compute_sale_order_id',
    store=True,
    readonly=True,
    index='btree_not_null',
)
can_be_reinvoiced = fields.Boolean(
    "Can be reinvoiced",
    compute='_compute_can_be_reinvoiced'
)
```

#### `_compute_can_be_reinvoiced`

```python
@api.depends('product_id.expense_policy')
def _compute_can_be_reinvoiced(self):
    for expense in self:
        expense.can_be_reinvoiced = expense.product_id.expense_policy in ['sales_price', 'cost']
```

- `expense_policy = 'no'` or `False` (unset) → `can_be_reinvoiced = False`
- Only `cost` and `sales_price` qualify for reinvoicing.

#### `_compute_sale_order_id`

```python
@api.depends('can_be_reinvoiced')
def _compute_sale_order_id(self):
    for expense in self.filtered(lambda e: not e.can_be_reinvoiced):
        expense.sale_order_id = False
        expense.sale_order_line_id = False
```

When the product changes such that `can_be_reinvoiced` becomes `False`, both the SO link and SOL link are cleared. This prevents a dangling reference when the expense policy changes.

#### `_onchange_sale_order_id`

```python
@api.onchange('sale_order_id')
def _onchange_sale_order_id(self):
    to_reset = self.filtered(lambda line: not self.env.is_protected(self._fields['analytic_distribution'], line))
    to_reset.invalidate_recordset(['analytic_distribution'])
    self.env.add_to_compute(self._fields['analytic_distribution'], to_reset)
```

When the SO changes, the analytic distribution is marked for recompute via onchange. Lines with manually-set analytic distributions are protected by `is_protected()` — their distributions are not reset. This prevents the onchange from overwriting deliberate manual overrides and handles the split wizard case where each split inherits the parent's distribution.

#### `action_post` — Analytic Account Auto-Creation

```python
def action_post(self):
    for expense in self:
        if expense.sale_order_id and not expense.analytic_distribution:
            analytic_account = self.env['account.analytic.account'].create(
                expense.sale_order_id._prepare_analytic_account_data()
            )
            expense.analytic_distribution = {analytic_account.id: 100}
    return super().action_post()
```

If the expense has an SO but no analytic distribution, Odoo creates a new analytic account from the SO's data and assigns 100% distribution. This is required because the reinvoice mechanism relies on analytic lines having a proper distribution — without it, `_sale_can_be_reinvoice()` would not fire correctly.

#### `_sale_expense_reset_sol_quantities`

```python
def _sale_expense_reset_sol_quantities(self):
    """
    Resets the quantity of a SOL created by a reinvoiced expense to 0 when
    the expense or its move is reset to an unfinished state.

    Note: Resetting qty_delivered raises for storable products when sale_stock
          is installed, but that's fine since storing a physical product via
          expense does not make sense.
    """
    self.check_access('write')
    # If we can edit the expense, we may not be able to edit the sol without sudoing.
    self.sudo().sale_order_line_id.write({
        'qty_delivered': 0.0,
        'product_uom_qty': 0.0,
        'expense_ids': [Command.clear()],
    })
```

Called when the vendor bill is reversed, reset to draft, or deleted. Zeros out the SOL quantities and clears `expense_ids` to prevent phantom references. Uses `sudo()` because the expense user (employee or approver) may not have write access to the SOL, which belongs to the salesman who owns the SO. Note: the `qty_delivered` write raises for storable products with `sale_stock` — this is intentional, as physical goods should not be handled through the expense reimbursement flow.

#### `_get_split_values`

```python
def _get_split_values(self):
    vals = super()._get_split_values()
    for split_value in vals:
        split_value['sale_order_id'] = self.sale_order_id.id
    return vals
```

When an expense is split, each resulting child expense inherits the parent's `sale_order_id`. This keeps the reinvoice target intact across the split operation.

#### `action_open_sale_order`

Opens the linked SO in form view. `ensure_one()` enforces single-record context.

---

### `hr.expense.split` — Extended (Wizard)

File: `models/hr_expense_split.py`

The split wizard model (`hr.expense.split.wizard`) carries `sale_order_id` through the split operation so that child expenses retain the reinvoice target.

#### New Fields

| Field | Type | Notes |
|---|---|---|
| `sale_order_id` | `Many2one(sale.order)` | Domain: `state = 'sale'`, `company_id` match. Compute with write-back store. |
| `can_be_reinvoiced` | `Boolean` | Same compute logic as `HrExpense`. |

```python
sale_order_id = fields.Many2one(
    'sale.order',
    string="Customer to Reinvoice",
    compute='_compute_sale_order_id',
    readonly=False,
    store=True,
    domain="[('state', '=', 'sale'), ('company_id', '=', company_id)]"
)
```

#### `_compute_sale_order_id`

```python
@api.depends('can_be_reinvoiced')
def _compute_sale_order_id(self):
    for split in self:
        split.sale_order_id = split.sale_order_id if split.can_be_reinvoiced else False
```

Preserves the value if already set and still valid; otherwise clears it.

#### `_get_values`

```python
def _get_values(self):
    vals = super()._get_values()
    vals['sale_order_id'] = self.sale_order_id.id
    return vals
```

The `sale_order_id` is written onto the newly created child expense record during split confirmation.

---

### `account.move.line` — Extended

File: `models/account_move_line.py`

This is where the reinvoice bridge fires. The base `_sale_*` methods are defined in `sale/models/account_move_line.py`.

#### `_sale_can_be_reinvoice` — Expense Override

```python
def _sale_can_be_reinvoice(self):
    self.ensure_one()
    if self.expense_id:  # expense flow is different from vendor bill reinvoice flow
        return (
            self.expense_id.product_id.expense_policy in {'sales_price', 'cost'}
            and self.expense_id.sale_order_id
            and self.display_type == 'product'
        )
    return super()._sale_can_be_reinvoice()
```

The expense flow uses the `expense_id` pointer directly, bypassing the debit/credit direction check used by the vendor-bill reinvoice flow. Only `display_type = 'product'` lines are reinvoiced — non-product lines (e.g., tax lines) are skipped.

#### `_get_so_mapping_from_expense`

```python
def _get_so_mapping_from_expense(self):
    mapping_from_expense = {}
    for move_line in self.filtered(lambda move_line: move_line.expense_id):
        mapping_from_expense[move_line.id] = move_line.expense_id.sale_order_id or None
    return mapping_from_expense
```

Builds a mapping of `{move_line_id: sale_order_id}` from each move line's `expense_id.sale_order_id`. Returns `None` (not absent) for lines without an SO, which downstream code treats as "no mapping".

#### `_sale_determine_order` — Merge Two Mappings

```python
def _sale_determine_order(self):
    # EXTENDS sale
    mapping_from_invoice = super()._sale_determine_order()
    mapping_from_invoice.update(self._get_so_mapping_from_expense())
    return mapping_from_invoice
```

Merges the vendor-bill mapping (from `sale`) with the expense mapping. Expense-based mappings take precedence for `expense_id` lines because `_get_so_mapping_from_expense()` is called after the parent.

#### `_sale_prepare_sale_line_values`

```python
def _sale_prepare_sale_line_values(self, order, price):
    res = super()._sale_prepare_sale_line_values(order, price)
    if self.expense_id:
        res.update({
            'name': self.name,  # employee-provided expense description, not product name
            'expense_ids': [Command.set(self.expense_id.ids)],
            'product_uom_qty': self.expense_id.quantity,
            'analytic_distribution': self.analytic_distribution,
        })
    return res
```

- `name`: description from the analytic line (the employee-written expense name), not the product's name.
- `expense_ids`: links the SOL back to the expense, enabling the `sale.order.line` → `hr.expense` O2M.
- `product_uom_qty`: set to the expense's quantity, not `1.0`. For standard unit-quantity expenses, these are equal; for mileage or quantity-based expenses, this carries the correct count.
- `analytic_distribution`: copied from the move line (which was set from the expense's distribution, potentially auto-created from the SO in `action_post`).

#### `_sale_create_reinvoice_sale_line` — Force Per-Expense SOL Split

```python
def _sale_create_reinvoice_sale_line(self):
    # We force each reinvoiced expense to be on their own sale order line,
    # else we cannot properly edit the quantities if the user manually overrides anything
    expensed_lines = self.filtered('expense_id')
    res = super(AccountMoveLine, self - expensed_lines)._sale_create_reinvoice_sale_line()
    res.update(
        super(
            AccountMoveLine,
            expensed_lines.with_context({'force_split_lines': True})
        )._sale_create_reinvoice_sale_line()
    )
    return res
```

Passes `force_split_lines: True` context for expensed lines. This context signals the base reinvoice logic (in `sale`) to create a separate SOL per move line rather than attempting to reuse an existing matching SOL. Without this, multiple expenses on the same SO with the same product would collapse into one SOL.

---

### `account.move` — Extended

File: `models/account_move.py`

Triggers SOL quantity reset whenever the vendor bill transitions away from a posted state.

```python
def _reverse_moves(self, default_values_list=None, cancel=False):
    self.expense_ids._sale_expense_reset_sol_quantities()
    return super()._reverse_moves(default_values_list, cancel)

def button_draft(self):
    self.expense_ids._sale_expense_reset_sol_quantities()
    return super().button_draft()

def unlink(self):
    self.expense_ids._sale_expense_reset_sol_quantities()
    return super().unlink()
```

All three operations (reverse, reset to draft, delete) call `_sale_expense_reset_sol_quantities()` before executing. This ensures that phantom billed quantities do not persist after the source invoice becomes invalid.

---

### `sale.order` — Extended

File: `models/sale_order.py`

#### New Fields

| Field | Type | Notes |
|---|---|---|
| `expense_ids` | `One2many(hr.expense, inverse=sale_order_id)` | Domain: `state in ('posted', 'in_payment', 'paid')`. Readonly. |
| `expense_count` | `Integer` | Count of expenses linked via `order_line.expense_ids`. Compute with `compute_sudo=True`. |

```python
expense_ids = fields.One2many(
    comodel_name='hr.expense',
    inverse_name='sale_order_id',
    string='Expenses',
    domain=[('state', 'in', ('posted', 'in_payment', 'paid'))],
    readonly=True,
)
expense_count = fields.Integer("# of Expenses", compute='_compute_expense_count', compute_sudo=True)
```

#### `_compute_expense_count`

```python
@api.depends('expense_ids')
def _compute_expense_count(self):
    for sale_order in self:
        sale_order.expense_count = len(sale_order.order_line.expense_ids)
```

Counts through the SOL back-reference, not the direct O2M. This gives the count of all posted/paid expenses ever linked to the SO, regardless of whether their SOL has been zeroed (which happens when the vendor bill is reversed). The `expense_ids` O2M on `sale.order` is domain-filtered to `state in posted/in_payment/paid`, so it only shows active posted expenses.

#### `_search_display_name` — Bypass ir.rule for Expense Selection

```python
@api.model
def _search_display_name(self, operator, value):
    if (
        self.env.context.get('sale_expense_all_order')
        and self.env.user.has_group('sales_team.group_sale_salesman')
        and not self.env.user.has_group('sales_team.group_sale_salesman_all_leads')
    ):
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        domain = super()._search_display_name(operator, value)
        company_domain = Domain('state', '=', 'sale') & ('company_id', 'in', self.env.companies.ids)
        query = self.sudo()._search(domain & company_domain)
        return Domain('id', 'in', query)
    return super()._search_display_name(operator, value)
```

A salesman with limited partner visibility would normally only see SOs for their accessible partners. For expense reinvoicing, the user needs to select any confirmed SO in their companies. This override (activated only via `sale_expense_all_order` context) uses `sudo()` with a company-scoped query to bypass ir.rule, then wraps the result back in an `id in` domain as the non-sudo user. This preserves auditability while enabling the selection.

---

### `sale.order.line` — Extended

File: `models/sale_order_line.py`

#### New Fields

| Field | Type | Notes |
|---|---|---|
| `expense_ids` | `One2many(hr.expense, inverse=sale_order_line_id)` | Readonly. Back-reference linking expenses to the SOL. |

```python
expense_ids = fields.One2many(
    comodel_name='hr.expense',
    inverse_name='sale_order_line_id',
    string='Expenses',
    readonly=True,
)
```

This O2M powers the `sale_order.expense_count` computation and the "Expenses" smart button on the SO form. For expense-generated SOLs, `force_split_lines: True` ensures a 1:1 relationship. For vendor-bill reinvoiced lines (from `sale` module), multiple expense lines can theoretically share the same SOL.

---

### `product.template` — Extended

File: `models/product_template.py`

#### `expense_policy_tooltip`

```python
@api.depends('expense_policy')
def _compute_expense_policy_tooltip(self):
    for product_template in self:
        if not product_template.can_be_expensed or not product_template.expense_policy:
            product_template.expense_policy_tooltip = False
        elif product_template.expense_policy == 'no':
            product_template.expense_policy_tooltip = _(
                "Expenses of this category may not be added to a Sales Order."
            )
        elif product_template.expense_policy == 'cost':
            product_template.expense_policy_tooltip = _(
                "Expenses will be added to the Sales Order at their actual cost when posted."
            )
        elif product_template.expense_policy == 'sales_price':
            product_template.expense_policy_tooltip = _(
                "Expenses will be added to the Sales Order at their sales price "
                "(product price, pricelist, etc.) when posted."
            )
```

Displayed below the `expense_policy` radio buttons in the product form. Only rendered for expensable products with a non-false policy.

#### `_compute_visible_expense_policy`

Adds group check: `hr_expense.group_hr_expense_user` required to see the expense policy field. Extends base logic which only checks product type.

#### `_compute_expense_policy`

```python
@api.depends('can_be_expensed')
def _compute_expense_policy(self):
    super()._compute_expense_policy()
    self.filtered(lambda t: not t.can_be_expensed).expense_policy = 'no'
```

Ensures that products that cannot be expensed (non-consu/non-service types) always have `expense_policy = 'no'`.

---

## Data: Default Expense Policy on Standard Products

File: `data/sale_expense_data.xml` (noupdate=1)

On module installation/upgrade, sets the expense policy on Odoo's four standard expense products:

| Product (xmlid) | `expense_policy` | `invoice_policy` |
|---|---|---|
| `hr_expense.expense_product_meal` | `sales_price` | default (order) |
| `hr_expense.expense_product_mileage` | `sales_price` | `delivery` |
| `hr_expense.expense_product_travel_accommodation` | `cost` | `delivery` |
| `hr_expense.expense_product_communication` | `cost` | default (order) |

**Policy rationale**: Meals and mileage use `sales_price` because the amount is a known, approved rate (e.g., per-diem, mileage rate) — the employee should not profit from it, and the list price reflects the approved rate. Travel and communication use `cost` because the actual spent amount is passed through with no markup; the company recovers exactly what was paid.

---

## Views

### HR Expense Form (`hr_expense_form_view_inherit_sale_expense`)

- **Smart button** `action_open_sale_order`: shown when `sale_order_id` is set. Displays the SO name and navigates to the SO form. Placed after the `action_open_account_move` button.
- **`sale_order_id` field**: Three visibility variants based on `groups`:
  - Non-sales, non-accountant: `no_create_edit` and `no_open` options — can select from dropdown but cannot create or open records.
  - Salesman (no accountant): standard M2O widget with autocomplete.
  - Accountant/Admin: `no_open` option — can select and create but not open the record directly.
- **`can_be_reinvoiced`**: invisible field used to conditionally hide `sale_order_id` via domain.

### HR Expense Tree (`hr_expense_tree_view_inherit_sale_expense`)

- **`sale_order_id`** added as optional column, hidden by default. Visible only when `can_be_reinvoiced = True` and expense is not yet posted/refused.

### HR Expense Split Wizard (`hr_expense_split_view_inherit_sale_expense`)

- **`can_be_reinvoiced`**: column invisible, guards `sale_order_id` visibility.
- **`sale_order_id`**: `force_save="1"` ensures it is saved even when readonly.

### Product Form (`product_product_view_form_inherit_sale_expense`)

- **Invoicing group**: displays `expense_policy` radio buttons plus the `expense_policy_tooltip` description below.
- **`list_price`**: hidden unless `expense_policy == 'sales_price'`.
- **`taxes_id`**: hidden when `expense_policy == 'no'`; shown for `cost` and `sales_price`.

### Product List (`product_product_view_list_inherit_sale_expense`)

- **`expense_policy`** added as optional column, shown by default.
- **`taxes_id`** hidden by default.

### Sale Order Form (`sale_order_form_view_inherit`)

- **Smart button** `hr_expense_action_from_sale_order`: shown when `expense_count > 0`. Displays expense count and navigates to a filtered expense list (domain: `sale_order_id = active_id`).

---

## Cross-Module Integration

### Reinvoice Flow: Expense → SO → Customer Invoice

```
1. Employee creates expense with reinvoiceable product (expense_policy in {cost, sales_price})
2. Employee/manager selects sale_order_id (only state='sale' SOs selectable)
3. Expense sheet approved → individual expenses reach 'posted' state
4. action_post():
   a. Creates vendor bill (account.move)
   b. Generates analytic lines with distribution
   c. If sale_order_id set but no analytic_distribution:
      → creates analytic account from sale_order_id._prepare_analytic_account_data()
      → assigns {analytic_account_id: 100}
5. Analytic line creation triggers _prepare_analytic_lines()
6. For each account.move.line with expense_id:
   a. _sale_can_be_reinvoice() → True
   b. _sale_determine_order() → returns {move_line_id: expense.sale_order_id}
   c. _sale_create_reinvoice_sale_line(force_split_lines=True) → creates SOL per expense
   d. _sale_prepare_sale_line_values():
      name = expense.name, qty = expense.quantity, expense_ids = [expense.id]
7. SOL written → expense.sale_order_line_id set
8. Salesperson sees expense-linked SOL on the SO
9. Customer invoice created from SO → recovers expense cost
```

### Reversal Flow: Vendor Bill → SOL Reset

```
1. User reverses / resets to draft / deletes the vendor bill
2. _reverse_moves / button_draft / unlink on account.move
3. Calls expense_ids._sale_expense_reset_sol_quantities()
4. SOL: qty_delivered = 0, product_uom_qty = 0, expense_ids cleared
5. expense.sale_order_line_id still set (stale reference not corrected)
6. If expense re-posted → new analytic line → new SOL created
```

### Split Flow: Expense Split → Child Expenses Keep SO

```
1. User splits an expense with sale_order_id set
2. _get_split_values() copies sale_order_id to each child expense
3. Each child expense posted independently
4. Each child's analytic line creates its own SOL on the same SO
5. Multiple SOLs on the same SO (one per split expense)
```

---

## Edge Cases and Failure Modes

### Missing Analytic Distribution on Posting

If `action_post` runs without an analytic distribution on an expense with `sale_order_id`, the method auto-creates an analytic account from `sale_order_id._prepare_analytic_account_data()`. Without this, the reinvoice mechanism would not fire since the analytic line creation step depends on a valid distribution.

### Stale `sale_order_line_id` on Reversal

`_sale_expense_reset_sol_quantities()` writes to the SOL but does not clear `expense.sale_order_line_id`. Re-posting the same expense creates a new SOL; the old `sale_order_line_id` still points to the zeroed-out line. This is a known mild inconsistency — the stale reference is not corrected on reversal. In practice this rarely causes issues since the SOL is already zeroed.

### Non-Salesman Creating Expenses (RLS Context)

The `_search_display_name` override with `sale_expense_all_order` context bypasses partner-based ir.rule for SO name search. Without it, a salesman with limited partner visibility could not select SOs belonging to other customers, even though they legitimately need to reinvoice expenses to those SOs. This is a deliberate trade-off: the user already has expense submission and approval rights, so targeting an arbitrary SO is considered acceptable.

### Multiple Expenses on Same SO Without `force_split_lines`

Without the `force_split_lines: True` context, the base `_sale_create_reinvoice_sale_line()` (in `sale`) would attempt to reuse an existing matching SOL on the same SO (same product, same price). Multiple expenses with the same product would collapse into a single SOL with accumulated quantity. Manual edits to one expense's `qty_delivered` would affect the aggregated line. The `force_split_lines` override prevents this.

### Storable Products with `sale_stock`

`_sale_expense_reset_sol_quantities()` calls `write({'qty_delivered': 0.0})` on the SOL. For storable products with `sale_stock` installed, this raises a validation error because undelivering requires stock moves. This is intentional — storable products should not be expensed, as the physical flow (receiving, delivering) is managed separately from expense reimbursement.

### Expense Policy Change After SO Selected

If the user changes the expense's product from a `cost`-policy item to a `no`-policy item, `_compute_can_be_reinvoiced` → `False` triggers `_compute_sale_order_id` to reset `sale_order_id = False`. The previously selected SO is lost. If the user switches back to a reinvoiceable product, they must re-select the SO.

### SO State Guards in Base Reinvoice Engine

The base `sale` module's `_sale_create_reinvoice_sale_line()` raises `UserError` if the SO state is `draft`, `sent` (not validated), `cancel`, or `locked`. `sale_expense` does not override these guards — an expense cannot be linked to an unconfirmed or locked SO because the field-level domain restricts `state = 'sale'` and the name search uses the same context.

---

## Performance Considerations

- The `btree_not_null` index on `sale_order_id` and `sale_order_line_id` ensures efficient filtering on the expense model when queries target posted/paid expenses with an SO link.
- `_sale_expense_reset_sol_quantities()` uses `sudo()` and a single `write()` call per expense to minimize DB round-trips during vendor bill reversal.
- `expense_count` uses `compute_sudo=True` so the count is computed as superuser, bypassing record rules — this is safe because the count is non-sensitive and the computation is lightweight.

---

## Odoo 18 → 19 Changes

No major architectural changes to `sale_expense` between Odoo 18 and 19. The module structure, field names, and reinvoice flow remain consistent.

Key elements in Odoo 19:
- `sale_expense/models/hr_expense.py` — `sale_order_line_id` field with `btree_not_null` index
- `sale_expense/models/account_move_line.py` — `force_split_lines` context pattern for per-expense SOL creation
- `sale_expense/data/sale_expense_data.xml` — sets `invoice_policy = 'delivery'` for `expense_product_mileage` and `expense_product_travel_accommodation`

### `btree_not_null` Index on `sale_order_line_id`

Odoo 19 adds `index='btree_not_null'` on `hr.expense.sale_order_line_id`. This is a PostgreSQL partial index (`btree (col) WHERE col IS NOT NULL`) that efficiently filters expenses with a linked SOL without consuming storage for null entries. The same pattern is used on `sale_order_id`. This improves performance when querying posted expenses that have been reinvoiced, particularly in the `expense_ids` O2M on `sale.order`.

### `invoice_policy = 'delivery'` for Mileage and Travel

The data update sets `invoice_policy = 'delivery'` for `expense_product_mileage` and `expense_product_travel_accommodation`. This means customer invoicing from the SO only recognizes revenue when the SOL is delivered (not when the order is confirmed). This aligns with how mileage and travel expenses are typically recognized — the service is performed first, then billed. The `sales_price` policy for meals means they are invoiced at order time, reflecting that the meal cost is known upfront.

### Consistency with Base Reinvoice Engine

The `force_split_lines` override in `sale_expense` is compatible with the Odoo 19 base reinvoice engine in `sale/models/account_move_line.py`. The base engine's `_sale_create_reinvoice_sale_line()` accepts the `force_split_lines` context without modification. If the base engine changes in a future version, this override should continue to work as long as the context key is respected.

---

## Security

### No Dedicated ACL File

`sale_expense` does not ship its own `security/ir.model.access.csv` or `security/*.xml`. All access control derives from the two dependency modules:

| Model | ACL Source | Who Has What |
|---|---|---|
| `hr.expense` | `hr_expense` module | `hr_expense.group_hr_expense_user` (employee/approver) |
| `sale.order` | `sale` module | `sales_team.group_sale_salesman` (salesman) |
| `sale.order.line` | `sale` module | `sales_team.group_sale_salesman` (salesman) |
| `account.move` | `account` module | `account.group_account_invoice` (accountant) |
| `product.supplierinfo` | `purchase` module | `purchase.group_purchase_user` |

This means there is no explicit ACL that grants an expense employee the right to write `sale.order.line` records — that right comes from `sale` module ACLs on the salesman. The bridge works because `_sale_expense_reset_sol_quantities()` uses `sudo()` to write to the SOL regardless of who triggers it.

### Cross-Record Access: Expense User vs. SOL Owner

The most significant cross-record security tension is between the **expense user** (who creates/approves the expense) and the **salesman** (who owns the SO and its lines).

| Scenario | Expense User ACL | SOL ACL | Result |
|---|---|---|---|
| Expense posted → SOL created | Expense user triggers `action_post` | Salesman's ACL | `sudo()` in `_sale_create_reinvoice_sale_line` bypasses ACL to create SOL |
| Vendor bill reversed | Expense user resets vendor bill | Salesman's ACL | `_sale_expense_reset_sol_quantities()` uses `sudo()` to zero the SOL qty |
| Salesman views SO | No SOL ACL | Salesman's ACL | Can see the expense-linked SOL normally |
| Expense employee manually edits the reinvoiced SOL | No ACL to SOL | Salesman's ACL | Blocked by ACL unless `sudo()` is used |

The `sudo()` calls in `_sale_expense_reset_sol_quantities()` and `_sale_create_reinvoice_sale_line` are the deliberate mechanism that bridges this gap: the expense user can trigger changes to a SOL they do not directly own.

### `_search_display_name` Ir.rule Bypass

The `_search_display_name` override in `sale.order` with `sale_expense_all_order` context is a **deliberate security trade-off**:

```python
# Activated only via sale_expense_all_order context
if operator in Domain.NEGATIVE_OPERATORS:
    return NotImplemented  # Negative operators are blocked
query = self.sudo()._search(domain & company_domain)  # Bypasses ir.rule
return Domain('id', 'in', query)  # Wrapped back as non-sudo user
```

**What this allows**: An expense user (non-salesman) can select any confirmed SO in their company when linking an expense for reinvoicing — even SOs belonging to partners they would not normally have access to under the `sales_team.group_sale_salesman_all_leads` ir.rule.

**Why it is acceptable**: The expense user already has expense submission and approval rights. Targeting an arbitrary confirmed SO for reinvoicing is a business convenience, not a security escalation — the salesman still owns the SO and any changes to it are logged under the expense user's session. Negative operators are explicitly blocked to prevent enumeration attacks.

### `force_split_lines` Context Does Not Bypass ACL

The `force_split_lines: True` context passed to `_sale_create_reinvoice_sale_line()` for expensed lines does **not** bypass record rules. The user still needs:

- Write access to the `sale.order` (implicit when creating a line via SOL create)
- Read/write access to the expense record

The split context only controls SOL merging behavior in the base reinvoice engine, not access rights.

### Wizard Access (No Sale_expense Wizards)

`sale_expense` does not define any `*.wizard` models of its own. The split operation uses the base `hr_expense` split wizard (`hr.expense.split.wizard`), whose ACL is managed entirely by the `hr_expense` module. The split wizard propagates `sale_order_id` to child expenses via `_get_values()`, which does not require elevated privileges.

---

## See Also

- [Modules/sale](modules/sale.md) — Base sale module (reinvoice engine: `_sale_*` methods on `account.move.line`)
- [Modules/hr_expense](modules/hr_expense.md) — Employee expense management (base `hr.expense` model)
- [Modules/sale_management](modules/sale_management.md) — Sales management wrapper (depends chain)
- [Core/API](core/api.md) — `@api.depends`, `@api.onchange`, `@api.model` decorator patterns
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — State machine and action button patterns