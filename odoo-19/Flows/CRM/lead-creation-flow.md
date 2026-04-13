---
type: flow
title: "Lead Creation Flow"
primary_model: crm.lead
trigger: "User action — CRM → Leads → Create / Website form / Email alias / Import"
cross_module: true
models_touched:
  - crm.lead
  - res.partner
  - crm.team
  - utm.source
  - utm.campaign
  - utm.medium
  - mail.message
  - audience
audience: ai-reasoning, developer
level: 1
source_module: crm
source_path: ~/odoo/odoo19/odoo/addons/crm/
created: 2026-04-07
version: "1.0"
---

# Lead Creation Flow

## Overview

A CRM lead can be created from four distinct sources: manually by a salesperson, via a website form submission, through an incoming email alias routing, or by CSV/Excel import. Each source populates different fields and triggers different onchange cascades, but all ultimately result in a `crm.lead` record with `type='lead'`. UTM tracking is applied automatically when the source is known.

## Trigger Point

Four entry paths converge on `crm.lead.create(vals)`:

1. **Manual creation** — CRM → Leads → Create button (user fills form)
2. **Website form** — `website_crm_iap_reveal` or `website_form` controller POST
3. **Email alias** — incoming email routed via `mail.alias` to `crm.lead` model
4. **CSV/Excel import** — Settings → Import → Load File → `crm.lead` target

---

## Complete Method Chain

```
1. crm.lead.create(vals)
   │
   ├─► 2. _onchange_partner_id()        [if partner_id in vals]
   │     └─► 3. fields synced from res.partner (email, phone, address...)
   │
   ├─► 4. _onchange_stage_id()          [if stage_id in vals]
   │     └─► 5. default values from stage (requirements hint)
   │
   ├─► 6. _onchange_company_id()         [if company_id set]
   │     └─► 7. team_id assigned from company default_team_id
   │
   ├─► 8. IF user_id NOT in vals:
   │     └─► 9. user_id = current_uid (logged-in user)
   │
   ├─► 10. IF team_id NOT in vals:
   │      └─► 11. team_id = crm.team from user's default team
   │
   ├─► 12. type = vals.get('type', 'lead')
   │      └─► 13. probability = default for type (lead=10, opp=auto)
   │
   ├─► 14. priority = vals.get('priority', '1')
   │
   ├─► 15. tag_ids = default_tags from team_id
   │
   ├─► 16. utm_source_id tracked          [utm.mixin inheritance]
   │      └─► 17. vals['campaign_id'] from source
   │
   ├─► 18. medium_id from channel source  [website/phone/email]
   │      └─► 19. utm_medium set accordingly
   │
   ├─► 20. message_post "Lead Created"   [mail.thread inheritance]
   │      └─► 21. mail.message created, followers notified
   │
   ├─► 22. IF vals.get('partner_name') or email without partner:
   │      └─► 23. create_lead_partner() → res.partner.create({...})
   │            └─► 24. partner_id written back to lead
   │
   ├─► 25. website_first_visited_dt = now()   [if from website]
   │
   ├─► 26. google adwords fields populated     [if utm_source='adwords']
   │
   ├─► 27. lead_scoring_items computed        [PLS: frequency scan]
   │      └─► 28. automated_probability recalculated
   │
   ├─► 29. activity_auto_schedule()            [from team_id assignment]
   │      └─► 30. mail.activity created for assigned user
   │
   └─► 31. IF alias_id set on team:
          └─► 32. alias name recorded on lead for email routing
```

---

## Decision Tree

```
Lead Created
│
├─► FROM website?
│  ├─► YES → utm_medium='organic', medium_id=website channel
│  └─► NO
│
├─► FROM google adwords?
│  ├─► YES → utm_medium='cpc', utm_source_id=adwords, gclid tracked
│  └─► NO
│
├─► FROM email alias?
│  ├─► YES → alias_name routed, email_normalized set, partner auto-created
│  └─► NO
│
├─► FROM phone / lead form?
│  ├─► YES → phone_sanitized set, medium_id=phone, mobile normalized
│  └─► NO
│
└─► ALWAYS:
   └─► Lead logged in chatter, followers notified
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `crm_lead` | Created | name, type='lead', user_id, team_id, partner_id, stage_id, priority |
| `res_partner` | Created (optional) | name, email, phone — linked via partner_id |
| `mail_message` | Created | body='Lead Created', model='crm.lead', res_id=lead_id |
| `mail_followers` | Created | partner_id of creator, lead in followed |
| `mail_activity` | Created (optional) | user_id assigned, activity type from team template |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Missing required `name` | `ValidationError` | ORM `required=True` on name field |
| Duplicate email (strict mode) | `ValidationError` | `_sql_constraints` on email_normalized |
| Invalid stage_id | `ValidationError` | Stage must belong to lead's team |
| Access denied (no CRM rights) | `AccessError` | ACL: `group_crm_manager` or `group_user` required |
| Import with invalid company_id | `ValidationError` | Company must exist in res.company |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Follower added | `mail.followers` | Creator automatically follows the lead |
| Chatter post | `mail.message` | System message "Lead Created" in discussion |
| Partner created | `res.partner` | Anonymous lead → named contact record |
| Activity scheduled | `mail.activity` | First follow-up todo created for assigned user |
| Lead scoring updated | `crm.lead.scoring.frequency` | Frequency table consulted for probability |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `create()` | Current user | `group_crm_user` | Respects record rules — only own team visible |
| `_onchange_partner_id()` | Current user | Read ACL on res.partner | Visible partner fields only |
| `create_lead_partner()` | `sudo()` | Write on res.partner | System context for creation |
| `message_post()` | `mail.thread` | Read ACL on crm.lead | Follower-based notification |
| `activity_auto_schedule()` | Current user | Write on mail.activity | Activity created for assigned user |

**Key principle:** Most Odoo methods run as the **current logged-in user**, not as superuser. Use `sudo()` only when intentionally bypassing ACL.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1-25  ✅ INSIDE transaction  — atomic (all or nothing)
Step 21     ✅ INSIDE transaction — mail.message written in same DB txn
Steps 29-30 ❌ OUTSIDE transaction — mail.activity (ORM write, but rollback-safe)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-25 | ✅ Atomic | Rollback on any error |
| mail.message post | ✅ Within ORM | Rolled back with transaction |
| mail.activity auto-schedule | ✅ Within ORM | Rolled back with transaction |
| Notification email (async) | ❌ Async queue | Retried by `ir.mail.server` cron |

**Rule of thumb:** If it's inside `create()`/`write()` body → inside transaction. If it uses `mail.mail` (outbound email) → outside transaction (queue).

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click Create button | ORM deduplicates — only one record created (browser-level debounce recommended) |
| Re-create lead with same email | New record created — no dedup at ORM level (use `email_normalized` dedup wizard) |
| Import re-run with same data | New records created each time — import is not idempotent by default |
| Duplicate detection | `duplicate_lead_count` computed on create, user shown warning banner |

**Common patterns:**
- **Idempotent:** `create()`, `write()`, `action_*()` state transitions
- **Non-idempotent:** Import runs, sequence increment, auto-partner creation

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `_onchange_partner_id()` | Sync fields from partner | self | Extend with `super()` + additional field writes |
| Step 23 | `create_lead_partner()` | Custom partner creation logic | vals, partner_id | Override to add custom fields |
| Pre-create | `_init()` / hook in `create()` | Pre-creation validation | vals | Extend `create()` with vals |
| Post-create | `_crm_lead_post_create()` | Post-creation side effect | self | Extend via `create()` override |
| Step 29 | `activity_auto_schedule()` | Custom activity types | self | Override to set different activity |
| Validation | `_check_lead_quality()` | Custom lead quality gate | self | Add `@api.constrains` decorator |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def create(self, vals):
    # your code

# CORRECT — extends with super()
@api.model
def create(self, vals):
    res = super().create(vals)
    # your additional code
    return res
```

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `create()` | `unlink()` | `lead.unlink()` | Cascade deletes mail messages, activities, followers |
| Assign to wrong user | `write({'user_id': new_id})` | Reassignment | History preserved in chatter |
| Wrong partner linked | `write({'partner_id': correct_id})` | Partner swap | Old partner unlinked, new one linked |
| Archive lead | `write({'active': False})` | `action_archive()` | Lead hidden but not deleted; recoverable |

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_create_lead()` button | Interactive | Manual |
| Website form | `website_crm_iap_reveal` controller | HTTP POST | Per submission |
| Email gateway | `mail.alias` inbound routing | SMTP/pipe | Per email |
| Import | `base_import.import` wizard | CSV/Excel | Manual batch |
| Automated action | `base.automation` | Rule triggered | Per rule match |
| Onchanges on related models | `_onchange_partner_id()` cascade | Partner change | On demand |

**For AI reasoning:** When asked "what happens if X?", trace all triggers to understand full impact. The email alias path is especially important — it creates a lead entirely without user interaction.

---

## Related

- [Flows/CRM/lead-conversion-to-opportunity-flow](Flows/CRM/lead-conversion-to-opportunity-flow.md) — Lead → Opportunity conversion
- [Flows/CRM/lead-assignment-flow](Flows/CRM/lead-assignment-flow.md) — Auto-assignment of unassigned leads
- [Modules/CRM](Modules/CRM.md) — CRM module reference
- [Modules/Sale](Modules/sale.md) — Sale order from opportunity
- [Modules/mail](Modules/mail.md) — Mail and chatter integration
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Pipeline stage patterns
- [Core/API](Core/API.md) — @api decorator patterns
