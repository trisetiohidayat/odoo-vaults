---
type: flow
title: "Lead Assignment Flow"
primary_model: crm.lead
trigger: "Cron scheduler — Daily at 01:00 / Manual — CRM → Assignment → Assign Leads"
cross_module: true
models_touched:
  - crm.lead
  - crm.team
  - crm.team.member
  - crm.assignment.rule
  - mail.activity
  - mail.message
audience: ai-reasoning, developer
level: 1
source_module: crm
source_path: ~/odoo/odoo19/odoo/addons/crm/
created: 2026-04-07
version: "1.0"
---

# Lead Assignment Flow

## Overview

The lead assignment flow automatically distributes unassigned leads to sales team members based on configurable assignment rules. It runs as a nightly cron job (`ir_cron_crm_lead_assign`) or can be triggered manually from the CRM dashboard. The system evaluates territory, skill, workload, and round-robin rules to decide which user receives each lead. This ensures leads are never left unassigned and that workload is balanced across the team.

## Trigger Point

Two entry paths:

1. **Cron scheduler** — `ir_cron_crm_lead_assign` runs daily at 01:00 server time → `_cron_assign_leads()` → `_action_assign_leads()`
2. **Manual trigger** — CRM → Leads → Assignment tab → "Assign Leads" button → `action_assign_leads()` → `_action_assign_leads()`

---

## Complete Method Chain

```
1. _action_assign_leads()                [entry point from cron or manual]
   │
   ├─► 2. _get_assignable_leads()        [query unassigned, active, not lost]
   │     └─► 3. domain: [('user_id', '=', False), ('active', '=', True),
   │                      ('stage_id.is_won', '=', False), team assignment_enabled=True]
   │
   ├─► 4. _allocate_leads()              [distribute leads to teams first]
   │     └─► 5. leads matched to teams by territory/domain
   │           └─► 6. write({'team_id': matched_team.id}) on each lead
   │
   ├─► 7. _run_cron_assign()             [batch assignment loop per team]
   │     └─► 8. for each team with leads:
   │           └─► 9. _assign_and_convert_leads() per team
   │                 └─► 10. for each lead in team:
   │
   ├─► 11. crm.assignment.rule.apply(lead)  [evaluate all rules for lead]
   │     └─► 12. rule evaluation: territory match
   │           └─► 13. rule evaluation: skill/product match
   │                 └─► 14. rule evaluation: workload balance check
   │
   ├─► 15. IF rule.type = 'round_robin':
   │      └─► 16. next_user = rotation_list.pop(0); rotation_list.append(next_user)
   │
   ├─► 17. IF rule.type = 'load_balancing':
   │      └─► 18. user with lowest current workload selected
   │            └─► 19. lead_month_count checked against assignment_max
   │
   ├─► 20. IF rule.type = 'random':
   │      └─► 21. random.shuffle(team_member_ids); assign to first
   │
   ├─► 22. write({'user_id': assigned_user.id, 'team_id': assigned_team.id})
   │
   ├─► 23. write({'date_last_action': fields.Datetime.now()})
   │      └─► 24. date_last_stage_update updated
   │
   ├─► 25. activity_schedule()          [follow-up activity for assigned user]
   │      └─► 26. mail.activity created with type from team template
   │
   ├─► 27. message_post "Lead assigned to {user.name}"
   │      └─► 28. mail.message created, assigned user follows lead
   │
   ├─► 29. IF auto_create_activity:
   │      └─► 30. next activity planned based on team schedule template
   │
   ├─► 31. IF max_assign reached per user:
   │      └─► 32. user skipped, next user selected
   │            └─► 33. lead_ids consumed from pool, loop continues
   │
   └─► 34. Assignment log written to lead chatter
```

---

## Decision Tree

```
Lead Pulled from Assignment Pool
│
├─► Assignment rule type = round_robin?
│  ├─► YES → sequential assignment from team rotation list
│  └─► NO
│
├─► Assignment rule type = load_balancing?
│  ├─► YES → user with lowest lead_month_count selected
│  │       └─► user has capacity? (monthly < max) → assign
│  │       └─► NO capacity → skip to next lowest
│  └─► NO
│
├─► Assignment rule type = random?
│  ├─► YES → random.shuffle of eligible members → assign to first
│  └─► NO
│
├─► Territory/field domain match?
│  ├─► YES → user with matching territory assigned
│  └─► NO → fall back to default round_robin
│
├─► User assignment_max reached?
│  ├─► YES → skip user, select next in priority order
│  └─► NO → assign to this user
│
└─► ALWAYS:
   └─► activity scheduled for assigned user, chatter logged
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `crm_lead` | Updated | user_id assigned, team_id set, date_last_action |
| `crm_team_member` | Updated | lead_month_count incremented |
| `mail_activity` | Created | user_id = assigned user, activity_type_id, res_model='crm.lead' |
| `mail_message` | Created | body='Lead assigned to {name}', model='crm.lead' |
| `mail_followers` | Created/Updated | assigned user added as follower |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No assignment rules configured | Silent skip | No leads assigned, log entry written |
| All team members at max capacity | Silent skip | Leads left unassigned for the day |
| User removed from team during run | `AccessError` / skip | User no longer in team — skipped |
| Assignment cron runs with no leads | Silent no-op | Normal behavior — nothing to assign |
| Concurrent assignment by two crons | Locking / race condition | `ir.cron` with `multi`=False prevents overlap |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Lead assigned to user | `crm_lead` | user_id, team_id, date_last_action updated |
| User follower added | `mail_followers` | Assigned user automatically follows the lead |
| Follow-up activity created | `mail_activity` | To-do created for assigned user |
| Monthly count incremented | `crm_team_member` | lead_month_count updated on team member |
| Assignment logged | `mail_message` | Chatter records who was assigned and when |
| Lead removed from unassigned pool | `crm_lead` | user_id set → no longer matches domain filter |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `_cron_assign_leads()` | `sudo()` (superuser) | System cron context | Bypasses user ACL for system-level logic |
| `_action_assign_leads()` | `sudo()` (via cron) | System cron context | Lead writes as superuser |
| Manual trigger | Current user | `group_crm_manager` | Only managers can trigger manual assignment |
| `write({'user_id': ...})` | `sudo()` | System write | Required to assign leads to any user |
| `activity_schedule()` | `sudo()` (cron) | Write on mail.activity | Activity created as superuser |
| `message_post()` | `mail.thread` | Read ACL on crm.lead | Follower-based notification |

**Key principle:** The cron-triggered assignment runs as **superuser** (`sudo()`) to allow cross-user assignment without permission issues. Manual triggers respect user ACLs and require manager-level access.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1-33  ✅ ALL INSIDE transaction  — atomic
Individual lead assignments are batched per commit bundle
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-33 | ✅ Atomic (per lead) | Each lead assignment is atomic |
| Bundle commit | ✅ Per N leads | `crm.assignment.commit.bundle` commits every N leads |
| Activity creation | ✅ Within ORM | Rolled back with lead assignment |
| Notification email | ❌ Async queue | Retried by `ir.mail.server` cron |
| Cron failure mid-batch | Partial commit | Previously committed bundles persist; remaining skipped |

**Rule of thumb:** The assignment uses bundle commits to avoid a single bad lead blocking the entire batch. If a lead write fails, only that lead is skipped — the rest continue.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Cron re-runs within same night | Already-assigned leads filtered out — no double assignment |
| Manual trigger while cron running | `multi=False` on cron prevents concurrent cron instances |
| Re-trigger on already-assigned lead | Lead already has user_id — not in assignable pool — skipped |
| Assignment_max reset mid-batch | Next cron run (next day) will pick up capacity |
| Lead assigned, user then removed | Lead retains assignment — user removal does not cascade-unassign |

**Common patterns:**
- **Idempotent:** Assignment is idempotent per lead (already assigned = skipped)
- **Non-idempotent:** `lead_month_count` increments on every assignment run

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `_get_assignable_leads()` | Custom lead filter domain | self | Override to add domain restrictions |
| Step 11 | `crm.assignment.rule.apply()` | Custom rule evaluation logic | lead | Extend rule model with new types |
| Step 15 | Round-robin rotation logic | Custom rotation algorithm | self | Override `_get_next_rr_user()` |
| Step 17 | Load-balancing logic | Custom workload calculation | self | Override `_get_least_busy_user()` |
| Step 25 | `activity_schedule()` | Custom activity type | self | Override to set different activity template |
| Post-assignment | `_crm_lead_post_assign()` | Post-assignment side effect | self, user_id | Extend `_action_assign_leads()` |
| Territory match | `_match_territory()` | Custom territory logic | lead, team | Override to add geo-matching |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def _action_assign_leads(self):
    # your code

# CORRECT — extends with super()
def _action_assign_leads(self):
    res = super()._action_assign_leads()
    # your additional code
    return res
```

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Lead assigned to wrong user | Reassign | `write({'user_id': correct_user_id})` | Original assignment overwritten |
| Unassign lead | `write({'user_id': False})` | Manual unassign | Lead goes back to unassigned pool |
| Re-run assignment | `_action_assign_leads()` again | Next cron or manual trigger | Already-assigned leads filtered — only truly unassigned leads get picked |
| Activity not wanted | Mark activity done/cancelled | `activity.action_done()` | Activity still in DB, just closed |
| Monthly count incorrect | Direct DB write | Admin-only SQL | Not recommended — use Odoo's reset |

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| Cron scheduler | `ir_cron_crm_lead_assign` | Server startup | Daily at 01:00 (configurable) |
| Manual trigger | `action_assign_leads()` button | Interactive | Manual |
| Team-level trigger | `crm.team.action_assign_leads()` | Per team | Manual per team |
| Automated action | `base.automation` rule | Rule triggered | On rule match |
| API / external | RPC `execute_kw` call | External system | On demand |

**For AI reasoning:** When asked "what happens if X?", trace all triggers to understand full impact. The cron is the primary path — it runs every night so all leads accumulated during the day get distributed in the morning.

---

## Related

- [Flows/CRM/lead-creation-flow](lead-creation-flow.md) — Lead creation sources
- [Flows/CRM/lead-conversion-to-opportunity-flow](lead-conversion-to-opportunity-flow.md) — Lead → Opportunity conversion
- [Modules/CRM](CRM.md) — CRM module reference
- [Modules/sales_team](sales_team.md) — Sales team and member management
- [Patterns/Workflow Patterns](Workflow Patterns.md) — Pipeline stage patterns
- [Core/API](API.md) — @api decorator patterns
