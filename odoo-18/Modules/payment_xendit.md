---
Module: payment_xendit
Version: 18.0.0
Type: addon
Tags: #odoo18 #payment_xendit #payment
---

## Overview

`payment_xendit` integrates Odoo with Xendit, an Asian-focused payment provider supporting credit/debit cards (Visa, Mastercard), DANA, OVO, QRIS, and bank transfer methods (BCA, Permata, BPI) across Indonesia and Philippines. Uses Xendit's Invoice API for redirect flows and the Charges API for tokenized payments. Webhook notifications are verified by comparing external_id.

## Models

### payment.provider (extends base)
**Inheritance:** `payment.provider` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| code | selection | Adds `('xendit', "Xendit")`. `ondelete='set default'` |
| xendit_public_key | Char | Xendit Public Key (required_if_provider='xendit', groups=base.group_system) |
| xendit_secret_key | Char | Xendit Secret Key (required_if_provider='xendit', groups=base.group_system) |
| xendit_webhook_token | Char | Webhook Token (required_if_provider='xendit', groups=base.group_system) |

**Feature Support Fields:** `support_tokenization=True`

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_supported_currencies | self | recordset | Filters to `SUPPORTED_CURRENCIES`: IDR, PHP |
| _xendit_make_request | self, endpoint, payload=None | dict | POST to `https://api.xendit.co/{endpoint}`. Uses HTTP Basic Auth with `(xendit_secret_key, '')` |
| _get_redirect_form_view | self, is_validation=False | ir.ui.view or None | **Returns None for validation operations** — prevents rendering a card form for token validation (Xendit's Card method uses direct flow incompatible with validation) |
| _get_default_payment_method_codes | self | set | Returns `{'card', 'dana', 'ovo', 'qris', 'visa', 'mastercard'}` |

### payment.transaction (extends base)
**Inheritance:** `payment.transaction` (classic `_inherit`)

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_specific_processing_values | self, processing_values | dict | For card payments, computes `rounded_amount` based on currency decimal requirements |
| _get_specific_rendering_values | self, processing_values | dict | For non-card payments, creates Xendit invoice via `/v2/invoices`. Returns `{'api_url': invoice_url}`. Skips for card payment method (handled separately) |
| _xendit_prepare_invoice_request_payload | self | dict | Builds invoice payload: `external_id` (reference), `amount` (rounded), `description`, `customer` (given_names from partner_name, email, mobile_number from partner phone), `success_redirect_url` (with access token), `failure_redirect_url`, `payment_methods` (mapped), `currency`. Address fields conditionally included |
| _send_payment_request | self | None | Token payment via `_xendit_create_charge()`. Raises if no token |
| _xendit_create_charge | self, token_ref, auth_id=None | None | Creates charge via `/credit_card_charges`. Sets `is_recurring=True` for tokenized payments. Calls `_handle_notification_data` with response |
| _get_tx_from_notification_data | self, provider_code, notification_data | recordset | Looks up by `external_id` |
| _process_notification_data | self, notification_data | None | Sets `provider_reference` from `id`. Maps `payment_method` via `PAYMENT_METHODS_MAPPING`. Maps `status` via `PAYMENT_STATUS_MAPPING`: 'PENDING' → pending, 'SUCCEEDED'/'PAID'/'CAPTURED' → done (+ tokenize if requested), 'CANCELLED'/'EXPIRED' → canceled, 'FAILED' → error |
| _xendit_tokenize_from_notification_data | self, notification_data | None | Creates token: `provider_ref` = `credit_card_token_id`, `payment_details` = last 4 of `masked_card_number` |

## Security / Data

**Security:** `xendit_public_key`, `xendit_secret_key`, `xendit_webhook_token` restricted to `base.group_system`. No ACL file.

**Data:** None.

## Critical Notes

- **Currency decimals:** IDR and PHP require integer amounts (no decimals) — rounded with `CURRENCY_DECIMALS={'IDR': 0, 'PHP': 0}`.
- **Card flow vs invoice flow:** Card payments use direct charges API (`/credit_card_charges`). All other methods use invoice API (`/v2/invoices`). `_get_specific_rendering_values` explicitly skips invoice creation for card method.
- **Validation form bypass:** `_get_redirect_form_view` returns `None` for Xendit validation operations — prevents rendering a useless card form.
- **Access token in success URL:** `_xendit_prepare_invoice_request_payload` generates an access token (`generate_access_token(reference, amount)`) and passes it in the success redirect URL for secure transaction matching.
- **is_recurring flag:** For tokenized card payments, `is_recurring=True` ensures subsequent payments don't require 3DS re-authentication.
- **v17→v18:** No breaking changes observed.
