---
type: flow
title: "Opportunity Win Flow"
primary_model: crm.lead
trigger: "User action — Opportunity → Won → Close"
cross_module: true
models_touched:
  - crm.lead
  - sale.order
  - crm.stage
  - crm.lead.scoring.frequency
  - mail.activity
  - mail.message
  - project.project
audience: ai-reasoning, developer
level: 1
source_module: crm
source_path: ~/odoo/odoo19/odoo/addons/crm/
created: 2026-04-07
version: "1.0"
---

# Opportunity Win Flow

## Overview

Marking an opportunity as won is the culmination of the sales process — it closes the deal, sets probability to 100%, closes all pending activities, updates the Predictive Lead Scoring (PLS) frequency table, optionally confirms linked sale orders, and triggers revenue recognition. The won state is terminal for the pipeline (though recoverable). This flow is triggered either by drag-dropping the kanban card to the "Won" stage column, or by clicking the "Mark Won" button which calls `action_set_won_rainbow()`.

## Trigger Point

Two entry paths:

1. **Drag-drop** — Kanban view: drag opportunity card to "Won" stage column → `write({'stage_id': won_stage.id})`
2. **Button** — Opportunity form → "Mark Won" button → `action_set_won_rainbow()` called directly

---

## Complete Method Chain

```
1. action_set_won_rainbow() / stage change to 'won'
   │
   ├─► 2. _stage_set_won()             [internal stage transition handler]
   │     └─► 3. write({'stage_id': won_stage.id})
   │
   ├─► 4. write({'date_closed': fields.Datetime.now()})
   │
   ├─► 5. IF merge_lead_ids present:
   │     └─► 6. _compute_lead_probability() — probability = 100
   │           └─► 7. write({'active': False}) on each merged lead
   │                 └─► 8. merged leads archived, linked to winner
   │
   ├─► 9. _onchange_stage_id()         [stage change cascade]
   │
   ├─► 10. probability = 100           [write]
   │      └─► 11. automated_probability overridden to 100
   │
   ├─► 12. activity_complete()         [all pending activities closed]
   │      └─► 13. mail.activity records marked 'done'
   │
   ├─► 14. message_post "Opportunity marked as won"
   │      └─► 15. mail.message created, followers notified
   │
   ├─► 16. IF order_ids exist:
   │      └─► 17. _notify_lead_done() — sale order notified
   │            └─► 18. sale.order.action_confirm() if auto-confirm enabled
   │
   ├─► 19. _pls_increment_frequencies()   [PLS: naive bayes update]
   │      └─► 20. crm.lead.scoring.frequency updated per field value
   │            └─► 21. won_count incremented for each field value
   │
   ├─► 22. _notify_lead_done()         [email to sales team]
   │      └─► 23. mail.notification sent to followers
   │
   ├─► 24. recurring_plan computed     [IF recurring revenue fields set]
   │      └─► 25. recurring_revenue_monthly calculated
   │
   ├─► 26. expected_revenue locked      [write — no further changes]
   │      └─► 27. revenue amount frozen at current value
   │
   └─► 28. IF project creation enabled on team:
          └─► 29. project.project.create({...}) from opportunity data
                └─► 30. project_id written back to opportunity
```

---

## Decision Tree

```
Opportunity Won Triggered
│
├─► Drag-drop to Won stage?
│  ├─► YES → write({'stage_id': won_stage.id}) — auto path
│  └─► NO → action_set_won_rainbow() called explicitly
│
├─► Linked sale.order exists?
│  ├─► YES → auto-confirm SO? → sale.order.action_confirm()
│  │       └─► NO → keep SO in current state
│  └─► NO → continue without SO
│
├─► Merge_lead_ids present?
│  ├─► YES → merge targets archived (active=False)
│  └─► NO → no merge
│
├─► Has recurring revenue?
│  ├─► YES → recurring_revenue_monthly computed and locked
│  └─► NO → skip recurring
│
├─► Team has project creation enabled?
│  ├─► YES → project.project created linked to opportunity
│  └─► NO → skip project
│
└─► ALWAYS:
   └─► probability = 100, date_closed = now, PLS frequencies updated
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `crm_lead` | Updated | stage_id=won, probability=100, date_closed, active (merged leads=False) |
| `crm_lead_scoring_frequency` | Updated | won_count incremented per field value |
| `mail_activity` | Updated | state='done', date_done set on all pending |
| `mail_message` | Created | body='Opportunity marked as won' |
| `sale_order` | Confirmed (optional) | state='sale', date_order frozen |
| `project_project` | Created (optional) | name from opportunity, partner_id |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Opportunity already won | `UserError` | Stage already at Won — no-op or re-raise |
| Access denied (read-only user) | `AccessError` | `group_crm_user` write rights required |
| Linked SO in locked state | `UserError` | Sale order locked — cannot auto-confirm |
| No won stage configured | `UserError` | CRM configuration error — no stage with is_won=True |
| Concurrent drag-drop by two users | `UserError` | Record rules / write lock prevents double-win |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Probability locked at 100% | `crm_lead` | Pipeline revenue fully recognized |
| Pending activities closed | `mail_activity` | All open to-dos marked 'done' |
| PLS frequency table updated | `crm_lead_scoring_frequency` | won_count increments — improves future predictions |
| Sale order confirmed | `sale_order` | Revenue recognition begins (if SO linked) |
| Chatter post | `mail_message` | Win event logged, followers notified |
| Project created | `project_project` | If team has create_project=True |
| Merged leads archived | `crm_lead` | active=False on merge target leads |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `action_set_won_rainbow()` | Current user | `group_crm_user` | Write on crm.lead |
| Stage change via kanban | Current user | `group_crm_user` | Record rule must allow stage update |
| `sale.order.action_confirm()` | Current user | `group_sale_user` | Sale order write rights |
| `_pls_increment_frequencies()` | `sudo()` | Write on crm.lead.scoring.frequency | System-level table update |
| `activity_complete()` | Current user | Write on mail.activity | User's own activities |
| `project.project.create()` | `sudo()` | Write on project.project | Team project creation |
| `message_post()` | `mail.thread` | Read ACL on crm.lead | Follower-based notification |

**Key principle:** Most Odoo methods run as the **current logged-in user**, not as superuser. Use `sudo()` only when intentionally bypassing ACL.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1-28  ✅ ALL INSIDE transaction  — atomic (all or nothing)
sale.order.action_confirm() — within same DB transaction
project.project.create() — within same DB transaction
PLS frequency update — within same DB transaction
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-28 | ✅ Atomic | Full rollback on any error |
| SO confirmation | ✅ Within ORM | Rolled back with transaction |
| Project creation | ✅ Within ORM | Rolled back with transaction |
| PLS frequency update | ✅ Within ORM | Rolled back with transaction |
| Follower email notification | ❌ Async queue | Retried by `ir.mail.server` cron |

**Rule of thumb:** If it's inside `create()`/`write()` body → inside transaction. If it uses `mail.mail` (outbound email) → outside transaction (queue).

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click Mark Won button | First call succeeds, second raises `UserError` ("already won") |
| Re-trigger on already-won lead | Stage is already at Won — `action_set_won_rainbow()` is a no-op or raises |
| Kanban drag to Won when already Won | Record rules / stage validation prevents |
| Confirmed SO already confirmed | `action_confirm()` is idempotent (checks state before confirming) |

**Common patterns:**
- **Non-idempotent in expectation:** Win flow is designed to run once; re-running is a no-op
- **Idempotent:** `sale.order.action_confirm()` checks state before writing

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 2 | `_stage_set_won()` | Stage transition logic | self | Override to add pre/post win logic |
| Step 14 | `_notify_lead_done()` | Custom win notification | self | Extend to add more recipients |
| Step 19 | `_pls_increment_frequencies()` | Custom PLS update | self | Override to exclude certain fields |
| Step 28 | Project creation hook | Create linked project | self | Add `@api.model` method for project vals |
| Pre-win validation | `_check_can_be_won()` | Custom win eligibility check | self | Add `@api.constrains` or method override |
| Post-win | `_crm_lead_post_win()` | Post-win side effect | self | Override `action_set_won_rainbow()` |
| Rainbowman message | `_get_rainbowman_message()` | Custom achievement message | self | Override to customize celebration |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def action_set_won_rainbow(self):
    # your code

# CORRECT — extends with super()
def action_set_won_rainbow(self):
    res = super().action_set_won_rainbow()
    # your additional code
    return res
```

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

**NOT directly reversible** — the Won state is designed to be terminal. The official reversal path is:

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Won marked | Reopen via stage change | Drag back from Won stage to earlier stage | Probability resets, date_closed cleared |
| Archived merge targets | Unarchive | `write({'active': True})` on merged leads | Requires admin access |
| Confirmed sale order | Create credit note | `sale.order._invoice_count` reversal | Accounting entry remains |
| Created project | Archive project | `project.project.active=False` | Project history preserved |
| Revenue locked | Override expected_revenue | `write({'expected_revenue': new_value})` | Manual override allowed — no validation |

**Important:** Revenue recognition entries in `account.move` (via `sale_order`) are **not reversible** through this flow — they require a credit note or manual journal entry reversal.

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_set_won_rainbow()` button | Interactive | Manual |
| Kanban drag-drop | `write({'stage_id': won_stage.id})` | Interactive | Per drag event |
| Automated action | `base.automation` rule | Rule triggered | Per rule match |
| API / external | RPC `execute_kw` call | External system | On demand |
| Stage probability rule | Stage `is_won=True` on write | Config-based | Automatic on stage set to won |

**For AI reasoning:** When asked "what happens if X?", trace all triggers to understand full impact. The drag-drop and button paths are equivalent; both ultimately call the same internal logic.

---

## Related

- [Flows/CRM/lead-creation-flow](lead-creation-flow.md) — Lead creation sources
- [Flows/CRM/lead-conversion-to-opportunity-flow](lead-conversion-to-opportunity-flow.md) — Lead → Opportunity conversion
- [Flows/CRM/lead-assignment-flow](lead-assignment-flow.md) — Lead assignment
- [Modules/CRM](CRM.md) — CRM module reference
- [Modules/Sale](Sale.md) — Sale order confirmation and revenue
- [Modules/Account](Account.md) — Revenue recognition and journal entries
- [Patterns/Workflow Patterns](Workflow Patterns.md) — Pipeline stage patterns
- [Core/API](API.md) — @api decorator patterns
