---
title: "Pos Pine Labs"
module: pos_pine_labs
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Pos Pine Labs

## Overview

Module `pos_pine_labs` — auto-generated from source code.

**Source:** `addons/pos_pine_labs/`
**Models:** 2
**Fields:** 7
**Methods:** 3

## Models

### pos.payment (`pos.payment`)

—

**File:** `pos_payment.py` | Class: `PosPayment`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `pine_labs_plutus_transaction_ref` | `Char` | — | — | — | Y | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### pos.payment.method (`pos.payment.method`)

Sends a payment request to the Pine Labs POS API.

        :param dict data: Contains `amount`, `transactionNumber`, and `sequenceNumber`.
        :return: On success, returns `responseCode`, `status`

**File:** `pos_payment_method.py` | Class: `PosPaymentMethod`

#### Fields (6)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `pine_labs_merchant` | `Char` | — | — | — | Y | — |
| `pine_labs_store` | `Char` | — | — | — | Y | — |
| `pine_labs_client` | `Char` | — | — | — | — | — |
| `pine_labs_security_token` | `Char` | — | — | — | — | — |
| `pine_labs_allowed_payment_mode` | `Selection` | — | — | — | — | — |
| `pine_labs_test_mode` | `Boolean` | — | — | — | — | — |


#### Methods (3)

| Method | Description |
|--------|-------------|
| `pine_labs_make_payment_request` | |
| `pine_labs_fetch_payment_status` | |
| `pine_labs_cancel_payment_request` | |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
