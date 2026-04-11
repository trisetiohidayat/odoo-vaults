---
Module: payment_demo
Version: 18.0.0
Type: addon
Tags: #odoo18 #payment_demo #payment
---

## Overview

`payment_demo` is a sandbox/dummy payment provider used for testing and development. It simulates all payment operations (authorization, capture, void, refund, tokenization) without any external API calls. Transactions transition through states based on simulated notification data. Demo provider **cannot be enabled** (`state='enabled'`) — only `test` or `disabled`.

## Models

### payment.provider (extends base)
**Inheritance:** `payment.provider` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| code | selection | Adds `('demo', 'Demo')`. `ondelete='set default'` |

**Feature Support Fields:** `support_express_checkout=True`, `support_manual_capture='partial'`, `support_refund='partial'`, `support_tokenization=True`

**Constraints:**

| Constraint | Description |
|------------|-------------|
| `_check_provider_state` | Raises `UserError` if `code=='demo'` and `state not in ('test', 'disabled')` |

### payment.token (extends base)
**Inheritance:** `payment.token` (classic `_inherit`)

| Field | Type | Description |
|-------|------|-------------|
| demo_simulated_state | Selection | Simulated state for tokens: `pending`, `done`, `cancel`, `error`. Allows creating tokens that always produce specific outcomes |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _build_display_name | *args, should_pad=True, **kwargs | str | For demo tokens, calls `super()` with `should_pad=False` to suppress padding |

### payment.transaction (extends base)
**Inheritance:** `payment.transaction` (classic `_inherit`)

| Field | Type | Description |
|-------|------|-------------|
| capture_manually | Boolean | Related from `provider_id.capture_manually` |

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| action_demo_set_done | self | None | Wizard action: sets tx to 'done'. Calls `_handle_notification_data` with `simulated_state='done'` |
| action_demo_set_canceled | self | None | Wizard action: sets tx to 'cancel' |
| action_demo_set_error | self | None | Wizard action: sets tx to 'error' |
| _send_payment_request | self | None | Simulates token payment. Reads `token_id.demo_simulated_state` and calls `_handle_notification_data` with that state |
| _send_refund_request | **kwargs | recordset | Simulates refund: creates child refund tx, immediately calls `_handle_notification_data` with `simulated_state='done'` |
| _send_capture_request | self, amount_to_capture=None | recordset | Simulates capture: calls `_handle_notification_data` with `simulated_state='done'` and `manual_capture=True` |
| _send_void_request | self, amount_to_void=None | recordset | Simulates void: calls `_handle_notification_data` with `simulated_state='cancel'` |
| _get_tx_from_notification_data | self, provider_code, notification_data | recordset | Looks up by `reference` |
| _process_notification_data | self, notification_data | None | Sets `provider_reference='demo-{reference}'`. If `tokenize=True`, immediately creates token (regardless of state) with `demo_simulated_state` stored. Maps `simulated_state`: 'pending' → pending, 'done' → authorized (if manual capture and not manual_capture flag) or done, 'cancel' → canceled, else error |
| _demo_tokenize_from_notification_data | self, notification_data | None | Creates `payment.token` with `demo_simulated_state` set to current simulated state |

## Security / Data

**Security:** None.

**Data:** None.

## Critical Notes

- **Cannot be enabled:** Constraint prevents `state='enabled'`. Always in test mode or disabled.
- **Immediate tokenization:** Tokens are created immediately on transaction creation (not waiting for authorization/done), to persist the simulated state.
- **Batch size:** No external API — no rate limiting concerns.
- **Refund simulation:** Refunds always succeed and go directly to 'done'.
- **Manual capture:** If `capture_manually=True` on provider, regular 'done' notification results in 'authorized' state rather than 'done'.
- **v17→v18:** No specific changes. Demo provider unchanged across versions.
