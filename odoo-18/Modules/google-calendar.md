---
Module: google_calendar
Version: Odoo 18
Type: Integration
Tags: [google, calendar, sync, google-calendar, google-meet, oauth2, two-way-sync]
---

# google_calendar — Google Calendar Synchronization

## Overview

The `google_calendar` module provides **bidirectional synchronization** between Odoo `calendar.event` / `calendar.recurrence` records and Google Calendar. It extends the base `calendar.event` with Google-specific fields, the `google.calendar.sync` mixin, and a full synchronization engine driven by both user-triggered sync (from calendar view) and a 12-hour cron job.

**Depends:** `google_account`, `calendar`
**Category:** Productivity
**License:** LGPL-3
**API:** Google Calendar API v3

---

## Architecture Overview

```
google.calendar.migration (reset_account.py)
    └─ google.calendar.account.reset (TransientModel)

google.calendar.sync (AbstractModel mixin — google_sync.py)
    ├─ google_id, need_sync, active fields
    ├─ _sync_odoo2google() — Odoo → Google (after-commit)
    ├─ _sync_google2odoo() — Google → Odoo (batch)
    ├─ _google_insert(), _google_patch(), _google_delete() — API calls
    └─ _get_records_to_sync(), _get_sync_domain() — abstract methods

calendar.event  (inherits google.calendar.sync)
    ├─ google_id (computed from recurrence)
    ├─ guests_readonly, videocall_source (+ google_meet)
    ├─ _get_google_synced_fields(), _odoo_values(), _google_values()
    └─ _get_sync_domain(), _get_event_user(), _check_modify_event_permission()

calendar.recurrence  (inherits google.calendar.sync)
    ├─ _get_event_google_id() — generates per-instance google_id: {rec_google_id}_{timestamp}
    ├─ _apply_recurrence() — deletes original single event from Google before promoting to recurrence
    ├─ _write_from_google() — handles base event time changes, re-creates recurrence
    └─ _get_sync_domain() — only synced by owner (user_id = current user)

calendar.attendee  (extends base)
    └─ do_tentative(), do_accept(), do_decline() — trigger _sync_event()

res.users  (extends base)
    ├─ google_calendar_* fields (related to res.users.settings)
    ├─ _get_google_calendar_token() — auto-refreshes token if expired
    ├─ _sync_google_calendar() — main sync orchestrator
    ├─ _sync_request() — full/delta sync request with sync token
    └─ _sync_all_google_calendar() — cron entry point (12h interval)

res.users.settings  (inherits base)
    ├─ google_calendar_rtoken, google_calendar_token, google_calendar_token_validity
    ├─ google_calendar_sync_token — Google-side next sync token (persisted)
    ├─ google_calendar_cal_id — last synced calendar ID
    └─ _refresh_google_calendar_token() — OAuth2 refresh flow

GoogleCalendarService  (utils/google_calendar.py)
    ├─ get_events(sync_token?, token) — delta or full sync
    ├─ insert(values, token) — creates event + Google Meet if needed
    ├─ patch(event_id, values, token) — updates event
    └─ delete(event_id, token) — removes from Google (with singleEvents flag)

GoogleEvent  (utils/google_event.py)
    ├─ Immutable recordset-like wrapper for Google event dicts
    ├─ is_cancelled(), is_recurrence(), is_recurrent(), is_recurrence_follower()
    ├─ full_recurring_event_id() — detects rescheduled recurring events
    ├─ owner(env) — resolves organizer from extendedProperty or email
    └─ odoo_ids(env) — maps google_id → odoo_id via _event_ids_from_google_ids or metadata

google.service  (from google_account)
    └─ OAuth2 token management, _refresh_google_token(), _get_client_id()
```

---

## Model: `google.calendar.sync` (AbstractModel Mixin)

**File:** `addons/google_calendar/models/google_sync.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `google_id` | `Char` | Google Calendar event/recurrence ID, copy=False |
| `need_sync` | `Boolean` | True by default. Set False after successful Google sync. Set True when synced fields change |
| `active` | `Boolean` | Default True. Inactive events are not synced to Google |

### Fields That Trigger `need_sync=True`

On every `write()` call, if any key intersects with `_get_google_synced_fields()`, `need_sync` is set to True. The sync is then executed post-commit via `@after_commit`.

### `write()` Hook

```python
def write(self, vals):
    google_service = GoogleCalendarService(self.env['google.service'])
    if 'google_id' in vals:
        self.env.registry.clear_cache()  # _event_ids_from_google_ids
    synced_fields = self._get_google_synced_fields()
    if 'need_sync' not in vals and vals.keys() & synced_fields and not self.env.user.google_synchronization_stopped:
        vals['need_sync'] = True
    result = super().write(vals)
    if self.env.user._get_google_sync_status() != "sync_paused":
        for record in self:
            if record.need_sync and record.google_id:
                record.with_user(record._get_event_user())._google_patch(google_service, record.google_id, record._google_values(), timeout=3)
    return result
```

For new records without `google_id`, the sync is an insert (via `create()` hook).

### `@after_commit` Decorator

All Google API calls (`_google_insert`, `_google_patch`, `_google_delete`) are decorated with `@after_commit`, which defers execution until after the current database transaction commits. This ensures that:

- If the Odoo database transaction rolls back (e.g., the event creation crashes), the Google event is never created (avoiding duplicates)
- Google receives only confirmed changes

### `_sync_odoo2google()`

```python
def _sync_odoo2google(self, google_service: GoogleCalendarService):
    if not self:
        return
    records_to_sync = self.filtered(self._active_name)  # active only
    cancelled_records = self - records_to_sync  # inactive = cancelled
    updated_records = records_to_sync.filtered('google_id')  # already on Google
    new_records = records_to_sync - updated_records  # new events

    for record in cancelled_records:
        if record.google_id and record.need_sync:
            record.with_user(record._get_event_user())._google_delete(google_service, record.google_id)
    for record in new_records:
        if record._is_google_insertion_blocked(sender_user=self.env.user):
            continue
        record.with_user(record._get_event_user())._google_insert(google_service, record._google_values())
    for record in updated_records:
        record.with_user(record._get_event_user())._google_patch(google_service, record.google_id, record._google_values())
```

### `_sync_google2odoo()`

```python
@api.model
def _sync_google2odoo(self, google_events: GoogleEvent, write_dates=None, default_reminders=()):
    existing = google_events.exists(self.env)
    new = google_events - existing - google_events.cancelled()
    odoo_values = [dict(self._odoo_values(e, default_reminders), need_sync=False) for e in new]
    new_odoo = self.with_context(dont_notify=True)._create_from_google(new, odoo_values)
    cancelled = existing.cancelled()
    cancelled_odoo = self.browse(cancelled.odoo_ids(self.env))
    # Handle rescheduled recurring events (old google_id → new google_id)
    rescheduled_events = new.filter(lambda gevent: not gevent.is_recurrence_follower())
    if rescheduled_events:
        google_ids_to_remove = [event.full_recurring_event_id() for event in rescheduled_events]
        cancelled_odoo += self.env['calendar.event'].search([('google_id', 'in', google_ids_to_remove)])
    cancelled_odoo.exists()._cancel()
    synced_records = new_odoo + cancelled_odoo
    # Last-write-wins for updates: Google wins if Google write_date >= Odoo write_date
    pending = existing - cancelled
    pending_odoo = self.browse(pending.odoo_ids(self.env)).exists()
    for gevent in pending:
        odoo_record = self.browse(gevent.odoo_id(self.env))
        if odoo_record not in pending_odoo:
            continue
        updated = parse(gevent.updated)
        odoo_record_write_date = write_dates.get(odoo_record.id, odoo_record.write_date)
        if not odoo_record_write_date or updated >= pytz.utc.localize(odoo_record_write_date):
            vals = dict(self._odoo_values(gevent, default_reminders), need_sync=False)
            odoo_record.with_context(dont_notify=True)._write_from_google(gevent, vals)
            synced_records |= odoo_record
    return synced_records
```

---

## Model: `calendar.event` (Google Extension)

**File:** `addons/google_calendar/models/calendar.py`

`Meeting` class: `_name = 'calendar.event'`, `_inherit = ['calendar.event', 'google.calendar.sync']`

### Fields Added by Google Extension

| Field | Type | Notes |
|-------|------|-------|
| `google_id` | `Char` | From mixin. Computed from `recurrence_id._get_event_google_id(event)` if not set directly |
| `guests_readonly` | `Boolean` | Defaults False. Set True when Google says `guestsCanModify=False` — only organizer can edit |
| `videocall_source` | `Selection` | Extended with `'google_meet'` option. Auto-set when `videocall_location` contains `meet.google.com` |

### `_compute_google_id`

```python
@api.depends('recurrence_id.google_id')
def _compute_google_id(self):
    for event in self:
        google_recurrence_id = event.recurrence_id._get_event_google_id(event)
        if not event.google_id and google_recurrence_id:
            event.google_id = google_recurrence_id
        elif not event.google_id:
            event.google_id = False
```

For recurring events, `google_id` is derived from recurrence google_id + start timestamp (NOT stored as a separate DB field, computed on the fly). Non-recurring events store their Google ID directly.

### Fields Synced to Google (`_get_google_synced_fields`)

```python
@api.model
def _get_google_synced_fields(self):
    return {'name', 'description', 'allday', 'start', 'date_end', 'stop',
            'attendee_ids', 'alarm_ids', 'location', 'privacy', 'active', 'show_as'}
```

> **Note:** `recurrency` is NOT in this set — recurrence rules are synced through `calendar.recurrence` model, not per-event.

### `_odoo_values(google_event, default_reminders)` — Google → Odoo

Converts a `GoogleEvent` dict into Odoo field values:

- `active`: False if cancelled
- `name`: Google summary or `(No title)`
- `description`: HTML-sanitized Google description
- `location`: Google location field
- `user_id`: Resolved via `google_event.owner(env)` — checks extendedProperty owner_id first, then email match
- `privacy`: Google visibility
- `attendee_ids`: Created/updated from Google attendees, matched by normalized email
- `alarm_ids`: Created from Google reminders (30min before default or per-event overrides)
- `recurrency`: True if Google event is recurrent
- `videocall_location`: Google Meet URL (from `conferenceData.entryPoints[entryPointType=video].uri`)
- `show_as`: `'free'` if `transparency=transparent`, else `'busy'`
- `guests_readonly`: Not `bool(google_event.guestsCanModify)`
- `allday`: Based on presence of `dateTime` vs `date` in Google response

For **recurring event instances** (followers):
- `google_id` = computed from recurrence google_id + start timestamp
- `recurrency` propagated from Google
- `follow_recurrence` = `not google_event.is_recurrence_follower()` (i.e., True if it was an exception)

### `_google_values()` — Odoo → Google

```python
def _google_values(self):
    start = {'date': None, 'dateTime': None}
    end = {'date': None, 'dateTime': None}
    if self.allday:
        start['date'] = self.start_date.isoformat()
        end['date'] = (self.stop_date + relativedelta(days=1)).isoformat()
    else:
        start['dateTime'] = pytz.utc.localize(self.start).isoformat()
        end['dateTime'] = pytz.utc.localize(self.stop).isoformat()
    values = {
        'id': self.google_id,
        'start': start,
        'end': end,
        'summary': self.name,
        'description': self._get_customer_description(),
        'location': self.location or '',
        'guestsCanModify': not self.guests_readonly,
        'organizer': {'email': self.user_id.email, 'self': self.user_id == self.env.user},
        'attendees': [...],
        'extendedProperties': {
            'shared': {'%s_odoo_id' % self.env.cr.dbname: self.id},
        },
        'reminders': {'overrides': [...], 'useDefault': False}
    }
    # Request Google Meet conference if no videocall_location and no google_id (new event)
    if not self.google_id and not self.videocall_location and not self.location:
        values['conferenceData'] = {'createRequest': {'requestId': uuid4().hex}}
    if self.privacy:
        values['visibility'] = self.privacy
    if self.show_as:
        values['transparency'] = 'opaque' if self.show_as == 'busy' else 'transparent'
    if not self.active:
        values['status'] = 'cancelled'
    return values
```

**Key behaviors:**
- All-day events: `dateTime=null`, `date` set to ISO date; end date is +1 day (Google end is exclusive)
- New events get a `conferenceData.createRequest` to generate Google Meet link automatically
- Cancelled events set `status: 'cancelled'` (not actually deleted — preserves google_id for potential re-creation)
- `extendedProperties.shared.{dbname}_odoo_id` stores Odoo event ID for reverse-lookup
- When the organizer is a non-synced Odoo user, `extendedProperties.shared.{dbname}_owner_id` is set instead
- Non-Odoo-user organizers: only `id, summary, attendees, start, end, reminders` are sent (to avoid 403 on Google sharing rules)

### `_get_sync_domain()`

```python
def _get_sync_domain(self):
    ICP = self.env['ir.config_parameter'].sudo()
    day_range = int(ICP.get_param('google_calendar.sync.range_days', default=365))
    lower_bound = fields.Datetime.subtract(fields.Datetime.now(), days=day_range)
    upper_bound = fields.Datetime.add(fields.Datetime.now(), days=day_range)
    return [
        ('partner_ids.user_ids', 'in', self.env.user.id),
        ('stop', '>', lower_bound),
        ('start', '<', upper_bound),
        # Do not sync follow_recurrence events — they are synced at recurrence creation
        '!', '&', '&', ('recurrency', '=', True), ('recurrence_id', '!=', False), ('follow_recurrence', '=', True)
    ]
```

Sync range is configurable via `google_calendar.sync.range_days` ICP (default 365 days each direction).

### `_check_modify_event_permission(values)`

When a non-organizer attendee tries to write to an event where `guests_readonly=True`, raises `ValidationError`. Edge cases bypassed:
- `need_sync=True` only (sync restart context)
- `skip_event_permission=True` (reset account wizard)

### `create()` Hook

```python
@api.model_create_multi
def create(self, vals_list):
    notify_context = self.env.context.get('dont_notify', False)
    return super(Meeting, self.with_context(dont_notify=notify_context)).create([
        dict(vals, need_sync=False) if vals.get('recurrence_id') or vals.get('recurrency') else vals
        for vals in vals_list
    ])
```

Events that are part of a recurrence are created without syncing — the recurrence itself handles the Google sync.

### Google Meet Detection

When `_compute_videocall_source` detects `meet.google.com` in `videocall_location`, it sets `videocall_source = 'google_meet'`. Conversely, `_google_values()` can generate a Google Meet link automatically for new events without an existing `videocall_location`.

---

## Model: `calendar.recurrence` (Google Extension)

**File:** `addons/google_calendar/models/calendar_recurrence_rule.py`

`_name = 'calendar.recurrence'`, `_inherit = ['calendar.recurrence', 'google.calendar.sync']`

### Key Methods

#### `_apply_recurrence()`

When a single event becomes the base of a recurrence:
1. For each previously synced event with a `google_id`: calls `_google_delete()` to remove from Google (since the recurrence will now own those slots)
2. Creates an inactive copy of each deleted event with the original `google_id` (so the next sync can delete them from Google)
3. Sets all events' `need_sync = False` (recurrence sync handles them)

#### `_get_event_google_id(event)`

Generates the per-instance Google ID for a recurring event:

```python
def _get_event_google_id(self, event):
    if self.google_id:
        if event.allday:
            time_id = event.start_date.isoformat().replace('-', '')
        else:
            start_compacted_iso8601 = event.start.isoformat().replace('-', '').replace(':', '')
            time_id = '%sZ' % start_compacted_iso8601
        return '%s_%s' % (self.google_id, time_id)
    return False
```

Format: `{recurrence_google_id}_{YYYYMMDDTHHMMSSZ}` for timed events, `{recurrence_google_id}_{YYYYMMDD}` for all-day.

#### `_write_from_google(vals)`

Called when Google pushes updates to the recurrence. Handles:
1. **Attendee sync**: Creates/updates/removes attendees across all events
2. **Time field change** (start/stop/allday): Archives old events, re-creates the recurrence with new values
3. **Rule change** (`rrule` different): Detaches events no longer matching, applies new recurrence

#### `_google_values()`

Sends the recurrence as a Google RRULE event. Key transformations:
- Strips `DTSTART` from rrule string (Google doesn't accept it)
- Appends `Z` to non-UTC `UNTIL` values (Google requires UTC until)
- Stores Odoo recurrence ID in `extendedProperties.shared.{dbname}_odoo_id`

---

## Model: `res.users.settings` (Google Extension)

**File:** `addons/google_calendar/models/res_users_settings.py`

### Fields

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `google_calendar_rtoken` | `Char` | `base.group_system` | OAuth2 refresh token (never exposed to client) |
| `google_calendar_token` | `Char` | `base.group_system` | OAuth2 access token |
| `google_calendar_token_validity` | `Datetime` | `base.group_system` | When the access token expires |
| `google_calendar_sync_token` | `Char` | `base.group_system` | Google-side next sync token (persisted across sessions) |
| `google_calendar_cal_id` | `Char` | `base.group_system` | Last synced calendar ID (changing triggers full resync) |
| `google_synchronization_stopped` | `Boolean` | `base.group_system` | User manually stopped sync |

### Token Management

**`_set_google_auth_tokens(access_token, refresh_token, ttl)`**:
- Writes `google_calendar_token` and `google_calendar_rtoken`
- Sets `google_calendar_token_validity` to `now + ttl seconds`

**`_refresh_google_calendar_token()`**:
- Calls `google.service._refresh_google_token('calendar', rtoken)`
- Updates access token and validity
- On HTTP 400/401: clears tokens (invalid grant), commits, raises `UserError`

**Token auto-refresh in sync flow** (`res_users.py`):
```python
def _get_google_calendar_token(self):
    self.ensure_one()
    if self.res_users_settings_id.sudo().google_calendar_rtoken and not self.res_users_settings_id._is_google_calendar_valid():
        self.sudo().res_users_settings_id._refresh_google_calendar_token()
    return self.res_users_settings_id.sudo().google_calendar_token
```

### `_google_calendar_authenticated()`

```python
def _google_calendar_authenticated(self):
    return bool(self.sudo().google_calendar_rtoken)
```

### `_is_google_calendar_valid()`

```python
def _is_google_calendar_valid(self):
    return self.sudo().google_calendar_token_validity >= (fields.Datetime.now() + timedelta(minutes=1))
```

Tokens expiring within 1 minute are considered invalid.

---

## Model: `res.users` (Google Extension)

**File:** `addons/google_calendar/models/res_users.py`

Fields are related to `res_users_settings_id.*` with `groups="base.group_system"`.

### `_get_google_calendar_token()`

Auto-refreshes token if expired before returning it.

### `_sync_google_calendar(google_service)`

Main sync orchestrator:

```python
def _sync_google_calendar(self, calendar_service):
    self.ensure_one()
    results = self._sync_request(calendar_service)
    if not results or (not results.get('events') and not self._check_pending_odoo_records()):
        return False
    events, default_reminders, full_sync = results.values()
    # Google → Odoo
    events.clear_type_ambiguity(self.env)
    recurrences = events.filter(lambda e: e.is_recurrence())
    odoo_events = self.env['calendar.event'].browse((events - recurrences).odoo_ids(self.env))
    odoo_recurrences = self.env['calendar.recurrence'].browse(recurrences.odoo_ids(self.env))
    synced_recurrences = self.env['calendar.recurrence']._sync_google2odoo(recurrences, recurrences_write_dates)
    synced_events = self.env['calendar.event']._sync_google2odoo(events - recurrences, events_write_dates, default_reminders=default_reminders)
    # Odoo → Google
    recurrences = self.env['calendar.recurrence']._get_records_to_sync(full_sync=full_sync)
    recurrences -= synced_recurrences
    recurrences.with_context(send_updates=send_updates)._sync_odoo2google(calendar_service)
    synced_events |= recurrences.calendar_event_ids - recurrences._get_outliers()
    events = self.env['calendar.event']._get_records_to_sync(full_sync=full_sync)
    (events - synced_events).with_context(send_updates=send_updates)._sync_odoo2google(calendar_service)
    return bool(results) and (bool(events | synced_events) or bool(recurrences | synced_recurrences))
```

### `_sync_request(calendar_service, event_id=None)`

```python
def _sync_request(self, calendar_service, event_id=None):
    full_sync = not bool(self.sudo().google_calendar_sync_token)
    with google_calendar_token(self) as token:
        if not event_id:
            events, next_sync_token, default_reminders = calendar_service.get_events(
                self.res_users_settings_id.sudo().google_calendar_sync_token, token=token)
        else:
            # Force sync without sync_token (avoid full sync on single-event trigger)
            events, next_sync_token, default_reminders = calendar_service.get_events(
                sync_token=token, token=token, event_id=event_id)
    if next_sync_token:
        self.res_users_settings_id.sudo().google_calendar_sync_token = next_sync_token
```

- First sync: `full_sync=True`, no sync token → fetches last 365 days of events
- Subsequent syncs: uses stored `sync_token` for delta sync (Google returns only changes)
- `InvalidSyncToken` exception (HTTP 410): falls back to full sync

### `_check_pending_odoo_records()`

Returns True if there are pending Odoo events/recurrences to sync to Google (used to determine if a "no new events from Google" result still requires Odoo→Google sync).

### `_sync_all_google_calendar()` (Cron)

```python
@api.model
def _sync_all_google_calendar(self):
    """ Cron job """
    users = self.env['res.users'].sudo().search([
        ('google_calendar_rtoken', '!=', False),
        ('google_synchronization_stopped', '=', False)
    ])
    google = GoogleCalendarService(self.env['google.service'])
    for user in users:
        user.with_user(user).sudo()._sync_google_calendar(google)
        self.env.cr.commit()
```

**Cron schedule:** Every 12 hours (`google_calendar_data.xml`, `ir_cron_sync_all_cals`)

### Sync Control Methods

```python
def stop_google_synchronization(self):
    self.sudo().google_synchronization_stopped = True

def restart_google_synchronization(self):
    self.sudo().google_synchronization_stopped = False
    self.env['calendar.recurrence']._restart_google_sync()
    self.env['calendar.event']._restart_google_sync()

def pause_google_synchronization(self):
    self.env['ir.config_parameter'].sudo().set_param("google_calendar_sync_paused", True)

def unpause_google_synchronization(self):
    self.env['ir.config_parameter'].sudo().set_param("google_calendar_sync_paused", False)
```

---

## Model: `calendar.attendee` (Google Extension)

**File:** `addons/google_calendar/models/calendar_attendee.py`

When an attendee accepts/tentatively accepts/declines via the Odoo mail link, the change is synced to Google:

```python
def _sync_event(self):
    all_events = self.mapped('event_id').filtered(lambda e: e.google_id)
    other_events = all_events.filtered(lambda e: e.user_id and e.user_id.id != self.env.user.id)
    for user in other_events.mapped('user_id'):
        service = GoogleCalendarService(self.env['google.service'].with_user(user))
        other_events.filtered(lambda ev: ev.user_id.id == user.id).with_user(user)._sync_odoo2google(service)
    google_service = GoogleCalendarService(self.env['google.service'])
    (all_events - other_events)._sync_odoo2google(google_service)
```

Organizer's own event changes go through the main sync. Other users' events that this user attended are synced using that user's token.

---

## Model: `google.calendar.account.reset` (TransientModel)

**File:** `addons/google_calendar/wizard/reset_account.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `Many2one(res.users)` | User whose Google account to reset |
| `delete_policy` | `Selection` | `dont_delete` / `delete_google` / `delete_odoo` / `delete_both` |
| `sync_policy` | `Selection` | `new` (only new events) / `all` (all existing events) |

### `reset_account()` Logic

1. Find all events/recurrences for the user with `google_id`
2. If `delete_google`: call `google.delete(event.google_id)` for each
3. If `delete_odoo`/`delete_both`: clear `google_id`, unlink events (unless `delete_google` only)
4. If `sync_policy == 'new'`: set `need_sync = False` for existing events (skip them in next sync)
5. Clear auth tokens, `google_calendar_sync_token`, `google_calendar_cal_id`

---

## `GoogleCalendarService` (Utility)

**File:** `addons/google_calendar/utils/google_calendar.py`

### API Endpoints Used

| Method | Endpoint | Description |
|--------|----------|-------------|
| `get_events` | `GET /calendar/v3/calendars/primary/events` | Delta sync or full sync |
| `insert` | `POST /calendar/v3/calendars/primary/events` | Create event (+ conferenceDataVersion) |
| `patch` | `PATCH /calendar/v3/calendars/primary/events/{id}` | Update event |
| `delete` | `DELETE /calendar/v3/calendars/primary/events/{id}` | Remove event (with singleEvents=true for recurrences) |

### `get_events()` Sync Token Logic

```python
if sync_token:
    params['syncToken'] = sync_token  # delta sync
else:
    # full sync — restrict to day_range (default 365 days each side)
    params['timeMin'] = lower_bound.isoformat() + 'Z'
    params['timeMax'] = upper_bound.isoformat() + 'Z'
```

On HTTP 410 with `fullSyncRequired`: raises `InvalidSyncToken` → triggers full sync.

### Pagination

Handles `nextPageToken` to iterate through all pages (events can span many pages for heavy users).

### `insert()` — Conference Data

```python
url = "/calendar/v3/calendars/primary/events?conferenceDataVersion=%d&sendUpdates=%s" % (
    1 if need_video_call else 0, "all" if send_updates else "none")
```

- `conferenceDataVersion=1`: allows creating Google Meet link on insert
- `sendUpdates=all`: notifies attendees of the change

### Authorization Scope

```python
def _get_calendar_scope(self, RO=False):
    return 'https://www.googleapis.com/auth/calendar%s' % ('.readonly' if RO else '')
```

---

## `GoogleEvent` (Utility Class)

**File:** `addons/google_calendar/utils/google_event.py`

A set-like immutable wrapper for Google event dicts. Inspired by Odoo recordsets.

### Key Methods

#### `owner(env)` — Resolving Event Organizer

```python
def owner(self, env):
    # Check extendedProperty for real owner (when event inserted by attendee, not owner)
    real_owner_id = self.extendedProperties and self.extendedProperties.get('shared', {}).get('%s_owner_id' % env.cr.dbname)
    if real_owner_id and real_owner.exists():
        return real_owner
    elif self.organizer and self.organizer.get('self'):
        return env.user
    elif self.organizer and self.organizer.get('email'):
        org_email = email_normalize(self.organizer.get('email'))
        return env['res.users'].search([('email_normalized', '=', org_email)], limit=1)
    else:
        return env['res.users']
```

This handles the case where user A creates an event in Odoo but user B syncs first — the event is inserted into user B's calendar with user A's ID stored in extended properties.

#### `full_recurring_event_id()` — Rescheduling Detection

When a recurring event instance is rescheduled in Google, its `google_id` changes from `{id}_{range}` to `{id}_{range}_{timestamp}`. This method reconstructs the old ID for cleanup:

```python
def full_recurring_event_id(self):
    # Matches: ID_RANGE_TIMESTAMP from ID + recurringEventId
    id_value = re.match(r'(\w+_)', self.id)
    rec_pattern = re.search(r'(\w+_R\d+(?:T\d+)?(?:Z)?)', self.recurringEventId)
    ts_pattern = re.search(r'(\d{8}(?:T\d+Z?)?)$', self.id)
    return f"{id_range}_{timestamp}"
```

#### `clear_type_ambiguity(env)`

For cancelled events without a `recurrence` field, the type (single event vs recurrence) is ambiguous. This method loads Odoo IDs and sets `recurrence=True` for those matching `calendar.recurrence`.

#### Odoo ID Resolution Priority

1. Check `_event_ids_from_google_ids` ORM cache (google_id → odoo_id from DB)
2. Check extended property `{dbname}_odoo_id` in event metadata
3. Deduplicate: only match Odoo records without `google_id` set (avoids double-linking when splitting recurrence)

---

## `calendar.alarm_manager` Extension

**File:** `addons/google_calendar/models/calendar_alarm_manager.py`

```python
@api.model
def _get_notify_alert_extra_conditions(self):
    base = super()._get_notify_alert_extra_conditions()
    return SQL("%s AND event.google_id IS NULL", base)
```

Events that are synced with Google DO NOT trigger Odoo's internal alarm notifications — Google handles reminders for synced events. Non-synced events (without `google_id`) still trigger Odoo alarms.

---

## HTTP Controller

**File:** `addons/google_calendar/controllers/main.py`

Route: `/google_calendar/sync_data` (type=json, auth=user)

Called from the calendar view sync button. Returns status dictionary:
- `need_config_from_admin`: Client ID not set
- `need_auth`: User hasn't authorized Odoo
- `need_refresh`: Sync happened, client needs refresh
- `no_new_event_from_google`: No changes from Google
- `sync_stopped` / `sync_paused`: Sync not active

---

## Cron

**File:** `addons/google_calendar/data/google_calendar_data.xml`

```xml
<record forcecreate="True" id="ir_cron_sync_all_cals" model="ir.cron">
    <field name="name">Google Calendar: synchronization</field>
    <field name="model_id" ref="model_res_users"/>
    <field name="code">model._sync_all_google_calendar()</field>
    <field name="user_id" ref="base.user_root" />
    <field name="interval_number">12</field>
    <field name="interval_type">hours</field>
</record>
```

---

## L4: Conflict Resolution and Edge Cases

### Conflict Resolution: Last-Write-Wins

`_sync_google2odoo` uses `write_date` comparison: Google updates are applied only if `gevent.updated >= odoo_record.write_date`. If Odoo was updated after the Google event's last modification time, the Google update is skipped.

**Edge case:** Migration from pre-13.4 versions may have `write_date=None`. In that case, Google always wins (force update).

### Rescheduled Recurring Events

When a recurring event instance is rescheduled, its `google_id` changes. `_sync_google2odoo` detects this via `full_recurring_event_id()` and cancels the old Odoo event before applying the new one.

### All-Day Recurrence Edge Case

When creating an all-day recurrent event, the first occurrence is wrongly synced as a single event. `_handle_allday_recurrences_edge_case()` sets `need_sync=False` on such events when `forbid_sync=True` (i.e., when all events in the batch are already skipping sync because they belong to a recurrence).

### Odoo → Google (Organizer Not Synced)

When the event's `user_id` does not have a Google token, events are still synced but:
- `extendedProperties.shared.{dbname}_owner_id` stores the real owner user ID
- Only basic fields are sent (id, summary, attendees, start, end, reminders) — avoids 403 errors from Google's sharing restrictions

### Deletion Handling

When `unlink()` is called on a synced event:
1. If `archive_on_error` context AND active field exists: archive instead (archive = cancel on Google)
2. Otherwise: call `action_archive()` which triggers Google deletion and `_cancel()` (removes google_id, then unlinks)

### `sendUpdates` Control

`send_updates` context key (True by default) controls whether Google sends email notifications to attendees on changes. Set to False for mass operations to avoid spamming.

---

## Configuration

| ICP Parameter | Default | Purpose |
|---------------|---------|---------|
| `google_calendar_client_id` | — | OAuth2 Client ID |
| `google_calendar_client_secret` | — | OAuth2 Client Secret |
| `google_calendar_sync_paused` | False | Global sync pause flag |
| `google_calendar.sync.range_days` | 365 | Sync window (past and future days) |

---

## Related Models

| Model | Module | Role |
|-------|--------|------|
| `calendar.event` | `calendar` | Base calendar event (extended by google_calendar) |
| `calendar.recurrence` | `calendar` | Base recurrence (extended by google_calendar) |
| `calendar.attendee` | `calendar` | Base attendee (extended by google_calendar) |
| `calendar.alarm` | `calendar` | Alarm/reminder definitions |
| `res.users` | `base` | User (extended with google_* fields) |
| `res.users.settings` | `base` | Per-user settings (stores google tokens) |
| `google.service` | `google_account` | OAuth2 token management |
| `ir.config_parameter` | `base` | System-wide configuration |