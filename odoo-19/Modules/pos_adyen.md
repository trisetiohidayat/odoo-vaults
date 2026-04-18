---
title: "Pos Adyen"
module: pos_adyen
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Pos Adyen

## Overview

Module `pos_adyen` — auto-generated from source code.

**Source:** `addons/pos_adyen/`
**Models:** 3
**Fields:** 7
**Methods:** 2

## Models

### pos.config (`pos.config`)

—

**File:** `pos_config.py` | Class: `PosConfig`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `adyen_ask_customer_for_tip` | `Boolean` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### pos.payment.method (`pos.payment.method`)

—

**File:** `pos_payment_method.py` | Class: `PosPaymentMethod`

#### Fields (5)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `adyen_api_key` | `Char` | — | — | — | — | — |
| `adyen_terminal_identifier` | `Char` | — | — | — | — | — |
| `adyen_test_mode` | `Boolean` | — | — | — | — | — |
| `adyen_latest_response` | `Char` | — | — | — | — | — |
| `adyen_event_url` | `Char` | — | — | — | Y | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `get_latest_adyen_status` | |
| `proxy_adyen_request` | |


### res.config.settings (`res.config.settings`)

—

**File:** `res_config_settings.py` | Class: `ResConfigSettings`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `pos_adyen_ask_customer_for_tip` | `Boolean` | Y | — | — | Y | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
