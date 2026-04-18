---
type: snippet
title: "Method Chain Notation Examples"
description: "Copy-paste patterns for documenting Odoo method chains"
usage: Reference template for Flows/ documentation
updated: 2026-04-06
version: "1.1"
created: YYYY-MM-DD
---

# Method Chain Notation — Examples

## Basic Sequential Chain

```
method_a()
  └─► method_b()
        └─► method_c()
```

Simple: A calls B, which calls C. No branching.

---

## Branching: IF/ELSE

```
method_trigger()
  ├─► IF condition:
  │      └─► path_a()
  │            └─► effect_positive()
  │
  └─► ELSE:
         └─► path_b()
               └─► effect_negative()
```

When `condition` is True → `path_a()` runs.
When `condition` is False → `path_b()` runs.

---

## Branching: Multiple Conditions

```
method_trigger()
  ├─► IF state == 'draft':
  │      └─► handle_draft()
  │
  ├─► IF state == 'confirmed':
  │      └─► handle_confirmed()
  │
  └─► IF state == 'done':
         └─► handle_done()
```

Use `├─► IF` (not `├─► ELSE IF`) when each is independently checked.

---

## Cross-Model Trigger

```
hr.employee.create(vals)           [hr module]
  └─► resource.resource.create()   [resource module]
        └─► _inverse_calendar_id()
              └─► calendar synced back to hr.employee
```

Note: `[module_name]` annotation shows which module owns the code.

---

## Nested Side Effects

```
sale.order.action_confirm()
  └─► procurement_group.create()
        └─► stock.picking.create()
              └─► stock.move.create()
                    └─► move_dest_ids linked to origin
```

Nested depth: main action → child record → grandchild record.

---

## Side Effect (No Return Value)

```
sale.order.action_confirm()
  └─► mail.message.create()      [side effect — not chained to result]
        └─► notification sent
  └─► activity planned           [another side effect]
```

Side effects happen in parallel after the main operation, not as a prerequisite chain.

---

## Error/Exception Path

```
method_with_validation()
  ├─► IF not validated_condition:
  │      └─► raise ValidationError("Error message")
  │            └─► [flow stops here — write blocked]
  │
  └─► [normal path continues]
```

When validation fails → error raised → database write is rolled back.

---

## Computed Field Cascade

```
field_x written
  └─► @api.depends('field_x')
        └─► _compute_dependent_field()
              └─► @api.depends triggered
                    └─► _compute_sub_dependent()
                          └─► cascade continues
```

Use for showing how changing one field triggers multiple computed recalculations.

---

## State Machine Transition

```
action_confirm()
  ├─► _check_company()           [pre-validation]
  ├─► _check_product()           [pre-validation]
  ├─► IF not all_products_available:
  │      └─► state = 'waiting'
  │            └─► action_assign() deferred
  │
  └─► IF all_available:
         └─► state = 'assigned'
               └─► _action_assign()
                     └─► reservation created
```

Full state transition with pre-checks and conditional paths.

---

## Cron Job / Scheduled Action

```
ir_cron.auto_action()
  └─► _cron_run_scheduler()
        └─► search([criteria])
              └─► action_called_for_each()
                    └─► batch effects
```

For scheduled actions that iterate over records and call action methods in batch.

---

## Wizard Action Flow

```
wizard.action_apply()
  └─► vals = {
        'field': wizard.value,
        ...
      }
  └─► target_model.create(vals)   [target model affected]
  └─► wizard.unlink()             [wizard cleanup]
        └─► return action           [form closes, redirect]
```

Wizards collect data, apply it to a target model, then self-destruct.

---

## Extension Point Pattern

```
action_confirm()
  ├─► _pre_confirm_validation()  [hook — extend here]
  │     └─► super().action_confirm()
  │           └─► core logic
  │
  └─► _post_confirm_hook()  [hook — extend here]
        └─► super().action_confirm()
              └─► custom side effect
```

Use `super().method()` to extend, never replace.

---

## Security Context Pattern

```
method_called_by_user()
  │
  ├─► Current user context  [user_id = request.uid]
  │     └─► ACL checked: user must have group
  │
  ├─► _internal_helper()  [sudo — bypasses ACL]
  │     └─► System context, no permission check
  │
  └─► mail.message.create()  [follower-based]
        └─► Any follower receives notification
```

**Rule:** `sudo()` is only used for internal cross-model writes where user shouldn't have direct ACL on the related model.

---

## Transaction Boundary Pattern

```
public.action()
  │
  ├─► Steps 1-5  ✅ INSIDE transaction
  │     └─► Atomic — rollback on any error
  │
  └─► self.env['mail.mail'].create()  ❌ OUTSIDE
        └─► Queued via ir.mail.server cron

┌─────────────────────────────────────┐
│ TRANSACTION (atomic)                │
│  1. record.create()                 │
│  2. compute_field updated           │
│  3. related.write()                 │
│  4. constraint checked              │
│  5. DB commit                       │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│ OUTSIDE (async / fire-and-forget)   │
│  6. mail.mail queued               │
│  7. queue_job created              │
│  8. external API webhook           │
└─────────────────────────────────────┘
```

**Key:** If called from within `create()`/`write()`, it's inside. If uses `queue_job` or `mail.mail`, it's outside.

---

## Idempotency Pattern

```
# Idempotent — safe to re-run
def action_confirm(self):
    if self.state == 'confirmed':  # guard
        return
    self.write({'state': 'confirmed'})

# Non-idempotent — NOT safe to re-run
def action_done(self):
    self.ensure_one()
    self.move_id.action_post()  # posted entries are immutable
    # NO guard — once done, cannot be re-done
```

---

## Reverse / Undo Pattern

```
# Confirm → Cancel (reversible)
action_confirm()
  └─► state = 'confirmed'
        └─► action_cancel()
              └─► state = 'cancelled'  ✓ reversible

# Done → NOT reversible (immutable)
action_done()
  └─► state = 'done'
        └─► move.action_post()  # accounting entries posted
              └─► Must create reverse entry, original stays
```

---

## Cron Trigger Pattern

```
_cron_process_pending()
  │
  └─► self.search([('state', '=', 'pending')])
        └─► for each record:
              ├─► action_process()  [in loop]
              └─► record.write({...})

# Cron runs as superuser unless model has _cron_id
# Use `with_context(uid=user_id)` to run as specific user
```

---

## Usage in Flow Documents

When writing a Flow file, combine these patterns:

```markdown
## Complete Method Chain

```
primary_model.action(args)
  ├─► [A] IF condition:
  │      └─► helper_method()      [side effect]
  │            └─► mail.notification
  │
  ├─► [B] related_model.create()  [cross-module]
  │      └─► _inverse_field_set()
  │            └─► @api.depends cascade
  │
  └─► [C] ELSE:
         └─► validation_check()
               └─► raise ValidationError("msg")
                     └─► [blocked]
```
```

## Security Context Example

```
sale.order.action_confirm()
  ├─► Current user context  [requires group_sale_salesman]
  │     └─► ACL checked: button only visible to sales team
  │
  ├─► _action_confirm_lines()  [sudo internally]
  │     └─► procurement_group.create()  [no direct ACL needed]
  │
  └─► message.post()  [follower-based]
        └─► sales team notified
```

## Transaction Boundary Example

```
sale.order.action_confirm()
  ├─► 1-6 ✅ Inside transaction
  │     ├─► state → confirmed
  │     ├─► procurement_group created
  │     ├─► stock.picking created
  │     ├─► stock.move created
  │     └─► message posted
  │           └─► BUT mail.mail is queued, not sent immediately
  │
  └─► mail.mail.send()  ❌ Outside (async via queue)
```

See also: [Flows/TEMPLATE-flow](Flows/TEMPLATE-flow.md) for full flow document structure.
