---
Module: pos_self_order_razorpay
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_self_order_razorpay #self_order #payment #razorpay
---

## Overview

Enables Razorpay terminal payment requests in kiosk self-order mode. Overrides `_payment_request_from_kiosk` to send Razorpay Ezetap payment requests, and handles status polling and cancellation via dedicated controller endpoints.

**Depends:** `pos_self_order`, `pos_razorpay`

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

**Methods:**
- `_payment_request_from_kiosk(order)` -> if `use_payment_terminal != 'razorpay'`, delegates to super. Otherwise:
  - `reference_prefix = order.config_id.name.replace(' ', '')`
  - Builds `referenceId = '{prefix}/Order/{order.id}/{uuid}'`
  - Calls `razorpay_make_payment_request({'amount': order.amount_total, 'referenceId': referenceId})`
  - Returns result

---

## Controllers

### `pos_self_order_razorpay.controllers.orders.PosSelfOrderControllerRazorpay`
**Inheritance:** `pos_self_order.controllers.orders.PosSelfOrderController`

**Methods:**
- `razorpay_payment_status(access_token, order_id, payment_data, payment_method_id)` -> `/pos-self-order/razorpay-fetch-payment-status/`: polls Razorpay status, on `AUTHORIZED`: adds payment with full card/transaction details, calls `action_pos_order_paid()`, broadcasts `PAYMENT_STATUS` via `call_bus_service`. On `FAILED`/error: broadcasts `fail` status
- `razorpay_cancel_status(access_token, order_id, payment_data, payment_method_id)` -> `/pos-self-order/razorpay-cancel-transaction/`: calls `razorpay_cancel_payment_request`, broadcasts `fail` via `call_bus_service`
- `call_bus_service(order, payment_result)` -> helper: broadcasts `PAYMENT_STATUS` notification with order and order line data

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Razorpay reference format:** Razorpay Ezetap expects `referenceId` in format `{prefix}/Order/{id}/{uuid}` — this allows correlating Odoo orders with Razorpay transactions.

2. **Kiosk domain filter:** The base `pos_self_order` `pos.payment.method` `_load_pos_self_data_domain` already filters for `razorpay` terminal type in kiosk mode.

3. **Authorization flow:** Payment is recorded on `AUTHORIZED` status (not `CAPTURED`) — Odoo records the payment when Razorpay authorizes the transaction. Capture is handled by Razorpay's own settlement process.

4. **Full card data on payment:** The `razorpay_payment_status` response populates extensive card/transaction metadata on the `pos.payment` record: card type, brand, last four digits, issuer bank, auth code, payment mode, etc.
