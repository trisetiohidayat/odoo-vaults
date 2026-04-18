---
title: "Pos Razorpay"
module: pos_razorpay
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Pos Razorpay

## Overview

Module `pos_razorpay` — auto-generated from source code.

**Source:** `addons/pos_razorpay/`
**Models:** 2
**Fields:** 11
**Methods:** 4

## Models

### pos.payment (`pos.payment`)

—

**File:** `pos_payment.py` | Class: `PosPayment`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `razorpay_reverse_ref_no` | `Char` | — | — | — | — | — |
| `razorpay_p2p_request_id` | `Char` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### pos.payment.method (`pos.payment.method`)

—

**File:** `pos_payment_method.py` | Class: `PosPaymentMethod`

#### Fields (9)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `razorpay_tid` | `Char` | — | — | — | — | — |
| `razorpay_allowed_payment_modes` | `Selection` | — | — | — | — | — |
| `razorpay_username` | `Char` | — | — | — | — | — |
| `razorpay_api_key` | `Char` | — | — | — | — | — |
| `razorpay_test_mode` | `Boolean` | — | — | — | — | — |
| `razorpay` | `RazorpayPosRequest` | — | — | — | — | — |
| `razorpay` | `RazorpayPosRequest` | — | — | — | — | — |
| `razorpay` | `RazorpayPosRequest` | — | — | — | — | — |
| `razorpay` | `RazorpayPosRequest` | — | — | — | — | — |


#### Methods (4)

| Method | Description |
|--------|-------------|
| `razorpay_make_refund_request` | |
| `razorpay_make_payment_request` | |
| `razorpay_fetch_payment_status` | |
| `razorpay_cancel_payment_request` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
