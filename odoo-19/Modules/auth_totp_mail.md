---
title: "Auth Totp Mail"
module: auth_totp_mail
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Auth Totp Mail

## Overview

Module `auth_totp_mail` — auto-generated from source code.

**Source:** `addons/auth_totp_mail/`
**Models:** 3
**Fields:** 3
**Methods:** 7

## Models

### auth_totp.device (`auth_totp.device`)

Notify users when trusted devices are removed from their account.

**File:** `auth_totp_device.py` | Class: `Auth_TotpDevice`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `unlink` | |


### res.config.settings (`res.config.settings`)

—

**File:** `res_config_settings.py` | Class: `ResConfigSettings`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `auth_totp_enforce` | `Boolean` | — | — | — | — | Y |
| `auth_totp_policy` | `Selection` | — | Y | — | — | Y |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `get_values` | |


### res.users (`res.users`)

Send an alert on new connection.

        - 2FA enabled -> only for new device
        - Not enabled -> no alert

**File:** `res_users.py` | Class: `ResUsers`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `match` | `TOTP` | — | — | — | — | — |


#### Methods (5)

| Method | Description |
|--------|-------------|
| `write` | |
| `authenticate` | |
| `action_open_my_account_settings` | |
| `get_totp_invite_url` | |
| `action_totp_invite` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
