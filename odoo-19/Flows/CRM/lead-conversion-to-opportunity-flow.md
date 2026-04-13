---
type: flow
title: "Lead Conversion to Opportunity Flow"
primary_model: crm.lead
trigger: "User action — Lead → Convert to Opportunity"
cross_module: true
models_touched:
  - crm.lead
  - res.partner
  - sale.order
  - crm.stage
  - mail.activity
  - mail.message
audience: ai-reasoning, developer
level: 1
source_module: crm
source_path: ~/odoo/odoo19/odoo/addons/crm/
created: 2026-04-07
version: "1.0"
---

# Lead Conversion to Opportunity Flow

## Overview

Converting a qualified lead into a sales opportunity moves the record from `type='lead'` to `type='opportunity'`, assigns it to the pipeline, optionally creates or links a `res.partner`, and optionally creates a `sale.order` draft. This is the core bridge between marketing (leads) and sales (pipeline). The wizard `crm.lead.convert.lead2opportunity` gives the user full control over partner assignment and order creation.

## Trigger Point

Two entry paths:

1. **Wizard** — Lead form → "Convert to Opportunity" button → `crm.lead.to.opportunity` wizard opens → user fills options → `wizard.apply()` called
2. **Direct action** — `action_convert_opportunity(partner_id, user_id, team_id)` called programmatically (skips wizard)

---

## Complete Method Chain

```
1. action_convert_opportunity() / wizard.apply()
   │
   ├─► 2. _convert_opportunity_stage()
   │     └─► 3. stage_id set to first opportunity stage (sequence > 1, not won)
   │
   ├─► 4. _onchange_partner_id()        [re-evaluated after partner change]
   │     └─► 5. fields synced from selected partner
   │
   ├─► 6. partner_id assigned           [from wizard or existing]
   │     └─► 7. IF create_partner=True:
   │            └─► 8. _create_new_lead_partner() → res.partner.create({...})
   │                  └─► 9. partner_id written to lead
   │
   ├─► 10. _handle_partner_assignment()
   │      └─► 11. IF existing partner found by email: used
   │            └─► 12. commercial_partner_id updated
   │
   ├─► 13. IF link_to_existing_opportunity=False:
   │      └─► 14. sale.order.create()   [draft SO from opportunity vals]
   │            └─► 15. opportunity_id written on sale.order
   │                  └─► 16. sale_order_ids added to crm.lead
   │
   ├─► 17. type = 'opportunity'         [write to lead]
   │     └─► 18. probability reset to automated value
   │
   ├─► 19. lost_reason_id = False      [clear if set]
   │     └─► 20. lead removed from lost list
   │
   ├─► 21. activity_scheduled()         [follow-up activity]
   │      └─► 22. mail.activity created for assigned user
   │
   ├─► 23. message_post "Converted to Opportunity"  [mail.thread]
   │      └─► 24. mail.message created, followers notified
   │
   ├─► 25. UTM data preserved           [utm_source_id, campaign_id, medium_id kept]
   │
   ├─► 26. date_conversion = now()
   │
   ├─► 27. date_open = now()            [assignment timestamp]
   │
   ├─► 28. last_activity_id updated     [activity reference stored]
   │
   └─► 29. IF sale_order_ids exist:
          └─► 30. sale.order records linked, opportunity_id set on each
```

---

## Decision Tree

```
Convert to Opportunity Wizard
│
├─► create_partner = True?
│  ├─► YES → new res.partner created from lead contact fields
│  └─► NO → skip partner creation
│
├─► existing partner found by email?
│  ├─► YES → partner_id = existing partner (deduplicated)
│  └─► NO → no partner linked
│
├─► deduplicate_leads = True?
│  ├─► YES → _merge_opportunity() called — lead merged with existing
│  └─► NO → no merge
│
├─► user_id set in wizard?
│  ├─► YES → assigned user overridden
│  └─► NO → keep existing user_id
│
├─► team_id set in wizard?
│  ├─► YES → team reassigned
│  └─► NO → keep existing team_id
│
└─► ALWAYS:
   └─► stage → first opportunity stage, type → 'opportunity'
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `crm_lead` | Updated | type='opportunity', stage_id, partner_id, user_id, date_conversion |
| `res_partner` | Created (optional) | name, email, phone, commercial_partner_id |
| `sale_order` | Created (optional) | partner_id, origin=crm_lead.name, state='draft' |
| `mail_activity` | Created | res_model='crm.lead', user_id, activity_type_id |
| `mail_message` | Created | body='Converted to Opportunity', model='crm.lead' |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Lead already converted | `UserError` | "Lead is already an opportunity" |
| Invalid partner_id in wizard | `ValidationError` | Partner must exist in res.partner |
| Access denied (no write rights) | `AccessError` | CRM user ACL required |
| User not in selected team | `UserError` | Sales team membership validation |
| Conversion without required fields | `ValidationError` | Name required on opportunity |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Type changed | `crm_lead` | `type` flips from 'lead' to 'opportunity' |
| Partner created | `res_partner` | New contact from lead's email/phone/name |
| Sale order draft created | `sale_order` | Draft SO linked to opportunity |
| Follow-up activity scheduled | `mail_activity` | To-do created for assigned salesperson |
| Chatter logged | `mail_message` | Conversion event recorded in discussion |
| Lost reason cleared | `crm_lead` | `lost_reason_id` set to False |
| Lead removed from lost list | `crm_lead` | Added back to active pipeline |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `action_convert_opportunity()` | Current user | `group_crm_user` | Respects record rules |
| `sale.order.create()` | `sudo()` | Write on sale.order | System context for cross-model write |
| `res.partner.create()` | `sudo()` | Write on res.partner | Partner creation needs superuser |
| `activity_schedule()` | Current user | Write on mail.activity | User-context activity creation |
| `message_post()` | `mail.thread` | Read ACL on crm.lead | Follower-based notification |

**Key principle:** Most Odoo methods run as the **current logged-in user**, not as superuser. Use `sudo()` only when intentionally bypassing ACL.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1-29  ✅ ALL INSIDE transaction  — atomic (all or nothing)
sale.order.create() — within same DB transaction
partner create() — within same DB transaction
activity + message_post — within same DB transaction
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-29 | ✅ Atomic | Full rollback — lead, partner, SO all rolled back |
| Sale order creation | ✅ Within ORM | Rolled back with transaction |
| Partner creation | ✅ Within ORM | Rolled back with transaction |
| Notification email | ❌ Async queue | Retried by `ir.mail.server` cron |

**Rule of thumb:** If it's inside `create()`/`write()` body → inside transaction. If it uses `mail.mail` (outbound email) → outside transaction (queue).

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click Convert button | First call succeeds, second raises `UserError` ("already an opportunity") |
| Re-convert archived lead | Must first reactivate (`action_unarchive`), then convert |
| Wizard re-opened on already-converted lead | Form shows error, convert button disabled |
| Partner already exists with same email | Partner dedup prevents duplicate — existing partner used |

**Common patterns:**
- **Non-idempotent:** Converting a lead to opportunity (can only happen once)
- **Idempotent:** State checks prevent re-conversion safely

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `_convert_opportunity_stage()` | Custom stage selection logic | self | Override to set different target stage |
| Step 8 | `_create_new_lead_partner()` | Custom partner creation | vals, lead | Extend with `super()` + extra fields |
| Step 11 | `_handle_partner_assignment()` | Custom partner matching | self | Override to add dedup rules |
| Step 14 | `sale.order.create()` hook | Create SO from custom vals | self, vals | Add `@api.model` method to prepare SO vals |
| Pre-write | `_before_write()` hook | Pre-conversion validation | vals | Extend `write()` override |
| Post-conversion | `_crm_lead_post_convert()` | Post-conversion side effect | self | Override `action_convert_opportunity()` |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def action_convert_opportunity(self, partner_id):
    # your code

# CORRECT — extends with super()
def action_convert_opportunity(self, partner_id):
    res = super().action_convert_opportunity(partner_id)
    # your additional code
    return res
```

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Convert to opportunity | Archive opportunity | `write({'active': False})` | Lead recoverable via "Unarchive" |
| New partner created | Unlink partner | `partner.unlink()` | Only if no other records linked |
| Sale order created | Cancel draft SO | `sale_order.action_cancel()` | Must not be confirmed |
| Stage changed | Revert stage manually | `write({'stage_id': old_id})` | Probability may not revert |
| User reassigned | Reassign | `write({'user_id': original_id})` | History preserved in chatter |

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_convert_opportunity()` button | Interactive | Manual |
| Wizard | `crm.lead.to.opportunity` model | Interactive | Per wizard submission |
| Automated action | `base.automation` rule | Rule triggered | Per rule match |
| API / external | RPC `execute_kw` call | External system | On demand |
| Onstage change | Stage → auto-convert setting | Config-based | Automatic on stage entry |

**For AI reasoning:** When asked "what happens if X?", trace all triggers to understand full impact. The wizard is the most common path; the direct action path is typically used by automated rules.

---

## Related

- [Flows/CRM/lead-creation-flow](lead-creation-flow.md) — Lead creation sources
- [Flows/CRM/opportunity-win-flow](opportunity-win-flow.md) — Mark opportunity as won
- [Flows/CRM/lead-assignment-flow](lead-assignment-flow.md) — Auto-assignment after conversion
- [Modules/CRM](CRM.md) — CRM module reference
- [Modules/Sale](Sale.md) — Sale order from opportunity
- [Modules/res.partner](res.partner.md) — Partner model reference
- [Patterns/Workflow Patterns](Workflow Patterns.md) — Pipeline stage patterns
- [Core/API](API.md) — @api decorator patterns
