---
description: Core analytic accounting — plans, accounts, lines, distribution models, and cross-module Json distribution architecture.
---

# Analytic Accounting (`analytic`)

## Module Overview

| Attribute | Value |
|---|---|
| **Name** | Analytic Accounting |
| **Version** | 1.2 |
| **Category** | Accounting/Accounting |
| **Depends** | `base`, `mail`, `uom` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Installable** | True |

The `analytic` module provides the foundational infrastructure for tracking costs and revenues against arbitrary dimensions -- independent of the general financial ledger. Analytic accounts can represent projects, departments, cost centres, or any other analytical segmentation. The module is a pure framework; actual line creation is driven by downstream modules (`project`, `hr_expense`, `sale`, `purchase`, `account`, etc.).

---

## Architecture Overview

### Core Design: Two Mixins

```
analytic.plan.fields.mixin   →  adds per-plan Many2one columns (account_id, x_plan2_id, …)
    ↓ inherited by
account.analytic.line       →  concrete lines with amounts

analytic.mixin              →  adds analytic_distribution Json field with merge logic
    ↓ inherited by
account.analytic.distribution.model
    + downstream models via _inherit (account.move.line, purchase.order.line, etc.)
```

**`account.analytic.line`** is the concrete record of a posted analytic entry. **Plans** are the categorisation schema. **Accounts** are the individual dimension values under a plan. The Json distribution on other models (invoices, purchase orders, expenses) references accounts across all plans simultaneously.

---

## Model Inventory

### `account.analytic.plan` -- Analytic Plans

Defines a named plan (e.g. "Project", "Department") that acts as a container for accounts. Plans are hierarchical via `parent_id`/`parent_path`.

**Fields:**

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required. `translate=True`. Inverse triggers `_sync_all_plan_column` |
| `description` | Text | Free-text description |
| `parent_id` | Many2one (`self`) | Root plans only. Inverse triggers `_sync_all_plan_column`. `index='btree_not_null'`, `ondelete='cascade'`. Domain prevents self-reference |
| `parent_path` | Char (indexed) | Materialised path for tree queries (`1/5/23/`) |
| `root_id` | Many2one (`self`) | Computed from `parent_path`. The topmost ancestor |
| `children_ids` | One2many (`self`) | Child plans |
| `children_count` | Integer | Computed count of `children_ids` |
| `complete_name` | Char | Recursive compute: `"Parent / Child"` |
| `account_ids` | One2many -> `account.analytic.account` | Accounts belonging to this plan |
| `account_count` | Integer | Count of direct `account_ids` |
| `all_account_count` | Integer | Count of accounts in this plan and ALL child plans (SQL query) |
| `color` | Integer | Random 1-11 default; drives Kanban colour |
| `sequence` | Integer | Default 10. Controls sort order |
| `default_applicability` | Selection | `optional` / `mandatory` / `unavailable`. Company-dependent. Set to `optional` at `_auto_init` via precommit hook |
| `applicability_ids` | One2many -> `account.analytic.applicability` | Per-domain applicability rules, domain-filtered to current company |

#### Applicability System

The applicability system controls whether a plan's accounts must be filled in on a given business document.

**`account.analytic.applicability` fields:**

| Field | Type | Notes |
|---|---|---|
| `analytic_plan_id` | Many2one -> `account.analytic.plan` | `index='btree_not_null'` |
| `business_domain` | Selection | Only `('general', 'Miscellaneous')` in the core module. Downstream modules (e.g. `account`) extend this selection with domain-specific values |
| `applicability` | Selection | `optional` / `mandatory` / `unavailable` |
| `company_id` | Many2one -> `res.company` | Optional company scoping. `_check_company_auto = True` |

`_get_score(**kwargs)` ranks applicability rules by:
- Matching `business_domain`: +1 point
- Company match: +0.5 points (penalised as less important than domain matching)

The rule with the highest score wins. Default (no rule matches) falls back to `plan.default_applicability`.

#### Dynamic Column Architecture

Each root plan generates a **stored Many2one field** on every model inheriting `analytic.plan.fields.mixin`:

| Plan type | Column name | Creation |
|---|---|---|
| Project plan (ID in `ir.config_parameter` `analytic.project_plan`) | `account_id` | Created once, permanent |
| All other root plans | `x_plan{N}_id` (e.g. `x_plan2_id`) | Created dynamically by `_sync_plan_column` |
| Child plans (any plan with a parent) | `x_{plan_column_name}_{depth}_id` (e.g. `x_account_id_1`) | Non-stored related field for grouping |

The column name is determined by `_strict_column_name()`:
```python
def _strict_column_name(self):
    return 'account_id' if self == project_plan else f"x_plan{self.id}_id"
```

`_sync_plan_column(model)` creates or updates these dynamic fields whenever:
- A plan's `name` changes (via `_inverse_name`)
- A plan's `parent_id` changes (via `_inverse_parent_id`)

It processes plans sorted by `parent_path` to ensure parents are handled before children. Stored fields get a B-tree index with a partial index predicate (`column IS NOT NULL`) for performance.

#### Key Methods

- `__get_all_plans()` -- `@ormcache()` memoised. Reads `analytic.project_plan` from `ir.config_parameter`. **Raises `UserError` if the project plan does not exist.** Returns `(project_plan, other_plans)` as a tuple of IDs.
- `_get_all_plans()` -- Wraps output through `.browse()` to produce actual recordset objects.
- `get_relevant_plans(**kwargs)` -- Returns plans visible in a given business context. Includes plans forced by already-selected accounts even if `unavailable`. Returns dicts with `id`, `name`, `color`, `applicability`, `all_account_count`, `column_name`.
- `_find_plan_column(model)` -- Finds the stored `ir.model.fields` record for this plan's column on a given model.
- `_find_related_field(model)` -- Finds the related (non-stored) field for a child-plan grouping column.
- `_hierarchy_name()` -- Returns `(depth, field_name)` for a plan: computes depth from `parent_path` count and formats the related field name (prepending `x_` if it starts with `account_id`).
- `write()` -- When `parent_id` changes: moves analytic lines from old column to new column (or vice versa) before/after the column is deleted/created, via `_update_accounts_in_analytic_lines`.
- `unlink()` -- Removes the plan's dynamic field, then any related fields that are no longer used.

---

### `account.analytic.account` -- Analytic Accounts

A leaf node under a plan. Represents a project, cost centre, department, or any other analytical dimension.

**Fields:**

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required. `index='trigram'`, `translate=True`, `tracking=True` |
| `code` | Char | Reference code. `index='btree'`, `tracking=True`. Included in `display_name` as `[CODE] Name - Partner` |
| `active` | Boolean | Default `True`. `tracking=True`. Archived accounts are hidden but data is preserved |
| `plan_id` | Many2one -> `account.analytic.plan` | Required. `index=True`. Changing this moves all related `account.analytic.line` rows to the new plan's column |
| `root_plan_id` | Many2one -> `account.analytic.plan` | Related to `plan_id.root_id`. `store=True` |
| `color` | Integer | Related to `plan_id.color` |
| `line_ids` | One2many -> `account.analytic.line` | Via `auto_account_id` magic field -- shows lines for this account in the current plan context |
| `company_id` | Many2one -> `res.company` | `default=lambda self: self.env.company` |
| `partner_id` | Many2one -> `res.partner` | Customer association. `index='btree_not_null'` |
| `balance`, `debit`, `credit` | Monetary | Computed from `account.analytic.line` amounts via `_compute_debit_credit_balance`. Converts to company currency using today's rate |
| `currency_id` | Many2one -> `res.currency` | Related to `company_id.currency_id` |

#### Computed Balance Logic (`_compute_debit_credit_balance`)

Groups by plan using the plan's `_column_name()` to select the correct column, then issues two `_read_group` queries against `account.analytic.line`:
- **Query 1**: `amount >= 0` -> summed per `(account, currency)` group -> `data_credit`
- **Query 2**: `amount < 0` -> summed per `(account, currency)` group -> `data_debit`

Each currency group is individually converted to the company currency before summing into the account's final values:
```
debit  = -data_debit.get(account.id, 0.0)
credit =  data_credit.get(account.id, 0.0)
balance = credit - debit
```

Optional date filtering via `from_date`/`to_date` context keys.

#### Balance Aggregation in Grouped List Views

The model overrides `_read_group_select` and `_read_group_postprocess_aggregate` to intercept `balance:sum`, `balance:sum_currency`, `debit:sum`, `debit:sum_currency`, `credit:sum`, `credit:sum_currency` -- routing them through the full recordset compute rather than raw SQL aggregation. This ensures the monetary conversion and sign convention are respected in grouped list views.

#### Constrains

`_check_company_consistency` -- prevents changing `company_id` on an account if any `account.analytic.line` exists under a different company lineage. Uses a sudo search to check cross-company contamination.

#### Migration: Changing Plan

When `plan_id` is changed on `write()`:
1. `new_fname = new_plan._column_name()` is computed upfront
2. For each existing plan group: `current_fname = plan._column_name()`
3. `_update_accounts_in_analytic_lines(new_fname, current_fname, accounts)` issues a raw SQL `UPDATE` to move line references before the old column is deleted
4. If any lines would be orphaned (target column already holds other accounts), raises `RedirectWarning` showing the affected lines with a "See them" button

---

### `account.analytic.line` -- Analytic Lines

A concrete journal entry recording a cost or revenue against one or more analytic accounts. This is the primary data record of the analytic module.

**Inherits:** `analytic.plan.fields.mixin`

**Fields:**

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required |
| `date` | Date | Required. Default: `context_today`. `index=True` |
| `amount` | Monetary | Required. Default 0.0. **Positive = credit (revenue), Negative = debit (cost)** |
| `unit_amount` | Float | Quantity (hours, units). Default 0.0 |
| `product_uom_id` | Many2one -> `uom.uom` | Unit of measure for `unit_amount` |
| `partner_id` | Many2one -> `res.partner` | |
| `user_id` | Many2one -> `res.users` | Default: `context.get('user_id')` or `env.user.id`. `index=True` |
| `company_id` | Many2one -> `res.company` | Required, readonly. `default=lambda self: self.env.company` |
| `currency_id` | Many2one -> `res.currency` | Related, stored, `compute_sudo=True` |
| `category` | Selection | Only `('other', 'Other')` in core. Downstream modules extend this |
| `analytic_distribution` | Json | Computed from account references. Inverse splits lines into separate rows |
| `analytic_precision` | Integer | `store=False`. Reads `"Percentage Analytic"` decimal precision |
| `fiscal_year_search` | Boolean | Search-only field with `_search_fiscal_date` -- searches lines from the past fiscal year plus one year back |

#### `auto_account_id` Magic Field

`analytic.plan.fields.mixin` provides `auto_account_id` -- a computed/inversed/searchable proxy that resolves to the correct plan-specific column based on `context['analytic_plan_id']`.

- **Compute** (`_compute_auto_account`): reads `plan._column_name()` column from context
- **Inverse** (`_inverse_auto_account`): writes into `account.auto_account_id.plan_id._column_name()` -- i.e. the plan-specific column
- **Search** (`_search_auto_account`): ORs across all plan columns for all plans using `Domain.OR`

This is why `account.analytic.account.line_ids` (the One2many) uses `auto_account_id` as the inverse field -- it works across any plan.

#### `analytic_distribution` Inverse (Line Splitting)

`_inverse_analytic_distribution` handles percentage-based distribution by splitting one line into multiple rows:

1. Merges the existing key-based distribution with the new percentage-based distribution via `_merge_distribution`
2. For each resulting `(account_ids, percentage)` pair:
   - Creates a `vals` dict with the scaled `amount` and account references for each account's plan column
   - Writes to the first account, `create()`s the rest
3. Sends a bus notification: `"N analytic lines created"`

Example: setting a 60/40 split on a line with `amount = 100` creates two rows: one with `amount = 60` and one with `amount = 40`.

---

### `analytic.plan.fields.mixin` -- Abstract Mixin (Per-Plan Columns)

**Abstract model** mixed into any model that needs per-plan analytic account columns.

Provides:
- `account_id` -- Many2one to Project plan accounts (`on_delete='restrict'`)
- `auto_account_id` -- Context-dependent proxy (see above)
- `_get_plan_fnames()` -- Returns list of all plan column names present on this model
- `_get_analytic_accounts()` -- Returns `account.analytic.account` records for all filled plan columns
- `_get_distribution_key()` -- Returns comma-joined account IDs as a string key (e.g. `"12,34"`)
- `_get_analytic_distribution()` -- Returns `{"12,34": 100}` format for Json distribution
- `_get_mandatory_plans()` -- Returns plans whose applicability is `mandatory` for a given domain/company
- `_get_plan_domain(plan)` -- Returns `[('plan_id', 'child_of', plan.id)]` domain for a plan's accounts
- `_get_account_node_context(plan)` -- Returns `{'default_plan_id': plan.id}` for account selection widgets
- `_check_account_id()` -- `@api.constrains` on all plan field names; ensures at least one plan column is filled

#### View Patching (`_patch_view`)

Runtime XML patching inserts plan-specific fields into views without modifying XML files:
- For each non-project plan: adds a `<field name="x_plan{N}_id">` after `account_id` with `optional='show'`
- Sets plan-specific domain and context on each field
- Adds group-by filters for each plan and subplan depth using `_hierarchy_name()`

This means: adding a new plan automatically extends every downstream view.

---

### `analytic.mixin` -- Abstract Mixin (Json Distribution)

**Abstract model** mixed into financial/document models (e.g. `account.move.line`, `purchase.order.line`, `hr_expense`) that need `analytic_distribution`.

**Fields:**

| Field | Type | Notes |
|---|---|---|
| `analytic_distribution` | Json (stored, copyable) | `{"12,34": 40.0, "56": 60.0}` -- comma-joined account IDs -> percentage |
| `analytic_precision` | Integer | `store=False`. Reads `"Percentage Analytic"` decimal precision |
| `distribution_analytic_account_ids` | Many2many -> `account.analytic.account` | Compute+search field; decompresses JSON into a browseable recordset |

#### Database Index

`init()` creates a GIN index on JSON keys using `regexp_split_to_array(jsonb_path_query_array(...))` to extract account IDs. This enables fast lookup when searching on `analytic_distribution`.

#### Query Methods for Downstream Use

- `_query_analytic_accounts(table)` -- Returns an SQL fragment that extracts all account IDs from the JSON column: `regexp_split_to_array(jsonb_path_query_array(...))`
- `_read_group_groupby('analytic_distribution', ...)` -- Rewrites the query to join against a subquery that explodes JSON keys into rows, enabling standard grouped reports on distributions. **Only `__count` aggregate is supported** in this mode.
- `_get_count_id(query)` -- Maps table names to their ID column for the distribution subquery. Tables: `account_move_line`->`move_id`, `purchase_order_line`->`order_id`, `account_asset`->`id`, `hr_expense`->`id`. **Raises `ValueError` for unsupported tables.**

#### Distribution Validation (`_validate_distribution`)

When `context['validate_analytic']` is set:
- Fetches all `mandatory` plans for the document's company/domain
- Sums percentages by root plan from the distribution JSON
- Raises `ValidationError` if any mandatory root plan does not sum to exactly 100%

#### Merge Logic (`_merge_distribution`)

When the inverse setter receives `{'__update__': ['field1', ...]}`:
- Accounts whose root plan is NOT in `__update__` -- preserved from old distribution (proportionally scaled)
- Accounts whose root plan IS in `__update__` -- replaced by new distribution
- The two groups are recomputed to maintain 100% total

This allows editing one plan's distribution (e.g. Project) while preserving other plans' allocations.

---

### `account.analytic.distribution.model` -- Distribution Templates

Stores reusable distribution rules that auto-populate `analytic_distribution` on downstream document creation.

**Inherits:** `analytic.mixin`

**Fields:**

| Field | Type | Notes |
|---|---|---|
| `sequence` | Integer | Default 10. Sort order for model matching |
| `partner_id` | Many2one -> `res.partner` | Match on partner. `on_delete='cascade'` |
| `partner_category_id` | Many2one -> `res.partner.category` | Match on partner category. `on_delete='cascade'` |
| `company_id` | Many2one -> `res.company` | Optional. Global if not set. `on_delete='cascade'` |
| `analytic_distribution` | Json | Inherited from `analytic.mixin`. Reusable distribution template |

#### Model Matching (`_get_applicable_models`)

`_get_distribution(vals)` applies all matching models in sequence order:
1. Builds domain: `partner_id in [vals['partner_id'], False]`, `company_id in [vals['company_id'], False]`, `partner_category_id in [category_ids + False]`
2. For each matching model: merges its distribution if no root plan has already been covered
3. **Root-plan deduplication**: once a root plan contributes an account, no other model can contribute to that root plan

This means distribution models are **additive across plans but exclusive within a plan**.

#### Cross-Company Constraint

`_check_company_accounts` -- SQL query validates that no distribution model (with `company_id = NULL` or a different company) references an analytic account scoped to a specific company. **Raises `UserError` on violation.**

---

## Security

### Access Control (`ir.model.access.csv`)

All 5 concrete models require `group_analytic_accounting`:

| Model | Permission |
|---|---|
| `account.analytic.account` | CRUD |
| `account.analytic.line` | CRUD |
| `account.analytic.plan` | CRUD |
| `account.analytic.applicability` | CRUD |
| `account.analytic.distribution.model` | CRUD |

### Record Rules (`analytic_security.xml`)

| Model | Rule |
|---|---|
| `account.analytic.account` | Global. `['|', ('company_id', '=', False), ('company_id', 'parent_of', company_ids)]` -- accounts without a company are globally visible |
| `account.analytic.line` | `('company_id', 'in', company_ids)` -- lines must belong to a company in the user's allowed companies. No cross-company visibility |
| `account.analytic.applicability` | Same as account rule: global if `company_id` is NULL |
| `account.analytic.distribution.model` | Same as account rule |

**Critical difference:** Analytic lines require a company -- there is no global/anonymous line concept. Accounts can be company-less (demo data creates them without `company_id`).

---

## Key Workflows

### 1. Document Creation with Analytic Distribution

When a downstream document (e.g. vendor bill) is created:
1. `account.analytic.distribution.model._get_distribution(vals)` is called
2. Matching models are found and merged (additive across plans, exclusive within plan)
3. The resulting `analytic_distribution` dict is written to the line
4. The inverse setter splits into separate lines if distribution is non-uniform

### 2. Adding a New Analytic Plan

1. Admin creates `account.analytic.plan` record
2. `_inverse_name` triggers `_sync_all_plan_column`
3. `analytic.plan.fields.mixin` models (e.g. `account.move.line`) get a new stored column `x_plan{N}_id`
4. Views are dynamically patched to show the new field
5. `analytic_distribution` Json format remains `{"account_ids": percentage}` -- no change needed

### 3. Changing `analytic.project_plan` Config Parameter

`ir.config_parameter.write()` override validates the new value is a valid plan ID with a column, then:
1. Syncs the old plan's column across all mixin models
2. Unlinks the old column field from `ir.model.fields`

This is a **dangerous operation** -- column names are hardcoded references in SQL. The validation guards against corrupt schema.

### 4. Project Plan vs. Other Plans

The Project plan (ID stored in `ir.config_parameter`) is treated specially:
- Always gets `account_id` as its column name
- Cannot have a parent (enforced in `_onchange_parent_id`)
- Its column is not dynamically renamed when name changes (only the `field_description` is updated)

---

## Performance Considerations

| Concern | Mitigation |
|---|---|
| Balance compute across many accounts | `_read_group` aggregates on DB; monetary conversion done per-currency group, then summed |
| Dynamic field creation | `_auto_init` precommit hook defers field creation to post-commit |
| Plan cache invalidation | `@ormcache()` on `__get_all_plans()` cleared only on plan unlink |
| JSON key search | `init()` creates gin index `analytic_distribution_accounts_gin_index` using regex extraction of numeric keys from JSON |
| Distribution grouping in reports | `_read_group_groupby` rewrites query with a lateral join to explode JSON keys -- single-pass, avoids Python loops |
| `all_account_count` on plan | Single SQL query with `LIKE parent_path || '%'` JOIN to get all descendants at once |
| `_compute_auto_account` | Only reads the plan column that matches `context['analytic_plan_id']` -- not all plan columns |

---

## Cross-Module Integration

```
analytic (base framework)
    ├─ _inherit: analytic.plan.fields.mixin
    │   └─ account.move.line   → account_id, x_plan2_id, … columns
    │   └─ purchase.order.line → same
    │   └─ sale.order.line     → same
    │   └─ hr.expense          → same
    │
    ├─ _inherit: analytic.mixin
    │   └─ account.move.line   → analytic_distribution Json
    │   └─ purchase.order.line → same
    │   └─ hr.expense          → same
    │
    ├─ account.analytic.distribution.model._get_distribution()
    │   └─ called on create of financial/document lines
    │
    └─ account.analytic.line
        └─ balance computed via → account.analytic.account
                                    └─ plan via → account.analytic.plan
```

The `analytic` module is a framework only. Downstream modules (`account`, `purchase`, `sale`, `hr_expense`, `project`, `sale_timesheet`) consume its mixins and call its distribution APIs to create and validate analytic entries.

---

## Historical Changes (Odoo 18 -> 19)

| Area | Change |
|---|---|
| **Architecture** | Replaced single-plan model (one fixed `account_id` column per model) with multi-plan architecture (one stored column per plan, dynamic field creation) |
| **Json Distribution** | Introduced `analytic_distribution` Json field to replace per-plan percentage fields on financial lines |
| **Mixin Split** | Split the old monolithic analytic model into two mixins: `analytic.plan.fields.mixin` (per-plan columns) and `analytic.mixin` (Json distribution) |
| **Dynamic Fields** | Plans now dynamically create `ir.model.fields` records for their columns, rather than requiring SQL schema migrations |
| **Distribution Models** | `account.analytic.distribution.model` introduced as a more flexible replacement for per-partner/per-category account defaults |
| **Line Splitting** | Percentage-based distributions now automatically split a single line into multiple `account.analytic.line` records via the inverse setter |
| **Applicability** | `account.analytic.applicability` with scoring system replaces simple boolean applicability per model |
| **View Patching** | `_patch_view` dynamically extends view XML at runtime for additional plans; no XML inheritance required |

---

## Edge Cases

1. **Plan with no accounts**: `get_relevant_plans` excludes plans with `all_account_count == 0` unless forced by an already-selected account
2. **Archived account in distribution**: `_compute_distribution_analytic_account_ids` calls `.exists()` before populating the many2many -- archived accounts are silently excluded
3. **Company-less accounts**: Demo data creates all accounts with `company_id eval="False"`. The record rule `['|', ('company_id', '=', False), ...]` allows global access to these accounts
4. **Multi-currency lines**: Balance computation converts each currency group's sum to the company currency individually before summing into account totals
5. **Line splitting creates new records**: `_inverse_analytic_distribution` creates new lines and sends a bus notification -- the original line is one of the split lines; old lines are not automatically deleted
6. **Changing plan parent moves column**: `_update_accounts_in_analytic_lines` issues raw SQL `UPDATE ... SET new_col = curr_col, curr_col = NULL WHERE curr_col = ANY(...)` -- avoids ORM overhead for large datasets. If the SQL would orphan lines (target column already has unrelated accounts), raises `RedirectWarning`
7. **Subplan grouping field cleanup**: `_is_subplan_field_used` checks if any plan still exists at the same hierarchy depth before deleting the group-by related field on plan deletion
8. **Decimal precision on distributions**: `_sanitize_values` rounds all percentage values to `"Percentage Analytic"` precision (2 decimal places by default) before writing; ensures equality comparisons on Json fields work correctly
9. **Fiscal year search**: `fiscal_year_search` field searches lines from the current fiscal year start minus one year -- designed for comparative financial reporting
10. **`analytic.project_plan` not set**: `__get_all_plans()` raises `UserError` with a descriptive message. This config parameter MUST be set for the module to function
11. **Project plan re-parenting blocked**: `_onchange_parent_id` prevents adding a parent to the Project plan -- enforced with `UserError`
12. **Subplan field name collision**: `_hierarchy_name` prepends `x_` if the generated name would start with `account_id` (which is reserved for the Project plan), producing e.g. `x_account_id_1` instead of `account_id_1`

---

## Demo Data

Two plans created in `analytic_data.xml`:
- **Departments** (`analytic_plan_departments`) -- `default_applicability: optional`
- **Internal** (`analytic_plan_internal`) -- `default_applicability: unavailable`

The **Project** plan (`analytic_plan_projects`) is created separately via `set_param` into `ir.config_parameter` with `forcecreate="0"` and ID `1`.

Demo accounts are distributed across all three plans, all without a `company_id` (globally visible):
- Project plan: "Our Super Product", "Seagate P2", "Millennium Industries", "CampToCamp", "Acme Corporation", "Asustek", "Delta PC", "Spark Systems", "Nebula", "Luminous Technologies", "Desertic - Hispafuentes", "Lumber Inc", "Camp to Camp", "Active account"
- Departments plan: "Administrative", "Commercial & Marketing", "R&D", "HR", "Legal", "Finance", "Production"
- Internal plan: "Time Off", "Operating Costs"

A `decimal.precision` record for `"Percentage Analytic"` (2 digits) is also created at install time.

---

## L3: Cross-Module Integration Deep Dive

### cross_model: How Analytic Lines Are Created from Other Modules

Analytic lines are never created directly by the `analytic` module itself. Downstream modules inherit the mixins and hook into their own document flows to create lines. The integration follows a consistent pattern:

```
sale.order.line (inherits analytic.mixin)
    └─ analytic_distribution stored on line
    └─ On document posting (action_invoice_create, _validate_analytic_distribution)
         └─ account.move.line created with analytic_distribution copied
              └─ account.analytic.line records created via _inverse_analytic_distribution
                   └─ one line per distribution entry (account_ids + percentage)

purchase.order.line (same pattern)
hr_expense.line (same pattern)
```

The `analytic_distribution` Json on financial/document lines is the **seed**. When the document is posted (invoiced, confirmed, etc.), the downstream module calls `_validate_distribution` (triggered by `context['validate_analytic']`) and then copies the distribution to `account.move.line`. The inverse setter on `account.analytic.line.analytic_distribution` then **explodes** the Json into separate concrete line records, one per `(account_id, percentage)` pair, with the amount proportionally scaled.

### override_pattern: How `analytic.mixin` Auto-Populates Analytic Distribution

The auto-population flow uses the **distribution model matching** pattern:

1. **Trigger**: Downstream module calls `account.analytic.distribution.model._get_distribution(vals)` when creating a line (e.g., `purchase.order.line` in `purchase` module).

2. **Matching** (`_get_applicable_models`):
   - Builds a domain combining all filterable fields from `vals`: `partner_id`, `company_id`, `partner_category_id`
   - For `partner_category_id`: extends domain with `[False]` to also match models without a category restriction
   - For `partner_id` and `company_id`: extends with `[value, False]` to match both specific and global models

3. **Merge** (`_get_distribution`):
   - Iterates matching models in `sequence` order
   - Uses set intersection on `root_plan_id` to track which plans already have accounts assigned
   - **Additive across plans**: Model A's distribution (Project plan) + Model B's distribution (Department plan) are both included
   - **Exclusive within a plan**: Once Model A contributes a Project plan account, Model B's Project plan account is ignored
   - Result is a merged Json dict: `{"12": 100.0}` or `{"12": 40.0, "56": 60.0}`

4. **Write**: The merged dict is written to the line's `analytic_distribution` field. Because the field has `inverse='_inverse_analytic_distribution'`, this automatically splits the line if the distribution is non-uniform.

**Downstream override point**: Any module can extend `_get_applicable_models` or `_get_distribution` by overriding the method on `account.analytic.distribution.model`, or by calling `sudo()._get_distribution(vals)` with modified vals.

### workflow_trigger: When `account.analytic.line` Records Are Created

| Trigger Point | Module | Mechanism |
|---|---|---|
| Vendor bill posted | `account` | `account.move.line` created with `analytic_distribution`; `_inverse_analytic_distribution` called on write |
| Customer invoice posted | `account` | Same mechanism |
| Purchase order line confirmed | `purchase` | `_validate_distribution` called at confirm; lines created when PO is invoiced |
| Sale order line confirmed | `sale` | Similar flow via `sale_management` |
| Expense submitted | `hr_expense` | `_validate_distribution` called; lines created on sheet approval |
| Timesheet recorded | `sale_timesheet` / `hr_timesheet` | `account.analytic.line` created directly with `amount` from timesheet UoM/qty |
| Manual entry | `analytic` | User creates `account.analytic.line` directly |

The critical trigger is the `_inverse_analytic_distribution` on `account.analytic.line` itself -- it fires whenever the `analytic_distribution` Json is written to a line, splitting it into multiple records if needed.

### failure_mode: What Happens When Things Go Wrong

#### Scenario 1: No analytic plan exists / `analytic.project_plan` not set

```
__get_all_plans() reads ir.config_parameter 'analytic.project_plan'
    ↓
if not project_plan:
    raise UserError("A 'Project' plan needs to exist and its id needs to be set as `analytic.project_plan` in the system variables")
```

**Consequence**: The entire analytic system fails at the module level. Any code calling `_get_all_plans()` (which is called by every mixin method) will raise. **Mitigation**: The `analytic_data.xml` creates the Project plan with `id=1` and sets the parameter via `set_param` during installation.

#### Scenario 2: Distribution percentages do not sum to 100%

```
_validate_distribution() triggered by context['validate_analytic']
    ↓
for plan_id in mandatory_plans_ids:
    if float_compare(distribution_by_root_plan.get(plan_id, 0), 100, precision_digits=X) != 0:
        raise ValidationError("One or more lines require a 100% analytic distribution.")
```

**Consequence**: `ValidationError` blocks the document from being posted. **Scope**: Only enforced for plans where applicability is `mandatory`. Optional plans allow any sum. **Mitigation**: UI widget prevents submission until distribution sums to 100% for mandatory plans.

#### Scenario 3: Archived account used in distribution

```
_compute_distribution_analytic_account_ids():
    all_ids = {int(...) for rec in self for key in ...}
    existing_accounts_ids = set(self.env['account.analytic.account'].browse(all_ids).exists().ids)
    # .exists() silently removes archived/missing records
```

**Consequence**: Archived accounts are silently dropped from `distribution_analytic_account_ids` (the many2many). The distribution percentages are NOT re-normalized -- the sum will be less than 100% if an archived account held a percentage. This can cause `ValidationError` on mandatory plans. **Mitigation**: UI widget warns users when selecting archived accounts.

#### Scenario 4: Company-scoped account used in global distribution model

```
_check_company_accounts():
    query checks model.analytic_distribution references account.company_id
    AND model.company_id IS NULL OR != account.company_id
    ↓
    raise UserError("You defined a distribution with analytic account(s) belonging to a specific company but a model shared between companies or with a different company")
```

**Consequence**: `UserError` on `create()`/`write()` of the distribution model. Prevents saving the model. **Scope**: Only fires when the constraint is violated (i.e., when saving).

#### Scenario 5: Plan changed on account with existing lines (orphan risk)

```
_update_accounts_in_analytic_lines(new_fname, current_fname, accounts):
    domain = [(new_fname, 'not in', accounts.ids + [False]), (current_fname, 'in', accounts.ids)]
    if self.env['account.analytic.line'].sudo().search_count(domain, limit=1):
        raise RedirectWarning("Whoa there! Making this change would wipe out your current data.")
```

**Consequence**: `RedirectWarning` blocks the plan change and offers a "See them" button to inspect affected lines. User must manually move lines first. **Scope**: Fires when moving accounts between plans where the target column already contains unrelated accounts.

---

## L4: Deep Technical Analysis

### performance: Indexing Strategy for Analytic Line Queries

The analytic module uses five distinct indexing strategies across its models:

#### 1. B-tree Partial Index on Plan Columns (Dynamic Fields)

When `_sync_plan_column` creates a stored field for a root plan, it also creates a **partial B-tree index**:

```python
indexname = make_index_name(tablename, column)
create_index(self.env.cr, indexname, tablename, [column], 'btree',
             f'{column} IS NOT NULL')
```

The `WHERE column IS NOT NULL` predicate means the index only contains rows where the plan column is filled. This keeps the index small and fast on sparse data. Column names follow the pattern `x_plan{N}_id` or `account_id` for the project plan.

#### 2. GIN Index on `analytic_distribution` JSON

`analytic.mixin.init()` runs raw SQL to create a GIN index:

```sql
CREATE INDEX IF NOT EXISTS {table}_analytic_distribution_accounts_gin_index
  ON {table} USING gin(
    regexp_split_to_array(
      jsonb_path_query_array(analytic_distribution, '$.keyvalue()."key"')::text,
      '\D+'
    )
  )
```

This index extracts all numeric account IDs from the JSON keys and indexes them as a text array. It enables fast `ANY` and `OVERLAPS` queries when searching lines by account ID.

#### 3. Trigram Index on `account.analytic.account.name`

```python
name = fields.Char(..., index='trigram', ...)
```

The trigram index supports `ilike` search withGIN similarity, making fuzzy name searches fast on large account lists.

#### 4. B-tree Index on `account.analytic.line.date`

```python
date = fields.Date(..., index=True, ...)
```

Supports date-range filtering in list views and reports.

#### 5. `parent_path` B-tree for Hierarchical Plan Queries

```python
parent_path = fields.Char(index='btree')
```

The `parent_path` field stores materialized tree paths (e.g., `"1/5/23/"`). The `LIKE parent_path || '%'` pattern in `all_account_count` uses this index for efficient descendant queries without recursive CTEs.

#### Performance Anti-Patterns to Avoid

- **Do not** use `_get_plan_fnames()` in a loop over records -- it calls `__get_all_plans()` which hits the `@ormcache` but still iterates over all plans
- **Do not** `read()` individual fields on `account.analytic.line` records in a loop -- use `read_group` or `mapped()` instead
- **Do not** trigger `_validate_distribution` on every `write()` -- only on document posting (when `context['validate_analytic']` is set)

---

### version_change: `account.analytic.distribution.model` Changes in Odoo 19

The `account.analytic.distribution.model` was introduced in Odoo 18 as part of the new multi-plan architecture. In Odoo 19, several changes were made:

#### Structure Changes

| Aspect | Odoo 18 | Odoo 19 |
|---|---|---|
| Model name | Same | Same |
| Inherits | `analytic.mixin` | Same |
| `sequence` field | Added | Default 10 |
| `_rec_name` | Default (`name`) | `create_date` for chronological ordering |
| `_order` | Default | `sequence, id desc` |
| `_check_company_auto` | Not set | `True` |
| `_check_company_domain` | Not set | `models.check_company_domain_parent_of` |

#### `_get_distribution` Logic (Critical)

In Odoo 18, the distribution merge logic used a **first-match-wins** approach per plan, which meant the most specific model (highest sequence, most matching criteria) would take precedence. In Odoo 19, the logic was refactored to use **root-plan deduplication** via set intersection:

```python
applied_plans = vals.get('related_root_plan_ids', self.env['account.analytic.plan'])
for model in applicable_models:
    if not applied_plans & model.distribution_analytic_account_ids.root_plan_id:
        res |= model.analytic_distribution or {}
        applied_plans += model.distribution_analytic_account_ids.root_plan_id
```

This means:
- Models are processed in sequence order
- A root plan's first contributing model locks that plan
- Subsequent models contributing the same root plan are ignored for that plan
- But subsequent models CAN contribute to different root plans

#### Cross-Company Constraint Addition

Odoo 19 added `_check_company_accounts` (not present in Odoo 18):

```python
@api.constrains('company_id')
def _check_company_accounts(self):
    query = SQL(
        """SELECT model.id FROM account_analytic_distribution_model model
           JOIN account_analytic_account account
             ON ARRAY[account.id::text] && %s
          WHERE account.company_id IS NOT NULL
            AND model.id = ANY(%s)
            AND (model.company_id IS NULL OR model.company_id != account.company_id)""",
        self._query_analytic_accounts('model'),
        self.ids,
    )
```

This prevents a global distribution model (no `company_id`) from referencing company-scoped analytic accounts, which would leak cost data across companies.

---

### security: Access Control and Multi-Company Deep Dive

#### Group-Based Access: `group_analytic_accounting`

All 5 concrete models require `group_analytic_accounting` for any CRUD operation. The group is defined in `analytic_security.xml`:

```xml
<record id="group_analytic_accounting" model="res.groups">
    <field name="name">Analytic Accounting</field>
</record>
```

In `res.config.settings`, enabling Analytic Accounting sets this implied group:

```python
group_analytic_accounting = fields.Boolean(
    string='Analytic Accounting',
    implied_group='analytic.group_analytic_accounting'
)
```

Users without this group see no analytic menu items and cannot read/write any analytic records.

#### Multi-Company Record Rules (Critical Differences)

**`account.analytic.account`** -- Two-part domain:
```python
domain_force = ['|', ('company_id', '=', False), ('company_id', 'parent_of', company_ids)]
```
- Accounts **without** a `company_id` are visible to all users (globally shared)
- Accounts **with** a `company_id` are only visible if the user's company is in the account's company lineage (parent_of check supports multi-level company hierarchies)

**`account.analytic.line`** -- Single-part domain:
```python
domain_force = [('company_id', 'in', company_ids)]
```
- Lines **always** require a company (no `False` fallback)
- Users can only see lines from companies they have access to
- **No global lines exist** -- this is enforced at the data level (company is `required=True`, `readonly=True`)

**`account.analytic.applicability` and `account.analytic.distribution.model`** -- Same as account:
```python
domain_force = ['|', ('company_id', '=', False), ('company_id', 'parent_of', company_ids)]
```
- Global applicability rules and distribution models are visible to all companies
- Company-scoped ones are restricted to the company lineage

#### Data Leakage Risks

| Risk | Mitigation |
|---|---|
| User with access to Company A creates distribution model using Company B's accounts | `_check_company_accounts` SQL constraint prevents saving |
| Company A user sees Company B's analytic lines | Record rule `('company_id', 'in', company_ids)` filters automatically |
| Account without company exposes costs to all companies | Demo data uses company-less accounts; production should assign `company_id` |
| Partner-filtered distribution model leaks across companies | `partner_id` is matched only; partner may have records in multiple companies but the model itself must match `company_id` |

#### `bypass_search_access=True` on `partner_id`

In `account.analytic.account`, the `partner_id` field uses `bypass_search_access=True`:

```python
partner_id = fields.Many2one(
    'res.partner',
    bypass_search_access=True,  # Speed up name_search calls
    ...
)
```

This is a **security-relevant optimization**: it allows searching for accounts by partner name even when the user doesn't have read access to `res.partner`. This is appropriate because the account's `partner_id` is a classification field, not a data leak.

---

### plan_validation: `root_analytic_account_id` and Plan Validation Logic

There is **no field named `root_analytic_account_id`** in the Odoo 19 analytic module. The closest concept is `root_plan_id` on `account.analytic.account`, which references the topmost ancestor plan for any account.

#### `root_plan_id` Derivation

```python
root_plan_id = fields.Many2one(
    'account.analytic.plan',
    related="plan_id.root_id",  # via the plan's computed root_id
    store=True,
)
```

The plan's `root_id` is computed from `parent_path`:

```python
@api.depends('parent_id', 'parent_path')
def _compute_root_id(self):
    for plan in self.sudo():
        plan.root_id = int(plan.parent_path[:-1].split('/')[0]) if plan.parent_path else plan
```

**For root plans** (no parent): `root_id = plan` (self-reference via integer ID)
**For child plans**: `root_id = first segment of parent_path`

#### Plan Validation During Account Assignment

When a user assigns an analytic account to a financial line, the validation chain is:

1. **View-level domain** (`_get_plan_domain`): The account selection widget is filtered to only show accounts under the specific plan being edited:

   ```python
   def _get_plan_domain(self, plan):
       return [('plan_id', 'child_of', plan.id)]
   ```

   This prevents selecting an account from Plan A while editing Plan B's column.

2. **`@api.constrains` on mixin** (`_check_account_id`): Validates that at least one plan column is filled:

   ```python
   @api.constrains(lambda self: self._get_plan_fnames())
   def _check_account_id(self):
       fnames = self._get_plan_fnames()
       for line in self:
           if not any(line[fname] for fname in fnames):
               raise ValidationError(_("At least one analytic account must be set"))
   ```

   This fires only on the mixin's constraint check (not on the concrete model unless it calls the mixin's check).

3. **Mandatory plan validation** (`_validate_distribution`): When `context['validate_analytic']` is set, checks that each mandatory root plan sums to exactly 100%:

   ```python
   for plan_id in mandatory_plans_ids:
       if float_compare(distribution_by_root_plan.get(plan_id, 0), 100, ...) != 0:
           raise ValidationError("One or more lines require a 100% analytic distribution.")
   ```

   The `mandatory_plans_ids` come from `get_relevant_plans`, which only returns root plans (those without a parent). Child plans cannot be mandatory independently -- they inherit the applicability of their root plan.

4. **Company consistency on account** (`_check_company_consistency`): Prevents moving an account to a different company if it already has lines:

   ```python
   @api.constrains('company_id')
   def _check_company_consistency(self):
       for company, accounts in groupby(self, lambda account: account.company_id):
           if company and self.env['account.analytic.line'].sudo().search_count([
               ('auto_account_id', 'in', [account.id for account in accounts]),
               '!', ('company_id', 'child_of', company.id),
           ], limit=1):
               raise UserError(_("You can't change the company..."))
   ```

#### `get_relevant_plans` Filter Logic

This method (called by the UI widget and `_validate_distribution`) determines which plans are mandatory/optional/unavailable:

```python
def get_relevant_plans(self, **kwargs):
    project_plan, other_plans = self.env['account.analytic.plan']._get_all_plans()
    root_plans = (project_plan + other_plans).filtered(lambda p: (
        p.all_account_count > 0       # Must have accounts
        and not p.parent_id            # Must be root (no parent)
        and p._get_applicability(...) != 'unavailable'
    ))
    # Force-show plans with already-selected accounts (in case applicability changed)
    forced_plans = self.env['account.analytic.account'].browse(
        record_account_ids
    ).exists().mapped('root_plan_id') - root_plans
    return [dict for plan in (root_plans + forced_plans).sorted('sequence')]
```

Key points:
- **Only root plans** are returned (child plans are excluded from applicability)
- **Plans with zero accounts** are excluded unless already in use
- **Forced plans**: if a line already has an account from a now-unavailable plan, that plan is still shown so the user can change it
- **`sequence` ordering**: lower sequence number = higher priority in the UI

#### `root_analytic_account_id` Misconception

There is no such field. Some documentation or forum posts may refer to "root analytic account" but this is not a field name in the codebase. The correct concept is:
- **`root_plan_id`**: the topmost ancestor plan for an account
- **`plan_id.root_id`**: the same, accessed via the account's `plan_id` relationship

---

## Tags

#odoo #odoo19 #modules #analytic #accounting #distribution #json #orm
