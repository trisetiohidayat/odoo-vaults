# Mass Mailing SMS

## Overview
- **Name:** SMS Marketing
- **Category:** Marketing/Email Marketing
- **Summary:** Design, send and track SMS campaigns
- **Version:** 1.1
- **Depends:** `portal`, `mass_mailing`, `sms`
- **License:** LGPL-3
- **Application:** True

## Description
Full SMS marketing module for Odoo. Allows designing and sending SMS campaigns, tracking delivery, and managing SMS-specific contact lists. Supports A/B testing for SMS campaigns.

## Models

### `mailing.contact` (extends `mailing.contact`)
| Field | Type | Description |
|-------|------|-------------|
| `mobile` | Char | Mobile phone number |
Inherits `mail.thread.phone` for SMS blacklists.

### `mailing.list` (extends `mailing.list`)
| Field | Type | Description |
|-------|------|-------------|
| `contact_count_sms` | Integer | Count of contacts with valid SMS numbers |

#### Methods
- `action_view_mailings()`: Opens SMS mailings for this list (if context `mailing_sms` is set)
- `action_view_contacts_sms()`: Opens contacts with valid SMS recipients
- `action_send_mailing_sms()`: Opens SMS composer for this list
- `_get_contact_statistics_fields()`: Adds SMS-specific SQL aggregates (contact_count_sms)
- `_get_contact_statistics_joins()`: Adds SMS blacklist join to contact statistics
- `_mailing_get_opt_out_list_sms()`: Returns contacts opted out of SMS for this list

### `mailing.mailing` (extends `mailing.mailing`)
| Field | Type | Description |
|-------|------|-------------|
| `mailing_type` | Selection | Adds `sms` option |
| `sms_subject` | Char | Title for SMS messages (related to subject) |
| `body_plaintext` | Text | SMS body text (computed from sms_template_id) |
| `sms_template_id` | Many2one | SMS template used for the message |
| `sms_has_insufficient_credit` | Boolean | Shows IAP credit warning |
| `sms_has_unregistered_account` | Boolean | Shows IAP account warning |
| `sms_force_send` | Boolean | Send immediately instead of queuing |
| `sms_allow_unsubscribe` | Boolean | Include opt-out link in SMS |
| `ab_testing_sms_winner_selection` | Selection | A/B testing metric for SMS (related to campaign) |
| `ab_testing_mailings_sms_count` | Integer | Related SMS mailing count |

#### Methods
- `default_get()`: Defaults `keep_archives=True` for SMS mailings
- `_compute_medium_id()`: Sets SMS medium for SMS-type mailings
- `_compute_body_plaintext()`: Computes body from SMS template
- `_compute_sms_has_iap_failure()`: Checks for IAP credit/account failures
- `create()`: Uses `sms_subject` as mailing name for SMS type
- `action_retry_failed()`: Retries failed SMS for SMS-type mailings
- `action_retry_failed_sms()`: Resets failed SMS and puts mailing back in queue
- `action_test()`: Opens SMS test wizard for SMS-type mailings
- `_action_view_traces_filtered()`: Uses SMS trace views for SMS mailings
- `action_buy_sms_credits()`: Opens IAP credits purchase page
- `_get_opt_out_list_sms()`: Returns opted-out contacts for this mailing
- `_get_seen_list_sms()`: Returns already-targeted contacts for deduplication

### `mailing.trace` (extends `mailing.trace`)
Adds SMS-specific trace fields and methods.

### `sms.sms` (extends `sms.sms`)
Links SMS records to mailing campaigns for tracking.

### `sms.tracker` (extends `sms.tracker`)
Links SMS trackers to mailing traces for delivery tracking.

### `res.users` (extends `res.users`)
Adds portal access to SMS mailing features.

### `utm.campaign` (extends `utm.campaign`)
Extends A/B testing with SMS-specific winner selection options.

## Controllers

### `MassMailController` (extends `mass_mailing.main`)
Extends mass mailing tracking with SMS-specific endpoints.

## Related
- [[Modules/mass_mailing]] - Email marketing base
- [[Modules/sms]] - SMS sending module
- [[Modules/portal]] - Customer portal
