---
uid: project_sale_expense
title: Project Sale Expense
type: module
category: Services/Project Management
version: 1.0
created: 2026-04-06
modified: 2026-04-11
dependencies:
  - sale_project
  - sale_expense
  - project_hr_expense
author: Odoo S.A.
license: LGPL-3
summary: Full traceability of expense re-invoicing on project profitability reports
auto_install: true
tags:
  - odoo
  - odoo19
  - modules
  - project
  - expense
  - sale
  - profitability
  - integration
---

# Project Sale Expense (`project_sale_expense`)

## Overview

| Property | Value |
|----------|-------|
| Module | `project_sale_expense` |
| Version | 1.0 |
| Category | Services/Project |
| License | LGPL-3 |
| Depends | `sale_project`, `sale_expense`, `project_hr_expense` |
| Auto-install | True |

## Purpose

`project_sale_expense` integrates expense reinvoicing with project profitability reporting. It provides full traceability of expenses on a project's profitability report by linking expenses to sale orders and sale order lines, enabling the system to:

1. **Reinvoice expenses** from employees to customers through sale orders
2. **Track expense costs** against a project's analytic account
3. **Display expense revenues** (amount to invoice / invoiced) on the project profitability screen
4. **Merge analytic distributions** from project and sale order when computing expense distributions
5. **Prevent double-counting** of invoice lines linked to re-invoiced expenses in profitability reports

Without this module, `project_hr_expense` only shows expense costs in profitability, and `sale_expense` only handles the SO-to-expense flow but does not connect the cost/revenue cycle to the project profitability screen. With this module installed, managers can see both the **cost** (what the employee spent) and the **revenue** (what the customer is being billed for that expense) in a single project profitability view.

---

## Architecture and Module Chain

```
project_sale_expense
    depends on:
        sale_project          (links SO to project)
        sale_expense          (expense -> SO reinvoice flow)
        project_hr_expense    (expense costs on project profitability)
            depends on:
                project       (project._get_profitability_items)
                hr_expense    (expense model)
```

**Module chain summary:**

| Module | Role |
|--------|------|
| `hr_expense` | Base expense model (`hr.expense`), sheet, approvals, journal entries |
| `sale_expense` | Adds `sale_order_id`, `sale_order_line_id` on `hr.expense`; creates SOLs from expense postings |
| `project_hr_expense` | Shows expense costs in `project.project._get_expenses_profitability_items` |
| `sale_project` | Links a confirmed `sale.order` to a `project.project` |
| `project_sale_expense` | Bridges the gap: adds revenue side of reinvoiced expenses to project profitability, plus analytic distribution merging |

---

## Models Extended

### 1. `project.project` (in `models/project_project.py`)

**File:** `models/project_project.py`

Inherits from `project_hr_expense`'s `project.project` extension (which inherits from the base `project.project`).

#### Method: `_get_expenses_profitability_items(with_action=True)`

```python
def _get_expenses_profitability_items(self, with_action=True):
```

Returns the **expense costs and revenues** data structure for the project profitability panel. Extends the `project_hr_expense` version to include the **revenues** section.

**Logic (step by step):**

1. **Read group expenses by SO + product + currency:**
   ```python
   expenses_read_group = self.env['hr.expense']._read_group(
       [('state', 'in', ['posted', 'in_payment', 'paid']),
        ('analytic_distribution', 'in', self.account_id.ids)],
       groupby=['sale_order_id', 'product_id', 'currency_id'],
       aggregates=['id:array_agg', 'untaxed_amount_currency:sum'],
   )
   ```
   Groups posted/paid expenses that are linked to the project's analytic account(s). Produces a tuple per group: `(sale_order, product, currency, [ids], untaxed_sum)`.

2. **Build expense_ids index per SO and product:**
   ```python
   expenses_per_so_id.setdefault(sale_order.id, {})[product.id] = ids
   ```
   Maps `{so_id: {product_id: [expense_ids]}}` so revenue can be matched by SOL product.

3. **Check visibility permission:**
   ```python
   can_see_expense = with_action and self.env.user.has_group('hr_expense.group_hr_expense_team_approver')
   ```
   Only expense team approvers get a clickable action on the profitability section.

4. **Sum billed costs across currencies:**
   ```python
   amount_billed = sum(currency._convert(untaxed_sum, self.currency_id, self.company_id))
   ```
   Aggregates the **costs** side (negative amount = the expense cost to the project).

5. **Read group reinvoiceable SOLs:**
   ```python
   sol_read_group = self.env['sale.order.line'].sudo()._read_group(
       [('order_id', 'in', list(expenses_per_so_id.keys())),
        ('is_expense', '=', True),
        ('state', '=', 'sale')],
       groupby=['order_id', 'product_id', 'currency_id'],
       aggregates=['untaxed_amount_to_invoice:sum', 'untaxed_amount_invoiced:sum'],
   )
   ```
   Finds SOLs that are expense lines (`is_expense=True`) belonging to the SOs that have posted expenses on this project. This is the **revenues** side.

6. **Match expenses to SOLs by product:**
   ```python
   if product_id in expense_data_per_product_id:
       dict_invoices_amount_per_currency[currency]['to_invoice'] += untaxed_sum
       dict_invoices_amount_per_currency[currency]['invoiced'] += invoiced_sum
       reinvoice_expense_ids += expense_data_per_product_id[product_id]
   ```
   Only counts SOL revenue when a matching expense (same product) exists. This ensures revenue is only shown for actually re-invoiced expenses.

7. **Return data structure:**
   ```python
   expense_data = {
       'costs': {
           'id': 'expenses', 'sequence': <from seq table>,
           'billed': -amount_billed,  # negative = cost
           'to_bill': 0.0,
       },
   }
   if reinvoice_expense_ids:
       expense_data['revenues'] = {
           'id': 'expenses', 'sequence': <from seq table>,
           'invoiced': total_invoiced,
           'to_invoice': total_to_invoice,
       }
   ```

**Key design decisions:**
- `is_expense=True` on SOL is set automatically when an expense move line is reinvoiced (via `sale_expense`'s `_sale_create_reinvoice_sale_line`).
- Only SOLs with a confirmed SO (`state='sale'`) are included.
- Only SOLs where a corresponding expense exists (matched by product) get revenue counted.
- Currency conversion uses `round=False` for the costs sum and `round=True` (default) for revenue conversion.

---

#### Method: `_get_already_included_profitability_invoice_line_ids()`

```python
def _get_already_included_profitability_invoice_line_ids(self):
```

Extends the parent method to **exclude invoice lines from the regular sales revenue calculation** when those lines belong to an expense-linked SO and product. This prevents double-counting — the revenue from re-invoiced expenses should appear only in the `expenses` section, not in the regular `sales` section.

**Logic:**
```python
expenses_read_group = self.env['hr.expense']._read_group(
    [('state', 'in', ['posted', 'in_payment', 'paid']),
     ('analytic_distribution', 'in', self.account_id.ids)],
    groupby=['sale_order_id'],
    aggregates=['__count'],
)
for sale_order, count in expenses_read_group:
    move_line_ids.extend(sale_order.invoice_ids.mapped('invoice_line_ids').ids)
```

For every SO that has posted expenses on this project, all its customer invoice line IDs are added to the exclusion list. These line IDs are then filtered out in the parent `_get_revenues_items_from_sol` method so they do not appear in the regular sales revenues.

---

### 2. `hr.expense` (in `models/hr_expense.py`)

**File:** `models/hr_expense.py`

Extends the `sale_expense` extension of `hr.expense`.

#### Method: `_compute_analytic_distribution()`

```python
def _compute_analytic_distribution(self):
```

Overrides the parent `_compute_analytic_distribution` (from `sale_expense` / `analytic.mixin`) to **merge** the analytic distribution from the sale order's project with any existing analytic distribution on the expense.

**When is it triggered:**
- Called by the Odoo analytic framework whenever `analytic_distribution` might need recomputation.
- Also triggered manually when the user changes `sale_order_id` via the onchange (the onchange invalidates the field and queues it for recomputation).

**Algorithm:**

```python
if not self.env.context.get('project_id'):  # skip if called from project context
    for expense in self.filtered('sale_order_id'):
        # Get existing expense analytic accounts
        expense_account_ids = analytic_mixin._get_analytic_account_ids_from_distributions(
            expense.analytic_distribution)
        # Get project's analytic distribution via the linked SO's project
        project_analytic_distribution = expense.sale_order_id.project_id._get_analytic_distribution()
        project_account_ids = analytic_mixin._get_analytic_account_ids_from_distributions(
            project_analytic_distribution)
```

**Merge strategy — plan compatibility check:**

```python
if not any(project_account.root_plan_id in expense_analytic_accounts.root_plan_id
           for project_account in project_analytic_distribution_accounts):
    # Plans are different -> keep both distributions
    expense.analytic_distribution = {
        **(expense.analytic_distribution or {}),
        **(project_analytic_distribution or {})
    }
else:
    # Plans overlap -> keep only the project distribution (higher priority)
    expense.analytic_distribution = project._get_analytic_distribution() \
        or expense.analytic_distribution \
        or {}
```

**Key behaviors:**
- If the project and expense use **different analytic plans**, both distributions are kept (concatenated).
- If they share the **same plan**, only the project's distribution is used (prevents duplicate entries on the same plan).
- The `project_id` context flag bypasses this logic (used during project-level recomputation to avoid circular calls).
- Prefetch optimization: analytic account records are prefetched by ID before looping.

**Edge cases:**
- Expense with no `sale_order_id` → skipped entirely.
- Expense with no project on SO (`sale_order_id.project_id` is False) → only expense/distribution-model distribution is used.
- New expense (analytic_distribution is None) → merge only project distribution if available.

---

#### Method: `action_post()`

```python
def action_post(self):
```

Extends `hr_expense.action_post` to set the analytic distribution to the project's analytic account when the expense is posted and has no existing distribution.

**Logic:**
```python
for expense in self:
    project = expense.sale_order_id.project_id
    if not project or expense.analytic_distribution:
        continue  # Skip if no SO project or already has distribution
    if not project.account_id:
        project._create_analytic_account()  # Auto-create AA if missing
    expense.analytic_distribution = project._get_analytic_distribution()
```

**Key behaviors:**
- Only applies when the expense is linked to a sale order that is attached to a project.
- If the project's analytic account does not exist yet, it is created on-the-fly via `project._create_analytic_account()`.
- If the expense already has an `analytic_distribution`, it is left unchanged (user-set values are preserved).
- This ensures the expense's analytic lines will be charged against the project's analytic account, which is what powers the profitability report.

---

### 3. `account.move.line` (in `models/account_move_line.py`)

**File:** `models/account_move_line.py`

Extends the `sale_expense` extension of `account.move.line`.

#### Method: `_sale_determine_order()`

```python
def _sale_determine_order(self):
```

Overrides the normal invoice-to-SO mapping logic to also consider mappings derived from expenses. The base `sale_expense` already provides `_get_so_mapping_from_expense`; this module's override extends it by merging the mapping with the one derived from the project analytic account.

**Combined mapping sources (in priority order):**
1. **From project analytic accounts:** `mapping_from_project` via `_get_so_mapping_from_project()` (inherited from `account_move_line` base).
2. **From expense sale_order_id:** `mapping_from_expense` via `_get_so_mapping_from_expense()` (from `sale_expense`).

```python
mapping_from_project = self._get_so_mapping_from_project()
mapping_from_expense = self._get_so_mapping_from_expense()
mapping_from_project.update(mapping_from_expense)  # expense mapping takes precedence
return mapping_from_project
```

**Why this matters:**
When a vendor bill (account move) is created from an expense that has a sale order, the expense-to-SO mapping must be applied after any project-based mapping. This ensures the expense line is correctly linked to the sale order for reinvoicing.

---

## Field Reference

### `hr.expense` Fields (added by `sale_expense` + `project_sale_expense`)

| Field | Type | Description |
|-------|------|-------------|
| `sale_order_id` | Many2one `sale.order` | Customer sale order to reinvoice this expense to. Compute-like field (writable) that resets `analytic_distribution` on change. |
| `sale_order_line_id` | Many2one `sale.order.line` | The generated SOL that represents this expense on the SO. Computed, read-only. |
| `can_be_reinvoiced` | Boolean | True if `product_id.expense_policy` is `'sales_price'` or `'cost'`. |

### `sale.order` Fields (added by `sale_expense`)

| Field | Type | Description |
|-------|------|-------------|
| `expense_ids` | One2many `hr.expense` | All posted/in_payment/paid expenses linked to this SO. Domain: `state in ('posted', 'in_payment', 'paid')`. |
| `expense_count` | Integer | Count of expense lines across all SOLs of this SO. |

### `sale.order.line` Fields (added by `sale_expense`)

| Field | Type | Description |
|-------|------|-------------|
| `expense_ids` | One2many `hr.expense` | Expenses that generated this SOL (inverse of `hr.expense.sale_order_line_id`). |
| `is_expense` | Boolean (in `sale`) | True for SOLs created from expense/vendor bill reinvoicing. Used to filter in profitability and `_get_qty_delivered_method`. |

---

## Expense-to-Sale Order Flow (L3: Cross-Model Integration)

### Complete Workflow

```
1. Employee creates hr.expense with sale_order_id pointing to confirmed SO
         |
2. Officer/manager approves expense (action_approve)
         |
3. User posts expense (action_post)
   -> project_sale_expense checks if project has analytic account
      -> creates AA if missing
   -> sets analytic_distribution to project's distribution
   -> hr_expense.account_move creates vendor bill (account.move)
         |
4. Vendor bill lines trigger _sale_can_be_reinvoice
   -> sale_expense checks expense_policy + sale_order_id
   -> if reinvoiceable, calls _sale_create_reinvoice_sale_line
         |
5. SOL created: is_expense=True, expense_ids linked
   -> qty_delivered is set via analytic computation
   -> product_uom_qty = expense.quantity (from _sale_prepare_sale_line_values)
         |
6. Customer invoice created from SO (advance payment or milestone)
   -> invoice line_ids are flagged via _get_already_included_profitability_invoice_line_ids
   -> revenue appears in expenses section (not sales section)
         |
7. Project profitability panel shows:
   costs:     -expense.untaxed_amount (what employee cost)
   revenues:   SOL.untaxed_amount_to_invoice / invoiced (what customer pays)
```

### Analytic Distribution Merge Logic (L3: Edge Cases)

When an expense with a `sale_order_id` is created or posted, its `analytic_distribution` is computed by merging two sources:

**Scenario A — Different analytic plans (e.g., "Project" vs "Financial"):**
```
expense.analytic_distribution = {
    'analytic_account_from_expense': 100,   # from distribution model
    'analytic_account_from_project':  100,  # from sale_order.project_id
}
```

**Scenario B — Same analytic plan:**
```
expense.analytic_distribution = {
    'analytic_account_from_project': 100  # project takes priority
}
```
The expense's own distribution on the same plan is discarded to prevent duplicate entries in the analytic ledger.

**Scenario C — No project on SO:**
```
expense.analytic_distribution = {
    'analytic_account_from_expense': 100  # only distribution model applies
}
```

**Scenario D — No distribution model, but has project:**
```
expense.analytic_distribution = project._get_analytic_distribution()
```

---

## Profitability Report Integration (L3: Workflow Triggers)

The project profitability panel is driven by several method calls:

```
User views project form
  -> project_profitability.py calls _get_profitability_values()
       -> _get_profitability_items()
            -> _get_items_from_aal()              (analytic line items)
            -> project_hr_expense._get_expenses_profitability_items()  (expense costs)
            -> project_sale_expense._get_expenses_profitability_items() (expense costs + revenues)
```

**Profitability data shape:**

```python
{
    'revenues': {
        'data': [{
            'id': 'expenses',
            'sequence': 13,
            'invoiced': <float>,    # from SOL.untaxed_amount_invoiced
            'to_invoice': <float>,  # from SOL.untaxed_amount_to_invoice
        }],
        'total': {'invoiced': <float>, 'to_invoice': <float>}
    },
    'costs': {
        'data': [{
            'id': 'expenses',
            'sequence': 13,
            'billed': <float>,      # from expense.untaxed_amount_currency (negative)
            'to_bill': 0.0,
            'action': {...}         # only if user is expense team approver
        }],
        'total': {'billed': <float>, 'to_bill': 0.0}
    }
}
```

**State transitions affecting profitability:**

| Expense State | Effect on Profitability |
|--------------|--------------------------|
| `draft` | Not shown |
| `submitted` | Not shown |
| `approved` | Not shown |
| `posted` | Shown in costs (billed) |
| `in_payment` | Shown in costs (billed) |
| `paid` | Shown in costs (billed) |
| `refused` | Never shown |

---

## Double-Counting Prevention (L3: Failure Mode)

**The problem:** When an expense is posted and reinvoiced, Odoo creates:
1. A vendor bill (account.move) for the expense
2. A SOL (`is_expense=True`) on the sale order
3. A customer invoice line when the SO is invoiced

Both the vendor bill line (via `_get_already_included_profitability_invoice_line_ids`) and the customer invoice line (in the normal sales revenue section) could independently appear in the project's profitability report.

**The solution:** `project_sale_expense` overrides `_get_already_included_profitability_invoice_line_ids` to add all customer invoice lines from SOs that have posted expenses on the project into the exclusion list. These lines are then filtered out by the parent `_get_revenues_items_from_sol` method, so they do **not** appear in the regular sales revenue panel. Instead, their revenue is captured in the `expenses` revenues section.

**Test case `test_project_profitability_2` validates this:**
```python
# Create expense -> post -> create invoice from SO -> post invoice
# Revenue from expense's SOL should appear in expenses section
# Revenue from invoice should NOT appear in regular sales section
project_profitability['revenues']['data'] == [
    expense_profitability['revenues'],  # from expenses section
    revenue_items_from_sol['data'][0],  # from sales section (non-expense SOL only)
]
```

---

## Performance Considerations (L4)

### Read Group Optimizations

`_get_expenses_profitability_items` uses `_read_group` with array aggregation:
```python
aggregates=['id:array_agg', 'untaxed_amount_currency:sum']
```
This avoids N+1 queries when collecting expense IDs for the action button — all IDs are returned in a single query per group.

### Currency Conversion

Currency conversion is done in a loop over currencies, not per-record:
```python
for currency, untaxed_sum in dict_amount_per_currency.items():
    amount_billed += currency._convert(untaxed_sum, self.currency_id, ...)
```
This is optimal — O(number of currencies) instead of O(number of expense records).

### Prefetch Optimization in `_compute_analytic_distribution`

```python
analytic_account_model = self.env['account.analytic.account'].with_prefetch(prefetch_ids)
```
All analytic account records needed in the loop are prefetched by ID before iteration, avoiding repeated lookups.

### When `with_action=False`

When called from the profitability panel (via `_get_profitability_items(False)`), the action button computation is skipped. Expense IDs are only collected when `can_see_expense=True`, reducing unnecessary data gathering.

---

## Security (L4)

### Access Control

| Operation | Required Group |
|-----------|----------------|
| View expense in profitability costs | `project.group_project_user` (base visibility) |
| See clickable action on costs/revenues | `hr_expense.group_hr_expense_team_approver` |
| Submit/approve/post expenses | `hr_expense.group_hr_expense_user` / `group_hr_expense_team_approver` |
| Link expense to SO | `sale_expense` does not add groups; relies on `hr.expense` ACLs |
| View project profitability | `project.group_project_manager` |

### Field-Level Security

No field-level (`groups=`) restrictions are applied in this module. Access control relies on:
- Model-level ACLs from `hr_expense` and `sale_expense`
- Record rules (if defined)
- The `can_see_expense` guard in profitability methods

### SQL Injection Risk

All queries use the ORM's `_read_group` and `search` methods. No raw SQL with user input. Safe.

---

## Odoo 18 to Odoo 19 Changes (L4)

### Major Changes in Odoo 19

1. **Removal of `hr_expense.sheet` model:** In Odoo 18, expenses were grouped into sheets (`hr.expense.sheet`). In Odoo 19, sheets no longer exist — expenses are individual records. This affects the profitability query which no longer filters by sheet.

2. **`analytic_distribution` replaces `account_analytic_id`:** The `account_id` field on expenses was replaced with `analytic_distribution` (JSON/array field) in Odoo 17+ and became fully dominant in Odoo 19. Queries filter on `analytic_distribution` using the `in` operator on account IDs.

3. **`is_expense` field on `sale.order.line`:** Introduced in Odoo 17+ as part of the sale expense module. Used to identify which SOLs were created from reinvoiced expenses.

4. **No more workflow engine:** State transitions are handled via explicit action methods (`action_submit`, `action_approve`, `action_post`) rather than the deprecated XML workflow engine. Profitability queries filter on `state in ['posted', 'in_payment', 'paid']` directly.

5. **`Domain` class:** The `Domain` class from `odoo.fields` is used instead of plain domain lists in `_get_add_purchase_items_domain` and `_get_profitability_aal_domain`.

6. **Multi-company currency handling:** The `_get_expenses_profitability_items` method properly handles expenses from different companies/currencies using `currency._convert()`.

7. **`sale_order_id` domain behavior:** The `sale_order_id` field on `hr.expense` has a domain `[('state', '=', 'sale')]` for display, but is activated through the `sale_expense_all_order` context key during name search to allow selecting from all confirmed SOs.

---

## Test Coverage

### `test_project_sale_expense.py`

**`TestSaleExpense.test_analytic_account_expense_policy`**
Tests that when a product's expense policy is changed from `cost` to `can_be_expensed=False`, the SO does not get a `project_account_id` set. Verifies the interaction between `sale_project` and expense policy logic.

**`TestSaleExpense.test_compute_analytic_distribution_expense`**
Tests the analytic distribution merge logic:
- When project has a different analytic plan than the expense: both distributions are applied.
- When project has no analytic account: only the expense's distribution applies.
- When project and expense share the same plan: only the project's distribution applies.

**`TestSaleExpense.test_change_product_expense_policy_analytic_distribution`**
Tests that changing an expense policy on a product does NOT recompute the analytic distribution on existing expenses. Verifies distribution stability.

### `test_project_profitability.py`

**`TestProjectSaleExpenseProfitability.test_project_profitability`**
Full end-to-end test covering:
- Expense creation linked to SO and project
- Expense approval and posting
- SOL creation with `is_expense=True`
- Customer invoice creation and posting
- Credit note (reverse invoice) handling
- SO cancellation effects on profitability
- Unlinking vendor bill (reset to approved) effects
- Multi-currency scenarios (foreign company/employee)

**`TestProjectSaleExpenseProfitability.test_project_profitability_2`**
Tests that customer invoices linked to re-invoiced expenses do NOT appear in the regular sales revenues section of profitability, confirming the double-counting prevention logic works correctly.

---

## Key Design Patterns

### Classic Inheritance (`_inherit`)

All extensions in this module use classic inheritance (`_inherit = 'model.name'`). No new tables are created — the extensions add fields and methods to existing tables.

### Method Extension via `super()`

All overridden methods call `super()` to preserve the parent chain:

```python
def _get_already_included_profitability_invoice_line_ids(self):
    move_line_ids = super()._get_already_included_profitability_invoice_line_ids()
    # ... add expense-related lines ...
    return move_line_ids
```

### Prefetch Optimization

The pattern used in `_compute_analytic_distribution` is noteworthy:

```python
prefetch_ids = set()
for expense in self.filtered('sale_order_id'):
    prefetch_ids.update(analytic_mixin._get_analytic_account_ids_from_distributions(...))
analytic_account_model = self.env['account.analytic.account'].with_prefetch(prefetch_ids)
for expense in expenses_to_recompute:
    #analytic_account_model.browse(...) uses prefetch
```

This collects all needed record IDs first, then passes them to the prefetch cache before iterating.

### Context-Based Circuit Breaking

```python
if not self.env.context.get('project_id'):
    # ... merge logic ...
```
The `project_id` context flag prevents circular calls when analytic distribution is recomputed from a project-level context.

---

## Related Modules

| Module | Description |
|--------|-------------|
| [Modules/hr_expense](hr_expense.md) | Base expense management (sheets removed in Odoo 19) |
| [Modules/sale_expense](sale_expense.md) | Links expenses to sale orders; creates SOLs on vendor bill posting |
| [Modules/project_hr_expense](project_hr_expense.md) | Shows expense costs on project profitability |
| [Modules/sale_project](sale_project.md) | Links sale orders to projects |
| [Modules/Project](Project.md) | Base project model with profitability framework |

## File Listing

```
project_sale_expense/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── account_move_line.py   # _sale_determine_order override
│   ├── hr_expense.py          # _compute_analytic_distribution, action_post
│   └── project_project.py     # _get_expenses_profitability_items, _get_already_included_...
└── tests/
    ├── __init__.py
    ├── test_project_profitability.py
    └── test_project_sale_expense.py
```

#odoo #odoo19 #modules #project #expense #sale #profitability #integration
