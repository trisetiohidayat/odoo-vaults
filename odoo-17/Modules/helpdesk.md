---
tags: [odoo, odoo17, module, helpdesk]
research_depth: medium
---

# Helpdesk Module — Deep Reference

**Source:** `enterprise/helpdesk/models/` (Odoo 17 Enterprise edition — the community/base version ships with a minimal stub; full module is enterprise-only)

**Note:** In Odoo 17, the base/community addons ship with `helpdesk` as a minimal stub. The complete Helpdesk module with SLA policies, teams, rating, and workflow is in `enterprise/helpdesk/`. This document covers the **enterprise edition** implementation.

## Overview

Customer support ticket management with SLA tracking, team-based assignment, email integration, and customer ratings. Tickets flow through configurable stages. SLA policies compute deadlines based on team working hours. Integrates with project, sale, and stock via enterprise addons.

## Files

| File | Model Extended | Purpose |
|------|---------------|---------|
| `helpdesk_ticket.py` | `helpdesk.ticket` | Core ticket model |
| `helpdesk_team.py` | `helpdesk.team` | Team config, alias, assignment rules |
| `helpdesk_sla.py` | `helpdesk.sla` | SLA policy definitions |
| `helpdesk_sla_status.py` | `helpdesk.sla.status` | Per-ticket SLA deadline/status computation |
| `helpdesk_stage.py` | `helpdesk.stage` | Stage definitions, kanban legend |
| `helpdesk_tag.py` | `helpdesk.tag` | Ticket tagging |
| `helpdesk_ticket_type.py` | `helpdesk.ticket.type` | Ticket type taxonomy |
| `res_partner.py` | `res.partner` | Partner helpdesk counts |
| `res_company.py` | `res.company` | Company-level defaults |
| `mail_message.py` | `mail.message` | Message tracking for SLA |
| `res_users.py` | `res.users` | User helpdesk role |

## Key Models

### helpdesk.ticket

**Inherits:** `portal.mixin`, `mail.thread.cc`, `utm.mixin`, `rating.mixin`, `mail.activity.mixin`, `mail.tracking.duration.mixin`

#### Fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Ticket subject (required) |
| `description` | Html | Full ticket body |
| `team_id` | Many2one | Helpdesk team |
| `ticket_ref` | Char | Auto-increment ticket reference number |
| `ticket_type_id` | Many2one | Ticket type (e.g. "Bug", "Feature Request") |
| `partner_id` | Many2one | Customer |
| `partner_name` | Char | Customer name (for portal forms) |
| `partner_email` | Char | Customer email (primary email field for portal) |
| `partner_phone` | Char | Customer phone |
| `commercial_partner_id` | Many2one | Related via partner_id |
| `user_id` | Many2one | Assigned user (computed, writable) |
| `stage_id` | Many2one | Current stage (computed, writable) |
| `fold` | Boolean | Related from stage_id |
| `priority` | Selection | '0' Low / '1' Medium / '2' High / '3' Urgent |
| `tag_ids` | Many2many | Tags |
| `color` | Integer | Kanban color |
| `kanban_state` | Selection | normal (grey) / blocked (red) / done (green) |
| `date_last_stage_update` | Datetime | Last time stage changed |
| `assign_date` | Datetime | First assignment time |
| `assign_hours` | Integer | Hours to first assignment |
| `close_date` | Datetime | Ticket close time |
| `close_hours` | Integer | Hours to close |
| `open_hours` | Integer | Hours ticket has been open |
| `active` | Boolean | Archive flag |
| `closed_by_partner` | Boolean | Partner closed ticket via portal |
| `properties` | Properties | Team-defined custom fields |

#### SLA Fields
| Field | Type | Description |
|-------|------|-------------|
| `sla_ids` | Many2many | SLA policies applied to this ticket |
| `sla_status_ids` | One2many | Computed per-policy status records |
| `sla_reached_late` | Boolean | Any SLA reached after deadline |
| `sla_reached` | Boolean | Any SLA successfully reached |
| `sla_deadline` | Datetime | Earliest SLA deadline |
| `sla_deadline_hours` | Float | Hours remaining until earliest SLA deadline |
| `sla_fail` | Boolean | Searchable: failed SLA policy |
| `sla_success` | Boolean | Searchable: successful SLA policy |

#### Time Tracking Fields
| Field | Type | Description |
|-------|------|-------------|
| `first_response_hours` | Float | Hours to first response |
| `avg_response_hours` | Float | Average response time |
| `total_response_hours` | Float | Total exchange time |
| `answered_customer_message_count` | Integer | Number of customer exchanges |
| `oldest_unanswered_customer_message_date` | Datetime | Oldest unanswered customer message |

#### Team Integration Fields
| Field | Type | Description |
|-------|------|-------------|
| `use_sla` | Boolean | Related from team |
| `use_rating` | Boolean | Related from team |
| `use_credit_notes` | Boolean | Related from team |
| `use_product_returns` | Boolean | Related from team |
| `use_product_repairs` | Boolean | Related from team |

### helpdesk.team

**Inherits:** `mail.alias.mixin`, `mail.thread`, `rating.parent.mixin`

#### Fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Team name |
| `member_ids` | Many2many | Team members |
| `alias_name` | Char | Email alias for incoming tickets |
| `alias_id` | Many2one | Mail alias |
| `assign_method` | Selection | manual / balanced / RR (round-robin) |
| `use_sla` | Boolean | Enable SLA policies |
| `sla_ids` | One2many | SLA policies for this team |
| `stage_ids` | Many2many | Pipeline stages for this team |
| `ticket_properties` | Properties | Custom ticket properties definition |
| `resource_calendar_id` | Many2one | Working hours calendar for SLA calculation |
| `privacy_visibility` | Selection | invite_internal / internal / followers |
| `open_ticket_count` | Integer | Open ticket count |
| `closed_ticket_count` | Integer | Closed ticket count |
| `rating_ids` | One2many | Linked ratings |
| `use_rating` | Boolean | Enable customer satisfaction ratings |
| `portal_show_rating` | Boolean | Show ratings on customer portal |
| `company_id` | Many2one | Company |
| `sequence` | Integer | Display order |

### helpdesk.sla

Defines SLA policy rules linked to teams.

#### Fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Policy name |
| `description` | Html | Policy description |
| `active` | Boolean | Archive flag |
| `team_id` | Many2one | Team |
| `ticket_type_ids` | Many2many | Applied ticket types |
| `tag_ids` | Many2many | Applied tags |
| `stage_id` | Many2one | Target stage (minimum stage to satisfy SLA) |
| `exclude_stage_ids` | Many2many | Stages excluded from time calculation |
| `priority` | Selection | '0'/'1'/'2'/'3' — minimum priority required |
| `partner_ids` | Many2many | Applied partners |
| `company_id` | Many2one | Related from team |
| `time` | Float | Maximum working hours to reach target stage |
| `ticket_count` | Integer | Active ticket count under this SLA |

### helpdesk.sla.status

Per-ticket, per-SLA computed status record. Created via `helpdesk.ticket.sla_ids`.

#### Fields
| Field | Type | Description |
|-------|------|-------------|
| `ticket_id` | Many2one | Ticket |
| `sla_id` | Many2one | SLA policy |
| `sla_stage_id` | Many2one | Stored from sla_id.stage_id |
| `deadline` | Datetime | Computed deadline based on team calendar |
| `reached_datetime` | Datetime | When ticket first reached target stage |
| `status` | Selection | ongoing / reached / failed |
| `color` | Integer | Kanban color (0=ongoing, 10=reached, 1=failed) |
| `exceeded_hours` | Float | Hours exceeded/under deadline (+ = late) |

#### Deadline Computation (`_compute_deadline`)
Uses team `resource_calendar_id`:
- Counts working days: `floor(sla_time / hours_per_day)`
- Calls `plan_days()` to skip non-working days
- Adjusts for ticket creation time within working day
- Adds excluded stage freeze hours via `_get_freezed_hours()`

#### Status Computation (`_compute_status`)
```
reached_datetime < deadline  → reached
reached_datetime >= deadline → failed
no reached_datetime + deadline > now()  → ongoing
no reached_datetime + deadline <= now() → failed
```

### helpdesk.stage

#### Fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Stage name |
| `team_ids` | Many2many | Teams using this stage |
| `sequence` | Integer | Order |
| `fold` | Boolean | Folded in kanban (closed tickets) |
| `template_id` | Many2one | Email template on ticket entry |
| `legend_blocked` | Char | Explanation shown when kanban_state=blocked |
| `legend_normal` | Char | Explanation shown when kanban_state=normal |
| `legend_done` | Char | Explanation shown when kanban_state=done |

## Workflow

### Ticket Creation
1. Via portal form, email alias, API, or manually
2. `default_get()` resolves team → assigns user and initial stage
3. SLA status records created for all matching SLA policies
4. `mail.tracking.duration.mixin` begins stage time tracking

### Stage Progression
- Stage change triggers `mail.tracking.duration.mixin` update
- When ticket enters target stage of an SLA policy → `reached_datetime` set on `helpdesk.sla.status`
- `_compute_status` recalculates → SLA marked reached or failed

### Closure
- Stage with `fold = True` closes ticket
- `close_date` and `close_hours` recorded

## SLA Computation Detail

### Excluded Stages (Freeze Time)
When `exclude_stage_ids` is set, time spent in those stages does not count toward the SLA deadline. Computed via `_get_freezed_hours()` which:
1. Reads `mail.tracking.value` records for stage_id changes
2. Sums working hours spent in excluded stages

### Deadline Formula
```
hours_per_day = team.resource_calendar_id.hours_per_day or 8
time_days = floor(sla.time / hours_per_day)
base_deadline = plan_days(time_days + 1, ticket.create_date)
sla_hours = sla.time % hours_per_day
sla_hours += freezed_hours
deadline = plan_hours(sla_hours, base_deadline)
```

## See Also
- [Modules/crm](Modules/CRM.md) — similar lead management and pipeline pattern
- [Modules/project](Modules/project.md) — task management, stage tracking
- [Modules/mail](Modules/mail.md) — mail.thread, email integration
- [Modules/rating](Modules/rating.md) — customer satisfaction ratings
- [Modules/portal](Modules/portal.md) — customer portal access
