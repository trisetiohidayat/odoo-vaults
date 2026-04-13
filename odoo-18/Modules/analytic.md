---
Module: analytic
Version: Odoo 18
Type: Core
Tags: #odoo, #odoo18, #analytic, #accounting
---

# Analytic Accounting

**Addon:** `analytic` | **Version:** 1.2 | **Depends:** `base`, `mail`, `uom`
**Source:** `~/odoo/odoo18/odoo/addons/analytic/`

## Overview

The `analytic` module provides **Analytic Accounting** — multi-dimensional cost/revenue tracking that operates independently from the general ledger. Analytic accounts let you break down financial entries across projects, departments, regions, or any business dimension without affecting debits/credits in the accounting journal.

**Core principle:** Analytic lines are derived from journal entries. The `analytic_distribution` JSON field on move lines drives automatic creation of `account.analytic.line` records. The analytic ledger is a read-only projection of accounting data, not a source of truth.

**Multi-plan support:** Odoo 18 supports an unlimited number of independent analytic plans simultaneously. A single journal entry can distribute across multiple plans at once.

---

## Model Inventory

| Model | Type | File | Purpose |
|-------|------|------|---------|
| `account.analytic.plan` | Concrete | `models/analytic_plan.py` | A tracking dimension (e.g., Projects, Departments) |
| `account.analytic.account` | Concrete | `models/analytic_account.py` | A named account within a plan |
| `account.analytic.line` | Concrete | `models/analytic_line.py` | A posted amount against an account |
| `account.analytic.applicability` | Concrete | `models/analytic_plan.py` | Per-domain applicability rules |
| `analytic.mixin` | Abstract | `models/analytic_mixin.py` | Adds `analytic_distribution` JSON to any model |
| `analytic.plan.fields.mixin` | Abstract | `models/analytic_line.py` | Adds per-plan Many2one columns + magic `auto_account_id` |
| `account.analytic.distribution.model` | Concrete | `models/analytic_distribution_model.py` | Auto-populate distribution by partner/company |

---

## `account.analytic.plan`

**File:** `models/analytic_plan.py`

The plan is the top-level analytic **dimension**. There is exactly one designated **"Project" plan** tracked by `analytic.project_plan` system parameter. All other root plans are secondary dimensions.

```python
class AccountAnalyticPlan(models.Model):
    _name = 'account.analytic.plan'
    _parent_store = True
    _order = 'sequence asc, id'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Plan name (required, translateable, inverse syncs columns) |
| `description` | Text | Free-text description |
| `parent_id` | Many2one(self) | Parent plan for hierarchical sub-plans |
| `parent_path` | Char | Materialized path for hierarchy (indexed btree) |
| `root_id` | Many2one(self) | Computed topmost ancestor; self if root |
| `children_ids` | One2many(self) | Direct child plans |
| `children_count` | Integer | Direct child count |
| `complete_name` | Char | Full hierarchical name "Parent / Child / ..." (recursive, stored) |
| `account_ids` | One2many(`account.analytic.account`) | Direct accounts in this plan |
| `account_count` | Integer | Direct account count |
| `all_account_count` | Integer | Account count including all descendant plans |
| `color` | Integer | Random color 1-11 for kanban UI |
| `sequence` | Integer | Display ordering (default 10) |
| `default_applicability` | Selection | `optional` / `mandatory` / `unavailable` (company-dependent) |
| `applicability_ids` | One2many(`account.analytic.applicability`) | Per-business-domain + company rules |

### Dynamic Column Generation (L4)

Each **root plan** dynamically creates a **stored `Many2one` column** on every model inheriting `analytic.plan.fields.mixin`. The column is created via `ir.model.fields` at runtime when a new plan is saved.

```python
def _strict_column_name(self):
    # Project plan → 'account_id' (magic canonical name)
    # Other root plans → 'x_plan{N}_id'
    return 'account_id' if self == project_plan else f"x_plan{self.id}_id"

def _column_name(self):
    return self.root_id._strict_column_name()  # always resolves to root's column name
```

`_sync_plan_column(model)` creates/deletes `ir.model.fields` records. The column name is derived from the root plan. For child plans, a **related (non-stored) field** is created instead, enabling grouping by sub-plan levels:

```python
def _hierarchy_name(self):
    # For depth=0 root: returns 'x_account_id_0' or 'x_x_plan{N}_id_0'
    # For depth=1 child: returns 'x_account_id_1' etc.
    depth = self.parent_path.count('/') - 1
    fname = f"{self._column_name()}_{depth}"
    if fname.startswith('account_id'):
        fname = f'x_{fname}'
    return depth, fname
```

### `__get_all_plans()` — Cached Plan Lookup

```python
@ormcache()
def __get_all_plans(self):
    project_plan = self.browse(int(self.env['ir.config_parameter'].sudo().get_param('analytic.project_plan', 0)))
    other_plans = self.sudo().search([('parent_id', '=', False)]) - project_plan
    return project_plan.id, other_plans.ids
```

The `analytic.project_plan` config parameter holds the ID of the designated project plan. If not set, creating a plan without this designation raises an error.

### `get_relevant_plans()` — Applicability Resolution

```python
def get_relevant_plans(self, **kwargs):
    # Returns root plans that:
    # 1. Have all_account_count > 0
    # 2. Are root plans (no parent_id)
    # 3. Have applicability != 'unavailable'
    # Plus forced_plans: accounts already selected that would otherwise be excluded
    # Result: list of dicts {id, name, color, applicability, all_account_count, column_name}
```

### `write()` — Plan Migration

When `parent_id` changes (plan gets a parent or is de-parented), `_update_accounts_in_analytic_lines()` migrates all related `account.analytic.account` lines to the appropriate plan column before the old column is unlinked.

### Unlink

```python
def unlink(self):
    # 1. Remove dynamic field created with the plan
    # 2. Remove related hierarchy-level fields
    # 3. Clear registry cache
```

---

## `account.analytic.account`

**File:** `models/analytic_account.py`

```python
class AccountAnalyticAccount(models.Model):
    _name = 'account.analytic.account'
    _inherit = ['mail.thread']
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Account name (required, trigram index, translateable, tracking) |
| `code` | Char | Reference number (B-tree index, tracking) |
| `active` | Boolean | Deactivate to hide without deleting (tracking) |
| `plan_id` | Many2one(`account.analytic.plan`) | Parent plan (required) |
| `root_plan_id` | Many2one(`account.analytic.plan`) | Computed root plan (stored, related) |
| `color` | Integer | Inherited from plan (related) |
| `line_ids` | One2many(`account.analytic.line`) | Linked via `auto_account_id` magic field |
| `company_id` | Many2one(`res.company`) | Company restriction |
| `partner_id` | Many2one(`res.partner`) | Optional customer link (auto_join for fast name_search) |
| `balance` | Monetary | Computed: credit - debit |
| `debit` | Monetary | Sum of negative amounts displayed as positive |
| `credit` | Monetary | Sum of positive amounts |
| `currency_id` | Many2one | Related from company.currency_id |

### Display Name

```python
def _compute_display_name(self):
    # Format: [code] name - commercial_partner_name
```

### Debit/Credit/Balance Compute (L4)

```python
def _compute_debit_credit_balance(self):
    # Groups analytic lines by plan column + currency
    # Converts all amounts to company currency
    # Respects context filters: from_date, to_date
    # Uses _read_group_postprocess_aggregate for manual sum of computed fields
```

The compute groups by `plan._column_name()` to isolate each plan's lines. The `_read_group_select` override intercepts `balance:sum`, `debit:sum`, `credit:sum` aggregate specs and replaces them with `id:recordset`, then `_read_group_postprocess_aggregate` manually sums the field values across the grouped recordsets.

### `write()` — Plan Migration

```python
def write(self, vals):
    if vals.get('plan_id'):
        new_fname = new_plan._column_name()
        for plan, accounts in self.grouped('plan_id'):
            current_fname = plan._column_name()
            self._update_accounts_in_analytic_lines(new_fname, current_fname, accounts)
```

### Constraints

```python
@api.constrains('company_id')
def _check_company_consistency(self):
    # Cannot set company if any existing analytic line references this account
    # from a non-child company
```

---

## `account.analytic.line`

**File:** `models/analytic_line.py`

```python
class AccountAnalyticLine(models.Model):
    _name = 'account.analytic.line'
    _inherit = 'analytic.plan.fields.mixin'
```

Inherits **`analytic.plan.fields.mixin`** — gets one stored Many2one column per root plan. The line stores `amount` and routes it to the appropriate plan column.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Description (required) |
| `date` | Date | Transaction date (required, default today, indexed) |
| `amount` | Monetary | Signed amount (positive=credit/revenue, negative=debit/expense) |
| `unit_amount` | Float | Quantity |
| `product_uom_id` | Many2one(`uom.uom`) | Unit of measure |
| `product_uom_category_id` | Many2one | Related from uom |
| `partner_id` | Many2one(`res.partner`) | Business partner, check_company |
| `user_id` | Many2one(`res.users`) | Responsible user (default: current user) |
| `company_id` | Many2one(`res.company`) | Required, readonly, default: env.company |
| `currency_id` | Many2one | Related from company.currency_id (stored, compute_sudo) |
| `category` | Selection | `other` (extensible by other modules) |
| `analytic_distribution` | Json | Computed from plan columns; inverse splits lines |
| `auto_account_id` | Many2one(`account.analytic.account`) | Magic field routing to the right plan column |
| `account_id` | Many2one(`account.analytic.account`) | Per-plan direct field (from mixin) |

### `analytic_distribution` Compute/Inverse

```python
def _compute_analytic_distribution(self):
    # Returns {<comma_separated_account_ids>: 100}
    line.analytic_distribution = {line._get_distribution_key(): 100}

def _inverse_analytic_distribution(self):
    # User changes distribution in UI:
    # 1. _merge_distribution(old + new) resolves partial updates
    # 2. For each (account_ids, percentage): write amount * pct/100 to that account
    # 3. First account updates current line; remaining accounts create new lines via copy_data
    # 4. Sends bus notification: "N analytic lines created"
    # 5. Creates new lines via self.create(to_create_vals)
```

### `_split_amount_fname()`

Returns `'amount'` — used by the inverse to scale amounts across split lines. Override in subclasses to split `unit_amount` instead.

### Special Date Domain

```python
def _condition_to_sql(self, alias, fname, operator, value, query):
    # Supports special value 'fiscal_start_year' for date
    # Resolves to: date >= (fiscalyear_date_from - 1 year)
```

---

## `analytic.mixin` (Abstract)

**File:** `models/analytic_mixin.py`

Provides `analytic_distribution` JSON field to any model that posts to analytic accounting. Used by `account.move.line`, `purchase.order.line`, `sale.order.line`, `hr.expense`, `account.asset`, and others.

```python
class AnalyticMixin(models.AbstractModel):
    _name = 'analytic.mixin'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `analytic_distribution` | Json | Stores `{account_key: percentage, ...}` |
| `analytic_precision` | Integer | Caches decimal precision for percentages (not stored) |
| `distribution_analytic_account_ids` | Many2many(`account.analytic.account`) | Computed accounts from distribution |

### Distribution JSON Format

```json
{
  "12": 70.0,
  "34": 30.0
}
```

- **Keys:** comma-separated account ID strings (for cross-plan combos)
- **Values:** float percentages (normalized to `Percentage Analytic` precision)
- **`__update__` key:** signals which account IDs are being modified during partial updates

### GIN Index for Performance (L4)

```python
def init(self):
    # Creates GIN index on jsonb_path_query_array for fast key lookups:
    # regexp_split_to_array(jsonb_path_query_array(analytic_distribution, '$.keyvalue()."key"')::text, '\D+')
    # Enables: WHERE analytic_distribution && ARRAY['12','34']
```

### Domain Condition Override

```python
def _condition_to_sql(self, alias, fname, operator, value, query):
    # Intercepts: =, !=, ilike, not ilike, in, not in
    # Handles: str (name_search), int, bool
    # Uses GIN array overlap/contains for 'in'/'not in'
    # Translates string name lookups to id-based subqueries
```

### `_read_group_groupby` Override (L4)

When grouping by `analytic_distribution`, the query creates a **lateral subquery** that explodes JSON keys into rows per analytic account — enabling per-account aggregation even when lines distribute across multiple accounts:

```python
# Nested query explodes keys:
# SELECT DISTINCT move_id, (regexp_matches(keys, '\d+', 'g'))[1]::int AS account_id
# This allows count/sum per individual account
```

### Validation

```python
def _validate_distribution(self, **kwargs):
    # Called when validate_analytic context is set
    # Gets mandatory plans for business_domain + company
    # Checks each mandatory root plan sums to exactly 100%
    # Raises ValidationError otherwise
```

### Distribution Merge

```python
def _merge_distribution(old, new):
    # Handles partial updates via __update__ key
    # Non-changing plans: old values scaled proportionally
    # Changing plans: replaced by new values
    # Returns combined distribution dict
```

### Sanitization

```python
def _sanitize_values(self, vals, decimal_precision):
    # float_round all percentage values to configured precision
    # Skips '__update__' key (stores raw float)
```

---

## `account.analytic.distribution.model`

**File:** `models/analytic_distribution_model.py`

Auto-populates `analytic_distribution` on supported documents based on **partner, partner category, or company**.

```python
class AccountAnalyticDistributionModel(models.Model):
    _name = 'account.analytic.distribution.model'
    _inherit = 'analytic.mixin'
    _rec_name = 'create_date'
    _order = 'sequence, id desc'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Priority (default 10, lower = applied first) |
| `partner_id` | Many2one(`res.partner`) | Match by specific partner |
| `partner_category_id` | Many2one(`res.partner.category`) | Match by partner category |
| `company_id` | Many2one(`res.company`) | Match by company (empty = all companies) |
| `analytic_distribution` | Json | Inherited from mixin — the distribution to apply |

### Matching and Application Logic

```python
@api.model
def _get_applicable_models(self, vals):
    # vals: {company_id, partner_id, partner_category_id, ...}
    # For each field: domain includes [value, False] — match specific value OR unset
    # partner_category_id: uses 'in' operator with [value, False]
    return self.search(domain)

@api.model
def _get_distribution(self, vals):
    # Main entry point for auto-fill on document creation
    # 1. Get applicable models
    # 2. Skip models whose root plan is already covered by a prior model
    # 3. Accumulate distributions via dict union
    # Returns combined distribution dict
```

### `analytic_plan_defaults` System Parameter

The `ir.config_parameter` mechanism drives default plan applicability per business domain via `account.analytic.applicability` records (not directly in this module). The `get_relevant_plans()` method on plans reads applicability records to determine mandatory/optional/unavailable status.

---

## `account.analytic.applicability`

**File:** `models/analytic_plan.py`

Links a plan to a business domain with a specific applicability level.

```python
class AccountAnalyticApplicability(models.Model):
    _name = 'account.analytic.applicability'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `analytic_plan_id` | Many2one(`account.analytic.plan`) | The plan |
| `business_domain` | Selection | `general` (extensible by other modules) |
| `applicability` | Selection | `optional`, `mandatory`, `unavailable` |
| `company_id` | Many2one(`res.company`) | Company-specific rule (optional) |

### Score Logic

```python
def _get_score(self, **kwargs):
    # No company + no domain: score = 0
    # Company matches kwargs company_id: score += 0.5
    # business_domain matches kwargs business_domain: score += 1
    # business_domain doesn't match: score = -1 (exclude)
    # Returns highest-scoring applicability
```

---

## How Analytic Lines Are Created from Journal Entries

### Flow: Account Move Line → Analytic Lines

1. User posts an `account.move` with `analytic_distribution` JSON on one or more lines
2. The move line stores `analytic_distribution`: `{"12": 70.0, "34": 30.0}`
3. A business domain (e.g., `sale_order`, `purchase_order`) calls `validate_analytic` in context:
   ```python
   line.with_context(validate_analytic=True)._validate_distribution()
   ```
4. If a plan is **mandatory** for that domain and sum ≠ 100%, `ValidationError` is raised
5. The distribution is stored on the move line; analytic lines are created when the account moves are **confirmed**

### Distribution Model Auto-Fill on Document Creation

```python
# In the creating document model:
vals['analytic_distribution'] = self.env['account.analytic.distribution.model']._get_distribution(vals)
```

### Cross-Plan Distribution

A single line can distribute across **multiple plans simultaneously**. The JSON key is a comma-separated list of account IDs from different plans:

```python
# 70% on Project plan (account 12) + Department plan (account 34), 30% on Project-only:
{"12,34": 70.0, "12": 30.0}   # Project: 100%, Department: 70%
```

The `_merge_distribution()` handles proportional scaling when only some plans are modified.

---

## Performance Architecture (L4)

### GIN Index for Analytic Distribution Queries

The `init()` on `analytic.mixin` creates a GIN index for JSON key extraction. This is critical for filtering/sorting by analytic distribution across large move line tables (potentially millions of rows).

```sql
CREATE INDEX ... ON account_move_line
USING gin(regexp_split_to_array(
    jsonb_path_query_array(analytic_distribution, '$.keyvalue()."key"')::text, '\D+'
));
```

### Plan Lookup Caching

`_get_all_plans()` is cached via `@ormcache()`. Plan resolution is O(1) after first call per process.

### Read Group Aggregates

`balance/debit/credit` on `account.analytic.account` use `_read_group_select` + `_read_group_postprocess_aggregate` to manually sum computed fields — necessary because the ORM cannot aggregate across a computed field that itself aggregates from a different table.

### `_read_group_groupby` for Distribution

The analytic distribution groupby explodes JSON keys into separate rows via a lateral join. This allows counting/summing per individual analytic account even when a single move line distributes across multiple accounts.

### Company Security

All queries respect inter-company isolation via `child_of` domain operators on `company_id`. The `_check_company_consistency` constraint on `account.analytic.account` prevents reassigning accounts that already have lines in a different company.

---

## Related Models (Cross-Module)

| Model | Module | Inherits | Role |
|-------|--------|----------|------|
| `account.move.line` | `account` | `analytic.mixin` | Stores distribution, posts to analytic |
| `purchase.order.line` | `purchase` | `analytic.mixin` | PO line distribution |
| `sale.order.line` | `sale` | `analytic.mixin` | SO line distribution |
| `hr.expense` | `hr_expense` | `analytic.mixin` | Expense distribution |
| `account.asset` | `account_asset` | `analytic.mixin` | Asset distribution |

---

## See Also

- [Core/Fields](Core/Fields.md) — Json field type used for `analytic_distribution`
- [Core/API](Core/API.md) — `@api.constrains`, `@api.depends`, `@api.onchange` decorators
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — ir.rule domain enforcement on analytic lines
- [Modules/Account](Modules/account.md) — `account.move.line` which generates analytic lines
