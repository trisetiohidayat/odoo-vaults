---
uuid: account-analytic-l3
tags: [odoo, odoo19, modules, analytic, accounting]
description: Analytic accounting module - plan-based distribution, account hierarchies, and distribution models
---

# Analytic Accounting (`analytic`)

> **Note:** In Odoo 19, the module was renamed from `account_analytic` to `analytic`. This module provides the core infrastructure for analytic accounting, allowing tracking of costs and revenues independent of the general ledger.

**Module Path (CE):** `odoo/addons/analytic/`
**Category:** Accounting/Accounting
**License:** LGPL-3
**Odoo Version:** 19.0+

## L1 - All Fields and Method Signatures

### Models Overview

| Model | Purpose |
|-------|---------|
| `account.analytic.plan` | Analytic plan container (hierarchy of plans) |
| `account.analytic.account` | Individual analytic account within a plan |
| `account.analytic.line` | Journal entries posted to analytic accounts |
| `account.analytic.distribution.model` | Auto-fill distribution templates |
| `account.analytic.applicability` | Plan applicability rules per business domain |
| `analytic.plan.fields.mixin` | Abstract mixin adding analytic fields to any model |

---

### `account.analytic.plan`

Organizes analytic accounts into hierarchical plans. Each plan generates a dynamic column on models that use it.

```python
class AccountAnalyticPlan(models.Model):
    _name = 'account.analytic.plan'
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Plan name (required, translatable) |
| `description` | Text | Plan description |
| `parent_id` | Many2one (self) | Parent plan for hierarchical plans |
| `parent_path` | Char | Materialized path for hierarchy (`1/5/12/`) |
| `root_id` | Many2one (self) | Root plan (computed from parent_path) |
| `children_ids` | One2many (self) | Child plans |
| `children_count` | Integer | Number of direct children |
| `account_ids` | One2many (`account.analytic.account`) | Accounts in this plan |
| `account_count` | Integer | Direct account count |
| `all_account_count` | Integer | Account count including all descendants |
| `color` | Integer | Plan color (1-11) for UI |
| `sequence` | Integer | Display order (default 10) |
| `default_applicability` | Selection | Default applicability (optional/mandatory/unavailable), company-dependent |
| `applicability_ids` | One2many | Plan-specific applicability rules |

**Key Methods:**

```python
def _get_all_plans(self)          # Returns (project_plan, other_plans) as recordsets
def _strict_column_name(self)     # Returns 'account_id' for project plan, 'x_plan{id}_id' for others
def _column_name(self)            # Returns root plan's column name
def _hierarchy_name(self)         # Returns (depth, fname) for sub-plan fields
def get_relevant_plans(self, **kwargs)   # Returns plans applicable for a business domain
def _get_applicability(self, **kwargs)  # Returns applicability for a plan
def action_view_analytical_accounts(self)  # Opens accounts list for this plan
def _sync_plan_column(self, model)         # Creates/deletes dynamic field columns on models
```

---

### `account.analytic.account`

Individual analytic account within a plan. Tracks balance/debit/credit from associated lines.

```python
class AccountAnalyticAccount(models.Model):
    _name = 'account.analytic.account'
    _inherit = ['mail.thread']
    _check_company_auto = True
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Account name (required, trigram indexed, translatable) |
| `code` | Char | Reference code (btree indexed) |
| `active` | Boolean | Archive flag (default True) |
| `plan_id` | Many2one (`account.analytic.plan`) | Parent plan (required) |
| `root_plan_id` | Many2one | Root plan (related, stored) |
| `color` | Integer | Color (related to plan) |
| `line_ids` | One2many (`account.analytic.line`) | Lines posted to this account |
| `company_id` | Many2one (`res.company`) | Company |
| `partner_id` | Many2one (`res.partner`) | Linked customer (optional) |
| `balance` | Monetary | Computed: credit - debit |
| `debit` | Monetary | Computed sum of negative amounts |
| `credit` | Monetary | Computed sum of positive amounts |
| `currency_id` | Many2one (related) | Company currency |

**Key Methods:**

```python
def _compute_debit_credit_balance(self)   # Aggregates line amounts with currency conversion
def _compute_display_name(self)             # Formats as "[code] name - partner"
def copy_data(self, default=None)          # Appends " (copy)" to name
def write(self, vals)                     # Handles plan change with line migration
def _update_accounts_in_analytic_lines(self, new_fname, current_fname, accounts)  # Migrates lines on plan change
```

---

### `account.analytic.line`

Individual distribution line posted to analytic accounts. Links general ledger entries to analytic tracking.

```python
class AccountAnalyticLine(models.Model):
    _name = 'account.analytic.line'
    _inherit = ['analytic.plan.fields.mixin']
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Line description (required) |
| `date` | Date | Line date (required, default today, indexed) |
| `amount` | Monetary | Amount (positive = credit, negative = debit, required) |
| `unit_amount` | Float | Quantity (default 0.0) |
| `product_uom_id` | Many2one (`uom.uom`) | Unit of measure |
| `partner_id` | Many2one (`res.partner`) | Partner |
| `user_id` | Many2one (`res.users`) | User who created the line (default: context or current) |
| `company_id` | Many2one (`res.company`) | Company (required, readonly, default: current) |
| `currency_id` | Many2one (related) | Currency (from company) |
| `category` | Selection | Category (default 'other') |
| `analytic_distribution` | Json | Distribution as dict `{account_key: percentage}` |
| `analytic_precision` | Integer | Decimal precision for percentages |

**Key Methods:**

```python
def _compute_analytic_distribution(self)              # Converts plan fields to Json distribution
def _inverse_analytic_distribution(self)                # Splits line into multiple lines per account
def _split_amount_fname(self)                        # Returns 'amount' for analytic lines
```

---

### `account.analytic.distribution.model`

Templates for automatic analytic distribution pre-filling based on partner/company/category.

```python
class AccountAnalyticDistributionModel(models.Model):
    _name = 'account.analytic.distribution.model'
    _inherit = ['analytic.mixin']
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Priority order (default 10) |
| `partner_id` | Many2one (`res.partner`) | Partner filter (cascade delete) |
| `partner_category_id` | Many2one (`res.partner.category`) | Partner category filter |
| `company_id` | Many2one (`res.company`) | Company filter |
| `analytic_distribution` | Json (inherited) | Distribution to apply |

**Key Methods:**

```python
def _get_distribution(self, vals)              # Returns combined distribution from matching models
def _get_applicable_models(self, vals)        # Searches models matching vals
def _get_default_search_domain_vals(self)     # Returns defaults {company: False, partner: False}
def _create_domain(self, fname, value)        # Builds domain clause for a field
```

---

### `analytic.plan.fields.mixin` (Abstract)

Mixin that adds dynamic analytic account fields to any model. When plans are created, columns are dynamically added to tables of models using this mixin.

```python
class AnalyticPlanFieldsMixin(models.AbstractModel):
    _name = 'analytic.plan.fields.mixin'
```

**Magic Fields (dynamically created per plan):**

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | Many2one (`account.analytic.account`) | Primary analytic account |
| `auto_account_id` | Many2one (computed) | Context-aware account using current plan |
| `x_plan{id}_id` | Many2one | Auto-generated per plan |

**Key Methods:**

```python
def _compute_auto_account(self)                   # Returns account from current plan context
def _inverse_auto_account(self)                  # Writes to the plan-specific column
def _search_auto_account(self, operator, value)   # OR search across all plan columns
def _get_plan_fnames(self)                       # Returns list of active plan column names
def _get_analytic_accounts(self)                  # Returns recordset of all selected accounts
def _get_distribution_key(self)                  # Returns comma-separated account IDs
def _get_analytic_distribution(self)              # Returns {id_str: 100} for inverse
def _get_mandatory_plans(self, company, business_domain)  # Returns mandatory plans for domain
def _get_plan_domain(self, plan)                  # Returns domain for plan accounts
def _patch_view(self, arch, view, view_type)     # Dynamically injects plan fields into views
```

---

## L2 - Distribution Model, Plan-Based vs Account-Based, Balance Computation

### Distribution Model Architecture

Odoo 19 uses a **Json-based distribution model** rather than the legacy account-based model.

```
analytic_distribution (Json field)
{
  "1,2,3": 60.0,    # 60% split across accounts 1, 2, 3
  "5": 40.0          # 40% to account 5
}
```

**Key insight:** When a user sets `analytic_distribution`, the `_inverse_analytic_distribution` method automatically **splits** the line into multiple records, one per distribution entry.

### Plan-Based vs Account-Based

**Legacy (Odoo 14 and below):** One `account_id` per line, distribution via multiple lines.

**Odoo 19 (plan-based):**
- A plan is a container for related accounts
- Each plan generates a **dynamic column** on models using the mixin
- Multiple plans can be active simultaneously (e.g., "Project" + "Department" + "Region")
- `auto_account_id` field uses context (`analytic_plan_id`) to determine which plan's column to read/write
- Views dynamically inject fields for each plan

**Plan column generation:**
```python
# Project plan (root) -> column: 'account_id'
# Other plans -> column: 'x_plan{id}_id'
```

### Balance Computation (`_compute_debit_credit_balance`)

```python
def _compute_debit_credit_balance(self):
    # 1. Build domain with optional date filter
    domain = [('company_id', 'in', [False] + self.env.companies.ids)]
    if self.env.context.get('from_date'):
        domain.append(('date', '>=', self.env.context['from_date']))
    if self.env.context.get('to_date'):
        domain.append(('date', '<=', self.env.context['to_date']))

    # 2. Group by plan and account, separate credit (>=0) and debit (<0)
    credit_groups = self.env['account.analytic.line']._read_group(
        domain=domain + [(plan._column_name(), 'in', self.ids), ('amount', '>=', 0.0)],
        groupby=[plan._column_name(), 'currency_id'],
        aggregates=['amount:sum'],
    )

    # 3. Convert all amounts to company currency
    # 4. Sum per account: debit = -negative_amounts, credit = positive_amounts
    # 5. balance = credit - debit
```

**Multi-currency support:** Amounts are converted using `_convert()` to the company's currency at the current date.

---

## L3 - Analytic Distribution on Move Lines, Mandatory vs Optional, Distribution Percentage

### Distribution on Account Move Lines

Analytic lines are created when journal entries are posted. The `analytic.plan.fields.mixin` is inherited by `account.move.line` (via `analytic.mixin`), giving it `account_id`, `auto_account_id`, and dynamic plan columns.

**Flow:**
1. User sets `analytic_distribution` on a move line (or selects `account_id`)
2. `_inverse_analytic_distribution` is called on write
3. If multiple accounts in distribution -> **splits the line** into multiple analytic lines, each with proportional amount
4. Analytic lines are stored in `account_analytic_line` table

**Split example:**
```
Original line: amount = 1000, distribution = {"1": 70.0, "2": 30.0}
Creates:
  Line 1: account_id=1, amount=700 (1000 * 70%)
  Line 2: account_id=2, amount=300 (1000 * 30%)
```

### Mandatory vs Optional Plans

Plans can be configured with different applicability levels:

| Applicability | Behavior |
|---------------|----------|
| `optional` | User can leave blank |
| `mandatory` | Validation error if no account selected |
| `unavailable` | Plan hidden from UI for that business domain |

**Configurable via:**
- `default_applicability` on the plan (company-dependent)
- `applicability_ids` on the plan (per business_domain + company)

**Business domains** are defined in `account.analytic.applicability`:
- `general` (default)
- `purchase`, `sale`, `account_asset`, `project`, etc. (extended by other modules)

### Distribution Percentage

**Rules:**
- Percentages must sum to 100% (enforced by UI widget)
- Supports decimal precision (configured via `analytic_precision`)
- Inversed by `_inverse_analytic_distribution` which creates multiple lines

**In the Json field:**
```python
{account_ids_as_csv: percentage_float}
# e.g., {"1,2": 50.0, "3": 50.0} -> 50% shared between 1&2, 50% to 3
```

---

## L4 - Performance, Odoo 18 to 19 Changes, Cross-Model with account.move.line

### Performance Considerations

1. **`_get_plan_fnames()` is called frequently** — used in every `_patch_view`, `_check_account_id`, and distribution computation. Caches result via ORM.

2. **Dynamic columns created via `_sync_plan_column`** — creates `ir.model.fields` records with `state='manual'`. Column names stored in `ir.config_parameter` for project plan (`analytic.project_plan`).

3. **`ormcache` on `__get_all_plans`** — plan list is cached to avoid repeated parameter lookups:
   ```python
   @ormcache()
   def __get_all_plans(self):
       project_plan = self.browse(int(self.env['ir.config_parameter'].sudo().get_param('analytic.project_plan', 0)))
   ```

4. **Trigram index on `name`** — enables fast `ilike` searches on analytic account names.

5. **GIN index on `analytic_distribution`** — created via `init()` hook for fast JSON key searches:
   ```python
   CREATE INDEX IF NOT EXISTS {table}_analytic_distribution_accounts_gin_index
       ON {table} USING gin(
           regexp_split_to_array(
               jsonb_path_query_array(analytic_distribution, '$.keyvalue()."key"')::text,
               '\D+'
           )
       );
   ```

6. **`_compute_debit_credit_balance` uses `_read_group`** — aggregation happens in PostgreSQL, not Python loops. Currency conversion done via `_convert()` per group.

7. **Plan migration via raw SQL** — `_update_accounts_in_analytic_lines` uses raw SQL `UPDATE ... WHERE column = ANY(%s)` for bulk migration when a plan changes parent, avoiding ORM overhead.

8. **`_patch_view` called on every `_get_view`** — view patching happens on every form/list render. No caching at Python level; relies on Odoo's view caching mechanism.

### Odoo 18 to 19 Changes

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| Module name | `account_analytic` | `analytic` |
| Distribution storage | One2many lines (legacy) | Json field + split lines |
| `account.analytic.distribution.model` | `account.analytic.distribution.model` | Same |
| Dynamic plan columns | Via `_code_get` | Via `_sync_plan_column` + `ir.model.fields` |
| `auto_account_id` | Existed | Enhanced with context handling |
| `analytic_precision` | Not present | Added for configurable decimal precision |
| `analytic.mixin` | Not separate | Extracted as standalone mixin |
| `_merge_distribution` | Not present | Added for inline distribution editing |

### Cross-Module with `account.move.line`

**`analytic.mixin`** (in `analytic/models/analytic_mixin.py`) provides the base:
```python
class AnalyticMixin(models.AbstractModel):
    _name = 'analytic.mixin'
    
    analytic_distribution = fields.Json(
        compute='_compute_analytic_distribution',
        inverse='_inverse_analytic_distribution',
    )
```

**Models using `analytic.mixin`:**

| Model | Module | Usage |
|-------|--------|-------|
| `account.move.line` | `account` | Invoice/entry lines |
| `account.asset` | `account_asset` (EE) | Asset acquisition lines |
| `hr.expense` | `hr_expense` | Expense lines |
| `project.task` | `project` | Timesheet planning |
| `sale.order.line` | `sale` | Sales order lines |
| `purchase.order.line` | `purchase` | PO lines |

**Applicability models** extend the applicability system:
- `analytic.applicability` — base applicability
- `hr_expense.models.analytic` — adds `expense` business_domain
- `project.models.analytic_applicability` — adds `project` domain
- `purchase.models.analytic_applicability` — adds `purchase` domain
- `mrp_account.models.analytic_account` — adds `manufacturing` domain

---

## Key Architecture Patterns

### Dynamic Column Creation

When a plan is created, `_sync_plan_column` is called:
```python
# Creates field on model using the mixin:
self.env['ir.model.fields'].sudo().create({
    'name': 'x_plan42_id',          # or 'account_id' for project plan
    'field_description': 'Plan Name',
    'model': 'account.move.line',
    'ttype': 'many2one',
    'relation': 'account.analytic.account',
    'copied': True,
    'on_delete': 'restrict',
})
```

### Distribution Merge Strategy

`analytic.mixin._merge_distribution` combines distributions when a line references multiple plans:
- Splits per plan, then merges shared accounts
- Ensures percentages are proportionally adjusted
- Uses `__update__` key to track which plans are being modified inline

### View Patching

`_patch_view` injects optional plan fields into existing views dynamically:
```python
# For each non-project plan, inject an optional field after 'account_id':
account_node.addnext(E.field(
    name=fname,
    optional='show',      # Field starts hidden but can be shown
    domain=repr(self._get_plan_domain(plan)),
    context=repr(self._get_account_node_context(plan)),
))
```

### Plan Hierarchy and Column Naming

Sub-plans generate **group-by-only fields** (non-stored related), not stored columns:
```python
# Sub-plan field: non-stored related to parent plan's column
{
    'name': 'account_id_1',       # depth=1 sub-plan group-by
    'ttype': 'many2one',
    'related': 'account_id.plan_id.parent_id',  # Traverse up hierarchy
    'store': False,
    'readonly': True,
}
```

### Line Splitting on Distribution Inverse

When `analytic_distribution` is set on a line, `_inverse_analytic_distribution` splits into multiple records:
1. Computes `final_distribution` by merging current account columns with Json input
2. For each distribution entry, computes proportional `amount`
3. Writes first entry to current line
4. `copy_data` + `create()` for remaining entries
5. Sends bus notification with count of created lines

### Mandatory Plan Validation

`_validate_distribution()` is called from consuming models' constraints. It:
1. Gets mandatory plans for the business domain and company
2. Sums percentages per root plan from the distribution
3. Raises `ValidationError` if any mandatory plan does not sum to 100%

---

## Common Integration Points

- **Sale/Purchase**: Analytic distribution on order lines -> auto-creates analytic lines on invoice confirmation
- **Expense**: `hr_expense` models use `analytic.mixin`, applicability rules set by `analytic.applicability`
- **Project/HR Timesheet**: Timesheet lines linked to analytic accounts for labor cost tracking
- **Assets**: `account.asset` inherits `analytic.mixin` — depreciation entries carry analytic distribution
- **Manufacturing**: `mrp.workorder` can post analytic lines for work-in-progress tracking

---

## Failure Modes and Edge Cases

### 1. Missing Project Plan Configuration

**Error:** `"A 'Project' plan needs to exist and its id needs to be set as 'analytic.project_plan'..."`

**Cause:** `ir.config_parameter` missing or pointing to non-existent plan.

**Fix:** Create a plan and set `analytic.project_plan`:
```python
self.env['ir.config_parameter'].sudo().set_param('analytic.project_plan', plan_id)
```

### 2. Plan Change with Existing Lines

**Error:** Constraint violation or orphaned analytic lines after plan parent change.

**Cause:** `_update_accounts_in_analytic_lines` uses `RedirectWarning` safety around SQL migration.

**Fix:** The write method handles this with two-phase update (before and after `_sync_plan_column`).

### 3. Distribution Does Not Sum to 100%

**Error:** `"One or more lines require a 100% analytic distribution."` (ValidationError)

**Cause:** `_validate_distribution()` checks mandatory plans; optional plans can have any sum.

**Fix:** UI widget enforces 100% sum; validation only fires for mandatory plans.

### 4. Deleted Account Still in Distribution

**Behavior:** `analytic_distribution` keys reference archived (not deleted) accounts. `_compute_distribution_analytic_account_ids` filters with `.exists()` to only return valid accounts.

### 5. Circular Plan Hierarchy

**Error:** Domain constraint prevents this at ORM level: `['!', ('id', 'child_of', id)]`

---

## Security Model

| Access | Required Group |
|--------|---------------|
| Read plans/accounts | `base.group_user` (all users) |
| Create/edit plans | `account.group_account_user` |
| Delete plans | `account.group_account_manager` |
| Read analytic lines | `base.group_user` |
| Create analytic lines | `base.group_user` (via journal entries) |

Record rules on `account.analytic.line` restrict access based on `company_id` and analytic account visibility. Archive/unarchive of accounts is unrestricted for accountants.

---

## Testing Strategy

| Test Type | Coverage |
|-----------|---------|
| Unit: plan CRUD + hierarchy | `_test_plan_hierarchy` |
| Unit: column name generation | `_test_column_name`, `_test_strict_column_name` |
| Unit: applicability scoring | `_test_applicability_get_score` |
| Unit: distribution merge | `_test_merge_distribution` |
| Unit: line splitting | `_test_inverse_analytic_distribution` |
| Integration: move line -> analytic line | Through `account` module tests |
| Integration: plan change -> line migration | `_test_plan_change_migration` |
| Performance: large account with 10k+ lines | Balance computation timing |

---

## See Also

- [Modules/Account](modules/account.md) — Invoice and journal entries that carry analytic distribution
- [Modules/Project](modules/project.md) — Project cost tracking via analytic accounts
- [Modules/hr_expense](modules/hr_expense.md) — Expense reporting with analytic distribution
- [Core/API](core/api.md) — @api.depends, computed fields used throughout
