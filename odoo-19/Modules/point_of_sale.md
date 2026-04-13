---
type: module
module: point_of_sale
tags: [odoo, odoo19, pos, point-of-sale, retail, session, order]
created: 2026-04-11
l: 4
---

# Point of Sale Module (`point_of_sale`)

## L1 — Module Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `point_of_sale` |
| **Category** | Sales |
| **Version** | 1.0 (Odoo 19) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Summary** | Full-featured POS system with session management, multi-payment, offline-capable order entry, kitchen printing, and accounting integration |

**Module Path:** `~/odoo/odoo19/odoo/addons/point_of_sale/`

### Dependencies

```
resource, stock_account, barcodes, html_editor, digest,
phone_validation, partner_autocomplete, iot_base,
google_address_autocomplete
```

### Core Architecture

The POS module is architected as a **two-tier system**:

1. **Frontend (JavaScript/SQLite)** — The POS UI runs in the browser (or Electron wrapper). It loads a snapshot of products, categories, payment methods, and printers via `pos.load.mixin` `_load_pos_data_*` methods. Orders are created locally and synced via UUID to the backend.
2. **Backend (Python/PostgreSQL)** — Handles session management, accounting entries, invoice generation, stock picking creation, and reconciliation. Works both online and queues orders for later sync when offline.

### Key Design Patterns

- **`pos.load.mixin`** — All models loaded into the POS frontend inherit this mixin. It defines `_load_pos_data_domain()` and `_load_pos_data_fields()` which the JS `models.js` loader uses to build the local SQLite database snapshot. This is the core pattern enabling **offline operation**.
- **`pos.bus.mixin`** — Enables real-time bus notifications so multiple POS terminals (and the backend) receive order state change events (e.g., `ACTION_NEW`, `ACTION_UPDATE_ORDER_STATE`, `ACTION_SEND_TO_KITCHEN`).
- **UUID-based sync** — Every `pos.order` and `pos.payment` carries a `uuid` field. The frontend creates records with locally-generated UUIDs; the backend upserts on `sync_from_ui()` matching `uuid`.
- **Session-state machine** — POS sessions move through `opening_control → opened → closing_control → closed`. Only `closed` sessions produce accounting entries.

---

## L2 — Models, Fields, Methods

### 2.1 `pos.session` — POS Session

**File:** `models/pos_session.py`
**Lines:** ~1700
**Inherits:** `mail.thread`, `mail.activity.mixin`, `pos.bus.mixin`, `pos.load.mixin`

The session is the **fundamental unit of POS accounting**. All orders belong to exactly one session. When a session is closed/validated, its accumulated amounts are posted to the accounting ledger in a single `account.move`.

#### State Machine (`POS_SESSION_STATE`)

```
┌──────────────────┐    open_ui()     ┌───────────┐    try_close()    ┌───────────────────┐
│ opening_control  │ ─────────────────│  opened   │ ──────────────────│ closing_control   │
│  (not started)   │                  │(in prog.) │                   │  (awaiting cash   │
└──────────────────┘                  └───────────┘                   │   reconciliation) │
                                                                          └───────────────────┘
                                                                                  │
                                                                          _validate_session()
                                                                                  │
                                                                                  ▼
                                                                            ┌───────────┐
                                                                            │  closed   │
                                                                            │ (posted)  │
                                                                            └───────────┘
```

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | Integer | Yes | auto | Primary key |
| `name` | Char | Yes | `/` | Session identifier (uses sequence, format: `Session #{sequence_number}`) |
| `config_id` | Many2one `pos.config` | Yes | — | POS terminal this session belongs to |
| `user_id` | Many2one `res.users` | Yes | — | User who opened the session |
| `state` | Selection | Yes | `opening_control` | Session state: `opening_control`, `opened`, `closing_control`, `closed` |
| `start_at` | Datetime | No | — | When session was opened |
| `stop_at` | Datetime | No | — | When session was closed |
| `sequence_number` | Integer | Yes | 1 | Sequence number for order naming |
| `login_number` | Integer | Yes | 0 | Number of times user has logged in |
| `cash_control` | Boolean | Yes | False | If True, require cash reconciliation at close |
| `cash_register_balance_start` | Monetary | No | 0 | Opening cash balance |
| `cash_register_balance_end_real` | Monetary | No | — | Actual counted closing balance |
| `cash_register_balance_end` | Monetary | No | 0 | Expected closing balance (computed) |
| `move_id` | Many2one `account.move` | No | — | Journal entry created at session close |
| `payment_method_ids` | Many2many `pos.payment.method` | No | — | Payment methods available in this session |
| `order_ids` | One2many `pos.order` | No | — | Orders belonging to this session |
| `cash_register_ids` | One2many `account.bank.statement` | No | — | Cash statements for each cash payment method |
| `statement_line_ids` | One2many `account.bank.statement.line` | No | — | Manual cash entries/withdrawals |
| `忍` | Boolean | No | — | Unused field (Japanese character, appears in source) |
| `amount_total` | Monetary | No | 0 | Computed total amount (company currency) |
| `amount_paid` | Monetary | No | 0 | Amount actually paid |
| `amount_tax` | Monetary | No | 0 | Tax amount |
| `amount_return` | Monetary | No | 0 | Change given |
| `amount_balance` | Monetary | No | 0 | Balance (paid - return) |
| `all_order_line_ids` | Many2many `pos.order.line` | No | — | All order lines in session (computed) |
| `all_payment_ids` | Many2many `pos.payment` | No | — | All payments in session (computed) |

#### Key Methods

**`open_ui()`** — Transitions session from `opening_control` to `opened`. Sets `start_at`. Called by POS interface when the terminal starts.

**`login()`** — Increments `login_number`. Called when a user logs in to an already-open session.

**`action_pos_session_open()`** — Server action that calls `open_ui()` and returns wizard action.

**`action_pos_session_closing_control()`** — Moves to `closing_control`. Shows cash control wizard if enabled.

**`action_pos_session_close()`** — Wrapper that calls `try_close()`.

**`try_close()`** — Main close logic:
1. Check if any orders are unpaid (`state != 'paid' AND state != 'done'`) — raises `UserError` if so.
2. Call `_update_amounts()` to recalculate totals from all orders/payments.
3. If `cash_control` enabled, validate `cash_register_balance_end_real` against expected balance.
4. Call `_validate_session()` to post accounting entries.

**`_validate_session()`** — The heavy lifter at session close:
1. Calls `_create_account_move()` to generate the `account.move`.
2. Calls `_reconcile_account_move_lines()` to reconcile receivable lines.
3. For each cash payment method with a cash register, creates closing statement lines.
4. Posts the account move.
5. Sends notifications via `pos.bus.mixin` (`SESSION_CLOSED`).

**`_create_account_move()`** — Creates a single `account.move` (journal entry) for the entire session. Uses `_accumulate_amounts()` to group transactions by account/partner/tax. Key fields:
- `journal_id`: from `config_id.journal_id`
- `date`: `stop_at` date
- `ref`: session name
- Lines created via `_credit_amounts()` and `_debit_amounts()` helpers

**`_accumulate_amounts(lines, amounts)`** — Accumulates amounts into `AmountCounter` namedtuples grouped by `(account_id, tax_ids, base_account_id, for_invoice)`. Handles:
- Sales lines → credit revenue accounts
- Tax lines → credit tax receivable accounts
- Payment lines → debit bank/receivable accounts
- Cash change → debit cash account
- Stock consumed (Anglo-Saxon) → debit cost of goods sold

**`_reconcile_account_move_lines()`** — Matches debit/credit lines in the session's account move for receivable accounts. Particularly important for `split_transactions` (customer-identified payments) where each customer gets their own receivable line.

**`_credit_amounts(vals, amount, amount_converted)`** — Creates credit line values dict for `account.move.line.create()`.

**`_debit_amounts(vals, amount, amount_converted)`** — Creates debit line values dict.

**`_update_amounts(order, amounts)`** — Recalculates `amount_total`, `amount_paid`, etc. from order/payment data.

**`write(vals)`** — Overridden to prevent modification of `closed` sessions and to check access rights.

---

### 2.2 `pos.order` — POS Order

**File:** `models/pos_order.py`
**Lines:** ~1900
**Inherits:** `portal.mixin`, `pos.bus.mixin`, `pos.load.mixin`, `mail.thread`

The central record. An order is created when the POS frontend sends order data via `sync_from_ui()`. Orders can be created online or queued offline and synced later.

#### State Machine

```
┌────────┐   sync_from_ui()    ┌─────────┐   action_pos_order_paid()   ┌──────┐
│ draft  │ ───────────────────→│  paid   │ ────────────────────────────→│ done │
│ (new)  │                     │(posted) │                               │(inv.)│
└────────┘                     └─────────┘                               └──────┘
     │                                                                            │
     │ cancel()                                                                  │ action_pos_order_invoice()
     ▼                                                                            ▼
┌──────────┐                                                                 ┌─────────────┐
│ cancelled │                                                                 │ account_move │
└──────────┘                                                                 └─────────────┘
```

**`draft`** — Order created but not finalized. Still editable in POS.
**`paid`** — Payment received. Order is locked from further edits.
**`done`** — Order has been invoiced (or explicitly marked done).
**`cancel`** — Order cancelled (requires `pos_order_cancel` access right).

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | Integer | Yes | auto | Primary key |
| `name` | Char | Yes | `/` | Order reference (uses sequence) |
| `access_token` | Char | No | — | Portal access token (from `portal.mixin`) |
| `uuid` | Char | Yes | `uuid4()` | Unique identifier for frontend sync |
| `date_order` | Datetime | Yes | `now()` | Order date/time |
| `create_date` | Datetime | Yes | auto | Record creation time |
| `write_date` | Datetime | No | auto | Last write time |
| `user_id` | Many2one `res.users` | Yes | — | Employee/cashier who created the order |
| `company_id` | Many2one `res.company` | Yes | — | Operating company |
| `currency_id` | Many2one `res.currency` | Yes | computed | Order currency (from config) |
| `partner_id` | Many2one `res.partner` | No | — | Customer for the order |
| `note` | Text | No | — | Order-level note |
| `pos_reference` | Char | No | — | POS-facing reference (receipt number) |
| `proposer` | Char | No | — | Origin of the order (e.g., "pos" or " food" with leading space) |
| `sequence_number` | Integer | Yes | 1 | Session-unique sequence number |
| `session_id` | Many2one `pos.session` | Yes | — | Parent session |
| `config_id` | Many2one `pos.config` | Yes | — | POS terminal config (related to session) |
| `lines` | One2many `pos.order.line` | No | — | Order lines |
| `payment_ids` | One2many `pos.payment` | No | — | Payments for this order |
| `amount_paid` | Monetary | Yes | 0 | Sum of payment amounts |
| `amount_total` | Monetary | Yes | 0 | Tax-inclusive total |
| `amount_tax` | Monetary | Yes | 0 | Tax amount |
| `amount_return` | Monetary | Yes | 0 | Change/return amount |
| `amount_difference` | Monetary | Yes | 0 | Difference between total and paid |
| `margin` | Monetary | Yes | 0 | Computed as `amount_total - total_cost` |
| `margin_percent` | Float | Yes | 0 | Margin as percentage of total |
| `total_cost` | Float | Yes | 0 | Sum of line costs |
| `state` | Selection | Yes | `draft` | Order state |
| `account_move` | Many2one `account.move` | No | — | Generated invoice |
| `invoice_id` | Many2one `account.move` | No | — | Alias for `account_move` |
| `to_invoice` | Boolean | Yes | False | Flag to generate invoice |
| `is_invoiced` | Boolean | Yes | False | Whether invoice was generated |
| `is_refund` | Boolean | Yes | False | Whether this is a refund order |
| `refunded_order_id` | Many2one `pos.order` | No | — | Original order for refunds |
| `picking_ids` | One2many `stock.picking` | No | — | Stock pickings for this order |
| `picking_count` | Integer | No | 0 | Number of pickings (computed) |
| `is_tipped` | Boolean | Yes | False | Whether tip was added |
| `tip_amount` | Monetary | Yes | 0 | Tip amount |
| `ticket_code` | Char | No | — | 5-digit code for portal access |
| `fiscal_position_id` | Many2one `account.fiscal.position` | No | — | Fiscal position applied |
| `tax_id` | Many2one `account.tax` | No | — | Default tax (deprecated in favor of line-level taxes) |
| ` pricelist_id` | Many2one `product.pricelist` | No | — | Pricelist used (deprecated, use `config_id.pricelist_id`) |
| `location_id` | Many2one `stock.location` | No | — | Stock location for picking |
| `force_line_ids` | One2many | No | — | Order lines with forced prices (for `pos_order_cancel`) |

#### Key Methods

**`sync_from_ui(order_data)`** — `@api.model` — Static method that receives a dict from the frontend. Creates or updates an order by UUID. Returns dict with `id`, `account_move` (if invoiced), and `fulfillment_success`. Handles both new orders and updates to existing orders.

**`_process_order(order_data)`** — Creates or writes the order record. Handles:
- `uuid` matching for upsert
- `date_order` parsing (handles both datetime and date strings)
- Fiscal position detection via `_get_fiscal_position()`
- Partner credit check via `partner.credit_check()`
- Line creation via `_process_lines()`
- Payment processing via `_process_payment_lines()`
- Stock picking creation via `_create_order_picking()`
- Invoice generation if `to_invoice` is True

**`_process_lines(lines)`** — Creates/updates `pos.order.line` records. Applies `_prepare_order_line()` for each line. Handles combo items by recursively processing `combo_line_ids`.

**`_prepare_order_line(line_data)`** — Prepares a single order line dict with:
- `product_id`, `qty`, `price_unit`, `discount`
- `tax_ids` (after fiscal position application via `_get_taxes()`)
- `pack_lot_ids` (for lot-tracked products)
- `full_product_name`
- `is_tip_line` (for tip products)
- `combo_item_id`, `combo_parent_id` (for combo lines)

**`_get_taxes(product, partner)`** — Determines applicable taxes. Applies:
1. Product-specific taxes
2. Fiscal position tax mappings (`account.fiscal.position.tax_ids`)
3. Partner customer taxes (from `res.partner.property_account_position_id`)

**`_get_fiscal_position(partner)`** — Determines which fiscal position to apply:
1. If `fiscal_position_id` is set on the order, use it
2. Else call `partner.property_account_position_id`
3. Else auto-detect from partner country via `_infer_fiscal_position()`

**`_process_payment_lines(payment_data)`** — Creates `pos.payment` records from payment data dicts. Validates that payment methods are allowed in the session's config.

**`_create_order_picking()`** — Creates a `stock.picking` of type `config_id.picking_type_id` for each order. Uses `_prepare_order_picking()` to build the picking. Creates `stock.move` records for each order line via `_prepare_order_line_for_procurement()`. If `ship_later` is enabled on the config, pickings are created only when the session closes.

**`_generate_pos_order_invoice()`** — Generates an `account.move` of type `out_invoice`. Uses `_prepare_invoice_vals()` to build the move header and `_prepare_invoice_lines()` for line items. Applies fiscal position to account mapping. Links the invoice to the order via `account_move` field.

**`_prepare_invoice_vals()`** — Builds the invoice header dict:
- `partner_id`, `invoice_origin` (order name), `move_type`: `out_invoice`
- `journal_id`: from config's `invoice_journal_id`
- `fiscal_position_id`: from order
- `pos_session_id`: link back to session
- `invoice_line_ids`: built separately

**`_prepare_invoice_lines(order_lines)`** — Builds invoice line dicts. For each order line:
- Determines account from product's `property_account_income_id` or category's `property_account_income_categ_id`
- Applies fiscal position account mapping
- Splits line if fiscal position maps to multiple accounts
- Handles refund lines (negative quantities/amounts)

**`action_pos_order_paid()`** — State transition `draft → paid`. Sets `amount_paid`, `amount_return`, `amount_difference`. Called when payment is confirmed. Checks that total is covered.

**`action_pos_order_invoice()`** — Generates invoice if `to_invoice` is set. Returns the invoice action.

**`refund()`** — Creates a refund (return) order:
1. Creates new order with `is_refund=True`, `refunded_order_id` pointing to original
2. Copies/refunds order lines
3. For paid orders: creates payment reversal if original had payments
4. For invoiced orders: calls `_generate_credit_note()`
5. Returns wizard to show refund result

**`_refund()`** — The actual refund creation logic (called from `refund()` wizard).

**`_generate_credit_note()`** — Creates an `account.move` of type `out_refund` linked to the original invoice.

**`action_cancel()`** — Cancels the order if in `draft` state. Only users with `pos_order_cancel` right can cancel.

**`action_pos_order_done()`** — State transition `paid → done`. Called after invoice is created. Triggers picking validation if all pickings are done.

**`_send_to_kitchen()`** — Sends order lines to kitchen display/printer via `pos.bus.mixin` notification (`ACTION_SEND_TO_KITCHEN`).

**`_get_pos_account_id(product)`** — Returns the income account for a product, applying fiscal position mappings.

**`_get_partner_credit_account_id(partner)`** — Returns the receivable account for the partner.

**`_get_split_receivable_account(payment_method)`** — Returns the receivable account for split transactions.

---

### 2.3 `pos.order.line` — Order Line

**File:** `models/pos_order.py`
**Inherits:** `pos.load.mixin`

Order lines represent individual products or services on an order.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | Integer | Yes | auto | Primary key |
| `name` | Char | Yes | `product_id.display_name` | Line description |
| `company_id` | Many2one `res.company` | Yes | — | Operating company |
| `order_id` | Many2one `pos.order` | Yes | — | Parent order (cascade delete) |
| `product_id` | Many2one `product.product` | Yes | — | Product variant |
| `product_template_id` | Many2one `product.template` | No | — | Product template (computed from product) |
| `attribute_value_ids` | Many2many `product.template.attribute.value` | No | — | Selected attribute values |
| `custom_attribute_value_ids` | One2many `pos.custom_attribute_value` | No | — | Custom attribute values |
| `price_unit` | Float | Yes | — | Unit price (before tax, after pricelist) |
| `price_type` | Selection | Yes | `original` | `original`, `manual`, or `automatic` (from pricelist) |
| `qty` | Float | Yes | 1.0 | Quantity ordered |
| `price_subtotal` | Monetary | Yes | — | Tax-exclusive subtotal (`price_unit * qty * (1 - discount/100)`) |
| `price_subtotal_incl` | Monetary | Yes | — | Tax-inclusive subtotal |
| `price_extra` | Float | Yes | 0 | Extra price from attribute selection |
| `discount` | Float | Yes | 0 | Discount percentage (0–100) |
| `tax_ids` | Many2many `account.tax` | No | — | Taxes applied to this line |
| `tax_ids_with_setting` | Many2many `account.tax` | No | — | Taxes from product settings (before fiscal position) |
| `pack_lot_ids` | One2many `pos.pack.operation.lot` | No | — | Lot/serial numbers for tracked products |
| `product_uom_id` | Many2one `uom.uom` | No | — | Unit of measure |
| `full_product_name` | Char | No | — | Full display name shown in POS |
| `uuid` | Char | Yes | `uuid4()` | Unique identifier |
| `is_tip_line` | Boolean | Yes | False | Whether this is a tip line |
| `margin` | Monetary | Yes | — | Line margin (`price_subtotal - total_cost`) |
| `margin_percent` | Float | Yes | — | Margin percentage |
| `total_cost` | Float | Yes | — | Total cost for margin calculation |
| `refunded_qty` | Float | Yes | 0 | Total quantity already refunded |
| `refunded_orderline_id` | Many2one `pos.order.line` | No | — | Original line this line refunded |
| `combo_parent_id` | Many2one `pos.order.line` | No | — | Parent combo line |
| `combo_line_ids` | One2many `pos.order.line` | No | — | Child lines of a combo |
| `combo_item_id` | Many2one `pos.combo.item` | No | — | Combo item that generated this line |
| `pos_category_id` | Many2one `pos.category` | No | — | POS category of the product |
| `has_product_customer_option` | Boolean | No | — | Whether product has customer-specific pricing |
| `customer_pricing_product_template_id` | Many2one `product.template` | No | — | Customer-specific pricing record |

#### Key Methods

**`write(vals)`** — Overridden to prevent modification of `done` orders. Only `refunded_qty` can be updated on done orders. When `order_edit_tracking` is enabled and a line's qty is reduced, `is_edited` is set to True and a `mail.thread` message is posted to the order.

**`_compute_amount_line_all()`** — Called by `_onchange_amount_line_all()`. Applies discount to `price_unit`, then calls `tax_ids_after_fiscal_position.compute_all()` to compute `price_subtotal` (excl. tax) and `price_subtotal_incl` (incl. tax). Uses fiscal position from `order_id.fiscal_position_id`.

**`_get_tax_ids_after_fiscal_position`** (compute) — Maps the line's `tax_ids` through the order's fiscal position via `fpos.map_tax()`. This is the authoritative tax list used for invoice lines.

**`_compute_margin()`** — Computes `margin` and `margin_percent` for the line. `total_cost` must be computed first (either in real-time or at session close for FIFO/AVCO products). Margin = `price_subtotal - total_cost`.

**`_is_product_storable_fifo_avco()`** — Returns True if the line's product is storable AND uses FIFO or Average Cost (AVCO) valuation. These products require cost computation at session close (not real-time) because the cost layer isn't determined until the stock move is created.

**`_compute_total_cost(stock_moves)`** — Called from `pos.order._compute_total_cost_in_real_time()` and `pos.order._compute_total_cost_at_session_closing()`. Matches stock moves (filtered by product_id) to compute unit cost, then sets `total_cost = qty * unit_cost`. For FIFO: uses `_get_price_unit()` on the matching move. For AVCO: uses the product's average cost.

**`get_existing_lots(company_id, config_id, product_id)`** — Returns available lots for a product in the POS's warehouse stock location (`picking_type_id.default_location_src_id.child_internal_location_ids`). Only lots with positive quantity are returned. This is called from the frontend when selecting a lot for a tracked product.

**`refunded_qty` (compute)** — Sums quantities from `refund_orderline_ids` where the refund order is not cancelled: `refunded_qty = -SUM(refund_line.qty)`. A line is fully refundable when `qty > refunded_qty`.

---

### 2.4 `pos.payment` — Payment

**File:** `models/pos_payment.py`
**Inherits:** `pos.load.mixin`

Records individual payments for an order. A single order can have multiple payments (split tender).

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | Integer | Yes | auto | Primary key |
| `name` | Char | No | — | Payment label (display name) |
| `uuid` | Char | Yes | `uuid4()` | Unique identifier |
| `pos_order_id` | Many2one `pos.order` | Yes | — | Parent order (cascade delete) |
| `payment_method_id` | Many2one `pos.payment.method` | Yes | — | Payment method used |
| `amount` | Monetary | Yes | — | Payment amount |
| `payment_date` | Datetime | Yes | `now()` | When payment was made |
| `currency_id` | Many2one `res.currency` | Yes | related | Order's currency |
| `currency_rate` | Float | No | related | Conversion rate to company currency |
| `partner_id` | Many2one `res.partner` | No | related | Customer (from order) |
| `session_id` | Many2one `pos.session` | Yes | related+stored | Session (from order) |
| `user_id` | Many2one `res.users` | No | related | Employee (from session) |
| `company_id` | Many2one `res.company` | No | related | Company |
| `card_type` | Char | No | — | Card type: `credit_card`, `debit_card`, etc. |
| `card_brand` | Char | No | — | Card brand: `Visa`, `AMEX`, `Mastercard` |
| `card_no` | Char | No | — | Last 4 digits of card number |
| `cardholder_name` | Char | No | — | Name on card |
| `payment_ref_no` | Char | No | — | Terminal payment reference number |
| `payment_method_authcode` | Char | No | — | Authorization code from terminal |
| `payment_method_issuer_bank` | Char | No | — | Issuing bank |
| `payment_method_payment_mode` | Char | No | — | Payment mode |
| `transaction_id` | Char | No | — | Provider transaction ID |
| `payment_status` | Char | No | — | Payment status string |
| `ticket` | Char | No | — | Payment receipt info |
| `is_change` | Boolean | Yes | False | Whether this is a change payment (negative amount to customer) |
| `account_move_id` | Many2one `account.move` | No | — | Accounting entry created at session close |
| `payment_method_id.active` | Boolean | No | — | Payment method active status |

#### Key Methods

**`_create_payment_moves()`** — Creates `account.move` entries for payments. Called at session close. Key logic:
- Skips `pay_later` type payments
- Skips zero-amount payments
- For `cash` payments with `is_change=True`: creates a separate debit entry for the cash account
- Groups change payments with the originating payment
- Creates credit line for receivable account (customer/partner)
- Creates debit line for the payment method's bank/receivable account
- Handles `split_transactions` (customer-identified payments) with separate receivable accounts per partner
- Handles `is_reverse=True` for refunds (uses reversed receivable account)

**`_get_receivable_lines_for_invoice_reconciliation(receivable_account)`** — Returns `account.move.line` records that should be reconciled with invoice receivable lines. Heuristic:
- Positive payment → negative balance lines (debit entries)
- Negative payment → positive balance lines (credit entries)

**`_check_amount()`** — `@api.constrains` — Prevents editing payments on `done` orders or orders with an invoice.

**`_check_payment_method_id()`** — `@api.constrains` — Ensures the payment method is allowed in the session's config.

---

### 2.5 `pos.config` — POS Configuration

**File:** `models/pos_config.py`
**Lines:** ~1000
**Inherits:** `pos.bus.mixin`, `pos.load.mixin`

Defines a POS terminal/interface. Each config represents a unique point-of-sale setup with its own sequence, payment methods, pricelists, and hardware settings.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | Integer | Yes | auto | Primary key |
| `name` | Char | Yes | — | POS terminal name |
| `is_order_printer` | Boolean | Yes | False | Whether this is a kitchen printer terminal |
| `picking_type_id` | Many2one `stock.picking.type` | No | — | Stock operation type for order delivery |
| `journal_id` | Many2one `account.journal` | No | — | Sales journal for accounting entries |
| `invoice_journal_id` | Many2one `account.journal` | No | — | Journal for invoices |
| `currency_id` | Many2one `res.currency` | No | computed | Currency (from journal or company) |
| `order_seq_id` | Many2one `ir.sequence` | No | — | Order numbering sequence |
| `sequence_id` | Many2one `ir.sequence` | No | — | Session sequence |
| `iface_cashdrawer` | Boolean | Yes | True | Show cash drawer button |
| `iface_electronic_scale` | Boolean | Yes | False | Enable scale integration |
| `iface_print_via_proxy` | Boolean | Yes | False | Print receipts via hardware proxy |
| `iface_scan_via_proxy` | Boolean | Yes | False | Scan barcodes via proxy |
| `iface_group_by_categ` | Boolean | Yes | False | Group products by category in UI |
| `iface_print_auto` | Boolean | Yes | False | Auto-print receipts after payment |
| `iface_tax_included` | Selection | Yes | `total` | Tax display: `subtotal` or `total` |
| `iface_available_categ_ids` | Many2many `pos.category` | No | — | Categories visible in this POS |
| `limit_categories` | Boolean | Yes | False | Restrict visible categories |
| `restrict_price_control` | Boolean | Yes | False | Require manager PIN for price changes |
| `cash_control` | Boolean | Yes | False | Require cash balance reconciliation |
| `amount_authorized_diff` | Float | Yes | 0 | Max allowed difference in cash payments |
| `receipt_header` | Text | No | — | Text printed at top of receipt |
| `receipt_footer` | Text | No | — | Text printed at bottom of receipt |
| `basic_receipt` | Boolean | Yes | False | Print receipt without prices |
| `proxy_ip` | Char | No | — | Hardware proxy IP address |
| `current_session_id` | Many2one `pos.session` | No | computed | Currently open session |
| `current_session_state` | Selection | No | computed | State of current session |
| `pricelist_id` | Many2one `product.pricelist` | No | — | Default pricelist |
| `available_pricelist_ids` | Many2many `product.pricelist` | No | — | Pricelists available to cashiers |
| `use_pricelist` | Boolean | Yes | False | Enable pricelist selection in POS |
| `company_id` | Many2one `res.company` | Yes | — | Operating company |
| `group_pos_manager_id` | Many2one `res.groups` | No | — | POS Manager group |
| `group_pos_user_id` | Many2one `res.groups` | No | — | POS User group |
| `tip_product_id` | Many2one `product.product` | No | — | Product used for tips |
| `fiscal_position_ids` | Many2many `account.fiscal.position` | No | — | Available fiscal positions |
| `module_pos_restaurant` | Boolean | Yes | False | Enable restaurant features (split bill, floor plan) |
| `module_pos_avatax` | Boolean | Yes | False | Enable Avatax tax calculation |
| `module_pos_discount` | Boolean | Yes | False | Enable global discounts |
| `module_pos_hr` | Boolean | Yes | False | Enable employee login |
| `payment_method_ids` | Many2many `pos.payment.method` | No | — | Payment methods available |
| `rounding_method` | Many2one `account.cash.rounding` | No | — | Cash rounding method |
| `cash_rounding` | Boolean | Yes | False | Enable cash rounding |
| `manual_discount` | Boolean | Yes | False | Allow line discounts |
| `ship_later` | Boolean | Yes | False | Ship orders separately from session |
| `warehouse_id` | Many2one `stock.warehouse` | No | — | Warehouse for stock operations |
| `is_posbox` | Boolean | Yes | False | Whether running on PosBox hardware |
| `show_product_images` | Boolean | Yes | False | Display product images |
| `order_edit_tracking` | Boolean | Yes | False | Track order modifications |
| `printer_ids` | Many2many `pos.printer` | No | — | Kitchen/display printers |
| `epson_printer_ip` | Char | No | — | Epson printer IP for IoT |
| `use_fast_payment` | Boolean | Yes | False | Skip payment confirmation |
| `statistics_for_current_session` | JSON | No | — | Real-time session statistics |
| `account_default_pos_receivable_account_id` | Many2one `account.account` | No | — | Default receivable for this config |
| `default_bill_ids` | One2many `pos.bill` | No | — | Predefined bill denominations |

#### Key Methods

**`open_ui()`** — Opens the POS interface. Creates a new session if none is open. Returns action to load the POS web client.

**`_create_sequences()`** — Creates `ir.sequence` records for order numbering and session naming if they don't exist.

**`_load_pos_data_read()`** — Returns all data needed by the POS frontend: products, categories, taxes, pricelists, payment methods, printers, combo items, etc. Called when the POS UI loads.

**`_load_pos_data_domain(model_name, data, config)`** — Returns domain for filtering which records of `model_name` are loaded into the POS.

**`get_pos_ui_session_info()`** — Returns session info dict for the frontend including `server_version`, `is_website_installed`, `pos_config`, `pos_session`, `pos_categories`, `products_by_id`, etc.

**`read(q)`** — Overridden to include computed fields in the POS data snapshot.

---

### 2.6 `pos.payment.method` — Payment Method

**File:** `models/pos_payment_method.py`
**Inherits:** `pos.load.mixin`

Defines payment instruments available at the POS (cash, credit card terminal, bank transfer, etc.).

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | Integer | Yes | auto | Primary key |
| `name` | Char | Yes | — | Method name shown in POS UI |
| `sequence` | Integer | No | — | Display order |
| `active` | Boolean | Yes | True | Whether method is active |
| `type` | Selection | No | computed | `cash`, `bank`, or `pay_later` (computed from `journal_id.type`) |
| `is_cash_count` | Boolean | No | computed | True if `type == 'cash'` |
| `journal_id` | Many2one `account.journal` | No | — | Associated journal (cash or bank type) |
| `outstanding_account_id` | Many2one `account.account` | No | — | Outstanding account for bank payments |
| `receivable_account_id` | Many2one `account.account` | No | — | Receivable account for this method |
| `split_transactions` | Boolean | Yes | False | Require customer identification per payment |
| `payment_method_type` | Selection | Yes | `none` | `none`, `terminal`, or `qr_code` |
| `use_payment_terminal` | Selection | No | — | Payment terminal type (inherited by subclasses) |
| `qr_code_method` | Selection | No | — | QR code format for bank app payments |
| `hide_use_payment_terminal` | Boolean | No | computed | Hide terminal field if not applicable |
| `hide_qr_code_method` | Boolean | No | computed | Hide QR method if not applicable |
| `default_qr` | Char | No | computed | Pre-generated QR code for offline use |
| `open_session_ids` | Many2many `pos.session` | No | computed | Open sessions using this method |
| `config_ids` | Many2many `pos.config` | No | — | POS configs using this method |
| `company_id` | Many2one `res.company` | No | — | Company |
| `default_pos_receivable_account_name` | Char | No | related | Display name of default receivable |
| `image` | Image | No | — | Icon for POS UI (50x50px) |

#### Key Methods

**`_get_payment_method_type()`** — Returns selection list: `none`, `terminal`, and `qr_code` (if QR methods are available in the system).

**`_is_online_payment()`** — Static method; overridden by `pos_online_payment` module. Default returns False.

**`_compute_type()`** — Computes `type` from `journal_id.type`: `cash` if `journal_id.type == 'cash'`, `bank` if `journal_id.type == 'bank'`, else `pay_later`.

**`_is_write_forbidden(fields)`** — Prevents writing to payment methods that have open sessions (except `sequence`).

**`_force_payment_method_type_values(vals, payment_method_type, if_present=False)`** — Clears incompatible fields when changing payment method type (e.g., clears `qr_code_method` when switching from `qr_code` to `terminal`).

**`get_qr_code(amount, free_communication, structured_communication, currency, debtor_partner)`** — Generates a base64-encoded QR code for `qr_code` payment methods.

---

### 2.7 `pos.order` — Order-Level Accounting (`_prepare_aml_values_list_per_nature`)

When an invoiced order is finalized via `_generate_pos_order_invoice()`, it builds `aml_vals_list_per_nature` — a `defaultdict(list)` with four categories of journal entry lines:

- **`product`** — Revenue lines for each order line. Account comes from `product_id.property_account_income_id` or category fallback. Tax lines are added separately from `tax_results['tax_lines_to_add']`.
- **`tax`** — Tax amounts mapped to each tax's `cash_basis_transition_account_id` (or default tax account).
- **`payment_terms`** — Receivable debit entries for each payment. Aggregated per receivable account unless `split_transactions=True`.
- **`cash_rounding`** — Rounding adjustment lines using `rounding_method.loss_account_id` (for negative diff) or `profit_account_id` (for positive diff), only when `strategy == 'add_invoice_line'`.
- **`stock`** — COGS/inventory entries (only when `inventory_valuation == 'real_time'` and pickings exist).

The sign for quantities and amounts is `-1` for refunds (`is_refund=True`) and `+1` for regular orders.

### 2.7b `account.bank.statement.line` Extension

**File:** `models/account_bank_statement.py`
**Inherits:** `account.bank.statement.line`

Extends the standard cash statement line with:

```python
pos_session_id = fields.Many2one('pos.session', string="Session",
    copy=False, index='btree_not_null')
```

This field links cash statement lines (created via cash in/out operations in the POS) back to the originating session. It enables:
- `rule_pos_bank_statement_line_user`: POS users can only see statement lines linked to their sessions.
- Session cash balance computation (`cash_register_balance_end`): includes `statement_line_ids.mapped('amount')`.
- Profit/loss recording at session close: `_post_statement_difference()` creates a statement line for the closing variance.

---

### 2.7c `pos.load.mixin` — Frontend Data Loading Contract

**File:** `models/pos_load_mixin.py`

Every model accessible in the POS frontend must inherit `pos.load.mixin` and implement the two method contract:

**`_load_pos_data_domain(data, config)`** — Returns a domain filter. The `config` argument is the `pos.config` record being loaded. Return `False` (not an empty list) to exclude this model entirely from loading.

**`_load_pos_data_fields(config)`** — Returns a flat list of field names to load from the server. These fields are sent to the frontend.

The `_load_pos_data_search_read()` method chains these: it converts the domain, searches records, then reads the specified fields. The `_server_date_to_domain()` helper appends `('write_date', '>', last_server_date)` when incremental sync is active (`pos_limited_loading=True`), allowing the frontend to only request records changed since the last sync.

Models registered in `pos.session._load_pos_data_models()` include ~37 model names. Custom models added via inheritance are automatically included if they inherit `pos.load.mixin`.

### 2.7d `pos.bus.mixin` — Real-Time Event Bus

**File:** `models/pos_bus_mixin.py`

Provides two capabilities:

1. **`access_token`** — A UUID stored on each session/config record. Used as the bus channel name.
2. **`_notify(name, message)`** — Sends a notification to the Odoo bus on channel `access_token`. The frontend subscribes to this channel via `bus.bus`.

Key notification events:
- `CLOSING_SESSION` — Sent when a session's `state` transitions to `closed` (in `pos.session.write()`)
- `SYNCHRONISATION` — Sent by `config_id.notify_synchronisation()` when an order is created/updated
- `UPDATE_CUSTOMER_DISPLAY-{device_uuid}` — Sent by `config_id.update_customer_display()` for external customer display hardware
- `ACTION_NEW`, `ACTION_UPDATE_ORDER_STATE`, `ACTION_SEND_TO_KITCHEN` — POS restaurant mode notifications

The `_ensure_access_token()` method lazily generates a UUID token on first access if none is set.

### 2.7e `account.cash.rounding` Extension

**File:** `models/account_cash_rounding.py`

Prevents deletion of a rounding method that is referenced by any `pos.config`:
```python
@api.ondelete(at_uninstall=False)
def _unlink_except_pos_config(self):
    if self.env['pos.config'].search_count([('rounding_method', 'in', self.ids)], limit=1):
        raise UserError(_("You cannot delete a rounding method that is used in a Point of Sale configuration."))
```

### 2.8 `pos.category` — POS Category

**File:** `models/pos_category.py`
**Inherits:** `pos.load.mixin`

Hierarchical product categories for organizing the POS product grid.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | Integer | Yes | auto | Primary key |
| `name` | Char | Yes | — | Category name (translatable) |
| `parent_id` | Many2one `pos.category` | No | — | Parent category (self-referential) |
| `child_ids` | One2many `pos.category` | No | — | Child categories |
| `sequence` | Integer | No | — | Display order |
| `image_512` | Image | No | — | Category image (512px) |
| `image_128` | Image | No | — | Category image (128px, thumbnail) |
| `color` | Integer | No | — | Color index for UI |
| `has_image` | Boolean | No | computed | True if `image_512` is set |
| `hour_until` | Float | Yes | 24.0 | Products available until this hour |
| `hour_after` | Float | Yes | 0.0 | Products available after this hour |

#### Key Methods

**`_check_category_recursion()`** — `@api.constrains` — Prevents circular parent-child relationships.

**`_get_hierarchy()`** — Returns the full path of parent category names as a string.

**`_get_descendants()`** — Returns a recordset of all descendant categories (children of children, recursively). Used for filtering products when `limit_categories` is enabled.

---

### 2.8 `pos.printer` — Printer / IoT Device

**File:** `models/pos_printer.py`
**Inherits:** `pos.load.mixin`

Kitchen printer and display configurations.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | Integer | Yes | auto | Primary key |
| `name` | Char | Yes | `Printer` | Internal printer name |
| `printer_type` | Selection | Yes | `iot` | `iot` (IoT Box printer) or `epson_epos` |
| `proxy_ip` | Char | No | — | Hardware proxy IP |
| `product_categories_ids` | Many2many `pos.category` | No | — | Categories routed to this printer |
| `company_id` | Many2one `res.company` | Yes | — | Company |
| `pos_config_ids` | Many2many `pos.config` | No | — | POS configs using this printer |
| `epson_printer_ip` | Char | No | `0.0.0.0` | Epson printer IP or serial number |

#### Key Methods

**`format_epson_certified_domain(serial_number)`** — Converts an Epson printer serial number to a certified domain name using SHA256 + Base32 encoding. Used when the printer has "Automatic Certificate Update" enabled.

**`_constrains_epson_printer_ip()`** — `@api.constrains` — Ensures `epson_printer_ip` is not empty when `printer_type == 'epson_epos'`.

**`_onchange_epson_printer_ip()`** — `@api.onchange` — Automatically converts IP/serial to certified domain format.

---

### 2.9 `pos.bill` — Denomination Bill

**File:** `models/pos_bill.py`
**Inherits:** `pos.load.mixin`

Defines bill denominations for cash payment quick-selection in the POS UI.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | Integer | Yes | auto | Primary key |
| `name` | Char | Yes | — | Bill value (e.g., "10.00") |
| `value` | Float | Yes | — | Monetary value |
| `pos_config_ids` | Many2many `pos.config` | No | — | POS configs showing this bill |
| `company_id` | Many2one `res.company` | No | — | Company |

---

### 2.10 `pos.note` — POS Note / Order Line Note

**File:** `models/pos_note.py`
**Inherits:** `pos.load.mixin`

Predefined notes that can be attached to order lines for kitchen communication.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | Integer | Yes | auto | Primary key |
| `name` | Char | Yes | — | Note text |
| `pos_config_ids` | Many2many `pos.config` | No | — | POS configs showing this note |
| `company_id` | Many2one `res.company` | No | — | Company |

---

## L3 — Edge Cases, Triggers, Failure Modes

### 3.1 Cross-Model Interactions

**Order → Session → Accounting**

When a `pos.order` is created, it must belong to an open `pos.session`. The session's `_validate_session()` aggregates all orders' amounts into a single `account.move`. If an order is created but the session is closed before the order is finalized, the system raises `UserError: "You cannot create orders for a closed session."` The order's `session_id` is a required field with `ondelete='cascade'`, so closing a session cascades to all its orders.

**Fiscal Position Application Chain**

Fiscal positions are applied at three levels:

1. **Line level** (`_prepare_order_line` → `_get_taxes`): Product taxes are mapped through the fiscal position's `account.fiscal.position.tax_ids` table.
2. **Invoice level** (`_prepare_invoice_vals`): The fiscal position is written to the invoice header.
3. **Account level** (`_prepare_invoice_lines`): Income accounts are mapped through `account.fiscal.position.account_ids`.

This means a fiscal position can change both *which taxes are applied* and *which accounts receive the revenue*.

**Stock Picking and Anglo-Saxon Accounting**

When `stock_account` is installed, POS orders create `stock.picking` records with `stock.move` entries. The picking's `stock.quant` updates affect inventory valuation. Combined with session-close accounting entries, this creates the dual-entry for cost of goods sold (COGS) under Anglo-Saxon accounting:
- **Sales entry** (session close): Debit Receivable, Credit Revenue
- **COGS entry** (picking validation): Debit COGS, Credit Inventory

**Partner Credit and `split_transactions`**

When `split_transactions` is enabled on a payment method, each payment creates its own receivable line keyed to the specific partner, rather than using the POS's default receivable account. This allows per-customer reconciliation at session close. The method `_get_split_receivable_account()` handles this.

### 3.2 Override Patterns

**`pos.load.mixin` — Frontend Data Loading**

Any model that needs to appear in the POS frontend must inherit `pos.load.mixin` and implement (or inherit default implementations of):
- `_load_pos_data_domain(data, config)` — Returns a domain filter (e.g., `[('available_in_pos', '=', True)]` for products)
- `_load_pos_data_fields(config)` — Returns the list of field names to load

The frontend's `models.js` iterates all registered models, calls these methods, and builds the SQLite snapshot.

**`pos.bus.mixin` — Real-time Events**

Provides methods for broadcasting events across POS terminals:
- `_send_to_channel()` — Sends a notification to the `pos.bus` channel
- Events: `ACTION_NEW`, `ACTION_UPDATE_ORDER_STATE`, `ACTION_SEND_TO_KITCHEN`, `SESSION_CLOSED`

**Fiscal Position Detection**

Models inheriting `account.fiscal.position.python` can provide a `_get_fiscal_position()` method returning a dynamically-computed fiscal position based on partner/order context.

### 3.3 Workflow Triggers

| Trigger | Action | Result |
|---------|--------|--------|
| POS UI loads | `pos.config` `_load_pos_data_read()` | Product/category/pricelist snapshot loaded to SQLite |
| Order finalized in POS | `sync_from_ui()` | `pos.order` created/updated, state `draft` |
| Payment confirmed | `action_pos_order_paid()` | State `draft → paid`, order locked |
| "Invoice" button clicked | `_generate_pos_order_invoice()` | `account.move` created, `to_invoice=False` |
| Session "Close" clicked | `try_close()` | Validate all orders paid |
| Session validated | `_validate_session()` → `_create_account_move()` | `account.move` posted for entire session |
| `stock_account` installed | `_create_order_picking()` | `stock.picking` + `stock.move` created |
| Split bill (restaurant) | `pos.order` `_split_bill()` | New `pos.order` created for subset of lines |
| Kitchen printer active | `_send_to_kitchen()` | `pos.bus` notification with line data |
| Offline order synced | `sync_from_ui()` with existing `uuid` | Order upserted, `ACTION_NEW` broadcast |

### 3.4 Failure Modes

**Insufficient Payment**

If total paid (`amount_paid`) is less than total (`amount_total`), the order remains in `draft` state. The `amount_difference` field tracks this shortfall. The order cannot be validated until the difference is covered by an additional payment or the order is cancelled.

**Session Closed with Unpaid Orders**

`try_close()` explicitly checks for any order in `draft` or `paid` (not `done`) state and raises `UserError` if found. This prevents accounting gaps where revenue is recognized without corresponding receivable entries.

**Concurrent Orders (Same Session, Multiple Terminals)**

Multiple POS terminals can add orders to the same session. The session has a single `account.move` at close. `_accumulate_amounts()` handles concurrent writes by re-reading totals from the database at close time rather than trusting in-memory values.

**Stock Unavailability**

For tracked products (lots/serial numbers), `_process_lines()` creates `pos.pack.operation.lot` records. If the lot is not available in the warehouse's quants, the picking will be in `assigned` or `confirmed` state depending on the routes. Odoo will not automatically reserve stock; this requires manual intervention or automation rules.

**Fiscal Position Changes After Invoice**

Once an invoice (`account.move`) is posted, its fiscal position is locked into the account mappings. Changing the partner's fiscal position afterward has no effect on already-posted invoices.

**Currency Mismatch**

The `currency_id` on `pos.order` is derived from the config's journal. If the journal's currency differs from the company's default, all amounts in the order are converted at the `currency_rate` stored on each payment. The session's accounting entries use the company's currency, with conversion handled at the payment level.

**Lock Date Violation**

`pos.session._check_start_date()` validates that the session's `start_at` does not precede any accounting lock date for the session's journal. If violated, raises `ValidationError` with the lock date details.

**Invoice Already Being Generated**

`_generate_pos_order_invoice()` wraps the invoice creation in `_with_locked_records()` with `allow_raising=False`. If another invoice is being generated concurrently, it raises `UserError: Some orders are already being invoiced. Please try again later.`

**Account Deleted Mid-Session**

If an account (revenue, receivable, tax) used in the session's order lines is deleted between order creation and session close, `_create_account_move()` will fail with a `ValidationError` when trying to create `account.move.line` records. The entire close operation rolls back.

**Cash Journal Missing Loss/Profit Account**

`_check_profit_loss_cash_journal()` validates that the cash journal has both `loss_account_id` and `profit_account_id` configured when `cash_control` is enabled. Without these, the closing difference cannot be recorded.

**Split Transaction + Customer Account Receivable Mismatch**

When `split_transactions=True`, payments use the customer's `property_account_receivable_id`. If this account differs from the POS's default receivable (e.g., due to a multi-company or multi-currency configuration), reconciliation may fail at session close.

**Multiple Unpaid Invoiced Orders**

If `_check_invoices_are_posted()` finds unposted invoices during `try_close()`, the session cannot be closed. All invoices linked to orders in the session must be posted first.

**Duplicate Cash Journals Across Payment Methods**

`_check_payment_method_ids_journal()` enforces that a single cash journal cannot be shared between multiple `pos.payment.method` records. This prevents a single cash drawer from being split across multiple payment method configurations.

**Session State Transitions — Forbidden Paths**

- `closed` sessions cannot be reopened (no write on `state` allowed once `closed`)
- `try_close()` cannot be called on sessions with `draft` orders
- `opening_control` sessions cannot accept orders until `open_ui()` is called
- `closing_control` sessions cannot accept new orders (draft state blocked by frontend)

---

## L4 — Performance, Security, Version History

### 4.1 Performance Implications

**SQLite Snapshot Loading**

When the POS UI loads, `_load_pos_data_read()` is called server-side to return all data. For large catalogs (10,000+ products), this can be slow. The `_load_pos_data_domain()` method on `product.product` filters to only `available_in_pos=True` products, and `pos.category` uses `_get_descendants()` to efficiently compute the category filter. In practice, the POS loads only a subset of the full product catalog based on the config's `iface_available_categ_ids` and pricelist restrictions.

**N+1 Query Risk in `_accumulate_amounts()`**

The session close method `_accumulate_amounts()` loops through all order lines and payment lines. Each line access may trigger related field lookups (tax_ids, account_id). This is mitigated by the ORM's prefetch mechanism — Odoo batches record access — but for very large sessions (1,000+ orders), this can take several seconds. The `amount_*` computed fields on `pos.session` use SQL `SUM()` aggregations which are more efficient than ORM record iteration.

**Offine Operation and UUID Sync**

When operating offline, the frontend creates orders with local UUIDs. On reconnection, `sync_from_ui()` performs a search by `uuid` to upsert. The `uuid` field is not indexed by default in older versions — adding an index on `pos.order.uuid` significantly improves sync performance for large offline queues.

**Stock Picking Creation**

`_create_order_picking()` creates a `stock.picking` and `stock.move` for each order. For restaurant mode with `ship_later` enabled, pickings are batched at session close rather than created per order, reducing database round-trips.

**Combo Items**

Combo items (restaurant POS) involve recursive line creation: a combo parent line spawns multiple combo child lines. The `_process_lines()` method handles this with a recursive call for `combo_line_ids`. For large combo menus, this recursive processing is O(n) in the number of combo items and is generally fast.

**`_validate_session()` Single Transaction**

The entire session validation (account move creation + reconciliation + cash statements) runs in a single database transaction via `with_cr()`. This ensures atomicity — if any step fails (e.g., account reconciliation fails due to missing account), the entire close operation rolls back.

### 4.2 Security Considerations

**Record Rules**

The `pos.order` model has a record rule restricting access:
- Users with `pos_order` group can read/write their own orders (where `user_id = uid`)
- Users with `pos_order_manager` group can read/write all orders
- Portal users can read their own orders via `portal.mixin`

**Session Access Control**

Only the user who opened a session (stored in `user_id`) can close it. Other cashiers can add orders to the session, but only the session owner or a manager can invoke `try_close()`.

**Preventing Price Manipulation**

`restrict_price_control` on `pos.config` requires manager authentication before price overrides. However, this only applies to manual price changes in the UI — a determined attacker with database access could still manipulate `price_unit` before `sync_from_ui()`. The `price_type` field distinguishes `manual` (cashier-entered) from `automatic` (pricelist-derived) prices, but there is no server-side enforcement that `manual` prices must be within a range.

**SQL Injection Risk**

All database operations use the Odoo ORM (`search()`, `create()`, `write()`, `unlink()`). No raw SQL with string interpolation is used in the POS models. All domain filters use tuple syntax `('field', 'operator', value)` which the ORM sanitizes.

**XSS in Product Notes**

`full_product_name` and `public_description` (on `product.template`) are rendered in the POS web client. The `html_editor` dependency provides sanitized HTML output, but raw HTML in these fields could pose a risk if not properly escaped by the frontend.

**Payment Card Data**

`pos.payment` stores `card_no` (last 4 digits only), `cardholder_name`, and terminal-specific fields. This is PCI-DSS relevant data. Odoo's POS module does not store full card numbers — it only stores what the payment terminal provides. Implementations should ensure the terminal (not Odoo) handles full card data and tokenization.

**CSV Injection**

The `export` functionality on POS orders/lines could be vulnerable to CSV injection if user-provided data (product names, partner names) contains formula prefixes (`=`, `+`, `-`). Odoo's export utilities generally escape these, but custom exports should be reviewed.

**Incomplete Session Close (Balancing Account)**

When the account move fails to balance (e.g., due to a deleted account, or a tax configuration change mid-session), Odoo rolls back the entire close transaction and presents a wizard (`pos.close.session.wizard`). The user can force-close the session by specifying a balancing account that absorbs the discrepancy. This is logged as an accounting error and should be reviewed by an accountant.

**Payment Method Write Protection**

`pos.payment.method._is_write_forbidden()` blocks writes to payment methods that have open sessions — except for the `sequence` field. This prevents accidentally changing a cash drawer journal mid-session, which would corrupt the cash reconciliation.

**Record Rule: `rule_pos_bank_statement_line_user`**

Only POS users can read `account.bank.statement.line` records that have a `pos_session_id` set. Lines without a session (e.g., manually created from accounting) remain hidden to POS users but visible to accountants.

**Invoice Access Rule: `rule_invoice_pos_user`**

Users with `group_pos_user` can read `account.move` records that have `pos_order_ids` set. This grants invoice read access to POS cashiers for orders they created, without giving full accounting access.

### 4.3 Odoo 18 → 19 Changes

**`pos.load.mixin` Standardization**

Odoo 18 formalized the `pos.load.mixin` pattern. In earlier versions, POS models had custom `_load_pos_data` methods. Odoo 19 uses `_load_pos_data_domain` and `_load_pos_data_fields` as the standard interface, making it easier to add custom models to the POS without inheriting from a specific base class.

**Fiscal Position Loading**

Odoo 19 added `_load_pos_data_domain` on `account.fiscal.position` to include both preset fiscal positions and those derived from partner `property_account_position_id`. This ensures fiscal positions are available offline in the POS frontend.

**Cash Rounding Enhancement**

The `cash_rounding` field and `rounding_method` on `pos.config` were enhanced. Odoo 19 supports `add_invoice_line` rounding strategy (adds a rounding line to the invoice rather than adjusting individual line prices).

**Combo Items**

The `combo_parent_id`, `combo_line_ids`, and `combo_item_id` fields on `pos.order.line` represent a significant new feature in Odoo 18/19 for restaurant POS, replacing the older "product set" approach.

**Kitchen Order Printing**

The `ACTION_SEND_TO_KITCHEN` notification via `pos.bus.mixin` replaced older print-via-proxy approaches, enabling real-time kitchen display updates.

**UUID for Order/Payment Sync**

The `uuid` field on `pos.order`, `pos.order.line`, and `pos.payment` was formalized in Odoo 18+ to support offline-first architecture. Prior versions relied on `id` which is not known until after server-side creation.

**Payment Method Type Selection**

`payment_method_type` with values `none`, `terminal`, `qr_code` replaced the older `use_payment_terminal` boolean. This allows more granular configuration of payment integration methods.

**Session-State Accounting Flow**

Odoo 19 refined the session-close accounting with `_accumulate_amounts()` creating grouped entries rather than one entry per payment, significantly reducing the number of `account.move.line` records for high-volume sessions.

### 4.4 Session Rescue Mode (`rescue`)

The `rescue` boolean field on `pos.session` is set when Odoo detects "orphan" orders — orders in the SQLite frontend database that were never successfully synced to the server (e.g., due to network failure mid-sync, server crash, or browser close). When the POS is reopened, Odoo automatically creates a `rescue=True` session to absorb these orders.

Key behaviors:
- Rescue sessions bypass the `_check_pos_config` constraint that prevents multiple open sessions per config.
- Rescue sessions are excluded from `current_session_id` / `current_session_state` computation (filtered with `not s.rescue`).
- The `_cannot_close_session()` check does not apply to rescue sessions — only `close_session_from_ui()` with a special code path handles their closure.
- At rescue session close (`action_pos_session_closing_control`), the cash closing balance is auto-computed from order payments + opening balance (the physical count step is bypassed).
- The rescue session carries the `rescue=True` flag which propagates to orders created within it.

**Orphan order recovery flow:**
1. Frontend creates orders with local UUIDs in SQLite.
2. Network failure prevents `sync_from_ui()` from being called.
3. User reopens POS — frontend detects unsynced orders.
4. Backend creates a `rescue=True` session for the config.
5. Frontend reconnects and `sync_from_ui()` pushes the orphan orders into the rescue session.
6. Rescue session is closed via `close_session_from_ui()`.

### 4.5 Stock Picking and `update_stock_at_closing`

The `update_stock_at_closing` boolean on `pos.session` controls when stock quants are updated:

| Setting | `update_stock_at_closing` | Behavior |
|---------|--------------------------|----------|
| **Real-time** (default) | `False` | `_create_order_picking()` called immediately when order is finalized (`_process_saved_order`). Stock is decremented at time of sale. |
| **At session close** | `True` | `_create_picking_at_end_of_session()` called in `_validate_session()`. All orders' pickings are batched into fewer database operations. |

This is determined at session creation from `pos_config.company_id.point_of_sale_update_stock_quantities`:
```python
update_stock_at_closing = pos_config.company_id.point_of_sale_update_stock_quantities == "closing"
```

**When is real-time picking forced regardless of this setting?**
- When `company_id.anglo_saxon_accounting` is True AND `to_invoice` is True: Stock moves must be created at order time to support COGS journal entries that reference picking valuation.

**`_create_picking_at_end_of_session()`:**
- Groups all non-cancelled, non-draft orders from the session.
- Calls `_launch_stock_rule_from_pos_order_lines()` for each order's lines (which creates `stock.picking` + `stock.move` via procurement).
- Uses `stock.warehouse` route and `picking_type_id` from config.

### 4.6 Account Move (Session Close) Deep Dive

The session's `_create_account_move()` is the most complex method in the POS module. It runs as a single atomic transaction at session close.

#### `_accumulate_amounts()` — Grouping Logic

This method walks all order lines and payment lines and groups them into `AmountCounter` namedtuples keyed by `(account_id, tax_ids, base_account_id, for_invoice)`. The accumulation categories:

1. **Sales lines** — Revenue credit entries. Each `pos.order.line` maps to a revenue account (from product's `property_account_income_id` or category default). Tax amounts are accumulated separately under the tax account.

2. **Tax lines** — Each unique `account.tax` in an order creates a credit entry to its `cash_basis_transition_account_id` (or the company default tax receivable/payable account).

3. **Payment lines** — Debit entries to the payment method's bank/receivable account. Cash payments: debit the cash journal's `default_account_id`. Bank payments: debit the `outstanding_account_id` on the payment method. When `split_transactions` is enabled, each payment gets its own receivable debit line keyed to the customer's account.

4. **Cash change (is_change=True payments)** — For cash payments where `is_change=True` (customer was owed change), the amount is debited to the cash account. This is paired with the originating payment in `_create_payment_moves()`.

5. **Stock variation (Anglo-Saxon)** — When `inventory_valuation == 'real_time'` and `update_stock_at_closing == True`, COGS (debit) and Inventory (credit) entries are created from the picking's valued moves.

#### Entry Balancing

The session account move MUST balance (debits == credits). The closing balance is checked via `move_id._check_balanced()` before posting. If unbalanced, the entire transaction rolls back and `_close_session_action()` returns a wizard asking the user to force-close with a balancing account.

#### `_reconcile_account_move_lines()`

After posting, receivable lines in the session move are reconciled:
- For non-split-transaction payments: the aggregated receivable line is reconciled with individual payment move lines.
- For split-transaction payments: each customer receivable line is reconciled with their corresponding payment move line.
- Uses `account.move.line.reconcile()` — creates partial reconciliations if amounts don't match exactly.

### 4.7 `pos.session` → `account.bank.statement` Cash Flow

Each `pos.session` creates or uses existing `account.bank.statement` records for its cash payment method:

- `cash_register_balance_start`: Set from the previous session's `cash_register_balance_end_real` when `cash_control` is enabled. Defaults to 0.
- `cash_register_balance_end_real`: Set by the cashier when counting the drawer at session close.
- `cash_register_balance_end` (theoretical): Computed as `cash_register_balance_start + SUM(statement_line_ids.amount) + SUM(cash_payment.amount)`.
- `cash_register_difference`: `cash_register_balance_end_real - cash_register_balance_end`.

The `account.bank.statement.line` records created during the session represent manual cash insertions/withdrawals (cash in/out operations done via the POS interface). When the session closes with a difference, `_post_statement_difference()` creates a statement line for the profit or loss amount, referencing the `loss_account_id` or `profit_account_id` from the cash journal.

Only ONE cash journal is supported per POS session (`cash_journal_id` is computed from `payment_method_ids.filtered('is_cash_count')[:1]`).

### 4.8 `pos.payment._create_payment_moves()` — Per-Payment Accounting

When an invoiced order's session is closed, `_generate_pos_order_invoice()` calls `pos.payment._create_payment_moves(is_reverse=...)` for each payment:

- `is_reverse=False`: Called for normal orders. Creates a debit to the receivable account and credit to the outstanding account.
- `is_reverse=True`: Called for refunds (reversed receivable). The receivable account used depends on whether `split_transactions` is enabled and whether it's a customer-specific receivable or the POS default receivable.

The `_get_receivable_lines_for_invoice_reconciliation()` heuristic on `pos.payment` determines which account move lines should be matched against the invoice receivable line:
- Positive amount payment + negative balance receivable line = match (payment reduces what customer owes)
- Negative amount payment (refund) + positive balance receivable line = match

### 4.9 `pos.preset` — Appointment/Booking Presets

`pos.preset` defines reusable order templates for appointment-style POS (e.g., `pos_appointment` module). Key fields:

| Field | Purpose |
|-------|---------|
| `pricelist_id` | Default pricelist for orders with this preset |
| `fiscal_position_id` | Auto-apply a fiscal position |
| `identification` | `'none'` / `'address'` / `'name'` — how much customer info to collect |
| `is_return` | If True, all quantities are negative (return mode) |
| `use_timing` | Enable appointment time slots |
| `resource_calendar_id` | Working hours for slot availability |
| `slots_per_interval` | Max orders per time interval |
| `interval_time` | Interval length in minutes |

The `_compute_slots_usage()` method queries `pos.order` records with matching `preset_id`, `preset_time`, and `state in ['draft', 'paid']` to compute occupancy per time slot. Orders with `preset_time` in the future are excluded from session close (their `session_id` is cleared before closing).

### 4.10 Onboarding Scenarios and Demo Data

`pos.config` provides three onboarding scenarios (loaded via `load_onboarding_*` methods):
1. **Furniture Shop** (`pos_config_main`) — Full demo with products, categories, existing orders
2. **Clothes Shop** (`pos_config_clothes`) — Category-restricted config with apparel products
3. **Bakery Shop** (`pos_config_bakery`) — Food/restaurant-style config

Each scenario automatically creates:
- An `account.journal` (type `sale` or `cash`)
- Cash + Bank + Customer Account payment methods
- Product categories and demo products
- Sets `limit_categories` + `iface_available_categ_ids`

### 4.11 Key Internal Algorithms

**Fiscal Position Auto-Detection (`_infer_fiscal_position`)**

When no fiscal position is explicitly set, the system infers one based on partner's country:
1. Search `account.fiscal.position` records where `country_id` matches partner's country
2. If none found, search for positions with `country_id = NULL` (country-wide positions)
3. Return the first match, or `False` if none

**Tax Computation with Fiscal Position**

`_prepare_order_line()` calls `_get_taxes()` which applies the fiscal position's `tax_ids` mapping to the product's default `taxes_id` field. The mapped taxes replace the original taxes — this is an override, not an addition. If the fiscal position has no mapping for a particular tax, that tax is removed.

**Cash Rounding Logic**

When `cash_rounding` is enabled and the rounding method's `rounding` is non-zero:
- `amount_total` is rounded to the nearest `rounding` value
- The difference between the unrounded total and rounded total is stored as an additional rounding line
- The rounding line uses the rounding method's `account_id` for accounting

**Combo Line Processing**

When processing an order line with a `combo_item_id`:
1. The combo item determines which products (sub-products) are included
2. For each sub-product, a child `pos.order.line` is created with:
   - `combo_parent_id` set to the parent line
   - `combo_item_id` set to the item that generated it
   - `qty` = parent `qty` × item `quantity`
3. The parent's `price_unit` is distributed across children (or children inherit zero price if combo price is all-inclusive)

---

## Model Relationship Diagram

```
pos.config ──────────────── pos.session
    │  1:N                      │  1:N
    │                           │
    ├─── pos.payment.method ─────┤
    │         │                 │
    │         └── pos.payment ──┤── pos.order
    │                   │       │       │
    ├─── product.pricelist       │       ├─── pos.order.line
    │                           │       │        ├── pos.product (combo)
    │                           │       │        └── pos.pack.operation.lot
    │                           │       │
    │                           │       ├─── account.move (invoice)
    │                           │       │
    │                           │       └─── stock.picking ── stock.move
    │
    ├─── pos.printer
    │
    ├─── pos.category (hierarchical)
    │
    └─── pos.bill (denominations)

pos.session ──────────────── account.move (session close, 1:1)
                                 │
                                 └── account.move.line ── account.account
                                          │
                                          └── Reconciliation (via partner_id)

pos.order ──────────────────── res.partner (customer)
pos.payment ────────────────── res.partner (customer, via split_transactions)
```

**Offline Queue Exhaustion**

When the POS operates offline for extended periods, the SQLite database accumulates orders. On reconnect, `sync_from_ui()` is called with potentially hundreds of orders. The method processes them sequentially in a single RPC call. Very large queues (>1000 orders) may hit RPC timeout limits. The recommendation is to sync more frequently or use background sync.

**Tip Product (`product_product_tip`)**

When `iface_tipproduct` is enabled, the POS creates a tip line as a separate `pos.order.line` with `is_tip_line=True` after the order is marked paid. The tip amount is added to `amount_paid` but does not affect `amount_total`. Tip lines use the product defined in `config_id.tip_product_id` (default: `point_of_sale.product_product_tip`, code `TIPS`).

**Multi-Terminal Shared Orders**

When `trusted_config_ids` is configured, multiple POS terminals share the same session context. Orders from one terminal appear on another via `pos.bus.mixin` notifications. The `_notify('SYNCHRONISATION', ...)` call broadcasts updated order state to all trusted configs. This requires matching `currency_id` — enforced by `_check_trusted_config_ids_currency()`.

**Fiscal Position on Invoice vs. Session Close**

Fiscal positions affect invoice entries (created at `action_pos_order_invoice()`) and session accounting entries (created at `_validate_session()`). Importantly, these are TWO separate accounting entries: the invoice is a customer receivable, while the session close is a summarized sales entry. The session close uses the fiscal position's account mappings but not its tax mappings (taxes are handled per order line when the invoice is created).

---

## Security — Access Control (`ir.model.access.csv`)

The `security/ir.model.access.csv` file defines per-model access rights for the three POS groups.

| Model | `group_pos_user` | `group_pos_manager` |
|-------|----------------|-------------------|
| `pos.category` | read | read |
| `pos.config` | read | read/write |
| `pos.session` | read | read/write |
| `pos.order` | read/write own | read/write all |
| `pos.order.line` | read/write own | read/write all |
| `pos.payment` | read/write own orders | read/write all |
| `pos.payment.method` | read | read |
| `pos.bill` | read | read/write |
| `pos.printer` | read | read/write |
| `pos.note` | read | read/write |
| `pos.preset` | read | read/write |

Record rules supplement the CSV:
- `rule_pos_multi_company`: All POS models scoped to `company_id in company_ids`
- `rule_pos_bank_statement_line_user`: Statement lines with `pos_session_id` are visible to POS users
- `rule_invoice_pos_user`: Invoices linked to POS orders are readable by POS users
- `rule_invoice_line_pos_user`: Invoice lines from POS invoices are readable by POS users

### PosConfig `_forbidden_change_fields`

When a session is open, these fields cannot be modified: `module_pos_restaurant`, `payment_method_ids`, `active`. Attempting to change them raises `UserError: Unable to modify this PoS Configuration because you can't modify ... while a session is open.`

---

## Related Documentation

- [Core/API](API.md) — ORM decorators `@api.model`, `@api.depends`, `@api.constrains`
- [Modules/Account](Account.md) — `account.move`, fiscal positions, tax computation
- [Modules/Stock](Stock.md) — `stock.picking`, `stock.move`, `stock.quant` (Anglo-Saxon valuation)
- [Modules/Product](Product.md) — `product.product`, `product.pricelist`, `uom.uom`
- [Modules/Sale](Sale.md) — Order workflow, `sale.order` vs `pos.order` comparison
- [Patterns/Workflow Patterns](Workflow Patterns.md) — State machine patterns (applicable to order/session states)
- [Patterns/Security Patterns](Security Patterns.md) — ACL, record rules, ir.rule
