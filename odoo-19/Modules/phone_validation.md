---
title: "Phone Validation"
module: phone_validation
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Phone Validation

## Overview

Module `phone_validation` — auto-generated from source code.

**Source:** `addons/phone_validation/`
**Models:** 5
**Fields:** 6
**Methods:** 8

## Models

### mail.thread.phone (`mail.thread.phone`)

Purpose of this mixin is to offer two services

      * compute a sanitized phone number based on _phone_get_number_fields.
        It takes first sanitized value, trying each field returned by the
  

**File:** `mail_thread_phone.py` | Class: `MailThreadPhone`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `phone_sanitized` | `Char` | Y | — | — | Y | — |
| `phone_sanitized_blacklisted` | `Boolean` | Y | — | — | Y | — |
| `phone_blacklisted` | `Boolean` | Y | — | — | Y | — |
| `phone_mobile_search` | `Char` | — | — | — | Y | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `init` | |
| `phone_action_blacklist_remove` | |


### base (`base`)

This method returns the fields to use to find the number to use to
        send an SMS on a record.

**File:** `models.py` | Class: `Base`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### phone.blacklist (`phone.blacklist`)

Blacklist of phone numbers. Used to avoid sending unwanted messages to people.

**File:** `phone_blacklist.py` | Class: `PhoneBlacklist`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `number` | `Char` | — | — | — | — | Y |
| `active` | `Boolean` | — | — | — | — | — |


#### Methods (6)

| Method | Description |
|--------|-------------|
| `create` | |
| `write` | |
| `add` | |
| `remove` | |
| `phone_action_blacklist_remove` | |
| `action_add` | |


### res.partner (`res.partner`)

—

**File:** `res_partner.py` | Class: `ResPartner`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### res.users (`res.users`)

Blacklist the phone of the user after deleting it.

**File:** `res_users.py` | Class: `ResUsers`

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
