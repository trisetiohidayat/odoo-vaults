---
tags:
  - odoo
  - odoo19
  - modules
  - sale
  - project
  - service
  - milestone
  - billing
description: "sale_project — bridges Sale and Project apps; auto-generates project.project and project.task from confirmed sales orders with full bidirectional SOL linking, milestone delivery, reinvoicing, and profitability tracking"
---

# sale_project — Sales-Project Integration

**aka** Sales - Project module
**Category** Sales/Sales
**Summary** Task Generation from Sales Orders
**License** LGPL-3
**Depends:** `sale_management`, `sale_service`, `project_account`
**Auto-installs:** `sale_management`, `project_account`
**Post-init hook:** `_set_allow_billable_in_project`
**Uninstall hook:** cleans up `ir.embedded.actions` records tied to `action_open_project_invoices` / `action_view_sos`

---

## Purpose

`sale_project` bridges the **Sale** and **Project** apps. It enables service product lines sold on a confirmed Sales Order to automatically generate `project.project` and `project.task` records, with full bidirectional linking back to `sale.order.line`. It provides milestone-based delivery tracking for revenue recognition, reinvoicing flows for project costs, and a profitability dashboard on the project.

---

## Dependency Chain

```
sale_management
    └── sale_service         (is_service, service_tracking, service_policy fields)
    └── sale_project         (this module — service → project/task generation)
project_account
    └── project_project.account_id  (analytic account on project for cost tracking)
```

`sale_project` does **not** depend on `sale_timesheet`. Time tracking is optional — `project_task` records are created regardless of whether timesheet logging is active.

---

## Models Extended

### `sale.order.line` — Extends `sale.order.line`

**File:** `models/sale_order_line.py`

Extends the sale order line with project/task generation fields and milestone-aware delivered quantity computation.

#### Fields Added

| Field | Type | Index | Store | Copy | Notes |
|---|---|---|---|---|---|
| `project_id` | `Many2one project.project` | `btree_not_null` | Yes | No | Generated project for this SOL. Set once per line; never cleared unless cancelled. |
| `task_id` | `Many2one project.task` | `btree_not_null` | Yes | No | Generated task for this SOL (only for `task_in_project` products). |
| `reached_milestones_ids` | `One2many project.milestone` | — | No | No | Mirror of `project.milestone.sale_line_id` filtered to `is_reached = True`. Used in `qty_delivered` computation. |
| `qty_delivered_method` | `Selection` | — | Yes | — | Extended to include `('milestones', 'Milestones')`. |

#### `qty_delivered_method` Logic — `_compute_qty_delivered_method`

```
service_type == 'milestones'
    AND is_expense == False
    → qty_delivered_method = 'milestones'
Otherwise
    → delegates to super() (ordered_qty, timesheet, manual)
```

Products with `service_type = 'milestones'` (mapped from `service_policy = 'delivered_milestones'`) automatically opt into milestone-based delivery tracking.

#### Delivered Quantity — `_prepare_qty_delivered` / `_compute_qty_delivered`

For milestone-tracked SOLs, `qty_delivered` is computed via `_prepare_qty_delivered`:

```python
project_milestone_read_group = self.env['project.milestone']._read_group(
    [('sale_line_id', 'in', lines_by_milestones.ids), ('is_reached', '=', True)],
    ['sale_line_id'],
    ['quantity_percentage:sum'],
)
# quantity_percentage:sum is the sum of all reached milestones' percentages
# For each SOL:
qty_delivered = reached_percentage_sum × product_uom_qty
```

**Example:** 3 milestones each at 33.33% → `qty_delivered = 0.9999 × qty_ordered`. Odoo rounds appropriately for invoicing. This read group aggregation handles multiple milestones correctly in a single query without N+1.

#### `analytic_distribution` — `_compute_analytic_distribution`

If the SOL has no explicit analytic distribution and either `product_id.project_id` or `order_id.project_id` is set, the project's analytic account is inherited:

```python
if line.analytic_distribution:
    # SOL already has a distribution — append project accounts, don't replace
    applied_root_plans = account_analytic_account.browse(...).root_plan_id
    accounts_to_add = project._get_analytic_accounts().filtered(
        lambda account: account.root_plan_id not in applied_root_plans
    )
    # Project account is added to each analytic distribution line
    line.analytic_distribution = {
        f"{account_ids},{','.join(map(str, accounts_to_add.ids))}": percentage
        for account_ids, percentage in line.analytic_distribution.items()
    }
else:
    line.analytic_distribution = project._get_analytic_distribution()
```

This preserves pre-existing multi-account distributions (e.g., from a sales team policy) and only appends the project account.

#### Project/Task Generation — `_timesheet_service_generation`

Called during `sale.order._action_confirm()` via `order_line.sudo()._timesheet_service_generation()`. Handles three `service_tracking` modes:

**`project_only` and `task_in_project`** — per-SO project creation:

1. Builds `map_so_project` (for products without a template) and `map_so_project_templates` (for template-based products) by querying existing SOLs on the same order that already have a project.
2. If the product's template hasn't been used on this order yet, calls `_timesheet_create_project()`:
   - Creates an analytic account via `order_id._prepare_analytic_account_data()` if `order_id.project_account_id` is not set.
   - Project name format: `"SO Name - [default_code] Product Name"` (code only if present).
   - If a `project_template_id` is set: calls `action_create_from_template()` (if template `is_template`) or `copy()` with values, then writes `sale_line_id` and `partner_id` onto all tasks including sub-tasks (which normally lose their SOL link during copy).
   - If no template: creates a bare project and pre-populates it with standard stages: To Do, In Progress, Done, Cancelled.
   - Sets `reinvoiced_sale_order_id = self.order_id` on the project and writes `project_id` back onto the SOL.
3. For `task_in_project` products where no task exists yet and the template hasn't been used, calls `_timesheet_create_task()`.
4. Calls `_handle_milestones()`.

**`task_global_project`** — task in existing project:

1. Looks up `product_id.project_id` (the global project pre-configured on the product).
2. Sets `so_line.project_id = map_sol_project[sol.id]` if no `so_line.order_id.project_id` exists.
3. Creates a task in that project if `product_uom_qty > 0`.

**`_handle_milestones()`** — milestone provisioning:

```
if service_policy != 'delivered_milestones' → return
if not project.allow_milestones → enable it
if project has milestones without a sale_line_id
    → assign them to this SOL, splitting quantity evenly (qty_percentage = 1/N each)
else
    → create one milestone named after the SOL, qty_percentage = 1.0
    → if task_in_project, assign it to the SOL's task
```

The auto-split logic means that if a project template pre-creates 3 milestones, they are evenly divided across the SOL quantity.

#### `write` — `product_uom_qty` Change

When `product_uom_qty` changes on a confirmed, service, non-expense SOL:
1. Regenerates the task via `_timesheet_service_generation()` (idempotent — if task exists, linking is updated rather than duplicated).
2. Recomputes `allocated_hours` on the linked task using `_convert_qty_company_hours()` (passes through `product_uom_qty` as hours; subclasses like `sale_timesheet` perform currency/UDH conversion).

#### `copy_data` — Preserving Analytic Distribution

When duplicating an SOL, if the analytic distribution matches the SO-level project distribution, the copy clears it (the project will be re-derived from the copy's context).

---

### `project.task` — Extends `project.task`

**File:** `models/project_task.py`

#### Fields Added

| Field | Type | Group | Index | Notes |
|---|---|---|---|---|
| `sale_order_id` | `Many2one sale.order` | — | — | Computed store. The authoritative SO for this task. |
| `sale_line_id` | `Many2one sale.order.line` | — | `btree_not_null recursive` | Computed store; copy-enabled. Domain filters to sellable, service, partner-compatible lines. |
| `project_sale_order_id` | `Many2one sale.order` | — | — | Related to `project_id.sale_order_id` |
| `sale_order_state` | `Selection` | — | — | Related to `sale_order_id.state` |
| `task_to_invoice` | `Boolean` | `group_sale_salesman_all_leads` | — | Computed + SQL-searchable. True if linked SOL is billable but not yet invoiced. |
| `allow_billable` | `Boolean` | — | — | Related to `project_id.allow_billable` |
| `partner_id` | `Many2one` | — | — | Inverse on core task. Extended with `_compute_partner_id` to skip non-billable tasks. |
| `display_sale_order_button` | `Boolean` | — | — | Project-sharing portal field. True if current user can access the linked SO. |

#### `TASK_PORTAL_READABLE_FIELDS` — Portal Extension

```python
@property
def TASK_PORTAL_READABLE_FIELDS(self):
    return super().TASK_PORTAL_READABLE_FIELDS | {
        'allow_billable',
        'sale_order_id',
        'sale_line_id',
        'display_sale_order_button',
    }
```

This extension makes sale-related fields visible on task portal pages (via project sharing). Without this, portal users accessing shared tasks would see blank values for these fields.

#### `sale_line_id` Domain — `_domain_sale_line_id`

Combines three conditions with `Domain.AND`:

1. `_sellable_lines_domain()` — SO must be in a confirmed state.
2. `_domain_sale_line_service()` — SOL must be a service product.
3. Partner compatibility: `order_partner_id.commercial_partner_id` is parent_of `task.partner_id`, or `order_partner_id` equals `task.partner_id`.

The `parent_of` operator means any task whose partner is a descendant (contact/child) of the SOL's ordering partner is also eligible — critical for B2B hierarchies where the legal entity places the order but individual contacts log time.

#### `sale_line_id` Compute — `_compute_sale_line`

The cascade priority for auto-assigning a task's SOL:

```
1. Parent task's sale_line_id  (if parent partner matches task partner commercially)
2. Milestone's sale_line_id    (milestone-level SOL wins over project)
3. Project's sale_line_id      (project-level default)
4. Leave blank                 (non-billable)
```

This is a read-only compute; the actual write is through `_inverse_partner_id`.

#### `sale_order_id` Compute — `_compute_sale_order_id`

```python
if not allow_billable → False
else
    sale_order = sale_line_id.order_id
              or project_id.sale_order_id
              or project_id.reinvoiced_sale_order_id
              or existing sale_order_id
    if sale_order and not task.partner_id → auto-fill from sale_order.partner_id
    if task.partner_id.commercial_partner_id ∈ {commercial partners of so.partner_id, so.partner_invoice_id, so.partner_shipping_id}
        → assign sale_order
    else
        → False
```

The partner consistency check prevents linking a task assigned to Customer A to a SO for Customer B.

#### `_inverse_partner_id`

When a task's partner is changed, if the new partner is incompatible with the current `sale_order_id`, both `sale_order_id` and `sale_line_id` are cleared. This breaks the billing link rather than silently misrouting revenue.

#### `_check_sale_line_type` — `@api.constrains`

Raises `ValidationError` if an SOL is explicitly set on a task and that SOL is **not** a service (`is_service = False`) or **is** an expense (`is_expense = True`). This guards against mislinking re-invoiced expense lines. The check runs with `sudo()` because Project Managers may not have access to all SOLs.

#### `_ensure_sale_order_linked`

Used in `create()` and `write()`. After a task is created/updated with a `sale_line_id`, confirms any draft quotations among the SOL's orders. This handles the SO creation-from-project flow where the SO may not yet be confirmed when the task is saved.

---

### `project.project` — Extends `project.project`

**File:** `models/project_project.py`

This is the most complex extension. It turns a project into a billable container and wires all profitability and invoicing logic.

#### Fields Added

| Field | Type | Group | Notes |
|---|---|---|---|
| `allow_billable` | `Boolean` | — | Master switch for billable projects. Computed from `project_account`. |
| `sale_line_id` | `Many2one sale.order.line` | — | Default SOL for all tasks/timesheets. Compute+store, manual readonly=False. |
| `sale_order_id` | `Many2one sale.order` | — | Related to `sale_line_id.order_id` |
| `has_any_so_to_invoice` | `Boolean` | — | True if any linked SO has `invoice_status = 'to invoice'` |
| `has_any_so_with_nothing_to_invoice` | `Boolean` | — | True if any linked SO has `invoice_status = 'no'` |
| `sale_order_line_count` | `Integer` | `group_sale_salesman` | Count of SOLs linked to this project |
| `sale_order_count` | `Integer` | `group_sale_salesman` | Count of distinct confirmed SOs |
| `invoice_count` | `Integer` | `group_account_readonly` | Customer invoices via this project's analytic account |
| `vendor_bill_count` | `Integer` | `group_account_readonly` | Related to `account_id.vendor_bill_count` |
| `partner_id` | `Many2one` | — | Compute+store. Clears if `allow_billable = False` or company mismatch. |
| `display_sales_stat_buttons` | `Boolean` | — | True when billable and has a partner |
| `sale_order_state` | `Selection` | — | Related to `sale_order_id.state` |
| `reinvoiced_sale_order_id` | `Many2one sale.order` | `group_sale_salesman` | SO used for reinvoicing project costs. Separate from `sale_order_id` to support multiple SOs. |

#### `_get_projects_for_invoice_status` — Raw SQL

Used to determine which projects have SOs in a specific `invoice_status`. Runs a single raw SQL query against `project_project`, `sale_order`, and `project_task`:

```sql
SELECT pp.id FROM project_project pp
 WHERE pp.active = true
   AND (EXISTS (SELECT 1 FROM sale_order so
                 JOIN project_task pt ON pt.sale_order_id = so.id
                WHERE pt.project_id = pp.id AND pt.active = true
                  AND so.invoice_status = %s)
        OR EXISTS (SELECT 1 FROM sale_order so
                   JOIN sale_order_line sol ON sol.order_id = so.id
                  WHERE sol.id = pp.sale_line_id
                    AND so.invoice_status = %s))
   AND pp.id IN %s
```

This raw SQL via `execute_query` is significantly faster than ORM queries for this use case — the ORM equivalent would require multiple `search` + `read_group` calls per project. The query returns project IDs only (a list of integers), which are then used to set the boolean flags.

#### `_get_sale_order_items_query` — 4-Source UNION Query

The `sale_order_count` and profitability computations use a UNION query across four sources to find all SOLs linked to a project:

| Source | SQL Table | Condition |
|---|---|---|
| 1 | `project_project` | `sale_line_id IS NOT NULL` |
| 2 | `project_task` | `sale_line_id IS NOT NULL`, non-closed tasks (configurable) |
| 3 | `project_milestone` | `sale_line_id IS NOT NULL`, `allow_billable = True` |
| 4 | `sale_order_line` | `project_id` FK, or order is `reinvoiced_sale_order_id` |

The `sale_order_line` source uses `order_id = ANY(reinvoiced_sale_order_ids)` to catch SOLs on the reinvoiced SO even without a direct project FK. This is important for the reinvoicing flow where a vendor bill's cost lines map to the analytic account of the project, which maps to the reinvoiced SO.

#### Revenue Computation — `_get_revenues_items_from_sol`

Groups SOLs by product, distinguishes service from material via `service_policy`, maps to revenue sections:

| Service Policy | Revenue Section |
|---|---|
| `ordered_prepaid` | `service_revenues` |
| `delivered_milestones` | `service_revenues` |
| `delivered_manual` | `service_revenues` |
| Non-service product | `materials` |

Currency conversion is applied from each SOL's currency to the project's `company_id` currency. Downpayment SOLs are tracked separately with a negative `to_invoice` value (the advance was already invoiced, so the net is reversed out in profitability).

#### Invoice Item Injection — `_get_items_from_invoices`

Scans `account.move.line` for entries with this project's analytic distribution that are **not** already linked to SOL-generated invoices (avoids double-counting):
- `display_type = 'cogs'` lines → `cost_of_goods_sold`
- Other lines → `other_invoice_revenues`

Draft invoices contribute to `to_invoice`; posted invoices contribute to `invoiced`.

#### Profitability Sections — `_get_profitability_labels`

| Section ID | Label |
|---|---|
| `service_revenues` | Other Services |
| `materials` | Materials |
| `other_invoice_revenues` | Customer Invoices |
| `downpayments` | Down Payments |
| `cost_of_goods_sold` | Cost of Goods Sold |

---

### `project.milestone` — Extends `project.milestone`

**File:** `models/project_milestone.py`

#### Fields Added / Modified

| Field | Type | Notes |
|---|---|---|
| `allow_billable` | `Boolean` | Related to `project_id.allow_billable` |
| `project_partner_id` | `Many2one` | Related to `project_id.partner_id` |
| `sale_line_id` | `Many2one sale.order.line` | Domain filters to `qty_delivered_method = 'milestones'` and partner-compatible lines. Default via context or lookup from `project.sale_order_id`. |
| `quantity_percentage` | `Float` | Compute+store. `product_uom_qty / sale_line_id.product_uom_qty`. |
| `sale_line_display_name` | `Char` | Related to `sale_line_id.display_name` |
| `product_uom_id` | `Many2one` | Related to `sale_line_id.product_uom_id` |
| `product_uom_qty` | `Float` | Compute+store (readonly=False). If `quantity_percentage` is set: `percentage × sol.product_uom_qty`. Else: `sol.product_uom_qty`. Allows manual override with automatic percentage recalculation. |

---

### `sale.order` — Extends `sale.order`

**File:** `models/sale_order.py`

#### Fields Added

| Field | Type | Group | Notes |
|---|---|---|---|
| `tasks_ids` | `Many2many project.task` | `group_project_user` | All tasks linked via `sale_order_id` or `sale_line_id`. |
| `tasks_count` | `Integer` | `group_project_user` | |
| `closed_task_count` | `Integer` | `group_project_user` | Tasks in `CLOSED_STATES` |
| `completed_task_percentage` | `Float` | `group_project_user` | `closed_task_count / tasks_count` |
| `visible_project` | `Boolean` | — | True if any SOL has `service_tracking = 'task_in_project'` |
| `project_ids` | `Many2many project.project` | `group_project_user, group_project_milestone` | All projects linked (direct, via SOLs, via `reinvoiced_sale_order_id`) |
| `project_count` | `Integer` | `group_project_user` | Active project count |
| `milestone_count` | `Integer` | — | Sum of all milestones across SOLs |
| `is_product_milestone` | `Boolean` | — | True if any SOL has `service_policy = 'delivered_milestones'` |
| `show_create_project_button` | `Boolean` | `group_project_user` | Only for PM, on confirmed orders, with service lines but no project |
| `show_project_button` | `Boolean` | `group_project_user` | True when order is confirmed and has active projects |
| `project_id` | `Many2one project.project` | — | Pre-selected project for `task_in_project` SOLs. Domain: `allow_billable=True`, `is_template=False`. |
| `project_account_id` | `Many2one` | — | Related to `project_id.account_id` |

---

### `account.move` — Extends `account.move`

**File:** `models/account_move.py`

Single method: `_get_action_per_item()` returns the standard `action_move_out_invoice_type` action for every invoice. Allows the profitability dashboard to link invoice entries to the invoice form.

---

### `account.move.line` — Extends `account.move.line`

**File:** `models/account_move_line.py`

#### `_compute_analytic_distribution`

Protects project-generated analytic distributions from being overridden by analytic default rules:

```python
project_amls = self.filtered(lambda aml:
    aml.analytic_distribution
    and any(aml.sale_line_ids.project_id)
)
super(AccountMoveLine, self - project_amls)._compute_analytic_distribution()
# project_amls retain their distribution
```

Additionally, when `context.get('project_id')` is set (invoice being created from a project), all non-receivable/payable lines get the project's analytic distribution.

#### `_get_so_mapping_from_project` — Reinvoice Mapping

Maps analytic-account-labelled expense lines to the SO on which they should be reinvoiced:

```
for each AML with analytic_distribution:
    extract analytic accounts from distribution
    find a project whose single analytic account matches (last wins in loop)
    if project found and has linked SO:
        map[aml.id] = earliest-created confirmed SO  (prefer 'sale' state)
```

This enables the reinvoice vendor bills flow: vendor bill cost lines with project analytic accounts are matched to customer SOs.

---

### `product.template` — Extends `product.template`

**File:** `models/product_template.py`

#### Fields Added / Extended

| Field | Changes |
|---|---|
| `service_tracking` | Adds three new selection values: `task_global_project`, `task_in_project`, `project_only`. All three have `ondelete = 'set default'`. |
| `project_id` | Company-dependent; for `task_global_project` products only |
| `project_template_id` | Company-dependent; for `task_in_project` and `project_only` products |
| `task_template_id` | Company-dependent; domain restricted to `project_id` if set |
| `service_policy` | Extended with `'delivered_milestones'` option (conditionally shown when `project.group_project_milestone` feature is enabled) |
| `service_type` | Added `'milestones'` selection value |

---

### `sale.order.template.line` — Extends `sale.order.template.line`

**File:** `models/sale_order_template_line.py`

When generating an order line from a template (`_prepare_order_line_values`), if the context contains `default_task_id` and the product uses `task_in_project` or `task_global_project` tracking, the generated SOL's `task_id` is deliberately set to `False`. This prevents duplicate task creation: the task is generated via `_timesheet_service_generation` on SO confirmation, not pre-assigned from the template.

---

## L3: Cross-Module Integration, Override Patterns, and Failure Modes

### Cross-Module Integration

```
sale_management
  └── sale_order (sale.order, sale.order.line)
          └── sale_project extends sale.order.line
                  └── sale_order_line._timesheet_service_generation()
                          │
                          ├─→ project.project (creates if needed)
                          │       ├─→ project_project.sale_line_id (link)
                          │       ├─→ project_project.reinvoiced_sale_order_id (link)
                          │       └─→ project_task (creates if task_in_project)
                          │               └─→ project_task.sale_line_id (link)
                          │
                          └─→ project.milestone (creates for milestone policy)
                                  └─→ project_milestone.sale_line_id (link)

sale_project extends project.project
  └─→ project_project.sale_line_id (domain, compute, inverse)
  └─→ project_project._get_sale_order_items_query() (4-source UNION)
  └─→ project_project._compute_sale_order_count()
  └─→ project_project._compute_has_any_so_to_invoice()
  └─→ project_project.action_view_sos()

sale_project extends project.task
  └─→ project_task.sale_line_id (domain, compute, inverse)
  └─→ project_task.sale_order_id (compute)
  └─→ project_task._check_sale_line_type()

sale_project extends account_move_line
  └─→ account_move_line._compute_analytic_distribution()
          └─→ project_account_id._get_so_mapping_from_project()
                  └─→ maps vendor bill AMLs → customer SO for reinvoicing
```

### Override Patterns

`sale_project` uses three override patterns:

1. **Field shadowing (adding to selection):** `qty_delivered_method` extends the parent's selection with `'milestones'`.
2. **Method pre/post-pend:** `_compute_qty_delivered_method`, `_compute_analytic_distribution`, `_timesheet_service_generation` — delegates to super for non-matching records and handles the special case itself.
3. **Full override with super call:** `create()`, `write()`, `_compute_sale_line` — calls super and then applies sale_project-specific logic.

### Workflow Trigger: SO Confirmation → Project/Task Creation

The trigger is in `sale_order.py`:

```python
# sale_order.py — _action_confirm() in sale_project context
if len(self.company_id) == 1:
    self.order_line.sudo().with_company(self.company_id)._timesheet_service_generation()
else:
    for order in self:
        order.order_line.sudo().with_company(order.company_id)._timesheet_service_generation()
```

- Runs as `sudo()` so salespeople without project access can still trigger generation.
- `with_company()` ensures multi-company correctly scopes project/template lookups.
- Called only on confirmation, not on draft edits.

### Failure Modes

| Scenario | Behavior | Error Type |
|---|---|---|
| `task_global_project` SOL confirmed with no product-level project and no SO-level `project_id` | `UserError` raised inside `_timesheet_service_generation()` with product name and SO name | `UserError` |
| Template project `action_create_from_template()` fails | Exception propagates; SOL remains unlinked; transaction rolls back | Any |
| SOL creates project but post-init hook fails (e.g., stage creation) | Project created but without default stages; SOL `project_id` set; minor degradation | Silent |
| Product has `project_template_id` but template has no tasks | Project created with no tasks; milestone provisioned on project; no task for SOL | Silent |
| Duplicate project attempt (same template, same SO) | `_can_create_project()` check prevents duplicate; existing project reused | Silent |
| SO cancelled after project/task created | `sale.order.write()` clears `sale_line_id` on projects but does not delete them | Silent |
| Locked SO — `product_uom_qty` change blocked by `sale.lock` | Write on SOL blocked at ORM level; `_timesheet_service_generation()` not called | ORM raises |
| Project's `sale_line_id` SOL cancelled | Project loses billing link; existing tasks remain; `qty_delivered` unchanged | Silent |
| Milestone without `is_reached` set | Does not contribute to `qty_delivered` | Silent |
| Zero-qty SOL with `service_tracking` | `_timesheet_service_generation()` skips via `_is_line_optional()` check | Silent |
| `is_expense` SOL | `_timesheet_service_generation()` skips all SOLs where `is_expense = True` | Silent |

---

## L4: Performance, Version Changes Odoo 18 → 19, Security, and Project Sharing with Portal

### Performance Considerations

#### `_get_projects_for_invoice_status` — Raw SQL vs ORM

Uses raw SQL via `execute_query` for speed. The ORM equivalent (`search + read_group` on projects x tasks x SOs) would generate ~3 joins per project with multiple round-trips. This raw query fetches all matching project IDs in one round-trip:

```python
result = self.env.execute_query(SQL("""
    SELECT id FROM project_project pp
     WHERE pp.active = true
       AND (EXISTS (...) OR EXISTS (...))
       AND id IN %(ids)s""",
    ids=tuple(self.ids),
    invoice_status=invoice_status
))
return self.env['project.project'].browse(id_ for id_, in result)
```

The SQL query uses `EXISTS` subqueries which are optimizable by PostgreSQL to stop at the first match. This is the fastest path for the invoice status indicators on the project kanban card.

#### `_fetch_sale_order_items_query` — UNION with Limit/Offset

The 4-source UNION query supports `limit` and `offset` for pagination. For single-project calls, it bypasses the UNION and uses a direct `_fetch_sale_order_items()`. For bulk operations (e.g., `sale_order_count` on a kanban with 50 projects), the UNION runs in a single SQL statement:

```python
if len(self) == 1:
    return {self.id: self._fetch_sale_order_items(domain_per_model)}
# Otherwise: single UNION query across all projects
```

#### `analytic_distribution` Cascade

The `_compute_analytic_distribution` method appends project accounts to existing distributions rather than replacing them. This avoids rebuilding the entire distribution dict when SOLs already have multi-account distributions from a sales team policy.

#### `sudo()` Usage

Project/task generation runs as `sudo()` inside `_timesheet_service_generation()` because a salesperson may confirm an SO without having `project.group_project_user` access. However, `_fetch_sale_order_items()` explicitly filters to `allow_billable = True` projects, so non-billable projects are excluded from all billing aggregations regardless of sudo.

#### Milestone Read Group

The `_prepare_qty_delivered()` uses a single `_read_group` call to aggregate all reached milestones across all SOLs in one query, rather than iterating per SOL:

```python
project_milestone_read_group = self.env['project.milestone']._read_group(
    [('sale_line_id', 'in', lines_by_milestones.ids), ('is_reached', '=', True)],
    ['sale_line_id'],
    ['quantity_percentage:sum'],
)
# One SQL query for all milestone SOLs
reached_milestones_per_sol = {sale_line.id: percentage_sum ...}
for line in lines_by_milestones:
    delivered_qties[line] = reached_milestones_per_sol.get(sol_id, 0.0) * product_uom_qty
```

---

### Odoo 18 → 19 Changes

| Area | Change |
|---|---|
| **Milestone delivery** | `quantity_percentage` field added. `_prepare_qty_delivered` now uses read group aggregation instead of a naive sum, correctly handling multiple milestones per SOL. |
| **SO → Project linkage** | `reinvoiced_sale_order_id` formalized as a separate field from `sale_order_id`. Previously the same SO was used for both billing and reinvoicing. |
| **`_domain_sale_line_id`** | Now uses the `Domain` class with `unquote()` for proper domain interpolation rather than string formatting. |
| **Profitability** | `_get_items_from_invoices` correctly routes `display_type = 'cogs'` lines to `cost_of_goods_sold` instead of `other_invoice_revenues`. |
| **`project_task_type`** | `show_rating_active` compute added; rating activation on stages is conditional on `allow_billable`. |
| **`_timesheet_service_generation`** | Idempotency improved: existing `task_id` and `project_id` are respected rather than regenerated, fixing double-task creation on draft→confirm→cancel→confirm cycles. |
| **`_fetch_sale_order_items_query`** | 4-source UNION now correctly includes SOLs whose order is the `reinvoiced_sale_order_id` even without a direct project FK. |
| **`project_milestone`** | `product_uom_qty` is now a compute (readonly=False) derived from `quantity_percentage × sol.product_uom_qty`, allowing manual override with automatic percentage recalculation. |
| **Portal/sharing** | `display_sale_order_button` and `TASK_PORTAL_READABLE_FIELDS` extension added for project sharing portal access. |

---

### Security Model

#### Record Rules (`ir.rule`)

| Rule | Model | Groups | Access |
|---|---|---|---|
| Project Manager SOL Read | `sale.order.line` | `project.group_project_manager` | Read only (no write/unlink/create) |

Domain: `(state = 'sale') AND (is_service = True) AND (project_id IS NOT FALSE OR task_id IS NOT FALSE)`

Gives Project Managers read access to service SOLs that have generated a project or task, without granting access to all SOLs.

#### Access Control (`ir.model.access.csv`)

| ID | Model | Group | R | W | C | D |
|---|---|---|---|---|---|---|
| `sale_order_line_project_manager` | `sale.order.line` | `project.group_project_manager` | 1 | 0 | 0 | 0 |
| `sale_order_project_manager` | `sale.order` | `project.group_project_manager` | 1 | 0 | 0 | 0 |
| `sale_order_project_user` | `sale.order` | `project.group_project_user` | 1 | 0 | 0 | 0 |
| `sale_order_line_project_user` | `sale.order.line` | `project.group_project_user` | 1 | 0 | 0 | 0 |

All write/create/delete access is denied for both groups. Salespeople cannot modify SOLs even if they can confirm SOs.

#### Partner Isolation

The partner compatibility checks in `_compute_sale_line`, `_compute_sale_order_id`, and `_inverse_partner_id` ensure that tasks cannot be billed to SOs for different commercial partners. This prevents revenue misattribution in multi-subsidiary or multi-contact hierarchies.

#### ACL Bypass via `sudo()`

The `sudo()` call in `_timesheet_service_generation()` is a deliberate security trade-off:
- It allows non-project users (salespeople) to trigger project creation
- It does **not** bypass `ir.rule` — the SOL's own ACL rules still apply
- The projects created are accessible because they are linked to the SO (which the salesperson owns)

---

### Project Sharing with Portal

When a project is shared with a portal user (via `project.collaborator` or `privacy_visibility = 'portal'`), the portal user gains access to the project and its tasks. The `sale_project` module enhances this experience:

#### `display_sale_order_button` — Portal Button Visibility

```python
@api.depends('sale_order_id')
def _compute_display_sale_order_button(self):
    if not self.sale_order_id:
        self.display_sale_order_button = False
        return
    try:
        sale_orders = self.env['sale.order'].search([('id', 'in', self.sale_order_id.ids)])
        for task in self:
            task.display_sale_order_button = task.sale_order_id in sale_orders
    except AccessError:
        self.display_sale_order_button = False
```

This compute:
1. Checks if the portal user can actually access the linked `sale_order_id`
2. Sets `display_sale_order_button = False` silently if access denied (no error shown to portal user)
3. The portal template then conditionally renders the "View Sales Order" button

#### `TASK_PORTAL_READABLE_FIELDS` — Sale Fields in Portal

```python
@property
def TASK_PORTAL_READABLE_FIELDS(self):
    return super().TASK_PORTAL_READABLE_FIELDS | {
        'allow_billable',
        'sale_order_id',
        'sale_line_id',
        'display_sale_order_button',
    }
```

Without this extension, portal users accessing shared tasks would see blank/null values for sale-related fields even though the data exists in the database. This property adds those fields to the list of fields included in the portal task JSON response.

#### How Project Sharing Works End-to-End

```
1. Project Manager sets privacy_visibility = 'portal'
      OR adds collaborator record for a partner

2. Portal user accesses /my/project/<id>
      ├─→ project_project.with_access(portal_user).read([...])
      │       └─→ Record rules filter to accessible projects
      │
      └─→ project_task.with_access(portal_user).read([...])
              ├─→ tasks filtered by project access
              ├─→ sale_order_id.read() → checks sale_order ACL
              │       └─→ if portal user has access to SO partner:
              │               display_sale_order_button = True
              │           else:
              │               display_sale_order_button = False
              │
              └─→ TASK_PORTAL_READABLE_FIELDS includes sale fields
                      └─→ sale_order_id, sale_line_id appear in JSON
                              └─→ Portal template renders sale info
```

---

## Service Tracking Modes

| `service_tracking` | Creates | Default `allow_billable` | `project_id` source |
|---|---|---|---|
| `no` | Nothing | unchanged | none |
| `task_global_project` | Task only | unchanged | `product_id.project_id` (pre-configured) |
| `task_in_project` | Project + Task | `True` | New per-SO project (or `order_id.project_id`) |
| `project_only` | Project only | `True` | New per-SO project |

| `service_policy` | Delivery method | Invoice trigger |
|---|---|---|
| `ordered_prepaid` | Prepaid (ordered qty) | At SO confirmation |
| `delivered_manual` | Manual delivery entry | When delivery is validated |
| `delivered_milestones` | Milestone completion | When milestone is marked reached |

---

## Workflow Summary

```
SO Confirmation (sale.order._action_confirm)
    │
    ├─→ sale.order.line._timesheet_service_generation()
    │       │
    │       ├─→ project_only / task_in_project
    │       │       ├─→ _timesheet_create_project()
    │       │       │       ├─→ with template → action_create_from_template() or copy()
    │       │       │       │       └─→ write sale_line_id, partner_id on all tasks
    │       │       │       └─→ without template → project.create() + default stages
    │       │       │       └─→ project.reinvoiced_sale_order_id = order
    │       │       │       └─→ sol.project_id = project
    │       │       │       └─→ _handle_milestones()
    │       │       │               └─→ enable allow_milestones if needed
    │       │       │               └─→ auto-assign orphan milestones or create new one
    │       │       │
    │       │       └─→ task_in_project only
    │       │               └─→ _timesheet_create_task()
    │       │                       └─→ with task_template → action_create_from_template()
    │       │                       └─→ without → task.sudo().create()
    │       │                               allocated_hours = product_uom_qty (non-milestone)
    │       │                               sale_line_id = sol
    │       │                               sale_order_id = order
    │       │
    │       └─→ task_global_project
    │               └─→ _timesheet_create_task() in product_id.project_id
    │                       (UserError if no global project configured)
    │
    └─→ Invoice Creation
            sale.order._create_invoices()
                └─→ sale.order.line._prepare_invoice_line()
                        └─→ analytic_distribution fallback:
                              task.project_id.account_id
                           or project_id.account_id
                           or project with sale_line_id match
```

---

## Hooks

### `_set_allow_billable_in_project` (post-init)

```
Projects to mark billable =
    Projects returned by _get_projects_to_make_billable_domain()
  + Projects of tasks in _get_projects_to_make_billable_domain
    (where project itself is NOT in the above set)
```

This ensures that projects become billable automatically if any of their tasks have a `sale_line_id`. Used when installing `sale_project` on an existing database.

### `uninstall_hook`

Removes `ir.embedded.actions` records whose `python_method` is `action_open_project_invoices` or `action_view_sos`, replacing their domain with `(0, '=', 1)` (always-false), effectively hiding the embedded action buttons without deleting related records.

---

## Key Edge Cases

1. **Sub-task partner mismatch**: If a sub-task's `partner_id` differs commercially from the parent's `sale_line_id`'s order partner, the sub-task's `sale_line_id` is left blank rather than incorrectly inheriting.

2. **Milestone with 0% reached**: A milestone with `quantity_percentage = 0` does not contribute to `qty_delivered`. Such milestones may exist temporarily during milestone setup.

3. **SO cancellation**: Cancelling an SO clears `sale_line_id` on projects but does **not** delete projects or tasks. Tasks remain for record-keeping; they lose their billing link.

4. **Project template copy**: When copying a template project, sub-tasks lose their `sale_line_id` during the standard `copy()`. The post-copy `write()` explicitly fixes this by setting `sale_line_id` and `sale_order_id` on all sub-tasks.

5. **Multi-company**: SOLs confirmed in different companies use `with_company()` per-order inside `_action_confirm()`. Project creation respects `product_id.project_template_id.company_id` alignment.

6. **Zero qty SOLs**: `service_tracking` is only applied if the SOL has `product_uom_qty > 0` or is not an optional line. Zero-qty lines do not generate tasks.

7. **Global project not set**: If a `task_global_project` SOL is confirmed without a global project on the product AND without an SO-level `project_id`, a `UserError` is raised rather than silently skipping task creation.

8. **Expense lines**: Re-invoiced expense SOLs cannot be manually linked to tasks (`_check_sale_line_type` raises `ValidationError`). The expense billing flow uses a different mechanism.

9. **Project template with no tasks**: If a project template is converted but has no task templates, the project is created with no tasks. The SOL is linked to the project but no task is generated.

---

## Related Documentation

- [Modules/Project](Modules/project.md)
- [Modules/sale_management](Modules/sale_management.md)
- [Modules/sale_service](Modules/sale_service.md)
- [Modules/sale_timesheet](Modules/sale_timesheet.md) — Timesheet-linked billing, UDH conversion, SOL→AAL→invoice flow
- [Modules/hr_timesheet](Modules/hr_timesheet.md) — Timesheet entry model, portal rendering
- [Core/API](Core/API.md)
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md)
- [Patterns/Security Patterns](Patterns/Security Patterns.md)
