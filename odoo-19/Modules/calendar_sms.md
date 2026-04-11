---
tags:
  - #odoo19
  - #modules
  - #calendar
  - #sms
---

# calendar_sms

## Overview

| Property | Value |
|----------|-------|
| Module | `calendar_sms` |
| Path | `odoo/addons/calendar_sms/` |
| Category | Productivity / Calendar |
| Version | 1.1 (Odoo 19 CE) |
| Dependencies | `calendar`, `sms` |
| Auto-install | `True` |
| License | LGPL-3 |
| Author | Odoo S.A. |

## Purpose

Extends the `calendar` module's alarm system with **SMS Text Message** as a fourth alarm type (alongside email, in-app notification, and screen notification). It provides both automated scheduled SMS reminders triggered by the `calendar.alarm_manager` cron, and an on-demand **Send SMS** action button on events. The module wires a default SMS template into the alarm system so that no manual configuration is required out of the box.

---

## Architecture

### File Map

```
calendar_sms/
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── calendar_alarm.py        # calendar.alarm extension (alarm_type + sms_template_id)
│   ├── calendar_alarm_manager.py # calendar.alarm_manager override (_send_reminder)
│   └── calendar_event.py        # calendar.event extension (_do_sms_reminder, action_send_sms)
├── data/
│   └── sms_data.xml             # Default SMS template (noupdate=1)
├── views/
│   └── calendar_views.xml       # Form/list view extensions
└── tests/
    ├── __init__.py
    └── test_calendar_sms.py    # Integration tests with mockSMSGateway
```

### Module Composition

Three models are extended. No new database tables are created.

```
calendar.alarm              (calendar base model)
    └── calendar_sms.CalendarAlarm
            _inherit = 'calendar.alarm'
            Fields added: alarm_type (+sms), sms_template_id

calendar.alarm_manager      (abstract model, base)
    └── calendar_sms.CalendarAlarm_Manager
            _inherit = 'calendar.alarm_manager'
            Method overridden: _send_reminder()

calendar.event              (calendar base model)
    └── calendar_sms.CalendarEvent
            _inherit = 'calendar.event'
            Methods added: _do_sms_reminder(), action_send_sms()
            Method extended: _get_trigger_alarm_types()
```

### Dependency Chain

```
calendar_sms
    ├── depends: calendar
    │       ├── provides: calendar.event, calendar.alarm, calendar.alarm_manager
    │       ├── alarm model: alarm_type (email/notification/popup), mail_template_id, notify_responsible
    │       ├── alarm_manager: _send_reminder() dispatches by alarm_type
    │       └── cron: ir_cron_scheduler_alarm runs _send_reminder() every minute
    └── depends: sms
            ├── provides: sms.template, sms.composer, smsSendingGateway
            └── sms.template model renders Jinja2 body with {{ object }} = calendar.event
```

---

## Models

### 1. `CalendarAlarm` -- `calendar.alarm`

**File:** `models/calendar_alarm.py`

Extends `calendar.alarm` with the SMS alarm type and a linked SMS template.

#### Fields

##### `alarm_type` -- Selection (inherited, extended)

```python
alarm_type = fields.Selection(selection_add=[
    ('sms', 'SMS Text Message')
], ondelete={'sms': 'set default'})
```

**L2:** The `selection_add` pattern appends `'sms'` to the parent's `('email', 'notification', 'popup')` options. The `ondelete` dict specifies that if an SMS-type alarm record is deleted (e.g., the `calendar_sms` module is uninstalled), the record's `alarm_type` is reset to the model's default (the first selection value, `'notification'`) rather than the record being cascade-deleted. This is a **data preservation strategy** -- existing alarm records do not vanish when the module is removed.

**L3:** The `ondelete={'sms': 'set default'}` mapping applies only when the current value of `alarm_type` is `'sms'`. If the user had previously set a non-SMS type, the `ondelete` rule has no effect.

##### `sms_template_id` -- Many2one `sms.template`

```python
sms_template_id = fields.Many2one(
    'sms.template', string="SMS Template",
    domain=[('model', 'in', ['calendar.event'])],
    compute='_compute_sms_template_id',
    readonly=False,
    store=True,
    help="Template used to render SMS reminder content."
)
```

**L2:**
- `domain` restricts selectable templates to those whose `model` is `calendar.event`. This prevents accidentally linking an unrelated template (e.g., a sale order confirmation template).
- `compute` + `readonly=False` + `store=True` is a hybrid pattern: the field is **computable but also manually overridable**. When the user does not set a value, the compute fills it automatically. When the user sets a custom template, their value is stored and the compute no longer overwrites it (because `alarm.sms_template_id` is already truthy).
- `store=True` persists the computed value to the database, which is important for performance: the cron job reads `sms_template_id` without triggering recomputation on every access.

**L3:** The domain `[('model', 'in', ['calendar.event'])]` references the `model_id` field on `sms.template`. The `sms.template` model stores `model_id` as a Many2one to `ir.model`, so this domain correctly filters.

#### Compute Method

```python
@api.depends('alarm_type', 'sms_template_id')
def _compute_sms_template_id(self):
    for alarm in self:
        if alarm.alarm_type == 'sms' and not alarm.sms_template_id:
            alarm.sms_template_id = self.env['ir.model.data']._xmlid_to_res_id(
                'calendar_sms.sms_template_data_calendar_reminder'
            )
        elif alarm.alarm_type != 'sms' or not alarm.sms_template_id:
            alarm.sms_template_id = False
```

**L2:** The `elif` branch covers two mutually exclusive cases: (a) the alarm type is not SMS, so the field must be cleared regardless of whether a template was set previously; (b) the alarm type is SMS but `sms_template_id` was already set (either manually or by a prior compute pass), in which case `not alarm.sms_template_id` is `False` and the branch is skipped, leaving the existing value intact.

**L4 Edge Case -- `xmlid_to_res_id` returns False:** If the XML ID `calendar_sms.sms_template_data_calendar_reminder` cannot be resolved (e.g., data was never loaded due to a noupdate migration issue), `_xmlid_to_res_id` returns `False`. In that case `not alarm.sms_template_id` is `True` and the assignment `alarm.sms_template_id = False` would be attempted. Since `False` cannot be assigned to a Many2one field, this silently sets the field to `False` (empty), meaning **no SMS is sent** for that alarm. No exception is raised.

**L4 Performance:** The `_xmlid_to_res_id` lookup is a `ir.model.data` database query per alarm record. With `store=True`, this is executed once when the alarm is created or when `alarm_type` changes to `'sms'`, not on every cron run.

---

### 2. `CalendarAlarm_Manager` -- `calendar.alarm_manager`

**File:** `models/calendar_alarm_manager.py`

Abstract model (`_inherit = 'calendar.alarm_manager'`). The base `calendar.alarm_manager` is also abstract and is instantiated as a singleton by the `ir_cron_scheduler_alarm` cron job.

#### Overridden `_send_reminder()`

```python
@api.model
def _send_reminder(self):
    super()._send_reminder()                          # 1. Send emails
    events_by_alarm = self._get_events_by_alarm_to_notify('sms')  # 2. Find due SMS alarms
    if not events_by_alarm:
        return
    # 3. Deduplicate event IDs across all alarms
    all_events_ids = list({event_id for event_ids in events_by_alarm.values()
                           for event_id in event_ids})
    for alarm_id, event_ids in events_by_alarm.items():
        # 4. Prefetch: load alarm and all events in two queries
        alarm = self.env['calendar.alarm'].browse(alarm_id).with_prefetch(
            list(events_by_alarm.keys()))
        events = self.env['calendar.event'].browse(event_ids).with_prefetch(all_events_ids)
        events._do_sms_reminder(alarm)              # 5. Send SMS per alarm
        events._setup_event_recurrent_alarms(events_by_alarm)  # 6. Schedule next occurrence
```

**L2:** `super()._send_reminder()` is called **first** (not after), ensuring email and SMS reminders are sent in the same cron run and in the correct order. Email failures do not block SMS delivery because each is a separate code path.

**L4 `_setup_event_recurrent_alarms` placement:** This method is called **inside the loop**, not after it. Each iteration handles a different alarm. Calling it inside the loop ensures that after each alarm's SMS batch is sent, the recurrence's next alarm trigger is updated before the next alarm is processed. If this were called outside the loop, the trigger would only reflect the last alarm in the iteration. This is important because `_setup_event_recurrent_alarms()` calls `event.recurrence_id.with_context(date=next_date)._setup_alarms()` which schedules the next `ir.cron.trigger` based on the next event's alarm.

**L4 Performance:**
- The `all_events_ids` set comprehension deduplicates event IDs before the loop. Without this, if one event has multiple SMS alarms (e.g., a 1-hour and a 24-hour reminder), the same event could be browsed multiple times in the prefetch cache.
- `with_prefetch(list(events_by_alarm.keys()))` pre-populates the ORM's prefetch cache for `calendar.alarm` records before iterating, avoiding N+1 reads on the alarm browse calls inside the loop.
- `with_prefetch(all_events_ids)` on the event recordset has the same effect for `calendar.event` records.

**L3 `_get_events_by_alarm_to_notify` SQL logic:**

The base `calendar.alarm_manager._get_events_by_alarm_to_notify('sms')` uses this SQL (via `SQL` parameter interpolation):

```sql
SELECT alarm.id, event.id
  FROM calendar_event AS event
  JOIN calendar_alarm_calendar_event_rel AS event_alarm_rel
    ON event.id = event_alarm_rel.calendar_event_id
  JOIN calendar_alarm AS alarm
    ON event_alarm_rel.calendar_alarm_id = alarm.id
 WHERE alarm.alarm_type = %s
   AND event.active
   AND event.start - CAST(alarm.duration || ' ' || alarm.interval AS Interval) >= %s
   AND event.start - CAST(alarm.duration || ' ' || alarm.interval AS Interval) < %s
```

The SQL computes the alarm trigger time dynamically using `event.start - INTERVAL`. For a 1-hour SMS alarm on an event starting at 10:00 AM, the alarm fires at 9:00 AM. The SQL matches this row when the cron runs between 9:00 AM and 10:00 AM.

**L4 Edge Case -- Missed Alarms:** If the cron has not run for an extended period (e.g., Odoo server was down), the SQL uses `lastcall` as the lower bound. All alarms whose trigger time falls between `lastcall` and `now` will be detected and sent. However, alarms whose trigger time was before `lastcall` (even by a few minutes) are **silently skipped**. This is by design: "The attendees receive an invitation for any new event already" (comment in source).

**L4 Edge Case -- Recurring Events:** For recurring events, a single SQL row only matches the first occurrence of a series (since `event.start` on recurring event lines is the start of that specific occurrence). After processing each alarm batch, `_setup_event_recurrent_alarms()` calls `event.recurrence_id.with_context(date=next_date)._setup_alarms()` to schedule the next `ir.cron.trigger` for the next occurrence in the series. This is the Odoo 19 `trigger_id` mechanism that replaces generic scheduler calls.

---

### 3. `CalendarEvent` -- `calendar.event`

**File:** `models/calendar_event.py`

Extends `calendar.event` with three additions.

#### `_do_sms_reminder(alarms)`

```python
def _do_sms_reminder(self, alarms):
    """ Send an SMS text reminder to attendees that haven't declined the event """
    for event in self:
        declined_partners = event.attendee_ids.filtered_domain([('state', '=', 'declined')]).partner_id
        for alarm in alarms:
            partners = event._mail_get_partners()[event.id].filtered(
                lambda partner: partner.phone_sanitized and partner not in declined_partners
            )
            if event.user_id and not alarm.notify_responsible:
                partners -= event.user_id.partner_id
            event._message_sms_with_template(
                template=alarm.sms_template_id,
                template_fallback=_("Event reminder: %(name)s, %(time)s.",
                                     name=event.name, time=event.display_time),
                partner_ids=partners.ids,
                put_in_queue=False
            )
```

**L2 Breakdown:**

| Step | Code | Purpose |
|------|------|---------|
| 1 | `declined_partners = event.attendee_ids.filtered_domain([('state', '=', 'declined')]).partner_id` | Collect partner records for all attendees who clicked "Decline" |
| 2 | `event._mail_get_partners()` | Inherited from `mail.thread.mixin` -- returns a `res.partner` recordset per event ID (handles the organizer + attendees) |
| 3 | `.filtered(lambda p: p.phone_sanitized and p not in declined_partners)` | Remove partners with no valid phone number and those who declined |
| 4 | `if event.user_id and not alarm.notify_responsible: partners -= event.user_id.partner_id` | Optionally exclude the event owner/organizer from receiving the SMS |
| 5 | `_message_sms_with_template(...)` | Dispatch the SMS immediately |

**L3 `_mail_get_partners` context:** This method (from `mail.thread.mixin`) returns the union of the event's `partner_ids` (attendees) and `user_id.partner_id` (organizer), even if the organizer is not listed as an attendee. The organizer is included by default, but step 4 removes them if `alarm.notify_responsible = False` (the default).

**L4 `phone_sanitized` field:** This is a computed field on `res.partner` (from the `phone_validation` mixin) that strips non-digit characters and validates the resulting number against the partner's country formatting rules. A partner without a phone number or with an invalid format has `phone_sanitized = False`. Such partners are **silently excluded** -- no error is raised and no SMS is queued. This is intentional design to avoid SMS gateway rejections for malformed numbers.

**L4 `put_in_queue=False`:** This parameter bypasses the SMS queue and sends synchronously. Since `_do_sms_reminder` is called from a cron context where a response does not need to be returned to a user, sending synchronously is acceptable. However, for high-volume deployments with many simultaneous SMS alarms, this could create a performance bottleneck because `_message_sms_with_template` makes an HTTP call to the SMS gateway for each partner individually. The alternative (`put_in_queue=True`) would batch into `sms.sms` pending records for async processing by `sms.sms.send` cron.

**L4 `notify_responsible` behavior:** The `notify_responsible` field is defined on `calendar.alarm` (in the base calendar module) as a `Boolean` defaulting to `False`. However, the `onchange` in the base alarm model (`_onchange_duration_interval`) resets `notify_responsible = False` whenever `alarm_type` is `'email'` or `'notification'`. There is **no such guard for `'sms'`** -- meaning for SMS alarms, `notify_responsible` remains settable to `True`. When `True`, the event organizer **receives the SMS too**; when `False` (default), the organizer is excluded. This mirrors the email reminder logic where the author is included by `_notify_attendees(notify_author=True)`.

**L4 Edge Case -- Multiple SMS Alarms on Same Event:** If an event has two SMS alarms (e.g., 1-hour and 24-hour) that both trigger in the same cron run, the alarm manager calls `_do_sms_reminder` twice with different alarms. Each call uses the alarm's specific `sms_template_id`, so two different SMS templates can be sent for the same event. The test (`test_send_reminder_match_both_events`) explicitly validates this.

**L4 Edge Case -- `sms_template_id` is `False`:** If the alarm was created with `alarm_type = 'sms'` but `_compute_sms_template_id` failed to resolve the default template XML ID, `alarm.sms_template_id` is `False`. When `_message_sms_with_template` is called with `template=False`, it falls back to `template_fallback` -- the plain text string `"Event reminder: {name}, {time}."`. This ensures SMS delivery is never blocked by a missing template.

#### `action_send_sms()`

```python
def action_send_sms(self):
    if not self.partner_ids:
        raise UserError(_("There are no attendees on these events"))
    return {
        'type': 'ir.actions.act_window',
        'name': _("Send SMS"),
        'res_model': 'sms.composer',
        'view_mode': 'form',
        'target': 'new',
        'context': {
            'default_composition_mode': 'mass',
            'default_res_model': 'res.partner',
            'default_res_ids': self.partner_ids.ids,
            'default_mass_keep_log': True,
        },
    }
```

**L2:** Called directly from the **Send SMS** button on the event form and list view. Opens the `sms.composer` wizard in mass composition mode pre-filled with all event attendees as recipients. `default_mass_keep_log=True` records the SMS in the mail.message log for each partner (visible in the chatter).

**L4 Security / UX:** The `UserError` guard checks `self.partner_ids` (the Many2many of `res.partner` on `calendar.event`). If the event has no attendees, no SMS can be sent, so an error is raised rather than opening an empty composer. The check runs on `self` which may be a recordset of multiple events in the list view case; if any event in the set has no partners, the error is raised.

**L4 UI Integration:** The button is registered in `views/calendar_views.xml` with `invisible="not user_can_edit"`, which checks if the current user has write access to the event. This prevents read-only users from sending SMS at will.

#### `_get_trigger_alarm_types()`

```python
def _get_trigger_alarm_types(self):
    return super()._get_trigger_alarm_types() + ['sms']
```

**L2:** Appends `'sms'` to the base return value `['email']`. This means when `calendar.event` is asked "which alarm types trigger notifications?", it now answers `['email', 'sms']`. The base `calendar.event` uses this method to filter which alarms to display in the "Reminders" kanban/list section of the event form. Without this extension, SMS-type alarms would not appear as selectable options in the UI.

**L3:** The base `calendar.event` also calls `_get_trigger_alarm_types()` internally to determine which alarms should be registered with the cron scheduler in `_setup_alarms()`. Adding `'sms'` here ensures SMS alarms are included in that scheduling logic.

---

## Default SMS Template

**XML ID:** `calendar_sms.sms_template_data_calendar_reminder`
**File:** `data/sms_data.xml`
**Loading:** `noupdate=1` -- the template is installed once and not overwritten on subsequent module upgrades unless explicitly reset.

```xml
<record id="sms_template_data_calendar_reminder" model="sms.template">
    <field name="name">Calendar Event: Reminder</field>
    <field name="model_id" ref="calendar.model_calendar_event"/>
    <field name="body">Event reminder: {{ object.name }}, {{ object.get_display_time_tz(object.partner_id.tz) }}</field>
</record>
```

**L2 Template Rendering:** The Jinja2 body uses:
- `{{ object.name }}` -- the event's display name
- `{{ object.get_display_time_tz(object.partner_id.tz) }}` -- a helper method that formats the event time in the **attendee's timezone** (not the organizer's). `object.partner_id` here refers to `event.partner_id`, a Many2one to `res.partner` representing the event's main contact/client on the event record (distinct from `partner_ids` which is the attendee list).

**L4 Edge Case -- `partner_id` on `calendar.event`:** This field is `user_id.partner_id` (a related field). It may be empty if the event has no organizer (`user_id` is False). `get_display_time_tz(None)` would likely raise an AttributeError or return a default. However, the template rendering is wrapped in a try/except in the SMS engine, so a rendering failure falls back to the `template_fallback` string rather than blocking the SMS send.

**L4 Upgrade Note (Odoo 18 to 19):** The template body has not changed between Odoo 18 and 19. The module structure and API are identical.

---

## Views

**File:** `views/calendar_views.xml`

### Form View Extension -- `calendar.alarm`

```xml
<field name="sms_template_id" invisible="alarm_type != 'sms'" required="alarm_type == 'sms'"
    context="{'default_model': 'calendar.event'}"/>
```

**L2:** The SMS template field is:
- `invisible` when alarm type is not SMS (cleaner UI; the field is meaningless for email/notification types)
- `required` when alarm type IS SMS (enforced at the UI level; prevents saving an SMS alarm without a template)
- `context={'default_model': 'calendar.event'}` pre-fills the model context when opening the template selection dropdown, filtering to relevant templates

### Event Form View Extension

```xml
<button name="action_send_sms" help="Send SMS to attendees" type="object"
    string="SMS" icon="fa-mobile" invisible="not user_can_edit"/>
```

**L2:** The SMS button appears in the `send_buttons` div alongside existing "Invite" / "Send Invitation" buttons. `icon="fa-mobile"` uses a FontAwesome icon. `user_can_edit` is a computed Boolean on `calendar.event` (from `mail.thread`) that reflects whether the current user has write access.

```xml
<field name="phone" position="attributes">
    <attribute name="options">{'enable_sms': false}</attribute>
</xpath>
```

**L2:** Disables the SMS linkify feature on the event's phone field. This prevents the SMS composition popup from appearing when clicking a phone number in the event form. This is intentional to avoid confusion: the event form's phone field is for the event's related contact, not for sending SMS reminders to attendees.

### Event List View Extension

```xml
<button name="action_send_sms" type="object" string="Send SMS"/>
```

**L2:** Adds the Send SMS button to the list view header. When multiple events are selected, the button is active and calls `action_send_sms` on the recordset.

---

## Cron Job Integration

| Cron | Model | Interval | Action |
|------|-------|----------|--------|
| `ir_cron_scheduler_alarm` | `calendar.alarm_manager` | Every minute | Calls `_send_reminder()` |

The cron job itself lives in the `calendar` module and is not overridden by `calendar_sms`. The module only overrides the `_send_reminder` method, so the cron schedule and trigger remain unchanged.

**L4 Cron `lastcall` Context:** The cron passes `lastcall` (the timestamp of its previous run) via the ORM context. `_get_events_by_alarm_to_notify` uses `lastcall` as the lower bound of the alarm trigger window:

```python
lastcall = self.env.context.get('lastcall', False) or fields.Date.today() - timedelta(weeks=1)
```

If `lastcall` is absent from the context (e.g., called manually outside of cron), the lower bound defaults to 1 week ago, meaning up to 1 week of missed SMS alarms could theoretically be sent at once.

---

## Test Coverage

**File:** `tests/test_calendar_sms.py`

`TestCalendarSms` inherits from `SMSCommon` (from `sms.tests.common`), which provides:
- `mockSMSGateway()` context manager: intercepts all `_send_sms` calls and stores them in `self._sms`
- `assertSMS()` assertion: validates recipient, sanitized number, state, and content

### `test_attendees_with_number`

**Scenario:** Event with two attendees: `partner_phone` (valid number) and `partner_no_phone` (no phone set).

```python
self.event._do_sms_reminder(self.event.alarm_ids)
self.assertEqual(len(self._sms), 1, "There should be only one partner retrieved")
```

**Validates:** Partners without a sanitized phone number are silently excluded. Only one SMS is sent to `partner_phone`.

### `test_send_reminder_match_both_events`

**Scenario:** Two events (`event_1h` and `event_24h`), each with two SMS alarms (1h and 24h), each alarm having its own custom template (`sms_template_1h` and `sms_template_24h`). `event_1h` has `partner_phone` and a duplicate `event_1h_dup` with `partner_phone_3`. `event_24h` has `partner_phone_2`.

```python
lastcall = fields.Datetime.now() - timedelta(hours=1)
self.env['calendar.alarm_manager'].with_context(lastcall=lastcall)._send_reminder()
self.assertEqual(len(self._sms), 3)
```

**Expected sends:**
1. `partner_phone` receives `sms_template_1h` body (from `event_1h` + 1h alarm)
2. `partner_phone_3` receives `sms_template_1h` body (from `event_1h_dup` + 1h alarm)
3. `partner_phone_2` receives `sms_template_24h` body (from `event_24h` + 24h alarm)

**Validates:**
- The 1-hour alarm on `event_1h` triggers because its trigger time (event start - 1h = now - 30min) is within `[lastcall, now]`
- The 24-hour alarm on `event_24h` triggers because its trigger time (event start - 24h = now - 30min) is within `[lastcall, now]`
- The 24-hour alarm on `event_1h` does NOT trigger because its trigger time (event start - 24h = now + 23h30m) is after `now`
- The 1-hour alarm on `event_24h` does NOT trigger because its trigger time (event start - 1h = now + 22h30m) is after `now`
- Custom templates are correctly associated with their respective alarms

---

## Security Considerations

| Concern | Detail |
|---------|--------|
| **SMS Cost** | Each SMS costs money (SMS gateway credits). The `calendar.alarm_manager` cron runs every minute and could send SMSs for many events. Rate-limiting should be considered at the SMS gateway or via `ir.config_parameter` (`mail.mail_force_send_limit` analog for SMS does not exist by default). |
| **Phone Number Exposure** | SMS is sent to attendees' phone numbers stored on `res.partner`. Users with read access to `calendar.event` can see attendee names but not phone numbers unless they also have `res.partner` read access. |
| **ACL** | `calendar.event` ACLs govern who can create events with SMS alarms. The `user_can_edit` invisible check on the Send SMS button prevents read-only users from triggering SMS sends. |
| **SMS Log** | When sending via `action_send_sms` with `default_mass_keep_log=True`, the SMS content is recorded in `mail.message` linked to each partner's record, providing an audit trail. |
| **No Recipient Validation at Alarm Creation** | An SMS alarm can be created without validating that any attendee has a phone number. The failure is silent (the partner is simply excluded from the SMS send). |

---

## L4 Summary: Odoo 18 to 19 Changes

The `calendar_sms` module is structurally unchanged between Odoo 18 and Odoo 19. The implementation is identical. The key observable behaviors are:

- The `alarm_type` extension via `selection_add` is the same pattern used in Odoo 16+
- The `readonly=False, store=True` compute pattern for `sms_template_id` is consistent with the approach used for `mail_template_id` in the calendar module
- The cron-based reminder dispatch model (`_send_reminder` per type) is unchanged since its introduction in Odoo 12+
- The Odoo 19 `ir.cron.trigger`-based alarm scheduling in the base `calendar` module does not change `calendar_sms` behavior

---

## Related Documentation

- [[Modules/Calendar]] -- `calendar.event`, `calendar.alarm`, `calendar.alarm_manager`, cron scheduler
- [[Modules/SMS]] -- `sms.template`, `sms.composer`, SMS gateway, `phone_sanitized`
- [[Core/API]] -- `@api.depends`, compute fields, `readonly=False` on computed fields
- [[Patterns/Inheritance Patterns]] -- `_inherit` extension pattern vs. `_inherits` delegation
