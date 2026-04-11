---
Module: pos_viva_wallet
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_viva_wallet #payment #terminal #viva_wallet
---

## Overview

Integrates Viva Wallet (Greek payment provider) terminals with POS. Full payment terminal integration: sale requests, cancellation, status polling, webhook handling, and bearer token management.

**Depends:** `point_of_sale`

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

| Field | Type | Notes |
|---|---|---|
| `viva_wallet_merchant_id` | Char | Merchant ID from Viva Wallet dashboard |
| `viva_wallet_api_key` | Char | API key from Viva Wallet |
| `viva_wallet_client_id` | Char | POS API credentials client ID |
| `viva_wallet_client_secret` | Char | POS API credentials client secret |
| `viva_wallet_terminal_id` | Char | Terminal ID (e.g., '16002169') |
| `viva_wallet_bearer_token` | Char | Current bearer token (default 'Bearer Token') |
| `viva_wallet_webhook_verification_key` | Char | Webhook verification key |
| `viva_wallet_latest_response` | Json | Buffers latest async webhook notification |
| `viva_wallet_test_mode` | Boolean | Use demo environment |
| `viva_wallet_webhook_endpoint` | Char (compute) | Full webhook URL with company_id and token |

**Methods:**
- `_viva_wallet_account_get_endpoint()` -> demo or production accounts URL
- `_viva_wallet_api_get_endpoint()` -> demo or production API URL
- `_viva_wallet_webhook_get_endpoint()` -> demo or production web URL
- `_compute_viva_wallet_webhook_endpoint()` -> sets to `{base_url}/pos_viva_wallet/notification?company_id={company}&token={verification_key}`
- `_is_write_forbidden(fields)` -> whitelist: `viva_wallet_bearer_token`, `viva_wallet_webhook_verification_key`, `viva_wallet_latest_response` are writable even during open session
- `_get_payment_terminal_selection()` -> adds `('viva_wallet', 'Viva Wallet')`
- `_bearer_token(session)` -> obtains OAuth2 bearer token via client credentials; updates `viva_wallet_bearer_token` field
- `_get_verification_key(endpoint, merchant_id, api_key)` -> calls `/api/messages/config/token` to get webhook verification key (returns 'viva_wallet_test' in test mode)
- `_call_viva_wallet(endpoint, action, data=None, should_retry=True)` -> main API call: adds Authorization header, retries with refreshed bearer token on credential expiry
- `_retrieve_session_id(data_webhook)` -> webhook handler: parses `MerchantTrns` = `{session_id}/{pos_session_id}`, polls `/sessions/{id}`, buffers response in `viva_wallet_latest_response`, sends notification
- `_send_notification(data)` -> sends `VIVA_WALLET_LATEST_RESPONSE` notification to pos.session channel
- `_load_pos_data_fields(config_id)` -> adds `'viva_wallet_terminal_id'`
- `viva_wallet_send_payment_request(data)` -> checks `group_pos_user`, calls `_call_viva_wallet(endpoint='transactions:sale', 'post', data)`
- `viva_wallet_send_payment_cancel(data)` -> checks `group_pos_user`, calls DELETE `/sessions/{sessionId}?cashRegisterId={cashRegisterId}`
- `viva_wallet_get_payment_status(session_id)` -> checks `group_pos_user`, calls GET `/sessions/{session_id}` without retry
- `write(vals)` -> if `viva_wallet_merchant_id` + `viva_wallet_api_key` present, auto-fetches and sets `viva_wallet_webhook_verification_key`
- `create(vals)` -> same webhook key auto-fetch on creation
- `get_latest_viva_wallet_status()` -> checks `group_pos_user`, returns `viva_wallet_latest_response` (sudo)
- `_check_viva_wallet_credentials()` -> `@api.constrains`: all 5 credentials must be present when `use_payment_terminal='viva_wallet'`

**Non-model functions:**
- `get_viva_wallet_session(should_retry=True)` -> returns `requests.Session` with HTTPAdapter retry config (5 retries, backoff_factor=2, status_forcelist=[202, 500, 502, 503, 504])

---

## Security / Data

**neutralize.sql:** Standardize config field values for production (viva_wallet_test_mode=False, empty tokens).

---

## Critical Notes

1. **Webhook endpoint:** The Viva Wallet webhook must be configured in the Viva Wallet merchant portal to point to `/pos_viva_wallet/notification`. The controller receives the webhook and triggers `_retrieve_session_id`.

2. **Token refresh:** `_call_viva_wallet` automatically refreshes the bearer token and retries the request once if the server returns `Could not validate credentials` — handled transparently.

3. **Write-forbidden whitelist:** Unlike most payment method fields, `viva_wallet_bearer_token`, `viva_wallet_webhook_verification_key`, and `viva_wallet_latest_response` can be written even when a POS session is open, since they are updated by background webhooks and token refresh processes.

4. **Dual environment:** Uses separate endpoints for test/production across accounts, API, and web subsystems.