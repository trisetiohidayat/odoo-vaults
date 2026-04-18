---
title: "Payment Demo"
module: payment_demo
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Demo

## Overview

Module `payment_demo` — auto-generated from source code.

**Source:** `addons/payment_demo/`
**Models:** 3
**Fields:** 3
**Methods:** 3

## Models

### payment.provider (`payment.provider`)

Override of `payment` to enable additional features.

**File:** `payment_provider.py` | Class: `PaymentProvider`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `code` | `Selection` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.token (`payment.token`)

Override of `payment` to build the display name without padding.

        Note: self.ensure_one()

        :param list args: The arguments passed by QWeb when calling this method.
        :param bool 

**File:** `payment_token.py` | Class: `PaymentToken`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `demo_simulated_state` | `Selection` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.transaction (`payment.transaction`)

Set the state of the demo transaction to 'done'.

        Note: self.ensure_one()

        :return: None

**File:** `payment_transaction.py` | Class: `PaymentTransaction`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `capture_manually` | `Boolean` | — | — | Y | — | — |


#### Methods (3)

| Method | Description |
|--------|-------------|
| `action_demo_set_done` | |
| `action_demo_set_canceled` | |
| `action_demo_set_error` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
