---
title: "Delivery Mondialrelay"
module: delivery_mondialrelay
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Delivery Mondialrelay

## Overview

Module `delivery_mondialrelay` — auto-generated from source code.

**Source:** `addons/delivery_mondialrelay/`
**Models:** 3
**Fields:** 4
**Methods:** 3

## Models

### delivery.carrier (`delivery.carrier`)

—

**File:** `delivery_carrier.py` | Class: `DeliveryCarrier`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `is_mondialrelay` | `Boolean` | Y | — | — | — | — |
| `mondialrelay_brand` | `Char` | Y | — | — | — | — |
| `mondialrelay_packagetype` | `Char` | Y | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `fixed_get_tracking_link` | |
| `base_on_rule_get_tracking_link` | |


### res.partner (`res.partner`)

—

**File:** `res_partner.py` | Class: `ResPartner`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `is_mondialrelay` | `Boolean` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sale.order (`sale.order`)

—

**File:** `sale_order.py` | Class: `SaleOrder`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_confirm` | |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
