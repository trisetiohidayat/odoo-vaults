# Google Calendar

## Overview
- **Module:** Google Calendar
- **Technical Name:** `google_calendar`
- **Location:** `/Users/tri-mac/odoo/odoo19/odoo/addons/google_calendar/`
- **Category:** Productivity
- **Depends:** `google_account`, `calendar`
- **License:** LGPL-3

## Description

Synchronizes Odoo calendar events and recurrences with Google Calendar. Supports full bidirectional sync: changes made in either Odoo or Google Calendar are reflected in the other. Uses OAuth2 for authentication and the Google Calendar API v3 for all operations.

## Key Features

- **Bidirectional Sync:** Creates, updates, and deletes events in both Odoo and Google Calendar
- **Recurrence Support:** Synchronizes recurring events (calendar recurrences) to Google
- **Attendee Sync:** Syncs attendee status changes (tentative, accepted, declined) from Google back to Odoo
- **Incremental Sync:** Uses Google sync tokens for efficient incremental updates
- **Token Management:** Stores per-user OAuth2 tokens in `res.users.settings`
- **After-commit Pattern:** API calls to Google are made after the Odoo transaction commits, ensuring data consistency
- **Google Meet:** Supports `google_meet` as a videocall source option
- **Sync Control:** Pause/resume synchronization at system or user level
- **Access Control:** Handles permission errors gracefully (non-organizer modifications)
- **Full Sync Fallback:** Automatically falls back to full sync if sync token becomes invalid

## Configuration

**System-wide (Settings > General > Google Calendar):**
- `google_calendar_client_id` — OAuth2 Client ID
- `google_calendar_client_secret` — OAuth2 Client Secret
- `google_calendar_sync_paused` — Pause all sync (boolean config parameter)

**Per-user (User Preferences):**
- `google_calendar_rtoken` — Refresh token (system field)
- `google_calendar_token` — Current access token (system field)
- `google_calendar_token_validity` — Token expiry time (system field)
- `google_calendar_sync_token` — Google sync token for incremental sync
- `google_calendar_cal_id` — Google Calendar ID
- `google_synchronization_stopped` — User-level sync pause

## Models

### `google.calendar.sync` (Abstract Model)

Mixin providing generic two-way synchronization with Google Calendar API.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `google_id` | Char | Google Calendar event ID (indexed, copy=False) |
| `need_sync` | Boolean | Flag to sync this record to Google (default: True) |
| `active` | Boolean | Active state (default: True) |

**Key Methods:**
- `write(vals)` — If synced fields change, mark `need_sync=True` and push update to Google via `_google_patch()`
- `create(vals_list)` — Create in Odoo then insert into Google (if active and sync enabled)
- `unlink()` — If `google_id` exists, archive the record (which deletes from Google) rather than hard-delete
- `_sync_odoo2google()` — Push local changes to Google: delete cancelled, insert new, patch updated
- `_sync_google2odoo(google_events, write_dates, default_reminders)` — Pull Google changes into Odoo: create new, update existing (based on `write_date` comparison), cancel removed. Handles recurrence rescheduling edge cases.
- `_google_insert()` — POST to Google Calendar API to create event (fires after commit via `@after_commit` decorator)
- `_google_patch()` — PATCH to Google to update event (fires after commit)
- `_google_delete()` — DELETE event from Google (fires after commit)
- `_get_records_to_sync(full_sync)` — Return Odoo records pending sync (limit: 200 per transaction)
- `_check_any_records_to_sync()` — Returns True if any records need syncing
- `_get_google_synced_fields()` — Return field names whose changes trigger sync
- `_odoo_values()` — Convert Google event to Odoo vals (abstract, implemented by `calendar.event`)
- `_google_values()` — Convert Odoo event to Google API format (abstract, implemented by `calendar.event`)
- `_get_sync_domain()` — Domain for which records to sync (abstract)
- `_get_event_user()` — Return the correct Odoo user for API calls (handles organizer vs. attendee)
- `_is_google_insertion_blocked()` — Prevent wrong-organizer sync issues

**Decorator:**
- `@after_commit` — Defers Google API calls until after the current database transaction commits

### `calendar.event` (Extension)

Inherits `google.calendar.sync` for bidirectional sync.

**Key Methods:**
- `_get_google_synced_fields()` — Returns set of synced fields
- `_odoo_values(google_event, default_reminders)` — Convert Google event dict to Odoo `calendar.event` values
- `_google_values()` — Convert Odoo event to Google Calendar API v3 format
- `_check_modify_event_permission()` — Validate user can modify the event on Google
- `_get_sync_domain()` — Sync records owned by or involving the current user
- `_get_event_user()` — Return organizer user for API calls
- `_is_google_insertion_blocked(sender_user)` — Prevent sync if sender is not the event organizer

### `calendar.recurrence` (Extension)

Inherits `google.calendar.sync` for recurrence sync.

**Key Methods:**
- `_apply_recurrence()` — Create Google recurrence from Odoo recurrence
- `_get_event_google_id()` — Generate recurring event Google ID format
- `_write_from_google(gevent, vals)` / `_create_from_google(gevents, vals_list)` — Apply Google data to Odoo
- `_google_values()` — Build Google recurrence rule (RRULE) from Odoo recurrence
- `_sync_google2odoo()` — Creates or updates Odoo recurrences from Google data

### `calendar.attendee` (Extension)

**Key Methods:**
- `do_tentative()` / `do_accept()` / `do_decline()` — After changing status in Odoo, trigger sync to Google
- `_sync_event()` — Trigger calendar event sync to Google

### `res.users` (Extension)

**Key Methods:**
- `_get_google_calendar_token()` — Get valid access token (auto-refreshes if expired)
- `_get_google_sync_status()` — Returns `sync_active`, `sync_paused`, or `sync_stopped`
- `_check_pending_odoo_records()` — Check if Odoo has records pending Google sync
- `_sync_google_calendar(calendar_service)` — Full bidirectional sync loop: pull from Google, push to Google
- `_sync_request(calendar_service, event_id)` — Fetch events from Google (full or incremental). Handles row locking and sync token management.
- `_sync_single_event(calendar_service, odoo_event, event_id)` — Sync a single event
- `_sync_all_google_calendar()` — Cron job that syncs all users with active Google calendar tokens
- `is_google_calendar_synced()` — Check if user has credentials and active sync
- `stop_google_synchronization()` / `restart_google_synchronization()` — User-level pause/restart
- `pause_google_synchronization()` / `unpause_google_synchronization()` — System-wide pause
- `_has_setup_credentials()` — Check if client ID and secret are configured
- `check_calendar_credentials()` — Check OAuth2 credential status
- `check_synchronization_status()` — Get combined credential + sync status
- `_has_any_active_synchronization()` — Check if any calendar sync is active

### `res.users.settings` (Extension)

Stores per-user Google Calendar OAuth2 tokens and preferences.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `google_calendar_rtoken` | Char | Refresh token |
| `google_calendar_token` | Char | Access token |
| `google_calendar_token_validity` | Datetime | Token expiry |
| `google_calendar_sync_token` | Char | Google sync token |
| `google_calendar_cal_id` | Char | Google Calendar ID |
| `google_synchronization_stopped` | Boolean | User-level sync stop |

**Key Methods:**
- `_set_google_auth_tokens()` — Store tokens after OAuth2 flow
- `_google_calendar_authenticated()` — Check if user has completed OAuth2 authorization
- `_is_google_calendar_valid()` — Check if current access token is still valid
- `_refresh_google_calendar_token()` — Refresh access token using stored refresh token

### `res.config.settings` (Extension)

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `cal_client_id` | Char | Google Calendar Client ID |
| `cal_client_secret` | Char | Google Calendar Client Secret |
| `cal_sync_paused` | Boolean | Pause all Google Calendar sync |

## Cron Jobs

- `_sync_all_google_calendar()` — Scheduled action syncs all active users. Runs sorted by token validity (oldest tokens first).

## Sync Architecture

```
Odoo Transaction Commit
    |
    v
@after_commit hook fires
    |
    v
_google_insert() / _google_patch() / _google_delete()
    |
    v
Google Calendar API (POST/PATCH/DELETE)
```

This ensures Google is only updated when Odoo data is definitively committed.

## Related

- [Modules/calendar](odoo-18/Modules/calendar.md) — Base calendar events and recurrences
- [Modules/google_account](odoo-17/Modules/google_account.md) — OAuth2 foundation
- [Modules/Product](odoo-18/Modules/product.md) — Meeting rooms and resources (via calendar)

---
*Documented: 2026-04-06*
