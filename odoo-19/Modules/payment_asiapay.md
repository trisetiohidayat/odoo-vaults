---
title: "Payment Asiapay"
module: payment_asiapay
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Asiapay

## Overview

Module `payment_asiapay` — auto-generated from source code.

**Source:** `addons/payment_asiapay/`
**Models:** 2
**Fields:** 5
**Methods:** 0

## Models

### payment.provider (`payment.provider`)

Override of `payment` to return the default payment method codes.

**File:** `payment_provider.py` | Class: `PaymentProvider`

#### Fields (5)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `code` | `Selection` | — | — | — | — | — |
| `asiapay_brand` | `Selection` | — | — | — | — | Y |
| `asiapay_merchant_id` | `Char` | — | — | — | — | Y |
| `asiapay_secure_hash_secret` | `Char` | — | — | — | — | Y |
| `asiapay_secure_hash_function` | `Selection` | — | — | — | — | Y |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.transaction (`payment.transaction`)

Override of `payment` to ensure that AsiaPay requirements for references are satisfied.

        AsiaPay requirements for references are as follows:
        - References must be unique at provider lev

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
