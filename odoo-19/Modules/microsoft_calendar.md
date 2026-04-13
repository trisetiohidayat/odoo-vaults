---
type: module
title: "Microsoft Calendar — Two-Way Odoo/Outlook Sync"
description: "Bidirectional synchronization between Odoo Calendar and Microsoft Outlook via Microsoft Graph API. Supports events, attendees, recurrences, reminders, and Teams meetings."
source_path: ~/odoo/odoo19/odoo/addons/microsoft_calendar/
tags:
  - odoo
  - odoo19
  - module
  - microsoft_calendar
  - calendar
  - outlook
  - integration
  - graph_api
related_modules:
  - calendar
  - microsoft_account
  - mail
created: 2026-04-11
version: "1.0"
---

## Quick Access

### Related Modules
- [Modules/Calendar](modules/calendar.md) — Base calendar module (dependency)
- [Core/API](core/api.md) — @api decorators used in sync logic
- [Core/Fields](core/fields.md) — Relational fields (Many2one, One2many) used for attendees

---

## Module Overview

| Property | Value |
|----------|-------|
| **Name** | Microsoft Calendar |
| **Technical Name** | `microsoft_calendar` |
| **Category** | Productivity / Integrations |
| **Summary** | Bidirectional sync between Odoo Calendar and Microsoft Outlook |
| **Depends** | `microsoft_account`, `calendar` |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Installable** | True |
| **Source** | `odoo/addons/microsoft_calendar/` |

### Description

The `microsoft_calendar` module enables **bidirectional, real-time synchronization** between Odoo Calendar and Microsoft Outlook Calendar. Events, attendees, reminders, locations, privacy settings, and recurring events are all synced via the **Microsoft Graph API v1.0**.

Formerly branded as "Outlook Calendar," the module handles all complexity of two-way sync including conflict resolution, token management, and recurrence edge cases.

---

## Architecture

### Overall Design

The module is structured around a **mixin pattern** (`microsoft.calendar.sync`) that is applied to two Odoo models:

```
calendar.event         <-- inherits --> microsoft.calendar.sync (mixin)
calendar.recurrence     <-- inherits --> microsoft.calendar.sync (mixin)
```

The mixin adds three core fields that form the sync anchor:

| Field | Type | Purpose |
|-------|------|---------|
| `microsoft_id` | Char | Organizer-specific event ID (Microsoft side) |
| `ms_universal_event_id` | Char | Global event ID (same across all Outlook calendars) |
| `need_sync_m` | Boolean | Flag: does this record need pushing to Microsoft? |

### Sync Flow Diagram

```
Odoo User creates/edits event
        |
        v
write() / create() on calendar.event
        |
        v
Fields in _get_microsoft_synced_fields() changed?
        |                    |
       YES                  NO
        |                    |
        v                    v
Set need_sync_m = True    No sync triggered
        |
        v
@after_commit hook fires
(post-transaction)
        |
        v
_microsoft_patch() or _microsoft_insert()
        |
        v
HTTP POST/PATCH to Microsoft Graph API
        |
        v
Microsoft updates Outlook
        |
        v
(next sync cycle: Microsoft -> Odoo)
        |
        v
Cron calls _sync_microsoft_calendar()
        |
        v
GET /me/calendarView/delta from Microsoft
        |
        v
_sync_microsoft2odoo() processes events
        |
        v
Odoo records created/updated/deleted
```

### Key Architectural Decisions

1. **Post-commit sync**: API calls to Microsoft happen *after* the Odoo database transaction commits. This prevents sync of rolled-back data.
2. **Universal ID for recurrence matching**: `ms_universal_event_id` (iCalUId) is used instead of `microsoft_id` for recurrence matching because the organizer-specific ID varies per user.
3. **Attendees cannot insert on behalf of organizers**: The `_is_microsoft_insertion_blocked()` check prevents attendees from creating events that appear to come from the organizer.
4. **Recurrence updates from Odoo are blocked**: Due to Outlook's spam limits on recurrence update emails, users are directed to manage recurring events in Outlook directly.

---

## Key Models

### 1. `microsoft.calendar.sync` (Abstract Mixin)

Applied to both `calendar.event` and `calendar.recurrence`. This is the core of the synchronization engine.

**Location:** `models/microsoft_sync.py`

**Fields Added:**

| Field | Type | Description |
|-------|------|-------------|
| `microsoft_id` | Char | Organizer event ID from Microsoft |
| `ms_universal_event_id` | Char | Global ID (iCalUId), constant across all calendars |
| `need_sync_m` | Boolean (default=True) | Set True when record needs pushing to Microsoft |
| `active` | Boolean (default=True) | Standard Odoo active — used to detect cancellations |

**Lifecycle Hooks:**

```python
# On CREATE
records = super().create(vals_list)
# For each record: _microsoft_insert() called via @after_commit

# On WRITE
result = super().write(vals)
# For each record with need_sync_m=True and microsoft_id set:
#   _microsoft_patch() or _microsoft_delete()

# On UNLINK
for ev in synced: ev._microsoft_delete()
return super().unlink()
```

**Core Sync Methods:**

| Method | Purpose |
|--------|---------|
| `_sync_odoo2microsoft()` | Main Odoo→Microsoft push: creates, patches, deletes |
| `_sync_microsoft2odoo()` | Main Microsoft→Odoo pull: creates, updates, removes |
| `_sync_recurrence_microsoft2odoo()` | Handles recurrence + occurrence sync |
| `_microsoft_insert()` | POST new event to Microsoft Graph |
| `_microsoft_patch()` | PATCH existing event on Microsoft |
| `_microsoft_delete()` | DELETE event from Microsoft |
| `_microsoft_attendee_answer()` | Send attendee response (accept/decline/tentative) |

**Post-Commit Pattern (`@after_commit`):**

```python
def after_commit(func):
    """Decorator that defers execution until after the current transaction commits."""
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        @self.env.cr.postcommit.add
        def called_after():
            with db_registry.cursor() as cr:
                env = api.Environment(cr, uid, context)
                func(self.with_env(env), *args, **kwargs)
    return wrapped
```

This pattern ensures that:
- Events are only synced if the Odoo transaction actually committed
- If Odoo crashes before commit, no orphaned Microsoft event is created
- If the Microsoft API call fails, the Odoo record still exists correctly

---

### 2. `calendar.event` (Extension via Mixin)

**Location:** `models/calendar.py`

**Additional Field:**

| Field | Type | Description |
|-------|------|-------------|
| `microsoft_recurrence_master_id` | Char | Microsoft seriesMasterId for recurrence exceptions |

**Fields Synced to Microsoft (`_get_microsoft_synced_fields`):**

```python
{
    'name',           # Event title
    'description',    # Body text
    'allday',        # All-day event flag
    'start',         # Start datetime
    'date_end',      # End date (for all-day)
    'stop',          # End datetime
    'user_id',       # Organizer
    'privacy',       # Sensitivity (public/private/confidential)
    'attendee_ids',  # Participant list
    'alarm_ids',     # Reminders
    'location',      # Location field
    'show_as',       # Show as (free/busy)
    'active',        # Active state (for cancellations)
    'videocall_location',  # Teams meeting URL or custom URL
}
```

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `_check_microsoft_sync_status()` | Returns True if sync is active AND Outlook connected |
| `_microsoft_values()` | Converts Odoo event → Microsoft Graph API payload |
| `_microsoft_to_odoo_values()` | Converts Microsoft Graph event → Odoo vals dict |
| `_forbid_recurrence_creation()` | Raises UserError directing user to Outlook |
| `_forbid_recurrence_update()` | Raises UserError directing user to Outlook |
| `_ensure_attendees_have_email()` | Validates all attendees have email (required for sync) |
| `_skip_send_mail_status_update()` | Prevents double emails during Microsoft sync |

**Organizer Change Handling:**

When a user changes the organizer of an event:
1. `_check_organizer_validation()` verifies the new organizer has sync active
2. `_recreate_event_different_organizer()` creates a new event under the new organizer
3. The old event is deleted from Microsoft and archived in Odoo

**Timezone Handling:**

```python
# Odoo stores datetimes in naive UTC in the database.
# When sending to Microsoft:
start = {'dateTime': pytz.utc.localize(self.start).isoformat(), 'timeZone': 'Europe/London'}
# Note: Microsoft requires all-day events to use 'Europe/London' (UTC) as timezone.
```

---

### 3. `calendar.recurrence` (Extension via Mixin)

**Location:** `models/calendar_recurrence_rule.py`

**Key Behavior: `need_sync_m` defaults to `False`**

Recurrences are synced only when they are "applied" (i.e., when the actual occurrence events are created). This avoids syncing recurrence rules that are never displayed.

**Important Override:**

```python
def _get_microsoft_sync_domain(self):
    # Do not sync Odoo recurrences to Microsoft
    # Microsoft recurrences are synced to Odoo (via calendar.event)
    return self._extend_microsoft_domain(Domain.FALSE)
```

This means **Odoo→Microsoft recurrence sync is disabled**. Only **Microsoft→Odoo** recurrence sync works. Recurrences created in Odoo are NOT pushed to Outlook due to the spam limitation on recurrence update emails.

**Recurrence Sync on Apply:**

```python
def _apply_recurrence(self, ...):
    # When an event becomes a recurrence, the old Microsoft event
    # must be deleted (the recurrence replaces it)
    for event in events._get_synced_events():
        if event.active and event.ms_universal_event_id:
            event._microsoft_delete(event.user_id, event.microsoft_id)
            # Archive the event but keep it in Odoo for recurrence
```

---

### 4. `calendar.attendee` (Extension)

**Location:** `models/calendar_attendee.py`

Attendee response status is synced back to Microsoft:

```python
class CalendarAttendee(models.Model):
    _inherit = 'calendar.attendee'

    def do_accept(self):
        res = super().do_accept()
        self._microsoft_sync_event('accept')
        return res

    def do_decline(self):
        res = super().do_decline()
        self._microsoft_sync_event('decline')
        return res

    def do_tentative(self):
        res = super().do_tentative()
        self._microsoft_sync_event('tentativelyAccept')
        return res
```

**Attendee State Mapping (Odoo ↔ Microsoft):**

| Odoo State | Microsoft State |
|-------------|----------------|
| `notresponded` | `needsAction` |
| `accepted` | `accepted` |
| `declined` | `declined` |
| `tentativelyaccepted` | `tentativelyAccepted` |
| `organizer` | `organizer` (Odoo only) |

---

### 5. `calendar.alarm_manager` (Extension)

**Location:** `models/calendar_alarm_manager.py`

**Purpose:** Suppress duplicate Odoo notifications for events sourced from Microsoft.

```python
class AlarmManager(models.AbstractModel):
    _inherit = 'calendar.alarm_manager'

    @api.model
    def _get_notify_alert_extra_conditions(self):
        base = super()._get_notify_alert_extra_conditions()
        # Only notify for events NOT from Microsoft
        return SQL("%s AND event.microsoft_id IS NULL", base)
```

This prevents users from receiving both an Odoo reminder and a Microsoft Teams reminder for the same event.

---

### 6. `res.users` (Extension)

**Location:** `models/res_users.py`

**User-Level Sync Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `microsoft_calendar_sync_token` | Char | Delta sync token for incremental syncs |
| `microsoft_synchronization_stopped` | Boolean | User has paused their personal sync |
| `microsoft_last_sync_date` | Datetime | Timestamp of last successful sync |

All three fields are stored in `res.users.settings` (not directly on `res.users`) via a `related` field with `groups='base.group_system'` access restriction.

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `_microsoft_calendar_authenticated()` | Check if user has a valid refresh token |
| `_get_microsoft_calendar_token()` | Get current access token (auto-refreshes if expired) |
| `_sync_microsoft_calendar()` | Main sync orchestrator (called by cron or UI) |
| `_sync_all_microsoft_calendar()` | Cron method — syncs all active users |
| `stop_microsoft_synchronization()` | Pause user's sync |
| `restart_microsoft_synchronization()` | Resume user's sync |

**Sync Orchestrator (`_sync_microsoft_calendar`):**

```python
def _sync_microsoft_calendar(self):
    # Step 1: Determine full vs delta sync
    full_sync = not bool(self.sudo().microsoft_calendar_sync_token)

    # Step 2: Microsoft -> Odoo
    events, next_token = calendar_service.get_events(current_sync_token)
    synced_events, synced_recurrences = calendar.event._sync_microsoft2odoo(events)
    settings.microsoft_calendar_sync_token = next_token

    # Step 3: Odoo -> Microsoft (recurrences, if any)
    recurrences = calendar.recurrence._get_microsoft_records_to_sync(full_sync=full_sync)
    recurrences -= synced_recurrences
    recurrences._sync_odoo2microsoft()

    # Step 4: Odoo -> Microsoft (events)
    events = calendar.event._get_microsoft_records_to_sync(full_sync=full_sync)
    (events - synced_events)._sync_odoo2microsoft()
```

**Important:** The `full_sync` variable gates what Odoo records are pushed to Microsoft:
- `full_sync=False` (delta sync): Only records with `need_sync_m=True` that were created/modified after the `first_synchronization_date` ICP are pushed
- `full_sync=True` (first sync or re-sync): All records with `need_sync_m=True` are pushed, regardless of creation date

---

### 7. `res.users.settings` (Extension)

**Location:** `models/res_users_settings.py`

Stores per-user Microsoft tokens and sync metadata:

```python
class ResUsersSettings(models.Model):
    _inherit = "res.users.settings"

    microsoft_calendar_sync_token = fields.Char(...)  # Delta token
    microsoft_synchronization_stopped = fields.Boolean(...)  # Pause flag
    microsoft_last_sync_date = fields.Datetime(...)  # Last sync time
```

These fields are blacklisted from web client exposure via `_get_fields_blacklist()`.

---

## Microsoft Calendar Service (`utils/microsoft_calendar.py`)

Wraps the Microsoft Graph REST API.

**API Endpoints Used:**

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `get_events()` | `GET /me/calendarView/delta` | Incremental sync of changed events |
| `insert()` | `POST /me/calendar/events` | Create new event |
| `patch()` | `PATCH /me/calendar/events/{id}` | Update event |
| `delete()` | `DELETE /me/calendar/events/{id}` | Delete event |
| `answer()` | `POST /me/calendar/events/{id}/{accept/decline/tentativelyAccept}` | Attendee response |
| `_get_single_event()` | `GET /me/events?$filter=iCalUId eq '{uid}'` | Find event by universal ID |

**Pagination:**

The `get_events` method automatically follows `@odata.nextLink` pagination, fetching all pages before returning. The `Prefer: odata.maxpagesize=50` header limits each page to 50 events. All pages are collected before returning, so a calendar with thousands of changed events in a single sync cycle results in multiple sequential API calls to follow each `nextLink`.

**Pagination Flow:**

```
Page 1: GET /me/calendarView/delta?$deltatoken=...
  Response: { value: [...50 events...], @odata.nextLink: url2 }
        |
        v
Page 2: GET url2
  Response: { value: [...50 events...], @odata.nextLink: url3 }
        |
        v
Page N: GET urlN
  Response: { value: [...last events...], @odata.deltaLink: url_with_token }
        |
        v
Extract $deltatoken from @odata.deltaLink
Return all events + next_sync_token
```

---

## MicrosoftEvent Helper (`utils/microsoft_event.py`)

A recordset-like class wrapping Microsoft Graph event dictionaries:

```python
class MicrosoftEvent(abc.Set):
    def __init__(self, iterable=()):
        # Wraps dicts from Microsoft API
        self._events = ReadonlyDict({item.get('id'): item for item in iterable})

    def is_recurrence(self): ...
    def is_cancelled(self): ...
    def is_recurrent(self): ...
    def match_with_odoo_events(self, env): ...
```

Key behavior: Events have two IDs:
- **`id`**: Organizer-specific (differs per user)
- **`iCalUId`**: Universal (same across all calendars)

Recurrence matching uses `iCalUId` as the authoritative ID.

**`match_with_odoo_events()` Matching Strategy:**

```
1. For recurrence candidates (seriesMaster or deleted):
   → Query calendar.recurrence on (ms_universal_event_id OR microsoft_id)

2. For event candidates (non-recurrence):
   → Query calendar.event on (ms_universal_event_id OR microsoft_id)

3. Two-pass matching per candidate type:
   Pass A: Match by iCalUId (universal) — preferred
   Pass B: Match by microsoft_id (organizer-specific) — fallback
           Also backfills ms_universal_event_id on Odoo record
```

This two-pass strategy handles the case where an Odoo record has a `microsoft_id` but no `ms_universal_event_id` (e.g., from older sync data), and ensures the universal ID is populated for all future sync operations.

---

## Synchronization Lifecycle

### 1. User Creates Event in Odoo

```
calendar.event.create(vals)
        |
        v
microsoft.calendar.sync.create() [mixin]
        |
        v
@after_commit: _microsoft_insert()
        |
        v
POST /me/calendar/events
        |
        v
Response: { id, iCalUId }
        |
        v
write({ microsoft_id: id, ms_universal_event_id: iCalUId, need_sync_m: False })
```

### 2. User Updates Event in Odoo

```
calendar.event.write({ name: "New Title" })
        |
        v
Fields in _get_microsoft_synced_fields()?
        |
        v
Set need_sync_m = True
        |
        v
@after_commit: _microsoft_patch()
        |
        v
PATCH /me/calendar/events/{microsoft_id}
        |
        v
Response: 200 OK
        |
        v
write({ need_sync_m: False })
```

### 3. Microsoft Updates Event (Pull)

```
Cron: _sync_all_microsoft_calendar()
        |
        v
GET /me/calendarView/delta?$deltatoken={token}
        |
        v
Response: list of MicrosoftEvent dicts
        |
        v
MicrosoftEvent(events).match_with_odoo_events(env)
        |
        v
_sync_microsoft2odoo()
        |
        v
For each event: _microsoft_to_odoo_values() -> write()
```

---

## Delta Sync Deep Dive (L4)

### How Delta Sync Works

Microsoft Graph's delta sync works by maintaining a **sync state** (the delta token) server-side for each user. This state tracks all calendar changes since the last request. When Odoo sends the stored `microsoft_calendar_sync_token`, Microsoft returns only events that changed (added, modified, or deleted) since that token was issued.

```
Initial sync (no token):
  GET /me/calendarView/delta?startDateTime=...&endDateTime=...
  → Returns ALL events in range + @odata.deltaLink with token

Subsequent sync (with token):
  GET /me/calendarView/delta?$deltatoken=abc123
  → Returns ONLY changed events + new @odata.deltaLink

Event lifecycle in delta response:
  - New/modified: appears in value[] with full event data
  - Deleted: appears with @removed: { reason: "deleted" }
  - Cancelled: appears with isCancelled: true
```

### The `full_sync` Variable

The `full_sync` boolean in `_sync_microsoft_calendar()` controls which Odoo records are pushed to Microsoft during the Odoo→Microsoft phase:

```python
full_sync = not bool(self.sudo().microsoft_calendar_sync_token)
```

- **`full_sync = True`**: All Odoo records with `need_sync_m=True` are pushed, regardless of when they were created. Used on first sync or when the delta token is invalidated.
- **`full_sync = False`**: Only Odoo records created after `microsoft_calendar.sync.first_synchronization_date` ICP AND with `need_sync_m=True` are pushed. This prevents spamming attendees with invitations for pre-existing Odoo events.

The `first_synchronization_date` ICP is set automatically on the first successful sync cycle via `_set_ICP_first_synchronization_date()`, which stores `now - 1 minute` (the 1-minute buffer prevents race conditions with concurrent write timestamps).

### When Full Sync Is Triggered

| Trigger | Mechanism | Location |
|---------|-----------|----------|
| No sync token stored yet | `full_sync = not bool(sync_token)` | `res_users.py:90` |
| `InvalidSyncToken` exception | `full_sync = True` | `res_users.py:94-96` |
| HTTP 410 Gone + fullSyncRequired | Retry with full sync | `utils/microsoft_calendar.py:114-116` |
| User restarts sync | `_restart_microsoft_sync()` sets `need_sync_m=True` on all records | `res_users.py:132-137` |
| Account reset wizard | `sync_policy='all'` clears `microsoft_id` + sets `need_sync_m=True` | `wizard/reset_account.py:39-43` |

### Delta Token Lifecycle

```
Token stored in: res.users.settings.microsoft_calendar_sync_token
Retrieved by:    self.sudo().microsoft_calendar_sync_token
Updated after:   successful get_events() call

Token becomes invalid when:
  - Microsoft server state is reset (fullSyncRequired error)
  - Calendar is deleted and recreated in Outlook
  - Microsoft account is disconnected and reconnected
  - @odata.deltaLink is no longer provided (should not happen in practice)
```

The `InvalidSyncToken` exception (defined in `utils/microsoft_calendar.py`) is raised when the HTTP response status is 410 Gone. The `_check_full_sync_required()` method checks for `fullSyncRequired` or `SyncStateNotFound` error codes. If confirmed, the code retries with a full sync (no token) and sets `full_sync = True` for the remainder of the sync cycle.

### Sync Cycle Timing

```
Cron triggers: _sync_all_microsoft_calendar()
  → For each user with microsoft_calendar_rtoken AND NOT microsoft_synchronization_stopped

Per-user sync cycle:
  1. Token acquisition (~0ms if valid, 100-500ms if refresh needed)
  2. GET /me/calendarView/delta (network: 100-2000ms depending on event volume)
  3. Odoo DB writes for Microsoft→Odoo events
  4. Odoo→Microsoft pushes for changed Odoo events
  5. Token save to res.users.settings (~10ms)
```

The default HTTP timeout is 5 seconds (`TIMEOUT` from `microsoft_account`). Each page of up to 50 events is fetched sequentially; there is no parallel page fetching.

---

## Configuration

**Settings → Integrations → Microsoft Calendar**

| Parameter | Config Parameter Key | Purpose |
|-----------|--------------------|---------|
| Client ID | `microsoft_calendar_client_id` | Azure AD app registration ID |
| Client Secret | `microsoft_calendar_client_secret` | Azure AD app secret |
| Sync Range | `microsoft_calendar.sync.range_days` | Days to look back/forward (default 365) |
| Lower Bound Override | `microsoft_calendar.sync.lower_bound_range` | Override lower bound for old event updates |
| First Sync Date | `microsoft_calendar.sync.first_synchronization_date` | Only sync events created after this date |
| Sync Paused | `microsoft_calendar_sync_paused` | Global pause flag (ir.config_parameter) |
| Graph Timeout | `microsoft_calendar.graph_timeout` | HTTP timeout in seconds (default 5s) |

**Per-User Settings** (in user preferences):
- `microsoft_synchronization_stopped` — Individual pause/resume
- Viewed via **Settings → Users → [User] → Preferences → Outlook Calendar**

---

## OAuth2 / Token Management

Tokens are managed by the `microsoft_account` module. The `microsoft_calendar` module consumes them:

```python
@contextmanager
def microsoft_calendar_token(user):
    yield user._get_microsoft_calendar_token()
    # Token auto-refreshes inside _get_microsoft_calendar_token()
```

**Token Fields** (in `microsoft_account`):
- `microsoft_calendar_token` — Current access token
- `microsoft_calendar_rtoken` — Refresh token
- `microsoft_calendar_token_validity` — Expiry timestamp

**Scopes Requested:**
```
offline_access openid Calendars.ReadWrite
```

**Token Auto-Refresh:**

```python
def _get_microsoft_calendar_token(self):
    if not self:
        return None
    self.ensure_one()
    # Check if token is expired (1-minute buffer)
    if self.sudo().microsoft_calendar_rtoken and not self._is_microsoft_calendar_valid():
        self._refresh_microsoft_calendar_token()
    return self.sudo().microsoft_calendar_token
```

The `_is_microsoft_calendar_valid()` check adds a 1-minute buffer before expiry to avoid race conditions where the token expires mid-request.

**Token Refresh Failure Handling:**

```python
def _refresh_microsoft_calendar_token(self, service='calendar'):
    try:
        access_token, ttl = self.env['microsoft.service']._refresh_microsoft_token(...)
        self.sudo().write({
            'microsoft_calendar_token': access_token,
            'microsoft_calendar_token_validity': fields.Datetime.now() + timedelta(seconds=ttl),
        })
    except requests.HTTPError as error:
        if error.response.status_code in (400, 401):
            # Delete refresh token and sync token
            self.env.cr.rollback()
            self.sudo().write({
                'microsoft_calendar_rtoken': False,
                'microsoft_calendar_token': False,
                'microsoft_calendar_token_validity': False,
            })
            self.res_users_settings_id.sudo().write({
                'microsoft_calendar_sync_token': False
            })
            self.env.cr.commit()
```

When a refresh token is invalidated (400/401), Odoo:
1. Rolls back any pending transaction
2. Clears all three token fields (`rtoken`, `token`, `validity`)
3. Clears the delta sync token (forcing full re-sync on next authorization)
4. Commits the clear operation immediately so it persists even if the user session ends

The user must re-authorize Odoo's access to their Outlook calendar via the OAuth redirect flow.

---

## Recurring Events

### The Core Limitation

**Recurrence updates from Odoo to Microsoft are blocked.** Due to Microsoft Outlook's spam prevention (sending one email per attendee per update), users are directed to manage recurring events in Outlook.

**Specifically blocked:**
- Creating a recurrence in Odoo (suggest: use Outlook)
- Updating a recurrence in Odoo (suggest: use Outlook)
- Deleting a recurring event from Odoo (suggest: use Outlook)

```python
def _forbid_recurrence_creation(self):
    raise UserError(_("Due to an Outlook Calendar limitation, recurrent events must be created directly in Outlook Calendar."))

def _forbid_recurrence_update(self):
    raise UserError(_("Due to an Outlook Calendar limitation, recurrence updates must be done directly in Outlook Calendar."))
```

### What Does Work: Microsoft → Odoo

Recurrences created in **Microsoft Outlook** sync to Odoo correctly. The `_sync_recurrence_microsoft2odoo()` method:
1. Creates the `calendar.recurrence` record
2. Creates all occurrence `calendar.event` records (up to 720)
3. Handles exceptions (modified occurrences) correctly

### Recurrence Data Mapping

When a recurrence syncs from Microsoft, these fields are mapped:

| Odoo Field | Microsoft Field | Notes |
|-----------|---------------|-------|
| `rrule` | `recurrence.pattern + recurrence.range` | Serialized iCal rule |
| `dtstart` | `start.dateTime` | First occurrence start |
| `end_type` | `recurrence.range.type` | `numbered`, `endDate`, `forever` |
| `count` | `recurrence.range.numberOfOccurrences` | Max 720 |
| `interval` | `recurrence.pattern.interval` | Every N days/weeks/months |
| `byday` | `recurrence.pattern.daysOfWeek` | Weekday selection |
| `day` | `recurrence.pattern.dayOfMonth` | Month day |
| `mon`..`sun` | `recurrence.pattern.daysOfWeek` | Boolean flags |

### Recurrence Event Types in Microsoft Graph

Microsoft distinguishes four event types, each handled differently:

| Type | Description | Sync Path |
|------|-------------|-----------|
| `singleInstance` | Regular one-off event | Direct sync |
| `seriesMaster` | The recurrence rule container | Creates `calendar.recurrence` in Odoo |
| `occurrence` | A single instance in a series | Fetched via `/events/{masterId}/instances` after delta sync; creates `calendar.event` in Odoo |
| `exception` | A modified occurrence (different from template) | Handled as a modified `calendar.event`; `seriesMasterId` links it to the recurrence |

**Why occurrences are fetched separately:**

The delta endpoint `/me/calendarView/delta` returns `seriesMaster` events but does **not** include the `iCalUId` attribute for individual occurrences. Therefore, after the delta sync completes, Odoo makes a second call to `/me/events/{seriesMaster.id}/instances` for each master to fetch the full occurrence details (including iCalUId) needed for reliable recurrence matching.

---

## Conflict Resolution

### Strategy: "Last Write Wins"

The sync uses timestamp comparison between Odoo and Microsoft:

```python
if ms_event_updated_time >= odoo_event_updated_time:
    # Microsoft wins: update Odoo
    odoo_event._write_from_microsoft(mevent, vals)
else:
    # Odoo wins: already updated via push, skip
    pass
```

### Old Event Update Guard

To prevent cascading email spam from Microsoft when old events are touched:

```python
def _check_old_event_update_required(self, lower_bound_day_range, update_time_diff):
    # Only update if:
    # 1. Event stop date >= lower_bound, OR
    # 2. Time diff between MS and Odoo updates >= 1 hour
```

This prevents a 1-second difference in write timestamps from triggering unnecessary recurrence update emails.

---

## Privacy and Data Handling

### Data Sent to Microsoft

When syncing an Odoo event to Microsoft, these are transmitted:
- Event title, description, location
- Start/end datetimes
- Attendee list (email + display name)
- Organizer information
- Reminder settings
- Privacy level (public/private/confidential)
- Show as status (free/busy)

### Data Received from Microsoft

When receiving from Microsoft:
- All event properties are mapped back to Odoo equivalents
- Attendees are matched to existing `res.partner` records by email
- New partners are created if needed
- Microsoft Teams meeting URLs (`joinUrl`) are stored in `videocall_location`

### Token Privacy

- Refresh tokens (`microsoft_calendar_rtoken`) are stored in `microsoft.service` model
- Sync tokens (`microsoft_calendar_sync_token`) are stored per-user in `res.users.settings`
- Tokens are **not exposed** to the web client (filtered via `_get_fields_blacklist`)

---

## Error Handling

### Token Expiry

```python
def _get_microsoft_calendar_token(self):
    if self.sudo().microsoft_calendar_rtoken and not self._is_microsoft_calendar_valid():
        self._refresh_microsoft_calendar_token()
    return self.sudo().microsoft_calendar_token
```

If refresh fails with 400/401, the refresh token is invalidated and the user must re-authorize.

### API Failures During Sync

Sync failures are logged but do not block the user:

```python
@after_commit
def _microsoft_patch(self, user_id, event_id, values, timeout=TIMEOUT):
    try:
        microsoft_service.patch(event_id, values, ...)
        self.with_context(dont_notify=True).write({'need_sync_m': False})
    except Exception:
        # need_sync_m stays True — will retry on next sync cycle
        _logger.warning("Could not sync record now: %s", self)
```

### CRON Exception Handling

```python
@api.model
def _sync_all_microsoft_calendar(self):
    users = self.env['res.users'].sudo().search([...])
    for user in users:
        try:
            user.with_user(user).sudo()._sync_microsoft_calendar()
            self.env.cr.commit()  # Commit after each user
        except Exception as e:
            _logger.exception("[%s] Calendar Synchro - Exception : %s!", user, e)
            self.env.cr.rollback()  # Rollback and continue to next user
```

Each user's sync result is committed individually. If one user's sync fails, the rollback does not affect other users' sync results.

---

## Account Reset Wizard

**Location:** `wizard/reset_account.py`

The `microsoft.calendar.account.reset` wizard allows administrators to:
1. Delete Microsoft events from Outlook (for synced non-recurring events)
2. Delete Odoo events (for all synced events)
3. Delete from both
4. Reset sync token (force full re-sync or stop sync)

```python
class MicrosoftCalendarAccountReset(models.TransientModel):
    delete_policy = fields.Selection([
        ('dont_delete', "Leave them untouched"),
        ('delete_microsoft', "Delete from Microsoft"),
        ('delete_odoo', "Delete from Odoo"),
        ('delete_both', "Delete from both"),
    ], default='dont_delete')

    sync_policy = fields.Selection([
        ('new', "Synchronize only new events"),
        ('all', "Re-synchronize all existing events"),
    ], default='new')
```

**Critical behavior in `reset_account()`:**

```python
# CRITICAL: Commit before clearing tokens
self.env.cr.commit()
# After commit, the _microsoft_delete calls are made in the now-orphaned transaction
# but the tokens are cleared, so subsequent sync won't retry them.

self.user_id._set_microsoft_auth_tokens(False, False, 0)
# Clears: microsoft_calendar_rtoken, microsoft_calendar_token, validity

self.user_id.res_users_settings_id.sudo().write({
    'microsoft_calendar_sync_token': False,
    'microsoft_last_sync_date': False
})
# Clears: delta token + last sync date
```

The explicit `commit()` before clearing tokens is critical: it ensures that any pending `_microsoft_delete()` HTTP requests are executed while the user still has a valid access token. After the commit, the token fields are cleared, so any subsequent operations will fail gracefully rather than attempting to use an invalidated token.

---

## HTTP Controller

**Location:** `controllers/main.py`

Single RPC endpoint for the frontend:

```python
@route('/microsoft_calendar/sync_data', type='jsonrpc', auth='user')
def microsoft_calendar_sync_data(self, model, **kw):
    if model == 'calendar.event':
        # Check: admin configured Microsoft API?
        if not client_id:
            return {"status": "need_config_from_admin", "action": action_id}

        # Check: user authorized Odoo to access Outlook?
        if not MicrosoftCal.is_authorized(request.env.user):
            return {"status": "need_auth", "url": auth_url}

        # Run sync
        need_refresh = request.env.user._sync_microsoft_calendar()

        return {"status": "need_refresh" if need_refresh else "no_new_event_from_microsoft"}
```

**Return Status Codes:**

| Status | Meaning |
|--------|---------|
| `need_config_from_admin` | Admin must set Azure app credentials |
| `need_auth` | User must authorize Odoo to access Outlook |
| `sync_stopped` | User has paused sync |
| `sync_paused` | Global pause is active |
| `need_refresh` | New data synced, UI should reload |
| `no_new_event_from_microsoft` | Sync completed, no new data |

---

## Cron Jobs

**Sync Cron:** `ir.cron` record — `base.cron` / `_sync_all_microsoft_calendar`

The method `_sync_all_microsoft_calendar()` runs for all users who:
1. Have a Microsoft refresh token (`microsoft_calendar_rtoken != False`)
2. Have not stopped their sync (`microsoft_synchronization_stopped = False`)

---

## Performance Analysis (L4)

### Sync Cycle Bottlenecks

| Bottleneck | Location | Impact | Mitigation |
|------------|----------|--------|------------|
| Sequential pagination | `_get_events_from_paginated_url` | Each `nextLink` is fetched sequentially; large change sets take O(n) time | Microsoft returns up to 50 events per page; average calendar with low churn = 1-2 pages |
| Occurrence detail fetch | `get_events()` loop | Second API call per recurrence master | Only occurs for `seriesMaster` events; most calendars have few masters |
| Per-event Odoo writes | `_sync_microsoft2odoo()` | N events = N write() calls | Events are batched via `with_context()`; Odoo ORM batches in memory |
| Per-member Teams notification | `_skip_send_mail_status_update()` | Prevents Odoo→Microsoft notification loop | Only affects alarm notifications, not attendee emails |
| HMAC token generation | `_generate_action_token()` / `_generate_email_access_token()` | Called per recipient in mail_group._notify_members | HMAC-SHA256 is sub-millisecond; not a practical bottleneck |

### Sync Timing by Calendar Size

| Calendar Size | Events Changed/Sync | Approximate Duration | Primary Driver |
|---------------|-------------------|---------------------|----------------|
| Small (<100 events) | 0-10 | 200-500ms | Network latency |
| Medium (100-1000 events) | 10-50 | 500ms-2s | API pagination + DB writes |
| Large (1000-10000 events) | 50-500 | 2s-10s | API pagination (10+ pages) + writes |

### First Sync vs Subsequent Sync

| Phase | Delta Token State | Odoo→Microsoft Scope | Microsoft→Odoo Scope |
|-------|-------------------|---------------------|---------------------|
| First sync | No token | All `need_sync_m=True` events | All events in `range_days` window |
| Subsequent sync | Token valid | Only post-`first_synchronization_date` + `need_sync_m=True` | Only changed events |
| After token invalidation | No token (re-triggered) | All `need_sync_m=True` events | All events (full re-scan) |

### Database Query Count Per Sync Cycle

For a sync cycle with N changed Microsoft events and M changed Odoo events:

```
1. Get sync token from res.users.settings
2. GET /me/calendarView/delta (HTTP)
3. Parse response + paginate (N HTTP calls for N pages)
4. For N Microsoft events:
   a. match_with_odoo_events: 1 search query (batch)
   b. _sync_microsoft2odoo: N writes
5. _get_microsoft_records_to_sync: 1 search query
6. _sync_odoo2microsoft: M HTTP PATCH calls
7. Save next_sync_token: 1 write
```

Total: O(1) queries for Microsoft→Odoo + O(M) queries for Odoo→Microsoft (batched by the ORM where possible).

---

## OAuth Token Security Architecture (L4)

### Three-Tier Token System

Microsoft 365 OAuth involves three distinct tokens:

| Token | Stored In | Lifetime | Purpose |
|-------|-----------|----------|---------|
| Access token (`microsoft_calendar_token`) | `microsoft.service` (per user, sudo) | ~1 hour | Authorizes each API call |
| Refresh token (`microsoft_calendar_rtoken`) | `microsoft.service` (per user, sudo) | ~90 days (sliding) | Generates new access tokens |
| Delta sync token (`microsoft_calendar_sync_token`) | `res.users.settings` (per user, sudo) | Until invalidated | Tracks change position in Microsoft |

### Why Three Tokens?

**Access token**: Short-lived for security. If leaked, window of exploitation is limited to ~1 hour.

**Refresh token**: Long-lived but stored server-side only. The client never sees it after initial OAuth flow. Microsoft can revoke it remotely.

**Delta sync token**: Odoo-specific. Microsoft's delta sync mechanism requires maintaining a server-side cursor. Without it, every sync would be a full scan. The token is opaque — Odoo stores it but cannot read or modify it.

### OAuth Scopes

```
offline_access   →获得refresh token（持续访问）
openid           → OpenID Connect 身份验证
Calendars.ReadWrite →读写用户日历
```

The `offline_access` scope is critical: without it, the refresh token is not issued, and users must re-authorize after each access token expiry.

### Token Storage Security

```python
# All token fields are accessed via sudo() in the calendar module:
self.sudo().microsoft_calendar_rtoken        # refresh token
self.sudo().microsoft_calendar_token         # access token
self.sudo().microsoft_calendar_sync_token    # delta token
```

The `groups='base.group_system'` restriction on the `related` fields in `res.users` means even ERP managers cannot read these values through the ORM's `read()` method. They remain visible in the database directly.

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Token stolen from DB backup | Refresh token invalidated by 400 response on use; delta token invalidated clears sync state |
| Token intercepted in transit | HTTPS enforced by Microsoft Graph API; access token is Bearer token |
| Refresh token replay | Microsoft refresh tokens are single-use; new refresh token issued on each refresh |
| User revokes Odoo access | `is_authorized()` check fails → sync stops; no orphaned data |
| Admin disconnects account | Reset wizard clears all tokens atomically + commits before clearing |
| CSRF on sync endpoint | `auth='user'` on controller route requires valid Odoo session |
| Token refresh race condition | 1-minute validity buffer prevents edge-case expiry during long requests |

---

## Odoo 18 → 19 Changes (L4)

### Architectural Changes

| Area | Odoo 18 | Odoo 19 | Why It Changed |
|------|---------|---------|----------------|
| Sync token storage | Stored directly on `res.users` | Per-user `res.users.settings` record | Separates user preferences from integration tokens; cleaner data model |
| `microsoft_id` field | Existed on `calendar.event` | Unchanged | — |
| `need_sync_m` default on recurrence | `True` (or unset) | Explicit `False` on `calendar.recurrence` | Prevents spurious recurrence push attempts; explicit is safer |
| `_primary_email` on `mail.group.message` | Not declared | `'_primary_email = 'email_from'` | Supports Odoo 19's new author email matching system for partner resolution |
| Delta sync error handling | Generic 410 handling | `InvalidSyncToken` exception + `fullSyncRequired` / `SyncStateNotFound` discrimination | Provides more granular control over re-sync strategy |
| Occurrence fetch in `get_events()` | Same pattern | Unchanged | — |
| `Domain` class usage | Raw Python list domains | `Domain.FALSE`, `Domain.OR()` throughout | Cleaner domain composition; better readability |
| `_skip_send_mail_status_update()` | Not present | Added | Prevents Odoo notification → Microsoft sync → Odoo notification loop |
| `alarm_manager` extension | Not present | `_get_notify_alert_extra_conditions()` added | Prevents duplicate Odoo reminders for Microsoft-sourced events |
| Per-user pause (`microsoft_synchronization_stopped`) | `False` | Stored in `res.users.settings` | Moved from direct field on `res.users` to per-user settings model |

### Behavioral Changes

| Behavior | Odoo 18 | Odoo 19 |
|----------|---------|---------|
| First sync date guard | `first_synchronization_date` ICP | Same mechanism; implementation refined |
| Event owner lookup | Search by organizer email | Same + `email_normalize()` applied to organizer email |
| Recurrence creation | Blocked with UserError | Still blocked; same `UserError` message |
| `restart_microsoft_synchronization()` | Clears `need_sync_m` on events | Additionally calls `_restart_microsoft_sync()` on both `calendar.recurrence` AND `calendar.event` (Odoo 18 may have only done events) |
| `owner_id()` fallback | Returned `False` if no organizer | Unchanged; `email_normalize` added for robustness |
| Token refresh failure | Cleared tokens | Same + explicit rollback + commit before clearing |

### API Compatibility Notes

- All public method signatures (`_sync_microsoft_calendar`, `_microsoft_insert`, `_microsoft_patch`, `_microsoft_delete`) remain unchanged
- XML view IDs and structure are unchanged (no view changes between versions)
- The `microsoft.calendar.account.reset` wizard remains functionally identical
- No database migration scripts needed for the core sync tables (only `res.users.settings` row creation)

---

## Related Modules

| Module | Role |
|--------|------|
| `microsoft_account` | OAuth2 token storage and management |
| `calendar` | Core calendar — provides `calendar.event`, `calendar.recurrence`, `calendar.attendee` |
| `mail` | Mail threading and notifications |

---

## Source Files Reference

| File | Role |
|------|------|
| `models/microsoft_sync.py` | Core mixin — sync engine, CRUD hooks, post-commit calls |
| `models/calendar.py` | `calendar.event` extension — field maps, validation |
| `models/calendar_recurrence_rule.py` | `calendar.recurrence` extension — recurrence sync logic |
| `models/calendar_attendee.py` | Attendee response sync |
| `models/calendar_alarm_manager.py` | Suppress duplicate Odoo notifications |
| `models/res_users.py` | User sync methods, token management |
| `models/res_users_settings.py` | Per-user token storage |
| `models/res_config_settings.py` | Admin settings (client ID/secret) |
| `utils/microsoft_calendar.py` | Microsoft Graph API wrapper |
| `utils/microsoft_event.py` | Event data structure wrapper |
| `controllers/main.py` | `/microsoft_calendar/sync_data` RPC endpoint |
| `wizard/reset_account.py` | Account reset wizard |

---

*Source: `~/odoo/odoo19/odoo/addons/microsoft_calendar/`*
