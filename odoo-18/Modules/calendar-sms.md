---
Module: calendar_sms
Version: Odoo 18
Type: Extension
Tags: [calendar, sms, alarm, event, notification]
---

# calendar_sms — SMS Notifications for Calendar Events

## Overview

**Addon key:** `calendar_sms`
**Depends:** `calendar`, `sms`
**Source path:** `~/odoo/odoo18/odoo/addons/calendar_sms/`

This module extends `calendar.alarm` with an SMS alarm type and routes SMS-based reminders through the `calendar.alarm_manager` cron job. It does not introduce new models — all new fields are added to existing `calendar` models via extension.

---

## Module Map

```
calendar_sms
├── models/
│   ├── calendar_alarm.py          ← alarm_type +='sms', sms_template_id, sms_notify_responsible
│   ├── calendar_alarm_manager.py  ← _send_reminder override sends SMS
│   └── calendar_event.py           ← _do_sms_reminder, action_send_sms, _get_trigger_alarm_types
└── __init__.py
```

---

## Model: `calendar.alarm` (extends base `calendar.alarm`)

**File:** `models/calendar_alarm.py`
**Inheritance:** `_inherit = 'calendar.alarm'`

Extends the base alarm model to add `alarm_type = 'sms'` as a third option alongside `notification` and `alarm`.

### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `alarm_type` | `Selection` (extend) | Added `'sms'` to base selection. `ondelete='sms' → 'set default'` |
| `sms_template_id` | `Many2one(sms.template)` | Domain: `model in ['calendar.event']`. Compute sets default template |
| `sms_notify_responsible` | `Boolean` | If True, also notifies the event's responsible (user_id). Valid only when `alarm_type == 'sms'` |

### `_compute_sms_template_id`

```
alarm_type == 'sms' AND no template set  → auto-assign 'calendar_sms.sms_template_data_calendar_reminder'
alarm_type != 'sms'                      → clear template
alarm_type == 'sms' WITH existing        → keep existing
```

The default SMS template is the `calendar_sms.sms_template_data_calendar_reminder` XMLID — a pre-installed template containing event reminder text.

### `_onchange_duration_interval()`

When `alarm_type` is `sms`, sets `sms_notify_responsible = False` unless toggled by the user. Also appends `" - Notify Responsible"` to the alarm name when `sms_notify_responsible` is checked.

---

## Model: `calendar.event` (extends base `calendar.event`)

**File:** `models/calendar_event.py`
**Inheritance:** `_inherit = 'calendar.event'`

### Fields

None added directly. Extends existing alarm-related methods.

### `_get_trigger_alarm_types()`

Extends the base alarm type list by returning `super() + ['sms']`. This ensures the alarm manager cron recognizes SMS-type alarms.

```python
def _get_trigger_alarm_types(self):
    return super()._get_trigger_alarm_types() + ['sms']
```

### `_do_sms_reminder(alarms)`

Core SMS sending method. Called by `calendar.alarm_manager._send_reminder()` when processing SMS alarms:

```
for alarm in alarms:
    1. Get all attendees (via _mail_get_partners())
    2. Exclude attendees who DECLINED the event
    3. Exclude attendees without a sanitized phone number
    4. If alarm.sms_notify_responsible is False:
       Exclude the event's user_id.partner_id from recipients
    5. Send SMS via _message_sms_with_template():
       - Template: alarm.sms_template_id (or fallback literal text)
       - Partners: filtered recipient set
       - put_in_queue: False (send immediately)
```

**Key filter: declined attendees are skipped.** An attendee who declined the calendar event will not receive the SMS reminder, even if they have a valid phone number.

### `action_send_sms()`

Wizard action that opens the `sms.composer` in mass composition mode, pre-filled with all event attendees as recipients. Requires at least one `partner_ids` on the event or raises `UserError`.

---

## Alarm Manager — `calendar.alarm_manager`

**File:** `models/calendar_alarm_manager.py`
**Inheritance:** `_inherit = 'calendar.alarm_manager'`

### `_send_reminder()` — Cron Override

The base `calendar` module's cron method processes all alarm types. The `calendar_sms` extension adds SMS handling after the base call:

```python
def _send_reminder(self):
    # 1. Process notification + email alarms (from base calendar module)
    super()._send_reminder()

    # 2. Get events with SMS alarms due now
    events_by_alarm = self._get_events_by_alarm_to_notify('sms')
    if not events_by_alarm:
        return

    # 3. For each alarm, fetch its events and send SMS
    for alarm_id, event_ids in events_by_alarm.items():
        alarm = self.env['calendar.alarm'].browse(alarm_id)
        events = self.env['calendar.event'].browse(event_ids)
        events._do_sms_reminder(alarm)

        # 4. For recurring events: set up next SMS alarm
        for event in events:
            if event.recurrence_id:
                next_date = event.get_next_alarm_date(events_by_alarm)
                event.recurrence_id.with_context(date=next_date)._setup_alarms()
```

**Recurring event handling:** If the event is part of a recurrence, after sending the current SMS reminder, `get_next_alarm_date()` is called to determine the next alarm trigger time for this alarm within the recurrence series, and `_setup_alarms()` is called to register that future alarm.

---

## L4: SMS Provider Integration

`calendar_sms` does NOT implement its own SMS gateway. It relies entirely on the `sms` module's ` _message_sms_with_template()` method, which:
1. Renders the `sms.template` using QWeb templating (with `calendar.event` as the rendering record)
2. Sends via the configured SMS provider (IAP or custom gateway)
3. Logs the SMS in `sms.sms` records

The `sms.template` record `calendar_sms.sms_template_data_calendar_reminder` (XMLID) is the default template installed by this module. It typically contains a template like:
```
Event reminder: {{ object.name }}, {{ object.display_time }}.
```

If no template is set and `alarm.sms_template_id` is `False`, the fallback literal string `"Event reminder: %(name)s, %(time)s."` is used instead.

---

## L4: Alarm Triggering Mechanism

The complete alarm flow:

```
calendar.alarm_manager (ir.cron)
         │
         │ _send_reminder() [cron]
         │
    ┌────┴────────────────────────────┐
    │ alarm_type='notification'       │ alarm_type='email'       │ alarm_type='sms'
    │ _notify_participants_sms         │ _send_mail_reminder      │ _do_sms_reminder
    │ (in-app notification)            │ (mail.mail record)       │ (_message_sms_with_template)
    └──────────────────────────────────┴──────────────────────────┘
```

Alarms are triggered when the cron `calendar.alarm_manager._send_reminder()` runs (typically every minute). It queries `calendar.event` records whose:
- `start_datetime` is within `[now - alarm_duration, now]`
- `alarm_ids` contains the alarm type
- Attendees have not declined

The `_get_events_by_alarm_to_notify('sms')` method performs this query specifically for SMS alarms.

---

## Alarm Types Comparison

| Alarm Type | Mechanism | Recipient Selection | Template |
|-----------|-----------|-------------------|----------|
| `notification` | In-app notification (bus) | All non-declined attendees | N/A (notification model) |
| `email` | `mail.mail` via composer | All non-declined attendees | `calendar.alarm.mail_template_id` |
| `sms` | `sms.sms` via `_message_sms_with_template` | All non-declined + phone-sanitized + optional responsible | `calendar.alarm.sms_template_id` |

---

## See Also

- [Modules/Calendar](modules/calendar.md) — base calendar module (alarm model, event model, alarm manager cron)
- [Modules/SMS](modules/sms.md) — SMS provider integration and `sms.template`
- [Core/API](core/api.md) — mixin patterns, `_mail_get_partners()`
