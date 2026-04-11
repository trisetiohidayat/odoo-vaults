---
Module: pos_razorpay
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_razorpay #payment #terminal #razorpay #india
---

## Overview

Integrates Razorpay Ezetap payment terminals (India) with POS. Supports payment requests, status polling, and cancellation. Compatible with the self-order kiosk flow via `pos_self_order_razorpay`.

**Depends:** `point_of_sale`

**Currency restriction:** Only valid for INR currency.

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

| Field | Type | Notes |
|---|---|---|
| `razorpay_tid` | Char | Device Serial No. (e.g., '7000012300') |
| `razorpay_allowed_payment_modes` | Selection | `all` (default), `card`, `upi`, `bharatqr` |
| `razorpay_username` | Char | Device login username |
| `razorpay_api_key` | Char | API key from Razorpay dashboard |
| `razorpay_test_mode` | Boolean | Default False |

**Methods:**
- `_get_payment_terminal_selection()` -> adds `('razorpay', 'Razorpay')`
- `razorpay_make_payment_request(data)` -> builds body with `pushTo: {deviceId: 'tid|ezetap_android'}`, `mode`, `amount`, `externalRefNumber`. Calls `/pay` endpoint. Returns `success=True` + `p2pRequestId` on approval.
- `razorpay_fetch_payment_status(data)` -> polls `/status` with `origP2pRequestId`. Parses status:
  - `AUTHORIZED` + `P2P_DEVICE_TXN_DONE` -> success with authCode, cardLastFourDigit, reverseReferenceNumber, etc.
  - `FAILED` or `P2P_DEVICE_CANCELED` -> error
  - `P2P_DEVICE_RECEIVED/SENT/QUEUED` -> return status code
- `razorpay_cancel_payment_request(data)` -> calls `/cancel` with `origP2pRequestId`. Returns success notification message.
- `_check_razorpay_terminal()` -> `@api.constrains`: raises UserError if `use_payment_terminal='razorpay'` and currency != 'INR'

---

### `pos.payment` (Extension)
**Inheritance:** `pos.payment`

| Field | Type | Notes |
|---|---|---|
| `razorpay_reverse_ref_no` | Char | Reverse/reference number for Razorpay |

---

### `razorpay_pos_request.py` (RazorpayPosRequest Class)

**`__init__(payment_method)`** -> stores all Razorpay config fields and creates `requests.Session`

**`_razorpay_get_endpoint()`** -> demo: `https://demo.ezetap.com/api/3.0/p2padapter/`; prod: `https://www.ezetap.com/api/3.0/p2padapter/`

**`_call_razorpay(endpoint, payload)`** -> POST to endpoint, reads `request_timeout` from `pos_razorpay.timeout` config param (default 10s)

**`_razorpay_get_payment_request_body(payment_mode=True)`** -> builds `pushTo` with `{deviceId: razorpay_tid|ezetap_android}` and `mode` if payment_mode; adds status request body (username, appKey)

**`_razorpay_get_payment_status_request_body()`** -> `{username, appKey: razorpay_api_key}`

---

## Security / Data

**neutralize.sql:** Sets `razorpay_test_mode=False` in production.

---

## Critical Notes

1. **Device ID format:** Razorpay Ezetap uses format `{tid}|ezetap_android` where `tid` is the terminal ID. This is the device identification sent in every payment request.

2. **Payment modes:** `upper()` is applied to the mode string — so 'all', 'card', 'upi', 'bharatqr' become 'ALL', 'CARD', 'UPI', 'BHARATQR' in the API request.

3. **Status codes:** `P2P_DEVICE_RECEIVED`, `P2P_DEVICE_SENT`, `P2P_STATUS_QUEUED` indicate the transaction is in progress — the frontend should poll again. Only `AUTHORIZED` + `P2P_DEVICE_TXN_DONE` is a final success.

4. **Refund reference:** `razorpay_reverse_ref_no` on `pos.payment` stores the `reverseReferenceNumber` from the successful transaction — needed for refund operations.

5. **Timeout config:** Request timeout is configurable via `pos_razorpay.timeout` system parameter, defaulting to 10 seconds.