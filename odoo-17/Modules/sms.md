---
tags: [odoo, odoo17, module, sms]
---

# SMS Module

**Source:** `addons/sms/models/`

Sends and tracks SMS messages via external providers (IAP — In-App Purchase — SMS service or custom gateways).

## Key Models

| Model | File | Description |
|-------|------|-------------|
| `sms.sms` | `sms_sms.py` | Individual SMS records with state tracking |
| `sms.template` | `sms_template.py` | Reusable SMS templates |
| `sms.tracker` | `sms_tracker.py` | Tracks SMS delivery via provider webhooks |
| `mail.thread` | Mixin in various files | Extends records with SMS capability |

## sms.sms

The core SMS record. Each record represents one outbound SMS.

### Fields
- `uuid` — Unique identifier for webhook delivery reports (alternate lookup key)
- `number` — Recipient phone number (E.164 format recommended)
- `body` — SMS text content
- `partner_id` — Optional `res.partner` link
- `mail_message_id` — Link to `mail.message` if sent as part of a notification
- `state` — Current SMS state
- `failure_type` — Error code if in `error` state
- `sms_tracker_id` — Link to `sms.tracker` for delivery tracking
- `to_delete` — Marked for garbage collection

### SMS States
```
outgoing → process → pending → sent
                       ↘ error → (canceled)
```

| State | Description |
|-------|-------------|
| `outgoing` | In queue, not yet sent to provider |
| `process` | Being processed by the provider |
| `pending` | Sent to provider, awaiting delivery confirmation |
| `sent` | Confirmed delivered (via webhook) |
| `error` | Failed (invalid number, no credit, etc.) |
| `canceled` | Manually canceled |

### State Mapping (IAP to Odoo)
The provider (IAP) uses different state names internally:

| IAP State | Odoo State |
|-----------|------------|
| `processing` | `process` |
| `success` | `pending` |
| `sent` | `pending` |
| `delivered` | `sent` |

### Failure Types
| Code | Meaning |
|------|---------|
| `sms_number_missing` | No phone number provided |
| `sms_number_format` | Invalid number format |
| `sms_country_not_supported` | Country not supported by provider |
| `sms_registration_needed` | Country-specific registration required |
| `sms_credit` | Insufficient IAP credit |
| `sms_server` | Provider server error |
| `sms_acc` | Unregistered account |
| `sms_blacklist` | Number is blacklisted |
| `sms_duplicate` | Duplicate detection |
| `sms_optout` | Recipient opted out |

### Key Methods

`send(unlink_failed=False, unlink_sent=True, auto_commit=False, raise_exception=False)`
: Main API to send SMS. Groups by provider and batches (default 500 per batch). Auto-commits between batches unless in test mode.

`_split_batch()`
: Splits records into batches of `_get_batch_size()` (default 500, configurable via `sms.session.batch-size`).

`_send()`
: Per-record send. Gets the appropriate `SmsApi` class and calls `_send_with_api()`.

`_send_with_api(sms_api, ...)`
: Calls the provider's batch API. On response, updates state and triggers tracker updates.

`_process_queue(ids=None)`
: Scheduled action entry point. Processes up to 10,000 queued SMS records in `outgoing` state. Called by the `sms` cron.

`action_set_canceled()` / `action_set_outgoing()` / `action_set_error(failure_type)`
: Manual state transition methods.

`resend_failed()`
: Action to retry SMS in `error` state. Resets to `outgoing` and calls `send()`.

`_gc_device()`
: Vacuum method (`@api.autovacuum`) that deletes records marked `to_delete=True`.

### Delivery Reports
The `sms.tracker` model tracks delivery via webhooks:
1. When SMS is sent, a `sms.tracker` record is created with the `sms_uuid`
2. Provider sends webhook to `/sms/status` with the UUID
3. `sms.tracker` updates the corresponding `sms.sms` state
4. Notifications (`mail.notification`) are updated to reflect delivery status

## sms.template

Reusable SMS templates linked to specific models.

### Fields
- `name` — Template name
- `model_id` — `ir.model` this template applies to (domain: `is_mail_thread_sms=True`)
- `model` — Char for the Python model name (computed, stored)
- `body` — SMS text content (translated)
- `sidebar_action_id` — Optional sidebar action to open the SMS composer

### Template Rendering
Templates use `mail.render.mixin` for QWeb rendering with model-specific fields. Jinja2 expressions like `{{ object.field_name }}` are supported.

### Methods

`action_create_sidebar_action()`
: Creates an `ir.actions.act_window` that opens the SMS composer with this template pre-filled.

`action_unlink_sidebar_action()`
: Removes the sidebar action.

`copy(default=None)` (overridden)
: Appends `(copy)` to the name.

## SMS Composer

The `sms.composer` (`sms.models`) handles composing and sending SMS:
- `comment` mode — Send to specific recipients
- `mass` mode — Send to a search result set
- `guess` mode — Automatically picks based on context

Accessed from:
- SMS template sidebar button
- `mail.thread` "Send SMS" action
- `phone_validation` mixin

## Architecture Notes

- SMS is sent via **IAP** (In-App Purchase) or custom gateway (override `SmsApi` / `_get_sms_api_class`)
- Batch sending groups SMS with the **same body** into a single API call for efficiency
- Delivery confirmation is **async** — states update via webhooks
- The `to_delete` flag marks records for garbage collection instead of immediate deletion, avoiding race conditions with in-flight webhooks

## See Also
- [[Modules/mail]] — Email vs SMS, `mail.thread` SMS capability
- `calendar_sms` — SMS reminders for calendar events
- `sms_twilio` — Twilio-specific SMS provider addon
- `phone_numbers` / `phone_validation` — Phone number formatting and validation
