---
tags: [odoo, odoo17, flow, analytic, cost-tracking, distribution]
---

# Analytic Distribution Flow — Odoo 17

Complete guide to how Odoo 17 distributes amounts across analytic accounts using JSON distributions, how analytic lines are created, and how plans are managed dynamically.

---

## Overview

Analytic accounting in Odoo tracks costs and revenues across configurable dimensions called **plans** (commonly used as projects, departments, or cost centers). Unlike the general ledger, which is legally required and immutable after posting, analytic accounts are a managerial reporting layer.

---

## Analytic Distribution — JSON Format

### Storage on `account.move.line`

**File:** `account/models/account_move_line.py:L381`

```python
analytic_distribution = fields.Json(
    string='Analytic Distribution',
    store=True,
)
```

### Structure
```python
{
    str(analytic_account_id): float(percentage),
    str(analytic_account_id2): float(percentage2),
}
```

### Example
```python
{
    "12": 70.0,    # 70% to Project Alpha (id=12)
    "15": 30.0,    # 30% to Department Beta (id=15)
}
```

### Key Rules
- Keys are **stringified** account IDs (JSON constraint)
- Percentages are floats (e.g., `70.0`, not `70`)
- Percentages **can** sum to ≠ 100% — Odoo allows under/over-allocation
- Percentages **should** sum to 100% for complete allocation
- An empty dict `{}` or `None` means **no distribution**
- At least one entry required if `analytic_distribution` is set

### Cross-Plan Distribution
The same `analytic_distribution` dict can contain accounts from **different plans**:
```python
{
    "12": 50.0,    # Project plan: 50%
    "23": 50.0,   # Department plan: 50%
}
```
Each plan's accounts are tracked independently. When a line totals 100% on one plan but only 50% on another, the second plan shows under-allocation.

---

## The `auto_account_id` Magic Field

**File:** `analytic/models/analytic_account.py:L54`

`account.analytic.line` has a field that switches context based on `analytic_plan_id`:

```python
auto_account_id = fields.Many2one(
    'account.analytic.account',
    compute='_compute_auto_account',
    inverse='_inverse_auto_account',
    search='_search_auto_account',
)

@api.depends_context('analytic_plan_id')
def _compute_auto_account(self):
    plan = self.env['account.analytic.plan'].browse(
        self.env.context.get('analytic_plan_id')
    )
    for line in self:
        line.auto_account_id = bool(plan) and line[plan._column_name()]
```

**Purpose:** The `account.analytic.line` table stores only **one** account column per plan. When the UI or ORM reads with a specific `analytic_plan_id` in context, `auto_account_id` returns the right account. Without the context, it returns nothing.

---

## Dynamic Plan Columns

### How They Are Created

**File:** `analytic/models/analytic_plan.py:L265`

When a plan is created or renamed, `_sync_plan_column()` creates a **custom column** on `account_analytic_line`:

```python
def _sync_plan_column(self):
    for plan in self:
        prev = plan._find_plan_column()

        if plan.parent_id and prev:
            prev.unlink()                    # child plans reuse parent's column
        elif prev:
            prev.field_description = plan.name  # rename
        elif not plan.parent_id:
            column = plan._strict_column_name()
            # Creates a manual Many2one field on account.analytic.line:
            field = self.env['ir.model.fields'].with_context(
                update_custom_fields=True
            ).sudo().create({
                'name': column,
                'field_description': plan.name,
                'state': 'manual',
                'model': 'account.analytic.line',
                'model_id': ...,
                'ttype': 'many2one',
                'relation': 'account.analytic.account',
                'store': True,
                'index': True,
            })
```

### Naming Convention

**File:** `analytic/models/analytic_plan.py:L116`

```python
def _strict_column_name(self):
    project_plan, _other_plans = self._get_all_plans()
    return 'account_id' if self == project_plan else f"x_plan{self.id}_id"
```

- The **Project plan** (configured via `analytic.project_plan` config param) gets the column named `account_id`
- Other plans get `x_plan{id}_id` — e.g., `x_plan3_id`, `x_plan7_id`

### The Project Plan
```python
@ormcache()
def __get_all_plans(self):
    project_plan = self.browse(int(
        self.env['ir.config_parameter'].sudo().get_param('analytic.project_plan', 0)
    ))
    if not project_plan:
        raise UserError(_("A 'Project' plan needs to exist..."))
    other_plans = self.sudo().search([('parent_id', '=', False)]) - project_plan
    return project_plan.id, other_plans.ids
```
Exactly one plan is designated as the **Project plan** — used as the default for most business workflows.

---

## Analytic Line Creation — `_create_analytic_lines()`

### Trigger Point

**File:** `account/models/account_move.py:L3988`

```python
def _post(self, soft=True):
    ...
    to_post.line_ids._create_analytic_lines()
    ...
```

Analytic lines are created when an `account.move` is **posted** (validated). They are **deleted on unpost** (line 4261).

### The Creation Method

**File:** `account/models/account_move_line.py:L3198`

```python
def _create_analytic_lines(self):
    """ Create analytic items upon validation of an account.move.line
        having an analytic distribution. """
    self._validate_analytic_distribution()   # raises if mandatory missing
    analytic_line_vals = []
    for line in self:
        analytic_line_vals.extend(line._prepare_analytic_lines())
    context = dict(self.env.context)
    context.pop('default_account_id', None)
    self.env['account.analytic.line'].with_context(context).create(analytic_line_vals)
```

### `_prepare_analytic_lines()`

**File:** `account/models/account_move_line.py:L3210`

```python
def _prepare_analytic_lines(self):
    self.ensure_one()
    analytic_line_vals = []
    if self.analytic_distribution:
        distribution_on_each_plan = {}
        for account_ids, distribution in self.analytic_distribution.items():
            line_values = self._prepare_analytic_distribution_line(
                float(distribution), account_ids, distribution_on_each_plan
            )
            if not self.company_currency_id.is_zero(line_values.get('amount')):
                analytic_line_vals.append(line_values)
        self._round_analytic_distribution_line(analytic_line_vals)
    return analytic_line_vals
```

For each entry in the `analytic_distribution` dict, one `account.analytic.line` is created.

### `_prepare_analytic_distribution_line()`

**File:** `account/models/account_move_line.py:L3225`

```python
def _prepare_analytic_distribution_line(self, distribution, account_ids, distribution_on_each_plan):
    self.ensure_one()
    account_field_values = {}
    decimal_precision = self.env['decimal.precision'].precision_get('Percentage Analytic')
    amount = 0
    for account in self.env['account.analytic.account'].browse(
        map(int, account_ids.split(","))
    ).exists():
        distribution_plan = distribution_on_each_plan.get(account.root_plan_id, 0) + distribution
        if float_compare(distribution_plan, 100, precision_digits=decimal_precision) == 0:
            # Last account in this plan: assign remaining amount (fix rounding)
            amount = -self.balance * (100 - distribution_on_each_plan.get(account.root_plan_id, 0)) / 100.0
        else:
            amount = -self.balance * distribution / 100.0
        distribution_on_each_plan[account.root_plan_id] = distribution_plan
        account_field_values[account.plan_id._column_name()] = account.id

    default_name = self.name or (self.ref or '/' + ' -- ' + (self.partner_id.name or '/'))
    return {
        'name': default_name,
        'date': self.date,
        **account_field_values,           # sets x_plan{id}_id or account_id
        'partner_id': self.partner_id.id,
        'unit_amount': self.quantity,
        'product_id': self.product_id.id or False,
        'product_uom_id': self.product_uom_id.id or False,
        'amount': amount,                   # negative for debits, positive for credits
        'general_account_id': self.account_id.id,
        'ref': self.ref,
        'move_line_id': self.id,
        'user_id': self.move_id.invoice_user_id.id or self._uid,
        'company_id': self.company_id.id,
        'category': (
            'invoice' if self.move_id.is_sale_document()
            else 'vendor_bill' if self.move_id.is_purchase_document()
            else 'other'
        ),
    }
```

**Key behavior:** When multiple accounts belong to the **same root plan**, the last account in the JSON dict receives the remainder to fix rounding errors, ensuring the plan sums exactly to 100%.

### Rounding — `_round_analytic_distribution_line()`

**File:** `account/models/account_move_line.py:L3259`

```python
def _round_analytic_distribution_line(self, analytic_lines_vals):
    if not analytic_lines_vals:
        return
    rounding_error = 0
    for line in analytic_lines_vals:
        rounded_amount = self.company_currency_id.round(line['amount'])
        rounding_error += rounded_amount - line['amount']  # accumulate error
        line['amount'] = rounded_amount

    # distribute rounding error across lines
    for line in analytic_lines_vals:
        if self.company_currency_id.is_zero(rounding_error):
            break
        amt = max(
            self.company_currency_id.rounding,
            abs(self.company_currency_id.round(rounding_error / len(analytic_lines_vals)))
        )
        if rounding_error < 0.0:
            line['amount'] += amt
            rounding_error += amt
        else:
            line['amount'] -= amt
            rounding_error -= amt
```

All amounts are rounded to currency precision. The total rounding error is distributed across the first N-1 lines until it is absorbed.

---

## Auto-Populate via Distribution Models

### `account.analytic.distribution.model`

**File:** `analytic/models/analytic_distribution_model.py:L13`

Automatically fills `analytic_distribution` on `account.move.line` when a line is created from an invoice, bill, or journal entry.

#### Model Fields
| Field | Type | Description |
|-------|------|-------------|
| `analytic_distribution` | Json | Distribution to apply |
| `partner_id` | Many2one | Match on specific partner |
| `partner_category_id` | Many2one | Match on partner category |
| `company_id` | Many2one | Match on specific company |
| `account_prefix` | Char | Match on account code prefix |
| `product_id` | Many2one | Match on specific product |
| `product_categ_id` | Many2one | Match on product category |

#### How Auto-Population Works

**File:** `account/models/account_move_line.py:L1168`

```python
def _compute_analytic_distribution(self):
    cache = {}
    for line in self:
        if line.display_type == 'product' or not line.move_id.is_invoice(include_receipts=True):
            arguments = frozendict({
                "product_id": line.product_id.id,
                "product_categ_id": line.product_id.categ_id.id,
                "partner_id": line.partner_id.id,
                "partner_category_id": line.partner_id.category_id.ids,
                "account_prefix": line.account_id.code,
                "company_id": line.company_id.id,
            })
            if arguments not in cache:
                cache[arguments] = self.env['account.analytic.distribution.model']\
                    ._get_distribution(arguments)
            line.analytic_distribution = cache[arguments] or line.analytic_distribution
```

Triggered during invoice/posting flow when `display_type == 'product'` or for non-invoice journal entries.

#### The Matching Algorithm — `_get_distribution()`

**File:** `analytic/models/analytic_distribution_model.py:L64`

```python
@api.model
def _get_distribution(self, vals):
    domain = []
    for fname, value in vals.items():
        domain += self._create_domain(fname, value) or []

    best_score = 0
    res = {}
    fnames = set(self._get_fields_to_check())

    for rec in self.search(domain):
        try:
            score = sum(
                rec._check_score(key, vals.get(key)) for key in fnames
            )
            if score > best_score:
                res = rec.analytic_distribution
                best_score = score
        except NonMatchingDistribution:
            continue
    return res
```

**Scoring system:**
- Each matching field = +1 point
- Company-specific match = +1 point; shared model match = +0.5 points
- The **highest-scoring** model wins

```python
def _check_score(self, key, value):
    if key == 'company_id':
        if not self.company_id or value == self.company_id.id:
            return 1 if self.company_id else 0.5
        raise NonMatchingDistribution
    if not self[key]:
        return 0
    if value and ((self[key].id in value) if isinstance(value, (list, tuple))
                  else (value.startswith(self[key])) if key.endswith('_prefix')
                  else (value == self[key].id)):
        return 1
    raise NonMatchingDistribution
```

**Domain building:**
```python
def _create_domain(self, fname, value):
    if not value:
        return False
    if fname == 'partner_category_id':
        value += [False]                       # include "unspecified" category
        return [(fname, 'in', value)]
    else:
        return [(fname, 'in', [value, False])]  # match value OR any/unset
```

---

## Analytic Plans — Applicability System

### Plan Structure

**File:** `analytic/models/analytic_plan.py`

Each plan has:
- `name`, `description`
- `parent_id` — for hierarchical plans (child plans inherit parent column)
- `color` — for UI display
- `sequence` — determines display order
- `default_applicability` — company-dependent default (optional/mandatory/unavailable)
- `applicability_ids` — per-business-domain override rules

### Applicability Rules

**File:** `analytic/models/analytic_plan.py:L206`

```python
def get_relevant_plans(self, **kwargs):
    project_plan, other_plans = self.env['account.analytic.plan']._get_all_plans()
    root_plans = (project_plan + other_plans).filtered(lambda p: (
        p.all_account_count > 0
        and not p.parent_id
        and p._get_applicability(**kwargs) != 'unavailable'
    ))
```

Called in the UI when displaying analytic distribution widgets. A plan is shown if:
1. It has at least one account
2. It has no parent
3. Its applicability for the current business domain ≠ 'unavailable'

---

## Complete End-to-End Flow: Sale Invoice

```
1. User confirms Sale Order
       │
2. Delivery Order validated
       │  → creates stock.move (no analytic lines yet)
       │
3. User creates and posts Customer Invoice
       │
   account.move._post()
       │
   Step: _recompute_dynamic_lines()
       │
   Step: to_post.line_ids._create_analytic_lines()
       │
   For each posted invoice line:
   ┌──────────────────────────────────────────────┐
   │ line._prepare_analytic_lines()               │
   │                                              │
   │ if line.analytic_distribution:               │
   │   for account_id, pct in dist.items():      │
   │     amount = -line.balance * pct / 100       │
   │     vals = {                                 │
   │       'name': line.name,                     │
   │       'account_id': account_id,              │
   │       'amount': amount,         # negative  │
   │       'date': line.date,                     │
   │       'move_line_id': line.id,               │
   │       'category': 'invoice',                 │
   │     }                                        │
   │     analytic_line_vals.append(vals)          │
   │                                              │
   │ _round_analytic_distribution_line(vals)      │
   │                                              │
   │ account.analytic.line.create(vals)          │
   └──────────────────────────────────────────────┘
       │
4. Analytic lines created
       │  One line per (account, percentage) entry
       │  Amount = -balance * pct/100 (negative for revenue)
       │
5. User receives payment → Register Payment
       │
   account.payment.register._create_payments()
       │
   _reconcile_payments()
       │
   (payment_line + invoice_receivable_line).reconcile()
       │
   Creates account.partial.reconcile
       │
   Invoice payment_state → 'paid'
       │
6. Analytic lines on the invoice remain unchanged
       │  (analytic lines are created at post time, not payment time)
       │  Unless CABA tax: then CABA move creates additional analytic lines
```

---

## Complete End-to-End Flow: Purchase Bill

```
1. Purchase Order confirmed
       │
2. Receipt validated
       │
3. Vendor Bill posted
       │
   account.move._post()
       │
   For each bill line (display_type='product'):
   ┌──────────────────────────────────────────────┐
   │ line._compute_analytic_distribution()        │
   │   → calls _get_distribution() on models     │
   │   → auto-fills line.analytic_distribution   │
   │                                              │
   │ line._create_analytic_lines()                │
   │   → amount = -line.balance * pct / 100      │
   │   → Creates account.analytic.line records    │
   │   → Amount is positive (debit = expense)     │
   └──────────────────────────────────────────────┘
       │
4. User pays bill via Register Payment
       │
   Creates account.payment.move
   Reconciles payment line with bill receivable line
       │
5. Analytic lines visible on Analytic Account report
       │  Revenue (negative) from sales
       │  Costs (positive) from purchases
       │
6. Analytic Account balance = Revenue - Costs
```

---

## Validation — `_validate_analytic_distribution()`

**File:** `account/models/account_move_line.py:L3165`

```python
def _validate_analytic_distribution(self):
    for line in self.filtered(lambda line: line.display_type == 'product'):
        try:
            line._validate_distribution(
                company_id=line.company_id.id,
                product=line.product_id.id,
                account=line.account_id.id,
                business_domain=(
                    'invoice' if line.move_id.is_sale_document(True)
                    else 'bill' if line.move_id.is_purchase_document(True)
                    else 'general'
                ),
            )
        except ValidationError:
            # raises if plan is mandatory but no distribution set
            # or if distribution does not sum to 100%
            lines_with_missing_analytic_distribution += line
```

Called inside `_create_analytic_lines()`. If any line requires 100% distribution on a mandatory plan and doesn't have it, raises `ValidationError` or `RedirectWarning`.

---

## Analytic Account — Balance Computation

**File:** `analytic/models/analytic_account.py:L138`

```python
@api.depends('line_ids.amount')
def _compute_debit_credit_balance(self):
    for plan, accounts in self.grouped('plan_id').items():
        # Read-group by (plan_column, currency_id) → sum(amount)
        credit_groups = self.env['account.analytic.line']._read_group(
            domain=domain + [(plan._column_name(), 'in', self.ids), ('amount', '>=', 0.0)],
            groupby=[plan._column_name(), 'currency_id'],
            aggregates=['amount:sum'],
        )
        # Similar for debit (amount < 0)
        for account in accounts:
            account.debit = -data_debit.get(account.id, 0.0)
            account.credit = data_credit.get(account.id, 0.0)
            account.balance = account.credit - account.debit
```

`balance` is the sum of all `amount` values on analytic lines linked to this account:
- Positive `amount` (costs/expenses) → debit increases balance
- Negative `amount` (revenues) → credit decreases balance

---

## See Also
- [Modules/analytic](modules/analytic.md) — `account.analytic.account`, `account.analytic.plan`
- [Modules/account](modules/account.md) — `account.move.line`, `analytic_distribution` field
- [Flows/Cross-Module/accounting-reconciliation-flow](flows/cross-module/accounting-reconciliation-flow.md) — reconciliation that may trigger CABA
- [Flows/Sale/full-sale-to-cash-flow](flows/sale/full-sale-to-cash-flow.md) — sale with analytics end-to-end
- [Flows/Purchase/full-purchase-to-payment-flow](flows/purchase/full-purchase-to-payment-flow.md) — purchase with analytics end-to-end
