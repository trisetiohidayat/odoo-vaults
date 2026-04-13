# Mass Mailing Event Track SMS

## Overview
- **Name:** Track Speakers SMS Marketing
- **Category:** Marketing/Email Marketing
- **Summary:** SMS marketing on event track speakers
- **Version:** 1.0
- **Depends:** `mass_mailing`, `mass_mailing_sms`, `sms`, `website_event_track`
- **Auto-install:** True
- **License:** LGPL-3

## Description
Extends `mass_mailing_event_track` to support SMS campaigns for event track speakers. Uses the mixed (SMS+email) mailing form view.

## Models

### `event.event` (extends `event.event`)
#### Methods
- `action_mass_mailing_track_speakers()`: Opens the mixed SMS/email mailing form for speakers (overrides to set `view_id`)

## Related
- [Modules/mass_mailing_event_track](mass_mailing_event_track.md) - Track email mailing
- [Modules/mass_mailing_sms](mass_mailing_sms.md) - SMS marketing
- [Modules/website_event_track](website_event_track.md) - Event track management
