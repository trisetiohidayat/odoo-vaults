---
title: "Payment Mercado Pago"
module: payment_mercado_pago
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Mercado Pago

## Overview

Module `payment_mercado_pago` — auto-generated from source code.

**Source:** `addons/payment_mercado_pago/`
**Models:** 3
**Fields:** 8
**Methods:** 1

## Models

### res.country (`res.country`)

Override of `payment` to enable additional features.

**File:** `payment_provider.py` | Class: `PaymentProvider`

#### Fields (7)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `code` | `Selection` | — | — | — | — | — |
| `mercado_pago_account_country_id` | `Many2one` | — | — | — | — | — |
| `mercado_pago_is_oauth_supported` | `Boolean` | Y | — | — | — | — |
| `mercado_pago_access_token` | `Char` | — | — | — | — | — |
| `mercado_pago_access_token_expiry` | `Datetime` | — | — | — | — | — |
| `mercado_pago_refresh_token` | `Char` | — | — | — | — | — |
| `mercado_pago_public_key` | `Char` | Y | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_start_onboarding` | |


### payment.token (`payment.token`)

—

**File:** `payment_token.py` | Class: `PaymentToken`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `mercado_pago_customer_id` | `Char` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.transaction (`payment.transaction`)

Override of `payment` to return Mercado Pago-specific rendering values.

        Note: self.ensure_one() from `_get_rendering_values`.

        :param dict processing_values: The generic and specific 

**File:** `payment_transaction.py` | Class: `PaymentTransaction`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
