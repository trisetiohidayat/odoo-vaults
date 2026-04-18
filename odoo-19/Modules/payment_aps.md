---
title: "Payment Aps"
module: payment_aps
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Aps

## Overview

Module `payment_aps` — auto-generated from source code.

**Source:** `addons/payment_aps/`
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
| `aps_merchant_identifier` | `Char` | — | — | — | — | Y |
| `aps_access_code` | `Char` | — | — | — | — | Y |
| `aps_sha_request` | `Char` | — | — | — | — | Y |
| `aps_sha_response` | `Char` | — | — | — | — | Y |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.transaction (`payment.transaction`)

Override of `payment` to ensure that APS' requirements for references are satisfied.

        APS' requirements for transaction are as follows:
        - References can only be made of alphanumeric ch

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
