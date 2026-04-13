---
Module: sale_timesheet
Version: Odoo 18
Type: Extension
Tags: #odoo #odoo18 #sale #timesheet #billing #aal #project #service
Related Modules: [sale_management](odoo-18/Modules/sale_management.md), [sale](odoo-18/Modules/sale.md), [project](odoo-18/Modules/project.md), [hr_timesheet](odoo-18/Modules/hr_timesheet.md)
---

# sale_timesheet — Sale Timesheet Billing

> Links timesheet entries (account.analytic.line) to sale order lines for time-and-materials billing. Supports both ordered-prepaid (milestone) and delivered-timesheet billing policies.

**Module:** `sale_timesheet`
**Depends:** `sale_management`, `hr_timesheet`, `project`
**Models Extended:** `sale.order.line`, `sale.order`, `account.move`, `account.move.line`, `account.analytic.line`, `project.task`, `project.project`, `product.product`, `product.template`
**Models Created:** `project.sale.line.employee.map`
**Source Path:** `~/odoo/odoo18/odoo/addons/sale_timesheet/`

---

## Overview

`sale_timesheet` bridges timesheet tracking with sale invoicing. When a service product with `invoice_policy = 'delivery'` and `service_type = 'timesheet'` is sold, every hour logged in the project creates delivered quantity that can be invoiced.

**Billing flow:**
```
Timesheet logged on project/task
    → account.analytic.line created
    → qty_delivered on sale.order.line increased
    → qty_to_invoice updated
    → Invoice created from SO
    → account.analytic.line.timesheet_invoice_id set
```

---

## Models

### `sale.order.line` — EXTENDED

Timesheet billing fields on sale order lines.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `qty_delivered_method` | `Selection` | Added `'timesheet'` option. When `product_id.type == 'service'` and `product_id.service_type == 'timesheet'`, set to `'timesheet'`. |
| `timesheet_ids` | `One2many(account.analytic.line, so_line)` | Domain: `project_id != False`. All timesheet entries that map to this SOL. |
| `analytic_line_ids` | `One2many` (override) | Domain narrowed to `project_id == False` (pure analytic lines, not timesheets). |
| `remaining_hours_available` | `Boolean` | `True` when `service_policy == 'ordered_prepaid'` AND UoM is time-based. Computed. |
| `remaining_hours` | `Float` | `product_uom_qty - qty_delivered` (in hours), only when `remaining_hours_available`. Stored. |
| `has_displayed_warning_upsell` | `Boolean` | Prevents upsell warning from showing multiple times per line. Copy=False. |

#### `_compute_qty_delivered_method()`

```python
@api.depends('product_id')
def _compute_qty_delivered_method(self):
    super()._compute_qty_delivered_method()
    for line in self:
        if not line.is_expense and line.product_id.type == 'service' and line.product_id.service_type == 'timesheet':
            line.qty_delivered_method = 'timesheet'
```

Sets `qty_delivered_method = 'timesheet'` for timesheet-billed service products. The base `sale` module sets it to `'manual'` or `'_ordered_quantity'`.

#### `_compute_qty_delivered()`

```python
@api.depends('analytic_line_ids.project_id', 'project_id.pricing_type')
def _compute_qty_delivered(self):
    super()._compute_qty_delivered()
    lines_by_timesheet = self.filtered(lambda sol: sol.qty_delivered_method == 'timesheet')
    domain = lines_by_timesheet._timesheet_compute_delivered_quantity_domain()
    mapping = lines_by_timesheet.sudo()._get_delivered_quantity_by_analytic(domain)
    for line in lines_by_timesheet:
        line.qty_delivered = mapping.get(line.id or line._origin.id, 0.0)
```

Delegates the actual sum to `_get_delivered_quantity_by_analytic`, which is defined on `account.analytic.line` in the `hr_timesheet` module (sum of `unit_amount` for lines matching domain and `so_line = line.id`).

#### `_timesheet_compute_delivered_quantity_domain()`

```python
def _timesheet_compute_delivered_quantity_domain(self):
    domain = [('project_id', '!=', False)]
    if self._context.get('accrual_entry_date'):
        domain += [('date', '<=', self._context['accrual_entry_date'])]
    return domain
```

**Hook for accruals:** The `accrual_entry_date` context is used by `sale_timesheet_accruals` (in `sale_timesheet` or `sale_management`) to compute delivered qty as of a past date for accrued revenue entries.

#### `_compute_remaining_hours()`

```python
@api.depends('qty_delivered', 'product_uom_qty', 'analytic_line_ids')
def _compute_remaining_hours(self):
    uom_hour = self.env.ref('uom.product_uom_hour')
    for line in self:
        remaining_hours = None
        if line.remaining_hours_available:
            qty_left = line.product_uom_qty - line.qty_delivered
            remaining_hours = line.product_uom._compute_quantity(qty_left, uom_hour)
        line.remaining_hours = remaining_hours
```

`remaining_hours` is the hours left to deliver on a prepaid service. Used in:
- SO line display name (appends "X hours remaining")
- Upsell warning trigger (`_get_prepaid_service_lines_to_upsell`)
- Task `remaining_hours_so` field

#### `_recompute_qty_to_invoice()`

```python
def _recompute_qty_to_invoice(self, start_date, end_date):
    """Recompute qty_to_invoice for timesheet-billed products within a date range."""
    lines_by_timesheet = self.filtered(lambda sol: sol.product_id and sol.product_id._is_delivered_timesheet())
    domain = lines_by_timesheet._timesheet_compute_delivered_quantity_domain()
    # ... filter by date range, exclude already-invoiced, handle refunds ...
    mapping = lines_by_timesheet.sudo()._get_delivered_quantity_by_analytic(domain)
    for line in lines_by_timesheet:
        qty_to_invoice = mapping.get(line.id, 0.0)
        line.qty_to_invoice = qty_to_invoice
```

This is called by `sale_make_invoice_advance` wizard when the user specifies a period for timesheet invoicing. It filters timesheets by date before linking them to invoice lines.

---

### `sale.order` — EXTENDED

Timesheet summary and invoice linking on the SO header.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `timesheet_count` | `Float` | Number of timesheet entries (grouped by order_id). Group: `hr_timesheet.group_hr_timesheet_user`. |
| `timesheet_encode_uom_id` | `Many2one(uom.uom)` | Related to `company_id.timesheet_encode_uom_id`. |
| `timesheet_total_duration` | `Integer` | Sum of timesheet `unit_amount` converted to the company's encoding UoM. Group: `hr_timesheet.group_hr_timesheet_user`. |
| `show_hours_recorded_button` | `Boolean` | `True` if the SO has timesheets or billable service products. |

#### `_create_invoices()`

```python
def _create_invoices(self, grouped=False, final=False, date=None):
    moves = super()._create_invoices(grouped=grouped, final=final, date=date)
    moves._link_timesheets_to_invoice(
        self.env.context.get("timesheet_start_date"),
        self.env.context.get("timesheet_end_date")
    )
    self._reset_has_displayed_warning_upsell_order_lines()
    return moves
```

After the base `_create_invoices`, it calls `_link_timesheets_to_invoice` on the created invoice moves. This is the mechanism that sets `timesheet_invoice_id` on `account.analytic.line` records.

#### `_get_prepaid_service_lines_to_upsell()`

Returns SOLs where:
- `is_service = True`
- `invoice_status != "invoiced"`
- `product_id.service_policy == 'ordered_prepaid'`
- `qty_delivered > product_uom_qty × service_upsell_threshold`
- `has_displayed_warning_upsell == False`

Triggers a mail activity creation (upsell warning) when the invoice status is computed and the threshold is exceeded.

---

### `account.analytic.line` — EXTENDED

Links timesheet entries to sale order lines for billing.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `timesheet_invoice_id` | `Many2one(account.move)` | The invoice that this timesheet was billed on. Index: `btree_not_null`. |
| `so_line` | `Many2one(sale.order.line)` | The SOL this timesheet maps to. Computed store, writable. Domain: sellable service lines matching the commercial partner. |
| `order_id` | `Many2one` (related) | Related to `so_line.order_id`. Stored, indexed. |
| `timesheet_invoice_type` | `Selection` | One of: `billable_time`, `billable_fixed`, `billable_milestones`, `billable_manual`, `non_billable`, `timesheet_revenues`, `service_revenues`, `other_revenues`, `other_costs`. Computed sudo, stored. |
| `commercial_partner_id` | `Many2one` | Computed: task's partner commercial entity or project partner commercial entity. |
| `is_so_line_edited` | `Boolean` | `True` when the user manually changed the SOL on a timesheet. |
| `allow_billable` | `Boolean` (related) | Related to `project_id.allow_billable`. |
| `sale_order_state` | `Selection` (related) | Related to `order_id.state`. |

#### `_compute_so_line()`

```python
@api.depends('task_id.sale_line_id', 'project_id.sale_line_id', 'employee_id', 'project_id.allow_billable')
def _compute_so_line(self):
    for timesheet in self.filtered(lambda t: not t.is_so_line_edited and t._is_not_billed()):
        timesheet.so_line = timesheet.project_id.allow_billable and timesheet._timesheet_determine_sale_line()
```

Only computes `so_line` if:
1. User has NOT manually edited the SOL (`is_so_line_edited = False`)
2. Timesheet is NOT already invoiced (`_is_not_billed()`)

#### `_timesheet_determine_sale_line()`

Priority for SOL assignment on a timesheet:

```
1. If task_id exists and task.allow_billable and task.sale_line_id:
   a. If task.pricing_type in ('task_rate', 'fixed_rate'): → task.sale_line_id
   b. If task.pricing_type == 'employee_rate':
      - Find project.sale_line_employee_ids entry matching (employee_id, partner_id match)
        → that map's sale_line_id
      - Else fallback: task.sale_line_id
2. If project.pricing_type == 'employee_rate':
   - Find project.sale_line_employee_ids entry matching (employee_id)
     → that map's sale_line_id
3. Return project.sale_line_id
4. Return False
```

This is the L4 billing logic: **employee rate** projects bill different employees at different SOL rates via the `project.sale.line.employee.map`.

#### `_is_not_billed()`

```python
def _is_not_billed(self):
    self.ensure_one()
    return not self.timesheet_invoice_id or (
        self.timesheet_invoice_id.state == 'cancel'
        and self.timesheet_invoice_id.payment_state != 'invoicing_legacy'
    )
```

A timesheet is "not billed" if it has no invoice, OR if its invoice was cancelled (but not legacy invoicing). This controls whether `_compute_so_line` auto-assigns the SOL.

#### `_check_can_write()`

Raises `UserError` if an invoiced timesheet (non-cancelled invoice) has its `unit_amount`, `employee_id`, `project_id`, `task_id`, `so_line`, or `date` modified. This is a hard guard — once a timesheet is invoiced, its time cannot be changed.

#### `_check_timesheet_can_be_billed()`

```python
def _check_timesheet_can_be_billed(self):
    return self.so_line in (
        self.project_id.mapped('sale_line_employee_ids.sale_line_id')
        | self.task_id.sale_line_id
        | self.project_id.sale_line_id
    )
```

Validates that the SOL assigned to the timesheet is part of the project's billing structure. Prevents random SOLs from being assigned to timesheets.

---

### `account.move` — EXTENDED

Invoice-level timesheet tracking.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `timesheet_ids` | `One2many(account.analytic.line, timesheet_invoice_id)` | All timesheets linked to this invoice. |
| `timesheet_count` | `Integer` | Number of linked timesheets. |
| `timesheet_total_duration` | `Integer` | Sum of timesheet durations on this invoice. |

#### `_link_timesheets_to_invoice()`

```python
def _link_timesheets_to_invoice(self, start_date=None, end_date=None):
    for line in self.filtered(lambda i: i.move_type == 'out_invoice' and i.state == 'draft'):
        for line in self.filtered(...).invoice_line_ids:
            sale_line_delivery = line.sale_line_ids.filtered(
                lambda sol: sol.product_id.invoice_policy == 'delivery'
                and sol.product_id.service_type == 'timesheet'
            )
            if sale_line_delivery:
                domain = line._timesheet_domain_get_invoiced_lines(sale_line_delivery)
                # Apply date filters if specified
                timesheets = self.env['account.analytic.line'].sudo().search(domain)
                timesheets.write({'timesheet_invoice_id': line.move_id.id})
```

Called from `sale.order._create_invoices()` after the invoice draft is created. It:
1. Finds invoice lines linked to timesheet-billed SOLs
2. Searches all uninvoiced (or cancelled-invoice) timesheets for those SOLs
3. Writes `timesheet_invoice_id = invoice.id` on those AALs

This links the timesheets so you can see which hours were billed to which invoice.

---

### `account.move.line` — EXTENDED

#### `_timesheet_domain_get_invoiced_lines()`

```python
@api.model
def _timesheet_domain_get_invoiced_lines(self, sale_line_delivery):
    return [
        ('so_line', 'in', sale_line_delivery.ids),
        ('project_id', '!=', False),
        '|', '|',
            ('timesheet_invoice_id', '=', False),
            '&', ('timesheet_invoice_id.state', '=', 'cancel'),
                   ('timesheet_invoice_id.payment_state', '!=', 'invoicing_legacy'),
            ('timesheet_invoice_id.payment_state', '=', 'reversed')
    ]
```

Domain for uninvoiced or reversed/cancelled timesheets. Used by `_link_timesheets_to_invoice` to find which timesheets to link.

---

### `project.project` — EXTENDED

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `pricing_type` | `Selection` | `'task_rate'` (default), `'fixed_rate'`, `'employee_rate'`. Computed from `sale_line_employee_ids` and `sale_line_id`. |
| `sale_line_employee_ids` | `One2many(project.sale.line.employee.map)` | Maps employees to SOLs with custom hourly rates. |
| `timesheet_product_id` | `Many2one(product.product)` | Default service product for timesheet billing (type=service, invoice_policy=delivery, service_type=timesheet). |
| `billing_type` | `Selection` | `'not_billable'`, `'manually'`. Computed from `allow_billable` and `allow_timesheets`. |
| `allocated_hours` | `Float` | Total hours allocated to the project (from service product quantity). |

#### `_update_timesheets_sale_line_id()`

When a `project.sale.line.employee.map` entry is created/updated, it calls `project._update_timesheets_sale_line_id()`. This finds all non-invoiced, editable timesheets for the matching employee and updates their `so_line` to the mapped SOL.

---

### `project.task` — EXTENDED

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `remaining_hours_so` | `Float` | Remaining hours on the SOL mapped to this task (considers in-progress unsaved timesheets). |
| `remaining_hours_available` | `Boolean` (related) | Related to `sale_line_id.remaining_hours_available`. |
| `is_project_map_empty` | `Boolean` | `True` if the project has no employee SOL mappings. |
| `has_multi_sol` | `Boolean` | `True` if task's timesheets have been billed to a different SOL than the task's `sale_line_id`. |

#### `_compute_remaining_hours_so()`

Computes remaining hours considering timesheets currently being entered (in the UI but not yet saved). It adjusts the remaining hours based on:
- Previously saved timesheets pointing to the task's SOL
- In-memory timesheet deltas (`unit_amount` changes vs `_origin.unit_amount`)

---

### `project.sale.line.employee.map` — NEW MODEL

Maps employees to SOLs with a custom hourly cost for `employee_rate` pricing projects.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | `Many2one(project.project)` | Required. |
| `employee_id` | `Many2one(hr.employee)` | Required. Unique per project. |
| `sale_line_id` | `Many2one(sale.order.line)` | The SOL this employee bills against. Filtered to service lines matching the project's partner. |
| `price_unit` | `Float` | Related from `sale_line_id.price_unit`. Computed readonly. |
| `currency_id` | `Many2one(res.currency)` | Related from `sale_line_id.currency_id`. |
| `cost` | `Monetary` | Custom hourly cost for this employee on this project. Overrides `employee.hourly_cost`. |
| `display_cost` | `Monetary` | `cost × hours_per_day` if company encodes timesheets in days; otherwise equals `cost`. Groups: `project.group_project_manager`, `hr.group_hr_user`. |
| `is_cost_changed` | `Boolean` | `True` if `cost != employee.hourly_cost`. |
| `cost_currency_id` | `Many2one(res.currency)` | Related to `employee.currency_id`. |

**SQL Constraint:** `(project_id, employee_id)` is unique.

**L4 — Employee rate billing:**
When `pricing_type == 'employee_rate'`, each employee on the project has their own SOL (and potentially their own rate). The `project.sale.line.employee.map` defines which SOL is used when that employee logs time. This allows, for example:
- Junior consultant: SOL with price `$100/hr`
- Senior consultant: SOL with price `$150/hr`
Both are on the same project, but bill at different rates via different SOLs.

---

### `product.template` — EXTENDED

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `service_type` | `Selection` | Added `'timesheet'` option: `"Timesheets on project (one fare per SO/Project)"`. `ondelete='set manual'`. |
| `service_upsell_threshold` | `Float` | `default=1`. Percentage multiplier on `product_uom_qty` that triggers upsell activity. |
| `service_upsell_threshold_ratio` | `Char` | Computed display string showing UoM conversion ratio (e.g., "1 unit = 8.00 hours"). |

#### `_selection_service_policy()`

Inserts `'delivered_timesheet'` as option 1 (after the base options):
```python
service_policies.insert(1, ('delivered_timesheet', _('Based on Timesheets')))
```

This adds the new policy alongside the base `ordered_prepaid` (delivered_manual, delivered_milestones).

#### `_get_service_to_general_map()`

```python
def _get_service_to_general_map(self):
    return {
        **super()._get_service_to_general_map(),
        'delivered_timesheet': ('delivery', 'timesheet'),  # invoice_policy, service_type
        'ordered_prepaid': ('order', 'timesheet'),         # prepaid hours, timesheet-tracked
    }
```

Maps service policies to the general `(invoice_policy, service_type)` tuple used for profitability categorization.

---

### `product.product` — EXTENDED

#### Methods

| Method | Description |
|--------|-------------|
| `_is_delivered_timesheet()` | Returns `True` if `type == 'service'` and `service_policy == 'delivered_timesheet'`. Used as a domain filter throughout the module. |
| `_onchange_service_fields()` | When `service_type` is set to `'timesheet'`, sets `uom_id` to the company's default timesheet UoM (or hours). |

---

### `sale.advance.payment.inv` Wizard — EXTENDED

Added period-based timesheet invoicing.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `date_start_invoice_timesheet` | `Date` | Start date filter for timesheet-based invoicing. |
| `date_end_invoice_timesheet` | `Date` | End date filter for timesheet-based invoicing. |
| `invoicing_timesheet_enabled` | `Boolean` | `True` if any SOL on the SO is a delivered-timesheet product. Computed. |

#### `_create_invoices()`

When `advance_payment_method == 'delivered'` and `invoicing_timesheet_enabled == True`:
1. Calls `sale_orders.order_line._recompute_qty_to_invoice(start_date, end_date)` to filter timesheets by date.
2. Passes `timesheet_start_date` and `timesheet_end_date` in context to `_create_invoices`.

---

## L4: Invoice Line Generation from Timesheets

### How an Invoice Line Is Created

When `_create_invoices` runs for a timesheet-billed SOL:

1. `sale.order.line` computes `qty_to_invoice` from `qty_delivered` (sum of AAL `unit_amount`).
2. Base `sale` module's `_create_invoices` creates invoice lines with `quantity = qty_to_invoice`.
3. `sale.order._create_invoices` calls `moves._link_timesheets_to_invoice()`.
4. `_link_timesheets_to_invoice` sets `timesheet_invoice_id` on all matching uninvoiced AALs.

### Prepaid Hours Billing (ordered_prepaid)

For `service_policy = 'ordered_prepaid'`:
- Invoice is created at order confirmation (or manually) for the full `product_uom_qty`.
- As timesheets are logged, `qty_delivered` increases.
- `qty_to_invoice` stays at `product_uom_qty` (already invoiced) — no additional invoice is generated from timesheets.
- `remaining_hours` decreases as time is consumed.
- When `remaining_hours == 0` and the SO is still active, the upsell warning fires.

### Delivered Timesheet Billing

For `service_policy = 'delivered_timesheet'`:
- No invoice at order confirmation.
- As timesheets are logged, `qty_delivered` increases.
- `qty_to_invoice` equals `qty_delivered - qty_invoiced`.
- Each invoice creates invoice lines for the newly delivered quantity.
- `_link_timesheets_to_invoice` is called with date filters to link only the relevant timesheets.

### AAL Creation from Timesheets

When a user logs a timesheet on a billable project:
1. `hr_timesheet` module creates `account.analytic.line` with `project_id`, `task_id`, `employee_id`, `unit_amount`.
2. `sale_timesheet`'s `_compute_so_line` assigns the `so_line` based on pricing type and employee mapping.
3. `_compute_qty_delivered` on the SOL sums the AAL `unit_amount` values, increasing `qty_delivered`.
4. `_compute_qty_delivered_method` confirms the method is `'timesheet'`.

### Prepaid Hours Consumption

For ordered-prepaid products:
```
product_uom_qty = 100 hours  (ordered qty)
qty_delivered increases as timesheets are logged
remaining_hours = product_uom_qty - qty_delivered
```

When `remaining_hours` hits zero, the line is fully consumed. The upsell threshold (`service_upsell_threshold`, default 1.0 = 100%) fires when:
```
qty_delivered > product_uom_qty × service_upsell_threshold
```

---

## Project Pricing Types

| Pricing Type | Description | SOL Used |
|---|---|---|
| `task_rate` | Each task can be mapped to any SOL | `task.sale_line_id` |
| `fixed_rate` | Project has one SOL; all tasks use it | `project.sale_line_id` |
| `employee_rate` | Each employee has a SOL mapping | `project.sale_line_employee_ids[employee_id].sale_line_id` |

The pricing type is computed: if `sale_line_employee_ids` exists → `employee_rate`; elif `sale_line_id` exists → `fixed_rate`; else → `task_rate`.

---

## L4: `_is_not_billed()` Deep Dive

This method controls the entire re-billing lifecycle of a timesheet:

```
Timesheet created → timesheet_invoice_id = False → _is_not_billed() = True
                                                              ↓
                                          so_line is auto-computed from task/project
                                                              ↓
Invoice created → _link_timesheets_to_invoice() runs
                                                              ↓
timesheet_invoice_id = invoice.id → _is_not_billed() = False
                                                              ↓
so_line is LOCKED (won't auto-change on write)
Invoice cancelled → _is_not_billed() = True (if not legacy)
                   → so_line can be reassigned
                   → timesheet can be re-invoiced
Invoice reversed → _is_not_billed() = True
                  → timesheet can be re-invoiced
```
