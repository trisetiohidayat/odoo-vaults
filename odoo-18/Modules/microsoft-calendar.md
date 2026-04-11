---
Module: microsoft_calendar
Version: Odoo 18
Type: Integration
Tags: [microsoft, outlook, calendar, sync, microsoft-graph, oauth2, two-way-sync, teams]
---

# microsoft_calendar — Microsoft Outlook Calendar Synchronization

## Overview

The `microsoft_calendar` module provides **bidirectional synchronization** between Odoo `calendar.event` / `calendar.recurrence` records and Microsoft Outlook Calendar via the **Microsoft Graph API** (not EWS). It extends `calendar.event` with Microsoft-specific fields, the `microsoft.calendar.sync` mixin, and a full sync engine driven by a 12-hour cron job.

Architecture is parallel to `google_calendar` but uses Microsoft Graph API v1.0 endpoints and a different event identity model (local `microsoft_id` + universal `ms_universal_event_id` / iCalUId).

**Depends:** `microsoft_account`, `calendar`
**Category:** Productivity
**License:** LGPL-3
**API:** Microsoft Graph API v1.0
**Post-init hook:** `init_initiating_microsoft_uuid` — sets a database UUID for the Outlook tenant

---

## Architecture Overview

```
microsoft.calendar.account.reset (TransientModel — reset_account.py)

microsoft.calendar.sync (AbstractModel mixin — microsoft_sync.py)
    ├─ microsoft_id (local event ID in a specific Outlook calendar)
    ├─ ms_universal_event_id (iCalUId — unique across all calendars)
    ├─ need_sync_m (Boolean)
    ├─ _sync_odoo2microsoft() — Odoo → Microsoft (after-commit)
    ├─ _sync_microsoft2odoo() — Microsoft → Odoo (batch)
    ├─ _microsoft_insert(), _microsoft_patch(), _microsoft_delete() — API calls
    ├─ _sync_recurrence_microsoft2odoo() — handles recurrence master + occurrences
    └─ _get_microsoft_service() — returns MicrosoftCalendarService

calendar.event  (inherits microsoft.calendar.sync)
    ├─ microsoft_recurrence_master_id (stores seriesMasterId from Outlook)
    ├─ _get_microsoft_synced_fields() — set of fields triggering resync
    ├─ _microsoft_to_odoo_values(), _microsoft_values() — format conversion
    ├─ _check_microsoft_sync_status(), _check_recurrence_overlapping()
    └─ _forbid_recurrence_creation() / _forbid_recurrence_update() — blocks Odoo recurrence editing

calendar.recurrence  (inherits microsoft.calendar.sync)
    ├─ need_sync_m (Boolean, default=False — only syncs when applied)
    ├─ _microsoft_to_odoo_values() — recurrence rule conversion
    ├─ _write_from_microsoft() — handle time field changes, re-creates recurrence
    └─ _microsoft_values() — delegates to base_event._microsoft_values(type='seriesMaster')

calendar.attendee  (extends base)
    └─ do_tentative(), do_accept(), do_decline() → _microsoft_sync_event()

res.users  (extends base)
    ├─ microsoft_calendar_sync_token, microsoft_synchronization_stopped, microsoft_last_sync_date
    ├─ _get_microsoft_calendar_token() — auto-refreshes token
    ├─ _refresh_microsoft_calendar_token() — OAuth2 refresh
    ├─ _sync_microsoft_calendar() — main sync orchestrator
    └─ _sync_all_microsoft_calendar() — cron entry point (12h)

res.users.settings  (inherits base)
    ├─ microsoft_calendar_sync_token (next sync token from Graph API deltaLink)
    ├─ microsoft_synchronization_stopped
    └─ microsoft_last_sync_date

res.config.settings  (extends base)
    ├─ cal_microsoft_client_id (config_parameter)
    └─ cal_microsoft_client_secret (config_parameter)

MicrosoftCalendarService  (utils/microsoft_calendar.py)
    ├─ get_events(sync_token?, token) — delta sync via /me/calendarView/delta
    ├─ _get_occurrence_details(serieMasterId, token) — fetch all recurrence instances
    ├─ insert(values, token) — POST /me/calendar/events
    ├─ patch(event_id, values, token) — PATCH
    ├─ delete(event_id, token) — DELETE
    └─ answer(event_id, answer, params, token) — POST /me/calendar/events/{id}/{accept|tentativelyAccept|decline}

MicrosoftEvent  (utils/microsoft_event.py)
    ├─ id (local to calendar), iCalUId (universal)
    ├─ type: 'singleInstance' | 'seriesMaster' | 'occurrence' | 'exception'
    ├─ is_recurrence(), is_recurrent(), is_cancelled(), is_recurrence_outlier()
    ├─ get_recurrence() — converts Outlook pattern/range to Odoo rrule dict
    ├─ match_with_odoo_events(env) — maps Outlook events to Odoo by iCalUId then id
    └─ owner_id(env) — resolves organizer from isOrganizer flag or email

microsoft.service  (from microsoft_account)
    └─ OAuth2 token management, _refresh_microsoft_token(), _get_microsoft_client_id()
```

---

## Model: `microsoft.calendar.sync` (AbstractModel Mixin)

**File:** `addons/microsoft_calendar/models/microsoft_sync.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `microsoft_id` | `Char` | Event ID specific to the user's Outlook calendar. Changes if the event is moved to a different calendar |
| `ms_universal_event_id` | `Char` | iCalUId — globally unique across all Outlook calendars. Stable even if the event moves between calendars |
| `need_sync_m` | `Boolean` | True by default. Set False after successful Microsoft sync. Set True when synced fields change |
| `active` | `Boolean` | Default True. Inactive events are not synced |

### `write()` Hook

```python
def write(self, vals):
    fields_to_sync = [x for x in vals if x in self._get_microsoft_synced_fields()]
    if fields_to_sync and 'need_sync_m' not in vals and self.env.user._get_microsoft_sync_status() == "sync_active":
        vals['need_sync_m'] = True
    result = super().write(vals)
    if self.env.user._get_microsoft_sync_status() != "sync_paused":
        for record in self:
            if record.need_sync_m and record.microsoft_id:
                if not vals.get('active', True):
                    record._microsoft_delete(record._get_organizer(), record.microsoft_id, timeout=3)
                elif fields_to_sync:
                    values = record._microsoft_values(fields_to_sync)
                    if not values:
                        continue
                    record._microsoft_patch(record._get_organizer(), record.microsoft_id, values, timeout=3)
    return result
```

Unlike Google Calendar (which uses a single `_google_values()` returning all fields), Microsoft sync uses a **selective sync** pattern: `_microsoft_values(fields_to_sync)` receives the list of changed fields and returns only the relevant Microsoft API fields to update.

### `@after_commit` Decorator

All Microsoft API calls are deferred to post-commit, same pattern as Google Calendar.

### `_sync_odoo2microsoft()`

```python
def _sync_odoo2microsoft(self):
    if not self:
        return
    records_to_sync = self.filtered(self._active_name)
    cancelled_records = self - records_to_sync
    records_to_sync._ensure_attendees_have_email()
    updated_records = records_to_sync._get_synced_events()  # those with ms_universal_event_id
    new_records = records_to_sync - updated_records

    for record in cancelled_records._get_synced_events():
        record._microsoft_delete(record._get_organizer(), record.microsoft_id)
    for record in new_records:
        values = record._microsoft_values(self._get_microsoft_synced_fields())
        sender_user = record._get_event_user_m()
        if record._is_microsoft_insertion_blocked(sender_user):
            continue
        if isinstance(values, dict):
            record._microsoft_insert(values)
        else:  # recurrence: returns list of values for base_event + occurrences
            for value in values:
                record._microsoft_insert(value)
    for record in updated_records.filtered('need_sync_m'):
        values = record._microsoft_values(self._get_microsoft_synced_fields())
        if not values:
            continue
        record._microsoft_patch(record._get_organizer(), record.microsoft_id, values)
```

Note: Non-recurrence events sync as a single dict. Recurrence events return a list of dicts (base event + each occurrence) — each occurrence is inserted separately.

### `_sync_microsoft2odoo()`

```python
@api.model
def _sync_microsoft2odoo(self, microsoft_events: MicrosoftEvent):
    existing = microsoft_events.match_with_odoo_events(self.env)
    cancelled = microsoft_events.cancelled()
    new = microsoft_events - existing - cancelled
    new_recurrence = new.filter(lambda e: e.is_recurrent())

    # Create new non-recurrence events
    odoo_values = [dict(self._microsoft_to_odoo_values(e, with_ids=True), need_sync_m=False)
                   for e in (new - new_recurrence)]
    synced_events = self.with_context(dont_notify=True)._create_from_microsoft(new, odoo_values)

    # Create/update recurrences
    synced_recurrences, updated_events = self._sync_recurrence_microsoft2odoo(existing, new_recurrence)
    synced_events |= updated_events

    # Remove cancelled events and recurrences
    cancelled_recurrences = self.env['calendar.recurrence'].search([
        '|',
        ('ms_universal_event_id', 'in', cancelled.uids),
        ('microsoft_id', 'in', cancelled.ids),
    ])
    cancelled_events = self.browse([e.odoo_id(self.env) for e in cancelled
                                     if e.id not in [r.microsoft_id for r in cancelled_recurrences]])
    cancelled_recurrences._cancel_microsoft()
    cancelled_events = cancelled_events.exists()
    cancelled_events._cancel_microsoft()
    synced_recurrences |= cancelled_recurrences
    synced_events |= cancelled_events | cancelled_recurrences.calendar_event_ids

    # Update existing records with last-write-wins: Microsoft wins if updated >= Odoo write_date
    for mevent in (existing - cancelled).filter(lambda e: e.lastModifiedDateTime):
        odoo_event = self.browse(mevent.odoo_id(self.env)).exists()
        if odoo_event:
            ms_event_updated_time = parse(mevent.lastModifiedDateTime)
            # Check lower bound for old events to avoid spam
            if ms_event_updated_time >= odoo_event_updated_time and old_event_update_condition:
                vals = dict(odoo_event._microsoft_to_odoo_values(mevent), need_sync_m=False)
                odoo_event.with_context(dont_notify=True)._write_from_microsoft(mevent, vals)
                # For recurrences, also update sub-events
                if odoo_event._name == 'calendar.recurrence':
                    update_events = odoo_event._update_microsoft_recurrence(mevent, microsoft_events)
                    synced_recurrences |= odoo_event
                    synced_events |= update_events
                else:
                    synced_events |= odoo_event

    return synced_events, synced_recurrences
```

---

## Model: `calendar.event` (Microsoft Extension)

**File:** `addons/microsoft_calendar/models/calendar.py`

`Meeting` class: `_name = 'calendar.event'`, `_inherit = ['calendar.event', 'microsoft.calendar.sync']`

### Fields Added by Microsoft Extension

| Field | Type | Description |
|-------|------|-------------|
| `microsoft_recurrence_master_id` | `Char` | Outlook `seriesMasterId` for events that are part of a recurrence |

### Synced Fields (`_get_microsoft_synced_fields`)

```python
@api.model
def _get_microsoft_synced_fields(self):
    return {'name', 'description', 'allday', 'start', 'date_end', 'stop',
            'user_id', 'privacy',
            'attendee_ids', 'alarm_ids', 'location', 'show_as', 'active', 'videocall_location'}
```

> **Note:** `recurrency` is NOT in the synced fields set. Recurrence rules are synced through `calendar.recurrence`. The `user_id` field IS synced (organizer/owner changes sync to Outlook).

### Microsoft → Odoo Values (`_microsoft_to_odoo_values`)

Converts an Outlook event to Odoo field values:

- `active`: False if cancelled
- `name`: Outlook `subject` or `(No title)`
- `description`: Outlook `body.content` (HTML)
- `location`: `location.displayName`
- `user_id`: Resolved via `owner_id(env)` — if `isOrganizer=True`, returns `env.user`; otherwise searches by organizer email
- `privacy` → `sensitivity`: Odoo `'public'/'private'/'confidential'` ↔ Outlook `'normal'/'private'/'confidential'`
- `allday`: `isAllDay` boolean
- `start`/`stop`: Parsed from `dateTime` with `timeZone` offset conversion via `pytz`
- `show_as`: `'free'` ↔ `'busy'` ↔ Outlook `showAs`
- `recurrency`: `microsoft_event.is_recurrent()`
- `videocall_location`: Auto-extracted from:
  1. `onlineMeeting.joinUrl` if `isOnlineMeeting=True`
  2. Location URL matching `https://teams.microsoft.com` pattern
- `alarm_ids`: Created from `reminderMinutesBeforeStart` (notification type only)
- `microsoft_id`: Outlook event id
- `ms_universal_event_id`: Outlook iCalUId
- `microsoft_recurrence_master_id`: Outlook seriesMasterId

For recurrence **exceptions** (outliers): `follow_recurrence = not is_recurrence_outlier()` — exceptions set `follow_recurrence=False`.

### Odoo → Microsoft Values (`_microsoft_values`)

Fields to values mapping:

| Odoo field | Microsoft field | Notes |
|------------|---------------|-------|
| `name` | `subject` | |
| `description` | `body.content` (HTML) | `_get_customer_description()` |
| `allday`/`start`/`stop` | `start.dateTime`/`end.dateTime` (UTC), `isAllDay` | All times in Europe/London timezone per spec; end date for allday is +1 day |
| `location` | `location.displayName` | |
| `videocall_location` missing | `isOnlineMeeting: True`, `onlineMeetingProvider: teamsForBusiness` | Auto-creates Teams meeting |
| `alarm_ids` | `isReminderOn`, `reminderMinutesBeforeStart` | |
| `user_id` | `organizer.emailAddress`, `isOrganizer` | |
| `attendee_ids` | `attendees[].emailAddress`, `attendees[].status.response` | Filters out organizer |
| `privacy`/`show_as` | `sensitivity`, `showAs` | Default privacy from `user_id.calendar_default_privacy` |
| `active=False` | `isCancelled: True` | Cancellation is a PATCH not DELETE |

For **seriesMaster** events (recurrence base):
```python
if values.get('type') == 'seriesMaster':
    recurrence = self.recurrence_id
    # Converts Odoo rrule to Outlook pattern/range:
    # - interval, rrule_type, month_by, day/byday
    # - end_type: 'count'/'forever'/'end_date'
    # - MAX_RECURRENT_EVENT = 720 (hard limit in Microsoft API)
```

### `_check_microsoft_sync_status()`

```python
def _check_microsoft_sync_status(self):
    outlook_connected = self.env.user._get_microsoft_calendar_token()
    return outlook_connected and self.env.user.sudo().microsoft_synchronization_stopped is False
```

Returns True only if both conditions are met:
1. User has a valid Microsoft access token
2. User has not manually stopped sync

### Recurrence Blocking

Unlike Google Calendar (which silently syncs via recurrence), Microsoft Calendar **forbids** creating or updating recurrences from Odoo:

```python
def _forbid_recurrence_creation(self):
    raise UserError(_("Due to an Outlook Calendar limitation, recurrent events must be created directly in Outlook Calendar."))

def _forbid_recurrence_update(self):
    raise UserError(_("Due to an Outlook Calendar limitation, recurrence updates must be done directly in Outlook Calendar."))
```

These are enforced in `create()` and `write()` when `_check_microsoft_sync_status()` returns True.

**Rationale:** Microsoft's recurring event model is complex (pattern/range API vs iCal RRULE) and Microsoft restricts who can send recurrence update notifications. Forcing users to manage recurrences from Outlook avoids spam and API limitations.

### `_check_recurrence_overlapping()`

Prevents an occurrence from being moved to a date that would violate Outlook's recurrence ordering constraints (an occurrence cannot move to or before the previous occurrence, or to or after the next occurrence):

```python
def _check_recurrence_overlapping(self, new_start):
    before_count = len(self.recurrence_id.calendar_event_ids.filtered(
        lambda e: e.start.date() < self.start.date() and e != self
    ))
    after_count = len(self.recurrence_id.calendar_event_ids.filtered(
        lambda e: e.start.date() < parse(new_start).date() and e != self
    ))
    if before_count != after_count:
        raise UserError(_("Outlook limitation: in a recurrence, an event cannot be moved to or before the day of the previous event..."))
```

### Organizer Change Handling

When `user_id` is changed in `write()`:

```python
if event.user_id.id != values['user_id'] and not change_from_microsoft:
    sender_user, partner_ids = event._get_organizer_user_change_info(values)
    partner_included = sender_user.partner_id in event.attendee_ids.partner_id
    event._check_organizer_validation(sender_user, partner_included)
    if event.microsoft_id:
        event._recreate_event_different_organizer(values, sender_user)
        deactivated_events_ids.append(event.id)
```

Organizer change validation:
- If the new organizer is NOT synced: error — "organizer must have Odoo Calendar synced with Outlook"
- If the new organizer IS synced but not an attendee: error — "must add organizer as attendee first"

`_recreate_event_different_organizer()`: copies the event, deletes the original from Outlook, creates a new event under the new organizer.

### `_ensure_attendees_have_email()`

Sync fails if any attendee in the synced event has no email address. Validates all events before syncing and raises `ValidationError` with up to 50 affected event names.

---

## Model: `calendar.recurrence` (Microsoft Extension)

**File:** `addons/microsoft_calendar/models/calendar_recurrence_rule.py`

`_name = 'calendar.recurrence'`, `_inherit = ['calendar.recurrence', 'microsoft.calendar.sync']`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `need_sync_m` | `Boolean` | **Default False** — only set True when the recurrence is explicitly applied, not on every field change |

### Key Methods

#### `_apply_recurrence()`

When a single event becomes a recurrence:
1. For each synced event with `ms_universal_event_id` but no `recurrence_id.ms_universal_event_id`: calls `_microsoft_delete()` on Outlook
2. Creates an inactive copy of each deleted event (preserves original `microsoft_id` for cleanup)
3. Sets `ms_universal_event_id = False` on the original event
4. Sets `need_sync_m = False` on all events (recurrence handles sync)

#### `_compute_rrule()` / `_inverse_rrule()`

Both set `need_sync_m = False` to avoid re-syncing after the Odoo-side rule serialization (updates come from Outlook, not from Odoo).

#### `_write_from_microsoft(vals)`

Handles three scenarios when Outlook updates a recurrence:
1. **Base event time fields changed**: Archives old events, recreates recurrence with new base values
2. **Non-time fields changed**: Writes only non-time fields (shared across all events), skips time fields
3. **Rule (rrule) changed**: Applies new recurrence, detaches events no longer matching

#### `_microsoft_values(fields_to_sync)`

```python
def _microsoft_values(self, fields_to_sync):
    return self.base_event_id._microsoft_values(fields_to_sync, initial_values={'type': 'seriesMaster'})
```

Recurrence syncs by sending the base event's values with `type='seriesMaster'` — Outlook's recurrence API operates on the seriesMaster.

#### `_get_microsoft_sync_domain()`

```python
def _get_microsoft_sync_domain(self):
    # Do not sync Odoo recurrences with Outlook Calendar anymore.
    domain = expression.FALSE_DOMAIN
    return self._extend_microsoft_domain(domain)
```

Returns `FALSE_DOMAIN` — meaning **Odoo does not push recurrence creations to Outlook**. Recurrences are only created in Odoo when syncing FROM Outlook.

---

## Model: `res.users.settings` (Microsoft Extension)

**File:** `addons/microsoft_calendar/models/res_users_settings.py`

### Fields

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `microsoft_calendar_sync_token` | `Char` | `base.group_system` | Next delta link token from Microsoft Graph (stored in settings, not on user) |
| `microsoft_synchronization_stopped` | `Boolean` | `base.group_system` | User manually stopped sync |
| `microsoft_last_sync_date` | `Datetime` | `base.group_system` | Last successful sync timestamp (used to filter events by write_date) |

> **Note:** Microsoft stores OAuth tokens (`microsoft_calendar_token`, `microsoft_calendar_rtoken`, `microsoft_calendar_token_validity`) on the `res.users` record directly (not in settings), unlike Google which uses `res.users.settings`. These are related from the user's sudo record. See `res_users.py` for full token field list.

---

## Model: `res.users` (Microsoft Extension)

**File:** `addons/microsoft_calendar/models/res_users.py`

### Fields (Related to Settings)

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `microsoft_calendar_sync_token` | `Char` | `base.group_system` | Related to settings — next sync token |
| `microsoft_synchronization_stopped` | `Boolean` | `base.group_system` | Manual stop flag |
| `microsoft_last_sync_date` | `Datetime` | `base.group_system` | Last sync timestamp |

### Additional Token Fields (Direct on res.users, not settings)

The user's `sudo().microsoft_calendar_rtoken`, `microsoft_calendar_token`, `microsoft_calendar_token_validity` are stored directly on `res.users` (not via settings). These are accessed via `sudo()` in token methods.

### `_get_microsoft_calendar_token()`

```python
def _get_microsoft_calendar_token(self):
    if not self:
        return None
    self.ensure_one()
    if self.sudo().microsoft_calendar_rtoken and not self._is_microsoft_calendar_valid():
        self._refresh_microsoft_calendar_token()
    return self.sudo().microsoft_calendar_token
```

### `_refresh_microsoft_calendar_token()`

On HTTP 400/401 (invalid grant):
1. Rollback and clear: `microsoft_calendar_rtoken=False`, `microsoft_calendar_token=False`, `microsoft_calendar_token_validity=False`
2. Clear sync token: `res_users_settings_id.microsoft_calendar_sync_token=False`
3. Commit the cleanup
4. Raise `UserError` with instructions to re-authorize

### `_sync_microsoft_calendar()`

Orchestrator (per-user):

```python
def _sync_microsoft_calendar(self):
    self.ensure_one()
    self.sudo().microsoft_last_sync_date = fields.datetime.now()
    if self._get_microsoft_sync_status() != "sync_active":
        return False

    self._set_ICP_first_synchronization_date(fields.Datetime.now())

    calendar_service = self.env["calendar.event"]._get_microsoft_service()
    full_sync = not bool(self.sudo().microsoft_calendar_sync_token)
    with microsoft_calendar_token(self) as token:
        try:
            events, next_sync_token = calendar_service.get_events(self.sudo().microsoft_calendar_sync_token, token=token)
        except InvalidSyncToken:
            events, next_sync_token = calendar_service.get_events(token=token)
            full_sync = True

    self.res_users_settings_id.sudo().microsoft_calendar_sync_token = next_sync_token

    # Microsoft → Odoo
    synced_events, synced_recurrences = self.env['calendar.event']._sync_microsoft2odoo(events) if events else (empty, empty)

    # Odoo → Microsoft
    recurrences = self.env['calendar.recurrence']._get_microsoft_records_to_sync(full_sync=full_sync)
    recurrences -= synced_recurrences
    recurrences._sync_odoo2microsoft()
    synced_events |= recurrences.calendar_event_ids

    events = self.env['calendar.event']._get_microsoft_records_to_sync(full_sync=full_sync)
    (events - synced_events)._sync_odoo2microsoft()

    self.sudo().microsoft_last_sync_date = fields.datetime.now()
    return bool(events | synced_events) or bool(recurrences | synced_recurrences)
```

### First Synchronization Date

`_set_ICP_first_synchronization_date()` stores a system-wide ICP `microsoft_calendar.sync.first_synchronization_date` on the first sync (per database, not per user). This prevents syncing pre-existing Odoo events to Microsoft (which would spam attendees with invitations).

### `_sync_all_microsoft_calendar()` (Cron)

Runs every 12 hours for all users with `microsoft_calendar_rtoken` and not stopped.

---

## Model: `calendar.attendee` (Microsoft Extension)

**File:** `addons/microsoft_calendar/models/calendar_attendee.py`

When an attendee responds (accept/tentative/decline) via Odoo:
1. Filters events that are synced and where the current user is an attendee (not the organizer)
2. For synced events: calls `_microsoft_attendee_answer()` with the answer type

```python
def _microsoft_sync_event(self, answer):
    params = {"comment": "", "sendResponse": True}
    linked_events = self.event_id._get_synced_events()
    for event in linked_events:
        if event._check_microsoft_sync_status() and self.env.user != event.user_id and self.env.user.partner_id in event.partner_ids:
            if event.recurrency:
                event._forbid_recurrence_update()
            event._microsoft_attendee_answer(answer, params)
```

### `_microsoft_attendee_answer(answer, params)`

Uses `ms_universal_event_id` (iCalUId) to fetch the event's local ID for the current user (since the local ID differs per attendee in shared calendars), then sends the answer via Microsoft Graph API.

---

## Model: `microsoft.calendar.account.reset` (TransientModel)

**File:** `addons/microsoft_calendar/wizard/reset_account.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `Many2one(res.users)` | User whose Microsoft account to reset |
| `delete_policy` | `Selection` | `dont_delete` / `delete_microsoft` / `delete_odoo` / `delete_both` |
| `sync_policy` | `Selection` | `new` (skip existing) / `all` (resync all) |

### `reset_account()` Logic

1. Get non-recurring synced events (recurrences not deleted due to spam prevention)
2. If `delete_microsoft`: call `_microsoft_delete()` on each event
3. If `sync_policy == 'all'`: clear `microsoft_id`, set `need_sync_m = True`
4. If `delete_odoo`/`delete_both`: clear `microsoft_id`, unlink events
5. Commit (so token cleanup happens with valid token)
6. Clear auth tokens and sync state

---

## `MicrosoftCalendarService` (Utility)

**File:** `addons/microsoft_calendar/utils/microsoft_calendar.py`

### API Endpoints Used

| Method | Endpoint | Description |
|--------|----------|-------------|
| `_get_events_delta` | `GET /v1.0/me/calendarView/delta` | Delta sync — returns changes since last sync token |
| `_get_occurrence_details` | `GET /v1.0/me/events/{serieMasterId}/instances` | Fetches all occurrences of a recurrence (gets iCalUId for each) |
| `get_events` | Combines above | Main entry point — delta + per-master occurrence details |
| `insert` | `POST /v1.0/me/calendar/events` | Creates event, returns `(event_id, iCalUId)` |
| `patch` | `PATCH /v1.0/me/calendar/events/{id}` | Updates event |
| `delete` | `DELETE /v1.0/me/calendar/events/{id}` | Removes event |
| `answer` | `POST /v1.0/me/calendar/events/{id}/{accept|tentativelyAccept|decline}` | Attendee response |
| `_get_single_event` | `GET /v1.0/me/events?$filter=iCalUId eq '...'` | Lookup by iCalUId |

### Delta Sync Token Logic

```python
def get_events(self, sync_token=None, token=None, timeout=TIMEOUT):
    events, next_sync_token = self._get_events_delta(sync_token=sync_token, token=token, timeout=timeout)
    # For every seriesMaster, fetch all its occurrences to get iCalUId
    for master in filter(lambda e: e.type == 'seriesMaster', events):
        events |= self._get_occurrence_details(master.id, token=token, timeout=timeout)
    return events, next_sync_token
```

On HTTP 410 with `fullSyncRequired` / `SyncStateNotFound`: falls back to full sync (re-fetches last 365 days).

### Pagination

Uses `@odata.nextLink` to iterate through all pages. Uses `Prefer: outlook.body-content-type="html", odata.maxpagesize=50` headers for efficient fetching.

### `insert()` — Returns Both IDs

```python
def insert(self, values, token=None, timeout=TIMEOUT):
    url = "/v1.0/me/calendar/events"
    headers = {'Content-type': 'application/json', 'Authorization': 'Bearer %s' % token}
    _dummy, data, _dummy = self.microsoft_service._do_request(url, json.dumps(values), headers, method='POST', timeout=timeout)
    return data['id'], data['iCalUId']
```

Returns a tuple: `(local_event_id, iCalUId)`.

### OAuth2 Scope

```python
def _get_calendar_scope(self):
    return 'offline_access openid Calendars.ReadWrite'
```

---

## `MicrosoftEvent` (Utility Class)

**File:** `addons/microsoft_calendar/utils/microsoft_event.py`

A set-like immutable wrapper for Microsoft event dicts, similar to `GoogleEvent`.

### Event Type System

Microsoft events have explicit `type` field unlike Google:
- `'singleInstance'` — regular event
- `'seriesMaster'` — recurrence definition
- `'occurrence'` — regular instance of a recurrence
- `'exception'` — modified instance of a recurrence

### iCalUId vs Microsoft ID

| Field | Google | Microsoft |
|-------|--------|-----------|
| Local ID | `google_id` | `microsoft_id` (changes if event moves calendar) |
| Universal ID | `google_id` is also the lookup key | `ms_universal_event_id` = `iCalUId` (stable across calendars) |

The Microsoft implementation uses both IDs: `microsoft_id` for API calls, `ms_universal_event_id` for matching Odoo records.

### Matching to Odoo (`_load_odoo_ids_from_db`)

Priority:
1. Match by `ms_universal_event_id` (iCalUId) — most reliable
2. Match by `microsoft_id` (local id) — fallback
3. When matched by local ID, also write `ms_universal_event_id` on the Odoo record for future reliability

### `get_recurrence()` — Odoo rrule Conversion

```python
def get_recurrence(self):
    # pattern['type']: 'absoluteMonthly'/'relativeMonthly'/'absoluteYearly'/'relativeYearly'/'daily'/'weekly'
    # range['type']: 'endDate'/'noEnd'/'numbered'
    # pattern['index']: 'first'/'second'/'third'/'fourth'/'last' → byday '1'/'2'/'3'/'4'/'-1'
    # pattern['daysOfWeek']: full weekday names → mon/tue/... prefix
    return {
        'rrule_type': type_dict.get(pattern['type']),
        'end_type': end_type_dict.get(range['type']),
        'interval': pattern['interval'],
        'count': range['numberOfOccurrences'],
        'day': pattern['dayOfMonth'],
        'byday': index_dict.get(pattern['index']),
        'until': range['endDate'],
        'month_by': month_by_dict.get(pattern['type']),
        'mon'/'tue'/...: bool in daysOfWeek,
    }
```

---

## `calendar.alarm_manager` Extension

**File:** `addons/microsoft_calendar/models/calendar_alarm_manager.py`

```python
@api.model
def _get_notify_alert_extra_conditions(self):
    base = super()._get_notify_alert_extra_conditions()
    return SQL("%s AND event.microsoft_id IS NULL", base)
```

Synced events (with `microsoft_id`) do NOT trigger Odoo internal reminders — Microsoft handles them. Non-synced events (no `microsoft_id`) still trigger Odoo alarms.

---

## HTTP Controller

**File:** `addons/microsoft_calendar/controllers/main.py`

Route: `/microsoft_calendar/sync_data` (type=json, auth=user)

Same status return pattern as Google Calendar:
- `need_config_from_admin` — Client ID not set
- `need_auth` — User hasn't authorized Odoo
- `need_refresh` / `no_new_event_from_microsoft` — sync completed
- `sync_stopped` / `sync_paused` — sync not active

---

## Cron

**File:** `addons/microsoft_calendar/data/microsoft_calendar_data.xml`

```xml
<record forcecreate="True" id="ir_cron_sync_all_cals" model="ir.cron">
    <field name="name">Outlook: synchronization</field>
    <field name="model_id" ref="model_res_users"/>
    <field name="code">model._sync_all_microsoft_calendar()</field>
    <field name="user_id" ref="base.user_root" />
    <field name="interval_number">12</field>
    <field name="interval_type">hours</field>
</record>
```

---

## L4: Microsoft Graph API vs EWS

Odoo 18 uses **Microsoft Graph API** (v1.0 endpoints), not the legacy Exchange Web Services (EWS). Graph API advantages:
- Single endpoint for all Microsoft 365 services
- OAuth2 with Microsoft identity platform (Azure AD / MSAL)
- Better rate limiting and reliability
- Unified calendar view across personal + shared calendars

### `seriesMasterId` vs RRULE

Unlike Google (which uses iCal RRULE strings), Microsoft uses a structured `pattern` + `range` object for recurrences:

**Pattern:**
```json
{
  "type": "absoluteMonthly",     // or relativeMonthly/daily/weekly/etc.
  "interval": 1,
  "daysOfWeek": ["monday", "friday"],
  "dayOfMonth": 15,
  "index": "first"               // for monthly-by-day: first/second/third/fourth/last
}
```

**Range:**
```json
{
  "type": "numbered",           // or endDate/noEnd
  "startDate": "2024-01-01",
  "numberOfOccurrences": 10,    // for numbered
  "endDate": "2024-12-31"        // for endDate
}
```

### Event Type Architecture in Microsoft

| Type | Description | Retrieved via |
|------|-------------|---------------|
| `singleInstance` | Normal one-time event | `/calendarView/delta` |
| `seriesMaster` | Recurrence definition | `/calendarView/delta` |
| `occurrence` | Instance of a recurrence | `/events/{masterId}/instances` (explicit fetch per master) |
| `exception` | Modified instance of a recurrence | `/events/{masterId}/instances` |

Odoo's sync fetches delta from `/calendarView/delta`, then explicitly fetches all occurrences for each `seriesMaster` found (to get their iCalUIds, which are not returned in delta responses).

### Token Refresh Mechanism

Same as Google: OAuth2 with refresh tokens stored on `res.users`. `_refresh_microsoft_calendar_token()` calls `microsoft.service._refresh_microsoft_token()`. On 400/401 (invalid grant), tokens are cleared and user must re-authorize.

### Sync Lower Bound (Anti-Spam)

`microsoft_calendar.sync.lower_bound_range` ICP (optional) prevents updating Odoo events that are older than N days. This avoids re-syncing ancient events that trigger constant no-op updates in Microsoft (which would spam attendees with notifications).

---

## Configuration

| ICP Parameter | Default | Purpose |
|---------------|---------|---------|
| `microsoft_calendar_client_id` | — | OAuth2 Application (client) ID |
| `microsoft_calendar_client_secret` | — | OAuth2 Client Secret |
| `microsoft_calendar_sync_paused` | False | Global sync pause |
| `microsoft_calendar.sync.range_days` | 365 | Sync window |
| `microsoft_calendar.sync.lower_bound_range` | — | Optional: skip updating events older than N days |
| `microsoft_calendar.sync.first_synchronization_date` | — | Set on first sync: prevents resyncing pre-existing Odoo events |
| `microsoft_calendar.microsoft_guid` | — | Tenant/instance GUID for Microsoft Graph API routing |

---

## Related Models

| Model | Module | Role |
|-------|--------|------|
| `calendar.event` | `calendar` | Base calendar event (extended) |
| `calendar.recurrence` | `calendar` | Base recurrence (extended) |
| `calendar.attendee` | `calendar` | Base attendee (extended) |
| `calendar.alarm` | `calendar` | Alarm definitions |
| `res.users` | `base` | User with microsoft_* fields + tokens |
| `res.users.settings` | `base` | Settings with microsoft sync token/state |
| `microsoft.service` | `microsoft_account` | OAuth2 token management |
| `ir.config_parameter` | `base` | System-wide configuration |