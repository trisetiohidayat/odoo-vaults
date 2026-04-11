---
Module: pos_online_payment
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_online_payment #payment #online #pos
---

## Overview

Enables online payment providers (Stripe, PayPal, etc.) as POS payment methods. Adds a new `type='online'` payment method type, a dedicated `is_online_payment` flag, and links `payment.transaction` to `pos.order`. Handles the full flow: transaction creation, webhook processing, payment recording.

**Depends:** `point_of_sale`, `payment`

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

| Field | Type | Notes |
|---|---|---|
| `is_online_payment` | Boolean | Default False. Marks method as online payment. |
| `online_payment_provider_ids` | Many2many `payment.provider` | Allowed providers (empty = all published) |
| `has_an_online_payment_provider` | Boolean (compute) | True if valid providers available |
| `type` | Selection (extends) | Adds `('online', 'Online')` to selection |

**Computed:** `_compute_type` -> if `is_online_payment`, sets `type='online'`

**Methods:**
- `_load_pos_data_fields(config_id)` -> adds `'is_online_payment'`
- `_get_online_payment_providers(pos_config_id=False, error_if_invalid=True)` -> returns eligible published providers filtered by POS config currency. Raises ValidationError if invalid providers and `error_if_invalid=True`
- `_compute_has_an_online_payment_provider()` -> depends on `is_online_payment` and `online_payment_provider_ids`
- `_is_write_forbidden(fields)` -> allows writing `online_payment_provider_ids` even when session open
- `create(vals_list)` -> forces `_force_online_payment_values` on `is_online_payment=True` records
- `write(vals)` -> if `is_online_payment` in vals: forces values. Separates online vs non-online for partial writes.
- `_force_online_payment_values(vals, if_present=False)` -> sets `type='online'`, disables `split_transactions`, `receivable_account_id`, `outstanding_account_id`, `journal_id`, `is_cash_count`, `use_payment_terminal`, `qr_code_method`; sets `payment_method_type='none'`
- `_get_payment_terminal_selection()` -> returns empty list for online payment methods (no terminal selection)
- `_compute_hide_use_payment_terminal()` -> hides terminal option for online type
- `_get_or_create_online_payment_method(company_id, pos_config_id)` -> searches existing OPM for company+config, falls back to company-only, falls back to creating new. Static utility method.

---

### `pos.config` (Extension)
**Inheritance:** `pos.config`

**Methods:**
- `_check_online_payment_methods()` -> `@api.constrains('payment_method_ids')`: max 1 online payment method per config; provider must support config currency
- `_get_cashier_online_payment_method()` -> returns first online payment method from `payment_method_ids`

---

### `pos.payment` (Extension)
**Inheritance:** `pos.payment`

| Field | Type | Notes |
|---|---|---|
| `online_account_payment_id` | Many2one `account.payment` | The accounting payment created for this online payment |

**Methods:**
- `create(vals_list)` -> validates: online payment methods require `online_account_payment_id`; non-online methods cannot have one; validates account payment exists
- `write(vals)` -> prevents editing essential fields (`amount`, `payment_date`, `payment_method_id`, `online_account_payment_id`, `pos_order_id`) for payments with online_account_payment or online payment method
- `_check_payment_method_id()` -> bypasses standard check for online payments; logs warning if online payment method differs from config's online payment method

---

### `pos.order` (Extension)
**Inheritance:** `pos.order`

| Field | Type | Notes |
|---|---|---|
| `online_payment_method_id` | Many2one `pos.payment.method` (compute) | From `config_id._get_cashier_online_payment_method` |
| `next_online_payment_amount` | Float | Next online payment amount, unlimited precision |

**Methods:**
- `_compute_online_payment_method_id()` -> `@api.depends('config_id.payment_method_ids')`: delegates to config
- `get_amount_unpaid()` -> `amount_total - amount_paid` (rounded)
- `_clean_payment_lines()` -> unlinks non-online payments for this order (used when order is deleted)
- `get_and_set_online_payments_data(next_online_payment_amount=False)` -> returns online payments made, amount unpaid, and handles order deletion when next amount is 0 and conditions are met (draft, not restaurant, no trusted config). Updates `next_online_payment_amount` if valid.
- `_check_next_online_payment_amount(amount)` -> validates 0 <= amount <= amount_unpaid
- `_get_checked_next_online_payment_amount()` -> returns amount if valid else False

---

### `pos.session` (Extension)
**Inheritance:** `pos.session`

**Methods:**
- `_accumulate_amounts(data)` -> collects `split_receivables_online` amounts from `payment.type == 'online'` payments
- `_create_bank_payment_moves(data)` -> creates split receivable journal items for online payments; matches them with account.payment receivable lines
- `_get_split_receivable_op_vals(payment, amount, amount_converted)` -> builds MoveLine vals: uses accounting partner's receivable account, partner, name='{session} - {payment_method} - {provider}'
- `_reconcile_account_move_lines(data)` -> reconciles online payment receivable lines (if account is reconcilable)

---

### `account.payment` (Extension)
**Inheritance:** `account.payment`

| Field | Type | Notes |
|---|---|---|
| `pos_order_id` | Many2one `pos.order` | Linked POS order, readonly |

**Methods:**
- `action_view_pos_order()` -> returns form action for linked `pos.order`

---

### `payment.transaction` (Extension)
**Inheritance:** `payment.transaction`

| Field | Type | Notes |
|---|---|---|
| `pos_order_id` | Many2one `pos.order` | Linked POS order, readonly |

**Methods:**
- `_compute_reference_prefix(provider_code, separator, **values)` -> if `pos_order_id` in values, returns `pos_order.pos_reference` instead of generic prefix
- `_post_process()` -> extends to call `_process_pos_online_payment()` after parent
- `_process_pos_online_payment()` -> for txs with `pos_order_id`, state `authorized/done`, no existing payment_id: creates accounting payment, creates `pos.payment` record, updates payment with `pos_payment_method_id`, `pos_order_id`, `pos_session_id`; if order draft and paid, processes saved order; sends `ONLINE_PAYMENTS_NOTIFICATION` to POS
- `action_view_pos_order()` -> returns form action for linked `pos.order`

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Online payment reconciliation:** Online payments use `split_receivables_online` in session closing. The `account.payment` linked to the POS payment is matched with a split receivable journal item, enabling reconciliation without a bank statement match.

2. **Currency validation:** `_get_online_payment_providers` filters providers by currency compatibility with the POS config's Sales Journal currency. If any provider uses a different currency, a ValidationError is raised.

3. **Transaction state machine:** `payment.transaction._process_pos_online_payment` handles the flow: authorized/done tx -> create account.payment -> create pos.payment with `online_account_payment_id` -> notify POS client. This runs automatically via `_post_process` hook.

4. **Order deletion:** `get_and_set_online_payments_data` with `next_online_payment_amount=0` deletes the draft order if: no existing online payments, draft state, not a restaurant order, no trusted config. Prevents orphan orders from abandoned online payment flows.

5. **Trusted configs:** The `trusted_config_ids` field on `pos.config` allows orders from other configs to count as "paid" in shared online payment scenarios (e.g., multiple POS sharing the same online payment method).