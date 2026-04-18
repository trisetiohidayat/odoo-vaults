---
title: "Sms Twilio"
module: sms_twilio
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Sms Twilio

## Overview

Module `sms_twilio` — auto-generated from source code.

**Source:** `addons/sms_twilio/`
**Models:** 7
**Fields:** 15
**Methods:** 5

## Models

### mail.notification (`mail.notification`)

—

**File:** `mail_notification.py` | Class: `MailNotification`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `failure_type` | `Selection` | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `fields_get` | |


### res.company (`res.company`)

—

**File:** `res_company.py` | Class: `ResCompany`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `sms_provider` | `Selection` | — | — | — | — | — |
| `sms_twilio_account_sid` | `Char` | — | — | — | — | — |
| `sms_twilio_auth_token` | `Char` | — | — | — | — | — |
| `sms_twilio_number_ids` | `One2many` | — | — | — | — | — |


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
| `sms_provider` | `Selection` | — | — | Y | — | Y |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_open_sms_twilio_account_manage` | |


### sms.composer (`sms.composer`)

—

**File:** `sms_composer.py` | Class: `SendSMS`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sms.sms (`sms.sms`)

Store the sid of Twilio on the SMS tracking record (as SMS will be deleted)
        :param results: a list of dict in the form [{
            'uuid': Odoo's id of the SMS,
            'state': State o

**File:** `sms_sms.py` | Class: `SmsSms`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `sms_twilio_sid` | `Char` | — | — | Y | — | — |
| `record_company_id` | `Many2one` | — | — | — | — | — |
| `failure_type` | `Selection` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `create` | |
| `fields_get` | |


### sms.tracker (`sms.tracker`)

Update the SMS tracker with the Twilio Status and Error code/msg

**File:** `sms_tracker.py` | Class: `SmsTracker`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `sms_twilio_sid` | `Char` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sms.twilio.number (`sms.twilio.number`)

—

**File:** `sms_twilio_number.py` | Class: `SmsTwilioNumber`

#### Fields (5)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `company_id` | `Many2one` | — | — | — | — | Y |
| `sequence` | `Integer` | Y | — | Y | — | Y |
| `number` | `Char` | Y | — | Y | — | Y |
| `country_id` | `Many2one` | Y | — | Y | — | Y |
| `country_code` | `Char` | Y | — | Y | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_unlink` | |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
