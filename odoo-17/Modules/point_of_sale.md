---
tags: [odoo, odoo17, module, point_of_sale, pos]
research_depth: medium
source: addons/point_of_sale/models/
---

# Point of Sale Module — Deep Reference

**Source:** `addons/point_of_sale/models/`

## Overview

Full retail POS system: orders, sessions, payments, cash management, invoicing, and stock picking. Differs from `sale.order` in that orders are created immediately from the POS interface and journal entries are created on session close rather than on order confirmation. Odoo 17 POS is browser-based and communicates with the server via JSON-RPC.

---

## Key Models

### pos.order (`pos_order.py`)

Inherits `portal.mixin` — customers can view receipts via portal. Created directly from the POS frontend UI. When the parent session is closed, all orders in that session are aggregated into a single `account.move` (sales journal entry) rather than per-order.

**State Machine:**
```
draft → paid → done → invoiced
       ↘ cancel
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Order reference, auto-generated `/` |
| `date_order` | Datetime | Order date, indexed |
| `user_id` | Many2one | Responsible cashier (defaults to uid) |
| `partner_id` | Many2one | Customer (optional, nullable) |
| `company_id` | Many2one | Company (required, readonly) |
| `pricelist_id` | Many2one | Pricelist used |
| `currency_id` | Many2one | Related to `config_id.currency_id` |
| `currency_rate` | Float | Order currency vs company rate |
| `session_id` | Many2one | POS session, domain `[('state','=','opened')]` |
| `config_id` | Many2one | POS config (related to session.config_id, stored) |
| `sale_journal` | Many2one | Related `session_id.config_id.journal_id` |
| `lines` | One2many | `pos.order.line` children |
| `payment_ids` | One2many | `pos.payment` records |
| `amount_tax` | Float | Tax amount (readonly) |
| `amount_total` | Float | Grand total (readonly) |
| `amount_paid` | Float | Sum of payments |
| `amount_return` | Float | Change returned (readonly) |
| `margin` | Monetary | Computed profit margin |
| `margin_percent` | Float | Margin as percentage |
| `state` | Selection | `draft / cancel / paid / done / invoiced` |
| `account_move` | Many2one | Invoice (`account.move`) |
| `picking_ids` | One2many | Stock pickings for delivery orders |
| `procurement_group_id` | Many2one | Group for chained pickings |
| `fiscal_position_id` | Many2one | Fiscal mapping |
| `to_invoice` | Boolean | Flag to generate invoice |
| `shipping_date` | Date | Scheduled delivery |
| `is_tipped` | Boolean | Tip already given |
| `tip_amount` | Float | Tip value |
| `pos_reference` | Char | Receipt number (indexed) |
| `nb_print` | Integer | Print count |
| `note` | Text | Internal notes |
| `is_invoiced` | Boolean | Computed from `account_move` |
| `is_refunded` | Boolean | Has refund orders |
| `refunded_order_ids` | Many2many | Linked refund orders |
| `refund_orders_count` | Integer | Count of refunds |
| `is_total_cost_computed` | Boolean | Margin cost fully computed |
| `last_order_preparation_change` | Char | Last printed prep state |
| `ticket_code` | Char | Unique ticket code for order lookup |
| `tracking_number` | Char | Computed tracking (session_id % 10 * 100 + seq % 100) |

**Key Methods:**

- `_process_order(order, draft, existing_order)` — Main entry point from POS frontend. Creates or updates `pos.order` + lines + payments in a single transaction. Handles rescue session for orders belonging to a closed session.
- `_get_valid_session(order)` — If the order's session is closed, reuses or creates a rescue session (`rescue=True`).
- `_process_payment_lines(pos_order, order, pos_session, draft)` — Creates `pos.payment` records from UI data. If `amount_return > 0`, creates a negative cash payment as change.
- `_process_saved_order(draft)` — After persisting, calls `action_pos_order_paid`, creates pickings, computes margin.
- `action_pos_order_paid()` — Sets state to `paid`.
- `_create_order_picking()` — Creates `stock.picking` for `ship_later` orders.
- `_generate_pos_order_invoice()` — Creates `account.move` invoice from the order.
- `_compute_margin()` — Real-time margin using Anglo-Saxon valuation from pickings.
- `_prepare_invoice_lines()` — Converts order lines to `Command.create` invoice line dicts using tax-base values.
- `_link_combo_items(order_vals)` — Links child combo lines to their parent via `combo_parent_id`.

**Tax Computation:**
- `_amount_line_tax(line, fiscal_position_id)` — Applies fiscal position to taxes, calculates price with discount, calls `tax_ids.compute_all()`.

---

### pos.session (`pos_session.py`)

Inherits `mail.thread` + `mail.activity.mixin`. Cash session that groups all POS operations for a single accounting entry. Only one non-rescue, non-closed session allowed per config at a time.

**State Machine:**
```
opening_control → opened → closing_control → closed
```

- `opening_control` — Session created, waiting for cashier to confirm opening (cash counting if cash control enabled).
- `opened` — Active sales can be recorded.
- `closing_control` — Manager initiating close; if cash control is on, triggers the cash-count wizard.
- `closed` — Journal entry posted to `move_id`, all non-invoiced orders set to `done`.

| Field | Type | Description |
|-------|------|-------------|
| `config_id` | Many2one | POS config (required, indexed) |
| `name` | Char | Session identifier from `ir.sequence` (unique SQL constraint) |
| `access_token` | Char | Security token for UI |
| `user_id` | Many2one | Opened-by user (default: uid) |
| `currency_id` | Many2one | Related to `config_id.currency_id` |
| `start_at` | Datetime | Opening timestamp |
| `stop_at` | Datetime | Closing timestamp |
| `state` | Selection | Session state |
| `sequence_number` | Integer | Per-session order counter |
| `login_number` | Integer | Resume counter (increments each login) |
| `rescue` | Boolean | Auto-generated rescue session flag |
| `order_ids` | One2many | All orders in this session |
| `order_count` | Integer | Computed order count |
| `payment_method_ids` | Many2many | Related to `config_id.payment_method_ids` |
| `cash_journal_id` | Many2one | First cash-type payment method's journal |
| `cash_control` | Boolean | True if any payment method has `is_cash_count` |
| `cash_register_balance_start` | Monetary | Opening cash balance |
| `cash_register_balance_end_real` | Monetary | Closing real count |
| `cash_register_balance_end` | Monetary | Theoretical closing balance |
| `cash_register_difference` | Monetary | Real minus theoretical |
| `cash_register_total_entry_encoding` | Monetary | Total cash in/out |
| `cash_real_transaction` | Monetary | Total from statement lines |
| `statement_line_ids` | One2many | `account.bank.statement.line` for cash ops |
| `move_id` | Many2one | Consolidated `account.move` for session |
| `picking_ids` | One2many | Stock pickings |
| `picking_count` | Integer | Number of pickings |
| `failed_pickings` | Boolean | Any picking not `done` |
| `update_stock_at_closing` | Boolean | Stock moves at session close |
| `total_payments_amount` | Float | Sum of all payments |
| `opening_notes` / `closing_notes` | Text | Session notes |
| `bank_payment_ids` | One2many | Aggregated bank `account.payment` records |

**Key Methods:**

- `create(vals_list)` — Auto-assigns sequence name from `pos.session` code, sets `update_stock_at_closing` from company setting (`point_of_sale_update_stock_quantities = closing`), then calls `action_pos_session_open()` automatically.
- `action_pos_session_open()` — Sets `start_at`, and if cash control, pulls previous session's closing balance as opening balance.
- `action_pos_session_closing_control(...)` — Transitions to `closing_control`. Validates no draft orders exist. If no cash control, immediately calls `action_pos_session_close`.
- `_validate_session(...)` / `action_pos_session_close(...)` — Core closing logic:
  1. Checks all invoices are posted via `_check_invoices_are_posted()`
  2. Runs stock picking creation if `update_stock_at_closing`
  3. Calls `_create_account_move()` to produce consolidated journal entry
  4. Posts the move and reconciles lines via `_reconcile_account_move_lines()`
  5. Sets uninvoiced orders to `done`
  6. Posts cash over/short via `_post_statement_difference()` (profit/loss accounts)
- `_post_statement_difference(amount, is_opening)` — Creates an `account.bank.statement.line` for cash variance using the cash journal's profit/loss accounts.
- `_check_start_date()` — Prevents session start before company lock date.
- `_check_pos_config()` — Ensures only one non-rescue, non-closed session per config.
- `login()` — Increments `login_number` and returns it.

---

### pos.config (`pos_config.py`)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | POS name (internal identification) |
| `company_id` | Many2one | Company (required) |
| `journal_id` | Many2one | POS sales journal (type `sale`/`general`, default code `POSS`) |
| `invoice_journal_id` | Many2one | Invoice journal (type `sale`) |
| `currency_id` | Many2one | Computed from `journal_id.currency_id` |
| `picking_type_id` | Many2one | Stock operation type (outgoing) |
| `warehouse_id` | Many2one | Default warehouse |
| `payment_method_ids` | Many2many | Available payment methods |
| `pricelist_id` | Many2one | Default pricelist |
| `available_pricelist_ids` | Many2many | Pricelists accessible in POS |
| `use_pricelist` | Boolean | Enable pricelist selection |
| `sequence_id` | Many2one | Order reference sequence |
| `sequence_line_id` | Many2one | Order line reference sequence |
| `current_session_id` | Many2one | Currently open session (computed) |
| `current_session_state` | Char | State of current session |
| `has_active_session` | Boolean | Computed |
| `session_ids` | One2many | All sessions for this config |
| `cash_control` | Boolean | Advanced cash control (computed from payment methods) |
| `amount_authorized_diff` | Float | Max cash difference for non-managers |
| `rounding_method` | Many2one | Cash rounding method |
| `cash_rounding` / `only_round_cash_method` | Boolean | Cash rounding settings |
| `tip_product_id` | Many2one | Product for tips |
| `fiscal_position_ids` | Many2many | Available fiscal positions |
| `default_fiscal_position_id` | Many2one | Default fiscal position |
| `module_pos_restaurant` | Boolean | Restaurant mode flag |
| `module_pos_discount` | Boolean | Global discounts flag |
| `module_pos_mercury` | Boolean | Integrated card payments |
| `module_pos_hr` | Boolean | Employee login screen |
| `group_pos_manager_id` / `group_pos_user_id` | Many2one | Security groups |
| `restrict_price_control` | Boolean | Managers-only price edit |
| `is_margins_costs_accessible_to_every_user` | Boolean | Show costs to all users |
| `manual_discount` | Boolean | Enable line discounts |
| `ship_later` | Boolean | Allow delayed delivery |
| `route_id` | Many2one | Delivery route |
| `picking_policy` | Selection | `direct` / `one` |
| `iface_*` | Boolean | Hardware flags: `cashdrawer`, `electronic_scale`, `customer_facing_display`, `print_via_proxy`, `scan_via_proxy`, `big_scrollbars`, `print_auto`, `tipproduct` |
| `receipt_header` / `receipt_footer` | Text | Custom receipt text |
| `trusted_config_ids` | Many2many | Trusted POS configs (cross-location) |
| `auto_validate_terminal_payment` | Boolean | Auto-confirm card payments |
| `uuid` | Char | Global unique ID for conflict prevention |

---

### pos.payment (`pos_payment.py`)

Records a single payment on a POS order.

| Field | Type | Description |
|-------|------|-------------|
| `pos_order_id` | Many2one | Parent order (required, indexed) |
| `amount` | Monetary | Payment amount |
| `payment_method_id` | Many2one | Payment method used |
| `payment_date` | Datetime | Payment timestamp |
| `currency_id` | Many2one | Related to order's currency |
| `currency_rate` | Float | Conversion rate |
| `partner_id` | Many2one | Customer (related to order) |
| `session_id` | Many2one | Session (stored, indexed) |
| `company_id` | Many2one | Company |
| `card_type` | Char | Card brand (Visa, Mastercard...) |
| `cardholder_name` | Char | Name on card |
| `transaction_id` | Char | Terminal transaction ref |
| `payment_status` | Char | Status from terminal |
| `ticket` | Char | Terminal receipt info |
| `is_change` | Boolean | True if this is a change payment (negative amount) |
| `account_move_id` | Many2one | Entry created at session close |

**Key Methods:**

- `_create_payment_moves(is_reverse=False)` — Called at session close. Creates `account.move` entries for each non-cash, non-pay-later payment. For `split_transactions` payments, creates per-customer receivable lines. Sets `account_move_id` on the payment. Handles reverse payments (refunds) with correct receivable account selection. Returns moves with credit line IDs for reconciliation.
- `_export_for_ui(payment)` — Serializes payment for POS frontend (excludes id, name, partner_id).
- `export_for_ui()` — Maps `_export_for_ui` across a recordset.

**Constraint:** `_check_payment_method_id()` — Validates that the payment method is allowed in the session's config.

---

### pos.payment.method (`pos_payment_method.py`)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Display name in POS UI |
| `journal_id` | Many2one | Cash or bank journal |
| `type` | Selection | `cash` / `bank` / `pay_later` (computed from journal) |
| `is_cash_count` | Boolean | True if cash type |
| `split_transactions` | Boolean | Force customer selection (customer-level receivable) |
| `receivable_account_id` | Many2one | Override company receivable |
| `outstanding_account_id` | Many2one | Outstanding account for bank |
| `use_payment_terminal` | Selection | Terminal integration (e.g., Vantiv, Adyen) |
| `config_ids` | Many2many | POS configs using this method |
| `open_session_ids` | Many2many | Currently open sessions (computed) |
| `image` | Image | Icon (max 50x50px) |

**Write Protection:** `_is_write_forbidden()` — Prevents modification of any field except `sequence` while open sessions exist using this method.

---

## POS Session → Accounting Flow

### On Session Close (`_create_account_move`)

1. All `paid` orders in session aggregated into one or more `account.move` entries.
2. Per order: sales credit entry for `amount_total`, tax credit entry for `amount_tax`.
3. Per payment method:
   - **Cash**: `account.bank.statement.line` created on the cash journal (no move line until statement reconciled).
   - **Bank**: `account.move` with debit to receivable/outstanding account.
   - **Pay Later**: skipped at session close (no payment move).
   - **Split transaction**: per-customer receivable entries.
4. Cash over/short posted as statement lines to profit/loss account.
5. `pos.session.move_id` links the consolidated journal entry.
6. Uninvoiced orders state → `done`.

### Rescue Sessions

If the POS frontend submits an order to a session that has already been closed, Odoo automatically creates a rescue session (`rescue=True`) for that config. Rescue sessions bypass opening cash control and use the previous session's closing balance as their opening balance. A rescue session is preferred over adding to an existing rescue session.

---

## POS → Sale Order Comparison

| Aspect | `pos.order` | `sale.order` |
|--------|-------------|--------------|
| Creation | Immediate from POS UI | Manual or e-commerce |
| Payment | `pos.payment`, cash immediate | `account.payment` after invoice |
| Accounting | On session close | On invoice confirmation |
| Picking | Optional (`ship_later`) | On order confirmation |
| State | draft → paid → done → invoiced | draft → sale → done |
| Margin | Real-time Anglo-Saxon | On order confirmation |
| Customer Portal | Inherits `portal.mixin` | No portal mixin by default |

---

## See Also

- [Modules/account](odoo-18/Modules/account.md) — `account.move` journal entries
- [Modules/stock](odoo-18/Modules/stock.md) — `stock.picking` for delivery
- [Modules/sale](odoo-18/Modules/sale.md) — comparison with `sale.order`
- [Modules/payment](odoo-18/Modules/payment.md) — payment processing