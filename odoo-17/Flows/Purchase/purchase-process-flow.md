---
tags: [odoo, odoo17, flow, purchase]
---

# Purchase Process Flow

## Overview

Full purchase process from Request for Quotation (RFQ) to receipt and vendor bill.

## Steps

### 1. Request for Quotation (`purchase.order` state: draft)

- Create a new RFQ
- Select vendor (`partner_id`)
- Add order lines (products, quantities, expected prices)
- Set `date_planned` per line (vendor lead time)
- Add vendor reference (`partner_ref`)
- Add notes / terms and conditions

### 2. Send RFQ (state: draft → sent)

- Click "Send to Vendor"
- Email sent to vendor via `mail.thread`
- Vendor responds with a price/availability update

### 3. Confirm Order (state: sent/to_approve → purchase)

- Click "Confirm Order" → `button_confirm()`
- Sets `date_approve` to now
- **On confirmation:**
  - State becomes `purchase` (locked)
  - Creates `stock.picking` (type: IN/Receipt) for each expected location
  - `date_planned` drives expected arrival scheduling

### 4. Receive Goods (state: purchase → done)

- Go to **Inventory** app
- Validate the receipt picking
- **On validation:**
  - `stock.quant` updated at the Input/Stock location
  - `stock.move` records created linking to `purchase.order.line`
  - `qty_received` updated on PO lines

### 5. Create Vendor Bill

- Go to **Accounting** app
- Click "Create Bill" from the PO
- Or navigate to **Purchase → Bills** and link to PO
- **Bill verification:** match the bill date and amounts against the receipt
- Validate → state becomes `posted`
- `qty_to_invoice` / `qty_invoiced` updated on PO lines

## State Transitions

```
draft ──send──▶ sent ──confirm──▶ purchase ──done──▶ done
   ↕                                        ↘ cancel
   └────────────── cancel ──────────────────────────▶
        │
        ▼
   to approve (optional approval step)
```

## Key Hooks & Events

| Trigger | What Happens |
|---------|-------------|
| `button_confirm()` | Locks PO, creates receipt picking, sets `date_approve` |
| Receipt validation | Updates `qty_received` on PO lines |
| Bill creation | Links `account.move.line` to `purchase.order.line` via `purchase_line_id` |
| `button_cancel()` | Cancels PO and any draft pickings |
| `button_draft()` | Resets to draft RFQ |

## Purchase Order → Stock Picking Link

Each `purchase.order.line` is linked to `stock.move` records created at PO confirmation. Receipt validation moves `stock.quant` at the Input or Stock location. The `partner_ref` field on the PO is used to match vendor delivery documents.

## See Also

- [Modules/purchase](odoo-18/Modules/purchase.md) — Full `purchase.order` and `purchase.order.line` reference
- [Modules/stock](odoo-18/Modules/stock.md) — `stock.picking`, `stock.move`, `stock.quant`
- [Modules/account](odoo-18/Modules/account.md) — Vendor bill creation and reconciliation
