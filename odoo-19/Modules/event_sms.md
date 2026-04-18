---
title: "Event Sms"
module: event_sms
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Event Sms

## Overview

Module `event_sms` — auto-generated from source code.

**Source:** `addons/event_sms/`
**Models:** 4
**Fields:** 5
**Methods:** 1

## Models

### event.mail (`event.mail`)

SMS action: send SMS to attendees

**File:** `event_mail.py` | Class: `EventMail`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `notification_type` | `Selection` | Y | — | — | — | — |
| `template_ref` | `Reference` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### event.mail.registration (`event.mail.registration`)

—

**File:** `event_mail_registration.py` | Class: `EventMailRegistration`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### event.type.mail (`event.type.mail`)

—

**File:** `event_type_mail.py` | Class: `EventTypeMail`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `notification_type` | `Selection` | Y | — | — | — | — |
| `template_ref` | `Reference` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sms.template (`sms.template`)

Context-based hack to filter reference field in a m2o search box to emulate a domain the ORM currently does not support.

        As we can not specify a domain on a reference field, we added a contex

**File:** `sms_template.py` | Class: `SmsTemplate`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `domain` | `Domain` | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `unlink` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
