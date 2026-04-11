# Point of Sale Module (point_of_sale)

## Overview

The `point_of_sale` module provides a full-featured Point of Sale (POS) system for retail and hospitality environments. It manages POS configurations, active sessions, orders, payments, and integrates with inventory, accounting, and invoicing.

## Key Models

### pos.config

The POS configuration model defines the settings for a Point of Sale terminal.

**Fields:**
- `name`: Char - Internal POS identification
- `company_id`: Many2one - Company owning this POS
- `journal_id`: Many2one - Accounting journal for session entries and invoice payments
- `invoice_journal_id`: Many2one - Journal for creating invoices
- `currency_id`: Many2one - Currency (computed from company)
- `pricelist_id`: Many2one - Default pricelist for the POS
- `available_pricelist_ids`: Many2many - Pricelists available in this POS
- `payment_method_ids`: Many2many - Payment methods available
- `picking_type_id`: Many2one - Stock operation type (outgoing delivery)
- `sequence_id`: Many2one - Order reference sequence
- `sequence_line_id`: Many2one - Order line reference sequence
- `session_ids`: One2many - All sessions for this POS
- `current_session_id`: Many2one - Currently active session (computed)
- `iface_cashdrawer`, `iface_electronic_scale`, `iface_print_via_proxy`, `iface_scan_via_proxy`: Boolean - Hardware interface flags
- `iface_print_auto`, `iface_print_skip_screen`: Boolean - Receipt printing behavior
- `iface_tax_included`: Selection - Tax display (subtotal/total)
- `iface_available_categ_ids`: Many2many - Product categories available in this POS
- `customer_display_type`: Selection - Customer-facing display (none/local/remote/proxy)
- `restrict_price_control`: Boolean - Only managers can modify prices
- `is_margins_costs_accessible_to_every_user`: Boolean - Margin/cost visibility
- `cash_control`: Boolean - Advanced cash control (computed)
- `set_maximum_difference`: Boolean - Maximum allowed cash difference at closing
- `receipt_header`, `receipt_footer`: Text - Custom receipt text
- `basic_receipt`: Boolean - Print receipt without prices
- `is_order_printer`: Boolean - Enable order printer for kitchen/bar
- `printer_ids`: Many2many - Kitchen/bar printers
- `uuid`: Char - Global unique identifier for the POS config
- `active`: Boolean - Active status
- `group_pos_manager_id`: Many2one - POS manager group
- `limit_categories`, `iface_start_category_id`: Category restriction settings
- `order_edit_tracking`: Boolean - Track order edits during session

**Key Methods:**

- `_default_warehouse_id()`: Returns the default warehouse from the company's available warehouses
- `_default_picking_type_id()`: Returns the POS operation type (outgoing) from the default warehouse
- `_default_sale_journal()`: Ensures a company account journal exists
- `_default_payment_methods()`: Returns compatible payment methods (non-cash plus one available cash method)
- `_get_group_pos_manager()`, `_get_group_pos_user()`: Return the respective security groups
- `_get_available_pricelists()`: Returns pricelists available for this config (considers company)
- `_get_available_categories()`: Returns all available POS categories (including descendants if restricted)
- `_get_special_products()`: Returns tip and custom products (e.g., internal use items)
- `_pos_has_valid_product()`: Checks if there is at least one sellable product available
- `_notify(event_type, payload)`: Sends real-time notification to connected POS clients (via `pos.bus.mixin`)
- `use_pos_category()`: Returns True if category restriction is enabled

**Default Defaults:**
- Warehouse: first warehouse for the company
- Picking type: POS type from the default warehouse
- Sale journal: auto-created via `_ensure_company_account_journal()`
- Invoice journal: first sale journal for the company
- Payment methods: non-cash methods + one unassigned cash method; auto-creates if none exist

### pos.session

Represents an active POS session. Sessions are the context within which orders are created and payments are collected.

**Session State Machine:**
```
opening_control -> opened -> closing_control -> closed
```
- `opening_control`: Initial state after `create()`; `action_pos_session_open()` moves to `opened`
- `opened`: Active selling state; `action_pos_session_closing_control()` moves to `closing_control`
- `closing_control`: Cash count in progress; `action_pos_session_close()` (via `_validate_session()`) moves to `closed`
- `closed`: Finalized; session account move posted

**Fields:**
- `name`: Char - Session name (format: `POSName/00001`)
- `config_id`: Many2one - Associated POS configuration
- `user_id`: Many2one - User who opened the session
- `state`: Selection - Session state
- `start_at`: Datetime - Opening timestamp
- `stop_at`: Datetime - Closing timestamp
- `sequence_number`: Integer - Last order sequence number used
- `login_number`: Integer - Login sequence (increments on each user resume)
- `currency_id`: Many2one - Currency (from config)
- `company_id`: Many2one - Company (from config)
- `cash_register_balance_start`: Monetary - Opening cash balance
- `cash_register_balance_end`: Monetary - Theoretical closing balance (computed)
- `cash_register_balance_end_real`: Monetary - Actual counted closing balance
- `cash_register_difference`: Monetary - Difference between counted and theoretical
- `cash_real_transaction`: Monetary - Total cash in/out via statement lines
- `cash_journal_id`: Many2one - Cash journal (computed)
- `cash_control`: Boolean - Whether cash control is enabled (computed)
- `order_ids`: One2many - Orders in this session
- `order_count`: Integer - Number of orders (computed)
- `payment_method_ids`: Many2many - Payment methods (from config)
- `statement_line_ids`: One2many - Cash statements/lines
- `move_id`: Many2one - Account move (journal entry) created at session close
- `picking_ids`: One2many - Stock pickings linked to orders
- `picking_count`, `failed_pickings`: Integer/Boolean - Picking statistics
- `rescue`: Boolean - Whether this is a rescue session (for orphan orders)
- `opening_notes`, `closing_notes`: Text - Notes at open/close
- `update_stock_at_closing`: Boolean - Whether to update stock at session closing
- `bank_payment_ids`: One2many - Aggregated bank payments
- `total_payments_amount`: Float - Sum of all payments (computed)

**Key Methods:**

- `action_pos_session_open()`: Transitions session from `opening_control` to `opened`. Sets opening cash balance from previous session's closing balance if cash control is enabled.
- `action_pos_session_closing_control()`: Transitions to `closing_control`, then immediately to `closed` if no cash control. For rescue sessions with cash control, computes the closing balance.
- `action_pos_session_close()`: Alias that calls `_validate_session()`.
- `_validate_session(balancing_account, amount_to_balance, bank_payment_method_diffs)`: The core closing logic:
  1. Checks no draft orders exist
  2. Checks all invoices are posted
  3. Creates stock pickings at end of session (if `update_stock_at_closing`)
  4. Creates the session account move (journal entry) via `_create_account_move()`
  5. Posts statement differences (cash over/short) via `_post_statement_difference()`
  6. Posts the account move
  7. Sets unpaid orders to `done`
  8. Reconciles move lines
  9. Triggers procurement rules for pickings
  10. Writes `state = 'closed'`
- `_post_statement_difference(amount)`: Creates a bank statement line for cash over/short, using the cash journal's loss or profit account.
- `_close_session_action(amount_to_balance)`: Returns a wizard to force-close a session when the account move is unbalanced.
- `close_session_from_ui(bank_payment_method_diff_pairs)`: Called from the frontend to attempt session close. Returns `{'successful': True}` on success or opens the closing wizard.
- `login()`: Increments `login_number` via an `ir.sequence` and returns the next value.
- `get_session_orders()`: Returns all orders in the session.
- `_get_captured_payments_domain()`: Returns a domain for payments with account move linked (captured/settled).
- `_get_closed_orders()`: Returns all non-cancelled orders in the session.
- `load_data(models_to_load, only_data)`: Loads POS data for the frontend. Returns a dictionary keyed by model name with `data`, `fields`, `relations`, and optionally `error`.
- `_load_pos_data_models(config_id)`: Returns the list of all models to load into the POS frontend (40+ models including product, tax, partner, pricelist, etc.).

**Data Loading via `pos.load.mixin`:**
The session uses `_load_pos_data_domain`, `_load_pos_data_fields`, and `_load_pos_data` to determine what data is sent to the POS frontend for the current session only.

### pos.order

Represents a POS order. Orders go through states: `draft` -> `paid` -> `done` -> `invoiced`.

**Fields:**
- `name`: Char - Order reference (default `/`, set on creation)
- `pos_reference`: Char - Receipt number (from `name`)
- `uuid`: Char - Unique identifier for the order
- `ticket_code`: Char - 5-digit code for portal invoice request
- `tracking_number`: Char - Short order number (computed, 3 digits)
- `date_order`: Datetime - Order date
- `user_id`: Many2one - Employee/cashier who created the order
- `partner_id`: Many2one - Customer (optional)
- `lines`: One2many - Order lines
- `payment_ids`: One2many - Payments
- `amount_subtotal`, `amount_tax`, `amount_total`: Monetary - Totals
- `amount_paid`: Monetary - Total paid so far
- `amount_return`: Monetary - Change due (positive means owed to customer)
- `amount_difference`: Monetary - Difference (used during payment)
- `state`: Selection - `draft`/`cancel`/`paid`/`done`/`invoiced`
- `session_id`: Many2one - Session context
- `config_id`: Many2one - POS configuration (via session)
- `currency_id`: Many2one - Currency (via config)
- `currency_rate`: Float - Currency conversion rate
- `pricelist_id`: Many2one - Applied pricelist
- `fiscal_position_id`: Many2one - Fiscal position
- `company_id`: Many2one - Company
- `account_move`: Many2one - Generated invoice
- `picking_ids`: One2many - Stock pickings
- `picking_count`, `failed_pickings`: Integer/Boolean - Picking statistics
- `procurement_group_id`: Many2one - Procurement group for stock moves
- `to_invoice`: Boolean - Marked for invoicing
- `is_invoiced`: Boolean - Computed from `account_move` state
- `is_tipped`, `tip_amount`: Boolean/Monetary - Tip tracking
- `is_edited`: Boolean - Whether order was modified after payment
- `has_deleted_line`: Boolean - Whether lines were deleted
- `nb_print`: Integer - Print count
- `general_note`: Text - Order-level note
- `refunded_order_id`, `refund_orders_count`: Related refund tracking
- `has_refundable_lines`: Boolean - Whether lines can be refunded
- `shipping_date`: Date - Shipping date for delivery orders
- `margin`, `margin_percent`: Monetary/Float - Profit margin
- `is_total_cost_computed`: Boolean - Whether cost has been computed

**Key Methods:**

- `_process_order(order, existing_order)`: The main entry point for creating/updating orders from the POS frontend.
  - Validates session state; redirects to an open session if the assigned session is closed
  - Handles missing/invalid partner: clears `partner_id` and `to_invoice`
  - Creates new order or updates existing order
  - Calls `_link_combo_items()` to link combo child lines to parent lines
  - Processes payment lines via `_process_payment_lines()`
  - Calls `_process_saved_order()` to trigger post-payment actions
  - **Raises `UserError`** if no open session is available for a closed session's order

- `_process_saved_order(draft)`: Handles post-creation/post-payment logic.
  - If not draft and not cancelled: calls `action_pos_order_paid()`, `_create_order_picking()`, `_compute_total_cost_in_real_time()`
  - If `to_invoice` and state is `paid`: generates invoice via `_generate_pos_order_invoice()`

- `action_pos_order_paid()`: Transitions to `paid` state. Checks that `amount_paid >= amount_total`.

- `_create_order_picking()`: Creates stock picking for deliverable products. Groups by partner/shipping date.

- `_reconcile_payments()`: Reconciles customer payments against the sales journal item.

- `_link_combo_items(combo_child_uuids_by_parent_uuid)`: Links child order lines to their parent combo line using UUID matching.

- `_prepare_combo_line_uuids(order_vals)`: Extracts combo parent-child UUID relationships from order data before creating lines.

- `_generate_pos_order_invoice()`: Creates an `account.move` invoice from the order.

- `_get_valid_session(order)`: Rescue mechanism. If an order arrives for a closed session, finds another open session for the same POS config rather than failing. Logs a warning and falls back to raising `UserError`.

- `_get_pos_anglo_saxon_price_unit(product, partner_id, quantity)`: Computes the Anglo-Saxon (average) cost price for margin calculation.

- `_compute_tracking_number()`: Computes a 3-digit tracking number from `session_id % 100` and `sequence_number % 100`.

**State Flow:**
1. `draft`: Order is being built in the POS interface
2. `paid`: Payment completed (either fully paid or pay-later)
3. `done`: Session closed and order not invoiced (journal entry created)
4. `invoiced`: Invoice was generated from the order

**Edge Cases:**
- Orders from closed sessions are automatically migrated to another open session for the same POS
- Partner-linked payments with `split_transactions=True` generate separate receivable lines per customer
- Combo products: child combo lines are stored separately but linked to their parent line
- Currency conversion: `currency_rate` is stored at order creation time for multi-currency POS

### pos.order.line

Represents a line item within a POS order.

**Fields:**
- `order_id`: Many2one - Parent order
- `product_id`: Many2one - Product
- `qty`: Float - Quantity
- `price_unit`, `price_subtotal`, `price_subtotal_incl`: Monetary - Pricing
- `discount`: Float - Discount percentage
- `tax_ids`: Many2many - Applied taxes
- `tax_ids_after_fiscal_position`: Many2many - Taxes after fiscal position applied
- `pack_lot_ids`: One2many - Lot/serial number selections (for tracked products)
- `combo_line_ids`: One2many - Child lines for combo products
- `combo_parent_id`: Many2one - Parent combo line (if this is a combo child)
- `is_pack_transfer`: Boolean - Whether pack operation lot was transferred
- `customer_note`: Char - Customer-facing line note
- `refunded_qty`: Float - Quantity already refunded
- `full_product_name`: Char - Full name including attribute values
- `uuid`: Char - Unique identifier

**Key Methods:**
- `_get_combo_children()`: Returns all combo child lines (including nested)
- `_prepare_tax_base_line_values()`: Converts order line to tax computation dict (delegates to product's `_prepare_base_line_for_taxes_computation`)

### pos.payment

Records a single payment for a POS order.

**Fields:**
- `pos_order_id`: Many2one - Parent order
- `payment_method_id`: Many2one - Payment method used
- `amount`: Monetary - Payment amount
- `payment_date`: Datetime - When payment was made
- `currency_id`, `currency_rate`: Many2one/Float - Currency info
- `partner_id`: Many2one - Customer
- `session_id`: Many2one - Session (via order)
- `is_change`: Boolean - Whether this is a change payment (cash return)
- `card_type`, `card_brand`, `card_no`, `cardholder_name`: Card details
- `payment_ref_no`, `payment_method_authcode`, `payment_method_issuer_bank`, `payment_method_payment_mode`: Terminal/transaction details
- `transaction_id`: Char - External transaction ID
- `payment_status`: Char - Status from payment provider
- `ticket`: Char - Receipt info from terminal
- `account_move_id`: Many2one - Generated journal entry line
- `uuid`: Char - Unique identifier

**Key Methods:**

- `_create_payment_moves(is_reverse=False)`: Creates `account.move` entries for payments.
  - Skips `pay_later` payments and zero-amount payments
  - Aggregates cash change payments with the payment that generated the change
  - Creates two lines: receivable debit and sales credit
  - For `split_transactions`, generates separate receivable lines per customer
  - Returns the created moves

- `_check_payment_method_id`: Constrain that the payment method must be in the session's allowed payment methods.

- `_check_amount`: Prevent editing payments for posted/invoiced orders.

### pos.payment.method

Defines the payment methods available in a POS (cash, bank card, credit account).

**Payment Method Types:**
- `cash`: Physical cash with cash drawer. Used for `is_cash_count=True` payments.
- `bank`: Bank card, payment terminal, or QR code. Links to a bank journal.
- `pay_later`: Customer account (no immediate payment, e.g., "charge it").

**Fields:**
- `name`: Char - Display name in POS interface
- `journal_id`: Many2one - Account journal (cash or bank type)
- `type`: Selection - Computed from `journal_id.type` or `pay_later`
- `is_cash_count`: Boolean - Whether this is a cash method (computed from `type == 'cash'`)
- `outstanding_account_id`: Many2one - Outstanding account for bank payments
- `receivable_account_id`: Many2one - Receivable account override (for split transactions)
- `split_transactions`: Boolean - Force customer identification and split journal entries per customer
- `use_payment_terminal`: Selection - Terminal integration type
- `payment_method_type`: Selection - Integration: `none`/`terminal`/`qr_code`
- `qr_code_method`: Selection - QR code format
- `default_qr`: Binary - Pre-generated QR code for offline use
- `config_ids`: Many2many - POS configs using this method
- `open_session_ids`: Many2many - Currently open sessions using this method (computed)
- `image`: Image - Icon for the payment button

**Key Methods:**

- `_compute_type()`: Sets `type` based on `journal_id.type`: `cash` for cash journals, `bank` for bank journals, `pay_later` otherwise.
- `_is_write_forbidden(fields)`: Prevents modification of a payment method if any session is currently open using it (except `sequence`).
- `_check_payment_method()`: Validates QR code configuration (requires bank journal with bank account and valid QR method).
- `get_qr_code(amount, free_communication, structured_communication, currency, debtor_partner)`: Generates a QR code for the payment using the configured format and bank account.
- `_force_payment_method_type_values(vals, payment_method_type, if_present)`: Disables incompatible fields when changing the integration type.

**QR Code Payments:**
When `payment_method_type = 'qr_code'`, the POS can display a QR code for the customer to scan with their banking app. The QR code encodes the amount, currency, and payment reference. It works offline because the QR code is pre-generated (amount=0, with debtor_partner set at payment time).

### pos.category

Product categories displayed in the POS tree view.

**Fields:**
- `name`: Char - Category name (required, translatable)
- `parent_id`: Many2one - Parent category (recursive)
- `child_ids`: One2many - Child categories
- `sequence`: Integer - Display order
- `image_128`: Image - Category image
- `color`: Integer - Color for POS UI
- `has_image`: Boolean - Computed from presence of `image_128`

**Key Methods:**
- `_check_category_recursion()`: Prevents recursive category hierarchies.
- `_get_descendants()`: Returns all descendant categories (recursive).
- `_get_hierarchy()`: Returns a list representing the category path (e.g., `['Electronics', 'Phones', 'Smartphones']`).
- `_compute_display_name()`: Shows full path as `"Electronics / Phones / Smartphones"`.
- `_unlink_except_session_open()`: Prevents deletion of categories while any POS session is open.
- `_load_pos_data_domain(data)`: Restricts loaded categories to those available in the POS config (if `limit_categories` is enabled).
- `create()`: Auto-inherits color from parent category.
- `write()`: Propagates color to children when parent changes.

### account.cash.rounding

Extends `account.cash.rounding` to support POS rounding behavior.

**Fields:**
- `rounding`: Float - Rounding unit (e.g., 0.05 for 5-cent rounding)
- `strategy`: Selection - `add_invoice_line` or `biggest_tax` (biggest tax rounding)
- `name`: Char - Display name
- `precision`: Integer - Decimal precision

## pos.load.mixin

A mixin that provides data loading infrastructure for the POS frontend. Models that inherit this mixin implement `_load_pos_data_domain`, `_load_pos_data_fields`, and optionally `_load_pos_data` to define what subset of their records should be sent to the POS client.

**Key Methods:**
- `_load_pos_data_domain(data)`: Returns a domain to filter which records to load. `data` contains already-loaded data from parent models.
- `_load_pos_data_fields(config_id)`: Returns the list of field names to include in the response.
- `_load_pos_data(data)`: Optional. Override to compute and return custom data structures.

Models that use `pos.load.mixin`: `pos.config`, `pos.session`, `pos.order`, `pos.order.line`, `pos.payment`, `pos.payment.method`, `pos.category`, `loyalty.card`, `loyalty.reward`, `loyalty.rule`, `loyalty.program`.

## Cross-Module Relationships

- **stock**: Pickings linked via `pos_order_id` on `stock.picking`, operation type from `stock.picking.type`, warehouse from `stock.warehouse`
- **account**: Journal entries for session closing and payments, invoice generation from orders, cash/bank journals, cash rounding
- **sale**: POS pricelist computation uses sale pricelist rules
- **product**: Product variants, combos, packagings, UoM, attributes
- **pos_loyalty**: Loyalty card/reward integration
- **pos_sale**: Link to sale orders
- **mail**: Message posting on sessions and orders (via `mail.thread`)

## Edge Cases

1. **Rescue Sessions**: When an order arrives but the session is already closed, a rescue session is created to hold the orphan order. `_get_valid_session()` finds or creates this rescue session.
2. **Cash Control Difference**: The difference between theoretical closing balance (`cash_register_balance_end`) and real counted balance (`cash_register_balance_end_real`) is posted to a profit/loss account at closing.
3. **Multi-Currency**: Orders store the `currency_rate` at creation time. Payments are converted using this rate. The session's account move is in the company's default currency.
4. **Split Transactions**: When a payment method has `split_transactions=True`, each customer gets their own receivable line in the journal entry, enabling accurate customer statement reporting.
5. **Order Edit Tracking**: When `order_edit_tracking` is enabled on the config, any order modification during the session is tracked and posted to the session's chatter.
6. **Stock at Closing**: Depending on config (`update_stock_at_closing`), stock is updated either immediately at order confirmation or deferred to session closing (preferred for accuracy).
7. **Combo Products in Orders**: A combo line has multiple child lines linked via `combo_line_ids`. All child lines share the parent's `uuid` for grouping, while each has a unique `uuid`.
8. **Payment Terminal Offline**: QR code payments work offline because the QR is pre-generated at payment method configuration time with `amount=False`, and the debtor partner and amount are resolved at scan time.
9. **Blocked Payment Method Edits**: Payment methods cannot be modified if any open session references them (except `sequence`).
