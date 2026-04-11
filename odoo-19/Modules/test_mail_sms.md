# SMS Tests (`test_mail_sms`)

**Category:** Hidden
**Depends:** `mail`, `sms`, `sms_twilio`, `test_orm`
**Installable:** True
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Test module for SMS messaging functionality. Provides test models simulating various SMS use cases including regular SMS, blacklist, opt-out, partner SMS, and many-to-many SMS, using `sms_twilio` as the SMS provider for outgoing SMS.

## Models

### `mail.test.sms` — Basic SMS test model
**Fields:** `name`, `phone_nbr`, `partner_id`

**Methods:**
- `_phone_get_number_fields()` — Returns `['phone_nbr']`
- `_mail_get_partner_fields()` — Returns `['partner_id']`

### `mail.test.sms.bl` — SMS blacklist test model
Tests SMS blacklist behavior (phone numbers in blacklist receive no SMS).

**Fields:** `name`, `phone_nbr`, `email`

**Methods:**
- `_compute_phone_nbr()` — Phone number computation.
- `_phone_get_number_fields()` — Returns `['phone_nbr']`
- `_mail_get_partner_fields()` — Returns `['partner_id']`

### `mail.test.sms.bl.activity` — SMS blacklist with activity
Extends blacklist model with `mail.activity` for activity-based SMS.

### `mail.test.sms.bl.optout` — SMS opt-out test model
Tests mailing list SMS opt-out behavior.

**Methods:**
- `_mailing_get_opt_out_list_sms(mailing)` — Returns opt-out records.

### `mail.test.sms.partner` — Partner-linked SMS model
**Methods:**
- `_mail_get_partner_fields()` — Returns `['partner_id']`
- `_mailing_get_opt_out_list_sms(mailing)` — Partner-based opt-out.

### `mail.test.sms.partner.2many` — Partner with 2many SMS records
**Methods:**
- `_mailing_get_opt_out_list_sms(mailing)` — Computes opt-out from multiple records.

### `sms.test.not.mail.thread` — Non-MailThread model
Sanity check model to ensure SMS sending works on non-threaded records.

**Methods:**
- `_mail_get_partner_fields()` — Returns empty (no thread)

## Data

- `security/ir.model.access.csv` — Access rights for SMS test models
