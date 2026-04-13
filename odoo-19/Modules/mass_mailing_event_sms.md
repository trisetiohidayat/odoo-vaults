# Mass Mailing Event SMS

## Overview
- **Name:** Event Attendees SMS Marketing
- **Category:** Marketing/Email Marketing
- **Summary:** SMS marketing on event attendees
- **Version:** 1.0
- **Depends:** `event`, `mass_mailing`, `mass_mailing_event`, `mass_mailing_sms`, `sms`
- **Auto-install:** True
- **License:** LGPL-3

## Description
Extends `mass_mailing_event` to support SMS campaigns for event attendees. Uses the mixed (SMS+email) mailing form view.

## Models

### `event.event` (extends `event.event`)
#### Methods
- `action_mass_mailing_attendees()`: Opens the mixed SMS/email mailing form (overrides to set `view_id`)
- `action_invite_contacts()`: Opens the mixed SMS/email mailing form for contacts

## Related
- [Modules/mass_mailing_event](Modules/mass_mailing_event.md) - Event email mailing
- [Modules/mass_mailing_sms](Modules/mass_mailing_sms.md) - SMS marketing
- [Modules/event](Modules/event.md) - Event management
