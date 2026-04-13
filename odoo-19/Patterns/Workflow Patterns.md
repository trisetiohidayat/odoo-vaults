---
type: pattern
tags: [odoo, odoo19, workflow, state, state-machine]
created: 2026-04-06
updated: 2026-04-06
version: "1.1"
---

# Workflow Patterns

## Overview

State machine implementation for business processes in Odoo 19. This guide covers the **declarative approach** (Selection field + action methods), which replaced the deprecated XML workflow engine.

**Key principle:** Transitions are controlled by **explicit `action_*()` methods** that validate before writing to the `state` field.

> **📖 Deep Dive:** Untuk method chain lengkap dengan branching, lihat [Flows/TEMPLATE-flow](Flows/TEMPLATE-flow.md).

---

## Quick Reference

| Component | Purpose | Example |
|-----------|---------|---------|
| `state` Selection field | Define valid states | `'draft'`, `'confirmed'`, `'done'` |
| `action_*()` methods | Control transitions | `action_confirm()`, `action_done()` |
| Guard conditions | Prevent invalid transitions | `if rec.state != 'draft': continue` |
| Pre-validation | Check business rules | `if not rec.partner_id: raise` |
| Side effects | Post-transition actions | Email, activity, record creation |

---

## State Field Definition

```python
state = fields.Selection([
    ('draft', 'Draft'),
    ('sent', 'Quotation Sent'),
    ('sale', 'Sales Order'),
    ('done', 'Done'),
    ('cancel', 'Cancelled'),
], string='Status', default='draft', tracking=True)
```

> **Best practice:** Add `tracking=True` to enable mail.thread chatter tracking on state changes.

---

## Basic Action Methods

### Standard Pattern

```python
def action_confirm(self):
    for rec in self:
        if rec.state != 'draft':
            continue
        rec.write({'state': 'confirmed'})
    return True

def action_done(self):
    for rec in self:
        if rec.state != 'confirmed':
            continue
        rec.write({'state': 'done'})
    return True

def action_cancel(self):
    for rec in self:
        rec.write({'state': 'cancel'})
    return True

def action_draft(self):
    for rec in self:
        rec.write({'state': 'draft'})
    return True
```

---

## Workflow with Pre-Validation

Pre-validation ensures business rules are met before state transition:

```python
def action_confirm(self):
    self.ensure_one()

    # Pre-validation
    if not self.partner_id:
        raise UserError('Partner is required before confirming!')

    if not self.line_ids:
        raise UserError('Order must have at least one line!')

    if self.amount_total <= 0:
        raise UserError('Order total must be greater than zero!')

    # Transition
    self.write({'state': 'confirmed'})

    # Side effects (after state change)
    self._send_confirmation_email()

    return True
```

### Validation Flow

```
action_confirm() called
  │
  ├─► ensure_one() — prevents bulk confirm
  │
  ├─► IF not partner_id:
  │      └─► raise UserError("Partner is required!")
  │            └─► Blocked — no state change
  │
  ├─► IF not line_ids:
  │      └─► raise UserError("Lines are required!")
  │            └─► Blocked — no state change
  │
  ├─► write({'state': 'confirmed'}) ✅
  │      └─► @api.constrains triggered
  │      └─► mail.thread notification
  │
  └─► _send_confirmation_email()
        └─► Async — outside transaction
```

---

## Workflow with Branching Logic

Branching handles different scenarios based on record state or conditions:

```python
def action_confirm(self):
    for rec in self:
        # Guard — only draft can be confirmed
        if rec.state != 'draft':
            continue

        # Branch A: Order requires immediate payment
        if rec.require_payment:
            rec.write({'state': 'sent'})
            rec._send_for_payment()
            rec._create_draft_invoice()

        # Branch B: Normal order — send quotation
        else:
            rec.write({'state': 'sent'})
            rec._send_quotation()

        # Common: Schedule follow-up activity
        rec.activity_schedule(
            'mail.mail_activity_data_call',
            user_id=rec.user_id.id,
            note=f'Follow up on quotation {rec.name}'
        )

    return True
```

### Branching Decision Tree

```
action_confirm()
  │
  ├─► Guard: state != 'draft'?
  │      └─► YES → continue (skip to next record)
  │
  ├─► Branch A: require_payment == True?
  │      ├─► YES → state = 'sent'
  │      │        └─► _send_for_payment()
  │      │        └─► _create_draft_invoice()
  │      │
  │      └─► NO → Branch B:
  │               state = 'sent'
  │               └─► _send_quotation()
  │
  └─► ALWAYS → activity_schedule()
```

### Multiple Branching Pattern

```python
def action_done(self):
    for rec in self:
        # Guard conditions
        if rec.state == 'done':
            continue  # Already done — skip
        if rec.state == 'cancel':
            continue  # Cancelled — cannot be done

        # Branch: Based on picking type
        if rec.picking_type_id.code == 'outgoing':
            # Delivery flow
            rec._action_generate_delivery()
            rec.write({'state': 'done'})

        elif rec.picking_type_id.code == 'incoming':
            # Receipt flow
            rec._action_process_receipt()
            rec.write({'state': 'done'})

        else:
            # Internal transfer
            rec.write({'state': 'done'})

        # Always log
        rec.message_post(body=f'Order marked as done by {rec.env.uid}')
```

---

## Workflow with Post-Transition Side Effects

Side effects run **after** the state transition is committed:

```python
def action_confirm(self):
    res = super().action_confirm()

    for rec in self:
        # These run after state is confirmed

        # 1. Create procurement
        rec._create_procurement_group()

        # 2. Send notification
        rec._send_confirmation_email()

        # 3. Schedule activity
        rec.activity_schedule(
            'mail.mail_activity_data_review',
            user_id=rec.user_id.id,
            note=f'Review confirmed order {rec.name}'
        )

        # 4. Create follower subscription
        rec.message_subscribe(partner_ids=[rec.partner_id.id])

    return res
```

### Side Effect Execution Order

```
action_confirm()
  │
  ├─► super().action_confirm()
  │      └─► write({'state': 'confirmed'})
  │            └─► DB COMMIT ✅
  │
  ├─► _create_procurement_group()  [inside loop]
  │      └─► Creates procurement records
  │
  ├─► _send_confirmation_email()  [inside loop]
  │      └─► ❌ OUTSIDE transaction (async queue)
  │
  └─► activity_schedule()  [inside loop]
         └─► ✅ Inside transaction (ORM write)
```

---

## Workflow with mail.activity Integration

Activity scheduling for follow-up tasks:

```python
def action_done(self):
    for rec in self:
        rec.write({'state': 'done'})

        # Schedule follow-up activity
        rec.activity_schedule(
            'mail.mail_activity_data_delivery',
            user_id=rec.user_id.id,
            date_deadline=fields.Date.context_today(rec) + timedelta(days=7),
            note=f'Confirm delivery of order {rec.name}'
        )

    return True

def action_cancel(self):
    for rec in self:
        # Unschedule pending activities
        rec.activity_ids.unlink()

        rec.write({'state': 'cancel'})

        # Log cancellation
        rec.message_post(body='Order cancelled')

    return True
```

---

## State Transition Diagram (Full Workflow)

```
┌─────────┐
│  draft  │ ← Initial state
└────┬────┘
     │ action_confirm()
     ├─► Pre-validation (partner, lines, amount)
     ├─► Branch A: require_payment → _send_for_payment()
     └─► Branch B: normal → _send_quotation()
     ▼
┌─────────┐
│  sent   │ ← Quotation sent / awaiting payment
└────┬────┘
     │ action_confirm() [second call after payment]
     │ action_lock() [manual lock]
     ▼
┌─────────┐
│  sale   │ ← Confirmed sales order
└────┬────┘
     │ action_done() [delivery completed]
     ▼
┌─────────┐
│  done   │ ← Completed (NOT directly reversible)
└─────────┘

Any state can go to:
     │ action_cancel()
     ▼
┌───────────┐
│  cancel   │ ← Cancelled (can reset to draft)
└─────┬─────┘
      │ action_draft()
      ▼
   [draft]
```

---

## Extension Points

| Override | When to Extend | Pattern |
|---------|----------------|---------|
| `action_confirm()` | Add pre-validation or side effects | `super()` then custom |
| `_check_before_confirm()` | Add validation logic | Create hook method |
| `_post_confirm_hook()` | Add post-transition actions | Create hook method |
| `_create_following_records()` | Trigger related record creation | Call in `action_confirm()` |

### Extension Example

```python
# WRONG — replaces entire method
def action_confirm(self):
    self.write({'state': 'confirmed'})
    return True

# CORRECT — extends with super()
class SaleOrderExtended(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        # Run Odoo standard logic first
        res = super().action_confirm()

        # Add custom side effects
        for rec in self:
            if rec.project_id:
                rec._create_project_tasks()
            rec._notify_slack_channel()

        return res
```

---

## Error Scenarios

| Scenario | Error | Prevention |
|---------|-------|-----------|
| Confirm already confirmed record | Silent skip (no error) | Use `ensure_one()` + state check |
| Done record modified | Accounting implications | `picking_ids.filtered(lambda p: p.state != 'done')` check |
| Cancel after done | Not reversible | Guard in `action_cancel()` |
| Concurrent state change | Race condition | Use `ir.sequence` for ordering |
| Missing required field on confirm | `ValidationError` | Pre-validation in action method |

---

## Anti-Patterns (Odoo 19)

| Anti-Pattern | Problem | Correct Alternative |
|-------------|---------|-------------------|
| Using XML workflow | Deprecated in Odoo 12+ | Use `state` field + `action_*()` methods |
| No guard in `action_*()` | Can be called from any state | Check `if rec.state != 'expected': continue` |
| Side effects before `write()` | Inconsistent state if write fails | Put side effects AFTER `write()` |
| Direct `state` field write | No validation | Use `action_*()` method |
| No `ensure_one()` on critical actions | Bulk operations on sensitive records | Add `self.ensure_one()` for critical transitions |

---

## Idempotency in Workflows

State machine actions should be **idempotent** — safe to call multiple times:

```python
def action_confirm(self):
    for rec in self:
        # Guard — already confirmed
        if rec.state != 'draft':
            continue

        rec.write({'state': 'confirmed'})

    return True

def action_done(self):
    for rec in self:
        # Guard — already done (NON-IDEMPOTENT for accounting)
        if rec.state == 'done':
            raise UserError('Order is already done!')

        # Allow re-confirmation from draft
        if rec.state == 'draft':
            rec.write({'state': 'confirmed'})

        rec.write({'state': 'done'})

    return True
```

---

## Decision Tree Template

For documenting complex workflows:

```
START: [Trigger event]
│
├─► Guard: [condition]?
│      ├─► NO → [Skip / Error / Continue]
│      └─► YES → Continue
│
├─► Pre-validation:
│      ├─► [Rule 1]?
│      │      ├─► FAIL → raise [Error]
│      │      └─► PASS → Continue
│      └─► [Rule 2]?
│             ├─► FAIL → raise [Error]
│             └─► PASS → Continue
│
├─► [State transition]
│      └─► write({'state': 'new_state'})
│            └─► @api.constrains triggered
│
├─► Branch: [condition_a]?
│      ├─► YES → [Path A actions]
│      └─► NO → Branch: [condition_b]?
│                   ├─► YES → [Path B actions]
│                   └─► NO → [Default actions]
│
└─► Side effects (ALWAYS):
       ├─► [Effect 1]
       ├─► [Effect 2]
       └─► [Effect 3]

END: [Result / Return value]
```

---

## Related

- [Flows/TEMPLATE-flow](Flows/TEMPLATE-flow.md) — Full flow document template with branching
- [Core/API](Core/API.md) — @api.depends, @api.onchange decorator patterns
- [Core/BaseModel](Core/BaseModel.md) — Model foundation, inheritance
- [Core/Exceptions](Core/Exceptions.md) — UserError, ValidationError, AccessError
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — State-based access control
- [Snippets/method-chain-example](Snippets/method-chain-example.md) — Method chain notation reference
