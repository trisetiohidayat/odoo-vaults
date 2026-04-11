---
Module: project_helpdesk
Version: Odoo 18
Type: Integration
Tags: #odoo, #odoo18, #project, #helpdesk, #integration
Related Modules: helpdesk, helpdesk_timesheet, project_enterprise
---

# Project Helpdesk (`project_helpdesk`)

## Module Overview

**Location:** Enterprise addons (`project_helpdesk`)
**Depends:** `project_enterprise`, `helpdesk`
**License:** OEEL-1
**Auto-install:** Yes

This bridge module enables bidirectional conversion between Helpdesk tickets and Project tasks. It does **not** define cross-linking fields itself — those are provided by `helpdesk_timesheet`, which adds `project_id` to `helpdesk.ticket` and `ticket_ids` to `project.project`. `project_helpdesk` provides the conversion action buttons and the wizard logic.

---

## Architecture

```
helpdesk.ticket  --(action_convert_to_task)-->  project.task
project.task     --(action_convert_to_ticket)--> helpdesk.ticket
```

The actual field linkage (ticket.project_id ↔ project.ticket_ids) is defined in `helpdesk_timesheet`:

| Model | Field | Type | Source |
|-------|-------|------|--------|
| `helpdesk.ticket` | `project_id` | Many2one → `project.project` | `helpdesk_timesheet` (related to `team_id.project_id`) |
| `helpdesk.team` | `project_id` | Many2one → `project.project` | `helpdesk_timesheet` |
| `project.project` | `ticket_ids` | One2many → `helpdesk.ticket` | `helpdesk_timesheet` |
| `project.project` | `ticket_count` | Integer (computed) | `helpdesk_timesheet` |
| `project.project` | `helpdesk_team` | One2many → `helpdesk.team` | `helpdesk_timesheet` |

---

## Models

### `helpdesk.ticket` — Extended by `project_helpdesk`

**File:** `models/helpdesk.py`

#### Action Methods

##### `action_convert_to_task()`
Launches the ticket-to-task conversion wizard.

```python
def action_convert_to_task(self):
    return {
        'name': _('Convert to Task'),
        'view_mode': 'form',
        'res_model': 'helpdesk.ticket.convert.wizard',
        'views': [(False, 'form')],
        'type': 'ir.actions.act_window',
        'target': 'new',
        'context': {**self.env.context, 'to_convert': self.ids},
    }
```

**L4 Note:** Accessible from the ticket form via the "Convert to Task" button. The wizard pre-selects the project from `ticket.team_id.project_id` if that team has exactly one associated project (handled by `helpdesk_timesheet` override of `_default_project_id`).

---

### `project.task` — Extended by `project_helpdesk`

**File:** `models/project.py`

#### Action Methods

##### `action_convert_to_ticket()`
Launches the task-to-ticket conversion wizard.

```python
def action_convert_to_task(self):
    if any(task.recurring_task for task in self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning',
                'message': _('Recurring tasks cannot be converted into tickets.'),
            }
        }
    return {
        'name': _('Convert to Ticket'),
        'view_mode': 'form',
        'res_model': 'project.task.convert.wizard',
        'views': [(False, 'form')],
        'type': 'ir.actions.act_window',
        'target': 'new',
        'context': {**self.env.context, 'to_convert': self.ids},
    }
```

**Constraints:** Recurring tasks cannot be converted — a blocking notification is shown.

---

### `helpdesk.ticket.convert.wizard` — TransientModel

**File:** `wizard/helpdesk_ticket_convert_wizard.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | Many2one → `project.project` | Target project for created tasks |
| `stage_id` | Many2one → `project.task.type` | Target stage; domain filtered to `project_id` |

#### Methods

##### `default_get(field_list)`
Pre-populates `project_id` with the first ticket's project if all selected tickets share the same one.

##### `_default_project_id()`
Returns the single shared `project_id` from selected tickets, or the first one sorted by sequence. Override point for `helpdesk_timesheet` to use `team_id.project_id`.

##### `_compute_default_stage()`
Depends on `project_id`. Defaults to the first stage of the selected project (`project_id.type_ids[0]`).

##### `action_convert()`
Core conversion logic:

```python
def action_convert(self):
    tickets_to_convert = self._get_tickets_to_convert()
    created_tasks = self.env['project.task'].with_context(mail_create_nolog=True).create(
        [self._get_task_values(ticket) for ticket in tickets_to_convert]
    )
    for ticket, task in zip(tickets_to_convert, created_tasks):
        ticket.active = False  # Archives the ticket
        ticket_sudo.message_post(body=_("Ticket converted into task %s", task_sudo._get_html_link()))
        task_sudo.message_post_with_view('mail.message_origin_link',
            values={'self': task_sudo, 'origin': ticket_sudo},
            subtype_id=self.env.ref('mail.mt_note').id)
    # Returns action to view created task(s)
```

**Key behavior:**
- Source ticket is **archived** (not deleted) — `active = False`
- Mail thread linkage: ticket posts a note linking to the new task; task posts origin link back to ticket
- Returns a form view for single conversion, tree view for batch

##### `_get_task_values(ticket)`
Maps ticket fields to task values:

```python
def _get_task_values(self, ticket):
    return {
        'name': ticket.name,
        'description': ticket.description,
        'project_id': self.project_id.id,
        'stage_id': self.stage_id.id,
        'partner_id': ticket.partner_id.id,
    }
```

**L4 Note:** Only `name`, `description`, `project_id`, `stage_id`, and `partner_id` are transferred. Priority, tags, attachments, and SLA policies are **not** carried over.

---

### `project.task.convert.wizard` — TransientModel

**File:** `wizard/project_task_convert_wizard.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | Many2one → `helpdesk.team` | Target helpdesk team |
| `stage_id` | Many2one → `helpdesk.stage` | Target stage; domain filtered to `team_id` |

#### Methods

Same pattern as ticket wizard:

| Method | Behavior |
|--------|----------|
| `default_get()` | Pre-populates `team_id` from task's project (via `helpdesk_timesheet._default_team_id()`) |
| `_compute_default_stage()` | Defaults to first stage of selected team |
| `action_convert()` | Creates `helpdesk.ticket` records, archives source task, links mail threads |
| `_get_ticket_values(task)` | Maps `name`, `description`, `team_id`, `stage_id`, `partner_id` |

---

## Business Flow

### Ticket → Task Conversion

1. Agent opens a ticket in `helpdesk.ticket` form
2. Clicks **"Convert to Task"** button → `action_convert_to_task()`
3. Wizard opens with `project_id` pre-selected (from team's project if set)
4. Agent selects target project and stage
5. `action_convert()` creates a `project.task`, archives the ticket, links mail threads
6. Task appears in the project; ticket remains accessible via "Archived" filter

### Task → Ticket Conversion

1. Project manager opens a task in `project.task` form
2. Clicks **"Convert to Ticket"** button → `action_convert_to_ticket()`
3. Wizard opens with `team_id` pre-selected (from task's project's linked helpdesk teams)
4. Agent selects target team and stage
5. `action_convert()` creates a `helpdesk.ticket`, archives the task, links mail threads

---

## `helpdesk_timesheet` — Cross-Module Fields (Prerequisite)

`helpdesk_timesheet` is the module that provides the actual linking fields. `project_helpdesk` depends on it transitively through `project_enterprise`.

### `helpdesk.team` Fields Added by `helpdesk_timesheet`

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | Many2one → `project.project` | Project for timesheet tracking; domain `allow_timesheets=True` |
| `timesheet_encode_uom_id` | Many2one → `uom.uom` | Related to `company_id.timesheet_encode_uom_id` |
| `total_timesheet_time` | Integer (computed) | Total encoded time across open tickets |

**Auto-creation:** If `use_helpdesk_timesheet` is enabled on a team without a `project_id`, `helpdesk_timesheet` auto-creates a project with `allow_timesheets=True`.

### `helpdesk.ticket` Fields Added by `helpdesk_timesheet`

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | Many2one → `project.project` | Related (`team_id.project_id`), readonly, stored |
| `timesheet_ids` | One2many → `account.analytic.line` | Time entries linked to this ticket |
| `total_hours_spent` | Float (computed, stored) | Sum of timesheet `unit_amount` |
| `analytic_account_id` | Many2one → `account.analytic.account` | Related to project's analytic account |

### `project.project` Fields Added by `helpdesk_timesheet`

| Field | Type | Description |
|-------|------|-------------|
| `ticket_ids` | One2many → `helpdesk.ticket` | All tickets in this project |
| `ticket_count` | Integer (computed) | Count of tickets in project |
| `helpdesk_team` | One2many → `helpdesk.team` | Teams linked to this project |
| `has_helpdesk_team` | Boolean (computed) | True if any team links here |

---

## L4: When to Use Project vs. Helpdesk

| Dimension | Helpdesk | Project |
|-----------|----------|---------|
| **Trigger** | Customer incoming request | Internal work breakdown |
| **Tracking** | SLA deadlines, customer satisfaction | Milestones, task dependencies |
| **Billing** | Time-and-materials via timesheets | Milestone/fixed-price via SO |
| **Portal** | Customer submits and tracks tickets | Customer views progress (optional) |
| **Escalation** | SLA policies, auto-close rules | Task escalation, overdue alerts |
| **Conversion trigger** | Ticket too complex for support → convert to project task | Task requires customer input → convert to ticket |

**Conversion pattern:** Use ticket→task for issues that grow into structured work breakdown. Use task→ticket for deliverables that spawn customer-facing questions.

---

## L4: SLA Integration

SLA policies in `helpdesk` apply to tickets. When a ticket is converted to a task, the SLA policy is **not** transferred. The task lifecycle is governed by project stage deadlines instead.

If SLA compliance tracking is critical, keep the ticket open in Helpdesk and link the task as a related record, rather than converting.

---

## Security

| Operation | Required Groups |
|-----------|-----------------|
| Convert ticket → task | `helpdesk.group_helpdesk_user` + `project.group_project_user` |
| Convert task → ticket | `project.group_project_user` + `helpdesk.group_helpdesk_user` |
| Read tickets/tasks | Respective model access rights |

The test `test_convert_ticket_to_task_no_rights` confirms that a user with only `helpdesk.group_helpdesk_user` cannot open the ticket conversion wizard.
