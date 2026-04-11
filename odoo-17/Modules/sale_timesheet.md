---
tags: [odoo, odoo17, module, sale_timesheet, timesheet]
research_depth: medium
---

# Sale Timesheet Module — Deep Reference

**Source:** `addons/sale_timesheet/models/`

## Overview

Links project task timesheets to sale order invoicing — billable hours tracked per task. When a service product with `invoice_policy = 'delivery'` and `service_type = 'timesheet'` is sold, every timesheet entry auto-bumps `qty_delivered` on the SO line, making it ready to invoice.

## Files

| File | Class Extended | Purpose |
|------|---------------|---------|
| `sale_order.py` | `sale.order`, `sale.order.line` | Delivered qty from timesheets, upsell activities |
| `account.py` | `account.analytic.line` | so_line assignment, billing type computation |
| `account_move.py` | `account.move`, `account.move.line` | Link timesheets to created invoice |
| `project.py` | `project.project`, `project.task` | Pricing types, profitability |
| `project_sale_line_employee_map.py` | `project.sale.line.employee.map` | Employee-to-SO-line rate mapping |

## Key Models

### sale.order (Extended)

#### Fields Added
| Field | Type | Description |
|-------|------|-------------|
| `timesheet_count` | Float | Number of timesheet entries on the SO |
| `timesheet_total_duration` | Integer | Total hours logged (encoded UoM) |
| `show_hours_recorded_button` | Boolean | Show button to log time |

#### Methods
| Method | Purpose |
|--------|---------|
| `_get_prepaid_service_lines_to_upsell()` | Detect when a prepaid SO line exceeds its upsell threshold |
| `_create_upsell_activity()` | Trigger mail activity to salesperson |
| `_create_invoices()` | After invoice creation, links timesheets via `_link_timesheets_to_invoice()` |
| `action_view_timesheet()` | Opens timesheet tree view filtered to this SO's lines |

### sale.order.line (Extended)

#### Fields Added
| Field | Type | Description |
|-------|------|-------------|
| `qty_delivered_method` | Selection | Now includes `'timesheet'` |
| `analytic_line_ids` | One2many | Non-project analytic lines |
| `timesheet_ids` | One2many | Timesheet lines (`project_id != False`) |
| `remaining_hours_available` | Boolean | Only for ordered_prepaid + time UoM |
| `remaining_hours` | Float | `product_uom_qty - qty_delivered` in hours |
| `has_displayed_warning_upsell` | Boolean | Prevents duplicate upsell warnings |

#### Delivered Qty Flow
```
employee logs time
  → account.analytic.line created with so_line = SOL
    → _compute_qty_delivered() on SOL
      → SUM(unit_amount of timesheet lines) / UoM factor
        → qty_delivered on SOL updated
          → invoice_status → 'to invoice'
```

### account.analytic.line (Extended)

#### Fields Added
| Field | Type | Description |
|-------|------|-------------|
| `so_line` | Many2one | Sale order line to bill to (computed unless manually edited) |
| `timesheet_invoice_id` | Many2one | Invoice this timesheet was linked to |
| `timesheet_invoice_type` | Selection | billable_time / billable_fixed / billable_milestones / billable_manual / non_billable / timesheet_revenues / service_revenues / other_revenues / other_costs |
| `order_id` | Many2one | Related via `so_line.order_id` |
| `is_so_line_edited` | Boolean | User manually changed so_line |
| `commercial_partner_id` | Many2one | From task or project partner |

#### so_line Computation (`_compute_so_line`)
The line is auto-assigned if:
1. Project has `allow_billable = True`
2. Timesheet is not already invoiced (`_is_not_billed()`)
3. Priority: task SOL (`task_rate`/`fixed_rate`) → employee map SOL (`employee_rate`) → project SOL

#### Billing Type Computation (`_compute_timesheet_invoice_type`)
```
no so_line + project.billing_type != 'manually'  → non_billable
no so_line + project.billing_type == 'manually'  → billable_manual
so_line + service + invoice_policy=delivery + service_type=timesheet + amount > 0  → timesheet_revenues
so_line + service + invoice_policy=delivery + service_type=timesheet + amount ≤ 0  → billable_time
so_line + service + invoice_policy=order        → billable_fixed
```

### project.project (Extended)

#### Fields Added
| Field | Type | Description |
|-------|------|-------------|
| `pricing_type` | Selection | task_rate / fixed_rate / employee_rate (computed, searchable) |
| `sale_line_employee_ids` | One2many | `project.sale.line.employee.map` entries |
| `timesheet_product_id` | Many2one | Default "Time" service product for billing |
| `billable_percentage` | Integer | % of timesheets with a so_line |
| `billing_type` | Selection | not_billable / manually (computed) |

#### Pricing Types
| Pricing Type | Description |
|-------------|-------------|
| `task_rate` (default) | Each task has its own rate — SO line on task determines billing |
| `fixed_rate` | Project has one SO line — all tasks bill to the same SOL |
| `employee_rate` | Employee-to-SOL map in `sale_line_employee_ids` — each employee has their own billing rate |

### project.sale.line.employee.map

Maps an employee to a specific SO line within a project, setting the billing rate.

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | Many2one | Project |
| `employee_id` | Many2one | Employee |
| `sale_line_id` | Many2one | SO line to bill this employee's time to |
| `cost` | Monetary | Override for employee's hourly cost on this project |
| `display_cost` | Monetary | Cost displayed in daily or hourly UoM per company setting |

SQL constraint: UNIQUE(project_id, employee_id) — one mapping per employee per project.

## Timesheet → Invoice Flow

### Step 1: Create Sale Order with Timesheet Service
1. Product with `type = 'service'`, `invoice_policy = 'delivery'`, `service_type = 'timesheet'`
2. On SO confirmation, `_timesheet_create_project()` creates a billable project
3. Task auto-created per SO line

### Step 2: Track Time
1. Employee logs time on task → `account.analytic.line` created
2. `_compute_so_line()` auto-assigns the correct SOL
3. `qty_delivered_method` = `'timesheet'` triggers `_compute_qty_delivered()`
4. `qty_delivered` on SOL = SUM of timesheet `unit_amount`

### Step 3: Upsell Warning (Prepaid Only)
When `service_policy = 'ordered_prepaid'` and `qty_delivered > product_uom_qty * upsell_threshold`:
- `_create_upsell_activity()` fires a mail activity to the salesperson
- Flag `has_displayed_warning_upsell = True` (reset when SOL is fully invoiced)

### Step 4: Invoice
1. `_create_invoices()` called on SO
2. `moves._link_timesheets_to_invoice()` searches all unbilled timesheet lines for SOLs with `invoice_policy == 'delivery'` and `service_type == 'timesheet'`
3. Writes `timesheet_invoice_id` on each matched timesheet
4. Timesheets with `timesheet_invoice_id.state == 'cancel'` + `payment_state != 'invoicing_legacy'` are also eligible

### Step 5: Credit Note Reversal
On `action_post()` for `out_refund` with a `reversed_entry_id`:
- Searches timesheets linked to the original invoice
- Clears `timesheet_invoice_id` so they can be re-billed

## Billing Modes Detail

### Task Rate (default)
```python
# _timesheet_determine_sale_line
if self.task_id.allow_billable and self.task_id.sale_line_id:
    return self.task_id.sale_line_id  # billing follows the task's SOL
```

### Employee Rate
```python
# _timesheet_determine_sale_line
map_entry = project.sale_line_employee_ids.filtered(
    lambda m: m.employee_id == self.employee_id
    and m.sale_line_id.order_partner_id.commercial_partner_id
        == self.task_id.partner_id.commercial_partner_id
)
return map_entry.sale_line_id
```

## Profitability Reporting

`project.project._get_profitability_items_from_aal()` extends the standard panel with timesheet-specific invoice types:

| Invoice Type | Label | Sequence |
|-------------|-------|---------|
| `billable_fixed` | Timesheets (Fixed Price) | 1 |
| `billable_time` | Timesheets (Billed on Timesheets) | 2 |
| `billable_milestones` | Timesheets (Billed on Milestones) | 3 |
| `billable_manual` | Timesheets (Billed Manually) | 4 |
| `non_billable` | Timesheets (Non Billable) | 5 |
| `timesheet_revenues` | Timesheet revenues | 6 |
| `other_costs` | Materials | 12 |

## See Also
- [[Modules/sale]] — sale.order
- [[Modules/project]] — project.task, project.project
- [[Modules/hr_timesheet]] — account.analytic.line base model
- [[Modules/stock_account]] — Anglo-Saxon COGS entries
