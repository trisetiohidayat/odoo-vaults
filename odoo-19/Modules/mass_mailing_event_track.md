# Mass Mailing Event Track

## Overview
- **Name:** Mass mailing on track speakers
- **Category:** Marketing/Email Marketing
- **Summary:** Mass mail event track speakers
- **Version:** 1.0
- **Depends:** `website_event_track`, `mass_mailing`
- **Auto-install:** True
- **License:** LGPL-3

## Description
Bridge module that adds mass mailing capabilities to event track speakers. Provides a button on event forms to email speakers about their scheduled talks.

## Models

### `event.event` (extends `event.event`)
#### Methods
- `action_mass_mailing_track_speakers()`: Opens mass mailing form targeted at speakers of confirmed (non-canceled) tracks for this event

### `event.track` (extends `event.track`)
- `_mailing_enabled = True`: Activates mailing on tracks

#### Methods
- `_mailing_get_default_domain()`: Excludes canceled tracks

## Related
- [Modules/mass_mailing](odoo-18/Modules/mass_mailing.md) - Base mass mailing module
- [Modules/website_event_track](odoo-18/Modules/website_event_track.md) - Event track/speaker management
