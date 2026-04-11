---
Module: pos_mercado_pago
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_mercado_pago #payment #terminal #mercadopago #latam
---

## Overview

Integrates Mercado Pago Point Smart terminals (Argentina/LATAM) with POS. Supports payment intent creation, status polling, cancellation, and terminal mode forcing via the Mercado Pago API.

**Depends:** `point_of_sale`

---

## Models

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

| Field | Type | Notes |
|---|---|---|
| `mp_bearer_token` | Char | Production user token (group: `group_pos_manager`) |
| `mp_webhook_secret_key` | Char | Production secret key (group: `group_pos_manager`) |
| `mp_id_point_smart` | Char | Terminal serial number (from back of device, after S/N:) |
| `mp_id_point_smart_complet` | Char | Full device ID (computed on write/create via `_find_terminal`) |

**Methods:**
- `_get_payment_terminal_selection()` -> adds `('mercado_pago', 'Mercado Pago')`
- `_check_special_access()` -> raises AccessError if no `group_pos_user`
- `force_pdv()` -> debug mode: calls PATCH `/devices/{id}` with `operating_mode='PDV'`. Raises UserError on unexpected response.
- `mp_payment_intent_create(infos)` -> POST `/devices/{id}/payment-intents` with infos dict. Logs and returns response.
- `mp_payment_intent_get(payment_intent_id)` -> GET `/payment-intents/{id}`. Logs and returns response.
- `mp_get_payment_status(payment_id)` -> GET `/v1/payments/{id}`. Logs and returns response.
- `mp_payment_intent_cancel(payment_intent_id)` -> DELETE `/devices/{id}/payment-intents/{id}`. Logs and returns response.
- `_find_terminal(token, point_smart)` -> searches `/devices` for device ID containing the entered serial number. Returns full device ID or raises UserError. Sets `mp_id_point_smart_complet` on the record.
- `write(vals)` -> if `mp_id_point_smart` or `mp_bearer_token` changed: calls `_find_terminal` to update `mp_id_point_smart_complet`
- `create(vals)` -> if `mp_bearer_token` present: calls `_find_terminal` to set `mp_id_point_smart_complet`

---

### `pos.session` (Extension)
**Inheritance:** `pos.session`

**Methods:**
- `_loader_params_pos_payment_method()` -> adds `'mp_id_point_smart'` to fields loaded for payment method

---

### `mercado_pago_pos_request.py` (MercadoPagoPosRequest Class)

**`__init__(mp_bearer_token)`** -> stores bearer token

**`call_mercado_pago(method, endpoint, payload)`**
- Adds `Authorization: Bearer {token}` header
- Adds `X-platform-id: dev_cdf1cfac242111ef9fdebe8d845d0987` (Odoo platform ID, not secret)
- Calls `requests.request(method, endpoint, headers, json=payload, timeout=10)`
- Returns JSON or error dict

---

## Security / Data

**neutralize.sql:** Standardizes test configuration values.

---

## Critical Notes

1. **Terminal discovery:** The terminal serial number entered by the user (e.g., `ABCD1234`) is not the full device ID. `_find_terminal` searches Mercado Pago's device list for any device whose ID contains the serial number string, then stores the full ID in `mp_id_point_smart_complet`. This is required because Mercado Pago generates full IDs like `prd_00123456789abcdef`.

2. **PDV mode:** `force_pdv()` is a debug-mode helper to force the terminal into POS mode via the Mercado Pago Integration API. Normally the terminal auto-switches when a payment intent is created.

3. **Manager-only credentials:** `mp_bearer_token` and `mp_webhook_secret_key` are restricted to `group_pos_manager` — these are sensitive production credentials.

4. **Odoo platform ID:** The `X-platform-id` header (`dev_cdf1cfac242111ef9fdebe8d845d0987`) identifies Odoo to Mercado Pago's backend for usage analytics — not a secret.