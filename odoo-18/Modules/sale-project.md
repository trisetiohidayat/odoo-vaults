---
Module: sale_project
Version: Odoo 18
Type: Integration
---

# Sale - Project (`sale_project`)

Links sale orders to project management. Automatically creates `project.project` and `project.task` records when service products are confirmed on a sale order. Handles milestone-based delivery tracking and profitability reporting from the project dashboard.

**Depends:** `sale_management`, `sale_service`, `project_account`
**Category:** Hidden
**Source:** `~/odoo/odoo18/odoo/addons/sale_project/`

---

## Models

### `sale.order` (EXTENDED)

Inherits from `sale.order`. Adds computed fields for project/task visibility and action buttons.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `tasks_ids` | Many2many | Computed tasks linked to this SO (via `sale_line_id` or `sale_order_id`) |
| `tasks_count` | Integer | Count of tasks (computed) |
| `closed_task_count` | Integer | Count of closed/cancelled tasks |
| `completed_task_percentage` | Float | Ratio of closed to total tasks |
| `project_ids` | Many2many | All projects linked to SOLs or directly (computed) |
| `project_count` | Integer | Count of active linked projects |
| `visible_project` | Boolean | True if any SOL has `service_tracking == 'task_in_project'` |
| `show_project_button` | Boolean | Show "View Project" button (computed) |
| `show_create_project_button` | Boolean | Show "Create Project" button (computed) |
| `show_task_button` | Boolean | Show "View Tasks" button (computed) |
| `milestone_count` | Integer | Count of milestones across all SOLs |
| `is_product_milestone` | Boolean | Any SOL uses milestone-based service policy |
| `project_id` | Many2one | Default project for `task_in_project` SOLs |
| `project_account_id` | Many2one | Related analytic account from project |
| `project_count` | Integer | Number of linked projects |

#### Key Methods

**`_action_confirm()`** — Overrides parent. Calls `_timesheet_service_generation()` on all SOLs when SO is confirmed. Single-company case is batched; multi-company iterates per order.

**`_compute_tasks_ids()`** — Uses `_read_group` to collect tasks grouped by `sale_order_id` and `state`. Tasks without `sale_order_id` are attributed from their `sale_line_id.order_id`. Increments `closed_task_count` for tasks in `CLOSED_STATES`.

**`_compute_project_ids()`** — Gathers projects from: SOL `product_id.project_id`, SOL `project_id`, and direct `sale_order_id` on projects. Filters by ACL unless user is project manager.

**`action_create_project()`** — Opens the project creation wizard with context set: `default_sale_order_id`, `default_sale_line_id`, `default_partner_id`, `default_allow_billable=1`, `default_company_id`. Sets `generate_milestone=True` if the default SOL product uses `delivered_milestones` policy.

**`action_view_task()`** — Returns action to open task list/form. If all tasks are in one project, uses `act_project_project_2_project_task_all` with the project as active ID. Sets default context: `default_sale_order_id`, `default_sale_line_id`, `default_partner_id`, `default_project_id`, `default_user_ids=[uid]`.

**`action_view_project_ids()`** — Opens the project kanban/list view filtered to projects linked to this SO (direct `sale_order_id` or via `project_ids`).

**`action_view_milestone()`** — Opens milestone list view for all SOLs on this order.

**`write(values)`** — If state changes to `cancel`, clears `sale_line_id` from all projects linked to this SO via `sudo()`.

#### L4 Notes

- Projects are linked via `project.sale_order_id` OR via the project's SOL (`project.sale_line_id`). Both paths are tracked.
- When a user manually creates a project from the SO, the project is created with `sale_order_id` set via the context (`create_for_project_id`).
- Tasks are attributed to the SO via two mechanisms: directly via `task.sale_order_id`, or indirectly via `task.sale_line_id.order_id`. The `_compute_tasks_ids` method handles both.

---

### `sale.order.line` (EXTENDED)

Inherits from `sale.order.line`. The central model for SOL-to-project/task generation. Handles service tracking modes and milestone delivery.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | Many2one | Generated project for this SOL |
| `task_id` | Many2one | Generated task for this SOL |
| `reached_milestones_ids` | One2many | Milestones linked to this SOL where `is_reached=True` |
| `qty_delivered_method` | Selection | Added value: `'milestones'` for milestone-based delivery |

#### Key Methods

**`_timesheet_service_generation()`** — The core generation method. Called on SO confirmation. Handles three `service_tracking` modes:

1. **`task_global_project`** (Task) — Looks up `product_id.project_id` per SOL, creates a task in that project. If no project found, uses `so_line.order_id.project_id`. Raises `UserError` if neither exists.

2. **`task_in_project`** (Project & Task) — Creates a new project if none exists for the SO. A task is then created in that project. Multiple SOLs with `task_in_project` share the same project (one project per SO). If a project template is set on the product, the project is duplicated from the template.

3. **`project_only`** (Project) — Creates the project but does NOT create a task. The project is still billable via its `sale_line_id`.

**`_timesheet_create_project_prepare_values()`** — Returns dict for project creation:
- `name`: `${client_order_ref} - ${SO.name}` or just `${SO.name}`
- `account_id`: from context `project_account_id` or `order_id.project_account_id` or newly created analytic account
- `partner_id`: from SO partner
- `sale_line_id`: `self.id` (links project to this SOL)
- `company_id`, `active`, `allow_billable`: `True`
- `user_id`: from product's `project_template_id.user_id`

**`_timesheet_create_project()`** — Creates the project. If `project_template_id` is set, duplicates the template and writes `sale_line_id`/`partner_id` on all tasks (including sub-tasks). If no template and only one `project_only`/`task_in_project` SOL on the SO, appends the product's default code and name to the project name. Writes `project_id` and `reinvoiced_sale_order_id` back to the SOL.

**`_timesheet_create_task_prepare_values(project)`** — Returns task vals dict:
- `name`: product name or custom SOL description (first line of `name` field)
- `allocated_hours`: `product_uom_qty` unless `service_type` is `'milestones'` or `'manual'` (then 0)
- `partner_id`, `description`, `project_id`, `sale_line_id`, `sale_order_id`, `company_id`

**`_timesheet_create_task(project)`** — Creates task via `sudo()` and writes `task_id` back to SOL. Posts a message on the task referencing the SO.

**`_handle_milestones(project)`** — If `service_policy == 'delivered_milestones'`:
- If project already has milestones without a `sale_line_id`, assigns this SOL to those milestones, splitting `product_uom_qty` across them
- Otherwise, creates a new milestone with `quantity_percentage=1` and links it to this SOL
- If `service_tracking == 'task_in_project'`, assigns the milestone to the generated task

**`_compute_qty_delivered`** — For milestone-delivered SOLs: `qty_delivered = sum(reached_milestones.quantity_percentage) * product_uom_qty`. Each milestone's `quantity_percentage` is computed as `milestone.product_uom_qty / sol.product_uom_qty`.

**`_prepare_invoice_line(...)`** — If no analytic distribution on the SOL or its project, falls back to the analytic account from the task's project, the SOL's own project, or any project where this SOL appears on the project's SOL or task.

#### L4 Notes

- The project is shared per SO (one project for all `task_in_project`/`project_only` SOLs in the same SO). The sharing is tracked in `map_so_project`.
- When a product has `project_template_id`, each SOL with that template gets its own project duplicated from the template.
- When a SO is confirmed, `_timesheet_service_generation` is called. But if the SO was previously confirmed, cancelled, and re-confirmed, existing projects/tasks are reused (search on `sale_line_id` prevents duplicate creation).
- `reached_milestones_ids` is a filtered O2M (`domain=[('is_reached', '=', True)]`), so only reached milestones appear.

---

### `project.project` (EXTENDED)

Inherits from `project.project`. Extends with sale-order linkage, profitability reporting, and invoice/stat buttons.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `allow_billable` | Boolean | Billable flag (no longer computed, directly stored) |
| `sale_line_id` | Many2one | Default SOL for tasks/timesheets in this project |
| `sale_order_id` | Many2one | Related SO (computed from `sale_line_id`) |
| `has_any_so_to_invoice` | Boolean | Any linked SO has `invoice_status='to invoice'` |
| `has_any_so_with_nothing_to_invoice` | Boolean | Any linked SO has `invoice_status='no'` |
| `sale_order_count` | Integer | Count of distinct SOs linked |
| `sale_order_line_count` | Integer | Count of SOLs linked |
| `invoice_count` | Integer | Customer invoices via analytic distribution |
| `vendor_bill_count` | Integer | Vendor bills via analytic distribution (related) |
| `partner_id` | Many2one | Computed: SO partner, writable only when `allow_billable=True` |
| `display_sales_stat_buttons` | Boolean | Show stat buttons (computed) |
| `reinvoiced_sale_order_id` | Many2one | SO used for stock picking reinvoice |

#### Key Methods

**`_fetch_sale_order_items(domain_per_model=None)`** — Returns all SOLs linked to this project via: project itself, tasks in the project, milestones on the project, or SOLs directly assigned to the project's `account_id`.

**`_get_sale_order_items_query(domain_per_model=None)`** — Builds a SQL query using `UNION ALL` across four sources: `project_project` (via `sale_line_id`), `project_task` (via `sale_line_id`), `project_milestone` (via `sale_line_id`), and `sale_order_line` (via `project_id`). Applies IR rules per model.

**`_get_revenues_items_from_sol(domain=None, with_action=True)`** — Computes profitability revenue data from SOLs. Groups SOLs by currency/product, converts to project currency, classifies into sections: `service_revenues`, `materials`, `downpayments`. For each section, computes `to_invoice` and `invoiced` amounts. Uses `service_policy` to determine invoice type (`ordered_prepaid` → `service_revenues`, `delivered_milestones` → `service_revenues`, etc.).

**`_get_revenues_items_from_invoices(...)`** — Computes revenue and COGS data from posted/draft invoices with analytic distribution matching this project. Distinguishes `other_invoice_revenues` (from regular invoices) and `cost_of_goods_sold` (from `display_type='cogs'` lines).

**`_get_profitability_items(with_action=True)`** — Combines SOL revenue data + invoice data + purchase data into a single profitability dict. Used by the project dashboard.

**`action_create_invoice()`** — Opens the advance payment invoice wizard with pre-filtered SOs that have `invoice_status in ['to invoice', 'no']`.

**`_ensure_sale_order_linked(sol_ids)`** — Confirms draft SOs linked to newly created projects/tasks. Called on project/task `create` and `write`.

#### L4 Notes

- `sale_line_id` is the default SOL for all tasks in the project. Individual tasks can override with their own `sale_line_id`.
- The profitability panel shows four revenue sections: `service_revenues`, `materials`, `other_invoice_revenues`, `downpayments`.
- `reinvoiced_sale_order_id` enables automatic reinvoicing of stock moves (from `stock_picking` configured with analytic costs) to the selected SO.
- `account_id` on the project is the analytic account. All SOLs and tasks in the project inherit the same analytic distribution unless explicitly overridden.

---

### `project.task` (EXTENDED)

Inherits from `project.task`. Links tasks to sale order lines for time tracking and billing.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `sale_order_id` | Many2one | Computed SO for this task (not stored directly) |
| `sale_line_id` | Many2one | SOL to which timesheet hours are billed |
| `project_sale_order_id` | Many2one | Related: `project_id.sale_order_id` |
| `sale_order_state` | Selection | Related state of the linked SO |
| `task_to_invoice` | Boolean | Computed: SO has `invoice_status not in ('no', 'invoiced')` |
| `allow_billable` | Boolean | Related from `project_id` |
| `display_sale_order_button` | Boolean | Portal users can see the SO button |

#### Key Methods

**`_compute_sale_line()`** — Determines the task's `sale_line_id`. Priority: parent task's SOL (if same commercial partner), milestone's SOL, project's `sale_line_id` (if same commercial partner). Only active when `allow_billable=True`.

**`_compute_sale_order_id()`** — Sets `partner_id` if `sale_line_id` has a partner. Validates that `partner_id.commercial_partner_id` matches the SO's commercial partner chain. If not consistent, sets `sale_order_id = False`.

**`_inverse_partner_id()`** — If the partner is changed to an inconsistent one, clears both `sale_order_id` and `sale_line_id`.

**`_check_sale_line_type()`** — Constrains `sale_line_id` to service lines that are NOT re-invoiced expenses. Raises `ValidationError` if violated.

**`_ensure_sale_order_linked(sol_ids)`** — Confirms draft SOs when a task is created/written with a `sale_line_id`.

#### L4 Notes

- `sale_line_id` is used by `sale_timesheet` to track hours and by `sale_lot` for milestone billing.
- The `_domain_sale_line_id()` method uses `sale_line_id` with commercial partner matching via `parent_of` operator.
- When a SOL is confirmed, the tasks are created. The tasks' `sale_order_id` is then set and validated for partner consistency.

---

### `product.template` (EXTENDED)

Extends `product.template` with three new `service_tracking` modes.

#### New Fields / Extended Fields

| Field | Type | Description |
|-------|------|-------------|
| `service_tracking` | Selection | Extended with: `task_global_project`, `task_in_project`, `project_only` |
| `project_id` | Many2one | Fixed project for `task_global_project` mode |
| `project_template_id` | Many2one | Template project for `task_in_project`/`project_only` modes |
| `service_policy` | Selection | Computed from `invoice_policy` + `service_type`. Added: `delivered_milestones` |
| `service_type` | Selection | Extended with: `milestones` |

#### Service Tracking Modes

| Value | Behavior |
|-------|----------|
| `no` | No project/task created. Product cannot have `project_id` or `project_template_id`. |
| `task_global_project` | Creates a task in `product_id.project_id`. Cannot have a `project_template_id`. |
| `task_in_project` | Creates a project (from template if set, or new) + a task per SOL. Cannot have a `project_id`. |
| `project_only` | Creates a project but no task. Cannot have a `project_id`. |

#### Service Policy Mapping

| `service_policy` | `invoice_policy` | `service_type` |
|-----------------|-----------------|---------------|
| `ordered_prepaid` | `order` | `manual` |
| `delivered_milestones` | `delivery` | `milestones` |
| `delivered_manual` | `delivery` | `manual` |

#### L4 Notes

- When `type` is changed to non-service, `service_tracking` is forced to `'no'` and `project_id` is cleared.
- The `_check_project_and_template` constraint validates that incompatible tracking/project/template combinations are rejected.
- `_inverse_service_policy()` writes back to `invoice_policy` and `service_type` when `service_policy` is changed.
- `_selection_service_policy()` conditionally adds `delivered_milestones` only if `project.group_project_milestone` is installed.

---

### `product.product` (EXTENDED)

#### Key Methods

**`_onchange_service_tracking()`** — Clears `project_id` and `project_template_id` when switching to incompatible tracking modes.

**`write(vals)`** — If `type` changes away from `'service'`, clears `service_tracking` and `project_id`.

---

### `project.milestone` (EXTENDED)

Inherits from `project.milestone`. Links milestones to SOLs for milestone-based service delivery.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `allow_billable` | Boolean | Related from `project_id` |
| `project_partner_id` | Many2one | Related from `project_id.partner_id` |
| `sale_line_id` | Many2one | SOL that this milestone updates when reached |
| `quantity_percentage` | Float | `product_uom_qty / sol.product_uom_qty` (stored) |
| `sale_line_display_name` | Char | Display name of linked SOL |
| `product_uom` | Many2one | Related from `sale_line_id.product_uom` |
| `product_uom_qty` | Float | Computed: `quantity_percentage * sol.product_uom_qty` |

#### L4 Notes

- When a milestone's `is_reached` is set to `True`, the SOL's `qty_delivered` is automatically updated via `_compute_qty_delivered` on `sale.order.line`.
- Multiple milestones can map to the same SOL (splitting the quantity).
- `action_view_sale_order()` opens the SOL's sale order.

---

### `account.move` (EXTENDED)

#### Methods

**`_get_action_per_item()`** — Returns the action to view the invoice for each move (used in project profitability panel to open invoices).

---

### `account.move.line` (EXTENDED)

#### Key Methods

**`_compute_analytic_distribution()`** — When a project creates an AML (with context `project_id`), it applies the project's analytic distribution to the AMLs (excluding receivable/payable lines).

**`_get_so_mapping_from_project()`** — Maps AMLs to SOs based on analytic distribution matching the project's analytic account. Uses root plan IDs from the distribution. Returns the oldest SO in `'sale'` state, or oldest draft SO if none are confirmed.

**`_sale_determine_order()`** — Combines mapping from analytic distribution (parent module) with project-based mapping. Project mapping overrides.

---

## Flow: SOL to Project/Task Generation

```
SO Confirmed (sale.order._action_confirm)
  └─ sale.order.line._timesheet_service_generation()
       │
       ├─ service_tracking == 'task_global_project'
       │    └─ _timesheet_create_task(product_id.project_id)
       │         └─ writes task_id back to SOL
       │
       ├─ service_tracking == 'task_in_project'
       │    ├─ _timesheet_create_project() [shared per SO]
       │    │    ├─ No template → project with name from SO
       │    │    └─ Has template → duplicate template project
       │    └─ _timesheet_create_task(project)
       │         └─ writes task_id + project_id back to SOL
       │
       └─ service_tracking == 'project_only'
            └─ _timesheet_create_project() [shared per SO]
                 └─ writes project_id back to SOL
```

---

## Security

The module defines ACLs in `sale_project_security.xml`. Key rules:
- `sale_project.project_user`: Read/write on SOL project/task fields
- Milestone access requires `project.group_project_milestone`

## Hooks

**`_set_allow_billable_in_project`** (post-init): Sets `allow_billable=True` on existing projects that have a `sale_line_id`.

**`uninstall_hook`**: Cleans up the `allow_billable` flag and milestone SOL links.

---

**Tags:** `#sale_project` `#service_tracking` `#project_generation` `#milestones` `#profitability`
