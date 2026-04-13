# Flows/Cross-Module/sale-stock-account-flow.md

# Sale → Stock → Account Flow — Odoo 15

## Overview

This flow traces how a sales order transforms through delivery and invoicing into accounting entries. It covers the complete cycle from `sale.order` confirmation through `stock.picking` to `account.move` and `account.payment`.

**Source modules**: `sale`, `sale_stock`, `stock`, `account`

---

## Full Flow Diagram

```
┌──────────────┐
│  sale.order  │  (Quotation → Sale Order)
└──────┬───────┘
       │ action_confirm()
       ▼
┌──────────────────────┐     ┌────────────────────┐
│  stock.picking       │     │  account.move      │
│  (Delivery Order)    │     │  (Draft Invoice)   │
└──────┬───────────────┘     └─────────┬──────────┘
       │                               │
       │_action_done()                 │ action_post()
       ▼                               ▼
┌──────────────────────┐     ┌────────────────────┐
│  Stock Valuation     │     │  Posted Invoice     │
│  account.move        │     │  (AR Journal Entry) │
└──────────┬───────────┘     └─────────┬────────────┘
           │                           │
           │                           │ action_register_payment()
           ▼                           ▼
┌──────────────────────┐     ┌────────────────────┐
│  Accounted Inventory │     │  account.payment   │
│  (COGS Entry)        │     │  (Bank/Cash Entry) │
└──────────────────────┘     └─────────┬────────────┘
                                       │
                                       │ reconciliation
                                       ▼
                              ┌────────────────────┐
                              │ Full Reconciliation │
                              │ (AR Cleared)       │
                              └────────────────────┘
```

---

## Step 1: Quotation to Sale Order

```
sale.order (draft)
    │
    └─► action_confirm()
            │
            ├─► procurement_group created
            ├─► _create_delivery_moves()
            ├─► sale.order.line._launch_stock_rule()
            │       └─► stock.rule create stock.picking
            │
            └─► invoice_status = 'to invoice'
```

**Source**: `addons/sale/models/sale_order.py`

### Key Fields

| Field | Model | Description |
|-------|-------|-------------|
| `order_line` | `sale.order.line` | Order lines with products |
| `procurement_group_id` | `procurement.group` | Groups related pickings |
| `invoice_status` | Selection | `no`, `to invoice`, `invoiced`, `upselling` |
| `partner_invoice_id` | `res.partner` | Invoice address |
| `partner_shipping_id` | `res.partner` | Delivery address |

---

## Step 2: Delivery Order Creation

```
procurement.group
    │
    └─► stock.picking (OUT or internal)
            │
            ├─► stock.move (per sale line)
            │       │
            │       └─► product_id, qty, location_id, location_dest_id
            │
            └─► origin = sale.order.name
```

**Source**: `addons/sale_stock/models/stock.py`

### Picking States

```
pending ──► confirmed ──► assigned ──► done
                │                           │
                └─► _action_assign()        └─► _action_done()
                                                      │
                                                      ├─► Valuation: account.move
                                                      ├─► Quant update: stock.quant
                                                      └─► SO lines: qty_delivered = qty
```

---

## Step 3: Stock Valuation Entry

When a delivery is done, Odoo posts inventory valuation entries.

```
stock.picking._action_done()
    │
    └─► stock.move._action_done()
            │
            └─► _account_entry_move()
                    │
                    └─► account.move (stock valuation)
                            │
                            ├── Line: Inventory (credit) — OUT
                            └── Line: Stock Output (debit) — OUT
```

**For Standard Price Product**:

```
Delivery of 10 units @ Rp 10,000

Journal Entry:
┌─────────────────────────────────┬───────┬─────────┐
│ Account                        │ Debit │ Credit  │
├────────────────────────────────┼───────┼─────────┤
│ 5110 - Cost of Goods Sold      │100,000         │
│ 1410 - Finished Goods          │        │100,000 │
└────────────────────────────────┴───────┴─────────┘
```

**Source**: `addons/stock_account/models/stock_move.py`

---

## Step 4: Invoice Creation

```
sale.order
    │
    └─► action_invoice_create()
            │
            ├─► _create_invoices()
            │       └─► account.move (draft, type='out_invoice')
            │               │
            │               ├── invoice_lines from sale_lines
            │               │       └─► with product, qty, price
            │               │
            │               └── tax_lines from taxes
            │
            └─► invoice_ids updated
```

### Invoice Line Mapping

```python
def _create_invoices(self, grouped=False, final=False):
    """Create invoices from sale order"""
    moves = self.env['account.move']

    for order in self:
        # Create move with proper type
        move_vals = order._prepare_invoice()

        # Create invoice lines
        for line in order.order_line:
            if line.display_type:
                continue
            move_vals['line_ids'] += [
                (0, 0, line._prepare_invoice_line())
            ]

        move = moves.create(move_vals)
        moves += move

    return moves
```

### Invoice Line Fields

```python
# sale.order.line._prepare_invoice_line()
invoice_line_vals = {
    'product_id': line.product_id.id,
    'name': line.name,
    'quantity': line.qty_delivered if final else line.product_uom_qty,
    'price_unit': line.price_unit,
    'tax_ids': [(6, 0, line.tax_id.ids)],
    'sale_line_ids': [(4, line.id)],
    'account_id': line.product_id.property_account_income_id.id,
}
```

---

## Step 5: Invoice Posting

```
account.move (draft)
    │
    └─► action_post()
            │
            ├─► _post() — validate
            │       ├─► _recompute_tax_lines()
            │       ├─► _compute_name()
            │       └─► state = 'posted'
            │
            └─► amount_residual tracked
                    └─► await payment
```

**Posted Invoice Journal Entry (Customer Invoice)**:

```
Invoice #INV/2023/0001 — Customer: PT ABC, Total: Rp 11,000,000

┌─────────────────────────────────┬───────┬─────────┐
│ Account                        │ Debit │ Credit  │
├────────────────────────────────┼───────┼─────────┤
│ 1200 - Accounts Receivable     │11,000,000        │
│ 4000 - Sales Revenue           │        │10,000,000│
│ 2200 - Output VAT Payable      │        │ 1,000,000│
└────────────────────────────────┴───────┴─────────┘
```

---

## Step 6: Payment Registration

```
account.move (posted invoice)
    │
    └─► action_register_payment()
            │
            └─► account.payment.register (wizard)
                    │
                    └─► action_create_payments()
                            │
                            └─► account.payment
                                    │
                                    └─► action_post()
                                            │
                                            └─► reconciliation
                                                    │
                                                    └─► account.partial.reconcile
                                                            └─► amount_residual = 0
```

**Payment Journal Entry**:

```
┌─────────────────────────────────┬───────┬─────────┐
│ Account                        │ Debit │ Credit  │
├────────────────────────────────┼───────┼─────────┤
│ 1100 - Bank BCA                │11,000,000        │
│ 1200 - Accounts Receivable     │        │11,000,000│
└────────────────────────────────┴───────┴─────────┘
```

---

## Step 7: Reconciliation

After payment is posted, reconciliation clears the receivable.

```python
# account.partial.reconcile creates
partial_rec = {
    'debit_move_id': payment_line.id,      # Bank line
    'credit_move_id': invoice_receivable.id,  # AR line
    'amount': 11,000,000,
    'max_date': payment.date,
}
```

**Result**:
- Invoice `amount_residual` → 0
- Invoice `payment_state` → `paid`
- Sale order `invoice_status` → `invoiced`

---

## Cross-Module Links

### Sale ↔ Stock

| Link | Field | Model |
|------|-------|-------|
| SO → Picking | `procurement_group_id` | `procurement.group` |
| Picking → SO | `origin` | `stock.picking` |
| Line → Line | `sale_line_id` | `stock.move` |
| Picking → Invoice | `picking_id` | `stock.picking` |

### Sale ↔ Account

| Link | Field | Model |
|------|-------|-------|
| SO → Invoice | `invoice_ids` | `sale.order` |
| Invoice → SO | `id` in `sale_line_ids` | `account.move.line` |
| Invoice → SO | `invoice_partner_bank_id` | `account.move` |

### Stock ↔ Account

| Link | Field | Model |
|------|-------|-------|
| Move → Entry | `stock_move_id` | `stock.move` |
| Valuation Layer | `stock_valuation_layer_ids` | `account.move` |
| Move Line → Move | `move_id` | `account.move.line` |

---

## Tax Flow

### Invoice Tax Line with Tags

```
account.tax (PPN 10%)
    │
    ├─► invoice_repartition_line_ids:
    │       ├─► Base line: tag_ids = [+tax_10_output]
    │       └─► Tax line: tag_ids = [+tax_10_output]
    │
    └─► refund_repartition_line_ids:
            ├─► Base line: tag_ids = [-tax_10_output]
            └─► Tax line: tag_ids = [-tax_10_output]
```

### Tax Tag Assignment Flow

```
Invoice Posted
    │
    └─► Tax lines created
            │
            └─► tax_tag_ids assigned from repartition
                    │
                    └─► account.move.line.tax_tag_ids
                            │
                            └─► Tax Report reads:
                                    SUM(+)tag - SUM(-)tag = net balance
```

---

## Cash Basis Accounting (CABA) Variant

For taxes with `tax_exigibility='on_payment'`:

```
Invoice Posted (on_payment tax)
    │
    └─► Tax line created
            amount_residual = tax_amount (not yet recognized)
            tax_tag_ids = +tax_10_output

Payment Registered
    │
    └─► Partial reconcile
            │
            └─► _create_tax_cash_basis_moves()
                    │
                    └─► CABA Entry:
                        ├─► Tax Receivable (base amount)
                        ├─► Tax Payable (tax amount)
                        └─► Transition Account
```

---

## Related Flows

- [Flows/Account/invoice-creation-flow](invoice-creation-flow.md) — Invoice creation
- [Flows/Account/invoice-post-flow](invoice-post-flow.md) — Invoice posting
- [Flows/Account/payment-flow](payment-flow.md) — Payment registration
- [Modules/Sale](Sale.md) — Sale order model
- [Modules/Stock](Stock.md) — Stock valuation
- [Modules/Account](Account.md) — Account models

---

**Source Modules**:
- `addons/sale/models/sale_order.py`
- `addons/sale_stock/models/stock.py`
- `addons/stock_account/models/stock_move.py`
- `addons/account/models/account_move.py`
- `addons/account/models/account_payment.py`
- `addons/account/models/account_partial_reconcile.py`
