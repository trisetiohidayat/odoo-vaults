---
type: flow
title: "Quotation to Sale Order Flow"
primary_model: sale.order
trigger: "User action — Sale > Quotations > Confirm"
cross_module: true
models_touched:
  - sale.order
  - sale.order.line
  - res.partner
  - stock.picking
  - account.move
  - procurement.group
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Sale/sale-to-delivery-flow](sale-to-delivery-flow.md)"
  - "[Flows/Sale/sale-to-invoice-flow](sale-to-invoice-flow.md)"
related_guides:
  - "[Modules/Sale](Sale.md)"
source_module: sale
source_path: ~/odoo/odoo19/odoo/addons/sale/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Quotation to Sale Order Flow

## Overview

This flow covers the transformation of a sale quotation (state = `quotation`) into a confirmed sale order (state = `sale`). When a user clicks the **Confirm Sale** button on a quotation, Odoo validates the cart, creates procurement groups, generates delivery pickings (or defers them based on picking policy), optionally creates a draft invoice based on the order's invoicing policy, and posts follow-up activities. The flow is transactional — if any step fails, the entire operation rolls back.

## Trigger Point

**User action:** `sale.order` in `quotation` state → **Confirm** button clicked, which calls `action_confirm()`.

Alternative triggers include:
- **Portal/e-commerce:** Customer accepts a quotation via the customer portal (`sale.portal` controller).
- **Cron scheduler:** `sale.order` with `auto_confirm` flag set via `base.automation` rule.
- **Web service / API:** External system POSTs to Odoo's sale order confirmation endpoint.

---

## Complete Method Chain

```
1. sale.order.action_confirm()
   │
   ├─► 2. _action_confirm()   [internal wrapper]
   │     └─► 3. _ensure_cart_is_valid()
   │           ├─► 4. _cart_update() called for each line
   │           │     ├─► 5. sale.order.line write({'state': 'sale'})
   │           │     └─► 6. product_uom_qty verified / updated
   │           │
   │           └─► 7. IF any line has insufficient stock:
   │                  └─► warning raised to user (non-blocking in Odoo 19)
   │
   ├─► 8. procurement_group_id created
   │     └─► procurement.group.create({'name': order.name, ...})
   │
   ├─► 9. IF picking_policy == 'direct':
   │      └─► 10. procurement_group.run() → stock.picking.create() per warehouse
   │            └─► 11. stock.picking.action_confirm()
   │                  └─► 12. stock.move created for each sale.order.line
   │
   │    IF picking_policy == 'one':
   │      └─► 13. Single stock.picking created for all lines
   │
   │    IF picking_policy == 'fifo' / 'manual':
   │      └─► 14. Picking deferred — created later by procurement scheduler
   │
   ├─► 15. IF order_policy == 'prepaid':
   │      └─► 16. _create_invoices(final=False)
   │            └─► 17. account.move (draft invoice) created
   │                  └─► 18. account.move.line records created per line
   │
   │    IF order_policy == 'manual':
   │      └─► 19. No invoice created automatically
   │
   │    IF order_policy == 'postpaid':
   │      └─► 20. No invoice created at this stage
   │            └─► Invoice deferred until stock.picking.action_done()
   │
   ├─► 21. action_wait()   [sets state = 'sale']
   │     └─► 22. sale.order write({'state': 'sale'})
   │
   ├─► 23. message_post("Order Confirmed", subtype_xmlid="sale.mt_order_confirmed")
   │     └─► 24. mail.followers notified
   │
   ├─► 25. activity_schedule(
          'sale.mail_act_sale_order_confirm',
          user_id=order.user_id,
          date_deadline=today
        )
        └─► mail.activity record created for follow-up

   ┌──────────────────────────────────────────────────────────────┐
   │ PARALLEL (outside write() body — scheduled/called directly) │
   └──────────────────────────────────────────────────────────────┘
        └─► _send_order_confirmation_mail()
              └─► mail.mail queued (ir.mail_server)
```

---

## Decision Tree

```
sale.order.action_confirm()
│
├─► _ensure_cart_is_valid() — ALL must pass:
│  ├─► Product exists and active? → YES continue / NO → ValidationError
│  ├─► Partner not blocked? → YES continue / NO → UserError
│  └─► At least one line with qty > 0? → YES continue / NO → UserError
│
├─► picking_policy check:
│  ├─► 'direct'  → create pickings immediately per procurement
│  ├─► 'one'     → create one combined picking for all lines
│  └─► 'manual'  → no picking created now (manual trigger later)
│
├─► order_policy check (invoice_policy on sale.order):
│  ├─► 'prepaid'  → _create_invoices() draft invoice NOW (before delivery)
│  ├─► 'manual'   → no automatic invoice (user creates manually)
│  └─► 'postpaid' → invoice deferred until delivery confirmed
│
└─► ALWAYS:
   └─► state → 'sale', activity scheduled, message posted
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `sale_order` | Updated | `state = 'sale'`, `date_order` (updated), `validity_date` consumed |
| `sale_order_line` | Updated | `state = 'sale'` on each line, `procurement_group_id` set |
| `procurement_group` | Created | `name = order.name`, `partner_id`, `move_type` |
| `stock_picking` | Created (if `picking_policy` in `direct`/`one`) | `group_id` linked, `origin = order.name`, `state = 'confirmed'` or `'assigned'` |
| `account_move` | Created (if `order_policy == 'prepaid'`) | `move_type = 'out_invoice'`, `state = 'draft'`, `invoice_origin = order.name` |
| `mail_activity` | Created | `res_id = order.id`, `activity_type_id`, `user_id` |
| `mail_followers` | Updated | Partner/agent subscribed as followers |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Partner is blocked/blacklisted | `UserError: "You cannot confirm a sale order for a blocked partner"` | `_check_partner_blocked()` in `action_confirm()` |
| Order has no lines | `UserError: "You cannot confirm an empty sale order"` | `_ensure_cart_is_valid()` guard |
| Product has no seller (vendor) | `UserError` | `_validate_availability()` checks vendor on product |
| No warehouse configured | `UserError: "No warehouse specified"` | `action_confirm()` calls `_get_warehouse_id()` |
| Insufficient stock with `validate_at_confirm=True` | `UserError` | Stock validation via `stock.picking.action_confirm()` |
| Access rights — user cannot confirm | `AccessError` | Button security via `groups` XML attribute on `action_confirm` |
| Attempt to re-confirm an already confirmed order | No-op (idempotent) | `action_confirm()` checks `if self.state != 'quotation': return False` |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Procurement group created | `procurement.group` | Groups related moves and pickings under one umbrella |
| Delivery pickings created | `stock.picking` | One picking per warehouse (or one combined) for route assignment |
| Stock moves reserved (if `action_assign` called) | `stock.quant` | `product_uom_qty` reserved on quants at source location |
| Draft invoice created | `account.move` | `out_invoice` record in draft state, lines per order line |
| Follow-up activity scheduled | `mail.activity` | To-do created for `sale_user` with deadline = today |
| Followers notified | `mail.followers` | Customer + sales rep receive mail notification |
| Order sequence consumed | `ir.sequence` | `sale.order` sequence next number allocated |
| Sage/EDI push (if configured) | `sale.order` | External system notified via webhook or EDI connector |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `action_confirm()` button | Current user | `group_sale_salesman` or higher | Button-level `groups` check |
| `_action_confirm()` | Current user (sudo'd internally) | Write on `sale.order` | ORM `sudo()` used for cross-model writes |
| `_ensure_cart_is_valid()` | Current user | Read on `product.product`, `res.partner` | Respects record rules |
| `procurement.group.create()` | `sudo()` (system) | System — no ACL | Internal framework call |
| `stock.picking.create()` | `sudo()` (system) | System — no ACL | Triggered by procurement |
| `_create_invoices()` | Current user | `group_account_invoice` | Creates in draft — may need billing rights |
| `activity_schedule()` | `sudo()` (mail) | `group_sale_salesman` | Activity created as system |
| `message_post()` | Current user | Read/Write on `mail.thread` | Follower notification |
| Mail notification sent | `mail.mail` | Public | Queued via `ir.mail_server` |

**Key principle:** Most Odoo methods run as the **current logged-in user**, not as superuser. The `action_confirm()` method internally uses `sudo()` for framework-level object creation (pickings, groups). Custom overrides should be careful not to break this assumption.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1–7    ✅ INSIDE transaction  — atomic (all or nothing)
Steps 8–14   ✅ INSIDE transaction  — procurement group + pickings created
Steps 15–20  ✅ INSIDE transaction  — draft invoice created (or skipped)
Steps 21–25  ✅ INSIDE transaction  — state write, message, activity
Step 26      ❌ OUTSIDE transaction — mail.mail queued via ir.mail_server
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1–25 | ✅ Atomic | Rollback on any error — no partial state |
| `message_post()` | ✅ Within ORM | Rolled back with transaction |
| `activity_schedule()` | ✅ Within ORM | Rolled back with transaction |
| `_send_order_confirmation_mail()` | ❌ Async queue | Mail may send even if transaction rolls back (rare edge case) |
| External EDI / webhook | ❌ Outside transaction | Attempted after commit; retried by `queue_job` if configured |

**Rule of thumb:** If it's inside `create()`/`write()` body or triggered directly in the same call stack — inside transaction. If it uses `queue_job`, `mail.mail` with `send_later`, or external HTTP call — outside transaction.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click Confirm button | ORM deduplicates — `action_confirm()` guard checks `if state != 'quotation'` — second call is a no-op |
| Re-trigger action on same record | `action_confirm()` returns early: `if self.state != 'quotation': return True` — no new pickings or invoices created |
| Duplicate procurement scheduler run | Procurement checks `if picking.state in ('done', 'cancel'): skip` — no duplicate pickings |
| Concurrent confirmation from two sessions | Database `state` field is exclusive — first write wins, second raises `UserError` or silently succeeds (depends on timing) |
| Network timeout + retry | Idempotent — second `action_confirm()` is a no-op if already confirmed |

**Common patterns:**
- **Idempotent:** `action_confirm()` (state guard), `write()` with same values (no-op), `action_wait()` (no-op if already sale)
- **Non-idempotent:** `procurement.group.create()` (new record each time), `ir.sequence` (number consumed), `stock.picking.action_done()` (quant state changes)

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `_ensure_cart_is_valid()` | Pre-confirmation validation | `self` | Add custom validation before calling `super()` |
| Step 4 | `_cart_update()` | Modify line state before confirmation | `self` | Extend to sync additional fields |
| Step 8 | `_get_procurement_group()` | Custom group creation logic | `self` | Override to use custom grouping key |
| Step 10–14 | `_create_picking()` (via procurement) | Control picking creation | `self` | Override procurement rule's `run()` method |
| Step 16 | `_create_invoices()` | Control invoice creation | `self, final=False` | Hook to add invoice line descriptions |
| Pre-state change | `_action_confirm()` | Pre-confirmation hook | `self, confirm=False` | Add side effects before state changes |
| Post-confirmation | `_after_confirm()` | Post-confirmation side effects | `self` | Extend with `super()` + your code |
| Invoice creation | `_invoice_paid_hook()` | Custom invoice behavior | `self, invoice` | Called in `_create_invoices()` |

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

**Odoo 19 specific hooks:**
- `sale.order` has `_action_confirm()` as the internal implementation
- Procurement is handled by `procurement.group.run()` — override `stock.rule` or `procurement.rule` for custom routing
- Invoice creation uses `_create_invoices()` which can be overridden per-order

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated — use `action_*` methods)
- Overriding `action_confirm` without calling `super()` — breaks procurement and picking flow

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `action_confirm()` | `action_cancel()` | `sale.order.action_cancel()` | Only if no picking is `done`; cancels pickings too |
| `action_cancel()` | `action_draft()` | `sale.order.action_draft()` | Resets to `quotation` state; pickings must be `cancel` or `draft` |
| `stock.picking` created | `action_cancel()` on picking | `stock.picking.action_cancel()` | Unreserves quants; only if not `done` |
| `account.move` draft invoice | `unlink()` | `account.move.unlink()` | Only in `draft` state; no posted invoices |
| Posted invoice (if paid) | `action_reverse()` | Creates credit note | Original invoice remains; credit note is new record |

**Important:** This flow is **partially reversible**:
- Picking `done` → cannot directly cancel; must create a **return picking** via `stock.return.picking` wizard
- Draft invoice → can be deleted (unlinked)
- Posted invoice → can be reversed (credit note), original is immutable
- Confirmed order → can cancel, but if procurement ran, stock moves may have been reserved/acted upon
- `action_draft()` after cancellation may not restore all pickings — some may remain cancelled

**Caveats:**
- Cancelling a sale order does **not** automatically cancel a paid invoice — invoice must be reversed manually
- If a picking is in `done` state, you cannot cancel it — must use the **Return** flow
- Unconfirming (`action_draft`) after `action_cancel` will re-open pickings that are in `draft` or `cancel` state only

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_confirm()` button | Interactive (UI) | Manual |
| Portal / e-commerce | `sale.portal()` controller `accept()` | Customer portal | On customer acceptance |
| Cron scheduler | `sale.order._cron_auto_confirm()` | Server module | Configurable (e.g., daily for expiring quotes) |
| Automated action | `base.automation` rule | Server action on `state = 'sent'` | On rule match |
| Webhook / API | External system POST to `/api/sale.order/<id>/action_confirm` | REST API | On demand |
| Upsell from SO | `sale.order.line._compute_amount()` trigger | Automatic | On upsell creation |

**For AI reasoning:** When asked "what happens if X?", trace all triggers to understand full impact. The same `action_confirm()` flow is used regardless of trigger — the procurement and picking logic is identical.

---

## Related

- [Modules/Sale](Sale.md) — Sale module reference
- [Flows/Sale/sale-to-delivery-flow](sale-to-delivery-flow.md) — Delivery flow from confirmed sale order
- [Flows/Sale/sale-to-invoice-flow](sale-to-invoice-flow.md) — Invoice creation from sale order
- [Modules/Stock](Stock.md) — Stock/picking module reference
- [Modules/Account](Account.md) — Account/invoice module reference
- [Patterns/Workflow Patterns](Workflow Patterns.md) — Workflow pattern reference
- [Core/API](API.md) — @api decorator patterns
