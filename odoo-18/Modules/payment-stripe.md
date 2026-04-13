---
Module: payment_stripe
Version: Odoo 18
Type: Integration
Tags: #payment, #stripe, #provider, #integration, #webhook, #sca, #stripe-connect, #express-checkout
---

# Payment Provider: Stripe (`payment_stripe`)

> **Source:** `~/odoo/odoo18/odoo/addons/payment_stripe/`
> **Manifest:** `version: 2.0`, `category: Accounting/Payment Providers`, `depends: payment`
> **License:** LGPL-3

An Irish-American payment provider covering the US and many other countries. Implements Stripe's PaymentIntents API and SetupIntents API (version `2019-05-16`). Supports card, SEPA, BACS, Bancontact, iDEAL, Giropay, P24, and more. Full tokenization (saved cards), manual capture, partial refunds, and SCA/3DS2 via Stripe Elements. Includes Stripe Connect onboarding hooks.

---

## Module Structure

```
payment_stripe/
├── models/
│   ├── __init__.py
│   ├── payment_provider.py      # payment.provider extension + Stripe Connect hooks
│   ├── payment_transaction.py   # payment.transaction extension
│   └── payment_token.py         # payment.token extension + SCA migration
├── controllers/
│   ├── __init__.py
│   ├── main.py                  # StripeController (return URL, webhook)
│   └── onboarding.py            # OnboardingController (Stripe Connect onboarding)
├── const.py                     # API version, currency decimals, status mapping, country list
├── utils.py                     # get_publishable_key, get_secret_key, include_shipping_address
├── data/
│   └── payment_provider_data.xml
└── static/src/**/*
```

---

## Models

### `payment.provider` (Extended)

Inherits `payment.provider` and registers `code = 'stripe'`. Stores Stripe credentials and implements the full Stripe Connect onboarding flow.

#### Fields

| Field | Type | Required | Groups | Description |
|-------|------|----------|--------|-------------|
| `code` | `Selection` | Yes | — | Extends selection with `('stripe', "Stripe")` |
| `stripe_publishable_key` | `Char` | Yes (if code=stripe) | — | Public key for frontend Stripe.js / Stripe Elements identification |
| `stripe_secret_key` | `Char` | Yes (if code=stripe) | `base.group_system` | Secret key for server-side Stripe API calls |
| `stripe_webhook_secret` | `Char` | No | `base.group_system` | `whsec_...` signing secret for webhook signature verification |

#### Feature Support Flags

| Feature | Support Level |
|---------|--------------|
| `support_express_checkout` | `True` — Apple Pay, Google Pay express buttons |
| `support_manual_capture` | `'full_only'` — Only full capture is supported (no partial) |
| `support_refund` | `'partial'` — Partial refunds |
| `support_tokenization` | `True` — Saved cards via SetupIntent |

#### Constraints

**`_check_state_of_connected_account_is_never_test`** — `(@api.constrains('state', 'stripe_publishable_key', 'stripe_secret_key'))`

Raises `ValidationError` if a provider with a connected Stripe account (Stripe Connect) is set to `'test'` state. The constraint is also triggered by writing on `state` so connected-account modules can indirectly fire it.

Stub method `_stripe_has_connected_account()` returns `False`; hook for `payment_stripe_connect`.

**`_check_onboarding_of_enabled_provider_is_completed`** — `(@api.constrains('state'))`

Raises `ValidationError` if provider is set to `'enabled'` while Stripe Connect onboarding is still ongoing.

Stub method `_stripe_onboarding_is_ongoing()` returns `False`; hook for `payment_stripe_connect`.

#### Action Methods

**`action_stripe_connect_account(menu_id=None)`**

Creates a Stripe Connect standard account and redirects to the onboarding link.

1. Checks `company_id.country_id.code` is in `const.SUPPORTED_COUNTRIES`
2. If `state == 'enabled'`: validates onboarding step, closes window
3. If `state != 'enabled'`: creates connected account via `_stripe_make_proxy_request('accounts', ...)`
4. Generates account link via `_stripe_create_account_link(connected_account_id, menu_id)`
5. Redirects user to Stripe-hosted onboarding URL

**`action_stripe_create_webhook()`**

Creates a Stripe webhook endpoint programmatically:

- Target URL: `{base_url}/payment/stripe/webhook`
- Events: `const.HANDLED_WEBHOOK_EVENTS`
- API version: `const.API_VERSION`
- Writes returned `secret` to `stripe_webhook_secret`
- Returns `display_notification` action

**`action_stripe_verify_apple_pay_domain()`**

Sends domain to `POST /apple_pay/domains` in Stripe API. Raises `UserError` if test keys are used (Stripe returns `livemode: false` but HTTP 200).

#### Business Methods — Payment Flow

**`_stripe_make_request(endpoint, payload=None, method='POST', offline=False, idempotency_key=None)`**

Core HTTP client for all Stripe API calls.

- URL: `https://api.stripe.com/v1/{endpoint}`
- Headers: `Authorization: Bearer {secret_key}`, `Stripe-Version: const.API_VERSION`
- `Idempotency-Key` header added for POST requests with `idempotency_key`
- HTTP 4xx with JSON `error` field raises `ValidationError` (unless `offline=True`)
- HTTP connection error raises `ValidationError`
- Timeout: 60 seconds
- If `offline=True`: errors are not raised — returned as response dict for flow-specific handling

**`_get_stripe_extra_request_headers()`** → `{}`

Stub for Stripe Connect — override in `payment_stripe_connect` to inject `Stripe-Account: {connected_account_id}`.

**`_get_stripe_webhook_url()`**

Returns `{base_url}/payment/stripe/webhook`.

#### Business Methods — Stripe Connect Onboarding

**`_stripe_fetch_or_create_connected_account()`**

Calls `_stripe_make_proxy_request('accounts', payload=self._stripe_prepare_connect_account_payload())`. Proxies through Odoo's server (not direct) to avoid exposing credentials.

**`_stripe_prepare_connect_account_payload()`**

Builds standard Stripe Connect account creation payload:
```python
{
    'type': 'standard',
    'country': <mapped country code>,
    'email': <company email>,
    'business_type': 'company',
    'company[address][city]': ...,
    'company[address][country]': ...,
    'company[address][line1]': ...,
    'company[address][line2]': ...,
    'company[address][postal_code]': ...,
    'company[address][state]': ...,
    'company[name]': ...,
    'business_profile[name]': ...,
}
```

**`_stripe_create_account_link(connected_account_id, menu_id)`**

Creates an AccountLink with `type: 'account_onboarding'`. Returns the `url` for Stripe-hosted onboarding. Uses `OnboardingController` return/refresh URLs.

**`_stripe_make_proxy_request(endpoint, payload=None, version=1)`**

Makes JSON-RPC 2.0 request to `https://stripe.api.odoo.com/api/stripe/{version}/{endpoint}`. The proxy is an Odoo server-side component that forwards requests to Stripe with additional context (`proxy_data`). This avoids exposing `stripe_secret_key` to the client.

**`_stripe_prepare_proxy_data(stripe_payload=None)`** → `{}`

Stub — override in `payment_stripe_connect` to add connected account context.

#### Business Methods — Inline Form

**`_stripe_get_publishable_key()`** → returns `stripe_utils.get_publishable_key(self.sudo())`

**`_stripe_get_inline_form_values(amount, currency, partner_id, is_validation, payment_method_sudo=None, **kwargs)`** → JSON string

Returns values for the Stripe.js inline form:
```python
{
    'publishable_key': ...,
    'currency_name': <lower currency name>,
    'minor_amount': <amount in minor units>,
    'capture_method': 'manual' | 'automatic',
    'billing_details': {
        'name': <partner.name>,
        'email': <partner.email>,
        'phone': <partner.phone>,
        'address': {<full address dict>}
    },
    'is_tokenization_required': <bool>,
    'payment_methods_mapping': <const.PAYMENT_METHODS_MAPPING>
}
```

**`_get_default_payment_method_codes()`** → `{'card', 'bancontact', 'eps', 'giropay', 'ideal', 'p24', 'visa', 'mastercard', 'amex', 'discover'}`

---

### `payment.transaction` (Extended)

Inherits `payment.transaction`. Creates Stripe PaymentIntents/SetupIntents, processes webhooks, handles capture, void, and refund.

#### Processing Values

**`_get_specific_processing_values(processing_values)`**

For `operation != 'online_token'` and `provider_code == 'stripe'`:
1. Calls `_stripe_create_intent()` to create a PaymentIntent (or SetupIntent for validation)
2. Returns:
```python
{
    'client_secret': <intent['client_secret']>,
    'return_url': <base_url>/payment/stripe/return?reference=<ref>
}
```

**`_get_specific_secret_keys()`**

Returns `{'client_secret': None}` for Stripe — prevents `client_secret` from being logged.

#### Intent Creation — `_stripe_create_intent()`

Branches on `self.operation`:

- `'validation'`: calls `_stripe_make_request('setup_intents', payload=_stripe_prepare_setup_intent_payload())`
- `'online_direct'`, `'online_token'`, `'offline'`: calls `_stripe_make_request('payment_intents', payload=_stripe_prepare_payment_intent_payload(), offline=(op=='offline'), idempotency_key=...)`

If response contains `error`: logs, sets transaction in error, and extracts the embedded intent object (if any).

**`_stripe_prepare_payment_intent_payload()`**

```python
{
    'amount': <minor_units>,
    'currency': <lower currency name>,
    'description': <reference>,
    'capture_method': 'manual' | 'automatic',
    'payment_method_types[]': <mapped payment method type>,
    'expand[]': 'payment_method',
    **shipping_address_from_sale_order_or_invoice
}
```

For `operation in ['online_token', 'offline']`:
```python
{
    'confirm': True,
    'customer': <token.provider_ref>,     # Stripe customer ID
    'off_session': True,
    'payment_method': <token.stripe_payment_method>,  # Stripe PaymentMethod ID
    'mandate': <token.stripe_mandate or None>,
}
```
Also calls `token_id._stripe_sca_migrate_customer()` if pre-SCA token.

For new payments with tokenization:
```python
{'customer': <new Stripe customer ID>, 'setup_future_usage': 'off_session'}
```
Plus mandate options if Indian currency.

**`_stripe_prepare_setup_intent_payload()`**

```python
{
    'customer': <new Stripe customer>,
    'description': <reference>,
    'payment_method_types[]': <mapped payment method type>,
    # + mandate options for Indian currencies
}
```

**`_stripe_create_customer()`**

Creates a Stripe `customer` object with full address, email, phone, name, and description. Used both for PaymentIntents (new customers) and SetupIntents.

#### Mandate Handling (India)

**`_stripe_prepare_mandate_options()`**

For Indian-supported currencies (`USD`, `EUR`, `GBP`, `SGD`, `CAD`, `CHF`, `SEK`, `AED`, `JPY`, `NOK`, `MYR`, `HKD`), adds `payment_method_options[card][mandate_options]` with:
- `reference`: transaction reference
- `amount_type`: `'maximum'`
- `amount`: max amount (default 15000 INR if not specified)
- `start_date`: Unix timestamp
- `interval`: `'sporadic'` or from mandate values
- `supported_types[]`: `'india'`
- `end_date`: optional Unix timestamp

#### Tokenization

**`_stripe_tokenize_from_notification_data(notification_data)`**

Extracts `payment_method` and `customer` from notification_data:
- For `operation == 'online_direct'`: `notification_data['payment_intent']['customer']` + charge's `mandate`
- For `operation == 'validation'`: `notification_data['setup_intent']['customer']`
- If the selected payment method generated a sub-method (e.g., SEPA): fetches `GET /customers/{customer_id}/payment_methods`

Creates `payment.token`:
```python
{
    'provider_id': ...,
    'payment_method_id': ...,
    'payment_details': <last4 from payment_method[type]>,
    'partner_id': ...,
    'provider_ref': <Stripe customer ID>,
    'stripe_payment_method': <Stripe PaymentMethod ID>,
    'stripe_mandate': <mandate string or None>,
}
```

#### S2S / Offline Payment Flow

**`_send_payment_request()`**

1. Calls `_stripe_create_intent()` which uses token's Stripe customer and PaymentMethod to confirm payment
2. Fetches PaymentMethod and injects into notification_data
3. Calls `_handle_notification_data`

#### Capture

**`_send_capture_request(amount_to_capture=None)`**

```
POST /payment_intents/{provider_reference}/capture
```

Fetches the updated PaymentIntent, injects into notification_data, calls `_handle_notification_data`.

#### Void / Cancel

**`_send_void_request(amount_to_void=None)`**

```
POST /payment_intents/{provider_reference}/cancel
```

#### Refund

**`_send_refund_request(amount_to_refund=None)`**

1. Creates child `refund_tx` (negative amount)
2. Sends:
```python
{'payment_intent': <provider_reference>, 'amount': <minor_units positive>}
```
3. Injects refund data into notification_data via `StripeController._include_refund_in_notification_data`
4. Calls `_handle_notification_data('stripe', notification_data)`

#### Webhook Processing

**`_get_tx_from_notification_data(provider_code, notification_data)`**

- Primary lookup: `reference` → search by `reference` field
- Fallback for `charge.refund.updated`: `object_id` (the refund ID) → search by `provider_reference`

**`_process_notification_data(notification_data)`**

Extracts `payment_method` from notification_data (may be dict from webhook or string from capture/void):

```python
# payment_method dict:
payment_method_type = payment_method.get('type')
if card: payment_method_type = payment_method['card']['brand']
```

Maps to `payment.method` via `const.PAYMENT_METHODS_MAPPING`.

Status mapping (`const.STATUS_MAPPING`):

| Stripe Status | Odoo State |
|--------------|-----------|
| `requires_confirmation`, `requires_action` | (no-op, draft) |
| `processing`, `pending` | `_set_pending()` |
| `requires_capture` | `_set_authorized()` |
| `succeeded` | `_set_done()` + tokenize if needed |
| `canceled` | `_set_canceled()` |
| `requires_payment_method`, `failed` | `_set_error(message)` |

For refunds (`operation == 'refund'` and `status == 'succeeded'`): triggers `payment.cron_post_process_payment_tx`.

---

### `payment.token` (Extended)

| Field | Type | Description |
|-------|------|-------------|
| `stripe_payment_method` | `Char` (readonly) | The Stripe PaymentMethod ID (e.g., `pm_xxx`). Used for S2S payments with pre-SCA tokens. |
| `stripe_mandate` | `Char` (readonly) | The Stripe Mandate ID for recurring payments (India / SEPA). |

#### Pre-SCA Migration

**`_stripe_sca_migrate_customer()`**

For tokens created before Stripe's SCA requirement (Pre-SCA tokens only had `provider_ref = customer_id`). For these:
1. Fetches `GET /payment_methods?customer={provider_ref}&type=card&limit=1`
2. Writes the returned PaymentMethod ID to `stripe_payment_method`
3. Next S2S payment will use the PaymentMethod directly instead of the customer default

---

## Controllers

### `StripeController` (`controllers/main.py`)

#### Routes

| Route | Type | Auth | Purpose |
|-------|------|------|---------|
| `/payment/stripe/return` | HTTP GET | public | Post-payment return; fetches PaymentIntent/SetupIntent from Stripe |
| `/payment/stripe/webhook` | HTTP POST | public | Stripe webhook receiver |
| `/.well-known/apple-developer-merchantid-domain-association` | HTTP | public | Apple Pay domain verification |

#### Return URL Processing

**`stripe_return(**data)`**

1. Looks up transaction by `reference` in `data`
2. For non-validation: fetches `GET /payment_intents/{payment_intent_id}?expand[]=payment_method`, injects into `data`
3. For validation: fetches `GET /setup_intents/{setup_intent_id}?expand[]=payment_method`, injects into `data`
4. Calls `tx._handle_notification_data('stripe', data)`
5. Redirects to `/payment/status`

#### Webhook Processing

**`stripe_webhook()`**

1. Parses JSON event
2. If `event.type` not in `HANDLED_WEBHOOK_EVENTS`: returns `''` (ack)
3. Extracts `event.data.object` (could be PaymentIntent, SetupIntent, Charge, or Refund)
4. Verifies signature with `_verify_notification_signature()`
5. Branches on event type:
   - `payment_intent.*`: fetches PaymentMethod, injects, calls `_handle_notification_data`
   - `setup_intent.succeeded`: fetches PaymentMethod, injects, calls `_handle_notification_data`
   - `charge.refunded`: paginates all refunds, creates child refund transactions for each unprocessed refund, calls `_handle_notification_data` on each
   - `charge.refund.updated`: injects refund object into data, calls `_handle_notification_data` (for status updates like failed refund)
6. Returns `''`

#### Signature Verification

**`_verify_notification_signature(tx_sudo)`**

1. Parses `Stripe-Signature` header into `{t: timestamp, v1: signature, ...}`
2. Checks timestamp age: raises `Forbidden` if > 10 minutes old (`WEBHOOK_AGE_TOLERANCE = 600s`)
3. Computes: `HMAC-SHA256(webhook_secret, "{timestamp}.{raw_body}")`
4. Compares with `hmac.compare_digest` (timing-safe)

#### Refund Creation from Webhook

**`_create_refund_tx_from_refund(source_tx_sudo, refund_object)`**

Converts Stripe refund `amount` (minor units) to major units using `payment_utils.to_major_currency_units()`, then calls `source_tx._create_child_transaction(converted_amount, is_refund=True)`.

### `OnboardingController` (`controllers/onboarding.py`)

| Route | Type | Auth | Purpose |
|-------|------|------|---------|
| `/payment/stripe/onboarding/return` | HTTP GET | user | Post-onboarding return; validates step, redirects to provider form |
| `/payment/stripe/onboarding/refresh` | HTTP GET | user | Onboarding link expired; generates new AccountLink and redirects |

---

## Constants (`const.py`)

### API Version

`API_VERSION = '2019-05-16'` — Stripe API version used throughout this module.

### Proxy URL

`PROXY_URL = 'https://stripe.api.odoo.com/api/stripe/'` — Odoo server proxy for Stripe API calls.

### Default Payment Method Codes

```python
{'card', 'bancontact', 'eps', 'giropay', 'ideal', 'p24', 'visa', 'mastercard', 'amex', 'discover'}
```

### Payment Method Mapping

```python
PAYMENT_METHODS_MAPPING = {
    'ach_direct_debit': 'us_bank_account',
    'bacs_direct_debit': 'bacs_debit',
    'becs_direct_debit': 'au_becs_debit',
    'sepa_direct_debit': 'sepa_debit',
    'afterpay': 'afterpay_clearpay',
    'clearpay': 'afterpay_clearpay',
    'cash_app_pay': 'cashapp',
    'mobile_pay': 'mobilepay',
    'unknown': 'card',  # For express checkout
}
```

### Status Mapping

```python
STATUS_MAPPING = {
    'draft':      ('requires_confirmation', 'requires_action'),
    'pending':    ('processing', 'pending'),
    'authorized': ('requires_capture',),
    'done':       ('succeeded',),
    'cancel':     ('canceled',),
    'error':      ('requires_payment_method', 'failed'),
}
```

### Handled Webhook Events

```python
HANDLED_WEBHOOK_EVENTS = [
    'payment_intent.processing',
    'payment_intent.amount_capturable_updated',
    'payment_intent.succeeded',
    'payment_intent.payment_failed',
    'payment_intent.canceled',
    'setup_intent.succeeded',
    'charge.refunded',         # Refund created in Stripe dashboard
    'charge.refund.updated',   # Refund status changed
]
```

### Indian Mandate Currencies

`['USD', 'EUR', 'GBP', 'SGD', 'CAD', 'CHF', 'SEK', 'AED', 'JPY', 'NOK', 'MYR', 'HKD']`

### Country Support

Full list of ~50+ countries in `SUPPORTED_COUNTRIES`. France territories (MQ, GP, GF, RE, YT, MF) map to `FR` in `COUNTRY_MAPPING`.

### Currency Decimals (Non-Standard)

```python
{'ISK': 2, 'UGX': 2, 'MGA': 0}  # ISK and UGX are zero-decimal in ISO but have 2 decimals in Stripe
```

---

## L4: Deep-Dive Notes

### How Stripe Payment Flow Works

1. **Checkout page** loads Stripe.js with the publishable key from `_stripe_get_publishable_key()`
2. Frontend calls Odoo's `_get_specific_processing_values` → `_stripe_create_intent()` creates a PaymentIntent
3. Odoo returns `client_secret` to frontend
4. Frontend uses `stripe.confirmPayment()` with the client secret (card data encrypted by Stripe.js — never touches Odoo server)
5. Stripe returns result; frontend calls `/payment/stripe/return` with `payment_intent` in URL params
6. `StripeController.stripe_return` fetches the PaymentIntent from Stripe API
7. `_handle_notification_data` updates transaction state
8. If `tokenize=True`: token created from `payment_intent.customer` + `payment_intent.payment_method`

### Webhook Verification

Stripe uses **HMAC-SHA256 with timestamp** to sign webhook payloads:
- Header: `Stripe-Signature: t=1720000000,v1=abc123...`
- Signed payload: `"{timestamp}.{raw_body}"`
- Expected: `HMAC-SHA256(webhook_secret, signed_payload)`
- Age tolerance: 10 minutes (prevents replay attacks)

### Stripe Connect (Hook Architecture)

The base module provides stubs that `payment_stripe_connect` overrides:
- `_stripe_has_connected_account()` → returns `True`
- `_stripe_onboarding_is_ongoing()` → checks if onboarding incomplete
- `_stripe_get_extra_request_headers()` → injects `Stripe-Account` header
- `_stripe_prepare_proxy_data()` → injects connected account into proxy call
- `_stripe_get_publishable_key()` → could be the connected account's key

The proxy at `https://stripe.api.odoo.com/api/stripe/` acts as an intermediary for:
- Account creation (`POST /accounts`)
- AccountLink generation (`POST /account_links`)
- All payment operations (to route through the connected account)

### `capture_manually = 'full_only'`

Unlike Adyen, Stripe's manual capture is `'full_only'`. This means:
- `capture_method: 'manual'` means the full amount must be captured in one operation
- Partial capture is not supported at the Stripe API level (Odoo still supports partial capture by creating multiple capture child transactions, each capturing part of the authorized amount)

### S2S / Offline Payment Flow

For tokenized (saved card) payments:
1. `operation == 'offline'` or `'online_token'`
2. `_stripe_create_intent()` uses `confirm: True, off_session: True, payment_method: <stripe_payment_method>`
3. Stripe charges the card without requiring the customer to re-enter details
4. If pre-SCA token: `_stripe_sca_migrate_customer()` fetches the PaymentMethod first
5. Indian currencies: mandate options added for recurring authorization

### How Refund Works

1. User triggers refund → `_send_refund_request` creates child `refund_tx`
2. `POST /refunds` with `payment_intent: <provider_reference>, amount: <minor_units>`
3. For Odoo-initiated refunds: `_handle_notification_data` processes via StripeController injection
4. For Stripe-initiated refunds (dashboard): `charge.refunded` webhook event:
   - Paginated fetch of all refunds on the charge
   - For each refund without a corresponding Odoo child transaction: create one
5. `charge.refund.updated`: handles status changes on already-processed refunds (e.g., refund failed because card expired)

### Apple Pay Domain Verification

Stripe requires domain verification to enable Apple Pay. The route `/.well-known/apple-developer-merchantid-domain-association` serves the verification file. The `action_stripe_verify_apple_pay_domain` button calls `POST /apple_pay/domains` on Stripe — this only works with live credentials.

---

## Hooks

```python
# post_init_hook
payment.setup_provider(env, 'stripe')   # Creates payment.provider record

# uninstall_hook
payment.reset_payment_provider(env, 'stripe')  # Removes/demotes provider
```

---

## Relations

- `payment.transaction` → `payment.provider` via `provider_id`
- `payment.transaction` → `payment.token` via `token_id`
- `payment.token` → `payment.provider` via `provider_id`
- `payment.token` → `res.partner` via `partner_id`

---

## See Also

- [Modules/payment](Modules/payment.md) — Base payment module
- [Modules/payment_adyen](Modules/payment_adyen.md) — Adyen provider for comparison
- [Modules/payment_paypal](Modules/payment_paypal.md) — PayPal provider
- [Core/API](Core/API.md) — Access token, idempotency key patterns
- [Patterns/Security Patterns](Patterns/Security Patterns.md) — Field groups for credentials
