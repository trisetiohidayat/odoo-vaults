---
title: "Payment Authorize"
module: payment_authorize
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Payment Authorize

## Overview

Module `payment_authorize` — auto-generated from source code.

**Source:** `addons/payment_authorize/`
**Models:** 3
**Fields:** 14
**Methods:** 1

## Models

### payment.provider (`payment.provider`)

Override of `payment` to enable additional features.

**File:** `payment_provider.py` | Class: `PaymentProvider`

#### Fields (6)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `code` | `Selection` | — | — | — | — | Y |
| `authorize_login` | `Char` | — | — | — | — | Y |
| `authorize_transaction_key` | `Char` | — | — | — | — | Y |
| `authorize_signature_key` | `Char` | — | — | — | — | Y |
| `authorize_client_key` | `Char` | — | — | — | — | — |
| `authorize_API` | `AuthorizeAPI` | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_update_merchant_details` | |


### payment.token (`payment.token`)

—

**File:** `payment_token.py` | Class: `PaymentToken`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `authorize_profile` | `Char` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### payment.transaction (`payment.transaction`)

Override of payment to return an access token as provider-specific processing values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic

**File:** `payment_transaction.py` | Class: `PaymentTransaction`

#### Fields (7)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `authorize_API` | `AuthorizeAPI` | — | — | — | — | — |
| `authorize_API` | `AuthorizeAPI` | — | — | — | — | — |
| `authorize_api` | `AuthorizeAPI` | — | — | — | — | — |
| `authorize_API` | `AuthorizeAPI` | — | — | — | — | — |
| `authorize_API` | `AuthorizeAPI` | — | — | — | — | — |
| `tx_details` | `AuthorizeAPI` | — | — | — | — | — |
| `authorize_API` | `AuthorizeAPI` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
