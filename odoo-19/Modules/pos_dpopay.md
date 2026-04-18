---
title: "Pos Dpopay"
module: pos_dpopay
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Pos Dpopay

## Overview

Module `pos_dpopay` — auto-generated from source code.

**Source:** `addons/pos_dpopay/`
**Models:** 2
**Fields:** 11
**Methods:** 1

## Models

### pos.payment (`pos.payment`)

—

**File:** `pos_payment.py` | Class: `PosPayment`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `dpopay_rrn` | `Char` | — | — | — | — | Y |
| `dpopay_transaction_ref` | `Char` | — | — | — | — | Y |
| `dpopay_mobile_money_phone` | `Char` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### pos.payment.method (`pos.payment.method`)

—

**File:** `pos_payment_method.py` | Class: `PosPaymentMethod`

#### Fields (8)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `dpopay_client_id` | `Char` | — | — | — | — | — |
| `dpopay_client_secret` | `Char` | — | — | — | — | — |
| `dpopay_mid` | `Char` | — | — | — | — | — |
| `dpopay_tid` | `Char` | — | — | — | — | — |
| `dpopay_payment_mode` | `Selection` | — | — | — | — | — |
| `dpopay_chain_id` | `Char` | — | — | — | — | — |
| `dpopay_test_mode` | `Boolean` | — | — | — | — | — |
| `dpopay_bearer_token` | `Char` | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `send_dpopay_request` | |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
