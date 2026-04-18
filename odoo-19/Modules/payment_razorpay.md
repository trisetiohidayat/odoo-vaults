---
title: "Payment Razorpay"
module: payment_razorpay
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Razorpay

## Overview

Module `payment_razorpay` — auto-generated from source code.

**Source:** `addons/payment_razorpay/`
**Models:** 3
**Fields:** 9
**Methods:** 2

## Models

### payment.provider (`payment.provider`)

Override of `payment` to enable additional features.

**File:** `payment_provider.py` | Class: `PaymentProvider`

#### Fields (9)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `code` | `Selection` | — | — | — | — | — |
| `razorpay_key_id` | `Char` | — | — | — | — | — |
| `razorpay_key_secret` | `Char` | — | — | — | — | — |
| `razorpay_webhook_secret` | `Char` | — | — | — | — | — |
| `razorpay_account_id` | `Char` | — | — | — | — | — |
| `razorpay_refresh_token` | `Char` | — | — | — | — | — |
| `razorpay_public_token` | `Char` | — | — | — | — | — |
| `razorpay_access_token` | `Char` | — | — | — | — | — |
| `razorpay_access_token_expiry` | `Datetime` | Y | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `action_start_onboarding` | |
| `action_razorpay_create_webhook` | |


### payment.token (`payment.token`)

Return a warning message when the maximum payment amount is exceeded.

        :param float amount: The amount to be paid.
        :param currency_id: The currency of the amount.
        :return: A wa

**File:** `payment_token.py` | Class: `PaymentToken`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.transaction (`payment.transaction`)

Override of `payment` to return razorpay-specific processing values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific pro

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
