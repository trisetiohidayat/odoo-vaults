---
Module: payment_paypal
Version: Odoo 18
Type: Integration
Tags: #payment, #paypal, #provider, #integration, #webhook, #ipn, #rest-api
---

# Payment Provider: PayPal (`payment_paypal`)

> **Source:** `~/odoo/odoo18/odoo/addons/payment_paypal/`
> **Manifest:** `version: 2.0`, `category: Accounting/Payment Providers`, `depends: payment`
> **License:** LGPL-3

An American payment provider for online payments worldwide. Uses PayPal REST API v2 (Orders and Captures). All payments use `intent: 'CAPTURE'` — no authorizations; capture is immediate. Supports IPN (Instant Payment Notification) webhooks and direct capture confirmation via controller. Tokenization is **not** supported for saved cards (PayPal checkout flow does not persist cards server-side in the same way Stripe/Adyen do).

---

## Module Structure

```
payment_paypal/
├── models/
│   ├── __init__.py
│   ├── payment_provider.py      # payment.provider extension
│   └── payment_transaction.py   # payment.transaction extension
├── controllers/
│   ├── __init__.py
│   └── main.py                  # PaypalController (webhook + capture route)
├── const.py                     # currencies, status mapping, webhook events
├── utils.py                     # get_normalized_email_account, format_partner_address, format_shipping_address
├── data/
│   └── payment_provider_data.xml
└── static/src/**/*
```

---

## Models

### `payment.provider` (Extended)

Inherits `payment.provider` and registers `code = 'paypal'`. Stores PayPal OAuth2 credentials and manages access token lifecycle.

#### Fields

| Field | Type | Required | Groups | Description |
|-------|------|----------|--------|-------------|
| `code` | `Selection` | Yes | — | Extends selection with `('paypal', "PayPal")` |
| `paypal_email_account` | `Char` | Yes | — | Public business email; used as `email_address` in PayPal order payload. Default: `self.env.company.email` |
| `paypal_client_id` | `Char` | Yes | — | PayPal OAuth2 client ID (public-facing identifier) |
| `paypal_client_secret` | `Char` | Yes | `base.group_system` | PayPal OAuth2 client secret for server-side token exchange |
| `paypal_access_token` | `Char` | — | `base.group_system` | Current OAuth2 bearer token (short-lived, auto-refreshed) |
| `paypal_access_token_expiry` | `Datetime` | — | `base.group_system` | When the current access token expires. Default: `'1970-01-01'` (expired on first use) |
| `paypal_webhook_id` | `Char` | No | — | PayPal webhook ID for signature verification |

#### Supported Currencies

**`_get_supported_currencies()`**

Filters to PayPal's supported set: `AUD, BRL, CAD, CNY, CZK, DKK, EUR, HKD, HUF, ILS, JPY, MYR, MXN, TWD, NZD, NOK, PHP, PLN, GBP, RUB, SGD, SEK, CHF, THB, USD`

Note: `RUB` (Russian Ruble) may be subject to sanctions restrictions.

#### Feature Support Flags

Inherits base flags only — PayPal does **not** set:
- `support_tokenization`: `False` (no saved cards in standard flow)
- `support_manual_capture`: `False` (all payments are `CAPTURE` intent, immediate)
- `support_refund`: `partial` (inherited from base)

#### Business Methods — Access Token

**`_paypal_fetch_access_token()`**

Implements OAuth2 client_credentials flow. Token is cached with 5-minute buffer before expiry.

```
POST /v1/oauth2/token
  grant_type: client_credentials
  auth: (client_id, client_secret)  — Basic auth header
```

Response contains `access_token` (string) and `expires_in` (seconds). Stored in:
- `paypal_access_token`: the token string
- `paypal_access_token_expiry`: `Datetime.now() + timedelta(seconds=expires_in)`

On next call, if `Datetime.now() > expiry - 5 minutes`: refreshes automatically.

**`_paypal_make_request(endpoint, data=None, json_payload=None, auth=None, is_refresh_token_request=False, idempotency_key=None)`**

Core HTTP client for PayPal REST API v2.

- URL: `{api_url}{endpoint}` — `api-m.paypal.com` (live) or `api-m.sandbox.paypal.com` (test)
- Headers: `Content-Type: application/json`, `Authorization: Bearer {token}`, `PayPal-Request-Id: {idempotency_key}`
- For token refresh: uses `auth=(client_id, client_secret)` and no Bearer header
- Timeout: 10 seconds
- HTTP errors logged and raised as `ValidationError`
- Connection/timeout errors raised as `ValidationError`

#### API URL Selection

**`_paypal_get_api_url()`**

- `state == 'enabled'`: returns `'https://api-m.paypal.com'`
- `state != 'enabled'`: returns `'https://api-m.sandbox.paypal.com'`

#### Action Methods

**`action_paypal_create_webhook()`**

Creates a PayPal webhook pointing to `/payment/paypal/webhook/` with events from `const.HANDLED_WEBHOOK_EVENTS`. Writes `paypal_webhook_id` from response. Raises `UserError` if base URL contains `localhost` (PayPal requires HTTPS).

#### Inline Form Values

**`_paypal_get_inline_form_values(currency=None)`** → JSON string

```python
{
    'provider_id': <self.id>,
    'client_id': <self.paypal_client_id>,
    'currency_code': <currency.name or None>,
}
```

**`_get_default_payment_method_codes()`** → `{'paypal'}` (single PayPal button)

---

### `payment.transaction` (Extended)

Inherits `payment.transaction`. Creates PayPal Orders (v2), processes capture confirmation, and handles IPN/webhook notifications.

#### Order Creation

**`_get_specific_processing_values(processing_values)`**

1. Builds payload via `_paypal_prepare_order_payload()`
2. Generates idempotency key: `payment_utils.generate_idempotency_key(self, scope='payment_request_order')`
3. Sends `POST /v2/checkout/orders` with payload
4. Returns `{'order_id': order_data['id']}` — frontend uses this to redirect to PayPal

#### Payload: `_paypal_prepare_order_payload()`

```python
{
    'intent': 'CAPTURE',
    'purchase_units': [{
        'reference_id': <tx.reference>,
        'description': '<company>: <reference>',
        'amount': {
            'currency_code': <currency.name>,
            'value': <amount>,         # Major currency units (float string)
        },
        'payee': {
            'display_data': {
                'brand_name': <company.name>,
                # 'business_email': <company.email>  # conditionally added
            },
            'email_address': <normalized paypal_email_account>,
        },
        **shipping_address_from_sale_order_or_invoice,  # optional
    }],
    'payment_source': {
        'paypal': {
            'experience_context': {
                'shipping_preference': 'SET_PROVIDED_ADDRESS' | 'NO_SHIPPING',
            },
            'name': {
                'given_name': <partner first name>,
                'surname': <partner last name>,
            },
            **invoice_address_from_partner,  # optional
        },
    },
}
```

**Shipping preference:**
- `'SET_PROVIDED_ADDRESS'`: PayPal displays shipping address from the sales order
- `'NO_SHIPPING'`: PayPal does not ask for shipping (for digital goods)

**Invoice address formatting** (`utils.format_partner_address`):
- Only included if `partner.country_id` is set (PayPal requires country for address)
- Maps: `street→address_line_1`, `street2→address_line_2`, `state.code→admin_area_1`, `city→admin_area_2`, `zip→postal_code`, `country.code→country_code`

**Payee email**: `paypal_utils.get_normalized_email_account(provider)` — strips unicode characters (e.g., zero-width spaces `\u200b`) from the email field.

#### Flow: Order → Capture

PayPal uses a two-step flow:
1. **Order creation** — `POST /v2/checkout/orders` with `intent: 'CAPTURE'` creates an order in `CREATED` state
2. **Capture** — Either via:
   - **Controller**: `PaypalController.paypal_complete_order()` at `/payment/paypal/complete_order` (JSON, public auth)
   - **Webhook**: `PaypalController.paypal_webhook()` with `CHECKOUT.ORDER.COMPLETED` event

#### Controller: Capture Route

**`paypal_complete_order(provider_id, order_id, reference=None)`**

1. If `reference` provided: fetches `tx_sudo` to generate idempotency key scoped to transaction
2. Sends `POST /v2/checkout/orders/{order_id}/capture`
3. Normalizes response via `_normalize_paypal_data()`
4. Looks up transaction and processes notification data

#### Webhook: `paypal_webhook()`

**`POST /payment/paypal/webhook/`** — HTTP, no CSRF, public auth

1. Parses JSON: `data['event_type']`, `data['resource']`
2. Only processes events in `const.HANDLED_WEBHOOK_EVENTS`:
   - `CHECKOUT.ORDER.COMPLETED` — order captured
   - `CHECKOUT.ORDER.APPROVED` — order approved but not yet captured
   - `CHECKOUT.PAYMENT-APPROVAL.REVERSED` — approval reversed
3. Normalizes webhook data via `_normalize_paypal_data(resource, from_webhook=True)`
4. Verifies webhook origin: `_verify_notification_origin()` — PayPal webhook signature verification
5. Looks up transaction and processes notification data
6. Returns `''` (empty JSON response)

#### Data Normalization: `_normalize_paypal_data(data, from_webhook=False)`

PayPal's response format differs between the direct API and webhook. This method normalizes both to a common structure:

**From direct API response (capture confirmation):**
```python
{
    'payment_source': <set of payment source keys>,
    'reference_id': <tx.reference>,
    # from captures[0]:
    'id': <capture ID>,
    'status': <'COMPLETED'>,
    'amount': {'value': ..., 'currency_code': ...},
    'txn_type': 'CAPTURE',
}
```

**From webhook:**
```python
{
    'payment_source': <keys of payment_source>,
    'reference_id': <reference_id from purchase_units>,
    # from purchase_units[0]:
    **<all fields of purchase unit>,
    'txn_type': <data['intent']>,
    'id': <data['id']> (the order ID),
    'status': <data['status']>,
}
```

Raises `ValidationError` if no `captures` in non-webhook response.

#### Webhook Signature Verification

**`_verify_notification_origin(notification_data, tx_sudo)`**

Implements PayPal's webhook signature verification (RFC 虚). Sends to `POST /v1/notifications/verify-webhook-signature`:

```python
{
    'transmission_id': <header PAYPAL-TRANSMISSION-ID>,
    'transmission_time': <header PAYPAL-TRANSMISSION-TIME>,
    'cert_url': <header PAYPAL-CERT-URL>,
    'auth_algo': <header PAYPAL-AUTH-ALGO>,
    'transmission_sig': <header PAYPAL-TRANSMISSION-SIG>,
    'webhook_id': <provider.paypal_webhook_id>,
    'webhook_event': <full notification_data>,
}
```

If `verification_status != 'SUCCESS'`: raises `Forbidden()`.

#### Transaction Lookup

**`_get_tx_from_notification_data(provider_code, notification_data)`**

1. Calls super first — handles direct lookups by `provider_reference`
2. For PayPal: if not found, falls back to `notification_data['reference_id']` → search by `reference` field
3. Raises `ValidationError` if still not found

#### State Processing

**`_process_notification_data(notification_data)`**

1. Validates amount and currency match
2. Extracts `id` (provider reference / PayPal capture ID) and `txn_type`
3. Sets `payment_method_id` to the PayPal payment method (searches by `code='paypal'`)
4. Maps `notification_data['status']` via `const.PAYMENT_STATUS_MAPPING`:

| PayPal Status | Odoo State |
|--------------|-----------|
| `PENDING`, `CREATED`, `APPROVED` | `_set_pending(pending_reason)` |
| `COMPLETED`, `CAPTURED` | `_set_done()` |
| `DECLINED`, `DENIED`, `VOIDED` | `_set_canceled()` |
| `FAILED` | `_set_error(...)` |

If `notification_data` is empty: sets `_set_canceled(state_message="The customer left the payment page.")` — this handles the case where the PayPal popup is closed without completing payment.

---

## Constants (`const.py`)

### Supported Currencies

```python
('AUD', 'BRL', 'CAD', 'CNY', 'CZK', 'DKK', 'EUR', 'HKD', 'HUF', 'ILS', 'JPY',
 'MYR', 'MXN', 'TWD', 'NZD', 'NOK', 'PHP', 'PLN', 'GBP', 'RUB', 'SGD', 'SEK',
 'CHF', 'THB', 'USD')
```

### Default Payment Method Codes

```python
{'paypal'}  # Single PayPal button
```

### Payment Status Mapping

```python
PAYMENT_STATUS_MAPPING = {
    'pending': ('PENDING', 'CREATED', 'APPROVED'),
    'done':    ('COMPLETED', 'CAPTURED'),
    'cancel':  ('DECLINED', 'DENIED', 'VOIDED'),
    'error':   ('FAILED',),
}
```

### Handled Webhook Events

```python
HANDLED_WEBHOOK_EVENTS = [
    'CHECKOUT.ORDER.COMPLETED',          # Payment captured
    'CHECKOUT.ORDER.APPROVED',           # Order approved but not captured
    'CHECKOUT.PAYMENT-APPROVAL.REVERSED', # Approval was reversed
]
```

---

## Utils (`utils.py`)

### `get_normalized_email_account(provider)`

Strips non-ASCII characters (especially `\u200b` zero-width space) from the PayPal email using `encode('ascii', 'ignore').decode('utf-8')`. PayPal requires clean email addresses in API payloads.

### `format_partner_address(partner)`

Returns PayPal-formatted address:
```python
{
    'email_address': <partner.email>,  # always included
    'address': {
        'address_line_1': <street>,
        'address_line_2': <street2>,
        'admin_area_1': <state.code>,
        'admin_area_2': <city>,
        'postal_code': <zip>,
        'country_code': <country.code>,
    }
}
```
Only returns `address` key if `partner.country_id` exists (PayPal requires country).

### `format_shipping_address(tx_sudo)`

Extracts shipping address from `sale_order_ids` or `invoice_ids` (checks for module presence via field existence):
- Returns empty dict if no linked records
- Validates completeness: requires `street`, `city`, `country_id`, and optionally `zip`/`state_id` based on country settings
- Calls `format_partner_address(partner_shipping_id)` with the validated partner

---

## L4: Deep-Dive Notes

### How PayPal Redirect Flow Works

1. Customer clicks PayPal button on Odoo checkout
2. Odoo creates a `payment.transaction` record (state: `pending` or `draft`)
3. Frontend JS calls `/payment/transaction/{id}/get_session_context` → `_get_specific_processing_values` → calls PayPal `POST /v2/checkout/orders`
4. PayPal returns `order_id` (e.g., `7DG58445AB123456G`)
5. Frontend redirects customer to PayPal with `order_id`
6. Customer approves payment on PayPal's site
7. PayPal redirects back to `/payment/paypal/complete_order` with `order_id`
8. Controller calls `POST /v2/checkout/orders/{order_id}/capture` → PayPal captures the payment
9. `_handle_notification_data` sets transaction to `done`
10. Customer redirected to `/payment/status`

### How IPN / Webhook Updates Transactions

PayPal's webhook is the authoritative source for server-to-server notification:

- `CHECKOUT.ORDER.COMPLETED`: The order was captured. Normalized data includes `status: 'COMPLETED'` → `_set_done()`
- `CHECKOUT.ORDER.APPROVED`: The buyer approved the order but PayPal hasn't captured yet. For Orders API with `intent: 'CAPTURE'`, this typically means the order is about to be captured. Normalized data includes `status: 'APPROVED'` → `_set_pending()`
- `CHECKOUT.PAYMENT-APPROVAL.REVERSED`: The buyer reversed the approval. Normalized data includes `status: 'VOIDED'` → `_set_canceled()`

The webhook is processed after the customer completes the redirect flow, so duplicate processing is possible but handled by Odoo's idempotency key on the capture request.

### Access Token Lifecycle

PayPal's OAuth2 tokens expire (typically after 9 hours). Odoo manages this transparently:
- First request after expiry (or within 5-minute buffer): calls `POST /v1/oauth2/token`
- Client credentials: `auth=(client_id, client_secret)` — HTTP Basic auth header
- No `Authorization` header on the token request
- Token and expiry stored in DB fields; next request reads from there

### Difference from Stripe/Adyen: No Tokenization

PayPal's standard checkout does not support saving card details server-side in the same way:
- No `SetupIntent` equivalent for card setup
- No stored `payment.token` records for PayPal (only the payment method `code='paypal'`)
- `support_tokenization` is not set on the provider (defaults to `False`)
- Refunds are processed directly on the capture without needing a stored token

### Idempotency Key Pattern

Odoo uses idempotency keys on PayPal capture requests to prevent duplicate captures:
```python
idempotency_key = payment_utils.generate_idempotency_key(tx_sudo, scope='payment_request_controller')
```
The key is sent as `PayPal-Request-Id` header. PayPal treats requests with the same `PayPal-Request-Id` as idempotent.

### Webhook Verification vs. Return URL Capture

There are two ways the capture confirmation reaches Odoo:
1. **Return URL** (`/payment/paypal/complete_order`): The customer is redirected back from PayPal; the controller calls capture directly
2. **Webhook** (`/payment/paypal/webhook`): PayPal sends `CHECKOUT.ORDER.COMPLETED` server-to-server

Both paths normalize data identically and call `_handle_notification_data`. The webhook serves as a fallback if the customer closes the browser before redirecting.

### `paypal_type` Debug Field

The field `payment.transaction.paypal_type` stores the PayPal `txn_type` from IPN. In Odoo 18's Orders API flow, this is set to `'CAPTURE'` for captured orders (the intent field from the normalized data). It has no functional impact — only used for debugging.

### No Manual Capture

All PayPal payments use `intent: 'CAPTURE'` — there is no separate authorization step. The `_send_capture_request` and `_send_void_request` methods are **not overridden** (inherited from base `payment.transaction`). This means:
- There is no "authorize" step in PayPal
- Void/cancel is handled via `CHECKOUT.PAYMENT-APPROVAL.REVERSED` webhook event (if not yet captured)
- Partial capture is not supported by PayPal in this flow

---

## Routes Summary

| Route | Type | Auth | Purpose |
|-------|------|------|---------|
| `/payment/paypal/complete_order` | JSON POST | public | Capture PayPal order after customer approval; main return handler |
| `/payment/paypal/webhook/` | HTTP POST | public | PayPal IPN/webhook server-to-server notification |

---

## Hooks

```python
# post_init_hook
setup_provider(env, 'paypal')   # Creates payment.provider record

# uninstall_hook
reset_payment_provider(env, 'paypal')  # Removes/demotes provider
```

---

## Relations

- `payment.transaction` → `payment.provider` via `provider_id` (Many2one)
- `payment.transaction` → `payment.method` via `payment_method_id` (Many2one) — resolves to `code='paypal'`

---

## See Also

- [Modules/payment](Modules/payment.md) — Base payment module
- [Modules/payment_stripe](Modules/payment_stripe.md) — Stripe provider for comparison
- [Modules/payment_adyen](Modules/payment_adyen.md) — Adyen provider for comparison
- [Core/API](Core/API.md) — Idempotency key pattern
- [Patterns/Security Patterns](Patterns/Security Patterns.md) — Field groups for credentials
