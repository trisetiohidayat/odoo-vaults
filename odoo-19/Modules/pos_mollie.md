---
title: "Pos Mollie"
module: pos_mollie
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Pos Mollie

## Overview

Module `pos_mollie` — auto-generated from source code.

**Source:** `addons/pos_mollie/`
**Models:** 1
**Fields:** 2
**Methods:** 3

## Models

### pos.payment.method (`pos.payment.method`)

—

**File:** `pos_payment_method.py` | Class: `PosPaymentMethod`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `mollie_terminal_id` | `Char` | — | — | — | — | — |
| `mollie_payment_provider_id` | `Many2one` | — | — | — | — | — |


#### Methods (3)

| Method | Description |
|--------|-------------|
| `mollie_create_payment` | |
| `mollie_create_refund` | |
| `mollie_cancel_payment` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
