---
Module: mass_mailing_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #mass_mailing #sms #iap
---

## Overview

Core SMS marketing module for Odoo. Adds `mailing_type='sms'` support to `mailing.mailing`, full SMS send pipeline via IAP, SMS-specific trace tracking, SMS A/B testing, link shortening, and unsubscription handling.

**Depends:** `mass_mailing`, `sms`

**Key Behavior:** All mass SMS goes through IAP credits. Supports both direct send and queued mode. Opt-out link management via `/sms/<mailing_id>/unsubscribe/<trace_code>`.

---

## Models

### `mailing.mailing` (Inherited)

**Inherited from:** `mailing.mailing`

| Field | Type | Note |
|-------|------|------|
| `mailing_type` | Selection | Adds `'sms'` — SMS mailing type |
| `sms_subject` | Char | Title field; related to `subject` |
| `body_plaintext` | Text | Compute from `sms_template_id` when `mailing_type='sms'` |
| `sms_template_id` | Many2one `sms.template` | Template for SMS body |
| `sms_has_insufficient_credit` | Boolean (compute) | Detected from trace failures of type `sms_credit` |
| `sms_has_unregistered_account` | Boolean (compute) | Detected from trace failures of type `sms_acc` |
| `sms_force_send` | Boolean | Immediately send instead of queue |
| `sms_allow_unsubscribe` | Boolean | Include opt-out link in SMS body |
| `ab_testing_sms_winner_selection` | Selection | SMS-specific A/B winner criteria (related to campaign) |
| `ab_testing_mailings_sms_count` | Integer (related) | Count of SMS A/B test mailings in campaign |

| Method | Returns | Note |
|--------|---------|------|
| `action_test()` | `ir.actions.act_window` | Uses `mailing.sms.test` wizard for SMS |
| `action_send_sms(res_ids)` | Boolean | Creates `sms.composer` in mass mode and sends |
| `action_retry_failed()` | — | Dispatches to `action_retry_failed_sms` for SMS type |
| `action_retry_failed_sms()` | — | Deletes failed SMS records and re-queues |
| `_action_send_mail(res_ids)` | — | Routes SMS mailings to `action_send_sms` |
| `_action_view_traces_filtered(view_filter)` | Action | Uses SMS-specific trace views when `mailing_type='sms'` |
| `action_buy_sms_credits()` | `ir.actions.act_url` | Opens IAP credits purchase URL |
| `_compute_medium_id()` | — | Auto-assigns SMS UTM medium when `mailing_type='sms'` |
| `_compute_body_plaintext()` | — | Syncs body from template |
| `_get_opt_out_list_sms()` | list | Delegates to model-specific `_mailing_get_opt_out_list_sms` |
| `_get_seen_list_sms()` | tuple | SQL query returning (seen_ids, seen_numbers) |
| `_send_sms_get_composer_values(res_ids)` | dict | Builds `sms.composer` values for mass send |
| `convert_links()` | dict | Shortens URLs in SMS body with tracking IDs |
| `get_sms_link_replacements_placeholders()` | dict | Returns char counts for link placeholders |
| `_get_default_mailing_domain()` | Domain | Adds `phone_sanitized_blacklisted=False` for SMS |
| `_prepare_statistics_email_values()` | dict | Overrides KPI table for SMS (received/clicked/bounced) |
| `_get_ab_testing_winner_selection()` | dict | Returns SMS-specific winner selection |
| `_get_ab_testing_siblings_mailings()` | recordset | Filters siblings by SMS type in campaign |
| `_get_default_ab_testing_campaign_values(values)` | dict | Sets SMS subject and SMS winner selection on campaign |

### `mailing.trace` (Inherited)

**Inherited from:** `mailing.trace`

| Field | Type | Note |
|-------|------|------|
| `trace_type` | Selection | Adds `'sms'` — SMS trace type |
| `sms_id` | Many2one `sms.sms` | Non-stored compute linking to SMS record |
| `sms_id_int` | Integer | Integer ID (indexed btree_not_null) for deleted-SMS resilience |
| `sms_tracker_ids` | One2many `sms.tracker` | Trackers linked to this trace |
| `sms_number` | Char | Sanitized recipient phone number |
| `sms_code` | Char | 3-char random code for unsubscription obfuscation |
| `failure_type` | Selection | Adds SMS-specific failure types (missing, format, credit, blacklisted, duplicate, optout, Twilio codes, etc.) |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_sms_id()` | — | Resolves `sms_id` from `sms_id_int`, excluding deleted SMS |
| `create(values_list)` | recordset | Auto-generates `sms_code` if `trace_type='sms'` and not provided |
| `_get_random_code()` | str | Returns 3 random alphanumeric chars |

### `mailing.list` (Inherited)

**Inherited from:** `mailing.list`

| Field | Type | Note |
|-------|------|------|
| `contact_count_sms` | Integer (compute) | Count of valid SMS-reachable contacts |

| Method | Returns | Note |
|--------|---------|------|
| `action_view_contacts_sms()` | Action | Opens contact list filtered for valid SMS recipients |
| `action_send_mailing_sms()` | Action | Opens SMS mailing form for this list |
| `_get_contact_statistics_fields()` | dict | Adds `contact_count_sms` SQL aggregate and SMS in blacklist check |
| `_get_contact_statistics_joins()` | str | Adds `phone_blacklist` join for SMS-specific blacklisting |
| `_mailing_get_opt_out_list_sms(mailing)` | list | Returns contact IDs opt-ed out on all lists but not opt-ed in on any |

### `mailing.contact` (Inherited)

**Inherited from:** `mailing.contact`, `mail.thread.phone`

| Field | Type | Note |
|-------|------|------|
| `mobile` | Char | Mobile phone number field |

### `sms.sms` (Inherited)

**Inherited from:** `sms.sms`

| Field | Type | Note |
|-------|------|------|
| `mailing_id` | Many2one `mailing.mailing` | Links SMS to its mass mailing |
| `mailing_trace_ids` | One2many `mailing.trace` | Linked traces via `sms_id_int` |

| Method | Returns | Note |
|--------|---------|------|
| `_update_body_short_links()` | dict | Appends `/s/<sms.id>` to shortened URLs for trace tracking |

### `sms.tracker` (Inherited)

**Inherited from:** `sms.tracker`

| Field | Type | Note |
|-------|------|------|
| `mailing_trace_id` | Many2one `mailing.trace` | Links tracker to mailing trace |

| Method | Returns | Note |
|--------|---------|------|
| `_action_update_from_provider_error(provider_error)` | tuple | Propagates error to traces |
| `_action_update_from_sms_state(sms_state, ...)` | — | Maps SMS state to trace status; triggers mailing completion check |
| `_update_sms_traces(trace_status, ...)` | recordset | Writes trace status, sets `sent_datetime` |
| `_update_sms_mailings(trace_status, traces)` | — | Marks mailing `done` when all traces are no longer `process` |

### `utm.campaign` (Inherited)

**Inherited from:** `utm.campaign`

| Field | Type | Note |
|-------|------|------|
| `mailing_sms_ids` | One2many `mailing.mailing` | SMS mailings only (filtered by `mailing_type='sms'`) |
| `mailing_sms_count` | Integer (compute) | Total SMS mailing count |
| `ab_testing_mailings_sms_count` | Integer (compute) | A/B test SMS mailing count |
| `ab_testing_sms_winner_selection` | Selection | SMS winner criteria: `manual`, `clicks_ratio` |

| Method | Returns | Note |
|--------|---------|------|
| `action_create_mass_sms()` | Action | Opens SMS mailing action with campaign context |
| `action_redirect_to_mailing_sms()` | Action | Opens list of campaign's SMS mailings |
| `_cron_process_mass_mailing_ab_testing()` | — | Extends parent cron; sends winner SMS mailing per campaign |

### `utm.medium` (Inherited)

**Inherited from:** `utm.medium`

| Method | Returns | Note |
|--------|---------|------|
| `_unlink_except_utm_medium_sms()` | — | Prevents deletion of SMS UTM medium |
| `SELF_REQUIRED_UTM_MEDIUMS_REF` | property | Adds `'mass_mailing_sms.utm_medium_sms': 'SMS'` to required mediums |

### `res.users` (Inherited)

**Inherited from:** `res.users`

| Method | Returns | Note |
|--------|---------|------|
| `_get_activity_groups()` | list | Splits `mailing.mailing` systray activity by `mailing_type` into Email Marketing and SMS Marketing groups |

---

## Controllers

### `MailingSMSController` (`mass_mailing_sms`)

| Route | Auth | Note |
|-------|------|------|
| `/sms/<mailing_id>/<trace_code>` | public | Renders SMS blacklist/opt-out page |
| `/sms/<mailing_id>/unsubscribe/<trace_code>` | public | Processes SMS unsubscribe request; validates + blacklists number |
| `/r/<code>/s/<sms_id_int>` | public | Short link redirect; records click with SMS trace |

---

## Critical Notes

- **IAP Credits Required:** SMS sending uses IAP. `sms_has_insufficient_credit` and `sms_has_unregistered_account` compute fields surface IAP failures on the mailing form.
- **Opt-out Flow:** Unsubscription is model-aware. If `mailing.list` is the target, updates `mailing.subscription.opt_out`. Otherwise blacklists via `phone.blacklist`.
- **Twilio Codes:** `twilio_authentication`, `twilio_callback`, `twilio_from_missing`, `twilio_from_to` failure types are Twilio-specific (migrated from bridge module in v18).
- **`_mailing_get_opt_out_list_sms`:** Called via `hasattr` check — each target model may implement its own opt-out logic.
- **A/B Testing Cron:** `_cron_process_mass_mailing_ab_testing` extends parent method to also handle SMS campaigns.
