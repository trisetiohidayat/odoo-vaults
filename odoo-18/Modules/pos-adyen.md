---
Module: pos_adyen
Version: Odoo 18
Type: Integration
Dependencies: point_of_sale
---

# POS Adyen (`pos_adyen`)

## Overview

`pos_adyen` integrates **Adyen payment terminals** with Odoo's Point of Sale. It enables cashiers to send payment requests directly to a physical Adyen card terminal (P400Plus, VX520, etc.) connected via Adyen's cloud Terminal API. The terminal handles the card interaction; Odoo receives the async payment result via webhook.

**Key architectural role:**
- Extends `pos.payment.method` with Adyen-specific fields and terminal configuration
- Extends `pos.config` with tip-on-terminal feature flag
- Provides a controller endpoint for Adyen async payment notifications
- Provides `proxy_adyen_request()` RPC for the POS frontend to communicate with terminals via Odoo server (circumvents CORS restrictions)
- Validates request authenticity using HMAC signatures

---

## Module Structure

```
pos_adyen/
├── models/
│   ├── pos_payment_method.py   # Adyen terminal fields + request methods
│   ├── pos_config.py           # adyen_ask_customer_for_tip field
│   └── res_config_settings.py  # adyen tip setting in POS config wizard
├── controllers/
│   └── main.py                 # /pos_adyen/notification webhook handler
└── __manifest__.py             # depends: point_of_sale; category: Sales/Point of Sale
```

---

## `pos.payment.method` — Extended

### Adyen-Specific Fields

| Field | Type | Notes |
|---|---|---|
| `adyen_api_key` | Char (sensitive) | Adyen API key for server-to-server terminal API calls |
| `adyen_terminal_identifier` | Char | `[TerminalModel]-[SerialNumber]`, e.g., `P400Plus-123456789` |
| `adyen_test_mode` | Boolean | Use Adyen test environment (`test` vs `live`) |
| `adyen_latest_response` | Char | Buffers the latest async notification from Adyen (sudo write) |
| `adyen_event_url` | Char (computed) | Webhook URL: `{base_url}/pos_adyen/notification` — paste into Adyen portal |

### Fields Inherited from `pos.payment.method`

| Field | Inherited From | Notes |
|---|---|---|
| `payment_terminal` | base `pos.payment.method` | Set to `'adyen'` to activate the terminal |

### Key Methods

**`_get_payment_terminal_selection()`** — Extends the base selection with `[('adyen', 'Adyen')]`.

**`_load_pos_data_fields(config_id)`** — Adds `adyen_terminal_identifier` to POS session data.

**`_check_adyen_terminal_identifier()`** (constraint) — Validates uniqueness of `adyen_terminal_identifier` across:
- Same company: raises `ValidationError`
- Different company: raises `ValidationError` with company name (terminals are company-scoped but must not be reused)
- Empty identifier: skipped (no error)

**`_get_payment_terminal_selection()`** — Returns base selection + `[('adyen', 'Adyen')]`.

**`get_latest_adyen_status()`** — Returns the JSON-parsed `adyen_latest_response` for the POS frontend to display. Requires `group_pos_user`.

**`proxy_adyen_request(data, operation=False) -> dict`** — The core proxy method:

1. Validates requester has `group_pos_user` or is `su`
2. Clears `adyen_latest_response` if this is a payment request (avoids stale responses)
3. Validates the request structure using `_is_valid_adyen_request_data()`:
   - `is_capture_data`: capture operation validation
   - `is_adjust_data`: adjust/delayed charge validation
   - `is_cancel_data`: abort request validation
   - `is_payment_request_with_acquirer_data`: standard payment + `SaleToAcquirerData`
   - `is_payment_request_without_acquirer_data`: standard payment, no extra data
4. For payment requests, appends HMAC metadata to `SaleToAcquirerData`
5. Calls `_proxy_adyen_request_direct()`

**`_is_valid_adyen_request_data(provided_data, expected_data) -> bool`** — Recursive structural validator. Uses `UNPREDICTABLE_ADYEN_DATA` sentinel for fields that can vary (amount, currency, transaction ID, etc.).

**`_get_expected_message_header(expected_message_category) -> dict`** — Returns expected `SaleToPOIRequest.MessageHeader` structure with `POIID = self.adyen_terminal_identifier`.

**`_get_expected_payment_request(with_acquirer_data) -> dict`** — Returns the expected full payment request structure for validation.

**`_get_valid_acquirer_data() -> dict`** — Returns `{ 'tenderOption': 'AskGratuity', 'authorisationType': 'PreAuth' }`. These are the mandatory acquirer data fields.

**`_get_hmac(sale_id, service_id, poi_id, sale_transaction_id) -> str`** — Computes HMAC-SHA256 over the transaction tuple using Odoo's `hmac()` utility with scope `'pos_adyen_payment'`.

**`_proxy_adyen_request_direct(data, operation) -> dict`** — Makes the actual HTTP POST to Adyen's Terminal API:
- URL: `https://terminal-api-{environment}.adyen.com/async` (test or live)
- Header: `x-api-key: {adyen_api_key}`
- Timeout: 10 seconds
- Returns `{'error': {...}}` on 401 auth failure, `True` on `'ok'` text response, parsed JSON otherwise

### `_is_write_forbidden` Override

**`_is_write_forbidden(fields)`** — Unconditionally allows writing to `adyen_latest_response` even when the payment method is in a "locked" state (e.g., during session). All other fields remain protected.

---

## `pos.config` — Extended

| Field | Type | Notes |
|---|---|---|
| `adyen_ask_customer_for_tip` | Boolean | Prompt customer for tip on Adyen terminal |

### Constraint: `_check_adyen_ask_customer_for_tip`

If `adyen_ask_customer_for_tip = True`, both `tip_product_id` and `iface_tipproduct` must be configured on the POS. Raises `ValidationError` if not.

---

## `res.config.settings` — Extended

| Field | Type | Notes |
|---|---|---|
| `pos_adyen_ask_customer_for_tip` | Boolean (computed, stored) | Mirrors `pos_config_id.adyen_ask_customer_for_tip` |

**`_compute_pos_adyen_ask_customer_for_tip()`** — `compute`/`store` on the settings wizard:
- If `pos_iface_tipproduct` is set: mirrors `pos_config_id.adyen_ask_customer_for_tip`
- If `pos_iface_tipproduct` is not set: sets `pos_adyen_ask_customer_for_tip = False`

---

## Controller: `PosAdyenController` (`/pos_adyen/notification`)

### Route: `POST /pos_adyen/notification`

**Auth:** `public` (no login required)
**Type:** `json`
**CSRF:** `False`
**Save session:** `False`

Receives asynchronous **payment responses** from Adyen's cloud service. This is Adyen's mechanism for notifying Odoo that a card payment was completed.

**Processing steps:**

1. **Initial validation** — Checks for `SaleToPOIResponse` key; ignores all other notifications.
2. **Message header validation** — Verifies `ProtocolVersion=3.0`, `MessageClass=Service`, `MessageType=Response`, `MessageCategory=Payment`, `POIID` is present.
3. **Terminal lookup** — Searches `pos.payment.method` by `adyen_terminal_identifier`; logs warning if terminal not found.
4. **HMAC validation** — Extracts `metadata.pos_hmac` from `AdditionalResponse`, compares against `adyen_pm._get_hmac(...)` using `consteq()` (timing-safe comparison). If invalid, logs warning and ignores.
5. **HMAC removal** — Strips the HMAC from `AdditionalResponse` before storing (prevents replay attacks).
6. **Response storage + notification** — Writes `adyen_latest_response` to the payment method and broadcasts `ADYEN_LATEST_RESPONSE` to the POS session via `_notify()`.
7. **Response** — Returns `[accepted]` (required by Adyen's protocol for guaranteed delivery).

**L4 — Transaction ID format:**
The `SaleTransactionID.TransactionID` is expected to be `{pos_session_id}--{uuid}` (split on `--`). The first part is the `pos.session` ID used to route the notification to the correct session.

**L4 — Why `save_session=False`:**
The webhook is called from an external service (Adyen's servers). Saving the session would cause Odoo to try to restore the current user's session context, which is unnecessary and could cause side effects.

**L4 — HMAC Security:**
The HMAC is computed server-side by `_get_hmac()` using Odoo's `hmac()` utility with a server-secret scope. When Adyen echoes it back in the notification, `_proxy_adyen_request_direct()` previously appended it to `SaleToAcquirerData` before forwarding the payment request to the terminal. This creates a round-trip that proves the notification originated from the same transaction lifecycle.

---

## Payment Flow (HPP vs. Terminal)

Odoo 18's `pos_adyen` uses **Terminal API** (PWS / Point-of-Sale Web Service), NOT Adyen's Hosted Payment Page (HPP).

### Terminal (PWS) Flow

```
1. Cashier enters amount in Odoo POS
2. POS frontend calls pos.payment.method.proxy_adyen_request()
   via /pos_adyen/proxy_adyen_request RPC
3. Odoo server formats SaleToPOIRequest (Payment request)
   and adds HMAC metadata to SaleToAcquirerData
4. Odoo server POSTs to https://terminal-api-{env}.adyen.com/async
5. Adyen routes request to physical terminal via internet/LAN
6. Customer taps/inserts card on terminal; enters PIN if required
7. Terminal sends result to Adyen cloud
8. Adyen POSTs async notification to /pos_adyen/notification
9. Odoo stores response in adyen_latest_response
10. Odoo broadcasts ADYEN_LATEST_RESPONSE to POS session
11. POS frontend reads response via get_latest_adyen_status()
12. Order marked as paid; receipt printed
```

### HPP vs. Terminal Comparison

| Aspect | HPP (Hosted Payment Page) | Terminal (PWS) |
|---|---|---|
| Card entry | Customer enters on web/mobile | Customer uses physical terminal |
| Interaction | Redirect to Adyen hosted page | In-store hardware terminal |
| POS integration | eCommerce / online orders | Physical POS |
| Tip handling | Not applicable | Terminal prompts for tip |
| Odoo module | `payment_adyen` (payment acquirer) | `pos_adyen` (payment terminal) |
| Notification | Server-side webhook | `/pos_adyen/notification` |

---

## Tip Handling at Adyen Terminals

When `pos.config.adyen_ask_customer_for_tip = True`:

1. The POS sends the base transaction amount and flags `tenderOption: AskGratuity` in the payment request
2. The terminal prompts the customer to add a tip (preset amounts shown on screen)
3. The customer selects or enters a tip amount on the terminal
4. The total (amount + tip) is charged to the card
5. The tip is captured as a separate line in Odoo's accounting

The tip is processed as part of the Adyen payment capture — Odoo records it using the configured `tip_product_id`.

> **Note:** The tip product must be configured in POS settings (`iface_tipproduct` + `tip_product_id`) for the tip feature to work.

---

## Error Handling

| Error | Cause | Response |
|---|---|---|
| Terminal not found | `adyen_terminal_identifier` not in DB | Logged warning; notification ignored |
| HMAC mismatch | Tampered or replayed notification | Logged warning; notification ignored |
| Missing response fields | Malformed Adyen notification | Logged warning; notification ignored |
| HTTP 401 | Invalid Adyen API key | `{'error': {'status_code': 401, 'message': ...}}` returned to POS |
| Adyen returns `'ok'` | Success acknowledgment | `True` returned |
| Request timeout | Terminal unreachable | HTTP 504 via `requests.post(timeout=10)` |

---

## L4: Adyen Request Validation Deep Dive

The `proxy_adyen_request()` method performs deep structural validation to prevent abuse:

1. **MessageHeader**: Verifies `ProtocolVersion`, `MessageClass`, `MessageType`, `MessageCategory`, and `POIID` (must match the configured terminal)
2. **PaymentRequest amounts**: Validates `Currency` and `RequestedAmount` match expected format (values are `UNPREDICTABLE_ADYEN_DATA` since amounts vary)
3. **SaleTransactionID**: Validates format; values are `UNPREDICTABLE_ADYEN_DATA`
4. **SaleToAcquirerData**: If present, validates all key-value pairs against known-good values (`tenderOption`, `authorisationType`); rejects unexpected keys
5. **Abort/Capture/Adjust operations**: Each has specific expected field structures validated separately

This validation ensures the Odoo server only acts as a transparent proxy for legitimate Adyen payment traffic — preventing attackers from crafting fake payment notifications.

---

## Related Documentation

- [Modules/Point of Sale](modules/point-of-sale.md) — POS core, payment methods
- [Modules/Account](modules/account.md) — Payment journal entries, tips
- [Core/HTTP Controller](core/http-controller.md) — `@http.route` decorator, JSON responses

#odoo #odoo18 #pos_adyen #payment-terminal #adyen #pos #tip #hmac
