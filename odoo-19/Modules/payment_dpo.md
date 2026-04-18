---
title: "Payment Dpo"
module: payment_dpo
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Dpo

## Overview

Module `payment_dpo` — auto-generated from source code.

**Source:** `addons/payment_dpo/`
**Models:** 2
**Fields:** 3
**Methods:** 0

## Models

### payment.provider (`payment.provider`)

Override of `payment` to return the default payment method codes.

**File:** `payment_provider.py` | Class: `PaymentProvider`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `code` | `Selection` | — | — | — | — | Y |
| `dpo_service_ref` | `Char` | — | — | — | — | Y |
| `dpo_company_token` | `Char` | — | — | — | — | Y |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.transaction (`payment.transaction`)

Override of `payment` to return DPO-specific processing values.

        Note: self.ensure_one() from `_get_processing_values`.

        :param dict processing_values: The generic processing values of

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
