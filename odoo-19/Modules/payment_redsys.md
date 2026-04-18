---
title: "Payment Redsys"
module: payment_redsys
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Redsys

## Overview

Module `payment_redsys` — auto-generated from source code.

**Source:** `addons/payment_redsys/`
**Models:** 2
**Fields:** 5
**Methods:** 1

## Models

### payment.provider (`payment.provider`)

Override of `payment` to return the default payment method codes.

**File:** `payment_provider.py` | Class: `PaymentProvider`

#### Fields (5)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `code` | `Selection` | — | — | — | — | Y |
| `redsys_merchant_code` | `Char` | — | — | — | — | Y |
| `redsys_merchant_terminal` | `Char` | — | — | — | — | Y |
| `redsys_secret_key` | `Char` | — | — | — | — | Y |
| `cipher` | `Cipher` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.transaction (`payment.transaction`)

Override of `payment` to set the Redsys-specific `provider_reference`.

**File:** `payment_transaction.py` | Class: `PaymentTransaction`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `create` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
