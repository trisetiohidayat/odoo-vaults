---
type: flow
title: "[Flow Title]"
primary_model: model.name
trigger: "[User action, button, or method that starts this flow]"
cross_module: true
models_touched:
  - model.a
  - model.b
  - model.c
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/other-flow](flows/other-flow.md)"
related_guides:
  - "[Business/Sale/sales-process-guide](business/sale/sales-process-guide.md)"
source_module: module_name
source_path: ~/odoo/odoo19/odoo/addons/module_name/
created: YYYY-MM-DD
updated: YYYY-MM-DD
version: "1.1"
---

# [Flow Title]

## Overview

[2-3 sentence description of what this flow does and why it matters.]

## Trigger Point

[Describe what initiates this flow — user action, system event, cron job, API call, etc.]

---

## Complete Method Chain

```
1. model.primary.create(vals)
   │
   ├─► 2. model.related.create({...})
   │     └─► 3. field inverse set (Many2one inverse)
   │           └─► 4. @api.depends triggered
   │                 └─► 5. computed field updated
   │
   ├─► 6. IF condition_a:
   │      └─► 7. method_a() called
   │            └─► 8. sub_effect()
   │
   ├─► 9. ELSE (condition_b):
   │      └─► 10. method_b() called
   │            └─► 11. alternative_effect()
   │
   └─► 12. model.cross.create({...})  [cross-module]
          └─► 13. cross_module_effect()
                └─► 14. notification sent
```

---

## Decision Tree

```
Primary Action
│
├─► condition_1?
│  ├─► YES → path_a
│  │        └─► effect_1
│  └─► NO → path_b
│         └─► effect_2
│
├─► condition_2?
│  ├─► YES → path_c
│  │        └─► side_effect_triggered
│  └─► NO → skip
│
└─► ALWAYS:
   └─► base_effect
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `model_primary` | Created | name, state, partner_id |
| `model_related` | Created | primary_id, field_x |
| `res_partner` | Created/Updated | linked record |
| `mail_mail` | Created | notification queued |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Duplicate value | `ValidationError` | `_sql_constraints` unique |
| Missing required | `ValidationError` | ORM `required=True` |
| Invalid state | `UserError` | Business rule validation |
| Access denied | `AccessError` | ACL restriction |
| [Custom scenario] | `ValidationError` | `[constraint_name]` |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Partner subscribed | `mail.followers` | Follower added |
| Quantity reserved | `stock.quant` | Reservation created |
| Activity planned | `mail.activity` | To-do created for user |
| Sequence incremented | `ir.sequence` | Next number consumed |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `create()` | Current user | `group_hr_user` | Respects record rules |
| `_compute_*()` | Current user | Read ACL on related fields | Only visible fields |
| `action_*()` | Current user | `group_hr_manager` | Button-level security |
| Internal `_*()` | `sudo()` | System (no ACL) | For cross-model writes |
| Mail notification | `mail.group` | Public | Follower-based |

**Key principle:** Most Odoo methods run as the **current logged-in user**, not as superuser. Use `sudo()` only when intentionally bypassing ACL.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1-6  ✅ INSIDE transaction  — atomic (all or nothing)
Step 7     ❌ OUTSIDE transaction — via queue_job (retry on failure)
Step 8     ❌ OUTSIDE transaction — via email queue (fire-and-forget)
Step 9     ❌ OUTSIDE transaction — external API (webhook)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-6 | ✅ Atomic | Rollback on any error |
| Mail notification | ❌ Async queue | Retried by `ir.mail.server` cron |
| External API | ❌ Async | Retried via `queue_job` if configured |
| Activity creation | ❌ Within ORM | Rolled back with transaction |

**Rule of thumb:** If it's inside `create()`/`write()` body → inside transaction. If it uses `queue_job`, `mail.mail`, or external HTTP call → outside transaction.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click save button | ORM deduplicates — only one record created |
| Re-save with same values | `write()` re-runs, no new record, no error |
| Re-trigger action on same record | State machine prevents re-execution (no-op or raise) |
| Duplicate API call (race condition) | Unique constraints prevent duplicate records |
| Network timeout + retry | Depends on idempotency key — document if using external API |

**Common patterns:**
- **Idempotent:** `create()`, `write()`, `unlink()`, `action_confirm()` (if state already confirmed)
- **Non-idempotent:** Sequence increment, log creation, financial entry posting

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `_compute_[field]()` | Custom computed value | self | Copy + extend with `super()` |
| Step 5 | `_onchange_[field]()` | Onchange cascade | self | Add field sync |
| Pre-create | `_init()` / hook in `create()` | Pre-creation validation | vals | Extend `create()` with vals |
| Post-create | `_<model>_post_create()` | Post-creation side effect | self | Extend via `create()` override |
| Step 7 | `_<action>_custom()` | Custom business logic | self | Extend via `action_*()` override |
| Validation | `_check_[rule]()` | Custom constraint | self | Add `@api.constrains` |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def action_confirm(self):
    # your code

# CORRECT — extends with super()
def action_confirm(self):
    res = super().action_confirm()
    # your additional code
    return res
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated — use `action_*` methods)

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `create()` | `unlink()` | `record.unlink()` | Cascade deletes related records |
| `action_confirm()` | `action_cancel()` | `record.action_cancel()` | Only if not yet `done` |
| `action_done()` | NOT directly reversible | Manual journal entry | Accounting entries are immutable |
| `action_draft()` | `action_confirm()` again | `record.action_draft()` | Resets to draft state |
| `action_assign()` | `action_unassign()` | `record.action_unassign()` | Unreserves quantities |

**Important:** Some flows are **partially reversible**:
- Picking `done` → can create return (`stock.return.picking`) but original move is not deleted
- Invoice `posted` → can `action_reverse()` to create credit note, but original entry remains
- Production `done` → can unbuild (`mrp.unbuild`), but components are returned to stock

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_*()` button | Interactive | Manual |
| Cron scheduler | `_cron_*()` | Server startup | Daily 00:00 |
| Onchange cascade | `_onchange_*()` | Field change | On demand |
| Webhook / API | `external_endpoint()` | External system | On demand |
| Automated action | `base.automation` | Rule triggered | On rule match |
| Onchanges on related models | Cascade onchange | Related field change | On demand |

**For AI reasoning:** When asked "what happens if X?", trace all triggers to understand full impact.

---

## Related

- [Modules/ModuleName](modules/modulename.md) — Module reference
- [Flows/Sale/sale-to-delivery-flow](flows/sale/sale-to-delivery-flow.md) — Related flow
- [Business/Sale/sales-process-guide](business/sale/sales-process-guide.md) — Step-by-step guide
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — Workflow pattern reference
- [Core/API](core/api.md) — @api decorator patterns
