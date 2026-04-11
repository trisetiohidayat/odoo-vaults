---
Module: mass_mailing_event_track_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #mass_mailing #event #sms
---

## Overview

Bridges `mass_mailing_event_track` with SMS support. Overrides `action_mass_mailing_track_speakers` on `event.event` to use the mixed SMS/email form view.

**Depends:** `mass_mailing_event_track`, `mass_mailing_sms`, `event`

**Key Behavior:** Same override pattern as `mass_mailing_event_sms` — forces the SMS-aware mixed mailing form view for track speaker mailings.

---

## Models

### `event.event` (Inherited)

**Inherited from:** `event.event`

| Method | Returns | Note |
|--------|---------|------|
| `action_mass_mailing_track_speakers()` | `ir.actions.act_window` | Sets `view_id` to `mailing_mailing_view_form_mixed` |
