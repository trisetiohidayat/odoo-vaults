---
Module: pos_self_order_adyen
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_self_order_adyen #self_order #payment #adyen
---

## Overview

Enables Adyen terminal payment requests in kiosk self-order mode. Overrides `_payment_request_from_kiosk` to send Adyen POS payment requests with POS-specific metadata, and handles Adyen webhook notifications.

**Depends:** `pos_self_order`, `pos_adyen`

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

**Methods:**
- `_get_valid_acquirer_data()` -> adds `metadata.self_order_id` using `UNPREDICTABLE_ADYEN_DATA` constant (prevents Adyen from treating it as a predictable field for fraud detection)
- `_payment_request_from_kiosk(order)` -> if `use_payment_terminal != 'adyen'`, delegates to super. Otherwise, builds Adyen SaleToPOIRequest with:
  - `MessageHeader`: ProtocolVersion=3.0, MessageClass=Service, MessageType=Request, MessageCategory=Payment, `SaleID='{config.display_name} (ID:{config.id})'`, `ServiceID=random9-10digit`, `POIID=adyen_terminal_identifier`
  - `PaymentRequest.SaleData.SaleTransactionID.TransactionID=order.pos_reference`, `TimeStamp=UTC now`
  - `SaleToAcquirerData='metadata.self_order_id={order.id}'`
  - `PaymentRequest.PaymentTransaction.AmountsReq.Currency=order.currency_id.name`, `RequestedAmount=order.amount_total`
  - Calls `proxy_adyen_request(data)` and returns success bool

---

## Controllers

### `pos_self_order_adyen.controllers.main.PosSelfAdyenController`
**Inheritance:** `pos_adyen.controllers.main.PosAdyenController`

**Methods:**
- `_process_payment_response(data, adyen_pm_sudo)` -> overrides parent to handle kiosk self-order payment responses:
  - Extracts `self_order_id` from Adyen `AdditionalResponse` metadata
  - Looks up `pos.order` by `self_order_id`
  - For `Success` results in kiosk mode: adds payment via `order.add_payment()`, calls `action_pos_order_paid()`, sends order to kitchen via `_send_order()`
  - Broadcasts `PAYMENT_STATUS` notification with `payment_result` (Success/fail) and order/line data
  - Returns `[accepted]` JSON response to Adyen

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Random ServiceID:** Each payment request uses a random 9-10 digit number for `ServiceID` — required by Adyen for idempotency.

2. **metadata.self_order_id:** Embeds the Odoo order ID in the Adyen metadata, allowing reconciliation between Odoo and Adyen transaction records via the webhook.

3. **SaleID format:** `{display_name} (ID:{id})` is required as the SaleID — the terminal verifies this matches the configured terminal identity.

4. **Webhook vs direct response:** `_process_payment_response` is called by the Adyen webhook controller (`pos_adyen/notification` route). It handles both kiosk self-order payments (which embed `self_order_id`) and regular POS payments (which do not — delegated to parent).

5. **Kiosk-specific flow:** Only kiosk mode (`self_ordering_mode == 'kiosk'`) triggers payment recording and `PAYMENT_STATUS` broadcast. Mobile/consultation modes rely on different payment flows (online payment or cash).
