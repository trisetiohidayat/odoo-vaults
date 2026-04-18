---
title: "Pos Mercado Pago"
module: pos_mercado_pago
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Pos Mercado Pago

## Overview

Module `pos_mercado_pago` — auto-generated from source code.

**Source:** `addons/pos_mercado_pago/`
**Models:** 2
**Fields:** 10
**Methods:** 7

## Models

### pos.payment.method (`pos.payment.method`)

Triggered in debug mode when the user wants to force the "PDV" mode.
        It calls the Mercado Pago API to set the terminal mode to "PDV".

**File:** `pos_payment_method.py` | Class: `PosPaymentMethod`

#### Fields (10)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `mp_bearer_token` | `Char` | — | — | — | — | — |
| `mp_webhook_secret_key` | `Char` | — | — | — | — | — |
| `mp_id_point_smart` | `Char` | — | — | — | — | — |
| `mp_id_point_smart_complet` | `Char` | — | — | — | — | — |
| `mercado_pago` | `MercadoPagoPosRequest` | — | — | — | — | — |
| `mercado_pago` | `MercadoPagoPosRequest` | — | — | — | — | — |
| `mercado_pago` | `MercadoPagoPosRequest` | — | — | — | — | — |
| `mercado_pago` | `MercadoPagoPosRequest` | — | — | — | — | — |
| `mercado_pago` | `MercadoPagoPosRequest` | — | — | — | — | — |
| `mercado_pago` | `MercadoPagoPosRequest` | — | — | — | — | — |


#### Methods (7)

| Method | Description |
|--------|-------------|
| `force_pdv` | |
| `mp_payment_intent_create` | |
| `mp_payment_intent_get` | |
| `mp_get_payment_status` | |
| `mp_payment_intent_cancel` | |
| `write` | |
| `create` | |


### pos.session (`pos.session`)

—

**File:** `pos_session.py` | Class: `PosSession`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
