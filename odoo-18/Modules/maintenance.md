---
Module: maintenance
Version: Odoo 18
Type: Business
---

# maintenance — Equipment Maintenance Management

**Module:** `maintenance`
**Odoo Version:** 18
**Source:** `~/odoo/odoo18/odoo/addons/maintenance/`

---

## Overview

The `maintenance` module manages equipment lifecycle maintenance, covering both preventive (scheduled) and corrective (reactive) maintenance. It tracks equipment inventory, schedules maintenance requests, monitors Mean Time Between Failure (MTBF) and Mean Time To Repair (MTTR), and integrates with email aliases for equipment-category-based ticket creation.

---

## Architecture

### Model Structure

```
maintenance.equipment                    # Equipment inventory
maintenance.equipment.category           # Equipment categorization with alias
maintenance.request                      # Maintenance tickets/work orders
maintenance.stage                       # Pipeline stages
maintenance.team                        # Team assignment and dashboard
maintenance.mixin                       # Abstract mixin for equipment-enabled models
res.config.settings                     # Configuration settings
```

### File Map

| File | Purpose |
|------|---------|
| `models/maintenance.py` | All core models |
| `models/res_config_settings.py` | Configuration panel |

---

## Core Models

### maintenance.equipment

**`maintenance.equipment`** represents a piece of equipment subject to maintenance.

**Inheritance:** `models.Model` + `mail.thread` + `mail.activity.mixin` + `maintenance.mixin`
** `_name`: `maintenance.equipment`
** `_description`: `"Maintenance Equipment"`
** `_check_company_auto`: `True`

#### Field Reference

**Identification**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` | Equipment name (required, translatable) |
| `display_name` | `Char` | Computed: `name/serial_no` if serial number exists |
| `serial_no` | `Char` | Serial/lot number. `unique` SQL constraint |
| `active` | `Boolean` | Archive flag (default `True`) |

**Classification**

| Field | Type | Description |
|-------|------|-------------|
| `category_id` | `Many2one(maintenance.equipment.category)` | Equipment category |
| `partner_id` | `Many2one(res.partner)` | Vendor/supplier |
| `partner_ref` | `Char` | Vendor reference number |
| `location` | `Char` | Physical location description |
| `model` | `Char` | Model name/number |
| `color` | `Integer` | Color for kanban display |

**Assignment**

| Field | Type | Description |
|-------|------|-------------|
| `owner_user_id` | `Many2one(res.users)` | Owner of the equipment. Subscribe owner to messages |

**Cost & Warranty**

| Field | Type | Description |
|-------|------|-------------|
| `cost` | `Float` | Equipment cost value |
| `warranty_date` | `Date` | Warranty expiration date |

**Tracking**

| Field | Type | Description |
|-------|------|-------------|
| `assign_date` | `Date` | Date equipment was assigned |
| `scrap_date` | `Date` | Date equipment was scrapped |

**Maintenance Metrics (from `maintenance.mixin`)**

| Field | Type | Description |
|-------|------|-------------|
| `mtbf` | `Integer` | Mean Time Between Failure (days). Computed from corrective maintenance requests |
| `mttr` | `Integer` | Mean Time To Repair (days). Average of `(close_date - request_date)` for done corrective requests |
| `latest_failure_date` | `Date` | Most recent corrective request date |
| `estimated_next_failure` | `Date` | `latest_failure_date + mtbf` days |
| `maintenance_count` | `Integer` | Total maintenance requests |
| `maintenance_open_count` | `Integer` | Non-done, non-archived requests |
| `expected_mtbf` | `Integer` | User-configured expected MTBF for comparison |

**Properties & Serial**

| Field | Type | Description |
|-------|------|-------------|
| `equipment_properties` | `Properties` | Dynamic properties defined by the category's `equipment_properties_definition` |
| `match_serial` | `Boolean` | Computed: `True` if a `stock.lot` with matching serial number exists |

**Relations**

| Field | Type | Description |
|-------|------|-------------|
| `maintenance_ids` | `One2many(maintenance.request)` | All maintenance requests for this equipment |
| `maintenance_team_id` | `Many2one(maintenance.team)` | Assigned team (from mixin, compute-on-write) |

#### Key Methods

**`action_open_matched_serial()`**

Opens the `stock.lot` form filtered by the equipment's `serial_no`. Only available if `stock.lot` is accessible.

**`_onchange_category_id()`**

When category changes, auto-fills `technician_user_id` from the category's responsible.

---

### maintenance.equipment.category

**`maintenance.equipment.category`** groups equipment and provides an email alias.

**Inheritance:** `models.Model` + `mail.alias.mixin` + `mail.thread`
** `_name`: `maintenance.equipment.category`
** `_description`: `"Maintenance Equipment Category"`

#### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` | Category name (required) |
| `company_id` | `Many2one(res.company)` | Company scope |
| `technician_user_id` | `Many2one(res.users)` | Default responsible for equipment in this category |
| `equipment_ids` | `One2many(maintenance.equipment)` | Equipment in this category |
| `equipment_count` | `Integer` | Computed count of equipment |
| `maintenance_count` | `Integer` | Total maintenance requests |
| `maintenance_open_count` | `Integer` | Open (non-done) maintenance requests |
| `fold` | `Boolean` | Folded in kanban pipe (computed from whether category is empty) |
| `color` | `Integer` | Color index |
| `note` | `Html` | Category notes |
| `alias_id` | `Many2one(mail.alias)` | Email alias. Emails to this alias create `maintenance.request` records |
| `equipment_properties_definition` | `PropertiesDefinition` | Schema for dynamic properties on equipment |

#### AliasMixin Behavior

The `mail.alias.mixin` makes each category an email gateway:
- Emails sent to the alias address create `maintenance.request` records in that category
- `alias_defaults` is set to `{'category_id': self.id}`
- `alias_model_id` is set to `maintenance.request`

---

### maintenance.request

**`maintenance.request`** is a maintenance ticket / work order.

**Inheritance:** `models.Model` + `mail.thread.cc` + `mail.activity.mixin`
** `_name`: `maintenance.request`
** `_description`: `"Maintenance Request"`
** `_order`: `id desc`
** `_check_company_auto`: `True`

#### Field Reference

**Identification & State**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` | Subject/title (required) |
| `company_id` | `Many2one(res.company)` | Company scope |
| `stage_id` | `Many2one(maintenance.stage)` | Pipeline stage (required, default from `_default_stage`) |
| `state` | N/A | Derived from `stage_id` — NOT a separate field |
| `kanban_state` | `Selection` | Kanban card state: `'normal'` (In Progress), `'blocked'` (Blocked), `'done'` (Ready for next stage) |
| `priority` | `Selection` | `'0'` (Very Low), `'1'` (Low), `'2'` (Normal), `'3'` (High) |
| `color` | `Integer` | Color index |
| `archive` | `Boolean` | Archive flag (NOT `active`). Default `False` |

**Equipment & Team**

| Field | Type | Description |
|-------|------|-------------|
| `equipment_id` | `Many2one(maintenance.equipment)` | Equipment under maintenance |
| `category_id` | `Many2one` | Related from `equipment_id.category_id` (stored, readonly) |
| `maintenance_team_id` | `Many2one(maintenance.team)` | Assigned team. Computed from equipment if set, otherwise defaults via `_get_default_team_id()` |
| `user_id` | `Many2one(res.users)` | Assigned technician. Computed from `equipment_id.technician_user_id` or `equipment_id.category_id.technician_user_id` |

**Scheduling**

| Field | Type | Description |
|-------|------|-------------|
| `request_date` | `Date` | Date the maintenance was requested (default `today`) |
| `schedule_date` | `Datetime` | Planned execution date |
| `close_date` | `Date` | Date the maintenance was completed |
| `duration` | `Float` | Duration in hours |

**Maintenance Type**

| Field | Type | Description |
|-------|------|-------------|
| `maintenance_type` | `Selection` | `'corrective'` (reactive) or `'preventive'` (scheduled) |
| `recurring_maintenance` | `Boolean` | Compute: `False` if `maintenance_type != 'preventive'`. Controls repeat scheduling |
| `repeat_interval` | `Integer` | Repeat every N units (default `1`) |
| `repeat_unit` | `Selection` | `'day'`, `'week'`, `'month'`, `'year'` |
| `repeat_type` | `Selection` | `'forever'` or `'until'` |
| `repeat_until` | `Date` | End date for repeat |

**Content**

| Field | Type | Description |
|-------|------|-------------|
| `description` | `Html` | Detailed description |
| `owner_user_id` | `Many2one(res.users)` | User who created the request (default `env.user`) |
| `done` | `Boolean` | Related from `stage_id.done` |

**Instructions**

| Field | Type | Description |
|-------|------|-------------|
| `instruction_type` | `Selection` | `'pdf'`, `'google_slide'`, `'text'` |
| `instruction_pdf` | `Binary` | PDF instruction document |
| `instruction_google_slide` | `Char` | Google Slide URL |
| `instruction_text` | `Html` | Text instructions |

#### Recurring Maintenance Flow

When a request with `recurring_maintenance == True` moves to a `done` stage:
1. `schedule_date += relativedelta(**{f"{repeat_unit}s": repeat_interval})`
2. If `repeat_type == 'forever'` OR `new_schedule_date <= repeat_until`:
3. `copy()` the request with the new `schedule_date` and reset to default stage

#### Stage Transitions

- When `stage_id` changes → `kanban_state` resets to `'normal'`
- When stage becomes `done` → `close_date` set to `today`
- When stage becomes not-done → `close_date` cleared
- All activities for this request are feedbacked/unlinked on stage change

---

### maintenance.team

**`maintenance.team`** organizes maintenance staff and provides dashboard metrics.

**Inheritance:** `models.Model`
** `_name`: `maintenance.team`
** `_description`: `"Maintenance Teams"`

#### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` | Team name (required) |
| `active` | `Boolean` | Archive flag |
| `company_id` | `Many2one(res.company)` | Company scope |
| `member_ids` | `Many2many(res.users)` | Team members. Domain: users whose `company_ids` includes team company |
| `request_ids` | `One2many(maintenance.request)` | All requests assigned to this team |
| `equipment_ids` | `One2many(maintenance.equipment)` | Equipment assigned to this team |

**Dashboard Counts (computed)**

| Field | Type | Description |
|-------|------|-------------|
| `todo_request_ids` | `One2many` | Open (non-done, non-archived) requests |
| `todo_request_count` | `Integer` | Total open requests |
| `todo_request_count_date` | `Integer` | Open requests with a scheduled date |
| `todo_request_count_high_priority` | `Integer` | Open requests with priority `'3'` |
| `todo_request_count_block` | `Integer` | Open requests with `kanban_state == 'blocked'` |
| `todo_request_count_unscheduled` | `Integer` | Open requests without a schedule date |

---

### maintenance.stage

**`maintenance.stage`** defines pipeline stages.

**Inheritance:** `models.Model`
** `_name`: `maintenance.stage`
** `_description`: `"Maintenance Stage"`
** `_order`: `sequence, id`

#### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` | Stage name (required) |
| `sequence` | `Integer` | Stage order (default `20`) |
| `fold` | `Boolean` | Folded in kanban collapsed view |
| `done` | `Boolean` | Marks requests in this stage as done (triggers `close_date` logic) |

---

### maintenance.mixin

**`maintenance.mixin`** is an abstract mixin that can be added to any model to give it equipment maintenance capabilities.

** `_name`: `maintenance.mixin`
** `_check_company_auto`: `True`

#### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `company_id` | `Many2one(res.company)` | Company |
| `effective_date` | `Date` | Effective date for MTBF calculation |
| `maintenance_team_id` | `Many2one(maintenance.team)` | Assigned team |
| `technician_user_id` | `Many2one(res.users)` | Assigned technician |
| `maintenance_ids` | `One2many(maintenance.request)` | Inverse — must be extended with `inverse_name` |
| `maintenance_count` | `Integer` | Total maintenance request count (stored) |
| `maintenance_open_count` | `Integer` | Open request count (stored) |
| `expected_mtbf` | `Integer` | Expected MTBF |
| `mtbf` | `Integer` | Computed MTBF from corrective requests |
| `mttr` | `Integer` | Computed MTTR from corrective requests |
| `latest_failure_date` | `Date` | Most recent corrective request date |
| `estimated_next_failure` | `Date` | `latest_failure_date + mtbf` |

#### MTBF/MTTR Computation

```
MTTR = avg(close_date - request_date) for all done corrective requests
MTBF = (latest_failure_date - effective_date) / count(corrective_requests)
estimated_next_failure = latest_failure_date + mtbf
```

---

## Activity Scheduling

`maintenance.request.activity_update()` manages calendar activities:

1. Requests without `schedule_date` → activities are unlinked
2. Requests with `schedule_date`:
   - Try to reschedule existing `mail_act_maintenance_request` activity
   - If no existing activity → schedule new one with `date_deadline = schedule_date`
   - User assigned: `user_id` or `owner_user_id` or `env.uid`

---

## Key Design Decisions

1. **Archive vs. delete:** The module uses an `archive` Boolean field rather than deleting records. This preserves historical data for MTBF/MTTR calculations.

2. **No `active` field on `maintenance.request`:** Requests use `archive` instead of the standard `active` pattern. This is deliberate to avoid confusion with `equipment.active`.

3. **MTBF from corrective only:** MTBF is computed only from `maintenance_type == 'corrective'` and `stage_id.done == True` requests. Preventive requests are excluded since they are scheduled, not triggered by failure.

4. **`kanban_state` reset on stage change:** When a request moves stages, kanban state resets to `'normal'` (in progress), preventing a blocked card from staying blocked after a stage transition.

5. **Mixin pattern:** `maintenance.mixin` allows any model (e.g., `project.project`, `account.asset`) to be treated as equipment with maintenance tracking. The mixin requires extending `maintenance_ids` with an `inverse_name` in the concrete model.

6. **Email aliases per category:** Each equipment category can have its own email alias. This allows creating maintenance tickets by emailing `repair@mycompany.com`, with the category auto-detected from the alias.

---

## Notes

- The module does not include a cron job to automatically generate preventive maintenance requests from plans. This is typically handled by a scheduled action (`ir.cron`) calling `_generate_requests()` on `maintenance.plan` records (in custom implementations or extended modules).
- Equipment serial number matching (`match_serial`) checks against `stock.lot` records, enabling traceability between inventory lots and maintenance history.
- The kanban view uses `stage_id.fold` to collapse empty stages.

---

## L4: Preventive vs. Corrective Maintenance

### Corrective Maintenance (`maintenance_type = 'corrective'`)
- Unplanned repairs triggered by equipment failure or operator report
- Drives MTBF/MTTR calculations
- Created via: email alias on category, manual creation, or from equipment kanban card

### Preventive Maintenance (`maintenance_type = 'preventive'`)
- Planned recurring maintenance based on schedule
- When a preventive request reaches a `done` stage with `recurring_maintenance = True`:
  - `write()` creates a **copy** of the request with the next `schedule_date`
  - Next date = `schedule_date + repeat_interval × repeat_unit`
  - Continues until `repeat_type = 'until'` AND `schedule_date > repeat_until`

**Example recurrence:**
```
repeat_interval=2, repeat_unit='week', repeat_type='forever'
→ Creates copy every 2 weeks indefinitely
```

---

## L4: Integration with Stock (Parts Consumption)

The `maintenance` module does **not** auto-generate `stock.picking` records. Integration is manual or via extension:

### Manual Picking Workflow
1. **Create `stock.picking`** (type `internal`) from team/equipment location
2. Move lines specify component products with quantities (filters, oils, belts)
3. Picking validated → quants consumed from stock
4. `maintenance.request.duration` (hours) recorded for labor tracking

### `stock.scrap` for Write-offs
When replaced parts cannot be returned to stock:
1. Scrap the parts from the equipment's location via `stock.scrap`
2. Scrap move generates a journal entry (debit expense, credit stock)
3. Scrap record linked to the maintenance request for traceability

### Integration via Custom Extension
A common pattern extends `maintenance.request`:
```python
class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'
    stock_picking_ids = fields.One2many('stock.picking', 'maintenance_request_id')
```
With a button that creates a picking pre-filled with the equipment's location and any configured spare parts.

---

## L4: Integration with Accounting (Maintenance Costs)

### Equipment Cost Tracking
- `maintenance.equipment.cost`: purchase cost of the equipment
- `maintenance.equipment.warranty_date`: warranty expiration date

### Cost Flow into Accounting

**1. Parts consumed via `stock.picking`:**
- When a picking is validated, a journal entry is created automatically by Odoo stock accounting
- Debit: Maintenance expense account (from product's `price_difference_account` or category)
- Credit: Stock account (or Cost of Goods Sold account)

**2. Labor costs (requires `hr_timesheet`):**
- `maintenance.request.duration` (Float hours) × labor rate
- Timesheet entry created → analytic line generated
- Analytic lines auto-post to maintenance expense account

**3. Asset depreciation (requires `account_asset`):**
- Equipment created as `account.asset` record
- Depreciation spreads the `cost` over its useful life
- Maintenance costs are **expensed separately** — they do NOT capitalize to the asset value without a separate journal entry to reclassify

### Configuration Checklist
In `Settings > Accounting > Invoicing > Categories` or `Inventory > Configuration`:
- **Maintenance Expense Account**: default debit account for maintenance-related stock moves
- **Parts Revenue Account**: for billable maintenance contracts (when customer pays for repair parts)
- **Service Revenue Account**: for labor charges on billable contracts

---

## L4: Email Alias / Auto-Ticket Creation

Equipment categories can have an `alias_id` (from `mail.alias.mixin`). When an email is sent:
1. `mail.thread` receives the message
2. `mail.alias.mixin._alias_get_creation_values()` sets `alias_defaults = {'category_id': self.id}`
3. `maintenance.request` record created with `category_id` pre-filled
4. `technician_user_id` inherited from `category_id.technician_user_id`
5. Activity scheduled for the assigned technician

This enables end-users to report issues by email without logging into Odoo — a common helpdesk-bridge pattern.

---

## Related Modules

| Module | Relationship |
|--------|-------------|
| `maintenance_worksheet` | Custom worksheet templates for maintenance requests |
| `project` | Convert maintenance requests to project tasks |
| `fetchmail` | Inbound email server for maintenance aliases |
| `account` | Maintenance cost accounting |
| `stock` | Parts consumption via picking/scrap |
| `mrp_repair` | Complex repair operations with parts and work orders |
| `account_asset` | Asset depreciation for equipment |

---

## Tags

#odoo #odoo18 #maintenance #equipment #mtbf #workflow

