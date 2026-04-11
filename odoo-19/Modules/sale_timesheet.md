---
type: module
module: sale_timesheet
tags: [odoo, odoo19, sale, timesheet, billing, project, aal, analytic]
created: 2026-04-06
updated: 2026-04-11
---

# sale_timesheet - Sales Timesheet Module

> **Sell services based on timesheets.** Allows tracking time spent on tasks/projects and invoicing those hours to customers. The core integration between `sale` and `hr_timesheet` modules.

**Category:** Sales/Sales | **Depends:** `sale_project`, `hr_timesheet` | **License:** LGPL-3

---

## Overview

The `sale_timesheet` module bridges two domains:

1. **Time tracking** - Employees log hours on `account.analytic.line` records linked to projects/tasks
2. **Sales invoicing** - Those hours are billed to customers via `sale.order.line` products

The module enables **time-and-materials billing**: customers pay per hour/day worked rather than a fixed price. It extends `sale_project` (which creates projects/tasks from SOLs) with timesheet-to-invoice linking, billable-type classification, and profitability reporting.

### Key Features

- Timesheet lines automatically linked to sale order lines (SOL)
- Three pricing strategies: task rate, fixed rate, employee rate
- Per-employee SOL mapping for different billing rates
- Upsell warnings when prepaid hours are nearly exhausted
- Credit note reversal clears invoice links on timesheets
- Profitability panel shows billable vs non-billable breakdown

---

## Architecture

```
sale_timesheet
├── models/
│   ├── hr_timesheet.py           # account.analytic.line extensions
│   ├── project_project.py       # project.project extensions
│   ├── project_task.py          # project.task extensions
│   ├── project_sale_line_employee_map.py  # Per-employee SOL mapping
│   ├── sale_order_line.py       # sale.order.line extensions
│   ├── sale_order.py            # sale.order extensions
│   ├── account_move.py          # account.move extensions
│   ├── account_move_line.py     # account.move.line extensions
│   ├── account_move_reversal.py # Reversal wizard extension
│   ├── product_product.py       # product.product extensions
│   ├── product_template.py      # product.template extensions
│   ├── hr_employee.py           # hr.employee extensions
│   └── res_config_settings.py   # Settings extension
├── wizard/
│   └── sale_make_invoice_advance.py  # Advance invoice with date range
├── report/
│   ├── project_report.py        # Project task analysis report
│   └── timesheets_analysis_report.py # Timesheet pivot analysis
└── controllers/
    └── portal.py                # Portal access for timesheets
```

---

## Models

---

### account.analytic.line (sale_timesheet extension)

> Extends `account.analytic.line` from `hr_timesheet` to add sale order billing intelligence.

**File:** `models/hr_timesheet.py`

#### TIMESHEET_INVOICE_TYPES Constant

```python
TIMESHEET_INVOICE_TYPES = [
    ('billable_time',      'Billed on Timesheets'),      # Delivery-based timesheet SOL
    ('billable_fixed',     'Billed at a Fixed price'),   # Order-based or milestones
    ('billable_milestones','Billed on Milestones'),       # Milestone service type
    ('billable_manual',    'Billed Manually'),             # Manual billing type
    ('non_billable',       'Non-Billable'),               # No SOL or not billable project
    ('timesheet_revenues', 'Timesheet Revenues'),         # Revenue recognition line
    ('service_revenues',   'Service Revenues'),           # Non-timesheet service revenue
    ('other_revenues',     'Other revenues'),             # Non-service revenue
    ('other_costs',        'Other costs'),               # Negative amounts, non-project
]
```

#### Fields

| Field | Type | Compute/Sudo | Store | Purpose |
|-------|------|-------------|-------|---------|
| `timesheet_invoice_type` | Selection | Yes (compute_sudo) | Yes | Classification of billable type (see TIMESHEET_INVOICE_TYPES) |
| `commercial_partner_id` | Many2one | No | No | Cached commercial partner from task/project |
| `timesheet_invoice_id` | Many2one | No | Yes (index btree_not_null) | Invoice this timesheet was posted to |
| `so_line` | Many2one | Yes (compute) | Yes | Sale order line to bill against |
| `order_id` | Many2one | related | Yes (index) | Related sale order (derived from so_line) |
| `is_so_line_edited` | Boolean | No | No | Flag: was SOL manually set by user? |
| `allow_billable` | Boolean | related | No | From project_id.allow_billable |
| `sale_order_state` | Selection | related | No | State of the linked sale order |

#### `timesheet_invoice_type` (compute_sudo, store)

Computed based on the SOL's product configuration. Uses `sudo()` for ACL bypass since timesheets may belong to projects the current user cannot access.

```python
@api.depends('so_line.product_id', 'project_id.billing_type', 'amount')
def _compute_timesheet_invoice_type(self):
    for timesheet in self:
        if timesheet.project_id:
            # No SOL: non-billable or manual
            if not timesheet.so_line:
                invoice_type = 'non_billable' if timesheet.project_id.billing_type != 'manually' else 'billable_manual'
            # Has SOL with service product
            elif timesheet.so_line.product_id.type == 'service':
                if timesheet.so_line.product_id.invoice_policy == 'delivery':
                    if timesheet.so_line.product_id.service_type == 'timesheet':
                        # Revenue recognition vs. billable depends on amount sign
                        invoice_type = 'timesheet_revenues' if timesheet.amount > 0 and timesheet.unit_amount > 0 else 'billable_time'
                    else:
                        service_type = timesheet.so_line.product_id.service_type
                        invoice_type = f'billable_{service_type}' if service_type in ['milestones', 'manual'] else 'billable_fixed'
                elif timesheet.so_line.product_id.invoice_policy == 'order':
                    invoice_type = 'billable_fixed'
        else:
            # No project: other revenues/costs
            if timesheet.amount >= 0 and timesheet.unit_amount >= 0:
                invoice_type = 'service_revenues' if (timesheet.so_line and timesheet.so_line.product_id.type == 'service') else 'other_revenues'
            else:
                invoice_type = 'other_costs'
```

#### `so_line` (compute, store, readonly=False)

Auto-determined via `_timesheet_determine_sale_line()`. Is recomputed only when:
- `is_so_line_edited` is False
- The timesheet has not been invoiced (`_is_not_billed()`)

```python
@api.depends('task_id.sale_line_id', 'project_id.sale_line_id', 'employee_id', 'project_id.allow_billable')
def _compute_so_line(self):
    for timesheet in self.filtered(lambda t: not t.is_so_line_edited and t._is_not_billed()):
        timesheet.so_line = timesheet.project_id.allow_billable and timesheet._timesheet_determine_sale_line()
```

#### `_domain_so_line()` - Domain Construction with Domain() Class

Returns a `Domain()` object (Odoo 19 `Domain` class replacing list-style domains) defining which SOLs are selectable on timesheets. Combines:
1. `sale_order_line._sellable_lines_domain()` - sellable products
2. `sale_order_line._domain_sale_line_service()` - service products
3. Commercial partner match against the timesheet's commercial partner

```python
def _domain_so_line(self):
    domain = Domain.AND([
        self.env['sale.order.line']._sellable_lines_domain(),
        self.env['sale.order.line']._domain_sale_line_service(),
        [
            ('order_partner_id.commercial_partner_id', '=', unquote('commercial_partner_id')),
        ],
    ])
    return str(domain)
```

> **L4 Note:** The use of `unquote()` in the domain means the literal string `'commercial_partner_id'` is passed to the client; the actual value substitution happens at the domain evaluation level. This is an Odoo 19 pattern for deferred domain variable injection.

---

### project.project (sale_timesheet extension)

> Extends `project.project` to add billing configuration, employee-SOL mapping, and timesheet profitability reporting.

**File:** `models/project_project.py`

#### Fields

| Field | Type | Compute/Store | Purpose |
|-------|------|--------------|---------|
| `pricing_type` | Selection | compute/search | Task rate / Fixed rate / Employee rate |
| `sale_line_employee_ids` | One2many | No | Per-employee SOL and cost mapping |
| `timesheet_product_id` | Many2one | compute/store | Default "Time" product for timesheet billing |
| `warning_employee_rate` | Boolean | compute | Warns if timesheets exist for unmapped employees |
| `billing_type` | Selection | compute | not_billable / manually |
| `allocated_hours` | Float | No | Hours budgeted for the project |

**`pricing_type` Selection Options:**
```python
[
    ('task_rate',     'Task rate'),
    ('fixed_rate',    'Project rate'),
    ('employee_rate', 'Employee rate')
]
```

**`billing_type` Selection Options:**
```python
[
    ('not_billable', 'not billable'),
    ('manually',     'billed manually'),
]
```

#### `pricing_type` (compute, search)

Automatically derived from the project's configuration:
```python
@api.depends('sale_line_id', 'sale_line_employee_ids', 'allow_billable')
def _compute_pricing_type(self):
    billable_projects = self.filtered('allow_billable')
    for project in billable_projects:
        if project.sale_line_employee_ids:
            project.pricing_type = 'employee_rate'
        elif project.sale_line_id:
            project.pricing_type = 'fixed_rate'
        else:
            project.pricing_type = 'task_rate'
    (self - billable_projects).update({'pricing_type': False})
```

Search method supports `operator='in'` with values from the selection tuple plus `False`:
```python
def _search_pricing_type(self, operator, value):
    if operator != 'in':
        return NotImplemented
    # Returns compound domain for each pricing type value using Domain.OR
    domains = []
    if 'task_rate' in value:
        domains.append([('sale_line_employee_ids', '=', False), ('sale_line_id', '=', False), ('allow_billable', '=', True)])
    if 'fixed_rate' in value:
        domains.append([('sale_line_employee_ids', '=', False), ('sale_line_id', '!=', False), ('allow_billable', '=', True)])
    if 'employee_rate' in value:
        domains.append([('sale_line_employee_ids', '!=', False), ('allow_billable', '=', True)])
    if False in value:
        domains.append([('allow_billable', '=', False)])
    return Domain.OR(domains)
```

---

### project.task (sale_timesheet extension)

> Extends `project.task` to support billable task pricing, remaining hours tracking, and automatic SOL assignment.

**File:** `models/project_task.py`

#### Fields

| Field | Type | Compute/Store | Purpose |
|-------|------|--------------|---------|
| `sale_order_id` | Many2one | No | Domain-filtered link to sale order |
| `pricing_type` | Selection | related | Mirrors project.pricing_type |
| `is_project_map_empty` | Boolean | compute | True if project has no employee mappings |
| `has_multi_sol` | Boolean | compute | True if task has timesheets with different SOLs |
| `timesheet_product_id` | Many2one | related | Inherited from project |
| `remaining_hours_so` | Float | compute/search | Time remaining on the SOL |
| `remaining_hours_available` | Boolean | related | From sale_line_id |
| `last_sol_of_customer` | Many2one | compute | Most recent SOL with remaining hours |

#### `remaining_hours_so` (compute, search, compute_sudo)

Tracks the time remaining on the SOL linked to the task, considering timesheet entries already logged.

```python
@api.depends('sale_line_id', 'timesheet_ids', 'timesheet_ids.unit_amount')
def _compute_remaining_hours_so(self):
    timesheets = self.timesheet_ids.filtered(
        lambda t: t.task_id.sale_line_id in (t.so_line, t._origin.so_line)
        and t.so_line.remaining_hours_available
    )
    mapped_remaining_hours = {
        task._origin.id: task.sale_line_id and task.sale_line_id.remaining_hours or 0.0
        for task in self
    }
    uom_hour = self.env.ref('uom.product_uom_hour')

    for timesheet in timesheets:
        delta = 0
        # Add back the original amount (undoing)
        if timesheet._origin.so_line == timesheet.task_id.sale_line_id:
            delta += timesheet._origin.unit_amount
        # Subtract the new amount
        if timesheet.so_line == timesheet.task_id.sale_line_id:
            delta -= timesheet.unit_amount
        if delta:
            mapped_remaining_hours[timesheet.task_id._origin.id] += \
                timesheet.product_uom_id._compute_quantity(delta, uom_hour)

    for task in self:
        task.remaining_hours_so = mapped_remaining_hours[task._origin.id]
```

> **L3 Edge Case:** The code acknowledges that `timesheet.so_line` sticks to its old value even when the SOL changes on the task. This means if you change the task's SOL, existing timesheets may show incorrect remaining hours until the timesheets are recomputed.

---

### project.sale.line.employee.map

> Maps employees to specific SOLs for `employee_rate` pricing. This is the core model for billing different employees at different rates on the same project.

**File:** `models/project_sale_line_employee_map.py`

**`_name = 'project.sale.line.employee.map'`**

#### Fields

| Field | Type | Compute/Store | Purpose |
|-------|------|--------------|---------|
| `project_id` | Many2one | No | The billable project |
| `employee_id` | Many2one | No | The employee (with domain preventing duplicates) |
| `existing_employee_ids` | Many2many | compute | Already-mapped employees in this project |
| `sale_line_id` | Many2one | compute/store | SOL to bill this employee's time against |
| `sale_order_id` | Many2one | related | Derived from project |
| `company_id` | Many2one | related | Derived from project |
| `partner_id` | Many2one | related | Derived from project |
| `price_unit` | Float | compute | Mirrors SOL's unit price |
| `currency_id` | Many2one | compute | Mirrors SOL's currency |
| `cost` | Monetary | compute/store | Hourly cost for this employee on this project |
| `display_cost` | Monetary | compute/inverse | Cost displayed in project's encoding UoM |
| `cost_currency_id` | Many2one | related | Employee's currency |
| `is_cost_changed` | Boolean | compute | True if cost manually differs from employee's default |

#### Uniqueness Constraint

```python
_uniqueness_employee = models.Constraint(
    'UNIQUE(project_id, employee_id)',
    'An employee cannot be selected more than once in the mapping. '
    'Please remove duplicate(s) and try again.',
)
```

---

### sale.order.line (sale_timesheet extension)

> Extends `sale.order.line` to compute delivered quantities from timesheets and track remaining hours on prepaid services.

**File:** `models/sale_order_line.py`

#### Fields

| Field | Type | Compute/Store | Purpose |
|-------|------|--------------|---------|
| `qty_delivered_method` | Selection | No | Adds 'timesheet' to parent's selection |
| `analytic_line_ids` | One2many | No | Analytic lines not linked to projects |
| `remaining_hours_available` | Boolean | compute | True for ordered_prepaid time products |
| `remaining_hours` | Float | compute/store | Hours left to deliver on the SOL |
| `has_displayed_warning_upsell` | Boolean | No | Prevents repeated upsell alerts |
| `timesheet_ids` | One2many | No | Timesheet records linked to this SOL |

---

### sale.order (sale_timesheet extension)

> Extends `sale.order` with timesheet tracking summaries, upsell activity creation, and timesheet-to-invoice linking.

**File:** `models/sale_order.py`

#### Fields

| Field | Type | Compute/Store | Purpose |
|-------|------|--------------|---------|
| `timesheet_count` | Float | compute | Number of timesheet entries on the SO |
| `timesheet_encode_uom_id` | Many2one | related | Company's encoding UoM |
| `timesheet_total_duration` | Integer | compute | Total hours/days logged on the SO |
| `show_hours_recorded_button` | Boolean | compute | Show "Hours Recorded" button |

---

### account.move (sale_timesheet extension)

> Extends `account.move` to track linked timesheets and compute total duration.

**File:** `models/account_move.py`

#### Fields

| Field | Type | Compute/Store | Purpose |
|-------|------|--------------|---------|
| `timesheet_ids` | One2many | No | Timesheets linked to this invoice |
| `timesheet_count` | Integer | compute | Number of linked timesheets |
| `timesheet_encode_uom_id` | Many2one | related | Company's encoding UoM |
| `timesheet_total_duration` | Integer | compute | Total hours logged on this invoice |

---

## Core Concepts

---

### TIMESHEET_INVOICE_TYPES

Nine classification types for timesheet lines used throughout billing, reporting, and portal visibility:

| Type | Label | When Applied |
|------|-------|-------------|
| `billable_time` | Billed on Timesheets | `delivered_timesheet` policy, negative or zero revenue sign |
| `billable_fixed` | Billed at Fixed Price | `ordered_prepaid` policy OR `invoice_policy='order'` |
| `billable_milestones` | Billed on Milestones | `delivered_milestones` service type |
| `billable_manual` | Billed Manually | Manual service type OR `billing_type='manually'` on project |
| `non_billable` | Non-Billable | No SOL and project is not manual billing |
| `timesheet_revenues` | Timesheet Revenues | `delivered_timesheet` policy with positive revenue sign (revenue recognition) |
| `service_revenues` | Service Revenues | No project but has SOL with service product |
| `other_revenues` | Other revenues | No project, no service SOL |
| `other_costs` | Other costs | Negative amounts without a project |

---

### Pricing Types

Three pricing strategies determine how SOLs are auto-assigned to timesheets:

#### 1. Task Rate (`task_rate`)

**Use case:** Bill different services at different rates to different customers. Each task can have a different SOL.

**Behavior:**
- Project has no `sale_line_id` and no employee mappings
- SOL is determined by `task_id.sale_line_id`
- Changing a task's SOL automatically re-links unbilled timesheets

#### 2. Fixed Rate (`fixed_rate`)

**Use case:** Bill a service at a fixed rate per hour/day regardless of the employee. The project has a single SOL.

**Behavior:**
- Project has `sale_line_id` but no employee mappings
- Task has no explicit SOL (or inherits from project)
- Timesheets without a task use the project's SOL
- Timesheets with a task use the task's SOL

#### 3. Employee Rate (`employee_rate`)

**Use case:** Employees deliver the same service at different rates (e.g., junior vs. senior consultant). Requires per-employee SOL mapping.

**Behavior:**
- Project has `sale_line_employee_ids` mappings
- Each employee is mapped to a specific SOL (and optionally a specific cost)
- `_timesheet_determine_sale_line()` looks up the employee in the mapping
- A warning is shown if an employee has logged time but is not in the mapping

---

### SOL Determination Cascade

When a timesheet is created or its SOL is recomputed, the `_timesheet_determine_sale_line()` method follows this 4-step cascade:

```
Step 1: No task?
  ├─ Project uses employee_rate?
  │   └─ Look up employee in project.sale_line_employee_ids
  │       └─ Found? Return mapped SOL
  │       └─ Not found? Continue
  └─ Project has sale_line_id?
      └─ Return project.sale_line_id

Step 2: Task exists and is billable with SOL?
  ├─ Task pricing_type is task_rate or fixed_rate?
  │   └─ Return task.sale_line_id

  └─ Task pricing_type is employee_rate?
      ├─ Look up employee in project.sale_line_employee_ids
      │   └─ Found with matching commercial partner?
      │       └─ Return mapped SOL
      │   └─ Not found or partner mismatch?
      └─ Return task.sale_line_id (fallback)

Step 3: No matching SOL found
  └─ Return False (non-billable)
```

**Key constraint:** The SOL from the employee mapping must have a `commercial_partner_id` matching the task's commercial partner.

---

### Service Policies

The module introduces `delivered_timesheet` as a new service policy alongside existing ones:

| Policy | Invoice Policy | Service Type | Delivery Computation | Invoicing |
|--------|---------------|-------------|---------------------|-----------|
| `ordered_prepaid` | order | timesheet | From timesheets | Full qty invoiced at order |
| `delivered_timesheet` | delivery | timesheet | From timesheets | Per timesheet entry |
| `delivered_milestones` | delivery | milestones | Manual | Per milestone |
| `delivered_manual` | delivery | manual | Manual | Manual |

---

## L3: Edge Cases

### Cross-Model Edge Cases

**1. SOL change on task after timesheets logged**
The `_compute_remaining_hours_so` code acknowledges that `timesheet.so_line` sticks to its old value even when the task's SOL changes. The `remaining_hours_so` field may show stale values until timesheets are individually recomputed.

**2. Employee mapping with partner mismatch**
If a project's partner changes, the `_compute_sale_line_id()` method on the mapping automatically clears SOLs where the commercial partner doesn't match. This can make previously-billable timesheets non-billable.

**3. Credit note after partial invoice**
When only some timesheets are invoiced (via date range), a subsequent credit note reversal clears the invoice link only for timesheets that were actually on the credited invoice. Other timesheets remain invoiced.

**4. Multi-company timesheet billing**
The `_timesheet_preprocess_get_accounts()` method validates mandatory analytic plans from the timesheet's company, not the SOL's company. If the company has different mandatory plans than the SOL's distribution, a `ValidationError` is raised.

**5. Upsell warning after credit note**
After a credit note is posted, the `has_displayed_warning_upsell` flag is NOT reset. If the same SOL crosses the threshold again, the upsell warning will fire. However, `_reset_has_displayed_warning_upsell_order_lines()` resets it when the delivered qty exactly equals ordered qty.

**6. Project `allow_billable` toggled off**
When `allow_billable` is set to False, existing unbilled timesheets have their SOL cleared via `write()`. Already-invoiced timesheets are unaffected.

**7. Draft invoice line deletion**
When a draft invoice line with a timesheet-service product is deleted, the `unlink()` override clears the `timesheet_invoice_id` on linked timesheets, making them available for re-invoicing.

**8. Employee with no user account**
`_timesheet_determine_sale_line()` falls back to `self.env.user.employee_id` when `employee_id` is not set on the timesheet. This works for timesheets created by users with linked employee records.

**9. Invoice reversal with modify=True**
The `account.move.reversal` wizard with `is_modify=True` clears invoice links on all timesheets linked to the original invoice, even those not in the reversal's `move_ids`. This is intentional - the entire invoice is being reversed.

**10. UoM mismatch between SOL and timesheet**
`_timesheet_convert_sol_uom()` and the analysis report SQL handle UoM conversion using the `factor` system.

---

## L4: Performance & Security

### Performance Implications

**1. `_get_profitability_items_from_aal()`**
- Uses `sudo()._read_group()` for bulk aggregation - single query per project
- Currency conversion per group, not per record
- `record_ids` are only populated for approver users, avoiding large data transfers for regular users
- For non-timesheet projects, the method short-circuits and strips timesheet sections

**2. `_compute_remaining_hours_so()`**
- Iterates over all timesheets in the task's `timesheet_ids`
- `product_uom_id._compute_quantity()` is called per timesheet for UoM conversion
- Could be optimized by batching UoM conversions if many timesheets exist

**3. `_recompute_qty_to_invoice()`**
- Searches all timesheets matching the SOLs and date range via `Domain()` objects
- Credit note handling requires an additional `reversed_entry_id` lookup
- Called on every invoice creation when date range is provided

**4. `_compute_timesheet_total_duration()` on sale.order**
- Uses `_read_group` aggregation for O(1) query regardless of timesheet count
- Converts UoM per order (not per timesheet) in Python

**5. Employee mapping lookup in `_timesheet_determine_sale_line()`**
- For `employee_rate` with a task, uses `filter()` on `sale_line_employee_ids`
- This is a Python-side filter on an already-loaded recordset (efficient)
- No additional database query if `sale_line_employee_ids` is prefetched

### Security Concerns

**1. `sudo()` usage**
Multiple methods use `sudo()` for cross-record access:
- `_compute_timesheet_invoice_type` uses `compute_sudo=True`
- `_compute_commercial_partner` uses `sudo()` for partner access
- Timesheet search and write in `_link_timesheets_to_invoice()` uses `sudo()`
- `AccountAnalyticLine._timesheet_preprocess_get_accounts()` uses `so_line.sudo().analytic_distribution`

These are necessary for timesheet officers accessing project data but should be reviewed if custom security rules are added to `account.analytic.line`.

**2. `is_cost_changed` tracking**
The `is_cost_changed` flag on `project.sale.line.employee.map` uses direct comparison between `cost` and `employee_id.hourly_cost`. If an employee's cost is updated, the map entry needs to be recomputed. The `_compute_cost()` method removes the field from the recompute set when `is_cost_changed` is True, which prevents auto-update. This is intentional (manual overrides should persist) but means cost changes on employees do not propagate to existing mappings.

**3. Timesheet modification after invoice**
`_check_can_write()` prevents modifying timesheets linked to delivery-policy SOLs that are posted-invoiced. However, this check runs on `write()`, not on individual field updates. For cancellation, `_is_not_billed()` allows re-linking if the invoice is cancelled. Credit notes that don't use the reversal wizard may leave orphaned links.

**4. Access rights on `project.sale.line.employee.map`**
The mapping model requires access rights separate from `project.project`. Users who can edit project employee mappings can change which SOL an employee's time is billed to. This should be restricted to project managers.

---

## Odoo 18 to 19 Changes

### `Domain()` Class Replacement for List Domains

**Before (Odoo 18):** Domains were Python lists.
```python
domain = ['&', ('field1', '=', value1), ('field2', '!=', False)]
domain &= [('field3', '>=', value3)]
```

**After (Odoo 19):** Uses the `Domain()` class for composable, type-safe domains.
```python
from odoo.fields import Domain
domain = Domain.AND([
    self.env['sale.order.line']._sellable_lines_domain(),
    self.env['sale.order.line']._domain_sale_line_service(),
    [('order_partner_id.commercial_partner_id', '=', unquote('commercial_partner_id'))],
])
return str(domain)
```

The `Domain()` class enables:
- Type-checked domain composition with `Domain.AND()`, `Domain.OR()`
- Safe interpolation via `unquote()` for deferred variable injection
- String serialization for storage in `domain` field attributes

### `billing_type` on project.project

Odoo 18 used `pricing_type` to determine whether a project was billable. Odoo 19 introduces a separate `billing_type` field with values `not_billable` and `manually`. The `pricing_type` still handles the rate determination (task/fixed/employee), while `billing_type` handles whether the project produces invoices automatically or manually.

### `timesheet_product_id` Field

The field was introduced or significantly modified in Odoo 19 to replace the ad-hoc product lookup. It stores a reference to the "Time" product (`sale_timesheet.time_product`) that serves as the default product for timesheet billing.

### Portal Controller Inheritance Change

The `SaleTimesheetCustomerPortal` now inherits from `TimesheetCustomerPortal` (from `hr_timesheet`), adding SOL and invoice search capabilities to the portal timesheet list.

### `_get_timesheets_to_merge()` Filter

Added `timesheet_invoice_id.state != 'posted'` filter to prevent merging timesheets that have been posted-invoiced. Previously, all non-invoiced timesheets could be merged regardless of invoice state.

### `_is_readonly()` Enhancement

Now checks `_is_not_billed()` in addition to the parent's readonly check:
```python
def _is_readonly(self):
    return super()._is_readonly() or not self._is_not_billed()
```

---

## Hooks

### Post-Init Hook: `_sale_timesheet_post_init()`

Runs on module installation (not upgrade). Migrates existing service products:
- Finds products with `type='service'`, `invoice_policy='order'`, `service_type='manual'`, and `service_tracking` in `['no', 'task_global_project', 'task_in_project', 'project_only']`
- Sets their `service_type` to `'timesheet'`
- Recomputes their `service_policy`

```python
def _sale_timesheet_post_init(env):
    products = env['product.template'].search([
        ('type', '=', 'service'),
        ('service_tracking', 'in', ['no', 'task_global_project', 'task_in_project', 'project_only']),
        ('invoice_policy', '=', 'order'),
        ('service_type', '=', 'manual'),
    ])
    for product in products:
        product.service_type = 'timesheet'
        product._compute_service_policy()
```

### Uninstall Hook: `uninstall_hook()`

Resets record rules on analytic lines to allow all access:
```python
def uninstall_hook(env):
    env.ref("account.account_analytic_line_rule_billing_user").write(
        {'domain_force': "[(1, '=', 1)]"}
    )
    env.ref("account.account_analytic_line_rule_readonly_user").write(
        {'domain_force': "[(1, '=', 1)]"}
    )
```

---

## Portal Integration

### Controllers

**`sale_timesheet.controllers.portal.PortalProjectAccount`**
- Inherits from both `PortalAccount` and `ProjectCustomerPortal`
- `_invoice_get_page_view_values()`: Adds timesheet list to the invoice portal page, filtering by the invoice's SOLs and applying the portal domain
- `portal_my_tasks_invoices()`: Lists invoices linked to a task's sale order

**`sale_timesheet.controllers.portal.SaleTimesheetCustomerPortal`**
- Inherits from `TimesheetCustomerPortal` (from `hr_timesheet`)
- Extends search inputs with `'so'` (search by SOL) and `'invoice'` (search by invoice)
- Extends groupby with `'so_line'` and `'timesheet_invoice_id'`
- Extends sortings with SOL and invoice options
- Overrides `_task_get_page_view_values()` to add sale order and invoice links to the task portal page

### Portal Search Logic

```python
# Search by SOL name
if search_in == 'so':
    return Domain('so_line', 'ilike', search) | Domain('so_line.order_id.name', 'ilike', search)

# Search by invoice reference
elif search_in == 'invoice':
    invoices = request.env['account.move'].sudo().search([
        '|', ('name', 'ilike', search), ('id', 'ilike', search)
    ])
    return Domain(request.env['account.analytic.line']._timesheet_get_sale_domain(
        invoices.mapped('invoice_line_ids.sale_line_ids'), invoices
    ))
```

---

## Dependencies

```
sale_timesheet
├── sale_project          # Project creation from SOLs, task generation
│   └── project           # Core project management
└── hr_timesheet          # Timesheet entry model, employee hourly cost
    ├── hr                # Employee management
    └── account_analytic  # Analytic lines
```

---

## Related Documentation

- [[Modules/Project]] - Core project management
- [[Modules/Sale]] - Sales order and invoicing
- [[Modules/hr_timesheet]] - Time tracking foundation
- [[Core/API]] - Domain() class and ORM patterns
- [[Patterns/Workflow Patterns]] - State machine and action patterns

---

## L4: SOLog Computation Logic

### How `_recompute_qty_to_invoice()` Works

The `_recompute_qty_to_invoice()` method on `sale.order.line` recalculates `qty_to_invoice` for timesheet-service products using a configurable date range. This is the core mechanism behind the invoice wizard's period-based timesheet selection.

**File:** `models/sale_order_line.py`, lines 150-181

**Step-by-step flow:**

```
1. Filter lines: only SOLs whose product has delivered_timesheet policy
2. Build domain for timesheet search:
   a. Base domain: project_id != False (must be actual timesheets, not analytic)
   b. Credit note handling:
      - Find posted out_refund moves that reverse entries
      - If timesheet was invoiced to a credit note (reversed_entry_id),
        it should be re-invoicable
   c. Exclude already-invoiced: timesheet_invoice_id IS NULL OR
      timesheet_invoice_id is cancelled (non-legacy) OR
      timesheet_invoice_id is reversed (payment_state='reversed')
3. If start_date: add date >= start_date to domain
4. If end_date:   add date <= end_date to domain
5. Search timesheets via sudo(), get unit_amount per SOL
6. Write qty_to_invoice on each SOL; preserve invoice_status if qty is 0
```

**Credit note handling (critical detail):**
The domain `(timesheet_invoice_id.state', '=', 'posted') & timesheet_invoice_id IN refund_account_moves.ids` means: if a timesheet was invoiced to a credit note that has been posted (i.e., the reversal is active), the timesheet becomes re-linkable. This handles the scenario where a partial invoice is credited — the credited timesheets should be available for the next invoice.

**UoM note:** `_get_delivered_quantity_by_analytic()` sums unit amounts directly from the analytic lines. The UoM factor is applied downstream in the invoice line creation, not here.

---

### `account_move_line.unlink()` — Re-enabling Timesheets for Re-invoice

When a draft invoice line with a timesheet-service product is deleted, the `unlink()` override on `account.move.line` ensures those timesheets are not permanently locked to the invoice.

**File:** `models/account_move_line.py`, lines 28-54

**Trigger conditions (all must be true simultaneously):**
- `move_id.move_type == 'out_invoice'`
- `move_id.state == 'draft'`
- `sale_line_ids.product_id.invoice_policy == 'delivery'`
- `sale_line_ids.product_id.service_type == 'timesheet'`
- The line being deleted is in `self.ids`

**Algorithm:**

```
1. Search all draft invoice lines in self (grouped by move_id)
2. For each move, find timesheets where:
   - timesheet_invoice_id = that move_id
   - so_line is one of the SOLs in that move's lines
3. Clear timesheet_invoice_id on those matched timesheets
4. Delete the move line
```

The grouping step (`sale_line_ids_per_move`) ensures timesheets are only unlinked if their SOL is actually on the same invoice move being modified. This prevents accidentally unlinking timesheets from unrelated moves.

---

### `account.move.action_post()` — Credit Note Link Clearing

When a credit note is posted, `_link_timesheets_to_invoice()` is NOT called (credit notes are created by reversal, not `_create_invoices`). Instead, `action_post()` handles the unlinking directly.

**File:** `models/account_move.py`, lines 96-105

**Trigger:** `move_type == 'out_refund'` with `reversed_entry_id` set (posted credit note from reversal)

**Logic:**

```python
credit_notes = self.filtered(lambda move: move.move_type == 'out_refund' and move.reversed_entry_id)
timesheets_sudo = self.env['account.analytic.line'].sudo().search([
    ('timesheet_invoice_id', 'in', credit_notes.reversed_entry_id.ids),
    ('so_line', 'in', credit_notes.invoice_line_ids.sale_line_ids.ids),
    ('project_id', '!=', False),
])
timesheets_sudo.write({'timesheet_invoice_id': False})
```

The `so_line IN credit_notes.invoice_line_ids.sale_line_ids` filter ensures only timesheets from the exact SOLs that were on the original invoice are unlinked. This handles partial credit notes correctly — timesheets linked to other SOLs on the same invoice are not disturbed.

---

### `account_move_reversal.py` — `is_modify=True` Invoice Reversal

The reversal wizard's `reverse_moves(is_modify=True)` path handles full invoice reversal (not credit note). When `is_modify=True`, the original invoice is cancelled and replaced, which means all its timesheet links must be cleared.

**File:** `models/account_move_reversal.py`, lines 7-15

**Trigger:** User chooses "Cancel Invoice" or "Modify Invoice" in the reversal wizard (both set `is_modify=True`)

**Key design decision:** The search for timesheets to unlink does NOT scope by `so_line`. This is intentional — a full invoice reversal cancels all line items, so all timesheets linked to that invoice should be released, regardless of which SOL they belong to.

**Comparison with `action_post()` credit note handling:**

| Scenario | Method | Scope by so_line |
|----------|--------|-----------------|
| Credit note posted (out_refund) | `action_post()` | Yes — only timesheets from credited SOLs |
| Full invoice reversal (is_modify=True) | `reverse_moves()` | No — all timesheets on the invoice |

---

### `SaleAdvancePaymentInv` Wizard — Period-Based Timesheet Invoicing

The advance invoice wizard extends the standard "Invoice Order" flow with optional date range filtering for timesheet-service products.

**File:** `wizard/sale_make_invoice_advance.py`

**New fields:**

| Field | Purpose |
|-------|---------|
| `date_start_invoice_timesheet` | Only timesheets on/after this date are included |
| `date_end_invoice_timesheet` | Only timesheets on/before this date are included |
| `invoicing_timesheet_enabled` | True if any SOL has a timesheet-service product with "to invoice" status |

**`invoicing_timesheet_enabled` compute logic:**
```python
# Only True if at least one SOL on any selected SO:
#   1. Has invoice_status == 'to invoice' (has something to invoice)
#   2. AND its product passes _is_delivered_timesheet()
#      (service + delivered_timesheet policy)
# This prevents the date fields from showing for non-timesheet SOs
```

**Invoicing flow with date range:**

```
Wizard._create_invoices()
  └─ if advance_payment_method == 'delivered'
       AND invoicing_timesheet_enabled:
       └─ if date range specified:
            SOL._recompute_qty_to_invoice(start, end)
            # Adjusts qty_to_invoice so only period timesheets count
         └─ SO._create_invoices(
                context={
                  timesheet_start_date: start,
                  timesheet_end_date: end
                }
             )
              └─ AccountMove._link_timesheets_to_invoice(start, end)
                 # Uses the date range to link only in-period timesheets
```

**`_get_range_dates()` hook (in `account.move`):**
Returns `(None, None)` by default. Override this in a custom module to auto-populate date range from the SO's confirmation date or a fiscal period, enabling automatic period-based invoicing without manual wizard input.

---

## L4: Product Extensions

### `product.product` — Time Product Protection

The `product.product` model is extended to protect the "Time" product (`sale_timesheet.time_product`) from accidental archival, deletion, or company assignment.

**File:** `models/product_product.py`

**`_is_delivered_timesheet()` — Detection method:**

```python
def _is_delivered_timesheet(self):
    self.ensure_one()  # Must be called on a single record
    return self.type == 'service' and self.service_policy == 'delivered_timesheet'
```

This is the canonical check used throughout `sale_timesheet` to determine if a product should participate in timesheet-based qty_delivered and qty_to_invoice computation. It is also used in the invoice wizard's `invoicing_timesheet_enabled` compute.

**`ondelete` protection:**
```python
@api.ondelete(at_uninstall=False)
def _unlink_except_master_data(self):
    time_product = self.env.ref('sale_timesheet.time_product')
    if time_product in self:
        raise ValidationError(...)
```

The `at_uninstall=False` flag means this check runs during normal operation but is skipped when the module is being uninstalled (allowing cleanup).

**`write()` protection — archival and company linking:**

```python
if ('active' in vals and not vals['active']) or ('company_id' in vals and vals['company_id']):
    # Blocks archiving or assigning company to the time product
```

Both conditions are checked separately — the time product cannot be archived, and it cannot be linked to a specific company (must remain multi-company).

---

### `product.template` — `delivered_timesheet` Service Policy

**File:** `models/product_template.py`

**`_selection_service_policy()` — Injection point:**

```python
def _selection_service_policy(self):
    service_policies = super()._selection_service_policy()
    service_policies.insert(1, ('delivered_timesheet', _('Based on Timesheets')))
    return service_policies
```

Inserted at position 1 (after `ordered_prepaid`) to place timesheet-based billing as the second option in the dropdown.

**`service_type` extension:**
```python
service_type = fields.Selection(selection_add=[
    ('timesheet', 'Timesheets on project (one fare per SO/Project)'),
], ondelete={'timesheet': 'set manual'})
```

The `ondelete='set manual'` means: if a product with `service_type='timesheet'` has its template deleted, the service_type reverts to `'manual'` rather than cascading to a full product deletion.

**`service_upsell_threshold` and `service_upsell_threshold_ratio`:**

```python
service_upsell_threshold = fields.Float('Threshold', default=1, ...)
# Default of 1 means the warning fires when qty_delivered == product_uom_qty
# (100% of ordered hours consumed)

service_upsell_threshold_ratio = fields.Char(
    compute='_compute_service_upsell_threshold_ratio', ...)
# Display string: "(1 Unit = X Hours)" when UoM is not hour
# False when UoM is already hour (no conversion needed)
```

The threshold is compared against `qty_delivered / (product_uom_qty * threshold) > 0` in `_get_prepaid_service_lines_to_upsell()`. Default `1` means warning fires at 100% consumed. Setting to `0.8` would fire at 80%.

**`_get_service_to_general_map()` — Policy routing:**

```python
def _get_service_to_general_map(self):
    return {
        **super()._get_service_to_general_map(),
        'delivered_timesheet': ('delivery', 'timesheet'),
        'ordered_prepaid':      ('order',    'timesheet'),
    }
```

Returns `(invoice_policy, service_type)` tuples. Both timesheet policies map to `service_type='timesheet'`. This is used by `sale_order_line._compute_qty_delivered_method()` to route SOLs to the timesheet delivery path.

**`_get_onchange_service_policy_updates()` — Project auto-clearing:**

```python
# When service_policy changes to 'delivered_timesheet',
# and tracking != 'no':
#   - If project_id exists but allow_timesheets=False: clear project_id
#   - If project_template_id exists but allow_timesheets=False: clear it
```

This prevents creating a timesheet-service product linked to a project that does not support timesheets.

---

## L4: Timesheets Analysis Report — SQL Structure

The `timesheets.analysis.report` is extended to join timesheet data with SOL and product tables, enabling revenue and margin computation per timesheet line.

**File:** `report/timesheets_analysis_report.py`

### Full Query Structure

```sql
SELECT A.*,
    (timesheet_revenues + A.amount) AS margin,
    (A.unit_amount - billable_time) AS non_billable_time
FROM (
    [super()._select() + sale_extensions]  -- SELECT
    [super()._from() + sale_joins]          -- FROM
    [super()._where()]                      -- WHERE
) A
```

### `_select()` Extensions

```sql
A.order_id AS order_id,
A.so_line AS so_line,
A.timesheet_invoice_type AS timesheet_invoice_type,
A.timesheet_invoice_id AS timesheet_invoice_id,

-- Timesheet revenues: hours * unit price, with UoM correction
CASE
    WHEN A.order_id IS NULL OR T.service_type in ('manual', 'milestones')
    THEN 0
    WHEN T.invoice_policy = 'order' AND SOL.qty_delivered != 0
    THEN (SOL.price_subtotal / SOL.qty_delivered)
         * (A.unit_amount / sol_product_uom.factor * a_product_uom.factor)
    ELSE A.unit_amount * SOL.price_unit
         / sol_product_uom.factor * a_product_uom.factor
END AS timesheet_revenues,

CASE WHEN A.order_id IS NULL THEN 0 ELSE A.unit_amount END AS billable_time
```

**Revenue calculation logic:**

| Condition | Formula | Rationale |
|-----------|---------|-----------|
| No SOL, or manual/milestones service | `0` | Revenue already recognized via milestones/manual |
| `invoice_policy='order'` with qty_delivered | `(price_subtotal/qty_delivered) * (timesheet_hours)` | Average rate per delivered unit |
| Otherwise (delivery policy) | `unit_amount * price_unit / sol_uom_factor * aal_uom_factor` | Direct rate × hours with UoM normalization |

**UoM normalization:** `sol_product_uom.factor` and `a_product_uom.factor` normalize both the SOL's UoM and the AAL's encoding UoM to a common reference (1 unit = 1). This ensures correct revenue math even when timesheets are logged in days and SOL is priced in hours.

### `_from()` Extensions

```sql
LEFT JOIN sale_order_line SOL ON A.so_line = SOL.id
LEFT JOIN uom_uom sol_product_uom ON sol_product_uom.id = SOL.product_uom_id
INNER JOIN uom_uom a_product_uom ON a_product_uom.id = A.product_uom_id
LEFT JOIN product_product P ON P.id = SOL.product_id
LEFT JOIN product_template T ON T.id = P.product_tmpl_id
```

- `INNER JOIN a_product_uom` — AAL must always have a UoM; this is guaranteed by the base report
- `LEFT JOIN` on SOL tables — timesheets without a SOL still appear in the report with NULL values; they contribute to `non_billable_time` and `other_costs`

### Margin Computation

```sql
margin = timesheet_revenues + A.amount
```

Where `A.amount` is the cost (negative for costs, positive for revenues from the base report). This gives `margin = timesheet_revenues - timesheet_costs`.

---

## L4: Portal & Controller Architecture

### `PortalProjectAccount` — Dual Inheritance Pattern

**File:** `controllers/portal.py`, lines 16-56

```python
class PortalProjectAccount(PortalAccount, ProjectCustomerPortal):
```

This class uses **diamond inheritance** — it inherits from two base classes that themselves inherit from a common ancestor. The Method Resolution Order (MRO) determines which parent's methods are called by `super()`.

**What each parent provides:**
- `PortalAccount` (from `account`): Invoice portal page, invoice access control
- `ProjectCustomerPortal` (from `project`): Task portal page, task access control

**What this class adds:**
- `_invoice_get_page_view_values()`: Decorates the invoice page with a timesheet list. The domain is constructed by:
  1. Intersecting the standard timesheet portal domain (`_timesheet_get_portal_domain()`)
  2. With a sale-domain that filters timesheets linked to the invoice's SOLs via `_timesheet_get_sale_domain()`
- `portal_my_tasks_invoices()`: New route `/my/tasks/<id>/orders/invoices` that shows all invoices linked to the task's sale order

**Design rationale:** Rather than overriding a single portal controller, the diamond pattern merges two existing portal domains (account + project) into one unified view.

---

### `SaleTimesheetCustomerPortal` — Portal Search/Groupby Extension

**File:** `controllers/portal.py`, lines 59-122

Extends `TimesheetCustomerPortal` (from `hr_timesheet`) with SOL and invoice-aware search and grouping.

**New search inputs:**
- `'so'`: Searches by SOL name (`so_line.name`) or SO name (`so_line.order_id.name`)
- `'invoice'`: Searches by invoice reference, then resolves to timesheets via `_timesheet_get_sale_domain()`

**New groupby options:**
- `'so_line'`: Groups timesheets by sales order line
- `'timesheet_invoice_id'`: Groups timesheets by invoice

**`_task_get_page_view_values()` additions:**
The override adds SO and invoice links to the task portal sidebar. It catches `AccessError`/`MissingError` silently — if the user lacks access to the SO or invoice, those links simply don't appear without breaking the page.

```python
try:
    if task.sale_order_id and self._document_check_access('sale.order', ...):
        values['so_accessible'] = True
        # Append SO link to task_link_section
except (AccessError, MissingError):
    pass  # SO not accessible; link omitted silently
```

**`portal_my_timesheets()` override with default `groupby='so_line'`:**

```python
@http.route()
def portal_my_timesheets(self, *args, groupby='so_line', **kw):
    return super().portal_my_timesheets(*args, groupby=groupby, **kw)
```

Changes the default grouping from the `hr_timesheet` default to grouping by SOL, so customers see their timesheets organized by service item on the portal.

---

## L4: Expanded Odoo 18 to 19 Changes

### `timesheet_invoice_type` Field Addition

Odoo 18 did not have a stored `timesheet_invoice_type` on `account.analytic.line`. The field was added in Odoo 19 along with the `TIMESHEET_INVOICE_TYPES` constant. This enables:
- Filtering and grouping timesheets by billable type in views and reports
- The `timesheet_invoice_type` field on `timesheets.analysis.report`
- The portal search/groupby by billable type

### `pricing_type` / `billing_type` Separation

Odoo 18 used a single `pricing_type` field on `project.project` with values including `billing_type`-like semantics. Odoo 19 splits this:
- `pricing_type`: How the rate is determined (`task_rate`/`fixed_rate`/`employee_rate`)
- `billing_type`: Whether invoicing happens automatically (`not_billable`) or manually (`manually`)

This separation allows a project to use `task_rate` pricing but be set to `manually` billing — timesheets are tracked and SOLs are assigned, but no automatic invoice is generated.

### `_is_not_billed()` — New Invoice Link State Check

Odoo 18 used a simpler check for whether a timesheet was editable/invoiced. Odoo 19 adds the `payment_state` edge case:

```python
def _is_not_billed(self):
    return not self.timesheet_invoice_id
        or (self.timesheet_invoice_id.state == 'cancel'
            and self.timesheet_invoice_id.payment_state != 'invoicing_legacy')
```

The `invoicing_legacy` payment state exemption ensures that cancelled legacy invoices (pre-Odoo 19 migrated data) do not incorrectly unlock their timesheets for re-invoicing.

### `_get_prepaid_service_lines_to_upsell()` — Threshold Parameterization

In Odoo 18, the upsell warning fired at exactly 100% of ordered hours. Odoo 19 adds the `service_upsell_threshold` field on `product.template`, defaulting to `1` (maintaining backward compatibility) but allowing configuration per product.

### `account_move_line.unlink()` — Timesheet Re-enabling

This ORM override did not exist in Odoo 18. The ability to delete a draft invoice line and have its timesheets automatically become re-invoicable is a new Odoo 19 feature, preventing the "orphaned invoice link" failure mode.

### Portal Controller Dual-Inheritance Architecture

Odoo 18 had separate portal controllers for timesheets (`TimesheetCustomerPortal`) and projects (`ProjectCustomerPortal`). Odoo 19 introduces `PortalProjectAccount` to unify invoice + project portal access, and `SaleTimesheetCustomerPortal` extends the timesheet portal with SOL awareness. This reflects Odoo's trend toward merged sales-project-timesheet views in the customer portal.

---

## L4: Expanded Performance & Security

### Performance: `_link_timesheets_to_invoice()`

The method uses two-stage domain construction:
1. `_timesheet_domain_get_invoiced_lines()` builds the base domain (non-invoiced, or cancelled non-legacy, or reversed)
2. Optional date range adds `date >= start` and/or `date <= end` via `Domain &= Domain(...)`

All three `Domain` objects are composed in Python, then converted to a SQL domain string via `str(domain)` passed to `.search()`. This defers domain evaluation to the ORM's SQL layer.

**Performance note for large date ranges:** If `start_date` is absent but `end_date` is present, the domain `date <= end_date` still allows index use on `date`. However, without a lower bound, scanning all historical timesheets for a given SOL is required. For large SOs with years of timesheets, consider always providing a start date.

### Security: `_check_timesheet_can_be_billed()` — SOL Ownership Guard

```python
def _check_timesheet_can_be_billed(self):
    return self.so_line in (
        self.project_id.mapped('sale_line_employee_ids.sale_line_id')
        | self.task_id.sale_line_id
        | self.project_id.sale_line_id
    )
```

This method validates that the timesheet's SOL is one of the legitimate billable SOLs for this project. It is used as a guard in the `sale_timesheet` profitability computation but is **not enforced on write/create** — meaning a user who manually assigns an SOL to a timesheet is not blocked, but that timesheet will be excluded from the profitability panel and potentially from the portal invoice view. This is a UX-level control rather than a hard security boundary.

### Security: `create_project_employee_mapping` Context in `hr.employee`

The `hr.employee.default_get()` override:

```python
@api.model
def default_get(self, fields):
    result = super().default_get(fields)
    project_company_id = self.env.context.get('create_project_employee_mapping', False)
    if project_company_id:
        result['company_id'] = project_company_id
    return result
```

When creating an employee mapping from a billable project (triggered via project form), the context variable forces the employee being mapped to belong to the same company as the project. This prevents cross-company employee SOL mappings, which would create billing integrity issues. The context is set by `project_project._update_timesheets_sale_line_id()` when it creates mapping records.

### Security: `service_upsell_threshold` — Activity Injection Context

The upsell activity creation in `_compute_field_value()`:

```python
super(SaleOrder, upsellable_orders.with_context(mail_activity_automation_skip=True))._compute_field_value(field)
```

The `mail_activity_automation_skip` context prevents recursive upsell activity creation if the `_compute_field_value()` call itself triggers a write that would re-invoke the compute. This is a race condition guard, not a security feature.

### Security: `is_so_line_edited` — Manual Override Flag

When a user manually sets an SOL on a timesheet, `is_so_line_edited` is set to `True`. This flag permanently locks the SOL — `_compute_so_line()` will never auto-change it, even if the task's SOL changes, the project's SOL changes, or the employee mapping updates. This is a **deliberate design choice** to give users control over billing assignment, at the cost of potentially stale SOL assignments after project restructuring.

