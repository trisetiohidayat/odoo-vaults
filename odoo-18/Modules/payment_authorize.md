---
Module: payment_authorize
Version: 18.0.0
Type: addon
Tags: #odoo18 #payment_authorize #payment
---

## Overview

`payment_authorize` integrates Odoo with Authorize.Net (SIM and CIM APIs). Supports credit card authorization, capture, voiding, refunding, and tokenized (Customer Profile) payments. Key distinguishing feature: per-transaction `authorize()` vs `auth_and_capture()` control, with manual capture support (`capture_manually` provider flag). Uses AuthorizeAPI class for all HTTP communication with Authorize.Net XML API.

## Models

### payment.provider (extends base)
**Inheritance:** `payment.provider` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| code | selection | Adds `('authorize', 'Authorize.Net')`. `ondelete='set default'` |
| authorize_login | Char | API Login ID (required_if_provider='authorize') |
| authorize_transaction_key | Char | API Transaction Key (required_if_provider='authorize', groups=base.group_system) |
| authorize_signature_key | Char | API Signature Key (required_if_provider='authorize', groups=base.group_system) |
| authorize_client_key | Char | API Client Key (public key for inline form; optional, auto-fetched via `action_update_merchant_details`) |

**Constraints:**

| Constraint | Description |
|------------|-------------|
| `_limit_available_currency_ids` | Only one currency allowed per Authorize.Net account (per their docs: "One gateway account is required for each currency") |

**Feature Support Fields:** `support_manual_capture='full_only'`, `support_refund='full_only'`, `support_tokenization=True`

### payment.provider Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_feature_support_fields | self | None | Enables manual capture (full_only), refund (full_only), tokenization |
| action_update_merchant_details | self | dict (action) | Calls `AuthorizeAPI.test_authenticate()` then `merchant_details()`. Updates `available_currency_ids` and `authorize_client_key` from merchant API response |
| _get_validation_amount | self | float | Returns `0.01` (Authorize.Net requires non-zero amount for auth-only transactions) |
| _authorize_get_inline_form_values | self | str (JSON) | Returns `json.dumps` of `{state, login_id, client_key}` for inline form rendering |
| _get_default_payment_method_codes | self | set | Returns `{'ach_direct_debit', 'card', 'visa', 'mastercard', 'amex', 'discover'}` |

### payment.transaction (extends base)
**Inheritance:** `payment.transaction` (classic `_inherit`)

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_specific_processing_values | self, processing_values | dict | Returns `{'access_token': generated_token}` for inline form validation |
| _authorize_create_transaction_request | self, opaque_data | dict | Creates either `authorize()` or `auth_and_capture()` request based on `capture_manually` or `operation=='validation'` |
| _send_payment_request | self | None | Sends tokenized payment request. Checks `authorize_profile` exists. Uses `authorize()` or `auth_and_capture()` via token. Handles response via `_handle_notification_data` |
| _send_refund_request | self, amount_to_refund=None | recordset | Full refund flow: retrieves tx details, checks current state (voided/refunded/authorized/captured), then voids (authorized) or refunds (captured). Handles all Authorize.Net refund edge cases |
| _send_capture_request | self, amount_to_capture=None | recordset | Sends `priorAuthCaptureTransaction` to Authorize for previously authorized payment |
| _send_void_request | self, amount_to_void=None | recordset | Sends `voidTransaction` to Authorize for authorized (not captured) payment |
| _get_tx_from_notification_data | self, provider_code, notification_data | recordset | Looks up by `reference` field |
| _process_notification_data | self, notification_data | None | Handles full Authorize.Net response lifecycle. Maps `x_response_code`: '1' (approved) with `x_type`: 'auth_capture'/'prior_auth_capture' → done, 'auth_only' → authorized (voided if validation), 'void' → canceled, 'refund' → done; '2' (declined) → canceled; '4' (held) → pending; else error. Also handles tokenization via `_authorize_tokenize()` on done/authorized |
| _authorize_tokenize | self | None | Creates customer profile + payment profile on Authorize.net, stores `authorize_profile` (profile_id) on `payment.token` |

### payment.token (extends base)
**Inheritance:** `payment.token` (classic `_inherit`)

| Field | Type | Description |
|-------|------|-------------|
| authorize_profile | Char | Authorize.Net Customer Profile ID (created per-partner/token combination) |

### AuthorizeAPI (plain Python class, no Odoo model)
**Not an Odoo model — plain utility class instantiated with a provider record.**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| __init__ | provider | None | Sets `self.url` (production or test endpoint), `self.state`, `self.name` (authorize_login), `self.transaction_key` |
| _make_request | operation, data=None | dict | JSON-RPC-style POST to Authorize.Net XML API. Includes merchantAuthentication. Returns error dict or full response |
| _format_response | response, operation | dict | Formats response to virtual `_format_response` format with `x_response_code`, `x_trans_id`, `x_type`, `payment_method_code` |
| create_customer_profile | partner, transaction_id | dict | Creates CIM profile from existing transaction. Returns `profile_id`, `payment_profile_id`, `payment_details` (last 4). Makes 2 API calls |
| delete_customer_profile | profile_id | dict | Deletes CIM profile |
| authorize | tx, token=None, opaque_data=None | dict | Auth-only transaction |
| auth_and_capture | tx, token=None, opaque_data=None | dict | Immediate capture transaction |
| _prepare_tx_data | token=None, opaque_data=False | dict | Builds payment profile or opaque data payload |
| _prepare_authorization_transaction_request | transaction_type, tx_data, tx | dict | Builds full transaction request with billTo (for non-tokenized), order, customer, customerIP |
| get_transaction_details | transaction_id | dict | Retrieves full transaction details |
| capture | transaction_id, amount | dict | Prior-auth capture |
| void | transaction_id | dict | Void transaction |
| refund | transaction_id, amount, tx_details | dict | Refund transaction (requires card number from tx_details) |
| merchant_details | self | dict | Fetches merchant details + public client key |
| test_authenticate | self | dict | Validates credentials |

## Security / Data

**Security:** `authorize_transaction_key`, `authorize_signature_key` fields restricted to `base.group_system`. No ACL file.

**Data:** None.

## Critical Notes

- **Authorize.Net CIM (Customer Profile API):** Tokenization creates a Customer Profile + Payment Profile per partner/token pair on Authorize.net's servers. The `authorize_profile` field stores the customer profile ID; `provider_ref` stores the payment profile ID.
- **Validation transactions:** `auth_only` with `operation='validation'` are authorized then immediately voided — `_authorize_tokenize()` runs before void.
- **Manual capture flow:** `_send_capture_request()` sends `priorAuthCaptureTransaction` after Odoo's child tx is created. The `_handle_notification_data` call updates the tx state from the capture response.
- **Refund edge cases:** Handles AUTHORIZE.NET-side voids/refunds that happened before Odoo's refund. If tx was voided on Authorize side, marks Odoo tx as canceled. If refunded on Authorize side, creates Odoo refund tx marked done.
- **Single currency constraint:** Authorize.Net requires one currency per merchant account — enforced via `_limit_available_currency_ids` constraint.
- **v17→v18:** No breaking changes. Signature key field added (for inline form security). `action_update_merchant_details` fetches client key automatically.
- **BillTo required for ACH:** `_prepare_authorization_transaction_request` builds billTo for non-tokenized transactions, splitting partner name if individual.
