---
Module: payment_worldline
Version: 18.0.0
Type: addon
Tags: #odoo18 #payment_worldline #payment
---

## Overview

`payment_worldline` integrates Odoo with Worldline's Hosted Checkout API (formerly Online Payments Platform). Supports 20+ payment methods across Europe including iDEAL, Bancontact, Klarna, PayPal, Twint, MBway, and all major card brands. Uses HMAC-SHA256 request signing with RFC1123 timestamps and idempotency keys. Tokenization creates Worldline tokens stored as `payment.token.provider_ref`.

## Models

### payment.provider (extends base)
**Inheritance:** `payment.provider` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| code | selection | Adds `('worldline', "Worldline")`. `ondelete='set default'` |
| worldline_pspid | Char | Worldline PSPID (required_if_provider='worldline') |
| worldline_api_key | Char | API Key (required_if_provider='worldline') |
| worldline_api_secret | Char | API Secret (required_if_provider='worldline') |
| worldline_webhook_key | Char | Webhook Key (required_if_provider='worldline') |
| worldline_webhook_secret | Char | Webhook Secret (required_if_provider='worldline') |

**Feature Support Fields:** `support_tokenization=True`

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _worldline_make_request | self, endpoint, payload=None, method='POST', idempotency_key=None | dict | Makes signed request to Worldline API. Builds `Authorization: GCS v1HMAC:{api_key}:{signature}` header with HMAC-SHA256 sig, `Date` (RFC1123), `Content-Type`, optionally `X-GCS-Idempotency-Key`. Checks `VALID_RESPONSE_CODES` before raising HTTP errors |
| _worldline_get_api_url | self | str | Production: `https://payment.direct.worldline-solutions.com`. Test: `https://payment.preprod.direct.worldline-solutions.com` |
| _worldline_calculate_signature | self, method, endpoint, content_type, dt_rfc, idempotency_key=None | str | HMAC-SHA256 base64 signature. Signing order: method, content_type, date, [idempotency key], `/v2/{pspid}/{endpoint}` |
| _get_default_payment_method_codes | self | set | Returns `{'card'}` |

### payment.transaction (extends base)
**Inheritance:** `payment.transaction` (classic `_inherit`)

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_reference | self, provider_code, prefix=None, separator='-', **kwargs | str | Overrides to enforce max 30-character reference for Worldline's `merchantReference` field. Uses `singularize_reference_prefix(prefix='WL')` if generated reference exceeds 30 chars |
| _get_specific_processing_values | self, processing_values | dict | Detects 3DS auth failure for token flow: if `operation='online_token'`, `state='error'`, `state_message` ends with 'AUTHORIZATION_REQUESTED', resets state to draft and `operation='online_redirect'`, sets `force_flow='redirect'` |
| _get_specific_rendering_values | self, processing_values | dict | Creates hosted checkout session via `_worldline_create_checkout_session()`. Returns `{'api_url': checkout_session_data['redirectUrl']}` |
| _worldline_create_checkout_session | self | dict | Builds full payload: `hostedCheckoutSpecificInput` (locale, returnUrl, showResultPage=False), `order` (amountOfMoney with minor units conversion, customer with billing/contact/personal info, references). If `payment_method_code` in `REDIRECT_PAYMENT_METHODS`, adds `redirectPaymentMethodSpecificInput`; else adds `cardPaymentMethodSpecificInput` with `authorizationMode=SALE` and `tokenize` flag |
| _send_payment_request | self | None | Token payment via `/payments`. Builds `cardPaymentMethodSpecificInput` with token, `unscheduledCardOnFileRequestor=merchantInitiated`, `unscheduledCardOnFileSequenceIndicator=subsequent`. Uses idempotency key to prevent duplicate charges |
| _get_tx_from_notification_data | self, provider_code, notification_data | recordset | Extracts `merchantReference` from `paymentResult.payment.paymentOutput.references` (handles both flat and nested keys) |
| _process_notification_data | self, notification_data | None | Extracts `paymentResult` (or direct payment data). Sets `provider_reference` (strips trailing `_suffix`). Determines payment method from `cardPaymentMethodSpecificOutput` or `redirectPaymentMethodSpecificOutput`. Maps status via `PAYMENT_STATUS_MAPPING`. Handles AUTHORIZATION_REQUESTED as error (3DS required). For validation operations with token data: creates token and marks done |
| _worldline_tokenize_from_notification_data | self, pm_data | None | Creates `payment.token` with `provider_ref` = Worldline token string, `payment_details` = last 4 card digits |

### WorldlineController (http.Controller)
**Routes:** `_return_url = '/payment/worldline/return'`, `_webhook_url = '/payment/worldline/webhook'`

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| worldline_return_from_checkout | self, **data | response | On return, fetches checkout session data via `GET /hostedcheckouts/{hostedCheckoutId}`. Extracts `createdPaymentOutput` as notification data, calls `_handle_notification_data` |
| worldline_webhook | self | response | Receives JSON notification, verifies `X-GCS-Signature` header (HMAC-SHA256), acknowledges with empty JSON response |
| _verify_notification_signature | static, request_data, received_signature, tx_sudo | None | HMAC-SHA256 comparison of received header vs expected from payload |

## Security / Data

**Security:** All key/secret fields restricted to `base.group_system`. Webhook signature verification via HMAC-SHA256 on raw request body.

**Data:** None.

## Critical Notes

- **HMAC signature:** Worldline uses a specific signing string format: `METHOD\nContent-Type\nDate\n[X-GCS-Idempotency-Key: key]\n/v2/{pspid}/{endpoint}\n`. Signature is base64-encoded HMAC-SHA256.
- **Idempotency keys:** Payment requests include `X-GCS-Idempotency-Key` to safely retry on network failures.
- **3DS handling:** Token payments that require 3DS authentication fail with 'AUTHORIZATION_REQUESTED' status. The override detects this and switches the transaction back to redirect flow.
- **Tokenization for validation:** When `operation='validation'` and status is `PENDING_CAPTURE`/`CAPTURE_REQUESTED` with token data, creates token and sets done (card verification use case).
- **Provider reference parsing:** Worldline's `payment.id` has format `{id}_{suffix}`. The `_process_notification_data` strips the suffix with `rsplit('_', 1)[0]`.
- **v17→v18:** New module in Odoo 18.
