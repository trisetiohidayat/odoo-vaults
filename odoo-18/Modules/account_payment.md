---
type: module
name: account_payment
version: Odoo 18
models_count: ~8
documentation_date: 2026-04-11
tags: [payment, transaction, provider, token]
---

# Account Payment

Payment processing integration — providers (Stripe, PayPal, etc.), payment transactions, tokens, and reconciliation with invoices.

## Models

### payment.transaction

Online payment transaction. States: `draft` → `pending` → `authorized` → `done` / `cancel` / `error`.

**Key Fields:**
- `provider` (`payment.provider`) — Payment provider
- `provider_reference` — Provider's transaction ID
- `payment_method_id` (`account.payment.method`) — Method (credit card, etc.)
- `partner_id` (`res.partner`)
- `amount`, `currency_id`
- `state` — `draft`, `pending`, `authorized`, `done`, `cancel`, `error`
- `operation` — `online_redirect` (payment page), `online_token` (saved token), `validation` (auth-only), `offline` (manual)
- `callback_hash` — HMAC signature to verify callback authenticity
- `tokenize` (`Boolean`) — Save payment method as token?
- `callback_model_id`, `callback_res_id` — Related record to update on success
- `source_transaction_id` — Parent transaction (for refunds)
- `last_state_message` — Last error/info message

**L3 Workflow:**
- `_get_tx_from_notification_data(provider, data)` — Factory method to find/create tx from provider webhook
- `_process_notification_data(data)` — Parses provider-specific webhook data
- `_process_feedback_data(provider, data)` — Orchestrates: get tx → validate → process
- `_post_process()` — After success: creates `account.payment`, reconciles with invoice
- `_create_payment_entries()` — Called by `_post_process()`:
  1. Creates `account.move` with liquidity + counterpart lines
  2. Links `payment_id` to the move
  3. Reconciles with matching invoice (`_reconcile_payment_to_invoice()`)
- `action_see_transaction_on_provider()` — Redirects to provider dashboard
- `action_capture()` — Captures authorized transaction
- `action_void()` — Voids/cancels authorized transaction
- `action_refund()` — Creates refund transaction

**L3 Token Flow:**
1. `tokenize=True` on payment form
2. After `_post_process()`, creates `payment.token`
3. Token linked to `partner_id` + `provider` + `provider_reference`
4. Next payment: `payment.transaction` created with `token_id` (no redirect needed)

**L3 `callback_hash` Validation:**
- Server-to-server callbacks signed with HMAC-SHA256
- Validates `provider_reference` matches tx, prevents replay attacks

### payment.provider

Payment provider configuration.

**Key Fields:**
- `name`, `code` — Internal + display name
- `state` — `disabled`, `enabled`, `test`, `custom`
- `is_published` — Available on website
- `journal_id` (`account.journal`) — Settlement journal
- `provider_channel_ids` — Website channels
- `amount`, `currency_ids` — Limits per amount/currency
- `country_ids`, `country_group_ids` — Geographic restrictions
- `payment_method_ids` — Available payment methods
- `redirect_form_view_id` — Custom payment form
- `capture_manually` — Don't auto-capture authorized payments
- `allow_express_checkout` — Express checkout button
- `inline_form_view_id` — Embedded card form
- `support_tokenization`, `support_refund` — Capabilities
- `company_id`, `website_id` (`website`)

**L3 Provider-Specific Methods:**
- `_stripe_create_payment_intent()` — Creates Stripe PaymentIntent
- `_paypal_init_tx()` — Initializes PayPal order
- `_razorpay_create_order()` — Creates Razorpay order
Each provider overrides: `init_tx`, `get_tx_status`, `render`, `_process_notification_data`

### payment.token

Saved payment credentials.

**Key Fields:**
- `partner_id`, `provider_id`, `payment_method_id`
- `provider_reference` — Token from provider
- `acquirer_ref` — Provider's customer ID
- `active` — Can be reused?
- `verified` — Identity verified?
- `record_id`, `record_xml_id` — Dynamic linking via `payment.context.*` fields

### account.payment.method

**Key Fields:**
- `name`, `code` — e.g., "Credit Card", "SEPA Direct Debit"
- `payment_type` — `inbound`, `outbound`
- `provider_ids` (m2m) — Which providers support this method

### account.payment.method.line

**Key Fields:**
- `journal_id`, `payment_method_id`, `name`
- `sequence`, `provider_id`
- `payment_method_id` (m2o) — Links journal to payment method

### account.payment.register (wizard)

Transient wizard to register payments from invoice list view.

**Key Fields:**
- `journal_id`, `payment_method_line_id`
- `amount`, `currency_id`, `date`
- `payment_difference`, `payment_difference_handling` — Write-off options
- `writeoff_account_id`, `writeoff_label`
- `group_payment` — Pay all selected invoices in one payment

## Integrations

- **Sale**: `sale_payment` links `payment.transaction` to `sale.order`
- **Account**: `account.payment` is the journal entry counterpart
- **Website**: `website_payment` handles frontend payment pages

## Code

- Models: `~/odoo/odoo18/odoo/addons/payment/models/`
