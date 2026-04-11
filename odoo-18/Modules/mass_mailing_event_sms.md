---
Module: mass_mailing_event_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #mass_mailing #event #sms
---

## Overview

Bridges `mass_mailing_sms` with the event module. Overrides `action_mass_mailing_attendees` and `action_invite_contacts` on `event.event` to use the mixed SMS/email form view (`mailing_mailing_view_form_mixed`) instead of the default mail form.

**Depends:** `mass_mailing_sms`, `event`, `mass_mailing`

**Key Behavior:** Forces use of mixed form view for event mailing actions when SMS is enabled.

---

## Models

### `event.event` (Inherited)

**Inherited from:** `event.event`

Two action overrides force the SMS-aware mixed form view.

| Method | Returns | Note |
|--------|---------|------|
| `action_mass_mailing_attendees()` | `ir.actions.act_window` | Sets `view_id` to mixed mailing form |
| `action_invite_contacts()` | `ir.actions.act_window` | Sets `view_id` to mixed mailing form |
