---
tags: [odoo, odoo17, flow, sale]
---

# Sales Process Flow

## Overview

Full sales process from quotation to delivery and invoicing.

## Steps

### 1. Quotation (`sale.order` state: draft)

- Create a new quotation
- Add order lines (products, quantities, prices)
- Set delivery date (`commitment_date`)
- Set payment/payment terms
- Optionally request online signature or prepayment

### 2. Send Quotation (state: draft → sent)

- Click "Send Quotation" or "action_quotation_send()`
- Email sent to customer via `mail.thread`
- Validity date can be set to auto-expire the quote

### 3. Confirm Order (state: sent → sale)

- Customer accepts (online signature or manual confirmation)
- Click "Confirm" → `action_confirm()`
- **On confirmation:**
  - State locks (`locked = True`) — order can no longer be edited directly
  - Creates `stock.picking` (type: OUT/Delivery) for each delivery warehouse
  - `date_order` is frozen as the confirmation date
  - Inventory reservation may occur (depends on warehouse config)

### 4. Delivery (state: sale → done)

- Go to **Inventory** app
- Validate the delivery picking
- **On validation:**
  - `stock.quant` updated at the customer location
  - `stock.move` records created linking to `sale.order.line`
  - `qty_delivered` updated on order lines

### 5. Invoice (optional, runs in parallel)

- Click "Create Invoice" on the confirmed order
- Options: "Invoice normal" / "Down payment (percentage)" / "Down payment (fixed)"
- Creates `account.move` (type: out_invoice) linked to order lines
- Validate the invoice → state becomes `posted`
- `qty_to_invoice` / `qty_invoiced` updated on order lines

## State Transitions

```
draft ──send──▶ sent ──confirm──▶ sale ──delivery done──▶ done
   ↕                                        ↘ cancel
   └────────────── cancel ────────────────────────────▶
```

## Key Hooks & Events

| Trigger | What Happens |
|---------|-------------|
| `action_confirm()` | Locks order, creates pickings |
| Picking validation | Updates `qty_delivered` on lines |
| Invoice creation | Updates `qty_to_invoice` / `qty_invoiced` |
| `action_cancel()` | Cancels order and any draft pickings |
| `action_draft()` | Resets to draft (only from cancel) |

## Sale Order → Stock Picking Link

Each `sale.order.line` is linked to one or more `stock.move` records created at confirmation. Delivery validation moves `stock.quant` at the customer/stock location.

## See Also

- [Modules/sale](modules/sale.md) — Full `sale.order` and `sale.order.line` reference
- [Modules/stock](modules/stock.md) — `stock.picking`, `stock.move`, `stock.quant`
- [Modules/account](modules/account.md) — Customer invoice creation
