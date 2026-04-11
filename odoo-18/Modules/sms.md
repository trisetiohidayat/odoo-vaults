# SMS Module (Odoo 18)

## Overview

The SMS module provides a unified framework for sending SMS messages via SMS aggregators (IAP - In-App Purchase) and routing delivery reports back to Odoo.

**Module Path:** `sms/`
**Key Models:** `sms.sms`, `sms.tracker`, `sms.template`
**Dependencies:** `mail`, `phone_validation`
**IAP Required:** Yes (SMS sending uses Odoo IAP credits)

---

## Architecture

```
sms.sms (outgoing messages)
    ├── mail.message (optional link)
    ├── res.partner (optional recipient partner)
    └── sms.tracker (links to mail.notification / mailing.trace)

mail.notification (extended)
    ├── sms.tracker (one2many)
    └── sms.sms (via sms_id_int)

mail.mailing.trace (extended)
    └── sms.tracker (via sms_uuid)

sms.template
    └── ir.model (applies to model)
```

---

## sms.sms

The core SMS sending model. Records every outgoing SMS with its delivery state.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | Char | Unique identifier for delivery reports (alternate key) |
| `number` | Char | Recipient phone number |
| `body` | Text | SMS message content |
| `partner_id` | Many2one | Recipient partner (optional) |
| `mail_message_id` | Many2one | Related mail.message (for tracking) |
| `state` | Selection | `outgoing`, `process`, `pending`, `sent`, `error`, `canceled` |
| `failure_type` | Selection | Error reason if `state=error` |
| `sms_tracker_id` | Many2one | Computed link to sms.tracker |
| `to_delete` | Boolean | Marked for garbage collection |

### State Machine

```
outgoing ──> process ──> pending ──> sent (delivered)
                │
                └──> error (failed)

Any state except sent ──> canceled
```

### State Definitions

| State | Meaning | Description |
|-------|---------|-------------|
| `outgoing` | In Queue | Created, waiting to be sent |
| `process` | Processing | Sent to IAP, awaiting delivery report |
| `pending` | Sent | Delivered to carrier |
| `sent` | Delivered | Confirmed delivered to recipient |
| `error` | Error | Failed (check failure_type) |
| `canceled` | Cancelled | Cancelled before sending |

### Failure Types

| Code | Meaning |
|------|---------|
| `unknown` | Unknown error |
| `sms_number_missing` | No phone number provided |
| `sms_number_format` | Invalid number format |
| `sms_country_not_supported` | Country not supported |
| `sms_registration_needed` | Country-specific registration required |
| `sms_credit` | Insufficient IAP credits |
| `sms_server` | Server error from IAP |
| `sms_acc` | Unregistered IAP account |
| `sms_blacklist` | Number is blacklisted |
| `sms_duplicate` | Duplicate message |
| `sms_optout` | Recipient opted out |

### Key Methods

#### `send()`
Main API for batch sending. Processes SMS in batches using IAP.

```python
def send(self, unlink_failed=False, unlink_sent=True, auto_commit=False, raise_exception=False):
    # Filters: only state='outgoing' and not to_delete
    # Splits into batches (default 500 per batch)
    # Calls _send() per batch
    # Auto-commits per batch if auto_commit=True
```

#### `_send()`
Entry point for sending. Gets the SmsApi class and delegates.

```python
def _send(self, unlink_failed=False, unlink_sent=True, raise_exception=False):
    # Gets sms_api from context or creates via _get_sms_company()
    # Calls _send_with_api()
```

#### `_send_with_api()`
Actually sends via the IAP gateway.

```python
def _send_with_api(self, sms_api, unlink_failed=False, unlink_sent=True, raise_exception=False):
    # Groups SMS by body
    # Sends batch to IAP endpoint
    # Handles responses: success -> state=pending
    #                     failure -> state=error with failure_type
    # Updates trackers and notifications
```

#### `_split_batch()`
Splits SMS records into batches of configurable size (default 500).

```python
def _split_batch(self):
    batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
        'sms.session.batch.size', 500))
```

#### `resend_failed()`
Resets failed SMS back to `outgoing` state and resends them.

```python
def resend_failed(self):
    # Filters: state='error' and not to_delete
    # Sets state to 'outgoing'
    # Calls send()
    # Returns display_notification result
```

#### `_process_queue()`
Cron entry point for processing queued outgoing SMS.

```python
@api.model
def _process_queue(self, ids=None):
    # Searches: state='outgoing' and not to_delete
    # Limits to 10000 messages
    # Calls send(auto_commit=True)
```

#### `_update_sms_state_and_trackers()`
Updates both SMS state and related tracker records atomically.

```python
def _update_sms_state_and_trackers(self, new_state, failure_type=None):
    # Writes state and failure_type on sms.sms
    # Calls tracker._action_update_from_sms_state()
```

#### `_gc_device()`
Autovacuum method that deletes SMS records marked `to_delete=True`.

```python
@api.autovacuum
def _gc_device(self):
    self._cr.execute("DELETE FROM sms_sms WHERE to_delete = TRUE")
```

---

## sms.tracker

Links SMS UUIDs to notification/trace records. Enables delivery report routing.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `sms_uuid` | Char | UUID of the related sms.sms (unique) |
| `mail_notification_id` | Many2one | Related mail.notification |

### Key Methods

#### `_action_update_from_sms_state()`
Routes SMS state changes to mail notifications.

```python
def _action_update_from_sms_state(self, sms_state, failure_type=False, failure_reason=False):
    notification_status = self.SMS_STATE_TO_NOTIFICATION_STATUS[sms_state]
    self._update_sms_notifications(notification_status, ...)
```

#### `_action_update_from_provider_error()`
Handles provider-specific error codes.

```python
def _action_update_from_provider_error(self, provider_error):
    # Maps provider error to failure_type
    # Bounce errors (invalid_destination, not_allowed, rejected)
    #   get error_status='bounce'
    # Updates notifications accordingly
```

#### `_update_sms_notifications()`
Writes notification status, respecting status transition rules.

```python
def _update_sms_notifications(self, notification_status, failure_type=False, failure_reason=False):
    # Status transition matrix prevents invalid transitions
    # e.g., cannot go from 'sent' back to 'pending'
    # Writes notification_status, failure_type, failure_reason
    # Triggers mail.message notification update
```

### Status Transition Matrix

| Target Status | Allowed From (all others ignored) |
|---------------|----------------------------------|
| `canceled` | `canceled` |
| `ready` | `ready`, `process`, `pending`, `sent` |
| `process` | `process`, `pending`, `sent` |
| `pending` | `pending`, `sent` |
| `bounce` | `bounce`, `sent` |
| `sent` | `sent` |
| `exception` | (any) |

---

## sms.template

SMS templates with Jinja2 rendering support. Similar to email templates.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Template name |
| `model_id` | Many2one | Target model (must support SMS) |
| `model` | Char | Related model technical name |
| `body` | Char | Template body with Jinja2 placeholders |
| `sidebar_action_id` | Many2one | Sidebar action for quick send |

### Key Methods

#### `_compute_render_model()`
Inherited from `mail.render.mixin`. Returns the model this template renders for.

---

## mail.notification Extension

The `sms` module extends `mail.notification` with SMS support:

### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `notification_type` | Selection | Adds `sms` option |
| `sms_id_int` | Integer | SMS record ID (no FK) |
| `sms_id` | Many2one | Computed link to sms.sms |
| `sms_tracker_ids` | One2many | SMS trackers linked to this notification |
| `sms_number` | Char | SMS recipient number |
| `failure_type` | Selection | Adds SMS-specific failure types |

### Failure Types Added

- `sms_expired` - SMS expired before delivery
- `sms_invalid_destination` - Number invalid
- `sms_not_allowed` - Carrier blocked
- `sms_not_delivered` - Not delivered
- `sms_rejected` - Rejected by carrier

---

## Sending Flow

```
1. Create sms.sms records (state=outgoing)
   --> set body, number, partner_id, mail_message_id

2. Call send()
   --> _split_by_api() yields SmsApi per gateway
   --> Per batch, _send() is called

3. _send_with_api()
   --> Groups SMS by body (for batch efficiency)
   --> Calls IAP /sms/sms/send_batch API
   --> Passes delivery_reports_url = /sms/status

4. IAP processes and sends SMS to carriers

5. Delivery reports arrive at /sms/status webhook
   --> Routes to sms.sms via UUID
   --> Updates state: pending (sent) or error
   --> Updates sms.tracker -> mail.notification

6. Notification updates trigger mail.message updates
```

---

## IAP Integration

### Required IAP Account

SMS sending requires an Odoo IAP account with SMS credits:
- Credits are consumed per SMS segment (160 chars)
- Different pricing per country/carrier
- Balance checked before sending

### Configuration

```
sms.session.batch.size = 500    # SMS per batch
sms.sms.use_proxy = False       # Use IAP proxy
```

### Gateway Dispatch

The `SmsApi` class handles IAP communication:
- `_send_sms_batch()` - Send batch of SMS
- Handles network errors gracefully
- Returns per-message status results

---

## Composer (sms.composer)

A transient wizard for composing and sending SMS from within Odoo.

Used by:
- SMS action from any `mail.thread` model
- SMS template "Send SMS" button
- Mailing SMS campaigns

### Key Methods

#### `_action_send()`
Processes the composer, creates `sms.sms` records, and triggers sending.

---

## Blacklist Handling

Numbers on the `phone.blacklist` automatically fail with `sms_blacklist` failure type before sending.

---

## Delivery Reports

When IAP delivers delivery confirmations via `/sms/status` webhook:

1. UUID is extracted from the notification
2. `sms.tracker` is found via `sms_uuid`
3. State is updated: `process` -> `pending` (sent) or `error`
4. `mail.notification` status is updated
5. `mail.message` is notified of the update
