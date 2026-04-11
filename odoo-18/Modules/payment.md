# Payment Module (Odoo 18)

## Overview

The payment module provides a unified payment processing framework supporting multiple payment providers (Stripe, PayPal, SEPA, etc.). It handles the complete payment lifecycle: from transaction creation through provider processing to completion/cancellation.

**Module Path:** `payment/`
**Key Models:** `payment.provider`, `payment.transaction`, `payment.token`, `payment.method`
**Dependencies:** `account` (for journal entries)

---

## Architecture

```
payment.transaction
    ├── payment.provider  (Many2one)
    ├── payment.method    (Many2one)
    ├── payment.token     (Many2one, optional)
    └── res.partner       (Many2one)

payment.provider
    └── payment.method    (Many2many)

payment.token
    ├── payment.provider  (Many2one)
    ├── payment.method    (Many2one)
    └── res.partner       (Many2one)
```

---

## payment.provider

The `payment.provider` model represents a payment gateway/account (e.g., Stripe account, PayPal account). Multiple providers can coexist; each operates independently per company.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Display name of the provider |
| `code` | Selection | Technical code (`none`, `stripe`, `paypal`, `bacs`, `custom`) |
| `state` | Selection | `disabled`, `enabled`, `test` |
| `company_id` | Many2one | Company this provider belongs to |
| `payment_method_ids` | Many2many | Payment methods supported by this provider |
| `allow_tokenization` | Boolean | Whether customers can save payment methods |
| `capture_manually` | Boolean | Manual capture mode (authorize first, capture later) |
| `allow_express_checkout` | Boolean | Enable express checkout (Google Pay, Apple Pay) |
| `redirect_form_view_id` | Many2one | QWeb template for redirect-based payments |
| `inline_form_view_id` | Many2one | QWeb template for inline/popup payments |
| `token_inline_form_view_id` | Many2one | QWeb template for token-based payments |
| `express_checkout_form_view_id` | Many2one | QWeb template for express checkout |
| `available_country_ids` | Many2many | Restrict availability by country |
| `available_currency_ids` | Many2many | Restrict availability by currency |
| `maximum_amount` | Monetary | Maximum transaction amount |
| `is_published` | Boolean | Visibility on website (separate from state) |
| `pre_msg` | Html | Help message displayed before payment |
| `pending_msg` | Html | Message shown when payment is pending |
| `auth_msg` | Html | Message shown when payment is authorized |
| `done_msg` | Html | Message shown when payment is confirmed |
| `cancel_msg` | Html | Message shown when payment is cancelled |
| `support_tokenization` | Boolean | Computed: provider supports tokenization |
| `support_manual_capture` | Selection | `full_only`, `partial`, or None |
| `support_express_checkout` | Boolean | Computed: provider supports express checkout |
| `support_refund` | Selection | `none`, `full_only`, `partial` |
| `module_id` | Many2one | Associated ir.module.module record |
| `module_state` | Selection | Module installation state |
| `image_128` | Image | Provider logo |
| `color` | Integer | Kanban card color (computed from state) |

### State Machine

```
disabled (grey) ──> enabled (green)
                  ──> test (orange)

enabled/test ──> archiving linked tokens on disable
```

### Key Methods

#### `_get_compatible_providers()`
Returns providers matching compatibility criteria (company, country, currency, amount, tokenization, express checkout).

```python
def _get_compatible_providers(
    self, company_id, partner_id, amount, currency_id=None,
    force_tokenization=False, is_express_checkout=False, is_validation=False
):
```

#### `_get_supported_currencies()`
Returns currencies supported by this provider. Override to restrict currencies.

#### `_get_validation_amount()` / `_get_validation_currency()`
Returns amount/currency for tokenization validation transactions.

#### `_get_redirect_form_view()` / `_get_inline_form_view()`
Returns the QWeb template used to render the payment form.

#### `_setup_provider(provider_code)`
Performs module-specific setup when the provider module is installed. Called by `_setup_provider` hook.

#### `_remove_provider(provider_code)`
Removes provider module-specific data when the module is uninstalled.

#### `_archive_linked_tokens()`
Called when provider is disabled or state changes. Archives all tokens linked to the provider.

#### `_activate_default_pms()` / `_deactivate_unsupported_payment_methods()`
Manages payment method activation based on provider state.

---

## payment.transaction

The `payment.transaction` model records every individual payment operation. Each transaction goes through a defined state machine.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `provider_id` | Many2one | Payment provider handling this transaction |
| `payment_method_id` | Many2one | Payment method used |
| `reference` | Char | Internal unique reference (auto-generated) |
| `provider_reference` | Char | Provider's own transaction ID |
| `amount` | Monetary | Transaction amount |
| `currency_id` | Many2one | Transaction currency |
| `token_id` | Many2one | Payment token used (if any) |
| `state` | Selection | `draft`, `pending`, `authorized`, `done`, `cancel`, `error` |
| `state_message` | Text | Provider's message about the state |
| `last_state_change` | Datetime | Timestamp of last state change |
| `operation` | Selection | `online_redirect`, `online_direct`, `online_token`, `validation`, `offline`, `refund` |
| `source_transaction_id` | Many2one | Parent transaction (for refunds/captures) |
| `child_transaction_ids` | One2many | Child transactions |
| `refunds_count` | Integer | Count of refund transactions |
| `is_post_processed` | Boolean | Whether post-processing has completed |
| `tokenize` | Boolean | Whether to create a token after success |
| `landing_route` | Char | URL to redirect after payment |
| `partner_id` | Many2one | Customer making the payment |
| `partner_name`, `partner_email`, `partner_phone`, etc. | Char | Duplicated partner values for traceability |

### State Machine

```
draft ──────> pending ──────> authorized ──────> done
   │              │               │
   │              │               └── cancel (void request)
   │              │
   └── cancel     └── error

Operations:
  online_redirect  -> draft -> pending -> done
  online_direct    -> draft -> done (or error)
  online_token     -> draft -> done (or error)
  validation       -> draft -> authorized (for tokenization)
  offline          -> done (using saved token)
  refund           -> done (child of source transaction)
```

### Key Methods

#### `_compute_reference()` / `_compute_reference_prefix()`
Generates unique reference strings. Pattern: `{prefix}-{sequence}` or `tx-{datetime}`.

#### `_get_processing_values()`
Returns dict with all values needed to render the payment form (provider_id, reference, amount, currency_id, partner_id, should_tokenize, and provider-specific values).

#### `_get_specific_processing_values()` / `_get_specific_rendering_values()`
Override points for provider-specific processing/rendering data.

#### `_send_payment_request()`
Requests payment via provider. Used for token-based payments (`online_token`, `offline`).

#### `_send_capture_request(amount_to_capture=None)`
Requests capture of an authorized transaction. Creates child transaction for partial captures.

#### `_send_void_request(amount_to_void=None)`
Requests void of an authorized transaction.

#### `_send_refund_request(amount_to_refund=None)`
Creates a refund child transaction and sends refund request to provider.

#### `_handle_notification_data()`
Matches transaction with provider webhook data and processes it.

#### `_get_tx_from_notification_data()`
Factory method that subclasses override per provider to find the transaction from webhook data.

#### `_process_notification_data()`
Processes provider-specific notification data. Subclasses override per provider.

### State Transition Methods

| Method | Allowed From | Target |
|--------|-------------|--------|
| `_set_pending()` | `draft` | `pending` |
| `_set_authorized()` | `draft`, `pending` | `authorized` |
| `_set_done()` | `draft`, `pending`, `authorized`, `error` | `done` |
| `_set_canceled()` | `draft`, `pending`, `authorized` | `cancel` |
| `_set_error()` | `draft`, `pending`, `authorized` | `error` |

### Constraints

```python
@api.constrains('state')
def _check_state_authorized_supported(self):
    # Only allow 'authorized' state if provider supports manual capture

@api.constrains('token_id')
def _check_token_is_active(self):
    # Only allow active tokens for new transactions
```

---

## payment.token

The `payment.token` model stores saved payment methods (credit cards, bank accounts) as tokens provided by the payment gateway.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `provider_id` | Many2one | Payment provider |
| `payment_method_id` | Many2one | Payment method type |
| `payment_details` | Char | Masked payment details (e.g., "**** 1234") |
| `partner_id` | Many2one | Owner partner |
| `provider_ref` | Char | Provider's token reference |
| `transaction_ids` | One2many | Transactions using this token |
| `active` | Boolean | Token active/inactive |

### Key Methods

#### `_get_available_tokens()`
Returns tokens available for a provider/partner combination. For validation operations, also returns commercial partner's tokens.

#### `_build_display_name()`
Formats token name as `**** 1234` (masked). Supports padding and max_length.

#### `_get_specific_create_values()`
Override point for provider-specific token creation values.

#### `_handle_archiving()`
Hook called when a token is archived. Override for provider-specific cleanup.

### Constraints

```python
@api.constrains('partner_id')
def _check_partner_is_never_public(self):
    # Public partner cannot have tokens (e.g., portal user acting as public)
```

---

## payment.method

The `payment.method` model represents a type of payment instrument (credit card, SEPA direct debit, etc.). It is independent of providers.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Display name |
| `code` | Char | Technical code |
| `sequence` | Integer | Display order |
| `primary_payment_method_id` | Many2one | Parent primary method (for brands) |
| `brand_ids` | One2many | Brands belonging to this primary method |
| `is_primary` | Boolean | Computed: is this a primary method (not a brand) |
| `provider_ids` | Many2many | Providers supporting this method |
| `active` | Boolean | Active status |
| `image` | Image | Logo (64x64) |
| `support_tokenization` | Boolean | Method supports tokenization |
| `support_express_checkout` | Boolean | Method supports express checkout |
| `support_refund` | Selection | Refund support level |
| `supported_country_ids` | Many2many | Countries where method is available |
| `supported_currency_ids` | Many2many | Currencies supported |

### Brand Hierarchy Example

```
primary: "Card"
  └── brand: "VISA"
  └── brand: "Mastercard"
  └── brand: "Amex"
```

### Key Methods

#### `_get_compatible_payment_methods()`
Returns payment methods matching compatibility criteria (providers, partner country, currency, tokenization, express checkout).

#### `_get_from_code()`
Finds payment method by code, with optional generic-to-specific mapping.

---

## State Machine Summary

```
1. Customer initiates payment
   --> payment.transaction created (state=draft)
   --> operation set (redirect/direct/token/validation)

2. Payment request sent to provider
   --> _set_pending() or _set_authorized() called
   --> provider processes payment

3. Provider sends notification (webhook)
   --> _handle_notification_data()
   --> _get_tx_from_notification_data() finds correct tx
   --> _process_notification_data() updates state
   --> _set_done() / _set_error() / _set_canceled()

4. Post-processing
   --> _cron_post_process() triggers for unprocessed txs
   --> _post_process() handles tokenization, linked document updates

5. Tokenization flow
   --> tokenize=True on transaction
   --> On success, payment.token record created
   --> Token linked to partner for future use
```

---

## Callback Security

Providers send webhook notifications to `/payment/{provider_code}/webhook`. The notification data contains a signature that must be validated:

```python
def _get_tx_from_notification_data(self, provider_code, notification_data):
    # Subclasses must implement per-provider logic
    # to find the transaction from the notification data
```

Common patterns:
- Find by `provider_reference` in notification
- Validate HMAC signature before trusting data
- Prevent replay attacks with idempotency keys

---

## Provider-Specific Subclasses

Each payment provider (Stripe, PayPal, SEPA, etc.) is a separate module that:

1. Inherits `payment.provider` and adds:
   - Provider-specific fields with `required_if_provider='code'`
   - API credentials fields (usually in `code` field's view)

2. Implements these methods:
   - `_get_supported_currencies()` - restrict currencies
   - `_get_specific_create_values()` - transaction creation
   - `_get_specific_rendering_values()` - form rendering data
   - `_get_specific_processing_values()` - processing data
   - `_send_payment_request()` - direct payment
   - `_send_capture_request()` - capture authorized
   - `_send_void_request()` - void authorized
   - `_send_refund_request()` - refund captured
   - `_get_tx_from_notification_data()` - webhook handling
   - `_process_notification_data()` - state update from webhook

3. Registers webhook endpoint via `ir_http` controller
