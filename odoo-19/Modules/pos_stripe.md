---
title: "Pos Stripe"
module: pos_stripe
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Pos Stripe

## Overview

Module `pos_stripe` — auto-generated from source code.

**Source:** `addons/pos_stripe/`
**Models:** 1
**Fields:** 1
**Methods:** 4

## Models

### pos.payment.method (`pos.payment.method`)

Captures the payment identified by paymentIntentId.

        :param paymentIntentId: the id of the payment to capture
        :param amount: without this parameter the entire authorized
              

**File:** `pos_payment_method.py` | Class: `PosPaymentMethod`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `stripe_serial_number` | `Char` | — | — | — | — | — |


#### Methods (4)

| Method | Description |
|--------|-------------|
| `stripe_connection_token` | |
| `stripe_payment_intent` | |
| `stripe_capture_payment` | |
| `action_stripe_key` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
