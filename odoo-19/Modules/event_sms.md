# SMS on Events

## Overview
- **Name**: SMS on Events
- **Category**: Marketing/Events
- **Depends**: `event`, `sms`
- **Summary**: Schedule and send SMS reminders for event registrations
- **Auto-install**: True

## Key Features
- Adds **SMS** as a notification type option for event mail schedulers
- Links SMS templates to event registration reminders
- Supports event-level and event-type-level SMS scheduling

## Extended Models

### `event.mail` (extended)
- `notification_type` - Added `sms` option alongside `mail`
- `template_ref` - Added `sms.template` to the reference selection
- `_compute_notification_type()` - Auto-sets to `sms` when template is an SMS template
- `_execute_event_based_for_registrations()` - Handles SMS sending via `_send_sms()`
- `_send_sms()` - Sends SMS to registrations using `_message_sms_schedule_mass()`
- `_template_model_by_notification_type()` - Maps `sms` to `sms.template`

### `event.mail.registration` (extended)
- `_execute_on_registrations()` - For SMS schedulers, calls `_send_sms()` on each registration; marks `mail_sent = True`

### `event.type.mail` (extended)
- `notification_type` - Added `sms` option
- `template_ref` - Added `sms.template` reference
- `_compute_notification_type()` - Auto-detects SMS templates

### `sms.template` (extended)
- `_search()` - Supports `filter_template_on_event` context to restrict to `event.registration` model
- `unlink()` - Cascades deletion to linked `event.mail` and `event.type.mail` records

## Data
- `data/sms_data.xml` - SMS templates for events (e.g., registration confirmation, reminder)

## Related
- [Modules/event](Modules/event.md) - Event management
- [Modules/sms](Modules/sms.md) - SMS sending
