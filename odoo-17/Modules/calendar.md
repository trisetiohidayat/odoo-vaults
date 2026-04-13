---
tags: [odoo, odoo17, module, calendar]
research_depth: medium
---

# Calendar Module — Deep Reference

**Source:** `addons/calendar/models/`

## Overview
Meeting scheduling, event management, attendee tracking, recurrence rules (iCal RRULE), and external calendar sync. The module extends `mail.thread` for full chatter support.

## Architecture

### Models
- `calendar.event` (aka `Meeting`) — the main event model
- `calendar.attendee` — RSVP tracking per attendee per event
- `calendar.alarm` — reminder configuration (notification or email)
- `calendar.recurrence` — RRULE master record for recurring event series
- `res.partner` extended with calendar-related fields

---

## calendar.event (Meeting)

**File:** `calendar_event.py`

Inherits `mail.thread` for full chatter. Every event is also a document recordable via `res_model`/`res_id` for linking to any Odoo model.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required) | Meeting subject |
| `description` | Html | Rich description |
| `user_id` | Many2one `res.users` | Organizer (default: current user) |
| `partner_id` | Many2one `res.partner` | Organizer's partner (related) |
| `start` | Datetime | Start datetime (default: next half-hour) |
| `stop` | Datetime | End datetime (default: start + 1 hour) |
| `duration` | Float | Duration in hours (computed from start/stop) |
| `allday` | Boolean | All-day event (switches to date-only mode) |
| `start_date` | Date | All-day start date |
| `stop_date` | Date | All-day end date |
| `location` | Char | Physical location string |
| `videocall_location` | Char | Video call URL (computed) |
| `videocall_source` | Selection | 'discuss' or 'custom' |
| `videocall_channel_id` | Many2one `discuss.channel` | Linked Discuss channel |
| `privacy` | Selection | `public` / `private` / `confidential` |
| `show_as` | Selection | `free` / `busy` (calendar visibility) |
| `partner_ids` | Many2many `res.partner` | All attendees |
| `attendee_ids` | One2many `calendar.attendee` | Attendee RSVP records |
| `current_attendee` | Many2one (computed) | Current user's attendee record |
| `current_status` | Selection (related) | Current user's RSVP state |
| `alarm_ids` | Many2many `calendar.alarm` | Reminders |
| `activity_ids` | One2many `mail.activity` | Linked activities |
| `recurrency` | Boolean | Is part of a recurrence |
| `recurrence_id` | Many2one `calendar.recurrence` | Parent recurrence rule |
| `follow_recurrence` | Boolean | Is not an exception to the rule |
| `rrule` | Char | iCal RRULE string (computed from recurrence fields) |
| `rrule_type` | Selection | daily/weekly/monthly/yearly |
| `rrule_type_ui` | Selection | Same + 'custom' for UI |
| `event_tz` | Selection | Timezone for recurrence |
| `end_type` | Selection | `count` / `end_date` / `forever` |
| `interval` | Integer | Repeat every N (days/weeks/etc) |
| `count` | Integer | Number of repetitions |
| `until` | Date | End date for recurrence |
| `mon`–`sun` | Boolean | Days of week (weekly recurrence) |
| `month_by` | Selection | `date` (day of month) / `day` (nth weekday) |
| `day` | Integer | Day of month (1-31) |
| `weekday` | Selection | Day name for monthly-by-weekday |
| `byday` | Selection | 1st/2nd/3rd/4th/-1 (last) |
| `recurrence_update` | Selection | `self_only` / `future_events` / `all_events` |
| `res_model` | Char | Linked document model |
| `res_id` | Many2oneReference | Linked document ID |
| `res_model_id` | Many2one `ir.model` | Model reference |
| `active` | Boolean | Active (archive support) |
| `categ_ids` | Many2many `calendar.event.type` | Category/tags |
| `display_time` | Char (computed) | Human-readable time display |
| `attendees_count` | Integer (computed) | Total attendee count |
| `accepted_count` | Integer (computed) | Accepted RSVPs |
| `declined_count` | Integer (computed) | Declined RSVPs |
| `tentative_count` | Integer (computed) | Tentative RSVPs |
| `awaiting_count` | Integer (computed) | No-response count |
| `is_organizer_alone` | Boolean (computed) | Organizer accepted but all others declined |
| `user_can_edit` | Boolean (computed) | Edit permission check |
| `access_token` | Char | Unique token for public invitations |
| `invalid_email_partner_ids` | Many2many (computed) | Attendees with invalid email |

### Duration / Stop Computation

```python
# _compute_stop: when start changes, duration is kept fixed, stop is recomputed
event.stop = event.start + timedelta(minutes=round(event.duration * 60))

# _compute_duration: recomputed from start/stop
event.duration = self._get_duration(event.start, event.stop)
```

### Allday Mode

When `allday=True`, `start`/`stop` are set to 08:00/18:00 local time and `start_date`/`stop_date` are synced via `_inverse_dates`.

---

## calendar.attendee

**File:** `calendar_attendee.py`

One record per attendee per event. Automatically subscribes the partner as a mail follower on creation.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | Many2one (required, cascade) | Parent event |
| `partner_id` | Many2one `res.partner` (required, cascade) | Attendee |
| `email` | Char (related) | Partner's email |
| `phone` | Char (related) | Partner's phone |
| `common_name` | Char (computed) | `partner_id.name` or email |
| `access_token` | Char | UUID for invitation email links |
| `mail_tz` | Selection (computed) | Attendee's timezone |
| `state` | Selection | RSVP status |
| `availability` | Selection | `free` / `busy` (external calendar sync) |

### RSVP States

| Value | Label |
|-------|-------|
| `needsAction` | Needs Action |
| `tentative` | Maybe |
| `declined` | No |
| `accepted` | Yes |

### RSVP Actions

```python
def do_accept(self)   # Posts chatter message, sets state='accepted'
def do_decline(self)  # Posts chatter message, sets state='declined'
def do_tentative(self) # Sets state='tentative'
```

### Email Notification

`_send_mail_to_attendees()` renders the `calendar.calendar_template_meeting_invitation` template per attendee, attaches an `.ics` calendar file, and sends via `message_notify`. The organizer is excluded from self-notification via `_should_notify_attendee()`.

---

## calendar.alarm

**File:** `calendar_alarm.py`

Reminder configuration reusable across events.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required, translate) | Auto-generated display name |
| `alarm_type` | Selection | `notification` (in-app) / `email` |
| `duration` | Integer (required) | Reminder interval |
| `interval` | Selection | `minutes` / `hours` / `days` |
| `duration_minutes` | Integer (computed, stored) | Total minutes (for searching) |
| `mail_template_id` | Many2one `mail.template` | Template for email reminders |
| `body` | Text | Additional message appended to notification |

### `duration_minutes` Computation

```python
# _compute_duration_minutes
if interval == "minutes": result = duration
elif interval == "hours":  result = duration * 60
elif interval == "days":   result = duration * 60 * 24
```

The `name` field auto-updates via `_onchange_duration_interval` to format `"Email - 1 hours"`.

---

## calendar.recurrence

**File:** `calendar_recurrence.py`

Master record for a recurring event series. Stores decomposed RRULE parameters and generates child `calendar.event` records.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (computed) | Human-readable recurrence description |
| `base_event_id` | Many2one `calendar.event` | Original event template |
| `calendar_event_ids` | One2many `calendar.event` | All occurrences |
| `event_tz` | Selection | Timezone for occurrence calculation |
| `rrule` | Char (computed/inverse) | Serialized iCal RRULE string |
| `rrule_type` | Selection | `daily`/`weekly`/`monthly`/`yearly` |
| `end_type` | Selection | `count`/`end_date`/`forever` |
| `interval` | Integer | Every N periods (default 1) |
| `count` | Integer | Number of occurrences |
| `until` | Date | End date |
| `mon`–`sun` | Boolean | Days selected for weekly recurrence |
| `month_by` | Selection | `date` (day-of-month) / `day` (nth-weekday) |
| `day` | Integer | Day of month (1-31) |
| `weekday` | Selection | Weekday name for monthly-by-weekday |
| `byday` | Selection | 1st/2nd/3rd/4th/-1st (last) |
| `dtstart` | Datetime (computed) | First occurrence start |

### RRULE Serialization

`_rrule_serialize()` converts decomposed fields to an iCal RRULE string using `dateutil.rrule`. `_rrule_parse()` reverses this using `rrule.rrulestr()`.

### Monthly by Weekday Example
```python
# "2nd Monday of each month":
month_by = 'day'
weekday = 'MON'
byday = '2'
# RRULE: FREQ=MONTHLY;BYDAY=MO;BYSETPOS=2
```

### Key Methods

| Method | Purpose |
|--------|---------|
| `_apply_recurrence()` | Generates all missing `calendar.event` records from the rule |
| `_detach_events()` | Strips recurrence link from event(s), marks `follow_recurrence=False` |
| `_get_occurrences(dtstart)` | Returns datetimes for each occurrence (handles DST) |
| `_get_ranges(start, duration)` | Returns `(start, stop)` tuples for each occurrence |
| `_setup_alarms()` | Schedules `ir.cron.trigger` entries for future reminders |
| `_split_from(event)` | Splits a recurrence at an event; returns new recurrence |
| `_stop_at(event)` | Detaches event and all following; closes recurrence by date |
| `_get_week_days()` | Returns tuple of selected `rrule.weekday` objects |

### DST Handling

Occurrences in tz-aware recurrence are localized with `pytz`, converted to UTC, and stored as naive datetimes. On retrieval, DST transitions are detected and adjusted to preserve the wall-clock time.

---

## Event–Recurrence Link

When a `calendar.event` has `recurrency=True`, Odoo either links to an existing `calendar.recurrence` or creates one on write. The `recurrence_update` selection field controls whether changes apply to:

- `self_only` — only this occurrence (detaches it from recurrence)
- `future_events` — this and all subsequent occurrences (splits the recurrence)
- `all_events` — the entire series (updates the recurrence base values)

---

## Reminder Execution

The `calendar_alarm_manager` module runs via cron and fires `ir.cron.trigger` entries created by `calendar.recurrence._setup_alarms()`. At trigger time, it sends in-app notifications (`bus.bus`) or renders and sends `mail.mail` via the alarm's `mail_template_id`.

---

## iCal Export

`_get_ics_file()` on `calendar.event` uses the `vobject` library to generate RFC 5545 `.ics` files attached to invitation emails.

---

## See Also
- [Modules/mail](Modules/mail.md) — notification framework, message_notify
- [Modules/res_partner](Modules/res_partner.md) — partners as attendees
- [Modules/google_calendar](Modules/google_calendar.md) — Google Calendar two-way sync
- [Modules/microsoft_calendar](Modules/microsoft_calendar.md) — Outlook Calendar sync
- [Modules/discuss](Modules/discuss.md) — video call integration
