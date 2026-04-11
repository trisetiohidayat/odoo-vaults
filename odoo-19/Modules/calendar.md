---
tags:
  - #odoo19
  - #modules
  - #calendar
---

# Calendar

## Overview

| Property | Value |
|----------|-------|
| Module | `calendar` |
| Path | `odoo/addons/calendar/` |
| Category | Productivity/Calendar |
| Version | 1.1 (Odoo 19) |
| Dependencies | `base`, `mail` |
| Application | True |
| License | LGPL-3 |
| Author | Odoo S.A. |

---

## Purpose

The Calendar module provides full-featured meeting and event scheduling for Odoo. It manages time-based events with attendees, reminders, recurrence rules (iCal RRULE), video call integration via Discuss, and synchronization with external calendars (Google Calendar, Microsoft Exchange). It is the foundational scheduling layer used by CRM, Project, HR, and many other modules.

**Odoo 18 to 19 changes:** Key improvements include redesigned recurrence handling with DST-safe occurrence calculation, `ir.cron.trigger`-based alarm scheduling (replacing generic scheduler calls), per-user default privacy settings stored in `res.users.settings`, and tighter integration with the Discuss video call system.

---

## Architecture

### Models (18 models total)

| Model | File | Role |
|-------|------|------|
| `calendar.event` | `calendar_event.py` | Core meeting/event model (inherits `mail.thread`) |
| `calendar.attendee` | `calendar_attendee.py` | Attendee with RSVP state, access token |
| `calendar.recurrence` | `calendar_recurrence.py` | Recurrence rule (iCal RRULE, dateutil-based) |
| `calendar.alarm` | `calendar_alarm.py` | Reminder/notification settings |
| `calendar.alarm_manager` | `calendar_alarm_manager.py` | Cron-based alarm dispatcher (abstract model) |
| `calendar.filter` | `calendar_filter.py` | Per-user calendar filter preferences |
| `calendar.event.type` | `calendar_event_type.py` | Meeting category/color tags |
| `res.partner` | `res_partner.py` | Extended with meeting_count, meeting_ids, busy lookup |
| `res.users` | `res_users.py` | Extended with calendar_default_privacy, systray |
| `res.users.settings` | `res_users_settings.py` | Stores per-user calendar_default_privacy |
| `discuss.channel` | `discuss_channel.py` | Video call channels for meetings |
| `mail.activity` | `mail_activity.py` | Linked calendar_event_id, bi-directional sync |
| `mail.activity.mixin` | `mail_activity_mixin.py` | activity_calendar_event_id computed field |
| `mail.activity.type` | `mail_activity_type.py` | Adds `category = 'meeting'` selection |
| `ir.http` | `ir_http.py` | `_auth_method_calendar` for token-based invite auth |
| `utils.py` | `utils.py` | `interval_from_events()` helper |

**L4 Note:** `mail.activity.type` is the actual model name (no `calendar_` prefix). It is stored in `addons/mail/models/mail_activity_type.py` but extended by the calendar module.

### Module Dependencies Graph

```
calendar
├── base           (required)
├── mail           (required, provides messaging/threading)
├── discuss        (optional, for video calls via discuss.channel)
├── google_calendar (optional, sync)
├── microsoft_calendar (optional, sync)
└── calendar_ics   (optional, iCal import)
```

---

## calendar.event — Core Event Model

Inherits: `mail.thread`, `_systray_view = 'calendar'`

### Field Definitions (L1-L2)

#### Identification & Description
```python
name = fields.Char('Meeting Subject', required=True)
description = fields.Html('Description',
    help="""When synchronization with an external calendar is active,
    this description is synchronized with the one of the associated
    meeting in that external calendar. Any update will be propagated
    there and vice versa.""")
location = fields.Char('Location', tracking=True)
notes = fields.Html('Notes')  # Internal-only, not synced externally
```

#### Organizer & Ownership
```python
user_id = fields.Many2one('res.users', 'Organizer',
    default=lambda self: self.env.user, index='btree_not_null')
partner_id = fields.Many2one('res.partner', string='Scheduled by',
    related='user_id.partner_id', readonly=True)
```

**L3 insight:** `user_id` is the event owner and default email sender. The `partner_id` is a convenience related field. All attendees have their own `calendar.attendee` record.

#### Video Calls
```python
videocall_location = fields.Char('Meeting URL',
    compute='_compute_videocall_location', store=True, copy=True)
videocall_source = fields.Selection([('discuss', 'Discuss'), ('custom', 'Custom')],
    compute='_compute_videocall_source')
videocall_channel_id = fields.Many2one('discuss.channel', 'Discuss Channel',
    index="btree_not_null")
access_token = fields.Char('Invitation Token', store=True, copy=False, index=True)
```

**L3:** `videocall_location` is computed: if `videocall_source == 'discuss'`, generates a Discuss route `/calendar/join_videocall/{access_token}`. If `access_token` is missing, generates one via `uuid.uuid4().hex`. Recurring events each get their own `access_token` to prevent the base event deletion issue.

#### Privacy & Visibility
```python
privacy = fields.Selection([
    ('public', 'Public'),
    ('private', 'Private'),
    ('confidential', 'Only internal users')], 'Privacy',
    help="People to whom this event will be visible.")
effective_privacy = fields.Selection(
    [('public', 'Public'), ('private', 'Private'), ('confidential', 'Only internal users')],
    'Effective Privacy', compute="_compute_effective_privacy")
show_as = fields.Selection([
    ('free', 'Available'),
    ('busy', 'Busy')], 'Show as', default='busy', required=True)
is_highlighted = fields.Boolean(compute='_compute_is_highlighted')
is_organizer_alone = fields.Boolean(
    compute='_compute_is_organizer_alone', string="Is the Organizer Alone",
    help="""Check if the organizer is alone in the event, i.e. if the organizer
    is the only one that hasn't declined the event (only if the organizer
    is not the only attendee)""")
```

**L2:** `effective_privacy` falls back to `user_id.calendar_default_privacy` when `privacy` is unset. `show_as = 'busy'` marks time as unavailable in partner busy lookup. `is_organizer_alone` is a computed field (not a method) that helps highlight when all attendees have declined — critical for CRM pipeline reviews.

#### Timing Fields
```python
start = fields.Datetime('Start', required=True, tracking=True,
    default=_default_start, index=True)
stop = fields.Datetime('Stop', required=True, tracking=True,
    default=_default_stop,
    compute='_compute_stop', readonly=False, store=True)
display_time = fields.Char('Event Time', compute='_compute_display_time')
allday = fields.Boolean('All Day', default=False)
start_date = fields.Date('Start Date', store=True, tracking=True,
    compute='_compute_dates', inverse='_inverse_dates')
stop_date = fields.Date('End Date', store=True, tracking=True,
    compute='_compute_dates', inverse='_inverse_dates')
duration = fields.Float('Duration', compute='_compute_duration',
    store=True, readonly=False)
```

**L2:**
- `stop` is computed from `start` + `duration` (stored by default). When `start` changes, `stop` is recomputed while `duration` is locked. The `store=True` means `stop` is written to the DB and recomputed on change.
- `_compute_stop` uses `self.env.remove_to_compute(duration_field, self)` to prevent re-computation loops: when `start` is updated, `duration` is marked computed so accessing `event.duration` inside `_compute_stop` does not trigger circular dependency.
- For allday events, `start_date`/`stop_date` hold the dates and `start`/`stop` are set to 08:00-18:00 as convention (allday events are timezone-agnostic by design).
- `_default_start` rounds now to the next half-hour. `_default_stop` adds `get_default_duration()` hours (default 1).

**L3:** The `_inverse_dates` onchange sets full-day events to 8 AM start / 6 PM stop convention.

#### Linked Document (Activity Linking)
```python
res_id = fields.Many2oneReference('Document ID', model_field='res_model')
res_model_id = fields.Many2one('ir.model', 'Document Model', ondelete='cascade')
res_model = fields.Char('Document Model Name',
    related='res_model_id.model', readonly=True, store=True)
res_model_name = fields.Char(related='res_model_id.name')
activity_ids = fields.One2many('mail.activity', 'calendar_event_id',
    string='Activities')
```

**L3:** `res_model`/`res_id` allow linking events to any Odoo model (CRM leads, Project tasks, etc.). When creating from a model context, `default_get` supports `active_model`/`active_id` as well as `default_res_model`/`default_res_id`.

#### Attendees
```python
attendee_ids = fields.One2many('calendar.attendee', 'event_id',
    'Participant')
current_attendee = fields.Many2one("calendar.attendee",
    compute="_compute_current_attendee", search="_search_current_attendee")
current_status = fields.Selection(string="Attending?",
    related="current_attendee.state", readonly=False)
should_show_status = fields.Boolean(compute="_compute_should_show_status")
partner_ids = fields.Many2many('res.partner', 'calendar_event_res_partner_rel',
    string='Attendees', default=_default_partners)
invalid_email_partner_ids = fields.Many2many('res.partner',
    compute='_compute_invalid_email_partner_ids')
unavailable_partner_ids = fields.Many2many('res.partner',
    string="Unavailable Attendees",
    compute='_compute_unavailable_partner_ids')
```

**L2:**
- `partner_ids` is the writeable field; `attendee_ids` is auto-synced via `_attendees_values()`.
- `invalid_email_partner_ids` uses `single_email_re` regex to flag partners with no/garbage email.
- `unavailable_partner_ids` uses `interval_from_events()` + `intervals_overlap()` to detect scheduling conflicts.

**L3:** `_compute_unavailable_partner_ids` does an O(2n) overlap check: groups all events by time slot, then for each partner looks up their busy events via `res.partner._get_busy_calendar_events()` (filters `show_as = 'busy'` only). This runs on save and warns users about conflicts.

**L4 Performance:** `_compute_unavailable_partner_ids` calls `partner_ids._get_busy_calendar_events()` which does a `search()` on `calendar.event` filtered by `partner_ids`. With many attendees, this can be expensive. Consider index on `(stop, start, partner_ids)` for large datasets.

#### Counters
```python
attendees_count = fields.Integer(compute='_compute_attendees_count')
accepted_count = fields.Integer(compute='_compute_attendees_count')
declined_count = fields.Integer(compute='_compute_attendees_count')
tentative_count = fields.Integer(compute='_compute_attendees_count')
awaiting_count = fields.Integer(compute="_compute_attendees_count")
```

#### Reminders / Alarms
```python
alarm_ids = fields.Many2many(
    'calendar.alarm', 'calendar_alarm_calendar_event_rel',
    string='Reminders', ondelete="restrict",
    help="Notifications sent to all attendees to remind of the meeting.")
```

**L3:** `ondelete='restrict'` prevents alarm deletion if any event uses it. Alarms can be of type `notification` (in-app) or `email` (SMTP). `duration_minutes` is the canonical field for alarm calculations.

#### Recurrence Fields
```python
recurrency = fields.Boolean('Recurrent')
recurrence_id = fields.Many2one('calendar.recurrence',
    string="Recurrence Rule", index='btree_not_null')
follow_recurrence = fields.Boolean(default=False)
recurrence_update = fields.Selection([
    ('self_only', "This event"),
    ('future_events', "This and following events"),
    ('all_events', "All events"),
], store=False, copy=False, default='self_only')
```

**L3:** `follow_recurrence = True` means the event is generated by the recurrence and is not an exception. Exception events (modified from recurrence) have `follow_recurrence = False`. The `recurrence_update` field is passed in vals during write to trigger different recurrence behaviors.

**All rrule fields (pseudo-related, compute on demand):**
```python
rrule = fields.Char('Recurrent Rule',
    compute='_compute_recurrence', readonly=False)
rrule_type_ui = fields.Selection(RRULE_TYPE_SELECTION_UI, string='Repeat',
    compute="_compute_rrule_type_ui", readonly=False)
rrule_type = fields.Selection(RRULE_TYPE_SELECTION, string='Recurrence',
    compute='_compute_recurrence', readonly=False)
event_tz = fields.Selection(_tz_get, string='Timezone',
    compute='_compute_recurrence', readonly=False)
end_type = fields.Selection(END_TYPE_SELECTION, string='Recurrence Termination',
    compute='_compute_recurrence', readonly=False)
interval = fields.Integer(string='Repeat On',
    compute='_compute_recurrence', readonly=False)
count = fields.Integer(string='Number of Repetitions',
    compute='_compute_recurrence', readonly=False)
mon, tue, wed, thu, fri, sat, sun = fields.Boolean(
    compute='_compute_recurrence', readonly=False)
month_by = fields.Selection(MONTH_BY_SELECTION, string='Option',
    compute='_compute_recurrence', readonly=False)
day = fields.Integer('Date of month',
    compute='_compute_recurrence', readonly=False)
weekday = fields.Selection(WEEKDAY_SELECTION,
    compute='_compute_recurrence', readonly=False)
byday = fields.Selection(BYDAY_SELECTION, string="By day",
    compute='_compute_recurrence', readonly=False)
until = fields.Date(compute='_compute_recurrence', readonly=False)
```

**L2:** These are not real related fields — they exist to support both creation (before `recurrence_id` exists) and display/edit. The compute pulls values from `recurrence_id` when it exists, falls back to defaults.

**L3:** `rrule_type_ui` distinguishes `custom` (non-standard interval) from standard intervals for display.

**L4 edge case:** DST changes cause event duplication when the recurrence spans DST transitions. Odoo 19 handles this via `_get_occurrences()` which applies per-occurrence timezone localization and checks DST offsets before/after period start. If DST differs, the original event start is used.

#### Edit Permissions
```python
user_can_edit = fields.Boolean(compute='_compute_user_can_edit')
```

**L3:** `user_can_edit` allows the organizer, any attendee's users, and non-private events by admins. Used in form view to conditionally show edit controls.

### Key Methods

#### `create(vals_list)` — L3
1. Sets `is_calendar_event_new=True` context to suppress notification spam.
2. Normalizes vals with defaults via `default_get()`.
3. Auto-creates `mail.activity` records on linked documents for meeting-type activity types (`category='meeting'`).
4. Auto-appends organizer/attendee contact details to `description` HTML via `_get_contact_details_description()` unless `skip_contact_description` context is set.
5. Splits vals into `recurring_vals` and `other_vals` — creates non-recurring events and recurring events in separate batches via `super().create()`.
6. For each recurring event, calls `_apply_recurrence_values()` to create recurrence and generate child events. Detached events (beyond the count limit) are archived.
7. Sends invitation emails to attendees for events starting in the future: `events.filtered(lambda e: e.start > fields.Datetime.now()).attendee_ids._send_invitation_emails()`.
8. Sets up cron triggers for non-allday events via `_setup_alarms()`. Recurring events call `recurrence_id._setup_alarms()`; standalone events call `_setup_alarms()` directly.

#### `write(vals)` — L3
1. Extracts `recurrence_update` setting (`self_only` / `future_events` / `all_events`).
2. Calls `_check_calendar_privacy_write_permissions()` to guard against non-attendees modifying private events.
3. Converts `partner_ids` changes to `attendee_ids` via `_attendees_values()`. If `videocall_channel_id` exists, new partners are added via `channel.add_members()`.
4. Sets `follow_recurrence = False` if any time field changes and the event is part of a recurrence (unless `recurrence_update` is explicitly set).
5. Pops recurrence fields and routes:
   - `all_events`: calls `_rewrite_recurrence()` (archives all, reactivates base, reapplies)
   - `future_events`: calls `_update_future_events()` (splits recurrence, creates new one)
   - `self_only`: calls `_apply_recurrence_values()` directly
   - `break_recurrence` (setting `recurrency=False`): detaches events via `_break_recurrence()`
6. Sends attendee notifications on partner/time changes.
7. After writing, calls `recurrence_id._setup_alarms(recurrence_update=True)` for recurring events or `_setup_alarms()` for standalone events when `update_alarms` is true.
8. If `update_time` and another user modified the event, resets organizer's attendee status to `needsAction` to force re-acceptance.

**L4:** When another user updates time fields, the organizer's attendee status is reset to `needsAction` to prevent inconsistent acceptance state across recurrence events.

**L3 security:** `_check_calendar_privacy_write_permissions()` raises an `ir.rule` access error if the event is private and the user is neither the organizer nor an attendee.

#### `_check_closing_date()` — Validation
```python
@api.constrains('start', 'stop', 'start_date', 'stop_date')
def _check_closing_date(self):
    if not meeting.allday and meeting.start and meeting.stop and meeting.stop < meeting.start:
        raise ValidationError(...)
    if meeting.allday and meeting.start_date and meeting.stop_date and meeting.stop_date < meeting.start_date:
        raise ValidationError(...)
```

---

## calendar.attendee — RSVP Records

### Field Definitions

```python
event_id = fields.Many2one('calendar.event', required=True,
    index=True, ondelete='cascade')
recurrence_id = fields.Many2one('calendar.recurrence',
    related='event_id.recurrence_id')  # convenience
partner_id = fields.Many2one('res.partner', required=True,
    readonly=True, ondelete='cascade')
email = fields.Char('Email', related='partner_id.email')  # computed
phone = fields.Char('Phone', related='partner_id.phone')
common_name = fields.Char(compute='_compute_common_name', store=True)
access_token = fields.Char('Invitation Token', default=_default_access_token)
mail_tz = fields.Selection(_tz_get, compute='_compute_mail_tz',
    help='Timezone used for displaying time in the mail template')
state = fields.Selection(STATE_SELECTION, default='needsAction')
availability = fields.Selection([('free','Available'), ('busy','Busy')],
    readonly=True)
```

**L2:** `access_token` is a `uuid.uuid4().hex` — used for public calendar invite links (e.g., ICS download). `mail_tz` propagates the attendee's timezone to mail templates for correct time display.

### State Transitions

| State | Meaning |
|-------|---------|
| `needsAction` | Pending response (default) |
| `accepted` | Attendee confirmed |
| `declined` | Attendee declined |
| `tentative` | Attendee tentatively accepted |

**L3:** `create()` auto-sets `state='accepted'` when creating an attendee for the current user (organizer). This avoids the organizer needing to self-accept.

### Key Methods

#### `_send_invitation_emails()`
Calls `_notify_attendees()` with `calendar_template_meeting_invitation`. This is the entry point for all invitation mailings.

#### `_notify_attendees(mail_template, notify_author=False, force_send=False)`
1. Skips attendees where `_skip_send_mail_status_update()` returns True (controlled by override in sync modules).
2. Generates `.ics` files per event via `_get_ics_file()`.
3. If template has attachments, creates copies per attendee with `res_model='mail.compose.message'`.
4. Renders template per attendee via `_render_field()` with `compute_lang=True`.
5. Sends via `event_id.message_notify()` (bypasses Followers for invites).
6. Batch-commits via `mail_ids.send_after_commit()` if under `mail.mail_force_send_limit`.
7. **L4:** `_should_notify_attendee(notify_author)` checks `self.partner_id != self.env.user.partner_id` — the current user is never notified of their own action. The `notify_author=True` flag bypasses this check.

**L4:** The `no_document` context flag prevents ICS attachments from creating document records. The `calendar_template_ignore_recurrence` context flag (set in alarm dispatcher at `calendar_alarm_manager.py:197`) prevents duplicate notifications for recurrence-triggered alarms.

#### `do_accept() / do_decline() / do_tentative()`
Each posts a `calendar.subtype_invitation` message to the event thread (using `message_post` with `author_id=attendee.partner_id.id`), then writes the state. Used by email action links and UI buttons.

### Security

- Portal users can only see their own attendees (`calendar_attendee_rule_my`: domain `[(1,'=',1)]` but scoped to `base.group_portal`).
- `write()` calls `event_id.check_access('write')` to prevent attendee state manipulation without event write access.

---

## calendar.recurrence — RRULE Model

### Field Definitions

```python
name = fields.Char(compute='_compute_name', store=True)
base_event_id = fields.Many2one('calendar.event', ondelete='set null', copy=False)
calendar_event_ids = fields.One2many('calendar.event', 'recurrence_id')
event_tz = fields.Selection(_tz_get, default=lambda self: self.env.context.get('tz') or self.env.user.tz)
rrule = fields.Char(compute='_compute_rrule', inverse='_inverse_rrule', store=True)
dtstart = fields.Datetime(compute='_compute_dtstart')

# RRULE parameters
rrule_type = fields.Selection(RRULE_TYPE_SELECTION, default='weekly')
end_type = fields.Selection(END_TYPE_SELECTION, default='count')
interval = fields.Integer(default=1)
count = fields.Integer(default=1)
mon = fields.Boolean(); tue = fields.Boolean(); wed = fields.Boolean()
thu = fields.Boolean(); fri = fields.Boolean(); sat = fields.Boolean(); sun = fields.Boolean()
month_by = fields.Selection(MONTH_BY_SELECTION, default='date')
day = fields.Integer(default=1)
weekday = fields.Selection(WEEKDAY_SELECTION)
byday = fields.Selection(BYDAY_SELECTION)
until = fields.Date('Repeat Until')
trigger_id = fields.Many2one('ir.cron.trigger')  # Odoo 19: alarm trigger per recurrence
```

**L2:** `rrule` is a serialized iCal RRULE string (e.g., `FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE`). The `compute` + `inverse` pattern means changes to UI fields (`rrule_type`, `interval`, etc.) auto-update `rrule`, and parsing an external `rrule` string populates all fields.

**L3:** `base_event_id` is the template event. Deleting it selects a new base via `_select_new_base_event()`. `trigger_id` holds the next cron alarm trigger for the recurrence — it is the single source of truth for scheduling alarms across all occurrences of the recurrence.

### RRULE Serialization

`_rrule_serialize()` builds an `rrule.rrule()` object from fields, then `str()` serializes it. Key rules:
- `count` is capped at `MAX_RECURRENT_EVENT = 720`
- `end_type='forever'` sets `count=720` (same cap)
- Weekly rules require at least one weekday (`mon`-`sun`)
- Monthly by day: uses `bymonthday=day`
- Monthly by weekday: uses `byweekday=weekday(byday)` e.g., `MO(+2)` for second Monday

### `_get_occurrences(dtstart)` — DST-Safe Calculation

**L4:** This is the most complex method. It handles DST transitions:

1. Localizes `dtstart` to `event_tz`.
2. Runs `rrule.rrule()` on the naive datetime in the timezone.
3. Re-localizes each occurrence back to the timezone (with `is_dst=False` handling).
4. Converts to UTC, strips timezone for storage.
5. Compares DST offset before/after period start. If DST differs, uses the original `dtstart` to prevent event time drift.

**Example:** Monthly 1st of each month at 6 AM New York. Feb to Mar crosses DST. Without this logic, 11 AM UTC stored would become 7 AM after DST (wrong). The fix stores 10 AM UTC after DST (correct).

### `_apply_recurrence(specific_values_creation=None, generic_values_creation=None)`

1. Gets date ranges from `_range_calculation()`.
2. Reconciles with existing events via `_reconcile_events()` (finds which ranges already have events).
3. Creates missing events with `recurrence_id=recurrence.id, follow_recurrence=True`.
4. Detaches events no longer matching the recurrence.
5. Returns detached events (typically archived).

**L4:** `specific_values_creation` allows per-occurrence custom field values. `generic_values_creation` applies to all new events in this batch.

### `_split_from(event, recurrence_values=None)`

Splits a recurrence at a given event:
1. Calls `_stop_at(event)` to detach all events from `event.start` onward.
2. Creates a new recurrence with the remaining events and new `base_event_id`.
3. Sets `count = max(new_count, len(detached_events))` to preserve event count.

**Used by:** `_update_future_events()` when editing future events.

### `_stop_at(event)`

Detaches all events from `event.start` onward, sets `end_type='end_date'` with `until` one day before the split point.

### `_setup_alarms(recurrence_update=False)`

**L4:** This method on `calendar.recurrence` (distinct from `calendar.event._setup_alarms()`) is called after email/SMS alarm dispatch. It:
1. Computes the next alarm trigger time: `next_event.start - timedelta(minutes=min_duration_minutes)`.
2. Calls `cron._trigger(at=next_date)` to schedule the next `ir.cron.trigger`.
3. Stores the trigger on `recurrence.trigger_id`.
4. If `recurrence_update=True`, it skips existing valid triggers to avoid duplicates.

### Constraints

```python
_month_day = models.Constraint("""CHECK (
    rrule_type != 'monthly' OR month_by != 'day'
    OR day >= 1 AND day <= 31
    OR weekday IN (...) AND byday IN (...))""",
    "The day must be between 1 and 31")
```

Enforces that monthly-by-date recurrences have a valid day 1-31.

### `_is_event_over()` — L4

Returns `True` if all events in the recurrence have ended (uses `stop` for timed, `stop_date` for allday). Used by sync modules to avoid sending invites for past recurring events.

---

## calendar.alarm — Reminder Settings

### Field Definitions

```python
name = fields.Char('Name', translate=True, required=True)
alarm_type = fields.Selection([('notification','Notification'), ('email','Email')],
    required=True, default='email')
duration = fields.Integer('Remind Before', required=True, default=1)
interval = fields.Selection(list(_interval_selection.items()),
    'Unit', required=True, default='hours')
duration_minutes = fields.Integer('Duration in minutes', store=True,
    search='_search_duration_minutes', compute='_compute_duration_minutes')
mail_template_id = fields.Many2one('mail.template',
    domain=[('model', 'in', ['calendar.attendee'])],
    compute='_compute_mail_template_id', readonly=False, store=True)
body = fields.Text("Additional Message")
notify_responsible = fields.Boolean("Notify Responsible", default=False)
```

**L2:** `duration_minutes` is the canonical integer field for alarm calculations. The `_search_duration_minutes` domain search handles multi-unit queries (e.g., `duration_minutes > 30` correctly translates to `hours > 0.5`).

**L3:** `mail_template_id` auto-defaults to `calendar_template_meeting_reminder` when `alarm_type == 'email'`. The template uses `calendar.attendee` as model for per-attendee rendering.

**L4:** `notify_responsible` is automatically cleared in `_onchange_duration_interval()` if `alarm_type` is not email/notification. The name auto-updates to `"Email - 1 hours"` format.

---

## calendar.alarm_manager — Cron Dispatcher

Abstract model (`_name = 'calendar.alarm_manager'`). Executed via `ir.cron_scheduler_alarm` running every minute.

### `_get_events_by_alarm_to_notify(alarm_type)`

SQL query finds events where `event.start - CAST(alarm.duration || ' ' || alarm.interval AS Interval) >= lastcall AND < now`. Uses `SQL` for safe interpolation. The interval arithmetic is PostgreSQL-native: `duration || ' ' || interval` constructs an `Interval` value (e.g., `'1 hours'`). Subclass override `_get_notify_alert_extra_conditions()` allows sync modules to exclude already-synced events.

### `_send_reminder()`

1. Gets email-type alarm events in the window.
2. Filters to non-declined attendees of future events (`stop > now`).
3. Groups attendees by alarm and sends via `_notify_attendees(notify_author=True, force_send=...)`.
4. **L4:** `notify_author=True` ensures the organizer receives the email reminder too (distinguishing from invite emails where `notify_author` is controlled by the caller).
5. Calls `_setup_event_recurrent_alarms(events_by_alarm)` for recurrence re-triggering.

### `get_next_notif()`

Returns next 24 hours of notification-type alarms for the current user. Uses `_get_next_potential_limit_alarm()` to find candidate events, then `do_check_alarm_for_one_date()` to apply per-event alarm filtering against `calendar_last_notif_ack`.

### `_notify_next_alarm(partner_ids)`

Sends the next alarm notification to partner IDs via the Odoo bus (`_bus_send`). Called after event create/write/delete.

---

## calendar.filter — Per-User Calendar Filters

```python
user_id = fields.Many2one('res.users', required=True,
    default=lambda self: self.env.user, index=True, ondelete='cascade')
partner_id = fields.Many2one('res.partner', required=True, index=True)
active = fields.Boolean('Active', default=True)
partner_checked = fields.Boolean('Checked', default=True)
```

**Constraint:** `UNIQUE(user_id, partner_id)` — a user cannot filter the same contact twice.

**L3:** `partner_checked` tracks whether the partner is visible in the calendar view's filter panel. `get_selected_calendars_partner_ids()` in `res.users` uses this to return the visible partner IDs.

---

## res.partner Extensions

```python
meeting_count = fields.Integer("# Meetings", compute='_compute_meeting_count')
meeting_ids = fields.Many2many('calendar.event', ...,
    string='Meetings', copy=False)
calendar_last_notif_ack = fields.Datetime(
    'Last notification marked as read from base Calendar',
    default=fields.Datetime.now)
```

**L3:** `_compute_meeting()` uses `search_fetch` with prefetch for performance. Includes events from child partners (company hierarchy). The SQL query groups by `(res_partner_id, calendar_event_id)` to avoid duplicates, then propagates child company events up to the parent.

**L3:** `_get_busy_calendar_events(start_datetime, end_datetime)` returns all busy (`show_as='busy'`) events overlapping the interval, grouped by partner. Used by the unavailable partner computation.

**L4:** `_get_busy_calendar_events()` calls `search()` for each partner individually within the loop, accumulating results into `event_by_partner_id`. With large partner lists, this is O(n) database round-trips.

---

## res.users Extensions

```python
calendar_default_privacy = fields.Selection(
    [('public','Public by default'),
     ('private','Private by default'),
     ('confidential','Internal users only')],
    compute="_compute_calendar_default_privacy",
    inverse="_inverse_calendar_res_users_settings")
```

**L3:** The value is stored in `res.users.settings` (a separate table). The compute reads from `res_users_settings_id.calendar_default_privacy`. Falls back to `calendar.default_privacy` ir.config_parameter (default `'public'`).

**L4 security:** `write()` raises `AccessError` if a user tries to update another's `calendar_default_privacy`. This prevents users from making their events public by changing the default without consent.

**Systray:** `_systray_get_calendar_event_domain()` builds a complex domain for today's non-declined events. For timed events, it converts "now" to user TZ and UTC. For allday events, it compares `start_date` against today's date in user TZ. The comment in the code includes an ASCII art diagram explaining the timezone offset math.

---

## discuss.channel — Video Call Binding

```python
calendar_event_ids = fields.One2many("calendar.event", "videocall_channel_id")

def _should_invite_members_to_join_call(self):
    if self.calendar_event_ids:
        return False  # Don't auto-invite for calendar-based calls
    return super()._should_invite_members_to_join_call()
```

**L3:** When a `calendar.event` with `videocall_source='discuss'` is created, `_create_videocall_channel()` either reuses an existing channel for the recurrence (searches for another event in the same recurrence that already has a channel) or creates a new group channel via `discuss.channel._create_group()`. For recurrences, all events share the same channel because the channel is set on all events in the recurrence simultaneously.

---

## mail.activity — Calendar Activity Link

```python
calendar_event_id = fields.Many2one('calendar.event',
    string="Calendar Meeting", index='btree_not_null', ondelete='cascade')
```

**L3:** Bi-directional sync:
- `write()`: when `date_deadline` changes, propagates the date diff to the linked `calendar_event_id.start` (respects user TZ for non-allday events).
- `calendar.event` write: syncs `name` to `summary`, `description` to `note`, `start` to `date_deadline`, `user_id` to `user_id`.
- Loop protection via context flags (`calendar_event_meeting_update`, `mail_activity_meeting_update`).

**L2:** `action_create_calendar_event()` opens the calendar event form with activity context, linking back via `default_activity_ids` and `orig_activity_ids`. `do_action_done()` appends activity feedback to the event's `notes` field (not `description`).

---

## Security Rules (calendar_security.xml)

| Rule | Model | Perm | Groups | Description |
|------|-------|------|--------|-------------|
| `calendar_event_rule_my` | `calendar.event` | read | Portal | See events where you are attendee |
| `calendar_event_rule_employee` | `calendar.event` | read | Internal | See all events |
| `calendar_event_rule_private` | `calendar.event` | all | — | Privacy domain: owner/attendee or public/confidential |
| `calendar_attendee_rule_my` | `calendar.attendee` | read | Portal | See all attendees (portal) |

**L4 privacy domain (record-rule level):** `_check_private_event_conditions()` is called in `_fetch_query()` to additionally suppress private field values (name, description, etc.) for non-owner/non-attendee users. This is ORM-level enforcement supplementing the record rule. The rule with `perm_read=False` for portal users on private events means portal users can see that a private event exists but cannot read its details.

**L4:** `_get_public_fields()` on `calendar.event` defines the fields visible on private events to non-participants: `id`, `active`, `allday`, `duration`, `user_id`, `interval`, `partner_id`, `count`, `rrule`, `recurrence_id`, `show_as`, `privacy`. All other fields (name, description, location, start, stop, etc.) are hidden via `_fetch_query()`.

---

## Cron Jobs

| Job | Model | Action | Interval |
|-----|-------|--------|----------|
| `ir_cron_scheduler_alarm` | `calendar.alarm_manager` | `_send_reminder()` | Every minute |

**L4:** The cron runs as `base.user_root` (superuser), ensuring alarm emails reach all users regardless of record rules. Trigger-based scheduling (via `ir.cron.trigger` on `calendar.recurrence.trigger_id`) means individual events can trigger outside this daily window for precise timing. When the cron fires, `_send_reminder()` queries all due email alarms (not just one), sends them, then calls `_setup_event_recurrent_alarms()` to schedule the next occurrence's alarms.

---

## iCal / vobject Export (`_get_ics_file()`)

**L2:** Generates RFC 5545-compliant `.ics` files. Requires the `vobject` Python package. Fields exported: `dtstart`, `dtend`, `summary`, `description` (HTML-sanitized to plain text), `location`, `rrule`, `valarm` (for each alarm), `attendee`, `organizer`.

**L4:** For allday events, `ics_datetime()` returns the date object directly (not UTC datetime), which makes the event a `DATE` VEVENT type per RFC 5545. The organizer CN parameter is sanitized by replacing `"` with `'`.

---

## Key Constants

```python
MAX_RECURRENT_EVENT = 720  # calendar_recurrence.py
DISCUSS_ROUTE = 'calendar/join_videocall'  # calendar_event.py

STATE_SELECTION = [
    ('accepted', 'Yes'),
    ('declined', 'No'),
    ('tentative', 'Maybe'),
    ('needsAction', 'Needs Action'),
]

RRULE_TYPE_SELECTION = [
    ('daily', 'Days'), ('weekly', 'Weeks'),
    ('monthly', 'Months'), ('yearly', 'Years'),
]
END_TYPE_SELECTION = [
    ('count', 'Number of repetitions'),
    ('end_date', 'End date'),
    ('forever', 'Forever'),
]
```

---

## Common Override Points (for subclasses)

| Method | Purpose | Known Overrides |
|--------|---------|----------------|
| `_skip_send_mail_status_update()` | Suppress invite emails for synced events | `calendar_google`, `calendar_microsoft` |
| `_get_notify_alert_extra_conditions()` | Exclude already-synced events from alarm dispatch | `calendar_google` |
| `_get_activity_excluded_models()` | Prevent activity creation for specific models | `appointment` |
| `_check_organizer_validation_conditions()` | Additional validation before event create | `calendar_google` |
| `_apply_recurrence()` | Sync recurrence to external calendar | `calendar_google`, `calendar_microsoft` |
| `_get_next_notif()` | Override notification content | `appointment` |

---

## Performance Considerations (L4)

1. **Recurrence range calculation** — `_range_calculation()` can generate up to 720 events. Each write to a recurrence triggers full re-evaluation. For high-frequency recurrence updates, batch operations matter.

2. **Busy event lookup** — `res.partner._get_busy_calendar_events()` does a `search()` on `calendar.event` filtered by `partner_ids`. With large partner lists, this is O(n) database queries (n partners) accumulated in a Python loop. The search includes `show_as='busy'` as a filter to reduce result set.

3. **Alarm dispatch** — `_get_events_by_alarm_to_notify()` runs a SQL query across `calendar_event`, `calendar_alarm_calendar_event_rel`, and `calendar_alarm`. Proper indexing on `calendar_event.start` and the join table is critical for performance.

4. **Unavailability computation** — `_compute_unavailable_partner_ids` does O(n*m) interval overlap checks for n attendees over m partner busy events. Cached when possible but can be expensive on large meetings.

5. **Attendee notification** — `_notify_attendees()` batch-commits via `mail_ids.send_after_commit()` but renders templates per attendee. For large events (100+ attendees), consider batching.

6. **`_get_public_fields()` cache:** This method calls `fields_get(attributes=['manual'])` which hits the schema. Called in `_fetch_query()` on every private event query, which could be expensive at scale.

---

## Odoo 18 to 19 Migration Notes

| Area | Old Behavior | New Behavior |
|------|-------------|--------------|
| Alarm scheduling | Generic scheduler call | `ir.cron.trigger` per recurrence (`trigger_id`) |
| Privacy defaults | Hardcoded per-user | `res.users.settings.calendar_default_privacy` |
| Recurrence DST | No special handling | Per-occurrence timezone-aware calculation |
| Attendee email parsing | Split on `:` | Direct `partner_id.email` lookup |
| Activity sync | One-way (activity event) | Bi-directional with loop protection |
| Private event names | Hidden in name_search | Hidden in `_fetch_query()` and display_name |
| Recurrence splitting | Base event archived | Base event reactivated + new recurrence |
| Video calls | Discuss channel auto-created | Lazy creation with recurrence sharing |

---

## Related Modules

- `calendar_google`: Google Calendar 2-way sync
- `calendar_google_calendar`: Google Calendar API integration
- `calendar_ics`: iCal import/export (.ics files)
- `calendar_sms`: SMS reminders (via `sms` module)
- `calendar_email`: Enhanced email reminders
- `appointment`: Appointment booking (extends `calendar.event`, `calendar.alarm_manager`)
- `project`: Task scheduling links to calendar events
- `crm`: Lead/opportunity meeting links
- `hr_holidays`: Time off linked to calendar
