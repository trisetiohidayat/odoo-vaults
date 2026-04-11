---
type: flow
title: "Ticket Resolution Flow"
primary_model: helpdesk.ticket
trigger: "User action — Ticket → Solve / Close"
cross_module: true
models_touched:
  - helpdesk.ticket
  - helpdesk.stage
  - helpdesk.sla.status
  - rating.rating
  - mail.message
  - mail.mail
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[[Flows/Helpdesk/ticket-creation-flow]]"
related_guides:
  - "[[Business/Helpdesk/helpdesk-configuration-guide]]"
source_module: helpdesk
source_path: ~/odoo/odoo19/odoo/addons/helpdesk/
created: 2026-04-07
version: "1.0"
---

# Ticket Resolution Flow

## Overview

A helpdesk ticket is resolved when an agent marks it as solved (sends a solution to the customer) or directly closes it. The flow transitions the ticket to a folded stage, records the close date and time-to-close, triggers a customer satisfaction rating request, processes the customer's rating and feedback, and optionally escalates or reopens the ticket on poor ratings or new customer replies. This is the terminal or branching point of the ticket lifecycle.

## Trigger Point

Multiple paths lead to ticket resolution:

| Trigger | Action | Path |
|---------|--------|------|
| Agent clicks "Stage: Solved" | `write({'stage_id': solved_stage_id})` | Direct close |
| Agent sends solution email | `write({'stage_id': solved_stage_id})` via email composer | Solution sent |
| Customer replies to closed ticket | `message_update()` | Ticket auto-reopens |
| Cron: auto-close inactive | `_cron_auto_close_tickets()` | Auto-close after N days |
| Bad rating received | `action_reopen()` or `action_escalate()` | Reopen/escalate path |

---

## Complete Method Chain

### Path A: Direct Close (Stage Change to Folded Stage)

```
1. helpdesk.ticket.write({'stage_id': solved_stage_id})
   │
   ├─► stage.fold == True? → closed stage detected
   │     └─► close_date = fields.Datetime.now()
   │     └─► oldest_unanswered_customer_message_date = False
   │
   ├─► helpdesk.ticket.write(..., close_date=now)
   │
   ├─► _sla_reach(stage_id)
   │     └─► Searches helpdesk.sla.status for this ticket
   │     └─► For each SLA where stage.sequence <= new_stage.sequence:
   │           reached_datetime = now  [SLA reached]
   │     └─► SLA statuses with no reached_datetime → reset to False
   │
   ├─► _track_template({'stage_id'})  [mail.thread]
   │     └─► If new stage has template_id:
   │           mail.message created with subtype 'mail.mt_note'
   │           Email rendered from template and queued
   │
   ├─► _track_subtype({'stage_id'})
   │     └─► Returns 'helpdesk.mt_ticket_stage' subtype
   │     └─► mail.tracking.value records created for audit trail
   │
   └─► helpdesk.ticket.write() returns
         └─► Ticket stage is now folded; close_hours computable
```

### Path B: Solution Sent + Rating Request

```
1. Agent uses email composer on ticket (chatter)
   └─► helpdesk.ticket.write({'stage_id': solved_stage_id})
         │
         ├─► All steps from Path A execute
         │
         └─► rating_parent_mixin._rating_apply()  [rating.parent.mixin]
               └─► rating.rating records created via rating_request()
                     └─► One rating.rating per team member (or per team)
                     └─► consumed = False (awaiting customer response)
                     └─► rating = 0 (not yet rated)
                     └─► email_sent = True
                           └─► mail.mail queued and sent to:
                                 partner_id.email (customer)
```

### Path C: Customer Rating Received

```
2. Customer clicks rating link in email (/rate/{token})
   │
   └─► rating.rating.write({'rating': 1-5, 'feedback': '...'})
         └─► consumed = True
         └─► write_date updated
         └─► _action_rating_update(rating, 'customer_feedback')
               │
               ├─► rating.rating.rating_stats_update()  [rating.parent.mixin]
               │     └─► Composite rating recomputed on helpdesk.team
               │           (last 7 days only, per _rating_satisfaction_days)
               │
               ├─► IF rating >= RATING_LIMIT_MIN (configurable threshold):
               │     └─► ticket.kanban_state = 'done' (green)
               │           mail.message posted: "Rating: {n}/5"
               │           ticket considered resolved
               │
               └─► IF rating < RATING_LIMIT_MIN:
                     └─► ticket.kanban_state = 'blocked' (red)
                     └─► _notify_bad_rating()
                           └─► message_post to followers: "Bad rating received"
                           └─► Optional: notify helpdesk manager group
                           └─► Agent should act: reopen or escalate
```

### Path D: Ticket Reopen

```
3. helpdesk.ticket.action_reopen()  [button on form]
   └─► write({'stage_id': in_progress_stage_id, 'close_date': False})
         └─► closed_by_partner = False
         └─► oldest_unanswered_customer_message_date = now
         └─► Ticket back in open state (stage.fold = False)
         └─► SLA may be re-applied if team.use_sla
```

### Path E: Ticket Escalate

```
4. helpdesk.ticket.action_escalate()
   └─► write({'priority': bump_priority, 'team_id': escalate_team_id})
         └─► priority bumped: '1'→'2', '2'→'3'
         └─► team_id changed to escalation team if configured
         └─► message_post: "Ticket escalated to {new_team}"
         └─► New assignee determined from new team via _determine_user_to_assign()
         └─► _sla_apply() called → new SLA deadline for new team
         └─► Mail notification sent to new assignee
```

### Path F: Subticket Creation

```
5. helpdesk.ticket.create({'parent_id': ticket_id, 'name': 'Sub-issue'})
   └─► New helpdesk.ticket created linked via parent_id
   └─► parent ticket not modified (separate lifecycle)
   └─► Subticket has own stage, SLA, assignee
```

---

## Decision Tree

```
Solution applied or closed
│
├─► stage_id changed to folded stage?
│  ├─► YES → close_date set, SLA reached flags updated
│  └─► NO → ticket stays open
│
├─► Team uses customer ratings (team.use_rating == True)?
│  ├─► YES → rating.rating created, email sent to customer
│  │     └─► Customer clicks rating link
│  │           ├─► rating >= RATING_LIMIT_MIN (good rating)?
│  │           │     ├─► YES → kanban_state = 'done'
│  │           │     │        └─► Ticket done — resolution flow complete
│  │           │     └─► NO (bad rating)?
│  │           │           ├─► kanban_state = 'blocked'
│  │           │           ├─► _notify_bad_rating() → manager notified
│  │           │           └─► Agent can:
│  │           │                 ├─► action_reopen() → back to in_progress
│  │           │                 └─► action_escalate() → priority bumped / team changed
│  │           │
│  └─► NO → Ticket closed, no rating requested
│
├─► Customer replies to closed ticket?
│  └─► YES → message_update() → closed_by_partner = False
│        └─► Ticket auto-reopened (stage returns to in_progress)
│
└─► New issue identified by agent?
   └─► YES → create() with parent_id set → subticket created
```

### Visual Decision Diagram

```
                    [Ticket in Progress]
                           │
                    Solve / Close action
                           │
              ┌────────────┴────────────┐
              │                         │
       stage_id → Solved          stage_id → Cancelled
       (fold=True)                 (fold=True, no rating)
              │                         │
       close_date = now          close_date = now
              │
       ┌──────┴──────┐
       │             │
team.use_rating   NO rating
= True            (email sent)     team.use_rating
       │             │          = False
rating.rating      │             │
record created      │             │
       │             │             │
  Email sent     Email sent    Ticket closed
  to customer    to customer   (no rating)
       │             │
  Customer     Customer does
  rates 1-5    not respond
       │             │
  ┌────┴────┐   Rating expired
  │         │   (after N days)
good/poor  no action
  │         │
  │    Ticket stays closed
  │
  ├─► Good (>= threshold) → kanban_state='done' → DONE
  │
  └─► Poor (< threshold)
        ├─► kanban_state='blocked'
        ├─► Manager notified
        └─► Reopen or Escalate?
              ├─► Reopen → Back to In Progress
              └─► Escalate → Priority bumped + new team
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `helpdesk_ticket` | **Updated** | stage_id, close_date, close_hours, kanban_state |
| `helpdesk_sla_status` | **Updated** | reached_datetime set for matching SLA stages; status recomputed |
| `rating_rating` | **Created** (Path B) | res_model='helpdesk.ticket', res_id=ticket.id, rating=0, consumed=False; **Updated** (Path C) with actual rating and feedback |
| `mail_message` | **Created** | Stage change notification; rating posted; escalation notice |
| `mail_mail` | **Created/Queued** | Rating request email; solution notification |

### Close Resolution States

| Outcome | `stage_id` | `close_date` | `kanban_state` | `rating.rating.consumed` |
|---------|-----------|-------------|----------------|--------------------------|
| Solved (good rating) | Folded (solved) | Set | `done` | `True` |
| Solved (no rating) | Folded (solved) | Set | `normal` | `False` |
| Solved (bad rating) | Folded (solved) | Set | `blocked` | `True` |
| Reopened | Not folded | Cleared | `normal` | Unchanged |
| Escalated | Not folded | Cleared | `normal` | Unchanged |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Close already-closed ticket | No error | `write()` re-runs, `close_date` already set — no-op |
| Rate already-rated ticket | No error | Rating `write()` succeeds; second rating overwrites |
| Reopen cancelled ticket | Business logic | Cancelled stage may have `fold=True` but is final |
| Escalate without escalation team | `ValidationError` | No valid team to escalate to |
| Rating after expiry | Rating accepted | No time-based restriction in base code |
| Close ticket with unsent response | No error | Ticket can be closed without sending solution |
| Auto-close cron with no to_stage_id | Cron skips ticket | `to_stage_id` required for auto-close |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Close date recorded | `helpdesk.ticket.close_date` | Used to compute `close_hours` and `open_hours` |
| SLA reached recorded | `helpdesk.sla.status.reached_datetime` | Compared to `deadline` to determine `status='reached'` or `'failed'` |
| Rating email sent | `mail.mail` | Queued for sending via `ir.mail_server` |
| Customer notified of close | `mail.message` | Subtype `mt_ticket_stage` posted to chatter |
| Team satisfaction score | `helpdesk.team` composite | Rating stats updated via `_rating_get_parent_field_name` |
| Unanswered message cleared | `oldest_unanswered_customer_message_date` | Set to `False` on close |
| Portal access | `mail.followers` | Partner still subscribed; can still see closed ticket |
| Sequence on dashboard | `helpdesk.team.ticket_closed` | Counter incremented for last-7-day stats |

---

## Security Context

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `write({'stage_id': ...})` | Current user | `helpdesk.group_helpdesk_user` | Stage must be in team's `stage_ids` |
| `_sla_reach()` | `sudo()` | `helpdesk.group_use_sla` | Internal SLA status write |
| `rating.rating.write()` | Public (token) | No login required | Portal rating via `/rate/{token}` |
| `action_reopen()` | Current user | `helpdesk.group_helpdesk_user` | Stage must allow reopen |
| `action_escalate()` | Current user | `helpdesk.group_helpdesk_manager` | Only managers can escalate |
| `_notify_bad_rating()` | Current user | `helpdesk.group_helpdesk_manager` | Manager notification |
| Rating email queue | `mail.group` | Public | Follower-based; sent without login |

**Key principle:** Rating submission via portal link is **public** — no login required. The token in the URL (`/rate/{token}`) identifies the rating record. This is intentional for customer experience.

---

## Transaction Boundary

```
Stage change write   ✅ INSIDE transaction — atomic
_sla_reach()         ✅ INSIDE transaction — atomic
_rating_apply()      ✅ INSIDE transaction — creates rating.rating
Email queue (rating) ❌ OUTSIDE transaction — via mail.mail queue
Rating write (customer) ❌ OUTSIDE transaction — customer HTTP POST
_notify_bad_rating() ✅ INSIDE transaction — if done within same request
action_escalate()    ✅ INSIDE transaction — all writes atomic
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| `helpdesk.ticket.write()` | ✅ Atomic | Rollback entire stage change |
| `_sla_reach()` | ✅ Atomic | Rolled back with stage change |
| `rating.rating.create()` | ✅ Atomic | Rolled back if stage change fails |
| Rating request email | ❌ Async queue | Email not sent; rating record exists |
| Customer rating write | ❌ HTTP request | If HTTP fails, rating not recorded; ticket stays open |
| `action_reopen()` | ✅ Atomic | All writes atomic |
| `action_escalate()` | ✅ Atomic | All writes atomic |

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Double-click "Close" button | Only one stage write; `close_date` already set — idempotent |
| Re-close an already closed ticket | `write()` re-runs, `close_date` unchanged — idempotent |
| Submit same rating twice | Second `write()` on `rating.rating` overwrites — not idempotent for rating |
| Trigger `action_escalate()` twice | Priority bumped twice; team could change twice — not idempotent |
| Reopen already-open ticket | `write()` succeeds, `close_date` already `False` — idempotent |
| Auto-close cron re-runs | Same tickets already closed — cron checks `stage_id.fold` |

**Common patterns:**
- **Idempotent:** Stage changes with close/open detection, SLA reach computation
- **Non-idempotent:** Rating write, escalation (priority bump accumulates)

---

## Extension Points

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Pre-close | `write()` override | Validate before stage change | vals | Extend `write()` with `super()` |
| SLA reach | `_sla_reach()` | Custom SLA reach logic | stage_id | Override on `HelpdeskTicket` |
| Rating request | `rating_parent_mixin._rating_apply()` | Custom rating trigger | rating, subtype | Override in `HelpdeskTeam` |
| Bad rating notify | `_notify_bad_rating()` | Custom escalation notification | self | Add via inheritance |
| Reopen validation | `action_reopen()` | Custom reopen rules | self | Extend with `super()` |
| Escalation logic | `action_escalate()` | Custom escalation targets | self | Override on `HelpdeskTicket` |
| Post-close | `write()` after stage change | Side effects on close | vals | Extend `write()` with post-processing |

**Standard override pattern:**
```python
# Extending ticket close behavior
def write(self, vals):
    if vals.get('stage_id') and self._is_closing(vals['stage_id']):
        # Custom pre-close validation
        self._validate_close_conditions()
    res = super().write(vals)
    if vals.get('stage_id') and self._is_closing(vals['stage_id']):
        # Custom post-close side effects
        self._after_close_hook()
    return res

def _is_closing(self, stage_id):
    stage = self.env['helpdesk.stage'].browse(stage_id)
    return stage.fold
```

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Stage change to closed | `action_reopen()` | `write({'stage_id': in_progress_id, 'close_date': False})` | SLA deadline may be recalculated |
| Rating sent | Cannot unsend email | Manual apology email | Email already delivered |
| Rating received | Cannot un-rate | Agent creates new subticket | Original rating stays in history |
| `kanban_state` = 'blocked' | Re-rate or reopen | `action_reopen()` | Manager must investigate |
| Escalation | Manual reassign | `write({'team_id': original_id})` | Escalation not tracked automatically |

**Important:** The **SLA status** is not automatically reset when a ticket is reopened. If the SLA should restart, call `_sla_apply()` after reopening. Closing a ticket with a `fold=True` stage sets the `close_date` and marks SLAs as `reached` or `failed` — these are **not automatically reversed** on reopen.

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | Stage drag in Kanban | Interactive | Manual |
| User action | "Close" button (direct stage write) | Interactive | Manual |
| Email response | `message_update()` on closed ticket | Inbound email | Per email |
| Cron scheduler | `_cron_auto_close_tickets()` | Server cron | Daily (configurable) |
| Portal action | Customer clicks "Solved" on portal | Customer portal | Per ticket |
| Rating portal | Customer submits `/rate/{token}` | Public link | Per ticket |
| API / RPC | `execute_kw('helpdesk.ticket', 'write', [ids, vals])` | External | On demand |

**For AI reasoning:** The auto-close cron (`ir_cron_auto_close_ticket`) runs on tickets that have been in `from_stage_ids` for more than `auto_close_day` days. It writes `stage_id = to_stage_id`. This is independent of the manual close flow.

---

## Related

- [[Modules/Helpdesk]] — Module reference
- [[Flows/Helpdesk/ticket-creation-flow]] — Ticket creation and SLA application
- [[Business/Helpdesk/helpdesk-configuration-guide]] — Configuring stages and rating
- [[Patterns/Workflow Patterns]] — State machine pattern reference
- [[Core/API]] — @api.depends, write() override patterns
