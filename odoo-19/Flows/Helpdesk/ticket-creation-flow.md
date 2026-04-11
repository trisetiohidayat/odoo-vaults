---
type: flow
title: "Ticket Creation Flow"
primary_model: helpdesk.ticket
trigger: "User action / Email — Helpdesk → Create Ticket"
cross_module: true
models_touched:
  - helpdesk.ticket
  - helpdesk.team
  - helpdesk.sla
  - helpdesk.sla.status
  - mail.message
  - mail.followers
  - utm.source
  - utm.medium
  - utm.campaign
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[[Flows/Helpdesk/ticket-resolution-flow]]"
related_guides:
  - "[[Business/Helpdesk/helpdesk-configuration-guide]]"
source_module: helpdesk
source_path: ~/odoo/odoo19/odoo/addons/helpdesk/
created: 2026-04-07
version: "1.0"
---

# Ticket Creation Flow

## Overview

A helpdesk ticket is created when a customer submits a request via the portal, an email is sent to the team's alias, or an agent manually creates one. The flow auto-populates partner details, captures UTM attribution, applies SLA policies with deadline computation, and notifies the team. This is the entry point for the entire helpdesk lifecycle.

## Trigger Point

Three primary entry points initiate this flow:

| Trigger | Mechanism | Context |
|---------|-----------|---------|
| Portal form | `helpdesk.ticket.create(vals)` | Customer via website |
| Email alias | `helpdesk.ticket.message_new()` | Inbound mail gateway |
| Agent manually | `helpdesk.ticket.create(vals)` | Internal agent action |

---

## Complete Method Chain

```
1. helpdesk.ticket.create(vals)
   │
   ├── vals keys accepted:
   │     name, partner_id, team_id, partner_email, partner_name,
   │     partner_phone, priority, ticket_type_id, tag_ids, user_id
   │
   ├─► 2. res.partner.find_or_create()  [inline partner creation]
   │     └─► If partner_name + partner_email given but no partner_id:
   │           res.partner record created or matched via email_normalize
   │
   ├─► 3. ir.sequence.next_by_code('helpdesk.ticket')
   │     └─► ticket_ref generated (e.g. "00042")
   │
   ├─► 4. team._determine_stage()  [helpdesk.team]
   │     └─► Returns first stage where stage.sequence == 0 (stage_new)
   │     └─► Writes stage_id to vals if not already set
   │
   ├─► 5. team._determine_user_to_assign()  [helpdesk.team]
   │     └─► Returns user based on team.assign_method:
   │           'randomly': round-robin equal count per user
   │           'balanced': user with fewest open tickets wins
   │     └─► Writes user_id to vals if not already set
   │     └─► If user assigned: assign_date = now, assign_hours = 0
   │
   ├─► 6. helpdesk.ticket.super().create(list_value)  [BaseModel.create]
   │     └─► mail.thread create() hook fires
   │
   ├─► 7. message_subscribe(partner_ids=ticket.partner_id.ids)  [mail.thread]
   │     └─► mail.followers record created for partner
   │     └─► partner sees ticket in portal
   │
   ├─► 8. _portal_ensure_token()  [portal.mixin]
   │     └─► Access token generated for public portal URL
   │
   ├─► 9. _sla_apply()  [helpdesk.ticket]
   │     └─► 9a. _sla_find()
   │           Searches helpdesk.sla records matching:
   │           team_id, priority, stage_id.sequence >= ticket.stage_id.sequence,
   │           ticket_type_ids, tag_ids, partner_ids
   │     └─► 9b. _sla_generate_status_values(slas)
   │           Creates helpdesk.sla.status records with:
   │           deadline = create_date + working_calendar.plan_days()
   │           (uses team.resource_calendar_id for working-hours computation)
   │     └─► 9c. helpdesk.sla.status records created (one per SLA policy)
   │
   └─► 10. mail.message records created by mail.thread.create()
          └─► _creation_subtype() → 'helpdesk.mt_ticket_new'
                └─► subtype_id = helpdesk.mt_ticket_new
                      └─► Email notification sent to ticket followers
```

### UTM Tag Capture (via mail.thread)

```
During message_subscribe or mail.message.create:
  └─► utm.mixin._track_subtype(init_values)
        └─► Reads email headers or partner's utm_{campaign,medium,source}_id
        └─► Writes utm.campaign, utm.source, utm.medium on ticket if found
```

### _track_template for Stage Notification

```
On create, if stage_id has a template_id:
  └─► _track_template({'stage_id'})
        └─► stage_id.template_id email template rendered
        └─► mail.tracking.value created for stage change
        └─► Email sent via email_layout_xmlid 'mail.mail_notification_light'
```

---

## Decision Tree

```
Ticket created (helpdesk.ticket.create)
│
├─► partner_id provided?
│  ├─► YES → partner_id set, partner_email derived from partner
│  └─► NO + partner_email provided?
│         └─► YES → res.partner.find_or_create() → partner_id linked
│         └─► NO → ticket created without partner (anonymous)
│
├─► team_id provided?
│  ├─► YES → _determine_stage() + _determine_user_to_assign() applied
│  └─► NO → _default_team_id(): searches user's team or first team
│
├─► user_id provided or auto-assigned?
│  ├─► YES → assign_date = now, assign_hours = 0
│  └─► NO → unassigned ticket, shown in "Unassigned Tickets" dashboard
│
├─► UTM tags captured?
│  └─► YES (if partner has utm_source_id / utm_campaign_id)
│        └─► utm.source, utm.medium, utm.campaign linked to ticket
│
├─► SLA applied?
│  ├─► YES (if team.use_sla == True and matching SLA policies exist)
│  │     └─► helpdesk.sla.status created with deadline
│  └─► NO (no SLA configured or team not using SLA)
│
├─► Email notification sent?
│  └─► YES: 'helpdesk.mt_ticket_new' subtype triggers email to followers
│        └─► If partner_email exists → email sent to customer
│        └─► If user_id assigned → notification to assigned agent
│
└─► Assigned to team member?
   └─► YES (if auto_assignment or user_id explicitly set)
         └─► message_subscribe(assignee) → assignee notified
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `helpdesk_ticket` | **Created** | name, team_id, partner_id, user_id, stage_id, priority, ticket_ref, create_date |
| `helpdesk_sla_status` | **Created** (one per matching SLA) | ticket_id, sla_id, deadline, status='ongoing' |
| `mail_followers` | **Created** | res_model='helpdesk.ticket', res_id=ticket.id, partner_id |
| `mail_message` | **Created** | model='helpdesk.ticket', subtype='helpdesk.mt_ticket_new', message_type='notification' |
| `res_partner` | **Created or Updated** (if new partner from email) | id linked via partner_id |
| `utm_source_rel` | **Updated** (if UTM matched) | source_id on partner linked to ticket |
| `ir_sequence` | **Updated** | next number consumed for 'helpdesk.ticket' |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Team does not exist | `ValidationError` | `team_id` is a Many2one to existing `helpdesk.team` |
| Partner email already exists | No error | `res.partner.find_or_create()` matches existing or creates new |
| No team available | No error | Ticket created with `team_id = False`, unassigned |
| SLA policy has no deadline | No deadline set | `resource.calendar` missing on team — `status.deadline = create_date` |
| User not in team members | Auto-assignment skips user | `_determine_user_to_assign()` only considers `team.member_ids` |
| Duplicate ticket_ref | `_sql_constraints` unique | Ticket reference sequence is sequential — no concurrent duplicates |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Partner subscribed | `mail.followers` | Customer can view ticket in portal |
| Portal token generated | `portal.mixin` | Customer receives unique access URL `/my/ticket/{id}` |
| SLA status created | `helpdesk.sla.status` | Deadline tracked; shown in Kanban SLA columns |
| Sequence consumed | `ir.sequence` | Next ticket gets "00043", etc. |
| Team open ticket count | `helpdesk.team.open_ticket_count` | Dashboard counter incremented |
| Assign date set | `helpdesk.ticket.assign_date` | Used to compute `assign_hours` for reporting |
| Partner email synced | `res.partner` | If `partner_email` differs, `_inverse_partner_email` may update partner |

---

## Security Context

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `create()` | Current user | `helpdesk.group_helpdesk_user` | Portal users can create via `/my/ticket` |
| `_determine_user_to_assign()` | `sudo()` inside team | No ACL | Internal auto-assignment logic |
| `_sla_apply()` | `sudo()` | `helpdesk.group_use_sla` | SLA computation runs as superuser |
| `message_subscribe()` | Current user | Write on ticket | Adds follower to current record |
| `res.partner.find_or_create()` | Current user | Write on partner | Creates partner if name+email given |
| Email notification | `mail.group` | Public | Follower-based — anyone subscribed gets email |

**Key principle:** Ticket creation runs as the **current logged-in user** (agent, portal user, or public). The `sudo()` call in `_sla_apply()` bypasses ACL only for SLA status writes, not for the ticket itself.

---

## Transaction Boundary

```
Steps 1-8  ✅ INSIDE transaction  — atomic (all or nothing)
Step 9     ✅ INSIDE transaction  — helpdesk.sla.status.create() within same DB transaction
Step 10    ❌ OUTSIDE transaction — via mail.queue_discuss (email notification)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| `helpdesk.ticket.create()` | ✅ Atomic | Rollback on any error |
| `res.partner.find_or_create()` | ✅ Atomic | Rolled back with ticket |
| `ir.sequence.next_by_code()` | ✅ Atomic | Rolled back with ticket |
| `_sla_apply()` | ✅ Atomic | Rolled back with ticket |
| `mail_followers` insert | ✅ Atomic | Rolled back with ticket |
| Email notification (mt_ticket_new) | ❌ Async queue | Retried by `ir.mail_server` cron; ticket already created |

**Rule of thumb:** All ORM `create()` calls within the `create()` method body are **atomic**. Only the email notification dispatched after the transaction commits is outside the boundary.

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Double-click "Create" button | ORM deduplicates — only one record created |
| Re-submit same email to alias | `message_new()` called twice — two tickets created |
| API call with same vals | `create()` produces new record each time (not idempotent) |
| Email with same Message-ID re-processed | `mail.message` deduplication prevents duplicate creation |
| SLA re-applied manually | `_sla_apply()` deletes old `helpdesk.sla.status` and recreates — safe to retry |

**Common patterns:**
- **Idempotent:** `create()` with duplicate prevention at application level
- **Non-idempotent:** Sequence increment — each call consumes a number even on rollback

---

## Extension Points

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Pre-create | `create()` vals loop | Pre-creation vals modification | vals | Extend `create()` with `super()` first, then modify |
| Partner creation | `res.partner.find_or_create()` | Custom partner matching logic | email, name | Override `find_or_create()` on `res.partner` |
| Stage determination | `helpdesk.team._determine_stage()` | Custom first-stage logic | self | Extend via inheritance on `HelpdeskTeam` |
| User assignment | `helpdesk.team._determine_user_to_assign()` | Custom assignment algorithm | self | Extend via inheritance on `HelpdeskTeam` |
| SLA policy | `helpdesk.ticket._sla_find()` | Custom SLA selection | self | Override `_sla_find_extra_domain()` |
| UTM capture | `utm.mixin._track_subtype()` | Custom campaign attribution | init_values | Extend via `mail.thread` inheritance on ticket |
| Post-create | `_sla_apply()` | Post-creation side effects | self | Extend with `super()._sla_apply()` then custom code |

**Standard override pattern:**
```python
# Extending ticket creation
@api.model_create_multi
def create(self, list_value):
    # Pre-processing
    for vals in list_value:
        if not vals.get('ticket_ref'):
            vals['ticket_ref'] = self.env['ir.sequence'].sudo().next_by_code('helpdesk.ticket')
    tickets = super().create(list_value)
    # Post-processing
    for ticket in tickets:
        ticket._custom_post_create_hook()
    return tickets
```

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `create()` | `unlink()` | `record.unlink()` | Cascade deletes `helpdesk.sla.status`; mail_followers removed; email notifications not retracted |
| `message_subscribe()` | `message_unsubscribe()` | `ticket.message_unsubscribe(partner_ids)` | Partner loses portal access |
| `_sla_apply()` | `_sla_apply(keep_reached=True)` | Re-apply SLA | Only preserves `reached_datetime` on already-reached SLAs |
| Portal token | Regenerate | `_portal_ensure_token()` | Old token invalidated |

**Important:** Unlinking a ticket **does not** delete the `mail.message` records — they remain as orphaned records. Email notifications already sent are **not** recalled.

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `helpdesk.ticket.create()` form | Interactive | Manual |
| Email alias | `message_new()` | Inbound mail gateway | Per email |
| Portal form | `/my/ticket` submit | Customer portal | Per submission |
| API / RPC | `execute_kw('helpdesk.ticket', 'create', [vals])` | External system | On demand |
| Onchanges on related models | `_compute_user_and_stage_ids()` | team_id change | On demand |
| Automated action | `base.automation` | Rule triggered | On rule match |

**For AI reasoning:** When asked "what happens if X?", trace all triggers to understand full impact. Email-based creation (`message_new`) bypasses some vals defaults and requires careful handling of `partner_id` population via `_mail_find_partner_from_emails()`.

---

## Related

- [[Modules/Helpdesk]] — Module reference
- [[Flows/Helpdesk/ticket-resolution-flow]] — Ticket close, rating, and reopen
- [[Business/Helpdesk/helpdesk-configuration-guide]] — Team, stage, and SLA configuration
- [[Patterns/Workflow Patterns]] — State machine pattern reference
- [[Core/API]] — @api.depends, @api.model_create_multi decorator patterns
