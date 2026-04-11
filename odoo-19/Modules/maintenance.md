---
tags: [odoo, odoo19, modules, maintenance, equipment, cmms]
description: Equipment maintenance tracking and maintenance request management for Odoo 19 CE - Full depth L4 documentation
---

# Maintenance Module (`maintenance`)

> **Community Edition** | License: LGPL-3
> Odoo 19 CE module for equipment and maintenance request management.
> Depends: `mail` | Application: Yes
> Path: `odoo/addons/maintenance/`

---

## Table of Contents

1. [L1 - Models Inventory](#1-l1---models-inventory)
2. [L2 - Field Types, Defaults, Constraints](#2-l2---field-types-defaults-constraints)
3. [L3 - Cross-Module, Override Patterns, Workflow Triggers](#3-l3---cross-module-override-patterns-workflow-triggers)
4. [L4 - Version Change Odoo 18 to 19](#4-l4---version-change-odoo-18-to-19)

---

## 1. L1 - Models Inventory

### 1.1 Model Overview

| Model | Type | Table | Description |
|-------|------|-------|-------------|
| `maintenance.stage` | Concrete | `maintenance_stage` | Kanban pipeline stages |
| `maintenance.equipment.category` | Concrete | `maintenance_equipment_category` | Equipment categorization |
| `maintenance.mixin` | Abstract | N/A | Shared equipment/request fields |
| `maintenance.equipment` | Concrete | `maintenance_equipment` | Physical assets to maintain |
| `maintenance.request` | Concrete | `maintenance_request` | Maintenance work orders |
| `maintenance.team` | Concrete | `maintenance_team` | Maintenance crew grouping |

### 1.2 `maintenance.stage`

Kanban pipeline stages for requests. Minimal model -- just name, sequence, fold, and done flag.

```python
class MaintenanceStage(models.Model):
    _name = 'maintenance.stage'
    _description = 'Maintenance Stage'
    _order = 'sequence, id'

    name = fields.Char('Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=20)
    fold = fields.Boolean('Folded in Maintenance Pipe')
    done = fields.Boolean('Request Done')
```

**Role:** Controls the kanban board columns. The `done` boolean field determines whether a request is considered complete (all stages where `done=True` mark the request as closed).

### 1.3 `maintenance.equipment.category`

Groups equipment for reporting and technician assignment.

```python
class MaintenanceEquipmentCategory(models.Model):
    _name = 'maintenance.equipment.category'
    _description = 'Maintenance Equipment Category'
```

Key fields: `name`, `company_id`, `technician_user_id` (default: `self.env.uid`), `color`, `note` (Html), `equipment_ids` (One2many), `maintenance_ids` (One2many), `equipment_count`, `maintenance_count`, `maintenance_open_count`, `fold` (computed), `equipment_properties_definition`.

**Key pattern:** The `fold` field (for kanban collapse) has a mutual dependency with `equipment_count`. This is explicitly resolved in `_compute_fold` by checking if `equipment_count == 0`. When a category has zero equipment, it is folded by default.

### 1.4 `maintenance.mixin` (Abstract)

Provides shared fields for any model that tracks maintenance. Any model (e.g., `fleet.vehicle`, `stock.quant`, `mrp.workcenter`) can inherit from this mixin to get maintenance tracking capability.

```python
class MaintenanceMixin(models.AbstractModel):
    _name = 'maintenance.mixin'
    _check_company_auto = True
    _description = 'Maintenance Maintained Item'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    effective_date = fields.Date('Effective Date',
                                  default=fields.Date.context_today, required=True,
                                  help="Used to compute MTBF")
    maintenance_team_id = fields.Many2one('maintenance.team', ...)
    technician_user_id = fields.Many2one('res.users', string='Technician', tracking=True)
    maintenance_ids = fields.One2many('maintenance.request')
    maintenance_count = fields.Integer(compute='_compute_maintenance_count', store=True)
    maintenance_open_count = fields.Integer(compute='_compute_maintenance_count', store=True)
    expected_mtbf = fields.Integer(string='Expected MTBF')
    mtbf = fields.Integer(compute='_compute_maintenance_request', string='MTBF')
    mttr = fields.Integer(compute='_compute_maintenance_request', string='MTTR')
    estimated_next_failure = fields.Date(compute='_compute_maintenance_request')
    latest_failure_date = fields.Date(compute='_compute_maintenance_request')
```

**MTBF/MTTR computation** filters only `maintenance_type == 'corrective'` and `stage_id.done == True` requests.

### 1.5 `maintenance.equipment`

Concrete model for physical assets. Inherits from `maintenance.mixin` plus `mail.thread` and `mail.activity.mixin`.

```python
class MaintenanceEquipment(models.Model):
    _name = 'maintenance.equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'maintenance.mixin']
    _description = 'Maintenance Equipment'
    _check_company_auto = True
```

Key equipment-specific fields:

| Field | Type | Purpose |
|-------|------|---------|
| `name` | Char (translate) | Equipment name |
| `active` | Boolean | Soft-delete support |
| `owner_user_id` | Many2one(res.users) | Owner of the equipment |
| `category_id` | Many2one | Equipment category |
| `partner_id` | Many2one(res.partner) | Vendor/supplier |
| `partner_ref` | Char | Vendor's reference number |
| `model` | Char | Equipment model name |
| `serial_no` | Char | Serial number (unique via SQL constraint) |
| `assign_date` | Date | When equipment was assigned |
| `cost` | Float | Equipment cost |
| `warranty_date` | Date | Warranty expiration |
| `scrap_date` | Date | End-of-life date |
| `equipment_properties` | Properties | Custom fields from category |
| `equipment_properties_definition` | (on category) | Schema for custom fields |

**SQL Constraint:**
```python
_serial_no = models.Constraint(
    'unique(serial_no)',
    'Another asset already exists with this serial number!',
)
```

**Display name pattern:** `name/serial_no` if serial_no is set.

### 1.6 `maintenance.request`

Work orders / maintenance tickets. Inherits from `mail.thread.cc` and `mail.activity.mixin`.

```python
class MaintenanceRequest(models.Model):
    _name = 'maintenance.request'
    _inherit = ['mail.thread.cc', 'mail.activity.mixin']
    _description = 'Maintenance Request'
    _order = "id desc"
    _check_company_auto = True
```

Key request fields:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `name` | Char | (required) | Subject/issue description |
| `request_date` | Date | today | When maintenance was requested |
| `owner_user_id` | Many2one(res.users) | `s.env.uid` | Requester |
| `category_id` | Many2one | (related from equipment) | Category from equipment |
| `equipment_id` | Many2one | (optional) | Equipment being maintained |
| `user_id` | Many2one(res.users) | (computed) | Assigned technician |
| `stage_id` | Many2one | `_default_stage` | Current pipeline stage |
| `priority` | Selection | (none) | 0=Very Low to 3=High |
| `archive` | Boolean | `False` | Soft-archive flag |
| `maintenance_type` | Selection | `'corrective'` | corrective or preventive |
| `schedule_date` | Datetime | (optional) | Planned start |
| `schedule_end` | Datetime | (computed) | Expected completion |
| `duration` | Float | (computed hours) | Duration in hours |
| `done` | Boolean | (related stage_id.done) | Completion flag |
| `kanban_state` | Selection | `'normal'` | normal/blocked/done |
| `close_date` | Date | (set on done) | Date completed |
| `recurring_maintenance` | Boolean | (computed) | Only True for preventive |
| `repeat_interval` | Integer | `1` | Recurrence interval |
| `repeat_unit` | Selection | `'week'` | day/week/month/year |
| `repeat_type` | Selection | `'forever'` | forever or until date |
| `repeat_until` | Date | (optional) | Recurrence end date |
| `instruction_type` | Selection | `'text'` | pdf/google_slide/text |
| `instruction_pdf` | Binary | - | PDF worksheet |
| `instruction_google_slide` | Char | - | Google Slide URL |
| `instruction_text` | Html | - | Inline text instructions |

### 1.7 `maintenance.team`

Groups requests and equipment for assignment.

```python
class MaintenanceTeam(models.Model):
    _name = 'maintenance.team'
    _inherit = ['mail.alias.mixin', 'mail.thread']
```

Key fields:

| Field | Type | Purpose |
|-------|------|---------|
| `name` | Char | Team name |
| `member_ids` | Many2many(res.users) | Team members |
| `request_ids` | One2many | All team requests |
| `equipment_ids` | One2many | Equipment assigned to team |
| `todo_request_ids` | One2many (computed) | Open, non-archived requests |
| `todo_request_count` | Integer (computed) | Count of open requests |
| `todo_request_count_date` | Integer (computed) | Scheduled count |
| `todo_request_count_high_priority` | Integer (computed) | High-priority count |
| `todo_request_count_block` | Integer (computed) | Blocked count |
| `todo_request_count_unscheduled` | Integer (computed) | Unscheduled count |
| `alias_id` | Many2one | Email alias for incoming requests |

---

## 2. L2 - Field Types, Defaults, Constraints

### 2.1 Key Field Defaults

| Field | Default | Location |
|-------|---------|----------|
| `maintenance_request.stage_id` | First stage by sequence | `_default_stage()` |
| `maintenance_request.maintenance_team_id` | First team in company or globally | `_get_default_team_id()` |
| `maintenance_request.request_date` | `fields.Date.context_today` | Field default |
| `maintenance_request.kanban_state` | `'normal'` | Field default |
| `maintenance_request.maintenance_type` | `'corrective'` | Field default |
| `maintenance_request.repeat_interval` | `1` | Field default |
| `maintenance_request.repeat_unit` | `'week'` | Field default |
| `maintenance_request.repeat_type` | `'forever'` | Field default |
| `maintenance_request.instruction_type` | `'text'` | Field default |
| `maintenance_request.archive` | `False` | Field default |
| `maintenance_equipment.active` | `True` | Field default |
| `maintenance_stage.sequence` | `20` | Field default |
| `maintenance_equipment_category.technician_user_id` | `self.env.uid` | Field default |
| `maintenance_team.active` | `True` | Field default |

### 2.2 SQL Constraints

**`maintenance.equipment`:**
```python
_serial_no = models.Constraint(
    'unique(serial_no)',
    'Another asset already exists with this serial number!',
)
```
Note: The constraint is on `serial_no` alone, not company-scoped. If multiple companies share the same serial number space, this could cause conflicts.

### 2.3 API Constraints (`@api.constrains`)

**`maintenance.request`:**
```python
@api.constrains('schedule_end')
def _check_schedule_end(self):
    for request in self:
        if request.schedule_date and request.schedule_end:
            if request.schedule_date > request.schedule_end:
                raise ValidationError("End date cannot be earlier than start date.")

@api.constrains('repeat_interval')
def _check_repeat_interval(self):
    for record in self:
        if record.repeat_interval < 1:
            raise ValidationError("The repeat interval cannot be less than 1.")
```

### 2.4 `@api.ondelete` Protections

**`maintenance.equipment.category`:**
```python
@api.ondelete(at_uninstall=False)
def _unlink_except_contains_maintenance_requests(self):
    for category in self:
        if category.equipment_ids or category.maintenance_ids:
            raise UserError(_("You can't delete an equipment category if some "
                             "equipment or maintenance requests are linked to it."))
```
Uses `at_uninstall=False` so this restriction only applies during normal operation, not during module uninstall.

### 2.5 Computed Field Dependencies

**`maintenance_request.duration`:**
```python
@api.depends('schedule_date', 'schedule_end')
def _compute_duration(self):
    for request in self:
        if request.schedule_date and request.schedule_end:
            duration = (request.schedule_end - request.schedule_date).total_seconds() / 3600
            request.duration = round(duration, 2)
        else:
            request.duration = 0
```

**`maintenance_request.schedule_end`:**
```python
@api.depends('schedule_date')
def _compute_schedule_end(self):
    for request in self:
        request.schedule_end = (request.schedule_date and
                                request.schedule_date + relativedelta(hours=1))
```

**`maintenance_request.recurring_maintenance`:**
```python
@api.depends('maintenance_type')
def _compute_recurring_maintenance(self):
    for request in self:
        if request.maintenance_type != 'preventive':
            request.recurring_maintenance = False
```

### 2.6 Computed Team Dashboard Fields

```python
@api.depends('request_ids.stage_id.done')
def _compute_todo_requests(self):
    for team in self:
        team.todo_request_ids = self.env['maintenance.request'].search([
            ('maintenance_team_id', '=', team.id),
            ('stage_id.done', '=', False),
            ('archive', '=', False)
        ])
        data = self.env['maintenance.request']._read_group(
            [...],
            ['schedule_date:year', 'priority', 'kanban_state'],
            ['__count']
        )
        team.todo_request_count = sum(count for (_, _, _, count) in data)
        team.todo_request_count_date = sum(count for (sd, _, _, count) in data if sd)
        team.todo_request_count_high_priority = sum(count for (_, p, _, count) in data if p == '3')
        team.todo_request_count_block = sum(count for (_, _, ks, count) in data if ks == 'blocked')
        team.todo_request_count_unscheduled = team.todo_request_count - team.todo_request_count_date
```

---

## 3. L3 - Cross-Module, Override Patterns, Workflow Triggers

### 3.1 Cross-Module Dependencies

**`maintenance` depends on:**
- `mail` (for messaging, activities, email aliases, CC tracking)

**Extended by other modules (known integrations):**
- `stock_maintenance`: Adds maintenance tracking to `stock.quant` via `maintenance.mixin`
- `hr_maintenance`: Adds maintenance request creation from `hr.equipment` (employee equipment)
- `fleet_maintenance`: (EE) Adds maintenance to `fleet.vehicle`
- `mrp_maintenance`: (EE) Adds maintenance to `mrp.workcenter`
- `maintenance_worksheet`: Custom worksheets with PDF/Google Slide/text instructions

### 3.2 `maintenance.mixin` Extension Pattern

The `maintenance.mixin` is an abstract model designed to be inherited by any model that needs maintenance tracking. Any concrete model that adds a `maintenance_ids` One2many pointing back to `maintenance.request` with the correct inverse_name automatically gets all mixin fields.

**Pattern for extending a model:**
```python
class MyModel(models.Model):
    _name = 'my.model'
    _inherit = ['maintenance.mixin']
    maintenance_ids = fields.One2many(
        'maintenance.request',
        'equipment_id',  # inverse_name on maintenance.request
        ...
    )
```

### 3.3 Workflow Triggers

#### 3.3.1 State Transitions (Stage Changes)

**`write()` behavior on stage change:**

```python
def write(self, vals):
    # Reset kanban_state to 'normal' when stage changes
    if vals and 'kanban_state' not in vals and 'stage_id' in vals:
        vals['kanban_state'] = 'normal'

    # When stage changes to done: auto-create next occurrence for preventive
    if 'stage_id' in vals and self.env['maintenance.stage'].browse(vals['stage_id']).done:
        for request in self:
            if request.maintenance_type != 'preventive' or not request.recurring_maintenance:
                continue
            schedule_date = request.schedule_date or now
            schedule_date += relativedelta(**{f"{request.repeat_unit}s": request.repeat_interval})
            schedule_end = schedule_date + relativedelta(hours=request.duration or 1)
            if request.repeat_type == 'forever' or schedule_date.date() <= request.repeat_until:
                request.copy({
                    'schedule_date': schedule_date,
                    'schedule_end': schedule_end,
                    'stage_id': request._default_stage().id,
                })

    # After write: manage close_date and activities
    if 'stage_id' in vals:
        self.filtered(lambda m: m.stage_id.done).write({'close_date': fields.Date.today()})
        self.filtered(lambda m: not m.stage_id.done).write({'close_date': False})
        self.activity_feedback(['maintenance.mail_act_maintenance_request'])
        self.activity_update()
```

#### 3.3.2 Archive/Reset Actions

```python
def archive_equipment_request(self):
    # Archives request and disables recurrence
    self.write({'archive': True, 'recurring_maintenance': False})

def reset_equipment_request(self):
    # Resets to first stage (no archive)
    first_stage = self.env['maintenance.stage'].search([], order="sequence asc", limit=1)
    self.write({'archive': False, 'stage_id': first_stage.id})
```

#### 3.3.3 Activity Scheduling

```python
def activity_update(self):
    """Schedule/reschedule maintenance activities based on schedule_date."""
    self.filtered(lambda r: not r.schedule_date).activity_unlink(
        ['maintenance.mail_act_maintenance_request'])
    for request in self.filtered(lambda r: r.schedule_date):
        date_dl = fields.Datetime.from_string(request.schedule_date).date()
        updated = request.activity_reschedule(
            ['maintenance.mail_act_maintenance_request'],
            date_deadline=date_dl,
            new_user_id=request.user_id.id or request.owner_user_id.id or self.env.uid)
        if not updated:
            request.activity_schedule(
                'maintenance.mail_act_maintenance_request',
                fields.Datetime.from_string(request.schedule_date).date(),
                note=request._get_activity_note(),
                user_id=request.user_id.id or request.owner_user_id.id or self.env.uid)
```

#### 3.3.4 Follower Auto-Addition

```python
def _add_followers(self):
    for request in self:
        partner_ids = (request.owner_user_id.partner_id +
                       request.user_id.partner_id).ids
        request.message_subscribe(partner_ids=partner_ids)

def create(self, vals_list):
    maintenance_requests = super().create(vals_list)
    for request in maintenance_requests:
        if request.owner_user_id or request.user_id:
            request._add_followers()
        if request.close_date and not request.stage_id.done:
            request.close_date = False
        if not request.close_date and request.stage_id.done:
            request.close_date = fields.Date.today()
    maintenance_requests.activity_update()
    return maintenance_requests
```

### 3.4 Computed `user_id` and `maintenance_team_id`

```python
@api.depends('company_id', 'equipment_id')
def _compute_user_id(self):
    for request in self:
        if request.equipment_id:
            request.user_id = (request.equipment_id.technician_user_id or
                              request.equipment_id.category_id.technician_user_id)
        if (request.user_id and
                request.company_id.id not in request.user_id.company_ids.ids):
            request.user_id = False

@api.depends('company_id', 'equipment_id')
def _compute_maintenance_team_id(self):
    for request in self:
        if request.equipment_id and request.equipment_id.maintenance_team_id:
            request.maintenance_team_id = request.equipment_id.maintenance_team_id.id
        if (request.maintenance_team_id.company_id and
                request.maintenance_team_id.company_id.id != request.company_id.id):
            request.maintenance_team_id = False
```

### 3.5 Mail Alias Integration

`maintenance.team` inherits `mail.alias.mixin`, enabling email-to-ticket creation:

```python
def _alias_get_creation_values(self):
    values = super()._alias_get_creation_values()
    values['alias_model_id'] = self.env['ir.model']._get('maintenance.request').id
    if self.id:
        values['alias_defaults'] = defaults = ast.literal_eval(self.alias_defaults or "{}")
        defaults['maintenance_team_id'] = self.id
    return values
```

### 3.6 Stage Group Expansion

Used in kanban view to show all stages even if they have no requests:

```python
@api.model
def _read_group_stage_ids(self, stages, domain):
    stage_ids = stages.sudo()._search([], order=stages._order)
    return stages.browse(stage_ids)
```

---

## 4. L4 - Version Change Odoo 18 to 19

### 4.1 Breaking Changes from Odoo 18

#### 4.1.1 `archive` Field Introduction (Odoo 19)

In **Odoo 18 and earlier**, maintenance requests used the standard `active` boolean for soft-delete. In **Odoo 19**, the module uses an **explicit `archive` field** on `maintenance.request`:

```python
archive = fields.Boolean(default=False,
    help="Set archive to true to hide the maintenance request without deleting it.")
```

This separates soft-delete from the standard `active` field, allowing archived requests to remain "active" records while being hidden from the kanban pipeline. The `todo_request_ids` computed field explicitly filters `archive = False`:

```python
team.todo_request_ids = self.env['maintenance.request'].search([
    ...
    ('archive', '=', False)
])
```

#### 4.1.2 `recurring_maintenance` Compute Change

In **Odoo 19**, `recurring_maintenance` is a computed field that **auto-resets to False** when `maintenance_type` changes away from `'preventive'`:

```python
@api.depends('maintenance_type')
def _compute_recurring_maintenance(self):
    for request in self:
        if request.maintenance_type != 'preventive':
            request.recurring_maintenance = False
```

This prevents data inconsistency where a request could be marked preventive but non-recurring.

#### 4.1.3 `kanban_state` Auto-Reset on Stage Change

A key behavior in Odoo 19: whenever `stage_id` is changed via `write()`, the `kanban_state` is **automatically reset to `'normal'`**:

```python
if vals and 'kanban_state' not in vals and 'stage_id' in vals:
    vals['kanban_state'] = 'normal'
```

This prevents a request from staying in `blocked` or `done` kanban state after moving to a new stage.

#### 4.1.4 `mail.thread.cc` Mixin

The `maintenance.request` model inherits `mail.thread.cc` (not just `mail.thread`):
```python
_inherit = ['mail.thread.cc', 'mail.activity.mixin']
```

The `cc` mixin enables carbon-copy functionality for incoming emails on the request's chatter.

### 4.2 Odoo 19 Infrastructure Changes

| Aspect | Change |
|--------|--------|
| `@api.model` vs `@api.model_create_multi` | Module uses `api.model_create_multi` -- modern Odoo 13+ pattern, correct for Odoo 19 |
| `maintenance_team_id` on mixin | Uses `index='btree_not_null'` for partial index on non-null values |
| `on_delete='restrict'` on `equipment_id` | Prevents equipment deletion while requests reference it |
| `instruction_type` | Now supports `'google_slide'` alongside `'pdf'` and `'text'` |
| `schedule_end` default | Computed as `schedule_date + 1 hour` via `_compute_schedule_end` |

### 4.3 Performance Notes

1. **Team dashboard queries:** `_compute_todo_requests` runs a separate `_read_group` query per team on every form load. With many teams and requests, this can be slow.
2. **MTBF computation:** `estimated_next_failure` depends on all corrective `maintenance_ids` being loaded -- potential N+1 if accessed in list view.
3. **Mail followers:** `_add_followers` is called on every `create()` and `write()` that changes `owner_user_id` or `user_id`, triggering message subscriptions.
4. **Stage group expansion:** `_read_group_stage_ids` runs `sudo()._search()` for every kanban view render, bypassing ir.model.access for performance.

### 4.4 Extension Points

| Point | Pattern | Notes |
|-------|---------|-------|
| Add maintenance to custom model | Inherit `maintenance.mixin` | Add inverse `maintenance_ids` One2many |
| Custom worksheet templates | Install `maintenance_worksheet` | Adds `instruction_*` fields to form |
| Auto-assign technicians | Override `_compute_user_id` | Called on create/write of request |
| Prevent category deletion | `_unlink_except_contains_maintenance_requests` | Already enforced |
| Extend recurring behavior | Override `write()` stage change logic | Handles preventive auto-creation |
| Email-to-ticket | Configure team alias | Via `mail.alias.mixin` |

### 4.5 Key Constants

```python
DAYS_PER_MONTH = 30
DAYS_PER_YEAR = DAYS_PER_MONTH * 12
```

Used throughout for 30-day/month depreciation and MTBF calculations. These are defined in `account_asset` but referenced in maintenance for duration-related computations.

### 4.6 Related Documentation

- [[Modules/Stock]] -- stock_maintenance integration
- [[Modules/Fleet]] -- fleet.vehicle maintenance tracking
- [[Modules/MRP]] -- mrp.workcenter maintenance
- [[Core/API]] -- @api.depends, @api.constrains patterns
