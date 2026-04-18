---
title: "Account Qr Code Emv"
module: account_qr_code_emv
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Account Qr Code Emv

## Overview

Module `account_qr_code_emv` — auto-generated from source code.

**Source:** `addons/account_qr_code_emv/`
**Models:** 1
**Fields:** 5
**Methods:** 0

## Models

### res.partner.bank (`res.partner.bank`)

Return an error for emv_qr if the account's country does no match any methods found in inheriting modules.

**File:** `res_bank.py` | Class: `ResPartnerBank`

#### Fields (5)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `display_qr_setting` | `Boolean` | Y | — | — | — | — |
| `include_reference` | `Boolean` | Y | — | — | — | — |
| `proxy_type` | `Selection` | Y | — | — | — | — |
| `country_proxy_keys` | `Char` | Y | — | — | — | — |
| `proxy_value` | `Char` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [[Modules/Base]]
- [[Modules/Account]]
