---
title: "Google Calendar"
module: google_calendar
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Google Calendar

## Overview

Module `google_calendar` — auto-generated from source code.

**Source:** `addons/google_calendar/`
**Models:** 8
**Fields:** 30
**Methods:** 16

## Models

### calendar.event (`calendar.event`)

Return True if values being updated intersects with Google synced values and False otherwise.

**File:** `calendar.py` | Class: `CalendarEvent`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `google_id` | `Char` | Y | — | — | Y | — |
| `guests_readonly` | `Boolean` | Y | — | — | — | — |
| `videocall_source` | `Selection` | Y | — | — | — | — |
| `google_service` | `GoogleCalendarService` | — | — | — | — | — |


#### Methods (3)

| Method | Description |
|--------|-------------|
| `create` | |
| `write` | |
| `action_mass_archive` | |


### calendar.alarm_manager (`calendar.alarm_manager`)

—

**File:** `calendar_alarm_manager.py` | Class: `AlarmManager`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### calendar.attendee (`calendar.attendee`)

—

**File:** `calendar_attendee.py` | Class: `CalendarAttendee`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `service` | `GoogleCalendarService` | — | — | — | — | — |
| `google_service` | `GoogleCalendarService` | — | — | — | — | — |


#### Methods (3)

| Method | Description |
|--------|-------------|
| `do_tentative` | |
| `do_accept` | |
| `do_decline` | |


### calendar.recurrence (`calendar.recurrence`)

Return the Google id of recurring event.
        Google ids of recurrence instances are formatted as: {recurrence google_id}_{UTC starting time in compacted ISO8601}

**File:** `calendar_recurrence_rule.py` | Class: `CalendarRecurrence`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `google_service` | `GoogleCalendarService` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### google.calendar.sync (`google.calendar.sync`)

When creating 'All Day' recurrent event, the first event is wrongly synchronized as
        a single event and then its recurrence creates a duplicated event. We must manually
        set the 'need_sy

**File:** `google_sync.py` | Class: `GoogleCalendarSync`

#### Fields (7)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `google_id` | `Char` | — | — | — | — | — |
| `need_sync` | `Boolean` | — | — | — | — | — |
| `active` | `Boolean` | — | — | — | — | — |
| `google_service` | `GoogleCalendarService` | — | — | — | — | — |
| `google_service` | `GoogleCalendarService` | — | — | — | — | — |
| `is_active_clause` | `Domain` | — | — | — | — | — |
| `is_active_clause` | `Domain` | — | — | — | — | — |


#### Methods (3)

| Method | Description |
|--------|-------------|
| `write` | |
| `create` | |
| `unlink` | |


### res.config.settings (`res.config.settings`)

—

**File:** `res_config_settings.py` | Class: `ResConfigSettings`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `cal_client_id` | `Char` | — | — | — | — | — |
| `cal_client_secret` | `Char` | — | — | — | — | — |
| `cal_sync_paused` | `Boolean` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### res.users (`res.users`)

Returns the calendar synchronization status (active, paused or stopped).

**File:** `res_users.py` | Class: `ResUsers`

#### Fields (7)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `google_calendar_rtoken` | `Char` | — | — | Y | — | — |
| `google_calendar_token` | `Char` | — | — | Y | — | — |
| `google_calendar_token_validity` | `Datetime` | — | — | Y | — | — |
| `google_calendar_sync_token` | `Char` | — | — | Y | — | — |
| `google_calendar_cal_id` | `Char` | — | — | Y | — | — |
| `google_synchronization_stopped` | `Boolean` | — | — | Y | — | — |
| `google` | `GoogleCalendarService` | — | — | — | — | — |


#### Methods (7)

| Method | Description |
|--------|-------------|
| `is_google_calendar_synced` | |
| `stop_google_synchronization` | |
| `restart_google_synchronization` | |
| `unpause_google_synchronization` | |
| `pause_google_synchronization` | |
| `check_calendar_credentials` | |
| `check_synchronization_status` | |


### res.users.settings (`res.users.settings`)

Get list of google fields that won't be formatted in session_info.

**File:** `res_users_settings.py` | Class: `ResUsersSettings`

#### Fields (6)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `google_calendar_rtoken` | `Char` | — | — | — | — | — |
| `google_calendar_token` | `Char` | — | — | — | — | — |
| `google_calendar_token_validity` | `Datetime` | — | — | — | — | — |
| `google_calendar_sync_token` | `Char` | — | — | — | — | — |
| `google_calendar_cal_id` | `Char` | — | — | — | — | — |
| `google_synchronization_stopped` | `Boolean` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
