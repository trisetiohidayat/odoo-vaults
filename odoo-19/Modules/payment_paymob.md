---
title: "Payment Paymob"
module: payment_paymob
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Paymob

## Overview

Module `payment_paymob` — auto-generated from source code.

**Source:** `addons/payment_paymob/`
**Models:** 2
**Fields:** 6
**Methods:** 1

## Models

### res.country (`res.country`)

Override of `payment` to return the default payment method codes.

**File:** `payment_provider.py` | Class: `PaymentProvider`

#### Fields (6)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `code` | `Selection` | — | — | — | — | — |
| `paymob_account_country_id` | `Many2one` | — | — | — | — | — |
| `paymob_public_key` | `Char` | — | — | — | — | Y |
| `paymob_secret_key` | `Char` | — | — | — | — | Y |
| `paymob_hmac_key` | `Char` | — | — | — | — | Y |
| `paymob_api_key` | `Char` | — | — | — | — | Y |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_sync_paymob_payment_methods` | |


### payment.transaction (`payment.transaction`)

Override of `payment` to ensure that Paymob references are unique.

        :param str provider_code: The code of the provider handling the transaction.
        :param str prefix: The custom prefix us

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

- [Modules/Base](base.md)
- [Modules/Base](base.md)
