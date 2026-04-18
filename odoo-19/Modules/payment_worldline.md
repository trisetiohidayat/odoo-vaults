---
title: "Payment Worldline"
module: payment_worldline
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Worldline

## Overview

Module `payment_worldline` — auto-generated from source code.

**Source:** `addons/payment_worldline/`
**Models:** 2
**Fields:** 6
**Methods:** 0

## Models

### payment.provider (`payment.provider`)

Override of `payment` to enable additional features.

**File:** `payment_provider.py` | Class: `PaymentProvider`

#### Fields (6)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `code` | `Selection` | — | — | — | — | Y |
| `worldline_pspid` | `Char` | — | — | — | — | Y |
| `worldline_api_key` | `Char` | — | — | — | — | Y |
| `worldline_api_secret` | `Char` | — | — | — | — | Y |
| `worldline_webhook_key` | `Char` | — | — | — | — | Y |
| `worldline_webhook_secret` | `Char` | Y | — | — | — | Y |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.transaction (`payment.transaction`)

Override of `payment` to ensure that Worldline requirement for references is satisfied.

        Worldline requires for references to be at most 30 characters long.

        :param str provider_code: 

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
