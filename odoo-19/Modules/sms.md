---
uid: sms
title: SMS Gateway
type: module
category: Sales/Sales
version: 3.0
created: 2026-04-06
modified: 2026-04-11
dependencies:
  - base
  - iap_mail
  - mail
  - phone_validation
author: Odoo S.A.
license: LGPL-3
summary: Framework for SMS text messaging via IAP gateway
tags:
  - #odoo
  - #odoo19
  - #modules
  - #sms
  - #iap
  - #messaging
  - #notifications
---

# SMS Gateway (`sms`)

## Module Overview

**Technical Name:** `sms`
**Category:** Sales/Sales
**Version:** 3.0
**Depends:** `base`, `iap_mail`, `mail`, `phone_validation`
**Auto-installs:** Yes
**License:** LGPL-3

The `sms` module provides a full SMS messaging framework built on Odoo's IAP (In-App Purchase) platform. It handles SMS creation, queuing, delivery through the IAP gateway, delivery report webhooks, and integration with `mail.thread` for notification dispatch. It does not include marketing campaigns — that is `sms_marketing`.

---

## Architecture

```
sms.sms              Core outgoing SMS record (queued, sent, failed)
sms.template         Reusable SMS templates with inline_field rendering
sms.tracker          Links SMS UUIDs to mail.notification records for status updates
sms.composer         Wizard for composing and sending SMS (3 modes)
sms.account.phone    Wizard: step 1 of IAP account registration (enter phone)
sms.account.code     Wizard: step 2 of IAP account registration (enter verification code)
sms.account.sender   Wizard: set the alphanumeric sender name
sms.template.preview Preview rendered template body against a live record
sms.template.reset   Reset template fields to XML source (template.reset.mixin)
```

### Inherited / Extended Models

| Model | Inheritance | Role |
|---|---|---|
| `base` (BaseModel) | Abstract mixin | `_sms_get_recipients_info()` available on every model |
| `mail.thread` | Abstract mixin | `_message_sms`, `_notify_thread_by_sms`, `_notify_thread` override |
| `mail.message` | Extension | Adds `message_type='sms'`, `has_sms_error` computed/search |
| `mail.notification` | Extension | Adds `notification_type='sms'`, `sms_id_int`, `sms_tracker_ids`, `sms_number`, delivery failure types |
| `mail.followers` | Extension | Routes SMS-type messages to `notif='sms'` in recipient data |
| `res.company` | Extension | `_get_sms_api_class()` returns `SmsApi` |
| `iap.account` | Extension | `sender_name` field, registration/sender wizard actions |
| `ir.model` | Extension | `is_mail_thread_sms` computed/search field for SMS-capable models |
| `ir.actions.server` | Extension | Adds `state='sms'`, `sms_template_id`, `sms_method` for server actions |

---

## Core Models

### `sms.sms` — Outgoing SMS Record

**File:** `~/odoo/odoo19/odoo/addons/sms/models/sms_sms.py`
**Inherits:** `base` (orm.base)
**Rec Name:** `number`
**Order:** `id DESC`

#### State Machine

```
outgoing ──send()──► process ──IAP success──► pending ──delivered webhook──► sent
    │                     │                         │
    │ (canceled)          │ (sent webhook)          │
    ▼                     ▼                         ▼
error ←─IAP failure── error                    error
    │
    └── resend_failed() ──► outgoing
```

| State | Meaning |
|---|---|
| `outgoing` | Queued, waiting for CRON or manual `send()` |
| `process` | Transmitted to IAP, awaiting response |
| `pending` | IAP accepted and sent to carrier (not yet confirmed delivered) |
| `sent` | Delivery confirmed via webhook |
| `error` | Failed; `failure_type` explains why |
| `canceled` | Manually canceled, blacklisted, or opted out |

#### Fields

| Field | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `uuid` | `Char` | `uuid4().hex` | `unique(uuid)` DB constraint | 32-char hex UUID assigned at create. Stable identifier for delivery report webhooks. Never changes. |
| `number` | `Char` | — | — | Raw phone number (pre-sanitization). Used as rec_name display. |
| `body` | `Text` | — | — | SMS message content. No ORM-level length check; IAP enforces GSM-7/UCS-2 limits. |
| `partner_id` | `Many2one(res.partner)` | — | — | Customer linked to this SMS. Populated in the `mail.thread` notification path. |
| `mail_message_id` | `Many2one(mail.message)` | — | `index=True` | Associated chatter message. Used to link SMS to the notification chain. |
| `state` | `Selection` | `'outgoing'` | `readonly=True, copy=False, required=True` | Current delivery state. See state machine above. |
| `failure_type` | `Selection` | — | `copy=False` | Why the SMS failed. Cleared to `False` on successful send. See full list below. |
| `sms_tracker_id` | `Many2one(sms.tracker)` | computed | — | Links to `sms.tracker` for this SMS. `_compute_sms_tracker_id` searches by `sms_uuid`. Read-only compute. |
| `to_delete` | `Boolean` | `False` | — | When `True`, record is marked for garbage collection. Prevents accidental re-notification after delivery. |

#### `failure_type` Values

**IAP-returned codes:**
- `sms_number_missing` — No number provided at all
- `sms_number_format` — Number failed E.164 formatting
- `sms_country_not_supported` — Carrier not supported by IAP
- `sms_registration_needed` — Country requires pre-registration with carrier
- `sms_credit` — Insufficient IAP credits
- `sms_server` — IAP internal server error
- `sms_acc` — IAP account not registered/activated
- `unknown` — Unmapped IAP response code

**Internally generated mass-mode codes:**
- `sms_blacklist` — Number in `phone.blacklist`
- `sms_duplicate` — Same sanitized number already processed in this batch
- `sms_optout` — Recipient opted out (extensible via `_get_optout_record_ids` override)

**Delivery report codes (via webhook):**
- `sms_expired` — TTL exceeded without delivery confirmation
- `sms_not_delivered` — Carrier confirmed undelivered
- `sms_invalid_destination` — Carrier rejected the destination number
- `sms_not_allowed` — Sender blocked by carrier policy
- `sms_rejected` — Content or sender rejected by carrier

#### Class-Level Constants

```python
IAP_TO_SMS_STATE_SUCCESS = {
    'processing': 'process',
    'success': 'pending',
    'sent': 'pending',         # webhook: carrier confirms sent
    'delivered': 'sent',       # webhook: confirmed delivered
}

BOUNCE_DELIVERY_ERRORS = {'sms_invalid_destination', 'sms_not_allowed', 'sms_rejected'}
DELIVERY_ERRORS = {'sms_expired', 'sms_not_delivered', *BOUNCE_DELIVERY_ERRORS}
```

The `BOUNCE_DELIVERY_ERRORS` set drives the bounce detection in `_action_update_from_provider_error`, which sets `notification_status = 'bounce'` (not `'exception'`) for hard bounces, allowing marketing modules to suppress retries.

#### Key Methods

**`create(vals_list)`**
Triggers the SMS queue scheduler cron on every SMS creation via `_trigger()`. This ensures the CRON fires even if no cron worker is actively running — the scheduler will pick it up at its next interval. The cron is identified by external ID `sms.ir_cron_sms_scheduler_action`.

**`send(unlink_failed=False, unlink_sent=True, raise_exception=False)`**
Main public API. Uses `try_lock_for_update()` (SELECT FOR UPDATE NOWAIT) to lock records and prevent double-send in concurrent environments. Splits by API class (override point for multi-company/multi-gateway), then into batch-size chunks (default 500, configurable via `sms.session.batch.size`). Calls `_send()` with the resolved `sms_api` in context.

- `unlink_failed=True`: permanently deletes SMS records that failed (not just marks them)
- `unlink_sent=True`: permanently deletes SMS records after confirmed delivery (default)
- `raise_exception=False`: network failures are swallowed and converted to `server_error` state

**`_split_by_api()`**
Generator yielding `(sms_api, recordset)` tuples. Default implementation yields a single `(SmsApi(self.env), self)`. Override in EE modules (e.g., `sms_twilio`, `sms_ovh`) to route different companies' SMS through different providers.

**`_send()`**
Resolves `sms_api` from context or from the company via `_get_sms_company()` and `company._get_sms_api_class()`. Delegates to `_send_with_api()`.

**`_get_sms_company()`**
Returns `mail_message_id.record_company_id` if available (set by mixins on company-dependent models), else `self.env.company`. Ensures correct IAP account is charged in multi-company setups.

**`_send_with_api(sms_api, ...)`**
1. Groups SMS records by `body` (all recipients with the same message text are batched into one IAP request)
2. Calls `sms_api._send_sms_batch(messages, delivery_reports_url)` where each message is `{content, numbers: [{uuid, number}]}`
3. On IAP exception: logs, optionally raises, falls back to `server_error` for all SMS
4. Iterates results grouped by `(iap_state, failure_reason)` for efficient batch writes
5. For success states: transitions SMS + calls `sms_tracker_id._action_update_from_sms_state()`
6. For failure states: maps via `PROVIDER_TO_SMS_FAILURE_TYPE`, falls back to `_action_update_from_provider_error()` for unknown codes
7. Calls `_handle_call_result_hook()` (empty pass; designed for `sms_marketing` to update mailing traces)
8. Calls `mail_message_id._notify_message_notification_update()` to push real-time UI updates to Odoo chatter

**`_split_batch()`**
Yields ID chunks of `_get_send_batch_size()` using `odoo.tools.split_every()`. Default batch size is 500, configured via `ir.config_parameter` `sms.session.batch.size`.

**`_process_queue()`**
CRON entry point. Searches `outgoing` SMS in batches of 500, locks with `try_lock_for_update()`, sends, then calls `ir_cron._commit_progress()` to commit the transaction and record remaining count. The per-batch commit strategy allows partial progress even if a later batch fails. Uses `@api.autovacuum` is NOT used here — this is a regular scheduled action.

**`_gc_device()`**
`@api.autovacuum` method. Deletes all `sms.sms` records where `to_delete = True` via raw SQL. Runs during Odoo's vacuum cycle. The `autovacuum` runs as the database superuser, bypassing row-level security.

**`resend_failed()`**
Filters to `error` state and `not to_delete`, resets to `outgoing`, calls `send()`, returns a `display_notification` action. Note: `exists()` after `send()` gives the count of SMS that were successfully re-queued (not the count sent).

---

### `sms.template` — SMS Template

**File:** `~/odoo/odoo19/odoo/addons/sms/models/sms_template.py`
**Inherits:** `mail.render.mixin`, `template.reset.mixin`
**Unrestricted rendering:** `_unrestricted_rendering = True`

#### Fields

| Field | Type | Description |
|---|---|---|
| `name` | `Char` (translate) | Template display name |
| `model_id` | `Many2one(ir.model)` | Target model. Domain: `is_mail_thread_sms=True`, non-transient. `ondelete='cascade'`. Required. |
| `model` | `Char` (related, stored, indexed) | The `ir.model.model` string (e.g. `res.partner`). Stored for fast filtering and rendering. |
| `body` | `Char` (translate, required) | SMS body text. Supports `{{record.field}}` inline template syntax via `mail.render.mixin`. Required. |
| `sidebar_action_id` | `Many2one(ir.actions.act_window)` | Sidebar action to make this template available on records of the related document model. Created via `action_create_sidebar_action()`. |
| `template_fs` | `Char` | Inherited from `template.reset.mixin`. Stores the source XML module path for reset functionality. |

#### Inherited Behavior

**`<mail.render.mixin>`** provides:
- `_render_field()` — renders a field with translation and language support
- `_render_template()` — QWeb-style template rendering with `{{object}}` / `{{record}}` / `{{ctx}}` / `${...}` syntax
- `render_model` compute (overridden by `_compute_render_model`)
- `_unrestricted_rendering = True` bypasses ACL checks during field access in templates, allowing any field to be referenced regardless of the user's read access

**`<template.reset.mixin>`** provides:
- `template_fs` — populated automatically at creation from `install_filename` context
- `reset_template()` — re-parses the original XML record and restores fields, including translation terms from `.po` files
- `_load_records_write()` override — during reset, blank fields not in XML are emptied (with default value preservation)

#### Methods

**`_compute_render_model()`**
Sets `render_model = model` (the `ir.model.model` string). Required because `mail.render.mixin` is shared with email templates and needs to know which model to browse for field evaluation.

**`action_create_sidebar_action()`**
Creates an `ir.actions.act_window` bound to `sms.composer` with context:
```python
{
    'default_template_id': template.id,
    'sms_composition_mode': 'guess',     # auto-detect mass vs. comment
    'default_res_ids': active_ids,
    'default_res_id': active_id,
}
```
The `'guess'` mode checks record count: if >1 → `mass`, if =1 → `comment`. The action is created with `binding_model_id` set to the template's model, so it appears in the sidebar Actions menu on those forms.

**`unlink()`**
Calls `sudo()` on the template recordset before deleting the sidebar action, then calls `super().unlink()`. This bypasses record-level ir.rule restrictions — only system users can delete templates anyway.

---

### `sms.tracker` — SMS-to-Notification Link

**File:** `~/odoo/odoo19/odoo/addons/sms/models/sms_tracker.py`
**Inherits:** `base`

#### Purpose

`sms.sms` records are marked `to_delete=True` after sending and purged by autovacuum. They cannot serve as reliable foreign keys for delivery report processing. `sms.tracker` provides a stable, permanent link between a sent SMS's UUID and its `mail.notification` record, enabling delivery report webhooks to update notification status indefinitely.

#### Fields

| Field | Type | Description |
|---|---|---|
| `sms_uuid` | `Char` (required) | UUID of the `sms.sms` record. `unique(sms_uuid)` DB constraint. |
| `mail_notification_id` | `Many2one(mail.notification)` | Linked notification. `ondelete='cascade'`. `index='btree_not_null'` — partial index (only indexes non-null values). |

#### `SMS_STATE_TO_NOTIFICATION_STATUS` Mapping

```python
'canceled'  → 'canceled'
'process'   → 'process'
'error'     → 'exception'
'outgoing'  → 'ready'
'sent'      → 'sent'
'pending'   → 'pending'
```

#### Key Methods

**`_action_update_from_sms_state(sms_state, failure_type=False, failure_reason=False)`**
Looks up notification status via `SMS_STATE_TO_NOTIFICATION_STATUS`, then calls `_update_sms_notifications()`.

**`_action_update_from_provider_error(provider_error)`**
Handles unknown/unmapped IAP error codes:
1. Reads `sms_known_failure_reason` from context (TODO: should become a parameter in future — RIGR in master per code comment)
2. Classifies `failure_type = f'sms_{provider_error}'`
3. Falls back to `'unknown'` if not in `DELIVERY_ERRORS`
4. If `failure_type in BOUNCE_DELIVERY_ERRORS`: sets `error_status = 'bounce'`
5. Calls `_update_sms_notifications(error_status or 'exception', ...)`

**`_update_sms_notifications(notification_status, failure_type, failure_reason)`**
Implements an idempotent state machine. For each incoming `notification_status`, it computes which existing notification statuses should be skipped (not overwritten):

| New status | Ignores (skips updates to) |
|---|---|
| `canceled` | canceled, process, pending, sent |
| `ready` | ready, process, pending, sent |
| `process` | process, pending, sent |
| `pending` | pending, sent |
| `bounce` | bounce, sent |
| `sent` | sent |
| `exception` | exception |

This prevents, for example, a late `delivered` webhook from overwriting an already-processed `bounce`, or a retry from downgrading `sent` to `pending`. If `sms_skip_msg_notification` is not in context, it also calls `mail_message_id._notify_message_notification_update()` for real-time chatter updates.

---

### `sms.composer` — SMS Composition Wizard

**File:** `~/odoo/odoo19/odoo/addons/sms/wizard/sms_composer.py`
**Inherits:** `base`
**Type:** `TransientModel`

Primary UI for sending SMS. Operates in three composition modes.

#### `composition_mode` Values

| Value | Description | Pipeline |
|---|---|---|
| `numbers` | Send to manually entered phone numbers (comma-separated) | Direct `sms.sms.create()` → `.send()` |
| `comment` | Post SMS notification on a document record | `record._message_sms()` → `mail.thread` → `mail.message` + `mail.notification` |
| `mass` | Batch send to many records, filtering blacklists | Direct `sms.sms.create()` → optional `.send()` |

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `composition_mode` | `Selection` | auto-guessed | `store=True`. Guessed from context `'sms_composition_mode'` or from `res_ids_count > 1`. |
| `res_model` | `Char` | context | Target model for comment and mass modes. |
| `res_id` | `Integer` | context | Single record ID. |
| `res_ids` | `Char` | context | Multiple record IDs stored as `repr([id1, id2, ...])`. Avoids Odoo's domain length limits for large sets. |
| `res_ids_count` | `Integer` (computed) | — | Number of records in `res_ids`. Drives composition mode auto-detection. |
| `comment_single_recipient` | `Boolean` (computed) | — | True when in `comment` mode with exactly one `res_id`. Enables single-recipient UI with editable phone number. |
| `template_id` | `Many2one(sms.template)` | context | Optional. Sets body and constrains valid recipients. |
| `body` | `Text` (computed, stored) | — | In `comment`+template+single-record: renders template via `_render_field` with `compute_lang=True`. In other modes: uses template raw body. |
| `recipient_valid_count` / `recipient_invalid_count` | `Integer` (computed) | — | Based on `_sms_get_recipients_info()`. Validates before send. |
| `recipient_single_number_itf` | `Char` | — | Editable phone number shown in single-recipient popup. If changed by user, written back to the record's `number_field_name` field. |
| `recipient_single_valid` | `Boolean` (computed) | — | Whether `recipient_single_number_itf` passes `_phone_format` validation for the target country. |
| `number_field_name` | `Char` | — | Which phone field to use (e.g. `mobile`, `phone`). Set from `_sms_get_recipients_info`'s `field_store`. |
| `numbers` | `Char` | — | Comma-separated raw numbers for `numbers` mode. |
| `sanitized_numbers` | `Char` (computed) | — | E.164-formatted numbers. Validated in `_compute_sanitized_numbers`. Raises `UserError` if any number fails format check. |
| `mass_keep_log` | `Boolean` | `True` | If True, creates `mail.message` log entries on each record in mass mode. |
| `mass_force_send` | `Boolean` | `False` | If True, sends immediately bypassing the queue. Default False (CRON processes queue). |
| `use_exclusion_list` | `Boolean` | `True` | If True, checks `phone.blacklist` before sending in mass mode. |

#### Mass Mode Filtering — `_prepare_mass_sms_values()`

Each record is classified before SMS creation:

```
blacklisted number  → state='canceled',  failure_type='sms_blacklist'
opted out           → state='canceled',  failure_type='sms_optout'
duplicate number    → state='canceled',  failure_type='sms_duplicate'
invalid number      → state='canceled',  failure_type='sms_number_format' or 'sms_number_missing'
valid               → state='outgoing',  failure_type=''
```

`_filter_out_and_handle_revoked_sms_values()` (empty pass; overridden by `sms_marketing` for consent revocation handling).

#### Action Methods

| Method | Behavior |
|---|---|
| `action_send_sms()` | Validates recipient counts; dispatches to `_action_send_sms_numbers/comment_single/comment/mass` |
| `action_send_sms_mass_now()` | Sets `mass_force_send=True` then calls `action_send_sms()` |
| `_action_send_sms_numbers()` | Creates `sms.sms` directly from `sanitized_numbers`, then `.send()` |
| `_action_send_sms_comment()` | Calls `record._message_sms()` for each record, going through `mail.thread` pipeline |
| `_action_send_sms_mass()` | Creates SMS directly (no `mail.message`), optionally logs via `_message_log_batch()`, optionally sends immediately |

---

## `mail.thread` Integration

### `_sms_get_recipients_info(force_field=False, partner_fallback=True)`

Defined in `models/sms_sms.py` as a mixin on `base` — available on every model. Returns a `dict` keyed by record ID:

```python
{
    record_id: {
        'partner': res.partner recordset,   # or empty recordset
        'sanitized': '+1234567890',         # E.164 formatted number or False
        'number': '01234567890',            # original raw number
        'partner_store': True/False,         # did number come from partner, not record
        'field_store': 'mobile',             # which field held the number
    }
}
```

**Resolution priority:**
1. `force_field` specified → use that field on the record directly
2. Iterate `_phone_get_number_fields()` on the record (typically `mobile`, then `phone`)
3. If no valid number on record → fall back to partners from `_mail_get_partners()`, iterate their phone fields
4. If still no valid number → return raw values with `sanitized=False` and `partner_store=False`

### Full Send Flow: `_message_sms` to `_notify_thread_by_sms`

```
External caller
        │
        ▼
MailThread._message_sms(body, number_field=..., partner_ids=..., sms_numbers=...)
        │
        ├── _sms_get_recipients_info(force_field=number_field)
        │
        ├── partner + sanitized number  → sms_pid_to_number[partner_id] = sanitized
        ├── partner, no sanitized       → just add to partner_ids (uses partner's stored number)
        └── no partner, no sanitized     → sms_numbers = [False]  (creates error notification)
        │
        ▼
message_post(message_type='sms', sms_content=body, sms_pid_to_number=..., sms_numbers=...)
        │
        ▼
MailThread._notify_thread()  [override]
        │
        ├── super()._notify_thread()  → builds recipients_data (notif channel per partner)
        │
        └── _notify_thread_by_sms()  [own implementation]
                │
                ├── Filter recipients_data where notif='sms'
                ├── For each SMS: create sms.sms (sudo) + mail.notification (sudo)
                │       └── If outgoing: also create sms.tracker via Command.create()
                └── If not put_in_queue: immediately sms_all.send()
```

### `_notify_thread_by_sms(message, recipients_data, ...)`

Receives `recipients_data` from `_notify_thread` (which already set `notif='sms'` for partners whose preferred channel is SMS). Creates:
1. `sms.sms` via `sudo()` with `state='outgoing'` (or `'error'`/`'sms_number_missing'` for empty numbers)
2. `mail.notification` via `sudo()` with `notification_type='sms'`, `sms_id_int=sms.id`, and conditionally a `sms.tracker` entry (`Command.create(...)` only if `sms.state == 'outgoing'`)
3. If `put_in_queue=False`: immediately calls `.send()` on outgoing SMS

The `sudo()` call is necessary because notification dispatch happens in the context of the message author, who may not have write access to `sms.sms` or `mail.notification` tables.

---

## IAP Integration

### `SmsApi` — IAP Communication Layer

**File:** `~/odoo/odoo19/odoo/addons/sms/tools/sms_api.py`

```
SmsApiBase (abstract, extensible for EE providers)
    └── SmsApi (concrete, Odoo IAP implementation)
```

#### Class Hierarchy

```python
class SmsApiBase:
    PROVIDER_TO_SMS_FAILURE_TYPE = {
        'server_error': 'sms_server',
        'sms_number_missing': 'sms_number_missing',
        'wrong_number_format': 'sms_number_format',
    }
    # Subclasses must implement _send_sms_batch()

class SmsApi(SmsApiBase):
    DEFAULT_ENDPOINT = 'https://sms.api.odoo.com'
    PROVIDER_TO_SMS_FAILURE_TYPE = SmsApiBase.PROVIDER_TO_SMS_FAILURE_TYPE | {
        'country_not_supported': 'sms_country_not_supported',
        'insufficient_credit': 'sms_credit',
        'unregistered': 'sms_acc',
    }
```

#### Key Methods

**`_contact_iap(local_endpoint, params, timeout=15)`**
Wraps `iap_jsonrpc()` with:
- `account_token`: from `iap.account.sudo().account_token`
- `dbuuid`: from `ir.config_parameter` `database.uuid`
- `endpoint`: from `sms.endpoint` config param or default `https://sms.api.odoo.com`

**Critical**: Blocks IAP calls during module installation via `if not self.env.registry.ready`. This prevents IAP calls before the database registry is fully loaded, which would fail in fresh-install scenarios.

**`_send_sms_batch(messages, delivery_reports_url)`**
Sends to `/api/sms/3/send`. Messages are grouped by body content:
```python
[
    {
        'content': 'Hello {{object.partner_id.name}}',
        'numbers': [
            {'uuid': 'abc123...', 'number': '+1234567890'},
            {'uuid': 'def456...', 'number': '+0987654321'},
        ]
    },
    ...
]
```
Returns a list of `{uuid, state, failure_reason?}` responses.

**`_send_verification_sms(phone_number)`** — Sends verification code via `/api/sms/1/account/create`

**`_verify_account(verification_code)`** — Confirms code via `/api/sms/2/account/verify`

**`_set_sender_name(sender_name)`** — Sets alphanumeric sender via `/api/sms/1/account/update_sender`

---

## Webhook: Delivery Reports

### `SmsController.update_sms_status`

**Route:** `/sms/status`
**Auth:** `auth='public'` (IAP servers call without Odoo session cookies)
**Type:** JSON-RPC

IAP POSTs batches of `{sms_status, uuids[]}` objects. The controller:
1. Validates UUID format (`^[0-9a-f]{32}$`) and status format (`^\w+$`) using regex — rejects ill-formed requests with HTTP 400
2. Searches `sms.tracker` via `sudo()` for each UUID group
3. Calls `_action_update_from_sms_state()` for known states, `_action_update_from_provider_error()` for unknown codes
4. Marks corresponding `sms.sms` rows as `to_delete=True` (marks for GC, does not delete synchronously)
5. Returns `'OK'`

UUID validation is the sole authentication mechanism since `auth='public'`. The IAP endpoint knows the correct UUIDs (assigned at SMS creation), making this accept-only.

---

## CRON Jobs

| Cron | Model | Interval | Purpose |
|---|---|---|---|
| `SMS: SMS Queue Manager` | `sms.sms` | Every 24 hours | Calls `_process_queue()` — picks up to `sms.session.batch.size` (default 500) `outgoing` SMS, locks, sends, commits progress |

The cron is also triggered directly from `sms.sms.create()` to ensure immediate sending when SMS records are created programmatically.

---

## Security

### Access Control (`ir.model.access.csv`)

| Record | Group | R | W | C | D |
|---|---|---|---|---|---|
| `sms.sms` | `base.group_system` | Yes | Yes | Yes | Yes |
| `sms.sms` | *(no public)* | No | No | No | No |
| `sms.template` | `base.group_system` | Full | Full | Full | Full |
| `sms.template` | `base.group_user` | Read-only | No | No | No |
| `sms.template` | *(no public)* | No | No | No | No |
| `sms.tracker` | `base.group_system` | Yes | Yes | Yes | Yes |
| `sms.tracker` | *(no public)* | No | No | No | No |
| `sms.composer` | `base.group_user` | Yes | Yes | Yes | No |
| `sms.template.preview` | `base.group_user` | Yes | Yes | Yes | No |
| `sms.template.reset` | `mail.group_mail_template_editor` | Yes | Yes | Yes | Yes |
| `sms.account.*` wizards | `base.group_system` | Full | Full | Full | Full |

### Record Rules

- `ir_rule_sms_template_system`: System group (`base.group_system`) gets unrestricted domain access to all `sms.template` records.
- All other SMS models rely purely on ir.model.access CSV entries — no record-level rules.

### Security Design Notes

- `sms.sms` and `sms.tracker` are not readable by regular users — only the technical/system user manages SMS sending.
- `mail.notification.sms_number` is restricted to `base.group_user` to prevent phone number enumeration by low-privilege users.
- `sms.account.*` wizards require `base.group_system` write access — only administrators can manage IAP accounts and sender names.
- The `/sms/status` webhook uses `auth='public'` because IAP calls it without Odoo session cookies. UUID validation is the sole authentication mechanism.

---

## Performance Considerations

1. **Batch splitting**: `_split_batch()` caps each IAP request at 500 SMS (configurable). Prevents timeout on large mass sends and respects IAP rate limits.

2. **`_notify_thread_by_sms` uses `sudo()`**: `sms.sms` and `mail.notification` are created with `sudo()` because notification dispatch runs as the message author (not necessarily the SMS manager). This avoids ACL permission errors during automated sending.

3. **`_compute_message_has_sms_error` uses raw SQL**: The computed field on `mail.thread` uses a direct SQL query joining `mail_message` and `mail_notification` rather than ORM `search()` — avoids N+1 queries when checking SMS errors on large record sets with many messages.

4. **SMS record GC**: After successful delivery, `sms.sms` records are marked `to_delete=True` and purged by `autovacuum`. This keeps the `sms.sms` table lean. Delivery reports can still update `mail.notification` via `sms.tracker` even after the SMS row is purged.

5. **UUID-based tracker lookups**: `sms.tracker` lookups use UUID (not SMS ID) because SMS records can be deleted before delivery reports arrive. UUIDs are stable indefinitely.

6. **`res_ids` stored as `repr(list)`**: The composer stores multiple record IDs as a `repr()`-encoded string rather than a Many2many, avoiding the Odoo domain length limit for mass sends on large record sets.

7. **Per-batch CRON commits**: `_process_queue()` commits after each batch of 500, enabling partial progress on large queues without holding a long transaction.

---

## Odoo 18 → 19 Changes

- **`sms.tracker` introduced**: Odoo 18 stored delivery tracking directly on `mail.notification` or relied on `sms.sms` records. Odoo 19 introduces `sms.tracker` as an explicit join table, allowing `mail.notification` updates long after `sms.sms` rows are garbage-collected.

- **IAP API version 3**: The send endpoint moved from `/api/sms/2/send` to `/api/sms/3/send`. The batch structure changed to group by body content (one entry per unique message body with multiple recipients).

- **`to_delete` flag**: Records are no longer immediately unlinked after sending. Instead, `to_delete=True` is set and records are purged by autovacuum. This allows debugging and webhook consistency.

- **`sms.session.batch.size` config**: Batch size for IAP requests is now configurable via `ir.config_parameter` (default 500), previously hardcoded.

- **`BOUNCE_DELIVERY_ERRORS` / `DELIVERY_ERRORS` constants**: Added in Odoo 19 to cleanly separate bounce-type errors (which set `notification_status='bounce'`) from regular delivery failures (`notification_status='exception'`).

- **`_handle_call_result_hook`**: Added as an empty pass method to allow `sms_marketing` and other extensions to process IAP responses without overriding `_send_with_api`.

- **`_gc_device` autovacuum**: Replaces manual cleanup. Uses `@api.autovacuum` decorator for automatic cleanup during Odoo's vacuum cycle, rather than a scheduled action.

- **`IAP_TO_SMS_FAILURE_TYPE` deprecation**: The `IAP_TO_SMS_FAILURE_TYPE` class variable (which mapped legacy IAP error codes to current `failure_type` values) is marked `TODO RIGR remove me in master` — it is no longer actively used in the current send flow.

---

## Edge Cases and Failure Modes

| Scenario | Behavior |
|---|---|
| SMS created, CRON never runs | `create()` triggers the cron immediately via `_trigger()`. `send()` can be called manually anytime. |
| IAP endpoint unreachable | `_send_with_api` catches exception, marks all SMS as `'error'`/`'sms_server'`, returns without raising (unless `raise_exception=True`). |
| Delivery report arrives for deleted SMS | Controller looks up `sms.tracker` (still exists), updates `mail.notification`. `sms.sms` row is already `to_delete=True` and will be purged by autovacuum. |
| Number in `phone.blacklist` in mass mode | SMS created with `state='canceled'`, `failure_type='sms_blacklist'`. Notification created with `notification_status='canceled'`. No IAP request made. |
| Same number appears twice in mass send | Second occurrence created as `state='canceled'`, `failure_type='sms_duplicate'`. |
| `sms_marketing` consent revoked mid-batch | Overrides `_filter_out_and_handle_revoked_sms_values()` to cancel revoked recipients before SMS creation. |
| Multi-company: SMS from shared model | `_get_sms_company()` uses `mail_message_id.record_company_id` if present, else falls back to `env.company`. Ensures correct IAP account is charged. |
| Template renders to empty body | IAP accepts the SMS (empty body is technically valid per protocol). No validation at ORM level. |
| Template body contains sensitive fields | `_unrestricted_rendering = True` allows access to all fields. ACLs on `sms.template` (read-only for regular users) prevent unauthorized template editing. |
| Concurrent `send()` on same SMS | `try_lock_for_update()` ensures only one process handles a given SMS. Second process gets a lock error and skips. |
| IAP returns unknown status code | `_action_update_from_provider_error()` falls back to `failure_type='unknown'`, `notification_status='exception'`. |
| Multiple IAP error types in one batch | `tools.groupby()` groups results by `(iap_state, failure_reason)`, minimizing the number of `write()` calls. |
| Module upgrade during active queue | `create()` blocks IAP calls during upgrade via `registry.ready` check. Queued SMS will be processed after upgrade completes. |

---

## See Also

- [Modules/phone_validation](Modules/phone_validation.md) — Phone number formatting, E.164 normalization, `_phone_get_number_fields`, `_phone_format`
- [Modules/mail](Modules/mail.md) — `mail.thread`, `mail.message`, `mail.notification`, `mail.render.mixin`, `template.reset.mixin`
- [Modules/iap_mail](Modules/iap_mail.md) — IAP account infrastructure, credits management
- [Core/API](Core/API.md) — `@api.model`, `@api.depends`, `@api.depends_context`, `@api.autovacuum`
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — State machine design (used by `sms.sms` state field)
- [Core/BaseModel](Core/BaseModel.md) — `try_lock_for_update()`, `sudo()`, recordset operations
