---
Module: pos_pine_labs
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_pine_labs #payment #terminal #pine_labs #india
---

## Overview

Integrates Pine Labs payment terminals (India/Malaysia) with POS. Supports payment requests, status polling, and cancellation. Requires proxy endpoint for non-India/Malaysia usage.

**Depends:** `point_of_sale`

**Currency restriction:** Only valid for INR currency.

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

| Field | Type | Notes |
|---|---|---|
| `pine_labs_merchant` | Char | Merchant ID from Pine Labs |
| `pine_labs_store` | Char | Store ID from Pine Labs |
| `pine_labs_client` | Char | Client ID from Pine Labs |
| `pine_labs_security_token` | Char | Security token |
| `pine_labs_allowed_payment_mode` | Selection | `all` (default), `card`, `upi` |
| `pine_labs_test_mode` | Boolean | Use UAT environment |

**Methods:**
- `_get_payment_terminal_selection()` -> adds `('pine_labs', 'Pine Labs')`
- `pine_labs_make_payment_request(data)` -> `data` contains `amount`, `transactionNumber`, `sequenceNumber`. Sends to `UploadBilledTransaction` endpoint. Returns `responseCode=0`, `status='APPROVED'`, `plutusTransactionReferenceID` on success.
- `pine_labs_fetch_payment_status(data)` -> `data` contains `plutusTransactionReferenceID`. Sends to `GetCloudBasedTxnStatus`. Returns success with `ResponseCode` 0 or 1001 (pending). Formats `TransactionData` tag-value pairs.
- `pine_labs_cancel_payment_request(data)` -> `data` contains `amount`, `plutusTransactionReferenceID`. Sends to `CancelTransactionForced`. Returns notification message on success.
- `_check_pine_labs_terminal()` -> `@api.constrains`: raises UserError if `use_payment_terminal='pine_labs'` and company currency != 'INR'

---

### `pos.payment` (Extension)
**Inheritance:** `pos.payment`

| Field | Type | Notes |
|---|---|---|
| `pine_labs_plutus_transaction_ref` | Char | PlutusTransactionReferenceID for refunds |

---

### Module-Level Helpers (in `pine_labs_pos_request.py`)

**`call_pine_labs(payment_method, endpoint, payload)`**
- Validates endpoint against `ALLOWED_ENDPOINTS` (UploadBilledTransaction, GetCloudBasedTxnStatus, CancelTransactionForced)
- Adds merchant/store/client/security token to payload
- For `UploadBilledTransaction`: adds `AllowedPaymentMode` (mapped via `ALLOWED_PAYMENT_MODES_MAPPING`) and `AutoCancelDurationInMinutes` (from `pos_pine_labs.payment_auto_cancel_duration` config param, default 10)
- Calls POST to `{pine_labs_url}{endpoint}`
- Returns parsed JSON or error dict

**`pine_labs_request_body(payment_mode, payment_method)`** -> dict with MerchantID, StoreID, ClientID, SecurityToken; adds AllowedPaymentMode + AutoCancelDurationInMinutes if payment_mode=True

**`_get_pine_labs_url(payment_method)`** -> returns proxy endpoint if configured; else uses direct URL: UAT `https://www.plutuscloudserviceuat.in:8201/API/CloudBasedIntegration/V1/`, prod `https://www.plutuscloudservice.in:8201/API/CloudBasedIntegration/V1/`

**Allowed endpoints:** `['UploadBilledTransaction', 'GetCloudBasedTxnStatus', 'CancelTransactionForced']`
**Payment modes:** `{'all': 0, 'card': 1, 'upi': 10}`
**Timeout:** 10 seconds
**Auto-cancel:** 10 minutes (configurable via `pos_pine_labs.payment_auto_cancel_duration`)

---

## Security / Data

**neutralize.sql:** Sets `pine_labs_test_mode=False` in production.

---

## Critical Notes

1. **Proxy required outside India/Malaysia:** The direct Pine Labs URLs are only accessible in India and Malaysia. Outside these countries, `pos_pine_labs.pine_labs_proxy_endpoint` system parameter must be set to a proxy URL.

2. **Auto-cancel duration:** `AutoCancelDurationInMinutes` (default 10 min) tells Pine Labs to auto-cancel transactions where the final confirmation request is not received within the window. Prevents ghost transactions.

3. **Payment mode mapping:** The API expects integer codes (0=all, 1=card, 10=upi) — mapped from human-readable selection via `ALLOWED_PAYMENT_MODES_MAPPING`.

4. **Pending status (code 1001):** `GetCloudBasedTxnStatus` returns code 1001 for pending transactions — treated as success without transaction data.

5. **`pine_labs_plutus_transaction_ref` on `pos.payment`:** Required for void/refund operations — the void request needs the reference ID from the original transaction.