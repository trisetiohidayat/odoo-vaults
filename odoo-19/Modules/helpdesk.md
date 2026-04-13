---
type: module
module: helpdesk
tags: [odoo, odoo19, helpdesk, ticket, sla, rating, support]
created: 2026-04-07
---

# Helpdesk Module (`helpdesk`)

## Overview

> **Quick Summary:** Odoo 19's Helpdesk module manages customer support tickets with team-based routing, SLA policy enforcement, automated assignment, customer ratings, and email gateway integration.

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Ticket Creation | [Flows/Helpdesk/ticket-creation-flow](Flows/Helpdesk/ticket-creation-flow.md) | Full method chain from create to SLA application |
| 🔀 Ticket Resolution | [Flows/Helpdesk/ticket-resolution-flow](Flows/Helpdesk/ticket-resolution-flow.md) | Close, rating, reopen, escalate flows |
| 📋 Configuration | [Business/Helpdesk/helpdesk-configuration-guide](Business/Helpdesk/helpdesk-configuration-guide.md) | Step-by-step setup for teams, stages, SLAs, ratings |

## Key Models

| Model | Type | Description |
|-------|---|---|
| `helpdesk.team` | Model | Support team with members, stages, SLA config, email alias |
| `helpdesk.ticket` | Model | Individual support ticket — primary record |
| `helpdesk.stage` | Model | Pipeline stage (New, In Progress, Solved, Cancelled) |
| `helpdesk.tag` | Model | Ticket categorization tags |
| `helpdesk.ticket.type` | Model | Ticket type classification (Bug, Question, etc.) |
| `helpdesk.sla` | Model | SLA policy definition (time, priority, stage target) |
| `helpdesk.sla.status` | Model | Per-ticket SLA status record with deadline and reached datetime |
| `mail.message` | Model (inherited) | Chatter messages on tickets |
| `rating.rating` | Model (inherited) | Customer satisfaction ratings linked to tickets |
| `res.partner` | Model (linked) | Customer (partner) linked to ticket |

## Key Field Reference

### `helpdesk.ticket`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Subject — required |
| `team_id` | Many2one | helpdesk.team |
| `stage_id` | Many2one | helpdesk.stage — determined from team on create |
| `user_id` | Many2one | Assigned agent — determined from team assignment policy |
| `partner_id` | Many2one | res.partner — customer |
| `partner_email` | Char | Derived from partner or set manually |
| `priority` | Selection | '0' Low, '1' Medium, '2' High, '3' Urgent |
| `ticket_ref` | Char | Auto-generated sequence (e.g., "00042") |
| `close_date` | Datetime | Set when stage.fold=True |
| `close_hours` | Integer | Computed from create_date to close_date using calendar |
| `sla_status_ids` | One2many | helpdesk.sla.status — deadline and reached tracking |
| `sla_fail` | Boolean | Computed: deadline passed or reached late |
| `sla_deadline` | Datetime | Minimum deadline across all SLA policies |
| `kanban_state` | Selection | 'normal', 'done', 'blocked' — driven by rating |
| `tag_ids` | Many2many | helpdesk.tag |
| `ticket_type_id` | Many2one | helpdesk.ticket.type |
| `use_rating` | Boolean | Related from team — whether ratings enabled |
| `use_sla` | Boolean | Related from team — whether SLA policies apply |
| `properties` | Properties | Custom ticket properties defined on team |

### `helpdesk.team`

| Field | Type | Notes |
|-------|------|-------|
| `stage_ids` | Many2many | Stages available to this team's tickets |
| `member_ids` | Many2many | res.users — team members |
| `auto_assignment` | Boolean | Enable automatic ticket assignment |
| `assign_method` | Selection | 'randomly' or 'balanced' |
| `use_sla` | Boolean | Enable SLA policies |
| `use_rating` | Boolean | Enable customer ratings |
| `resource_calendar_id` | Many2one | Working hours for SLA deadline computation |
| `auto_close_ticket` | Boolean | Enable auto-close after inactivity |
| `auto_close_day` | Integer | Days of inactivity before auto-close |
| `from_stage_ids` | Many2many | Stages triggering auto-close countdown |
| `to_stage_id` | Many2one | Target stage for auto-close |
| `privacy_visibility` | Selection | 'invited_internal', 'internal', 'portal' |

### `helpdesk.sla`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | SLA policy name (e.g., "Critical - 4h Response") |
| `team_id` | Many2one | Applies to this team only |
| `priority` | Selection | Matches ticket priority |
| `time` | Float | Hours until deadline |
| `stage_id` | Many2one | Target stage for SLA (deadline to reach this stage) |
| `exclude_stage_ids` | Many2many | Stages where SLA timer pauses |
| `ticket_type_ids` | Many2many | Applies only to these ticket types |
| `tag_ids` | Many2many | Applies only to tickets with these tags |
| `partner_ids` | Many2many | Applies only to these partners |

## Key Methods

### Ticket Lifecycle

| Method | Model | Purpose |
|--------|-------|---------|
| `create(vals)` | `helpdesk.ticket` | Creates ticket, determines stage/user, applies SLA, subscribes partner |
| `_compute_user_and_stage_ids()` | `helpdesk.ticket` | Derives `user_id` and `stage_id` from team on change |
| `_sla_apply()` | `helpdesk.ticket` | Finds and applies matching SLA policies, creates `helpdesk.sla.status` |
| `_sla_reach(stage_id)` | `helpdesk.ticket` | Marks SLA statuses as reached when ticket enters target stage |
| `_track_template(changes)` | `helpdesk.ticket` | Sends email template if stage has `template_id` |
| `_track_subtype(init_values)` | `helpdesk.ticket` | Returns 'mt_ticket_stage' subtype for stage changes |
| `action_reopen()` | `helpdesk.ticket` | Moves ticket back to in-progress stage |
| `action_escalate()` | `helpdesk.ticket` | Bumps priority and/or changes team |
| `assign_ticket_to_self()` | `helpdesk.ticket` | Sets `user_id = current_user` |
| `_cron_auto_close_tickets()` | `helpdesk.team` | Closes inactive tickets via cron |

### Team Assignment

| Method | Model | Purpose |
|--------|-------|---------|
| `_determine_stage()` | `helpdesk.team` | Returns first stage (sequence=0) for new tickets |
| `_determine_user_to_assign()` | `helpdesk.team` | Returns user based on balanced or random assignment |
| `_get_first_stage()` | `helpdesk.team` | Returns last folded stage (closed stage) |
| `_cron_auto_close_tickets()` | `helpdesk.team` | Scheduled action for auto-close |

### Rating Integration

| Method | Model | Purpose |
|--------|-------|---------|
| `_rating_apply()` | `rating.parent.mixin` | Called when ticket enters folded stage — sends rating request |
| `_action_rating_update()` | `rating.mixin` | Processes customer rating — sets kanban_state |
| `_notify_bad_rating()` | `helpdesk.ticket` | Manager notification on poor rating |

## Key Business Rules

- Ticket `stage_id` must belong to the ticket's `team_id.stage_ids` (domain constraint)
- SLA policies are matched on: `team_id`, `priority`, `ticket_type_id`, `tag_ids`, `partner_ids`
- SLA deadline uses `team.resource_calendar_id` — not wall-clock time
- Closing a ticket (stage.fold=True) sets `close_date` and marks SLAs as reached
- Reopening a ticket clears `close_date` but does **not** automatically reset SLA deadlines
- Rating submission is public via portal token (`/rate/{token}`) — no login required
- `kanban_state` is set to 'blocked' when rating < `RATING_LIMIT_MIN` (configurable)
- Auto-close cron runs on tickets in `from_stage_ids` for `auto_close_day` days of inactivity

## Related Modules

| Module | Relationship |
|--------|-------------|
| `helpdesk_account` | Links tickets to refunds and credit notes |
| `helpdesk_stock` | Links tickets to product returns |
| `helpdesk_repair` | Links tickets to repair orders |
| `helpdesk_sale_loyalty` | Links tickets to loyalty/coupon programs |
| `helpdesk_fsm` | Field Service Management integration |
| `helpdesk_timesheet` | Time tracking on tickets |
| `website_helpdesk` | Public portal form for ticket submission |
| `rating` | Rating infrastructure — inherited by `helpdesk.team` |

## Related Documentation

- [Flows/Helpdesk/ticket-creation-flow](Flows/Helpdesk/ticket-creation-flow.md) — Ticket creation, partner auto-fill, SLA application
- [Flows/Helpdesk/ticket-resolution-flow](Flows/Helpdesk/ticket-resolution-flow.md) — Ticket close, rating, reopen, escalate
- [Business/Helpdesk/helpdesk-configuration-guide](Business/Helpdesk/helpdesk-configuration-guide.md) — Team, stage, SLA, rating setup
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine design patterns
- [Core/API](Core/API.md) — @api decorators used in helpdesk models
- [Modules/rating](Modules/rating.md) — Rating infrastructure used by helpdesk
- [Modules/mail](Modules/mail.md) — Mail.thread integration for notifications
