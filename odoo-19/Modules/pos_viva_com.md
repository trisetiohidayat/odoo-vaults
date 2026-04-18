---
title: "Pos Viva Com"
module: pos_viva_com
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Pos Viva Com

## Overview

Module `pos_viva_com` — auto-generated from source code.

**Source:** `addons/pos_viva_com/`
**Models:** 2
**Fields:** 11
**Methods:** 7

## Models

### pos.payment (`pos.payment`)

—

**File:** `pos_payment.py` | Class: `PosPayment`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `viva_com_session_id` | `Char` | — | — | — | Y | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### pos.payment.method (`pos.payment.method`)

Get a key to configure the webhook.
    This key need to be the response when we receive a notification.
    Do not execute this query in test mode.

    :param endpoint: The endpoint to get the verif

**File:** `pos_payment_method.py` | Class: `PosPaymentMethod`

#### Fields (10)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `viva_com_merchant_id` | `Char` | — | — | — | — | — |
| `viva_com_api_key` | `Char` | — | — | — | — | — |
| `viva_com_client_id` | `Char` | — | — | — | — | — |
| `viva_com_client_secret` | `Char` | — | — | — | — | — |
| `viva_com_terminal_id` | `Char` | — | — | — | — | — |
| `viva_com_bearer_token` | `Char` | — | — | — | — | — |
| `viva_com_webhook_verification_key` | `Char` | — | — | — | — | — |
| `viva_com_latest_response` | `Json` | Y | — | — | — | — |
| `viva_com_test_mode` | `Boolean` | Y | — | — | — | — |
| `viva_com_webhook_endpoint` | `Char` | Y | — | — | — | — |


#### Methods (7)

| Method | Description |
|--------|-------------|
| `viva_com_send_payment_request` | |
| `viva_com_send_refund_request` | |
| `viva_com_send_payment_cancel` | |
| `viva_com_get_payment_status` | |
| `write` | |
| `create` | |
| `get_latest_viva_com_status` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
