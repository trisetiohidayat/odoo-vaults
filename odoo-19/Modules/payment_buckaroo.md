---
title: "Payment Buckaroo"
module: payment_buckaroo
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Buckaroo

## Overview

Module `payment_buckaroo` — auto-generated from source code.

**Source:** `addons/payment_buckaroo/`
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
| `buckaroo_website_key` | `Char` | — | — | — | — | Y |
| `buckaroo_secret_key` | `Char` | — | — | — | — | Y |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.transaction (`payment.transaction`)

Override of payment to return Buckaroo-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific proces

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
