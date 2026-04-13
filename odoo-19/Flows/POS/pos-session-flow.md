---
type: flow
title: "POS Session Flow"
primary_model: pos.session
trigger: "User action — POS → Open Session"
cross_module: true
models_touched:
  - pos.session
  - pos.order
  - pos.payment
  - account.bank.statement
  - account.bank.statement.line
  - account.move
  - stock.picking
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/POS/pos-order-to-invoice-flow](odoo-19/Flows/POS/pos-order-to-invoice-flow.md)"
  - "[Flows/Stock/receipt-flow](odoo-17/Flows/Stock/receipt-flow.md)"
related_guides:
  - "[Business/POS/pos-configuration-guide](odoo-19/Business/POS/pos-configuration-guide.md)"
source_module: pos
source_path: ~/odoo/odoo19/odoo/addons/point_of_sale/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# POS Session Flow

## Overview

The POS Session Flow governs the lifecycle of a Point of Sale session — from creation through opening, order processing, payment registration, and final closing with accounting reconciliation. Sessions act as containers that group all orders and payments taken during a work period. The flow spans `pos.session`, `pos.order`, `pos.payment`, `account.bank.statement.line`, and `account.move`, making it a cross-module process touching Point of Sale, Accounting, and Stock.

## Trigger Point

**User action:** Clicking **Open Session** on a POS configuration screen, or calling `pos.session.create(vals)` programmatically. The session may also be opened via the POS frontend `set_opening_control()` endpoint.

---

## Complete Method Chain

```
pos.session.create(vals)
  │
  ├─► [A] pos.config browse → config_id validated
  │     └─► update_stock_at_closing resolved from company setting
  │
  ├─► [B] session.sudo().create(vals)  (if group_pos_user)
  │     └─► record written with state='opening_control'
  │
  └─► [C] session.action_pos_session_open()  [auto-called]
        │
        ├─► IF config_id.cash_control AND NOT rescue:
        │     └─► search last_session for same config
        │           └─► cash_register_balance_start = last_session.cash_register_balance_end_real
        │                 └─► (defaults to 0 if no prior session)
        │
        └─► write({'state': 'opened'})  [sequence not yet assigned]
              └─► session ready for frontend use
```

```
Frontend: pos.order.create_from_ui(order_data)
  │
  ├─► pos.session.browse(session_id)
  │     └─► IF session.state in ('closing_control', 'closed'):
  │           └─► _get_valid_session(order) → find alternative open session
  │                 └─► raise UserError if none found
  │
  ├─► pos.order.create(vals)
  │     └─► pos.order._process_saved_order(draft=False)
  │           └─► pos.order.action_pos_order_paid()
  │                 └─► write({'state': 'paid'})
  │
  └─► pos.payment.create({amount, payment_method_id, session_id})
        └─► pos.payment._check_payment_method_id()
              └─► validates payment method belongs to session config
```

```
Cash Box Open: pos.session.action_cashbox_open()
  │
  └─► pos.session._post_cash_details_message('Opening cash', ...)
        └─► mail.message posted to session chatter
        └─► cash_register_balance_start set by frontend via set_opening_control()
```

```
Session Closing: pos.session.action_pos_session_closing_control()
  │
  ├─► IF draft orders exist:
  │     └─► raise UserError("Cannot close while draft orders remain")
  │
  ├─► IF NOT cash_control:
  │     └─► action_pos_session_close() → _validate_session()
  │
  ├─► IF rescue AND cash_control:
  │     └─► compute total_cash from payments + balance_start
  │           └─► cash_register_balance_end_real = total_cash
  │
  └─► action_pos_session_validate() → action_pos_session_close() → _validate_session()
```

```
_validate_session()
  │
  ├─► cash_real_transaction = sum(statement_line_ids.mapped('amount'))
  │
  ├─► IF update_stock_at_closing:
  │     └─► _create_picking_at_end_of_session()
  │           └─► stock.picking created per order
  │           └─► stock.move created per order line
  │
  ├─► record._create_account_move()  [account.move created]
  │     └─► account.move.line entries per payment method
  │           └─► receivable accounts credited
  │           └─► sales accounts credited
  │           └─► tax accounts credited
  │
  ├─► IF move_id unbalanced:
  │     └─► env.cr.rollback()
  │           └─► _close_session_action(balance) → wizard shown
  │
  ├─► _post_statement_difference(cash_difference_before_statements)
  │     └─► IF amount < 0:
  │           └─► account.bank.statement.line created
  │                 └─► counterpart = cash_journal_id.loss_account_id
  │           └─► IF amount > 0:
  │                 └─► account.bank.statement.line created
  │                       └─► counterpart = cash_journal_id.profit_account_id
  │
  ├─► move_id._post()  [account.move posted]
  │
  ├─► pos.order.search(state='paid').write({'state': 'done'})
  │     └─► uninvoiced orders marked done
  │
  ├─► _reconcile_account_move_lines(data)
  │     └─► receivable lines reconciled across orders
  │
  └─► write({'state': 'closed'})
        └─► picking_ids.move_ids._trigger_scheduler()
              └─► reorder rules evaluated
```

---

## Decision Tree

```
Session Opened (state='opened')
│
├─► [A] Order placed by cashier
│     └─► create_from_ui() called
│           └─► pos.order created in 'paid' state
│                 └─► pos.payment records created
│                       └─► session.order_ids updated
│
├─► [B] Cash box opened / float set
│     └─► set_opening_control(cashbox_value, notes)
│           └─► _set_opening_control_data()
│                 └─► cash_register_balance_start set
│                       └─► difference posted to chatter
│
├─► [C] More orders continue...
│     └─► (repeat A for each order)
│
└─► [D] Session closing triggered
      └─► action_pos_session_closing_control()
            ├─► Draft orders exist?
            │  ├─► YES → raise UserError (BLOCK)
            │  └─► NO → continue
            │
            ├─► Cash control enabled?
            │  ├─► YES → show cash counting wizard
            │  │     └─► cash_register_balance_end_real set
            │  └─► NO → skip directly to close
            │
            └─► state='closing_control'
                  └─► _validate_session()
                        ├─► Stock update at closing?
                        │  ├─► YES → _create_picking_at_end_of_session()
                        │  └─► NO → skip
                        │
                        ├─► Account move created successfully?
                        │  ├─► YES → _post_statement_difference()
                        │  │         └─► account.move posted
                        │  │               └─► orders → 'done'
                        │  │                     └─► reconciled
                        │  └─► NO → rollback → show balancing wizard
                        │
                        └─► state='closed'
                              └─► reorder rules triggered
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `pos_session` | Created → Updated → Closed | name, state, config_id, user_id, cash_register_balance_start/end_real |
| `pos_order` | Created per order | session_id, state, partner_id, amount_total, amount_paid |
| `pos_payment` | Created per payment | pos_order_id, amount, payment_method_id, payment_date |
| `account_bank_statement_line` | Created on close | pos_session_id, journal_id, amount, counterpart_account_id |
| `account_move` | Created on close (or per order if session closed) | journal_id, date, line_ids |
| `account_move_line` | Created per move line | account_id, balance, partner_id, reconcile |
| `stock_picking` | Created if update_stock_at_closing | pos_session_id, state |
| `stock_move` | Created per picking | picking_id, product_id, product_uom_qty |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No config_id on create | `UserError` | "You should assign a Point of Sale to your session" |
| Draft orders at close | `UserError` | "Cannot close POS while draft orders remain" |
| Already closed | `UserError` | "This session is already closed" |
| Unbalanced account move | `UserError` | `_check_balanced` constraint on `account.move` |
| Cash difference without loss/profit account | `UserError` | Cash journal must have loss_account_id and profit_account_id |
| Payment method not in session config | `ValidationError` | `_check_payment_method_id` constraint |
| Payment on done order | `ValidationError` | `_check_amount` — "Cannot edit payment for posted order" |
| Session in rescue from frontend | `UserError` | Cannot close rescue session via frontend (only `close_session_from_ui`) |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Cash balance inherited | `pos.session` | `cash_register_balance_start` carries forward from prior session |
| Order state update | `pos.order` | Paid orders become `done` when session closes normally |
| Stock moves created | `stock.move` | Picking generated at session close if `update_stock_at_closing` |
| Mail message | `mail.message` | Posted to session chatter on cash box open and order edits |
| Reorder rules | `stock.rule` | `_trigger_scheduler()` called on move_ids after close |
| Activity | `mail.activity` | Session creation triggers activity if mail.thread enabled |

---

## Security Context

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `pos.session.create()` | Current user → `sudo()` | `group_pos_user` | User needs POS group to create with sudo |
| `action_pos_session_open()` | Current user | `group_pos_user` | Opening via frontend |
| `action_pos_session_closing_control()` | Current user → `sudo()` | `group_pos_user` | Closes with elevated context |
| `_validate_session()` | `sudo()` if POS user | `group_pos_user` | Full record write in sudo |
| `_create_account_move()` | `with_company()` | Company write access | Account moves created in company context |
| `pos.payment.create()` | Current user | `group_pos_user` | Payment registration |

**Key principle:** Session operations use `sudo()` for POS users to bypass record-level restrictions during the complex close process, but `with_company()` ensures multi-company isolation.

---

## Transaction Boundary

```
pos.session.create(vals)     ✅ INSIDE transaction  — session + initial state
action_pos_session_open()    ✅ INSIDE transaction  — balance_start write
create_from_ui()             ✅ INSIDE transaction  — order + payments
action_pos_order_paid()      ✅ INSIDE transaction  — state write
_validate_session()          ✅ INSIDE transaction  — move, picking, reconciliation
  ├─► _create_account_move()   ✅ INSIDE transaction
  ├─► move_id._post()           ✅ INSIDE transaction
  └─► _reconcile_account_move_lines() ✅ INSIDE transaction
_post_statement_difference() ✅ INSIDE transaction  — statement line
write({'state': 'closed'})   ✅ INSIDE transaction
_post_scheduler()            ❌ OUTSIDE transaction — via cron/queue
mail.message_post()          ❌ OUTSIDE transaction — fire-and-forget
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-8 (open/orders) | ✅ Atomic | Rollback on any error |
| `_create_account_move()` | ✅ Atomic | Rollback + `_close_session_action` wizard shown |
| `move_id._post()` | ✅ Atomic | Rollback if posting fails |
| `mail.message_post()` | ❌ Async | Never blocks session close |
| `_trigger_scheduler()` | ❌ Queue | Retried by stock scheduler cron |

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Double-click Open Session | ORM deduplicates — one session created per click |
| Multiple orders with same UUID | First wins, subsequent rejected (UUID unique constraint) |
| Re-trigger `_validate_session()` on already-closed session | `UserError` raised — "This session is already closed" |
| Session close with no orders | `_create_account_move()` skipped if no non-cancelled orders |
| Payment on already-paid order | `ValidationError` raised via `_check_amount` |

**Session close is NOT idempotent** — once `state='closed'`, `_validate_session()` raises immediately. Any retry must be via a new session.

---

## Extension Points

| Step | Hook Method | Purpose | Override Pattern |
|------|-------------|---------|-----------------|
| Post-create | Override `create()` | Add default values or validation | `super().create(vals_list)` then extend |
| Cash balance init | `_compute_cash_balance()` | Custom starting balance logic | Extend `action_pos_session_open()` |
| Order processing | `_process_order()` | Modify order creation from frontend | Call `super()` then add side effects |
| Payment validation | `_check_payment_method_id()` | Add custom payment rules | Add `@api.constrains` |
| Stock picking | `_create_picking_at_end_of_session()` | Custom picking logic | Extend with `super()` |
| Account move creation | `_create_account_move()` | Add custom account entries | Extend with `super()` |
| Cash difference | `_post_statement_difference()` | Handle rounding or custom accounts | Extend with `super()` |
| Reconciliation | `_reconcile_account_move_lines()` | Custom reconciliation logic | Extend with `super()` |

**Standard override pattern:**
```python
# CORRECT — extends with super()
def _create_account_move(self, balancing_account, ...):
    res = super()._create_account_move(balancing_account, ...)
    # your additional account move entries
    return res
```

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `pos.session.create()` | Close + abandon | `_validate_session()` must run | Cannot simply delete — orders may reference it |
| `state = 'opened'` | Cannot reverse | Session must go through closing flow | Opening is a transient state |
| `state = 'closed'` | NOT reversible | Must create new session | Account moves are immutable |
| `stock.picking` created | Return picking | `stock.return.picking` wizard | Creates reverse moves, original stays |
| `account.move` posted | Reverse entry | `action_reverse()` via credit note | Invoice can be reversed; session move cannot |

**Important:** Once a session is `closed`, the state transition is irreversible. The `account.move` entries generated are permanent. Any corrections must be made via adjusting journal entries.

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `pos.session → Open Session` button | Interactive | Manual per shift |
| Frontend | `set_opening_control(cashbox_value, notes)` | POS UI | Per session |
| Cron / rescue | `_auto_close_abandoned_sessions()` | Server-side | Daily (configurable) |
| Frontend order | `create_from_ui()` | POS UI | Per order |
| Manual close | `action_pos_session_closing_control()` | Back-office | Manual end-of-shift |
| Rescue close | `close_session_from_ui()` | POS UI | Manual recovery |

---

## Related

- [Flows/POS/pos-order-to-invoice-flow](odoo-19/Flows/POS/pos-order-to-invoice-flow.md) — Invoice generation from paid orders
- [Business/POS/pos-configuration-guide](odoo-19/Business/POS/pos-configuration-guide.md) — POS setup and session management
- [Modules/pos](odoo-19/Modules/pos.md) — Full POS module reference
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine design patterns
- [Core/API](odoo-18/Core/API.md) — @api decorator patterns
- [Modules/Account](odoo-18/Modules/account.md) — account.move, account.bank.statement reference
- [Modules/Stock](odoo-18/Modules/stock.md) — stock.picking, stock.move reference
