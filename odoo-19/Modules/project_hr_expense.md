---
type: module
module: project_hr_expense
tags: [odoo, odoo19, project, hr_expense, profitability, analytic]
created: 2026-04-06
updated: 2026-04-11
updated_details: |
  2026-04-11 — Upgraded to L4 depth. Added version change Odoo 18→19 section,
  expanded performance analysis with query-level details, added supply-chain security
  analysis for cross-project expense visibility, documented _get_analytic_distribution
  origin on analytic.plan.fields.mixin, expanded edge cases 9-12, clarified
  _get_profitability_aal_domain JOIN cost analysis.
---

# Project HR Expense

## Overview

| Property | Value |
|----------|-------|
| **Name** | Project Expenses |
| **Technical** | `project_hr_expense` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Category** | Services/expenses |
| **Version** | 1.0 |
| **Auto-install** | Yes (bridging module) |
| **Summary** | Bridge between `project_account` and `hr_expense` — surfaces employee expenses in the project profitability report and embeds an Expenses smart button on the project form. |

## Purpose

`project_hr_expense` is a thin **bridging/extension module**. It does not introduce new database tables. Instead it:

1. Extends `project.project` with profitability methods that aggregate posted employee expenses charged to the project's analytic account.
2. Extends `hr.expense` so that when an expense is created from within a project form (via `project_id` context), the project's analytic distribution is auto-populated.
3. Wires two `ir.embedded.actions` records so that an "Expenses" tab appears in the project smart buttons and in the project update (dashboard) side panel.

## Dependencies

```yaml
depends:
  - project_account   # provides project.account_id, _get_profitability_items, _get_add_purchase_items_domain
  - hr_expense         # provides hr.expense model, analytic_distribution field
```

Both are marked `auto_install: True`, so installing `project_hr_expense` automatically pulls in its dependencies.

---

## Architecture

```
project.project  (project_hr_expense extends)
    │ account_id ──────────────────────────────────────────┐
    │                                                         │
    │ _get_expenses_profitability_items()                     │
    │   searches hr.expense                                  │
    │     WHERE analytic_distribution IN (account_id)        │
    │       AND state IN (posted, in_payment, paid)         │
    │                                                         │
    │ _get_already_included_profitability_invoice_line_ids() │
    │   searches account.move.line                           │
    │     WHERE expense_id != False                         │
    │       (excludes from purchase section to avoid double-count)
    │
    │ _get_profitability_aal_domain()
    │   excludes account.analytic.line
    │     WHERE move_line_id.expense_id != False
    │       (excludes AAL that came via vendor bill from expense)
    │
    │ _get_add_purchase_items_domain()
    │   excludes purchase.order.line
    │     WHERE expense_id != False
    │
    ├─► ir.embedded.actions  (×2)
    │     → action_open_project_expenses()
    │         sets context['project_id'] = project.id
    │             ↓
    │   hr.expense  (project_hr_expense extends)
    │     _compute_analytic_distribution()
    │       reads project._get_analytic_distribution()
    │         if project_id in context AND analytic_distribution not already set
    │     create()
    │       propagates project analytic_distribution into vals
```

---

## Models

### project.project — Extension

_Inherits: `project.project` (via `_inherit`). No new table created._

#### Action Methods

##### `action_open_project_expenses()`

Opens the expense list view filtered to all expenses whose `analytic_distribution` contains any of the project's analytic account IDs.

```python
def action_open_project_expenses(self):
    self.ensure_one()
    return self._get_expense_action(domain=[('analytic_distribution', 'in', self.account_id.ids)])
```

- `ensure_one()` enforces single-record context (called from a form button on one project).
- `domain` uses the `in` operator so multi-analytic-account projects (split% distributions) correctly surface all relevant expenses.
- Delegates to `_get_expense_action` for consistent action construction.

##### `_get_expense_action(domain=None, expense_ids=None)`

Internal helper that builds the `ir.actions.act_window` for the expense list. Factors out shared logic used by both `action_open_project_expenses` and `action_profitability_items`.

**Empty guard:** Returns `{}` immediately if both `domain` and `expense_ids` are falsy, preventing a clickable action from being registered on a profitability section that has no matching records.

```python
def _get_expense_action(self, domain=None, expense_ids=None):
    if not domain and not expense_ids:
        return {}
    action = self.env["ir.actions.actions"]._for_xml_id("hr_expense.hr_expense_actions_all")
    action.update({
        'display_name': self.env._('Expenses'),
        'views': [[False, 'list'], [False, 'form'], [False, 'kanban'],
                  [False, 'graph'], [False, 'pivot']],
        'context': {'project_id': self.id},
        'domain': domain or [('id', 'in', expense_ids)],
    })
    if not self.env.context.get('from_embedded_action') and len(expense_ids) == 1:
        action["views"] = `False, 'form'`
        action["res_id"] = expense_ids[0]
    return action
```

Key behaviours:
- When called from `action_profitability_items` (single expense), it opens the **form** view directly, unless invoked from the embedded action (where list view is preferred).
- `context` key `'project_id': self.id` is stored on the action so downstream `hr.expense.create()` calls pre-populate `analytic_distribution` from the project.
- `display_name` is localised via `self.env._()`.

##### `action_profitability_items(section_name, domain=None, res_id=False)`

Routes a profitability section click to the correct action. When `section_name == 'expenses'`, delegates to `_get_expense_action`. All other sections fall through to `project_account`.

```python
def action_profitability_items(self, section_name, domain=None, res_id=False):
    if section_name == 'expenses':
        return self._get_expense_action(domain, [res_id] if res_id else [])
    return super().action_profitability_items(section_name, domain, res_id)
```

---

#### Profitability Label and Sequence

##### `_get_profitability_labels()`

Adds the `expenses` key to the label map returned by `project_account`.

```python
def _get_profitability_labels(self):
    labels = super()._get_profitability_labels()
    labels['expenses'] = self.env._('Expenses')
    return labels
```

##### `_get_profitability_sequence_per_invoice_type()`

Assigns display order `13` to the expenses section, placing it after vendor bills (12) but before other cost types (14, 15).

```python
def _get_profitability_sequence_per_invoice_type(self):
    sequence_per_invoice_type = super()._get_profitability_sequence_per_invoice_type()
    sequence_per_invoice_type['expenses'] = 13
    return sequence_per_invoice_type
```

---

#### Core Profitability Computation

##### `_get_expenses_profitability_items(with_action=True)`

Fetches and aggregates all posted/in_payment/paid expenses linked to the project's analytic account, converts their amounts to the project's currency, and returns a costs-only profitability section.

```python
def _get_expenses_profitability_items(self, with_action=True):
    if not self.account_id:
        return {}
    can_see_expense = with_action and self.env.user.has_group(
        'hr_expense.group_hr_expense_team_approver')

    expenses_read_group = self.env['hr.expense']._read_group(
        [
            ('state', 'in', ['posted', 'in_payment', 'paid']),
            ('analytic_distribution', 'in', self.account_id.ids),
        ],
        groupby=['currency_id'],
        aggregates=['id:array_agg', 'untaxed_amount_currency:sum'],
    )
    if not expenses_read_group:
        return {}

    expense_ids = []
    amount_billed = 0.0
    for currency, ids, untaxed_amount_currency_sum in expenses_read_group:
        if can_see_expense:
            expense_ids.extend(ids)
        amount_billed += currency._convert(
            from_amount=untaxed_amount_currency_sum,
            to_currency=self.currency_id,
            company=self.company_id,
        )

    section_id = 'expenses'
    expense_profitability_items = {
        'costs': {
            'id': section_id,
            'sequence': self._get_profitability_sequence_per_invoice_type()[section_id],
            'billed': -amount_billed,
            'to_bill': 0.0,
        },
    }
    if can_see_expense:
        args = [section_id, [('id', 'in', expense_ids)]]
        if len(expense_ids) == 1:
            args.append(expense_ids[0])
        action = {'name': 'action_profitability_items',
                  'type': 'object', 'args': json.dumps(args)}
        expense_profitability_items['costs']['action'] = action
    return expense_profitability_items
```

**Key design decisions:**

- **No `to_bill`**: Employee expenses are always `billed` (already paid out of pocket) — there is no "to be billed" concept for expenses. `to_bill: 0.0` is therefore always zero.
- **Negative `billed`**: The `billed` value is negated (`-amount_billed`) because in the profitability data model, costs are expressed as negative numbers (revenues minus costs = margin).
- **Currency conversion**: Uses `currency._convert()` with `company=self.company_id` (not the expense's company) to convert all foreign-currency expenses into the **project's** currency. This is important for multi-company projects.
- **`_read_group` with `groupby=['currency_id']`**: Aggregates expenses per currency before conversion. Without this, a single `currency._convert()` call with a mixed-currency sum would be arithmetically incorrect.
- **Security gate (`can_see_expense`)**: Even when `with_action=False` (profitability snapshot without actions), non-approvers see zero expense data because `group_hr_expense_team_approver` is required. When `with_action=True`, the action link is only attached if the user can see the data.
- **`analytic_distribution` `in` operator**: Supports split-percentage distributions. An expense whose analytic distribution is `{account_A: 60, account_B: 40}` will be included if either account matches the project.

##### `_get_profitability_items(with_action=True)`

Merges the expenses cost section into the full profitability data structure returned by `project_account`.

```python
def _get_profitability_items(self, with_action=True):
    profitability_data = super()._get_profitability_items(with_action)
    expenses_data = self._get_expenses_profitability_items(with_action)
    if expenses_data:
        if 'revenues' in expenses_data:  # never true for expenses, preserved for future use
            revenues = profitability_data['revenues']
            revenues['data'].append(expenses_data['revenues'])
            revenues['total'] = {k: revenues['total'][k] + expenses_data['revenues'][k]
                                  for k in ['invoiced', 'to_invoice']}
        costs = profitability_data['costs']
        costs['data'].append(expenses_data['costs'])
        costs['total'] = {k: costs['total'][k] + expenses_data['costs'][k]
                          for k in ['billed', 'to_bill']}
    return profitability_data
```

Only the `costs` side is populated — expenses generate no revenue. The merge updates both `costs['data']` (individual section entry) and `costs['total']` (cumulative sum across all cost sections).

---

#### Double-Counting Prevention

##### `_get_already_included_profitability_invoice_line_ids()`

Extends the exclusion set used by `project_account` so that vendor bill journal items originating from an expense are **not** double-counted as purchase order costs.

```python
def _get_already_included_profitability_invoice_line_ids(self):
    move_line_ids = super()._get_already_included_profitability_invoice_line_ids()
    query = self.env['account.move.line'].sudo()._search([
        ('expense_id', '!=', False),
        ('id', 'not in', move_line_ids),
    ])
    return move_line_ids + list(query)
```

The logic: `account.move.line` records linked to `hr.expense` (via `expense_id`) are excluded from the purchase-order-line profitability scan in `project_account`, because those costs are already captured via `_get_expenses_profitability_items`. The `not in` guard prevents re-adding IDs already excluded by the parent call.

> **L4 Edge Case — State dependency**: The `hr.expense` → vendor bill flow creates `account.move.line` records linked via `expense_id` **only after the expense is posted**. However, `_get_expenses_profitability_items` only counts expenses in `['posted', 'in_payment', 'paid']` states. When an expense is in one of these states, the corresponding vendor bill lines are guaranteed to exist and be excluded. If an expense is in an earlier state (`draft`, `submitted`, `approved`) its bill lines do not exist, so no exclusion is needed.

##### `_get_profitability_aal_domain()`

Extends the analytic account line domain to exclude any AAL whose `move_line_id` links to an expense (already counted via the vendor bill route in `project_account`).

```python
def _get_profitability_aal_domain(self):
    return Domain.AND([
        super()._get_profitability_aal_domain(),
        ['|', ('move_line_id', '=', False), ('move_line_id.expense_id', '=', False)],
    ])
```

The `|` (OR) clause: include lines that have **no** `move_line_id` (pure analytic entries) OR whose linked journal line is **not** expense-linked. This prevents the `account.analytic.line` → `account.move.line` → `hr.expense` chain from producing a second cost entry.

**Performance note (L4):** The `move_line_id.expense_id` condition implicitly JOINs `account_move_line` into the domain. For large analytic line tables, this JOIN cost should be measured with `EXPLAIN ANALYZE`. The `move_line_id = False` branch allows the planner to short-circuit on pure AAL records without requiring the JOIN, which mitigates the cost for the majority of records that have no `move_line_id`.

##### `_get_add_purchase_items_domain()`

Extends the exclusion domain for the "Add Purchase Items" sidebar widget so expense-linked purchase order lines are not offered for manual inclusion.

```python
def _get_add_purchase_items_domain(self):
    return Domain.AND([
        super()._get_add_purchase_items_domain(),
        Domain('expense_id', '=', False),
    ])
```

This mirrors the double-counting prevention at the purchase order line level: if a purchase order line has already been re-invoiced as an expense, it should not appear in the "Add Purchase Items" panel.

---

### hr.expense — Extension

_Inherits: `hr.expense` (via `_inherit`). No new table created._

#### `_compute_analytic_distribution()` — Override

When `hr.expense` is created from within a project form (detected via `project_id` in the context), the project's analytic distribution is applied as a **fallback** — it only fills in `analytic_distribution` if the field is currently empty.

```python
def _compute_analytic_distribution(self):
    project_id = self.env.context.get('project_id')
    if not project_id:
        super()._compute_analytic_distribution()
    else:
        analytic_distribution = self.env['project.project'].browse(
            project_id)._get_analytic_distribution()
        for expense in self:
            expense.analytic_distribution = expense.analytic_distribution or analytic_distribution
```

- **Why fallback, not override?** The field may already be populated by `account.analytic.distribution.model` rules (the parent's `_compute_analytic_distribution`). The project context should not silently override a user-configured distribution, hence `expense.analytic_distribution or analytic_distribution`.
- **`project_id` context source**: Set by `action_open_project_expenses` / `_get_expense_action` when opening the expense list from a project. Also set by `ir.embedded.actions` records registered in `views/project_project_views.xml`.
- **`_get_analytic_distribution()` origin (L4):** This method is defined on `analytic.plan.fields.mixin` (`analytic/models/analytic_line.py`), which is inherited by `project.project` via `project/models/project_project.py` (`_inherit: ['analytic.plan.fields.mixin']`). The method returns `{account_ids_string: 100}` where `account_ids_string` is a comma-separated list of analytic account IDs. If the project has no analytic account, it returns `{}`.

#### `create(vals_list)` — Override

Ensures that any `vals` dict in `vals_list` that lacks an explicit `analytic_distribution` gets the project's analytic distribution applied at create time (before ORM computed-field logic runs).

```python
@api.model_create_multi
def create(self, vals_list):
    project_id = self.env.context.get('project_id')
    if project_id:
        analytic_distribution = self.env['project.project'].browse(
            project_id)._get_analytic_distribution()
        if analytic_distribution:
            for vals in vals_list:
                vals['analytic_distribution'] = vals.get(
                    'analytic_distribution', analytic_distribution)
    return super().create(vals_list)
```

- The `if analytic_distribution` guard avoids a redundant browse when the project has no analytic account.
- Uses `vals.get('analytic_distribution', analytic_distribution)` — the same fallback logic as `_compute_analytic_distribution` but applied directly to the vals dict before `super().create()`.

---

## XML Views and Embedded Actions

### ir.embedded.actions (x2)

Two records register the "Expenses" tab in the project UI:

**Smart button tab** (`project_embedded_action_hr_expenses`):
```xml
<record id="project_embedded_action_hr_expenses" model="ir.embedded.actions">
    <field name="parent_res_model">project.project</field>
    <field name="sequence">77</field>
    <field name="name">Expenses</field>
    <field name="parent_action_id" ref="project.act_project_project_2_project_task_all"/>
    <field name="python_method">action_open_project_expenses</field>
    <field name="context">{"from_embedded_action": true}</field>
    <field name="groups_ids" eval="[(4, ref('hr_expense.group_hr_expense_user'))]"/>
</record>
```

**Project update / dashboard tab** (`project_embedded_action_hr_expenses_dashbord`):
```xml
<record id="project_embedded_action_hr_expenses_dashbord" model="ir.embedded.actions">
    <field name="parent_res_model">project.project</field>
    <field name="sequence">77</field>
    <field name="name">Expenses</field>
    <field name="parent_action_id" ref="project.project_update_all_action"/>
    <field name="python_method">action_open_project_expenses</field>
    <field name="context">{"from_embedded_action": true}</field>
    <field name="groups_ids" eval="[(4, ref('hr_expense.group_hr_expense_user'))]"/>
</record>
```

Both require `group_hr_expense_user` — any user who can access expenses sees the tab. The `context` `{"from_embedded_action": true}` signals to `_get_expense_action` that single-record context should open the **list** view (not the form), which is the standard embedded-action behaviour.

---

## Demo Data

`data/project_hr_expense_demo.xml` (noupdate) performs two functions:

1. **Links existing demo expenses** (travel by car) to the `project.analytic_office_design` analytic account:
   - `hr_expense.travel_admin_by_car_expense` → 100% office design analytic
   - `hr_expense.travel_demo_by_car_expense` → 100% office design analytic

2. **Creates two new expenses** on `project.analytic_construction`, then advances them through `action_submit` / `action_approve` via XML `<function>` tags:
   - `transportation_expense`: 240.0 in company currency, product `expense_product_travel_accommodation`
   - `restaurant_expense`: 320.0 in company currency, product `expense_product_meal`

**Key limitation**: Both demo expenses end at `approved` state — the XML does not post them. Since `_get_expenses_profitability_items` only counts expenses in `['posted', 'in_payment', 'paid']`, the demo records do **not** populate the profitability section. Their purpose is to pre-populate the linked analytic accounts with expense data so that when a user posts an expense through the UI it is immediately visible in the report.

---

## Performance Considerations

| Operation | Performance Impact |
|-----------|-------------------|
| `_get_expenses_profitability_items` | `_read_group` with `analytic_distribution` `in` clause — leverages the `analytic_distribution` JSONB Gin index if one exists. For projects with thousands of expenses, this remains efficient because only `state` and `analytic_distribution` are filtered; no JOIN to `account.move.line` is performed here. |
| `_get_already_included_profitability_invoice_line_ids` | Adds a `sudo()` SQL query on `account.move.line` filtered by `expense_id != False`. This query only returns lines for **posted** expenses (bill exists). In a large dataset, `expense_id` should be indexed on `account_move_line` — verify index existence in production. |
| `_get_profitability_aal_domain` | Adds an implicit JOIN on `move_line_id` to filter analytic lines. If the analytic line table is large, this JOIN could be costly; however the `|` OR with `move_line_id = False` allows the planner to short-circuit on the left branch for pure AAL records (which dominate in most installations). Measure with `EXPLAIN ANALYZE` on the actual analytic line table size. |
| Currency conversion in loop | `currency._convert()` is called once per distinct expense currency, not once per expense, minimising conversion calls. |
| `_get_add_purchase_items_domain` | The `Domain.AND` with `expense_id = False` adds a cheap indexed-column filter to the parent domain from `project_account`. |

---

## Version Change: Odoo 18 to 19

No breaking API changes were identified between Odoo 18 and 19 for this module. All methods, domains, and embedded actions are identical in both versions.

| Aspect | Odoo 18 | Odoo 19 | Change |
|--------|---------|---------|--------|
| `project_hr_expense` manifest | Present | Present | None |
| `_get_expenses_profitability_items` | Present | Present | None |
| `_get_profitability_aal_domain` | Present | Present | None |
| `ir.embedded.actions` | Present | Present | None |
| `Domain.AND` usage | Present | Present | None |

The module was written for Odoo 18+ and uses `Domain.AND` and `Domain` sentinels throughout — no migration work is needed from 18 to 19.

---

## Security

| Concern | Implementation |
|---------|---------------|
| Who can see expense amounts in profitability? | `group_hr_expense_team_approver` — the standard Odoo expense approval group. Without it, the `billed` total is still computed (so the project margin is correct), but no action link or expense list is accessible from the section. |
| Who can see the "Expenses" smart-button tab? | `group_hr_expense_user` — any employee who can log expenses. |
| Can a non-approver see expense details via `action_open_project_expenses`? | The action opens the `hr_expense_actions_all` window with the project domain. Standard `hr.expense` ACLs then apply: a non-approver can only see their own expenses (or those of subordinates). The profitability total (computed regardless of `can_see_expense`) still excludes the non-visible expense amounts — **this is a known limitation**: the `billed` total includes all approved/posted expenses even if the viewer cannot see individual expense records. |
| Cross-company data isolation | `_get_expenses_profitability_items` filters only by `analytic_distribution` and `state`. It does **not** add a `company_id` filter. Expense records are implicitly scoped to the user's `company_ids` by the ORM's record rule layer. The project's `company_id` is used only for currency conversion. |
| SQL injection via domain | All domains use Odoo's ORM domain API (`Domain` sentinel, `&=`, `Domain.AND`). No raw SQL concatenation occurs. Safe. |
| Cross-project expense visibility (L4) | Expenses with split analytic distribution (e.g., `{account_A: 60, account_B: 40}`) appear in **both** projects' profitability at their proportional amount. A user with access to Project A but not Project B would see the expense's 40% portion counted in Project B's profitability if they somehow access Project B — but since they lack Project B access, the embedded action and profitability section are inaccessible. The data is not directly exposed; ACL enforcement is at the action level. |

---

## Edge Cases and Failure Modes

1. **Expense with split analytic distribution**: An expense distributed across multiple analytic accounts (e.g., 60% project A, 40% project B) will appear in **both** projects' profitability reports at its proportional amount. This is correct behaviour — each project bears its share of the cost.

2. **Expense unlinked from project after creation**: If an expense was created with a project's analytic distribution but the distribution is later manually cleared, the expense drops out of the project's profitability on next computation. No cleanup or history tracking is performed.

3. **Expense with no analytic account on project**: If `project.account_id` is `False`, `_get_expenses_profitability_items` returns `{}` immediately, avoiding a domain error. The project will show no expense section.

4. **Foreign-currency expense vs. single-currency project**: Currency conversion uses `company` (the project's company) as the conversion target context. If the project's `company_id` is `False` (multi-company mode with shared project), `currency._convert()` falls back to the rate table using the project's `currency_id` as destination, and the expense's `company_id` for the source company — this produces the correct converted amount. Always assign a `company_id` to projects used for expense tracking in multi-company setups.

5. **Approved expenses are invisible in profitability**: This is a common misconception — `draft`, `submitted`, and `approved` states are all excluded. Only `posted`, `in_payment`, or `paid` expenses appear. This is confirmed by the demo XML: the `action_submit` + `action_approve` calls leave expenses at `approved`, so they never populate the profitability section until a user posts them through the `hr.expense.post.wizard`.

6. **Vendor bill for expense already posted → state change**: When an approved expense is posted, `account.move.line` records are created with `expense_id` set. If the journal entry is then **reset to draft** and the expense returns to `approved` state, `_get_expenses_profitability_items` drops it (approved is not in the counted states). However, the `account.move.line` records still exist with `expense_id` set, so they remain excluded from the purchase section.

7. **Re-invoiced expense vs. project re-invoice flow**: If an expense product has `bill_count_as_expense=True` (triggering automatic vendor bill creation), the expense's cost appears in profitability via `_get_expenses_profitability_items`. The corresponding vendor bill lines are excluded via `_get_already_included_profitability_invoice_line_ids`. The `project_id` context for `_compute_analytic_distribution` is set when opening expenses from the project, not when the product is configured — so products must be selected from the project context to inherit the analytic distribution.

8. **Empty `_get_expense_action` guard**: If `_get_expenses_profitability_items` returns `{}` (no posted expenses), `action_profitability_items` calls `_get_expense_action(domain=None, expense_ids=[])` with both args falsy. `_get_expense_action` returns `{}` in this case, preventing any action from being registered on the profitability section. The section label still appears in the UI but clicking it has no effect — this is the correct graceful degradation.

9. **Project without analytic account in split distribution**: When `account_id` is `False`, `_get_expenses_profitability_items` returns `{}`. The `_compute_analytic_distribution` override calls `project._get_analytic_distribution()` which returns `{}` for projects without an analytic account. An expense created from such a project context will have no `analytic_distribution` set — correct behavior (no auto-population).

10. **Multi-record write on `hr.expense`**: `_compute_analytic_distribution` is a standard ORM computed field with `@api.depends('product_id', 'account_id', 'employee_id')`. It is called per-record by the ORM when any of its dependencies change. The context-based project override works because the context is set on the `env` before the write/create, and the ORM reads `self.env.context` during computation.

11. **Expense in draft state on project without analytic account**: The `analytic_distribution or analytic_distribution` fallback produces `{} or {} = {}`, which is falsy. The field remains unset. When the expense is later submitted and posted, the `_get_expenses_profitability_items` domain `analytic_distribution IN (self.account_id.ids)` with `self.account_id` still `False` would produce `analytic_distribution IN (False)` — which returns no results. If a project later gains an analytic account, existing draft expenses still lack the distribution and will not appear in profitability. They must be re-created or manually updated.

12. **Expense `create` with multiple records**: `@api.model_create_multi` is used, and the project context applies the same `analytic_distribution` to every record in `vals_list`. This is correct: all expenses created from the project context share the same analytic account.

---

## Related Models (Upstream)

| Model | Role | Key Field |
|-------|------|-----------|
| `project.project` | Parent (from `project_account`) | `account_id` (analytic account) |
| `analytic.plan.fields.mixin` | Provides `_get_analytic_distribution()` | Inherited by `project.project` |
| `account.analytic.account` | Analytic account linked to project | — |
| `hr.expense` | Extended model | `analytic_distribution` (JSON), `state`, `currency_id`, `untaxed_amount_currency` |
| `account.move.line` | Vendor bill lines | `expense_id`, `analytic_distribution` |
| `account.analytic.line` | Analytic entries | `move_line_id` |
| `purchase.order.line` | Purchase order lines | `expense_id` |
| `ir.embedded.actions` | Smart button registration | `python_method`, `parent_res_model`, `groups_ids` |

---

## Related Documentation

- [Modules/project_account](odoo-18/Modules/project_account.md) — Parent project profitability and analytic integration
- [Modules/hr_expense](odoo-18/Modules/hr_expense.md) — Employee expense management, states, approval workflow
- [Modules/project_purchase](odoo-18/Modules/project_purchase.md) — Purchase orders in project profitability (shares double-count prevention logic)
- [Modules/Stock](odoo-18/Modules/stock.md) — Inventory costs in project profitability (parallel pattern)

---

## Tags

`#odoo19` `#modules` `#project` `#hr_expense` `#profitability` `#analytic`
