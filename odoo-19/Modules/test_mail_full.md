# Mail Tests Full (`test_mail_full`)

**Category:** Hidden
**Depends:** `mail`, `mail_bot`, `portal`, `rating`, `mass_mailing`, `mass_mailing_sms`, `phone_validation`, `sms`, `test_mail`, `test_mail_sms`, `test_mass_mailing`
**Installable:** True
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Comprehensive mail module test suite combining `test_mail`, `test_mail_sms`, and `test_mass_mailing` with all mail sub-modules. Tests portal access, rating systems, SMS, phone validation, and full mailing features including opt-out and blacklist.

## Models

### `mail.test.portal` — Portal-accessible test model
**Fields:** `name`, `email`, `partner_id`

**Methods:**
- `_compute_access_url()` — Returns portal-accessible URL for the record.

### `mail.test.portal.no.partner` — Portal without partner
**Methods:**
- `_compute_access_url()` — Access URL without partner association.

### `mail.test.portal.public.access.action` — Public access test model
Tests public (no login required) portal access.

**Methods:**
- `_compute_access_url()` — Returns public access URL.
- `_get_access_action(access_uid, force_website)` — Returns public access action (no login).

### `mail.test.rating` — Rating test model
**Fields:** `name`, `email_from`, `phone_nbr`, `partner_id`

**Methods:**
- `_compute_email_from()` / `_compute_phone_nbr()` — Field computation.
- `_mail_get_partner_fields()` — Returns `['partner_id']`.
- `_phone_get_number_fields()` — Returns `['phone_nbr']`.
- `_rating_apply_get_default_subtype_id()` — Returns rating notification subtype.
- `_rating_get_partner()` — Returns rated partner.
- `_allow_publish_rating_stats()` — Controls rating visibility.

### `mail.test.rating.thread` — Rating with thread
**Fields:** `name`, `rating_ids` (M2M to rating.rating)

**Methods:**
- `_mail_get_partner_fields()` / `_rating_get_partner()` — Thread and rating mixin.

### `mail.test.rating.thread.read` — Read-only rating thread
Inherits read access from `portal` for portal access tests.

## Dependencies

| Module | Purpose |
|--------|---------|
| `test_mail` | Base mail test models |
| `test_mail_sms` | SMS test models |
| `test_mass_mailing` | Mass mailing test models |
| `mail_bot` | Odoo Bot |
| `portal` | Portal access |
| `rating` | Rating system |
| `phone_validation` | Phone number validation |
| `sms` | SMS messaging |
| `mass_mailing` / `mass_mailing_sms` | Email and SMS marketing |

## Data

- `security/ir.model.access.csv` — Access rights for portal/rating test models
- `security/ir_rule_data.xml` — Record rules for multi-company/multi-user access tests
- `views/test_portal_template.xml` — Portal email templates
- `data/mail_message_subtype_data.xml` — Mail message subtypes
