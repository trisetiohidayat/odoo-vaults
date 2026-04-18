---
title: "Pos Online Payment Self Order"
module: pos_online_payment_self_order
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Pos Online Payment Self Order

## Overview

Module `pos_online_payment_self_order` — auto-generated from source code.

**Source:** `addons/pos_online_payment_self_order/`
**Models:** 5
**Fields:** 3
**Methods:** 5

## Models

### payment.transaction (`payment.transaction`)

—

**File:** `payment_transaction.py` | Class: `PaymentTransaction`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### pos.config (`pos.config`)

—

**File:** `pos_config.py` | Class: `PosConfig`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `self_order_online_payment_method_id` | `Many2one` | — | — | — | Y | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `has_valid_self_payment_method` | |


### pos.order (`pos.order`)

—

**File:** `pos_order.py` | Class: `PosOrder`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `use_self_order_online_payment` | `Boolean` | Y | — | — | Y | — |


#### Methods (4)

| Method | Description |
|--------|-------------|
| `get_order_to_print` | |
| `create` | |
| `write` | |
| `get_and_set_online_payments_data` | |


### pos.payment.method (`pos.payment.method`)

—

**File:** `pos_payment_method.py` | Class: `PosPaymentMethod`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### res.config.settings (`res.config.settings`)

—

**File:** `res_config_settings.py` | Class: `ResConfigSettings`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `pos_self_order_online_payment_method_id` | `Many2one` | — | — | Y | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
