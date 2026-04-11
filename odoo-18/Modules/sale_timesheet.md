# sale_timesheet - Sales Timesheet

**Module:** `sale_timesheet`
**Depends:** `sale_project`, `hr_timesheet`
**Auto-install:** True
**Category:** Hidden

---

## Purpose

Bridges timesheet entries with sale orders. Links `account.analytic.line` (timesheet entries) to `sale.order.line` (service products), so time spent on projects/tasks is automatically billed. Provides pricing by task, by employee, or by project rate. Handles delivery-based invoicing where the qty_delivered is driven by timesheet unit amounts.

---

## sale.order Extension

**File:** `models/sale_order.py`

| Field | Type | Description |
|---|---|---|
| `timesheet_count` | `Float` | Count of timesheet entries on linked projects |
| `timesheet_encode_uom_id` | `Many2one` | Related to company's timesheet encoding UoM |
| `timesheet_total_duration` | `Integer` | Total recorded time in encoding UoM |
| `show_hours_recorded_button` | `Boolean` | Show button to view timesheets |

**Key Methods:**

- `_compute_timesheet_count()` - Counts AAL records linked to this SO's projects
- `_compute_timesheet_total_duration()` - Sums unit_amount from timesheets, converted to company's encoding UoM (hours or days)
- `_get_prepaid_service_lines_to_upsell()` - Returns SOLs with ordered_prepaid policy where delivered > threshold
- `_compute_field_value(field)` - Overrides `invoice_status` computation to trigger upsell activity creation
- `_create_upsell_activity()` - Creates mail activity for prepaid service upsell warning
- `_get_order_with_valid_service_product()` - Returns SOs with service products that can track timesheets
- `action_view_timesheet()` - Opens timesheet list filtered to this SO's order lines

---

## sale.order.line Extension

**File:** `models/sale_order_line.py`

| Field | Type | Description |
|---|---|---|
| `qty_delivered_method` | `Selection` | Added `'timesheet'` option for timesheet-driven delivery |
| `remaining_hours_available` | `Boolean` | True for ordered_prepaid service with time UoM |
| `remaining_hours` | `Float` | Computed remaining qty in hours |
| `timesheet_ids` | `One2many` | AAL records with `project_id != False` (timesheets linked to SOL) |

**Delivery Method Selection:**

```python
def _compute_qty_delivered_method(self):
    super()._compute_qty_delivered_method()
    for line in self:
        if not line.is_expense and line.product_id.type == 'service' \
                and line.product_id.service_type == 'timesheet':
            line.qty_delivered_method = 'timesheet'
```

**Delivered Qty from Timesheets:**

```python
def _compute_qty_delivered(self):
    super()._compute_qty_delivered()
    lines_by_timesheet = self.filtered(lambda sol: sol.qty_delivered_method == 'timesheet')
    domain = lines_by_timesheet._timesheet_compute_delivered_quantity_domain()
    mapping = lines_by_timesheet.sudo()._get_delivered_quantity_by_analytic(domain)
    for line in lines_by_timesheet:
        line.qty_delivered = mapping.get(line.id or line._origin.id, 0.0)
```

**Remaining Hours:**

```python
def _compute_remaining_hours(self):
    for line in self:
        if line.remaining_hours_available:
            qty_left = line.product_uom_qty - line.qty_delivered
            remaining_hours = line.product_uom._compute_quantity(qty_left, uom_hour)
            line.remaining_hours = remaining_hours
```

**Project/Task Creation:**

- `_timesheet_create_project()` - Overrides to set `allow_timesheets = True` and inherit `allocated_hours` from project template or product qty
- `_timesheet_create_project_prepare_values()` - Adds `allow_billable = True`

**Recompute Qty to Invoice:**

- `_recompute_qty_to_invoice(start_date, end_date)` - Searches timesheets in a date range to recompute `qty_to_invoice` for timesheet-delivered SOLs
- Handles credit notes (refunds) by reversing credited timesheets

**Display Name with Remaining:**

- `_compute_display_name()` - Appends "X hours remaining" or "X.XX days remaining" to SOL names when in context with `with_remaining_hours`

---

## account.analytic.line Extension

**File:** `models/hr_timesheet.py`

The core linking between timesheet and sale order:

| Field | Type | Description |
|---|---|---|
| `timesheet_invoice_type` | `Selection` | `'billable_time'` / `'billable_fixed'` / `'billable_milestones'` / `'billable_manual'` / `'non_billable'` / `'timesheet_revenues'` / `'service_revenues'` / `'other_revenues'` / `'other_costs'` |
| `commercial_partner_id` | `Many2one` | From task or project partner |
| `timesheet_invoice_id` | `Many2one` | Invoice this timesheet was billed on |
| `so_line` | `Many2one` | Sales order line (computed, not directly editable) |
| `order_id` | `Many2one` | Related to `so_line.order_id` (stored, indexed) |
| `is_so_line_edited` | `Boolean` | User manually edited the so_line |
| `allow_billable` | `Boolean` | Related from project |
| `sale_order_state` | `Selection` | Related from order_id |

**Domain on `so_line`:** Restricts to sellable service SOLs for the same commercial partner.

**SO Line Determination:**

```python
@api.depends('task_id.sale_line_id', 'project_id.sale_line_id', 'employee_id', 'project_id.allow_billable')
def _compute_so_line(self):
    for timesheet in self.filtered(lambda t: not t.is_so_line_edited and t._is_not_billed()):
        timesheet.so_line = timesheet.project_id.allow_billable and timesheet._timesheet_determine_sale_line()
```

**`_timesheet_determine_sale_line()` Logic:**

1. **Task rate** - Return `task_id.sale_line_id`
2. **Employee rate** - Check `sale_line_employee_ids` mapping for employee; fallback to `task.sale_line_id` or `project.sale_line_id`
3. **Fixed rate** - Return `project_id.sale_line_id`
4. **Non-billable** - Return False

**Invoice Type Computation:**

- `timesheet` service type + delivery policy + amount > 0 = `'timesheet_revenues'`
- `timesheet` service type + delivery policy + no amount = `'billable_time'`
- `milestones` / `manual` service type = `'billable_milestones'` / `'billable_manual'`
- Order-based invoicing = `'billable_fixed'`
- No so_line = `'non_billable'` or `'billable_manual'` (based on project billing_type)

**Write Protection:**

- `_check_can_write()` - Prevents modifying timesheets already invoiced with delivery policy (unit_amount, employee_id, project_id, task_id, so_line, date)
- `_unlink_except_invoiced()` - Prevents deleting invoiced timesheets

**Hourly Cost for Employee Rate:**

- `_hourly_cost()` - Returns mapping entry cost if `project_id.pricing_type == 'employee_rate'`

---

## project.project Extension (sale_timesheet)

**File:** `models/project_project.py`

| Field | Type | Description |
|---|---|---|
| `pricing_type` | `Selection` | `'task_rate'` / `'fixed_rate'` / `'employee_rate'` (computed from sale_line/employee mapping) |
| `sale_line_employee_ids` | `One2many` | Employee-to-SOL mapping for employee rate pricing |
| `timesheet_product_id` | `Many2one` | Default service product for timesheet billing |
| `warning_employee_rate` | `Boolean` | Warning when employees lack rate mapping |
| `billing_type` | `Selection` | `'not_billable'` / `'manually'` (computed from allow_billable + allow_timesheets) |

**Key Methods:**

- `_update_timesheets_sale_line_id()` - Syncs so_line on existing timesheets when employee mapping changes
- `action_billable_time_button()` - Action to view billable timesheet entries

---

## project.task Extension (sale_timesheet)

**File:** `models/project_task.py`

| Field | Type | Description |
|---|---|---|
| `sale_order_id` | `Many2one` | Related SO (filtered by partner hierarchy) |
| `pricing_type` | `Selection` | Related from project |
| `is_project_map_empty` | `Boolean` | No employee SOL mappings |
| `has_multi_sol` | `Boolean` | Timesheets linked to different SOLs than the task's SOL |
| `timesheet_product_id` | `Many2one` | Related from project |
| `remaining_hours_so` | `Float` | Computed remaining hours on the SOL |
| `remaining_hours_available` | `Boolean` | Related from sale_line_id |

**Key Methods:**

- `_get_last_sol_of_customer()` - Finds most recent SOL with remaining_hours > 0 for the customer's commercial partner
- `_compute_sale_line()` - Auto-fills task's SOL if billable and no SOL set
- `_compute_remaining_hours_so()` - Tracks delta between original and current unit_amount for the same SOL
- `_get_timesheet()` - Returns non-invoiced, non-project-less timesheets

---

## Timesheet to Invoice Flow

1. User records timesheet entries on tasks linked to a SOL
2. `so_line` is auto-determined from task/project/employee mapping
3. `qty_delivered` on SOL = sum of timesheet unit amounts (via `_compute_qty_delivered`)
4. On invoice creation: `_create_invoices()` calls `moves._link_timesheets_to_invoice()`
5. Timesheets are linked to the invoice via `timesheet_invoice_id`
6. `timesheet_invoice_type` drives profitability reporting and billing type

---

## Service Policy to Invoice Type Mapping

From `project.project` in sale_timesheet:

| Service Policy | Invoice Type |
|---|---|
| `ordered_prepaid` | `billable_fixed` |
| `delivered_milestones` | `billable_milestones` |
| `delivered_timesheet` | `billable_time` |
| `delivered_manual` | `billable_manual` |

---

## Profitability Sections (in Project Panel)

| Section | Domain |
|---|---|
| `billable_fixed` | Order-based service |
| `billable_time` | Delivered-by-timesheet service |
| `billable_milestones` | Milestone-delivered service |
| `billable_manual` | Manually billed service |
| `non_billable` | Timesheets with no SOL |
| `timesheet_revenues` | Timesheets with positive amount and so_line |
| `other_costs` | Materials / non-service |

---

## Key Security / Access Rules

- Timesheet write restrictions based on invoicing state
- `_is_not_billed()` check gates SO line auto-assignment
- Only approvers (group_hr_timesheet_approver) can see timesheet record IDs in profitability actions

---

## Dependencies

```
sale_project (auto-installs sale_management + project_account)
hr_timesheet
  └── sale_timesheet
        └── sale_project
        └── hr_timesheet
```

`sale_timesheet` is auto-installed with `sale_project` in standard installations since they are co-dependent.