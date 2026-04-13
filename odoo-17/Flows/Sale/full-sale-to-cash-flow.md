---
tags: [odoo, odoo17, flow, sale, stock, account, integration]
---

# Full Sale-to-Cash Flow — Odoo 17

Complete end-to-end business flow from quotation to cash receipt, covering the sale_stock and stock_account integrations in Odoo 17.

## Flow Diagram

```
Quotation (draft)
    |
    | [user clicks Send]
    v
Quotation (sent) -- mail.mail notification sent to customer
    |
    | [user clicks Confirm / action_confirm]
    v
Sale Order (sale)
    |
    | sale_stock.SaleOrder._action_confirm()
    |   -> order_line._action_launch_stock_rule()
    |       -> procurement.group.run()  [stock.rule evaluated]
    v
Stock Picking OUT (draft)
    |
    | [scheduler or manual Reserve]
    v
Stock Picking OUT (assigned) -- quants reserved
    |
    | [user clicks Validate]
    |   -> picking.button_validate()  [stock_picking.py:L1134]
    |       -> _action_done()          [stock_picking.py:L978]
    |           -> move._action_done()  [stock_move.py:L1909]
    |               -> quant._update_available_quantity()
    |               -> stock.valuation.layer created
    |               -> account.move generated (real_time valuation)
    v
Stock Picking OUT (done)
    |
    | [user clicks "Create Invoice"]
    |   -> order._create_invoices()
    |       -> _prepare_invoice() [sale_order.py:L1181]
    v
Account Move (draft) -- customer invoice
    |
    | [user clicks Confirm]
    |   -> move._post() [account_move.py:post()]
    |       -> _stock_account_prepare_anglo_saxon_out_lines_vals()
    |           [stock_account/account_move.py:L48]
    |           -> DR Expense  CR Stock Output (interim)
    |       -> _stock_account_anglo_saxon_reconcile_valuation()
    v
Account Move (posted)
    |
    | [user clicks Register Payment]
    |   -> account.payment.register wizard
    v
Account Payment (posted)
    |
    | [automatic reconciliation]
    |   -> move_line._reconcile_plan_with_sync()
    v
Fully Reconciled -- payment matched to invoice
```

---

## Module Responsibilities

| Module | Role |
|--------|------|
| `sale` | Sale order lifecycle, state machine, invoice creation |
| `sale_stock` | Bridges sale orders to stock pickings via procurement |
| `stock` | Picking lifecycle, move reservation, quant updates |
| `stock_account` | Anglo-Saxon COGS entries, valuation layers |
| `account` | Invoice posting, payment registration, reconciliation |

---

## Step-by-Step Detail

### Step 1: Quotation Creation

**State:** `draft` -> `sent`

**Trigger:** User clicks "Send Quotation" or `action_quotation_send()`

**Code:** `sale/models/sale_order.py`

**What happens:**
1. `sale.order` state transitions to `sent`
2. Email sent via `mail.mail` to customer
3. Order lines remain editable
4. Validity date is set / checked

---

### Step 2: Order Confirmation

**State:** `sent` -> `sale`

**Trigger:** User clicks "Confirm Sale Order"

**Code chain:**

```
sale_order.action_confirm()         [sale_order.py:L943]
    |
    ├── _can_be_confirmed()         -- must be in draft/sent
    ├── _prepare_confirmation_values()  -- writes state='sale', date_order
    |
    └── _action_confirm()           [sale_order.py:L1005]
            |
            |  sale_stock.SaleOrder._action_confirm() [sale_stock/models/sale_order.py:L154]
            |    calls: self.order_line._action_launch_stock_rule()
            |
            +---> sale_stock.SaleOrderLine._action_launch_stock_rule() [sale_order_line.py:L328]
                    |
                    |  1. Filter: only lines in state='sale', type in ('consu','product')
                    |  2. Compute qty to procure = product_uom_qty - already_procured
                    |  3. _get_procurement_group()
                    |     - uses existing procurement_group_id on sale.order if found
                    |     - else creates new procurement.group
                    |       vals: {sale_id, partner_id, move_type}
                    |  4. _prepare_procurement_values(group_id) -- passes warehouse, route
                    |  5. Procurement(group) object created per line
                    |  6. procurement.group.run(procurements)
                    |     -> evaluates stock.rule (MTO/MTS/manufacture/buy)
                    |     -> creates stock.picking with moves
                    |  7. Confirm any existing draft pickings: p.action_confirm()

            +---> base SaleOrder._action_confirm() [sale_order.py:L1005]
                    - creates analytic account if expense products present
```

**Key outcomes:**
- `stock.picking` (OUT/Delivery) created in `draft` state
- `procurement_group_id` set on both picking and sale order
- One `stock.move` per sale order line inside the picking
- `sale_line_id` set on each stock.move (`sale_stock/models/stock.py:L17`)
- Picking's `sale_id` derived from `group_id.sale_id` (`stock.py:L94`)

**Key code files:**
- `sale/models/sale_order.py:L943-981` -- `action_confirm`
- `sale/models/sale_order.py:L1005-1014` -- `_action_confirm`
- `sale_stock/models/sale_order.py:L154-156` -- override of `_action_confirm`
- `sale_stock/models/sale_order_line.py:L328-378` -- `_action_launch_stock_rule`
- `sale_stock/models/stock.py:L76-79` -- `procurement.group` inherits `sale_id`
- `sale_stock/models/stock.py:L91-106` -- `stock.picking` inherits `sale_id`

---

### Step 3: Stock Reservation

**State:** `draft` -> `confirmed` -> `assigned`

**Trigger:** Automatic (scheduler) or manual "Reserve" button

**Code:** `stock_picking.py:action_assign()` / `stock_move.py:_action_assign()`

**What happens:**
1. `stock.picking.action_assign()` called
2. For each `stock.move`:
   - `move._action_assign()`
   - Reserves quants: `quant._update_reserved_quantity()`
   - If insufficient stock: state becomes `partially_available`
   - If no stock at all: state becomes `waiting`
3. `stock.quant.reserved_qty` updated
4. Available qty = on_hand_qty - reserved_qty

**Key code:** `stock/models/stock_picking.py:action_assign()`

---

### Step 4: Delivery Validation

**State:** `assigned` -> `done`

**Trigger:** User clicks "Validate" button

**Code chain:**

```
picking.button_validate()          [stock/models/stock_picking.py:L1134]
    |
    ├── _pre_action_done_hook()    -- sanity checks
    |
    ├── split into: pickings_to_backorder / pickings_not_to_backorder
    |
    ├── pickings_to_backorder._action_done()
    |       [cancel_backorder=False]
    |
    └── pickings_not_to_backorder._action_done()
            [cancel_backorder=True]

    |
    v
picking._action_done()             [stock_picking.py:L978]
    |
    ├── moves = self.move_ids.filtered(lambda m: m.state not in ('done','cancel'))
    |
    └── todo_moves._action_done(cancel_backorder=...)  [stock_move.py:L1909]
            |
            |  For each move:
            |
            ├── move._action_done()
            |     -> for ml in move_line_ids: ml._action_done()
            |         -> quant._update_available_quantity(product, location, qty)
            |         -> svl = stock.valuation.layer created
            |         -> if real_time valuation:
            |              account.move generated via _account_entry_move()
            |
            └──  After all moves done:
                   -> svl._validate_accounting_entries()
                         [stock_account/models/stock_valuation_layer.py:L78]
                         -> creates account.move for valuation
                         -> reconciles interim accounts

    |
    v
sale_stock.StockPicking._action_done()  [sale_stock/models/stock.py:L108]
    |
    |  Auto-creates sale.order.line for products delivered via
    |  delivery (MTO/dropship) that were not originally on the SO.
    |  Only when: location_dest_id.usage == 'customer'
    |
    └── self.env['sale.order.line'].create(vals)  [L138-139]
```

**On stock_account (real-time valuation):**
```
On delivery done, for each stock.valuation.layer with real_time:

    DR  Cost of Goods Sold (expense from product category)
        CR  Stock Interim (stock_output account from product)

In Anglo-Saxon mode: no permanent entries yet.
The interim account holds the delivered value.
```

**Key code files:**
- `stock/models/stock_picking.py:L978` -- `_action_done`
- `stock/models/stock_picking.py:L1134` -- `button_validate`
- `stock/models/stock_move.py:L1909` -- `move._action_done`
- `sale_stock/models/stock.py:L108-140` -- auto-create SO lines
- `stock_account/models/stock_valuation_layer.py:L78-105` -- SVL accounting

---

### Step 5: Invoice Creation

**Trigger:** "Create Invoice" button or automatic via `sale_make_invoice_advance`

**Code:** `sale_order.py:_create_invoices()` [L1294]

```
order._create_invoices(grouped=False, final=False)
    |
    ├── _prepare_invoice()          [sale_order.py:L1181]
    |     values = {
    |       'move_type': 'out_invoice',
    |       'invoice_origin': self.name,
    |       'partner_id': partner_invoice_id,
    |       'campaign_id', 'medium_id', 'source_id' (UTM),
    |       'transaction_ids': linked payment transactions,
    |       'invoice_line_ids': []
    |     }
    |
    ├── _get_invoiceable_lines(final)
    |     - Skips down-payments already invoiced
    |     - Uses invoice policy (order vs delivery)
    |
    ├── For each invoiceable line:
    |     line._prepare_invoice_line(sequence=N)
    |       - product_id, quantity, price_unit
    |       - account_id from product or product category
    |       - tax_ids from product or fiscal position
    |
    └── account.move.create(invoice_vals_list)
          -> state = 'draft'
```

**Key code:** `sale/models/sale_order.py:L1181-1212` -- `_prepare_invoice`; `L1294-1391` -- `_create_invoices`

---

### Step 6: Invoice Validation (Post)

**State:** `draft` -> `posted`

**Trigger:** User clicks "Confirm" / `action_post()`

**Code:** `account_move.py:_post()`

```
move._post()
    |
    ├── account.move.line.create(
    |     self._stock_account_prepare_anglo_saxon_out_lines_vals()
    |   )  [stock_account/models/account_move.py:L48]
    |     |
    |     |  For each sale invoice line with real_time valuation:
    |     |
    |     |  DR  Expenses (COGS account)      | qty * price_unit
    |     |  CR  Stock Interim (stock_output) | qty * price_unit
    |     |  display_type = 'cogs'
    |     |  cogs_origin_id = line.id
    |     |
    |     |  Anglo-Saxon accounting: COGS booked when invoice
    |     |  is confirmed, not when delivery happens.
    |
    ├── super()._post()  -- validates, locks date check, posts
    |
    └── posted._stock_account_anglo_saxon_reconcile_valuation()
            [stock_account/models/account_move.py:L185]
            |
            |  Reconciles:
            |    - COGS lines from this invoice post
            |    - with stock interim lines from delivery (account.move)
            |  Uses _reconcile_plan() on account.move.line
            |  If fully matched -> full_reconcile record created
            |  If partial       -> partial_reconcile created
```

**The two Anglo-Saxon entries:**

| When | DR | CR |
|------|----|----|
| On delivery done (`_action_done`) | Stock Interim (stock_output) | Stock (asset) |
| On invoice post (`_post`) | Expenses (COGS) | Stock Interim (stock_output) |

**Net effect:** COGS expense recognized at invoice time (matching principle).

**Key code:** `stock_account/models/account_move.py:L40-56` -- `_post` override; `L79-171` -- `_stock_account_prepare_anglo_saxon_out_lines_vals`; `L185-249` -- `_stock_account_anglo_saxon_reconcile_valuation`

---

### Step 7: Payment Registration

**Trigger:** "Register Payment" button on posted invoice

**Code:** `account_payment_register` wizard

```
account.payment.register()
    |
    ├── wizard: journal, amount, date, payment_method
    |
    ├── payment_type = 'inbound'
    ├── partner_type = 'customer'
    ├── destination_account_id = partner's receivable account
    |
    └── payment.action_post()
          -> state = 'posted'
          -> journal entry created
```

---

### Step 8: Reconciliation

**Trigger:** Automatic (same partner, same receivable account) or manual

**Code:** `account_move_line.py:_reconcile_plan_with_sync()`

```
move_line.reconcile()
    |
    ├── _reconcile_plan_with_sync()
    |     - SQL query finds matching lines (same account, opposite sign)
    |     - Creates account.partial.reconcile
    |     - Union-Find algorithm assigns matching number
    |     - If fully matched -> account.full.reconcile
    |
    └── Invoice payment_state -> 'paid'
```

**Key code:** `account/models/account_move_line.py:_reconcile_plan`

---

## Valuation Impact

### Manual Valuation (`property_valuation = 'manual_periodic'`)
No automatic journal entries on delivery. Inventory value tracked only in `stock.valuation.layer` records. User runs manual valuation reports.

### Real-Time Valuation (`property_valuation = 'real_time'`) + Anglo-Saxon

On delivery (`stock.move._action_done()`):
```
DR  Stock Interim (stock_output)    qty * avg_cost
    CR  Stock (asset)               qty * avg_cost
```

On invoice post (`account.move._post()`):
```
DR  Cost of Goods Sold (expense)    qty * price_unit
    CR  Stock Interim (stock_output)  qty * price_unit
```

**Note:** The Anglo-Saxon price unit uses `_stock_account_get_anglo_saxon_price_unit()` which traces back through `stock.valuation.layer` to find the actual delivery cost, not the invoice price.

---

## Key Data Links Between Modules

| Source | Field | Target |
|--------|-------|--------|
| `sale.order` | `procurement_group_id` | `procurement.group` |
| `procurement.group` | `sale_id` | `sale.order` |
| `stock.picking` | `group_id` -> `sale_id` | `sale.order` |
| `stock.move` | `sale_line_id` | `sale.order.line` |
| `stock.move` | `picking_id.sale_id` | `sale.order` |
| `stock.valuation.layer` | `stock_move_id` | `stock.move` |
| `stock.valuation.layer` | `account_move_id` | `account.move` |
| `account.move.line` | `cogs_origin_id` | `account.move.line` (invoice line) |
| `account.move` | `stock_move_id` | `stock.move` |
| `account.move.line` | `stock_valuation_layer_ids` | `stock.valuation.layer` |

---

## State Summary Table

| # | Document | State | Key Method / Trigger |
|---|----------|-------|----------------------|
| 1 | `sale.order` | `draft` | Create quotation |
| 2 | `sale.order` | `sent` | Send quotation |
| 3 | `sale.order` | `sale` | `action_confirm()` -> `_action_launch_stock_rule()` |
| 4 | `stock.picking` | `draft` | Picking created by procurement |
| 5 | `stock.picking` | `confirmed/assigned` | Reservation |
| 6 | `stock.picking` | `done` | `button_validate()` -> `_action_done()` |
| 7 | `stock.valuation.layer` | created | `move._action_done()` |
| 8 | `account.move` | `draft` | `_create_invoices()` |
| 9 | `account.move` | `posted` | `_post()` -> Anglo-Saxon COGS lines |
| 10 | `account.move.line` | reconciled | `_reconcile_plan()` |
| 11 | `account.payment` | `posted` | Payment registered |

---

## Odoo 17 Specific Notes

- `sale_stock` adds `picking_policy` field (`direct` or `one`) to `sale.order` -- controls whether partial deliveries are allowed
- `sale_stock` adds `delivery_status` computed field to `sale.order` -- tracks `pending/started/partial/full`
- `sale_stock` adds `effective_date` to `sale.order` -- records when first delivery was done
- `stock_account` COGS lines use `display_type = 'cogs'` to distinguish from normal invoice lines
- The `cogs_origin_id` on COGS lines links back to the originating invoice line for traceability
- `_action_launch_stock_rule` is the **single entry point** for all procurement triggered from sales order lines
- `sale_stock`'s `StockPicking._action_done` creates new `sale.order.line` records for MTO/dropship deliveries not originally on the SO (L108-139)
- Auto-lock of SO (state -> readonly) triggered when `sale.group_auto_done_setting` is active (L976)

---

## See Also

- [Modules/sale](sale.md) -- sale.order, sale.order.line models
- [Modules/stock](stock.md) -- stock.picking, stock.move, stock.quant
- [Modules/account](account.md) -- account.move, reconciliation
- [Modules/stock_account](stock_account.md) -- stock.valuation.layer, Anglo-Saxon COGS
- [Flows/Stock/delivery-flow](Flows/Stock/delivery-flow.md) -- detailed picking lifecycle
- [Flows/Sale/sales-process-flow](sales-process-flow.md) -- Odoo 17 sales process overview
