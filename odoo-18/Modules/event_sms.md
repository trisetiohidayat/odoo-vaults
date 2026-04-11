---
Module: event_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #event #sms #notification
---

## Overview

Adds SMS notification support to event mail schedulers. Bridges `event` with `sms` module: `event.type.mail`, `event.mail`, and `event.mail.registration` all gain a `notification_type='sms'` option and an `sms.template` reference.

**Depends:** `event`, `sms`

**Key Behavior:** SMS schedulers send via `registrations._message_sms_schedule_mass`. When an SMS template is deleted, its linked `event.mail` and `event.type.mail` records are cascade-deleted.

---

## Models

### `event.type.mail` (Inherited)

**Inherited from:** `event.type.mail`

| Field | Type | Note |
|-------|------|------|
| `notification_type` | Selection | Adds `'sms'` |
| `template_ref` | Reference | Adds `sms.template` selection |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_notification_type()` | — | Sets to `'sms'` when `template_ref._name == 'sms.template'` |

### `event.mail` (Inherited)

**Inherited from:** `event.mail`

| Field | Type | Note |
|-------|------|------|
| `notification_type` | Selection | Adds `'sms'` |
| `template_ref` | Reference | Adds `sms.template` selection |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_notification_type()` | — | Sets to `'sms'` when `template_ref._name == 'sms.template'` |
| `_execute_event_based_for_registrations(regs)` | — | Routes `notification_type=='sms'` to `_send_sms` |
| `_send_sms(registrations)` | — | Calls `registrations._message_sms_schedule_mass` with template |
| `_template_model_by_notification_type()` | dict | Maps `'sms'` to `'sms.template'` |

### `event.mail.registration` (Inherited)

**Inherited from:** `event.mail.registration`

| Method | Returns | Note |
|--------|---------|------|
| `_execute_on_registrations()` | — | Filters SMS schedulers; calls `_send_sms` on each scheduler |

### `sms.template` (Inherited)

**Inherited from:** `sms.template`

| Method | Returns | Note |
|--------|---------|------|
| `_search(domain, ...)` | recordset | Adds `('model', '=', 'event.registration')` when `filter_template_on_event` context set |
| `unlink()` | — | Cascade-deletes linked `event.mail` and `event.type.mail` records |
