---
Module: pos_paytm
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_paytm #payment #terminal #paytm #india
---

## Overview

Integrates PayTM payment terminals with POS (India). Supports payment requests, status polling, and cancellation with auto/manual accept modes and all/card/QR payment modes.

**Depends:** `point_of_sale`

**Currency restriction:** Only valid for INR currency (enforced by `_check_paytm_terminal`).

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

| Field | Type | Notes |
|---|---|---|
| `paytm_tid` | Char | Terminal ID / Activation code (e.g., '70000123') |
| `channel_id` | Char | Default 'EDC' |
| `accept_payment` | Selection | `auto` (default) or `manual` |
| `allowed_payment_modes` | Selection | `all` (default), `card`, `qr` |
| `paytm_mid` | Char | PayTM Merchant ID |
| `paytm_merchant_key` | Char | Merchant/AES key (e.g., 'B1o6Ivjy8L1@abc9') |
| `paytm_test_mode` | Boolean | Default False |

**Methods:**
- `_get_payment_terminal_selection()` -> adds `('paytm', 'PayTM')`
- `_paytm_make_request(url, payload=None)` -> makes API call: demo/production URL based on `paytm_test_mode`, returns `body` of response or error dict
- `paytm_make_payment_request(amount, transaction_id, reference_id, timestamp)` -> builds request with `transactionAmount`, `autoAccept`, `paymentMode`, merchant head/body, calls API. Returns `resultInfo` on success (resultCode='A'), error on failure (resultCode='F')
- `paytm_fetch_payment_status(transaction_id, reference_id, timestamp)` -> polls status. Success: resultCode='S' with card/transaction details. Failure: resultCode='F'. Pending: resultCode='P'
- `_paytm_generate_signature(params_dict, key)` -> SHA256 hash of sorted params + salt, padded, encrypted with AES-256-CBC using merchant key and IV `@@@@&&&&####$$$$`, base64 encoded
- `_paytm_get_request_body(transaction_id, reference_id, timestamp)` -> builds body dict with MID, TID, datetime (IST timezone), merchantTransactionId, merchantReferenceNo
- `_paytm_get_request_head(body)` -> generates signature from body, returns head dict with `requestTimeStamp`, `channelId='EDC'`, `checksum`
- `_check_paytm_terminal()` -> `@api.constrains`: raises UserError if `use_payment_terminal='paytm'` and company currency != 'INR'

**Helper:**
- `iv = b'@@@@&&&&####$$$$'` -> AES-CBC initialization vector (constant)

---

## Security / Data

**neutralize.sql:** Sets `paytm_test_mode=False` in production.

---

## Critical Notes

1. **AES-256-CBC signature:** PayTM uses a custom signature scheme: sorted params joined by `|`, salted with 4 random chars, SHA256 hashed, padded with chr(12), encrypted with AES-256-CBC. The merchant key is used directly as the AES key.

2. **IST timezone:** All timestamps are converted to Asia/Kolkata timezone before sending to PayTM API.

3. **Auto vs manual accept:** When `accept_payment='auto'`, the `autoAccept='True'` flag is sent in the payment request, allowing PayTM to auto-accept without cashier confirmation.

4. **API endpoints:** Demo: `https://securegw-stage.paytm.in/ecr/`; Production: `https://securegw-edc.paytm.in/ecr/`