---
tags: [odoo, odoo17, module, google_calendar]
---

# Google Calendar Integration

**Source:** `addons/google_calendar/models/`

## Overview

Two-way synchronization between `calendar.event` and Google Calendar. Events, attendees, reminders, and recurrence rules are kept in sync.

## Key Models

| Model | Description |
|-------|-------------|
| `google.calendar.sync` | Abstract model with sync logic (mixin) |
| `calendar.event` (extended) | `calendar.event` inherits `google.calendar.sync` |
| `calendar.recurrence` (extended) | Recurrence rules synced via `_sync_google2odoo` |

## Sync Architecture

```
Odoo --write--> Google       via _sync_odoo2google()
         <--read--           via _sync_google2odoo() (cron-triggered)

All API calls are deferred via @after_commit decorator:
- Changes in Odoo are sent to Google AFTER the transaction commits
- This prevents duplicate events if Odoo crashes mid-transaction
```

### The `@after_commit` Pattern

```python
def after_commit(func):
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        @self.env.cr.postcommit.add  # runs after current transaction commits
        def called_after():
            with db_registry.cursor() as cr:
                env = api.Environment(cr, uid, context)
                func(self.with_env(env), *args, **kwargs)
    return wrapped

# Usage:
@after_commit
def _google_insert(self, google_service, values, timeout=TIMEOUT):
    with google_calendar_token(self.env.user.sudo()) as token:
        google_service.insert(values, token=token, timeout=timeout)
```

## `google.calendar.sync` Abstract Model

```python
class GoogleSync(models.AbstractModel):
    _name = 'google.calendar.sync'

    google_id = fields.Char('Google Calendar Id', copy=False)
    need_sync = fields.Boolean(default=True, copy=False)
    active = fields.Boolean(default=True)

    # Core sync methods:
    def _sync_odoo2google(self, google_service):
        # Odoo -> Google
        # - new records: _google_insert()
        # - updated records: _google_patch()
        # - cancelled records: _google_delete()

    @api.model
    def _sync_google2odoo(self, google_events, default_reminders=()):
        # Google -> Odoo
        # - creates new Odoo records from Google events
        # - updates existing Odoo records
        # - cancels/deletes Odoo records for cancelled Google events

    def _google_insert(self, google_service, values, timeout=3):    # @after_commit
    def _google_patch(self, google_service, google_id, values):       # @after_commit
    def _google_delete(self, google_service, google_id):               # @after_commit
```

## `calendar.event` Extension

```python
class Meeting(models.Model):
    _name = 'calendar.event'
    _inherit = ['calendar.event', 'google.calendar.sync']

    google_id = fields.Char(compute='_compute_google_id', store=True, readonly=False)
    videocall_source = fields.Selection(selection_add=[('google_meet', 'Google Meet')])

    # Fields synced to Google
    @api.model
    def _get_google_synced_fields(self):
        return {'name', 'description', 'allday', 'start', 'date_end', 'stop',
                'attendee_ids', 'alarm_ids', 'location', 'privacy', 'active', 'show_as'}

    # Odoo -> Google values
    def _google_values(self):
        # Returns dict formatted for Google Calendar API v3:
        # {id, summary, description, location, start, end, attendees, reminders, ...}

    # Google -> Odoo values
    @api.model
    def _odoo_values(self, google_event, default_reminders=()):
        # Parses Google event into Odoo vals:
        # {name, description, location, start, stop, allday, attendee_ids, alarm_ids, ...}
```

## Key Sync Behaviors

### Event Creation
- Sync is deferred via `@after_commit` to avoid duplicates on crash
- All-day events: `date` field set, `dateTime` set to `None`
- Timed events: `dateTime` set with timezone, `date` set to `None`
- Google Meet URL auto-generated via `conferenceData: {createRequest: {requestId}}`

### Recurrence
- Recurrence rules stored in `calendar.recurrence` and synced to Google
- Individual instances linked via `recurrence_id` and `follow_recurrence`
- Edge case: all-day recurrent events first synced as single events, then fixed

### Conflict Resolution
- **Last-write-wins**: uses `write_date` comparison (Google server time vs Odoo)
- Migration events (pre-13.4) without `write_date`: force update from Google

### Cancel / Archive
- Google-side cancellation archives Odoo event (sets `active=False`)
- Odoo-side unlink with `google_id` archives the record (triggers `_google_delete`)

## Credential Management

```python
@contextmanager
def google_calendar_token(user):
    yield user._get_google_calendar_token()
    # Token refresh handled automatically by google.service
```

Stored on `res.users`: `google_calendar_token`, `google_calendar_sync_token`.

## Cron Job

Full sync is triggered by a scheduled action (`ir.cron`) scanning events in a configurable range (default: past 365 days + future 365 days):

```python
def _get_sync_domain(self):
    return [
        ('partner_ids.user_ids', 'in', self.env.user.id),
        ('stop', '>', lower_bound),
        ('start', '<', upper_bound),
    ]
```

## See Also
- [[Modules/Calendar]] — `calendar.event`, `calendar.recurrence`
- [[Modules/Google]] — Google service credentials (`google_service`)
