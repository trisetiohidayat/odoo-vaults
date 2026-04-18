---
title: "Pos Qfpay"
module: pos_qfpay
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Pos Qfpay

## Overview

Module `pos_qfpay` — auto-generated from source code.

**Source:** `addons/pos_qfpay/`
**Models:** 1
**Fields:** 6
**Methods:** 1

## Models

### pos.payment.method (`pos.payment.method`)

—

**File:** `pos_payment_method.py` | Class: `PosPaymentMethod`

#### Fields (6)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `qfpay_terminal_ip_address` | `Char` | — | — | — | — | — |
| `qfpay_pos_key` | `Char` | — | — | — | — | — |
| `qfpay_notification_key` | `Char` | — | — | — | — | — |
| `qfpay_latest_response` | `Char` | — | — | — | — | — |
| `qfpay_payment_type` | `Selection` | — | — | — | — | — |
| `cipher` | `Cipher` | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `qfpay_sign_request` | |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
