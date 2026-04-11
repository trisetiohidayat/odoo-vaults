# sale_project - Sales - Project

**Module:** `sale_project`
**Depends:** `sale_management`, `sale_service`, `project_account`
**Auto-install:** `sale_management`, `project_account`
**Category:** Hidden

---

## Purpose

Links sale orders with project management. Enables automatic creation of projects and tasks from sale order lines containing service products. Tracks milestones, billable project settings, and analytic distribution from SO to generated project. Provides full visibility of project/task status from within the sale order.

---

## sale.order Extension

**File:** `models/sale_order.py`

| Field | Type | Description |
|---|---|---|
| `tasks_ids` | `Many2many` | Tasks linked to this SO (via search, computed) |
| `tasks_count` | `Integer` | Count of tasks |
| `closed_task_count` | `Integer` | Tasks in closed state |
| `completed_task_percentage` | `Float` | `closed_task_count / tasks_count` |
| `visible_project` | `Boolean` | Show project_id field if any SOL has task_in_project service_tracking |
| `project_ids` | `Many2many` | Projects linked to this SO (via sale_order_id or SOL project) |
| `project_count` | `Integer` | Number of projects |
| `milestone_count` | `Integer` | Count of milestones across all SOLs |
| `is_product_milestone` | `Boolean` | True if any SOL has delivered_milestones policy |
| `show_create_project_button` | `Boolean` | Show "Create Project" button |
| `show_project_button` | `Boolean` | Show "Project" smart button |
| `show_task_button` | `Boolean` | Show "Tasks" smart button |
| `project_id` | `Many2one` | Manually linked project (domain: allow_billable=True) |
| `project_account_id` | `Many2one` | Analytic account from linked project |

**Task Computation:**

```python
def _compute_tasks_ids(self):
    # Groups tasks by sale_order_id + state via read_group
    # Tasks without sale_order_id are linked via their sale_line_id.order_id
    # closed_task_count increments for tasks in CLOSED_STATES
```

**Project Computation:**

- Reads projects with `sale_order_id` in self.ids
- Also includes `order_line.product_id.project_id` and `order_line.project_id`
- `project_count` only counts active projects

**SO Confirmation:** `_action_confirm()` calls `_timesheet_service_generation()` on order lines to create tasks/projects.

**Key Actions:**

- `action_view_task()` - Opens task list/kanban/form (cross-project kanban if >1 project)
- `action_create_project()` - Opens `project.open_create_project` with SO context
- `action_view_project_ids()` - Kanban/list of linked projects
- `action_view_milestone()` - Opens milestone list filtered to this SO's SOLs

---

## sale.order.line Extension

**File:** `models/sale_order_line.py`

| Field | Type | Description |
|---|---|---|
| `qty_delivered_method` | `Selection` | Added `'milestones'` option |
| `project_id` | `Many2one` | Generated project (indexed, copy=False) |
| `task_id` | `Many2one` | Generated task (indexed, copy=False) |
| `reached_milestones_ids` | `One2many` | Reached milestones for this SOL |

**Delivered Qty from Milestones:**

```python
def _compute_qty_delivered(self):
    lines_by_milestones = self.filtered(lambda sol: sol.qty_delivered_method == 'milestones')
    # read_group on project.milestone: is_reached, sum quantity_percentage
    # qty_delivered = reached_percentage_sum * product_uom_qty
```

**Analytic Distribution:**

- Inherits `analytic.mixin`
- If SOL has a project, the project's analytic accounts are added to the SOL's distribution
- If SOL already has a distribution, project accounts are merged without duplicates

**Project/Task Generation:**

- `_timesheet_service_generation()` - The main entry point; handles all three service_tracking modes
- `_get_so_lines_new_project()` - SOLs with `service_tracking in ['project_only', 'task_in_project']`
- `_get_so_lines_task_global_project()` - SOLs with `service_tracking == 'task_global_project'`
- `_timesheet_create_project()` / `_timesheet_create_project_prepare_values()` - Creates project from SOL
- `_timesheet_create_task()` / `_timesheet_create_task_prepare_values()` - Creates task from SOL

**Project Creation Logic:**

- First SOL with template -> duplicates template project
- First SOL without template -> creates new project named after the SO
- Subsequent SOLs reuse the same project (1 project per SO)
- If SOL has explicit `project_id` set, uses that instead

**Project Values from SOL:**

```python
{
    'name': order.name,
    'account_id': order.project_account_id or new analytic account,
    'partner_id': order.partner_id,
    'sale_line_id': self.id,
    'allow_billable': True,
    'company_id': self.company_id,
    'sale_order_id': order.id,
}
```

**Task Creation Values:**

```python
{
    'name': SOL name (first line),
    'allocated_hours': converted qty in hours (for non-milestone/manual),
    'partner_id': order.partner_id,
    'description': SOL description,
    'project_id': project,
    'sale_line_id': self.id,
    'sale_order_id': order.id,
}
```

**Milestone Handling:**

```python
def _handle_milestones(self, project):
    if policy != 'delivered_milestones': return
    # Link existing unreached milestones in project to this SOL
    # Or create a new milestone with 100% quantity
```

**Copy Data:** When duplicating an SOL, if analytic_distribution matches the project default, it is cleared (to avoid carrying stale distribution).

**Write:** Changing `product_uom_qty` updates `task_id.allocated_hours`.

---

## project.task Extension (sale_project)

**File:** `models/project_task.py` (inherits sale_project)

| Field | Type | Description |
|---|---|---|
| `sale_line_id` | `Many2one` | SOL this task is linked to |
| `sale_order_id` | `Many2one` | SO this task is linked to |
| `sale_order_partner_id` | `Many2one` | Computed from SO partner |

These fields are defined in `project` core module. `sale_project` extends them to support cross-referencing and billing.

**Note:** In Odoo 18, `sale_line_id` on tasks is a core field from `project` module. The `sale_project` module adds views and integrations.

---

## project.project Extension (sale_project)

**File:** `models/project_project.py` (inherits sale_project)

| Field | Type | Description |
|---|---|---|
| `sale_line_count` | `Integer` | Count of linked SOLs (from project_sale_line_employee_map) |
| `sale_order_count` | `Integer` | Count of linked SOs |

**Key Methods:**

- `_compute_sale_order_count()` - Counts distinct SOs with SOLs in `sale_line_id` or `sale_line_employee_ids`
- `action_view_sale_orders()` - Opens SO list filtered to this project

---

## account.move Extension

**File:** `models/account_move.py`

| Field | Type | Description |
|---|---|---|
| `line_ids` | `One2many` | Overrides to add sale_project context |

---

## account.move.line Extension

**File:** `models/account_move_line.py`

Extends to support project/analytic linking for invoicing.

---

## Product Template Extension

**File:** `models/product_template.py`

- Service tracking fields and project template settings control task/project generation

---

## Key Service Tracking Modes

| Service Tracking | Behavior |
|---|---|
| `task_global_project` | Create task in a shared (global) project defined on the product |
| `project_only` | Create a new project per SO (no task unless also `task_in_project`) |
| `task_in_project` | Create a new project per SO AND create a task in that project |
| `no_follow` | No project/task creation |

---

## Milestone Billing Flow

1. SOL with `service_type = 'milestones'` has qty_delivered driven by reached milestones
2. `_handle_milestones()` creates/links milestones to the SOL
3. Milestones have `quantity_percentage` (default 1 = 100% of SOL qty)
4. When milestone is marked "reached", `qty_delivered` increases proportionally
5. Invoice is generated based on `qty_delivered`
6. `reached_milestones_ids` tracks which milestones have been billed

---

## Project Creation from SO

When `action_create_project()` is triggered:
- Creates project linked to SO via `sale_order_id`
- Links the SOL via `sale_line_id`
- Sets `allow_billable = True`
- Creates task stages if none exist
- If SOL has `delivered_milestones` policy, sets `generate_milestone = True` in context

---

## Analytic Distribution Inheritance

When a SOL generates a project:
- The project gets an analytic account (from SO or created fresh)
- When SOL has a project, the project's analytic accounts are merged into the SOL's `analytic_distribution`
- This ensures project costs flow to the same analytic account as the SO revenue

---

## Dependencies

```
sale_management
sale_service
project_account
  └── sale_project
```

Auto-installed with `sale_management` + `project_account`.

---

## Related Modules

| Module | Purpose |
|---|---|
| `sale_timesheet` | Timesheet tracking and billing |
| `sale_project_stock` | Stock moves in billable projects |
| `sale_project_stock_account` | Stock valuation for project tasks |
| `project_mrp` | Manufacturing tasks in projects |