---
title: "Payment Iyzico"
module: payment_iyzico
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Iyzico

## Overview

Module `payment_iyzico` — auto-generated from source code.

**Source:** `addons/payment_iyzico/`
**Models:** 2
**Fields:** 3
**Methods:** 0

## Models

### payment.provider (`payment.provider`)

Override of `payment` to return the supported currencies.

**File:** `payment_provider.py` | Class: `PaymentProvider`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `code` | `Selection` | — | — | — | — | Y |
| `iyzico_key_id` | `Char` | — | — | — | — | Y |
| `iyzico_key_secret` | `Char` | — | — | — | — | Y |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.transaction (`payment.transaction`)

Override of `payment` to return Iyzico specific rendering values.

         Note: `self.ensure_one()` from :meth:`_get_processing_values`

        :return: The provider-specific processing values.
   

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
