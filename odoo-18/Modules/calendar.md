# Calendar Module (Odoo 18)

## Overview

The Calendar module manages events, meetings, attendee invitations, and recurrence rules (iCal format). It integrates with the messaging system for invitations and reminders.

**Module Path:** `calendar/`
**Key Models:** `calendar.event`, `calendar.attendee`, `calendar.recurrence`, `calendar.alarm`
**Dependencies:** `mail` (messaging, activities), `resource`

---

## Architecture

```
calendar.event
    ├── calendar.attendee    (One2many)
    ├── calendar.recurrence  (Many2one, for recurring events)
    ├── calendar.alarm       (Many2many - reminders)
    ├── calendar.event.type  (Many2many - tags)
    ├── res.partner          (Many2many - attendees)
    ├── res.users            (organizer)
    └── discuss.channel      (videocall)

calendar.recurrence
    └── calendar.event      (One2many - instances)
```

---

## calendar.event

The main event model. Inherits `mail.thread` for messaging.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Meeting subject (required) |
| `description` | Html | Event description |
| `user_id` | Many2one | Organizer (default: current user) |
| `location` | Char | Physical/virtual location |
| `videocall_location` | Char | Meeting URL (computed) |
| `access_token` | Char | Invitation token for public links |
| `videocall_source` | Selection | `discuss` (Odoo Meet) or `custom` |
| `videocall_channel_id` | Many2one | Discuss channel for the meeting |
| `privacy` | Selection | `public`, `private`, `confidential` |
| `show_as` | Selection | `free` or `busy` (for availability) |
| `is_highlighted` | Boolean | Highlighted in calendar view |
| `is_organizer_alone` | Boolean | Computed: organizer is the only non-declined attendee |
| `active` | Boolean | Archive/unarchive events |
| `categ_ids` | Many2many | Tags/categories |
| `start` | Datetime | Event start (required) |
| `stop` | Datetime | Event end (required, computed from duration) |
| `display_time` | Char | Human-readable time string |
| `allday` | Boolean | All-day event (date only, no time) |
| `start_date` | Date | Date version of start (for allday) |
| `stop_date` | Date | Date version of stop (for allday) |
| `duration` | Float | Duration in hours |
| `res_id` | Many2oneReference | Linked document ID |
| `res_model_id` | Many2one | Linked document model |
| `res_model` | Char | Linked document model name |
| `res_model_name` | Char | Linked document model display name |
| `activity_ids` | One2many | Linked activities |
| `attendee_ids` | One2many | Attendee records |
| `current_attendee` | Many2one | Computed: current user's attendee record |
| `current_status` | Selection | Related: current attendee's state |
| `should_show_status` | Boolean | Whether to show accept/decline buttons |
| `partner_ids` | Many2many | Attendee partners (sync with attendee_ids) |
| `invalid_email_partner_ids` | Many2many | Partners with invalid emails |
| `alarm_ids` | Many2many | Reminder alarms |
| `recurrency` | Boolean | Whether event is recurring |
| `recurrence_id` | Many2one | Parent recurrence rule |
| `follow_recurrence` | Boolean | Event follows recurrence (not an exception) |
| `recurrence_update` | Selection | `self_only`, `future_events`, `all_events` |
| `rrule` | Char | iCal RRULE string (computed from fields) |
| `rrule_type` | Selection | `daily`, `weekly`, `monthly`, `yearly` |
| `event_tz` | Selection | Timezone for the event |
| `end_type` | Selection | `count`, `end_date`, `forever` |
| `interval` | Integer | Repeat interval (every N days/weeks/etc) |
| `count` | Integer | Number of repetitions |
| `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun` | Boolean | Days of week |
| `month_by` | Selection | `date` (day of month) or `day` (day of week) |
| `day` | Integer | Day of month |
| `weekday` | Selection | Monday-Sunday |
| `byday` | Selection | `1` (first), `2` (second), `3` (third), `4` (fourth), `-1` (last) |
| `until` | Date | End date for recurrence |
| `attendees_count` | Integer | Total attendee count |
| `accepted_count` | Integer | Accepted attendee count |
| `declined_count` | Integer | Declined attendee count |
| `tentative_count` | Integer | Maybe count |
| `awaiting_count` | Integer | No-response count |
| `user_can_edit` | Boolean | Computed: can current user edit |

### Computed Fields

#### `_compute_stop()`
Computes `stop` from `start` and `duration`.

#### `_compute_dates()`
Syncs `start_date`/`stop_date` with `start`/`stop` for allday events.

#### `_compute_videocall_location()`
Generates the meeting URL from `videocall_channel_id`.

#### `_compute_recurrence()`
Generates `rrule` from the recurrence field values.

### Key Methods

#### `_default_start()` / `_default_stop()`
Default meeting times (next half-hour, default 1-hour duration).

#### `_create_videocall_channel()`
Creates a `discuss.channel` for the meeting's video call.

```python
def _create_videocall_channel(self):
    # Creates discuss.channel with type='chat'
    # Sets name to event name
    # Adds organizer and all accepted attendees
    # Returns the channel
```

#### `_get_ics_partners()`
Returns attendee partners formatted for iCal export.

#### `_observe_start()`
Returns the event start time as a datetime for comparison.

---

## calendar.attendee

Attendee records linked to calendar events. One per partner per event.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | Many2one | Calendar event (required, cascade delete) |
| `partner_id` | Many2one | Attendee partner (required) |
| `email` | Char | Attendee email (related from partner) |
| `phone` | Char | Attendee phone (related from partner) |
| `common_name` | Char | Display name (computed from partner name or email) |
| `access_token` | Char | Invitation token for responding via email link |
| `mail_tz` | Selection | Attendee's timezone for email templates |
| `state` | Selection | `needsAction`, `tentative`, `declined`, `accepted` |
| `availability` | Selection | `free` or `busy` |

### Attendee States

| State | Meaning |
|-------|---------|
| `needsAction` | Invitation not yet responded to |
| `tentative` | Maybe (tentatively accepted) |
| `accepted` | Will attend |
| `declined` | Will not attend |

### Key Methods

#### Create Logic
- If creating for the current user and no state specified -> state=`accepted` (organizer)
- Syncs email from common_name if not provided

#### `_subscribe_partner()`
Adds the attendee partner to the event's message followers.

#### `do_accept()` / `do_decline()` / `do_tentative()`
Action methods for responding to invitations via email link.

---

## calendar.recurrence

Encapsulates an iCal recurrence rule and its generated event instances.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Auto-generated description (e.g., "Every 2 weeks on Monday") |
| `calendar_event_ids` | One2many | All events in this recurrence |
| `base_event_id` | Many2one | The template event for this recurrence |
| `rrule` | Char | iCal RRULE string |
| `rrule_type` | Selection | `daily`, `weekly`, `monthly`, `yearly` |
| `event_tz` | Selection | Timezone for the rule |
| `end_type` | Selection | `count`, `end_date`, `forever` |
| `count` | Integer | Number of occurrences |
| `interval` | Integer | Repeat interval |
| `until` | Date | End date |
| `mon` through `sun` | Boolean | Days of week |
| `month_by` | Selection | `date` or `day` |
| `day`, `weekday`, `byday` | Various | Monthly/yearly specifics |
| `exdate_ids` | One2many | Excluded dates (exceptions) |

### RRULE Type to dateutil Mapping

```python
SELECT_FREQ_TO_RRULE = {
    'daily': rrule.DAILY,
    'weekly': rrule.WEEKLY,
    'monthly': rrule.MONTHLY,
    'yearly': rrule.YEARLY,
}
```

### Key Methods

#### `_apply_recurrence()`
Creates all event instances from the recurrence rule.

#### `_break_recurrence()`
Removes recurrence from an event, converting future events to standalone.

#### `_rrule_serialize()` / `_rrule_deserialize()`
Converts between the UI fields and the iCal `rrule` string.

---

## calendar.alarm

Reminder definitions for calendar events.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Auto-generated name (e.g., "Email - 1 hours") |
| `alarm_type` | Selection | `notification` or `email` |
| `duration` | Integer | Time before event |
| `interval` | Selection | `minutes`, `hours`, `days` |
| `duration_minutes` | Integer | Total duration in minutes (computed) |
| `mail_template_id` | Many2one | Email template for reminders |
| `body` | Text | Additional message to send |

### Key Methods

#### `_compute_duration_minutes()`
Converts `duration + interval` into total minutes for scheduling.

#### `_compute_mail_template_id()`
Sets default reminder email template.

### Auto-generated Name

```python
def _onchange_duration_interval(self):
    self.name = "%s - %s %s" % (display_alarm_type, self.duration, display_interval)
# Result: "Email - 1 hours", "Notification - 15 minutes"
```

---

## Cron Jobs

### `_cron_scheduler()`
Processes pending event reminders. Runs via `calendar.ir_cron_scheduler_alarm`.

Actions:
1. Finds events with alarms triggered since last run
2. Creates `mail.activity` records for in-app notifications
3. Sends email reminders via `mail.template`
4. Handles both notification-type and email-type alarms

---

## Videocall Integration

Events can have integrated video calls:

1. **Source: `discuss`** - Uses Odoo's built-in video conferencing (default)
   - `_create_videocall_channel()` creates a `discuss.channel`
   - Channel added to event as `videocall_channel_id`
   - Route: `calendar/join_videocall/{access_token}`

2. **Source: `custom`** - External URL (e.g., Zoom, Teams link)
   - `videocall_location` stores the custom URL directly

---

## Recurrence Handling

### Creating a Recurrence

When `recurrency=True` is set on an event:

1. A `calendar.recurrence` record is created with the rule fields
2. The event is linked as `base_event_id`
3. Additional instances are generated via `_apply_recurrence()`
4. All instances share the same `recurrence_id`

### Modifying Recurrence

The `recurrence_update` field controls scope:

- `self_only` - Only this event is modified (becomes an exception)
- `future_events` - This and all future events are modified
- `all_events` - All events in the recurrence are modified

### Breaking Recurrence

Converting a recurring event to standalone:
1. Sets `recurrency=False`
2. Clears `recurrence_id`
3. Clears recurrence-related fields on the event

### Exception Events

Events that deviate from the recurrence pattern:
- `follow_recurrence=False`
- Modified fields stored directly on the event
- Does not affect other events in the recurrence

### Excluded Dates (Exdates)

Dates explicitly excluded from a recurrence:
- Stored in `exdate_ids` on `calendar.recurrence`
- Used when a specific occurrence is cancelled

---

## iCal Export

Events can be exported as iCal format:

```python
def _get_ics_partners(self):
    # Returns list of (name, email) tuples for attendees
    # Used by vobject iCal generation
```

The `vobject` Python library generates standard iCal RRULE strings from the recurrence fields.

---

## Resource Booking Integration

The `calendar.event` model is extended by `resource_calendar` for room/equipment booking:
- Links to `resource.resource` for room bookings
- `meeting_room_id` field for room assignment
- Availability checking against resource calendar
