---
type: flow
title: "Quality Check Flow"
primary_model: quality.check
trigger: "User action — Picking → Quality Check button"
cross_module: true
models_touched:
  - quality.check
  - quality.alert
  - quality.point
  - quality.alert.team
  - quality.point.test_type
  - stock.picking
  - stock.lot
  - stock.location
  - mail.mail
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Stock/picking-action-flow](odoo-19/Flows/Stock/picking-action-flow.md)"
  - "[Flows/Stock/receipt-flow](odoo-17/Flows/Stock/receipt-flow.md)"
related_guides:
  - "[Modules/quality](odoo-18/Modules/quality.md)"
source_module: quality
source_path: ~/odoo/enterprise/suqma-19.0-20250204/enterprise/quality/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Quality Check Flow

## Overview

The Quality Check Flow handles inline quality control during stock picking operations. When a warehouse operator triggers a quality check from a picking, Odoo creates a `quality.check` record linked to the picking, prepopulates product/lot/location from the picking, and presents the relevant test type to the operator. After the check is performed, the flow branches: a passing check advances the picking; a failing check creates a `quality.alert` and can redirect the failed goods to a designated failure location.

## Trigger Point

**User action:** Warehouse operator clicks the **"Quality Check"** button on a `stock.picking` form. This is rendered by the `button_quality_check()` method on the picking model (defined in stock addon, extended by quality).

The button only appears when at least one `quality.point` matches the picking's operation type and product.

---
> **⚡ Note on quality.point matching:** A `quality.point` applies to a picking when its `picking_type_ids` contains the picking's `picking_type_id` AND (its `product_ids` contains the picking line's product OR its `product_category_ids` contains the product's category). If no matching point exists, the button is hidden and no check can be created.

---

## Complete Method Chain

```
stock.picking  [trigger]
│
└─► 1. button_quality_check()    [stock/models/stock_picking.py]
      │
      ├─► 2. quality.check.create({
      │        'picking_id': picking_id,
      │        'product_id': picking_line_product_id,
      │        'point_id':   matched_quality_point_id,
      │        'team_id':    quality_point.team_id,
      │        'company_id': picking.company_id,
      │     })
      │     └─► ir.sequence.next_by_code('quality.check')  [reference assigned]
      │           └─► super().create(vals_list)  [ORM creates record]
      │
      └─► 3. quality.check._compute_test_type_id()  [@api.depends('point_id')]
            └─► 4. quality.check._compute_title()    [@api.depends('point_id')]
            └─► 5. quality.check._compute_note()     [@api.depends('point_id')]
            └─► 6. quality.check._compute_team_id()  [@api.depends('point_id')]
                  └─► 7. quality.check.onchange_picking_id()  [on ui open]
                        ├─► 8. product_id = self.picking_id.move_lines.product_id
                        ├─► 9. lot_id     = self.picking_id.move_lines.lot_id  (if any)
                        └─► 10. location_id = self.picking_id.location_id
                              └─► 11. quality.check.onchange_point_id()
                                    ├─► 12. test_type_id = point_id.test_type_id
                                    ├─► 13. measure_on   = point_id.measure_on
                                    └─► 14. title        = point_id.title

[User performs the physical check]

      └─► 15. quality.check.do_measure(measure_value)
            └─► 16. write({'measure_value': value})  [recorded]

      ├─► 17. PASS path — action_approve() / do_pass()
      │      └─► 18. write({
      │              'quality_state': 'pass',
      │              'user_id':       env.user.id,
      │              'control_date': datetime.now()
      │           })
      │           └─► 19. IF next point exists:
      │                 └─► action_next() → next quality.check created
      │           └─► 20. ELSE:
      │                 └─► picking.write({'quality_state': 'done'})  [stock updated]
      │
      └─► 21. FAIL path — action_fail() / do_fail()
            └─► 22. write({
                     'quality_state': 'fail',
                     'user_id':       env.user.id,
                     'control_date': datetime.now()
                  })
                  └─► 23. quality.alert.create({
                           'team_id':    check.team_id,
                           'user_id':    check.team_id.user_ids[0],
                           'priority':   '2',  # High by default
                           'product_id': check.product_id,
                           'picking_id': check.picking_id,
                           'check_id':   check.id,
                           'company_id': check.company_id,
                        })
                        └─► 24. ir.sequence.next_by_code('quality.alert')  [reference]
                              └─► super().create(vals_list)  [ORM creates alert]
                                  └─► 25. mail.mail.create({
                                           'subject':    alert.name,
                                           'body_html':  alert description,
                                           'recipient_ids': alert.user_ids,
                                        })
                                        └─► 26. mail.notification sent to assigned users
                                              └─► 27. quality.point.update_qty()
                                                    ├─► stock.quant updated (failure location)
                                                    └─► qty_alerted computed on check
```

---

## Decision Tree

```
User clicks "Quality Check" on stock.picking
│
├─► quality.point matching picking_type + product?
│  ├─► NO  → Button hidden (no check created)
│  └─► YES → quality.check created + onchanges fire
│
User records measurement (do_measure)
│
├─► Measured value within tolerance?
│  ├─► YES → do_pass() / action_approve()
│  │        ├─► quality_state = 'pass'
│  │        └─► Next check or picking state updated
│  │
│  └─► NO → do_fail()
│           ├─► quality_state = 'fail'
│           ├─► quality.alert created
│           │    ├─► Email notification to assigned user
│           │    └─► Alert visible in Quality → Alerts
│           └─► Failed qty redirected to failure_location_id (if configured)
│                └─► quality.point.update_qty() → stock.quant updated
│
└─► Additional decision:
   ├─► Continue picking validation?  (operator resumes after alert)
   └─► Block picking until alert resolved?  (configurable in quality.point)
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `quality_check` | Created (primary record) | name, picking_id, product_id, point_id, team_id, quality_state, control_date, user_id |
| `quality_alert` | Created (only on fail) | name, team_id, user_id, product_id, picking_id, check_id, priority, stage_id |
| `stock_picking` | Updated | quality_state updated to 'pass'/'done' |
| `stock_move_line` | May be updated | lot_id synced from check |
| `stock_quant` | Updated (on fail, failure location) | quantity moved to failure_location_id |
| `mail_mail` | Created (on alert creation) | subject, body_html, recipient_ids, state='outgoing' |
| `mail_followers` | Updated | check and alert records subscribed to by assignee |
| `stock_picking.quality_state` | Updated on picking | tracks overall picking quality status |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No quality.point defined for product/operation | Button not visible | No matching `quality.point` found → nothing to create |
| Measuring equipment not calibrated | `UserError` | Custom extension — check `measure_uom_id` against `calibration_date` |
| Qty discrepancy detected (measured != expected) | `UserError` | `qty_alerted` field set; operator must acknowledge difference |
| Quality point test type requires picture — none provided | `ValidationError` | Required field `picture` is blank on save |
| Attempt to re-check an already-passed check | `UserError` | `quality_state` is already 'pass' — no re-entry |
| Alert creation fails (no team members) | `UserError` | `quality.alert.team` has no `user_ids` → `_get_quality_team` raises |
| Attempt to close picking with open failed check | `UserError` | Picking validation blocked if any line has `quality_state = 'fail'` and no alert resolved |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Picking quality_state updated | `stock.picking` | quality_state toggles to reflect check status |
| Alert created on failure | `quality.alert` | Record created, assigned to team member |
| Email sent to alert assignee | `mail.mail` | Notification queued and sent |
| Failed goods redirected | `stock.quant` | Quantity moved to failure_location_id on the point |
| Activity scheduled | `mail.activity` | Activity created on check record for responsible user |
| Follower added | `mail.followers` | Team members subscribed to check and alert |
| Sequence number consumed | `ir.sequence` | Next number for quality.check / quality.alert |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `button_quality_check()` | Current user | `group_stock_user` + `quality.group_quality_user` | Button only visible with quality group |
| `quality.check.create()` | Current user | Write on `stock.picking`, Create on `quality.check` | Respects record rules |
| `_compute_*()` | Current user | Read on `quality.point`, `stock.picking` | Only visible fields computed |
| `do_pass()` / `do_fail()` | Current user | Write on `quality.check` | Operator-level action |
| `quality.alert.create()` | Current user | Create on `quality.alert`, `mail.mail` | Alert created in user's context |
| `mail.mail` notification | `mail.mail` env | `group_quality_user` | Follower-based — no public access |
| `quality.point.update_qty()` | `sudo()` | Write on `stock.quant` | Internal stock write, bypasses ACL |

**Key principle:** Quality checks run as the **current logged-in warehouse operator**, not as superuser. The team_id and responsible user are derived from the quality.point and team configuration, not from the creating user.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1-14   ✅ INSIDE transaction  — create + onchanges (all atomic)
Step 15      ✅ INSIDE transaction  — do_measure / write (atomic)
Steps 17-22  ✅ INSIDE transaction  — do_pass / do_fail (atomic)
Steps 23-24  ✅ INSIDE transaction  — quality.alert.create (atomic, same tx)
Step 25      ❌ OUTSIDE transaction — mail.mail (async queue via ir.mail.server)
Step 26      ❌ OUTSIDE transaction — mail.notification (async via bus)
Step 27      ✅ INSIDE transaction  — update_qty / stock.quant write (atomic)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-14 (create + onchanges) | ✅ Atomic | Rollback on any error — no check record created |
| Steps 15-22 (do_measure, pass/fail) | ✅ Atomic | Rollback — check state unchanged |
| Steps 23-24 (alert creation) | ✅ Atomic (same transaction) | If alert create fails, entire flow rolls back |
| mail.mail notification | ❌ Async queue | Retried by `ir.mail.server` cron — check not blocked |
| mail.activity | ✅ Within ORM | Rolled back with transaction |

**Rule of thumb:** The entire check-create → pass/fail → alert-create chain is atomic. Only email notification is deferred. If you need to block on external API, extend with a queue_job.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Quality Check" button | ORM deduplicates — only one quality.check record created per picking line per check |
| Re-record measure value on same check | `write()` re-runs, no new record, measure_value overwritten |
| Re-trigger pass on already-passed check | `do_pass()` runs again — `write()` re-executes, no error raised |
| Re-trigger fail on already-failed check | `do_fail()` runs again — `write()` re-executes, no new alert created |
| Multiple operators check same line simultaneously | Only first write succeeds (ORM optimistic locking); second gets `UserError` |
| Picking already quality_state='done' | Button hidden — cannot re-trigger |

**Non-idempotent operations:**
- `ir.sequence.next_by_code()` — consumes a sequence number on each create (even if rolled back, the sequence tick is consumed)
- `quality.alert.create()` — creates a new alert each time (unless caught by a duplicate guard)

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Pre-check | `_before_create_check()` | Validate product readiness | vals | Extend `create()` — check calibration |
| Step 2 | `create()` override | Pre-populate custom fields on check | vals_list | Call `super()`, then write extra fields |
| Step 7 | `_onchange_picking_id()` | Custom field sync from picking | self | Add field assignment after `super()` |
| Step 11 | `_onchange_point_id()` | Custom field sync from point | self | Add field assignment after `super()` |
| Step 15 | `do_measure()` | Record custom measurement logic | measure_value | Extend with UOM conversion, tolerance check |
| Step 17 | `do_pass()` | Post-pass side effects | self | `super()` then add logic |
| Step 21 | `do_fail()` | Post-fail side effects | self | `super()` then add logic (alert enhancement) |
| Step 23 | `quality.alert.create()` | Custom alert fields | vals | Extend via `_on_fail_create_alert()` |
| Step 27 | `update_qty()` | Custom failure location logic | self | Extend for multi-location routing |
| Validation | `_check_*()` | Custom constraint | self | Add `@api.constrains` decorator |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def do_pass(self):
    # your code

# CORRECT — extends with super()
def do_pass(self):
    res = super().do_pass()
    # your additional code
    self._update_picking_custom_field()
    return res
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated — use `action_*` methods)
- Overriding `button_quality_check` in stock without calling `super()` (breaks quality integration)

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `quality.check.create()` | `unlink()` | `record.unlink()` | Only if check has no linked alert |
| `do_pass()` | Reset to 'none' | Write `quality_state = 'none'` | Reopens check for re-inspection |
| `do_fail()` | Reset to 'none' | Write `quality_state = 'none'` | Also clears control_date; alert remains open |
| `quality.alert.create()` | `action_cancel()` | `alert.action_cancel()` | Moves alert to canceled stage, does not unlink |
| `picking.quality_state = 'done'` | NOT reversible | Manual correction required | Picking already validated — requires admin override |
| Failed qty redirected to failure location | Return transfer | `stock.return.picking` | Creates return picking to move goods back |

**Important:** `quality.alert` records are **not automatically deleted** when a check is reset from 'fail' to 'none'. The alert must be manually closed or canceled. This prevents alert loss during re-checks.

**Partial reversibility:**
- Check reset from 'fail' → 'none' is allowed (operator re-inspects)
- Alert created on fail is never auto-deleted — manual close required
- Sequence numbers consumed are never reclaimed

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action (primary) | `button_quality_check()` on picking form | Interactive — warehouse operator | Manual per picking |
| Scheduled check | `stock.picking.button_quality_check()` via cron | Automated recheck for returns | Daily / on demand |
| MRP work order | `mrp.workorder.button_quality_check()` | Manufacturing operator | Per work order |
| Inline from lot | `quality.check` created from `stock.lot` view | QC supervisor scanning lot | Per lot |
| Email alias | `quality.alert` created via incoming email alias | Vendors / customers report issues | On email received |
| On product receipt | Trigger via `stock.move.check_quality()` on move done | Inbound receipt check | Per receiving move |
| Onchange cascade | Picking line product change triggers re-check prompt | UI-driven | On demand |

**For AI reasoning:** When asked "what happens if X?", trace all triggers to understand full impact. A picking can trigger multiple checks if multiple `quality.point` records match the same operation type + product combination.

---

## Related

- [Modules/quality](odoo-18/Modules/quality.md) — Module reference (all models, fields, methods)
- [Flows/Stock/picking-action-flow](odoo-19/Flows/Stock/picking-action-flow.md) — Stock picking form action flow
- [Flows/Stock/receipt-flow](odoo-17/Flows/Stock/receipt-flow.md) — Inbound receipt flow
- [Flows/Stock/delivery-flow](odoo-19/Flows/Stock/delivery-flow.md) — Outbound delivery flow
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Workflow pattern reference (state machine)
- [Core/API](odoo-18/Core/API.md) — @api.depends, @api.onchange, @api.constrains decorators
- [Modules/Stock](odoo-18/Modules/stock.md) — Stock module (stock.picking, stock.move)