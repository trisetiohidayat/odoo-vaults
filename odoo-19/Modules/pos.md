---
type: module
module: pos
tags: [odoo, odoo19, pos, point-of-sale, retail]
updated: 2026-04-07
version: "1.0"
---

# Point of Sale (pos)

## Quick Access

### Flows (Technical — AI & Developer)
- [Flows/POS/pos-session-flow](flows/pos/pos-session-flow.md) — Session lifecycle: create → open → orders → close → accounting entries
- [Flows/POS/pos-order-to-invoice-flow](flows/pos/pos-order-to-invoice-flow.md) — Order to invoice: draft → posted → reconciled

### Guides (Functional — Business)
- [Business/POS/pos-configuration-guide](business/pos/pos-configuration-guide.md) — Configure POS with payment methods, open/close sessions, reconcile cash

### Related Modules
- [Modules/Account](modules/account.md) — Invoicing and accounting entries generated at session close
- [Modules/Stock](modules/stock.md) — Stock picking created at session close (update_stock_at_closing)
- [Modules/res.partner](modules/res.partner.md) — Customer partners for POS orders and invoices
- [Modules/Sale](modules/sale.md) — sale.order integration for delivery-based POS flows

### Patterns
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — State machine design (session states, order states)
- [Patterns/Security Patterns](patterns/security-patterns.md) — POS user groups and access rights

---

## Module Info

**File:** `~/odoo/odoo19/odoo/addons/point_of_sale/`

| Property | Value |
|----------|-------|
| `_name` | `pos.session`, `pos.order`, `pos.payment`, `pos.payment.method`, `pos.config` |
| Category | Point of Sale |
| Summary | Manage Point of Sale sessions, orders, and payments |
| Dependencies | `base`, `account`, `stock` (optional), `sale` (optional) |

---

## Key Models

| Model | `_name` | Purpose |
|-------|---------|---------|
| POS Session | `pos.session` | Container for a work period — groups orders and payments |
| POS Order | `pos.order` | Individual sale transaction at the POS |
| POS Order Line | `pos.order.line` | Product line on an order |
| POS Payment | `pos.payment` | Payment registered against an order |
| POS Payment Method | `pos.payment.method` | Payment method definition (cash, card, pay later) |
| POS Configuration | `pos.config` | POS terminal settings |

---

## Session State Machine

```
opening_control  →  opened  →  closing_control  →  closed
    (create)         (open)       (close btn)       (done)
```

| State | Trigger | Actions Allowed |
|-------|---------|----------------|
| `opening_control` | `pos.session.create()` | Open session (set cash float) |
| `opened` | `action_pos_session_open()` | Process orders, payments, cash box ops |
| `closing_control` | `action_pos_session_closing_control()` | Count cash, verify orders |
| `closed` | `_validate_session()` | No further actions on session |

---

## Order State Machine

```
draft  →  paid  →  done  →  (invoiced via account_move link)
(cancel possible at draft)
```

| State | Trigger | Accounting |
|-------|---------|-----------|
| `draft` | `pos.order.create()` | None |
| `paid` | `action_pos_order_paid()` | Payment registered |
| `done` | Session closes normally | Orders finalized |
| `cancel` | Manual cancel | Payments reversed |

---

## Integration Points

| Module | Interaction | Description |
|--------|-------------|-------------|
| `account` | Creates records | `account.move` on session close; `account.move.line` per payment |
| `account` | Uses journals | Invoice journal, cash journal, bank journal |
| `stock` | Creates records | `stock.picking` + `stock.move` if `update_stock_at_closing` |
| `sale` | Depends on | Delivery orders linked to POS orders |
| `pos_restaurant` | Extends | Restaurant-specific features (floor plans, kitchen printer) |
| `pos_self_order` | Extends | Self-service kiosk ordering |
| `pos_loyalty` | Extends | Loyalty programs and rewards at POS |

---

## Related Documentation

- [Flows/POS/pos-session-flow](flows/pos/pos-session-flow.md) — Full method chain documentation
- [Flows/POS/pos-order-to-invoice-flow](flows/pos/pos-order-to-invoice-flow.md) — Invoice generation flow
- [Business/POS/pos-configuration-guide](business/pos/pos-configuration-guide.md) — Step-by-step setup guide
- [Core/API](core/api.md) — @api decorators used in POS models
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — State machine patterns
- [Modules/pos](modules/pos.md) — This file (module entry point)
