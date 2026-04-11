---
Module: mass_mailing_slides
Version: 18.0.0
Type: addon
Tags: #odoo18 #mass_mailing #slides #elearning
---

## Overview

Adds mass mailing action to `slide.channel` (e-learning courses). Opens a `mailing.mailing` form targeting all members subscribed to the channel.

**Depends:** `mass_mailing`, `slide`, `mass_mailing_sms`

**Key Behavior:** Domain targets partners who are members of the channel via `slide_channel_ids`.

---

## Models

### `slide.channel` (Inherited)

**Inherited from:** `slide.channel`

| Method | Returns | Note |
|--------|---------|------|
| `action_mass_mailing_attendees()` | `ir.actions.act_window` | Targets `res.partner` domain based on channel membership |

**Context defaults set:**
- `default_mailing_model_id` → `res.partner`
- `default_mailing_domain` → `[('slide_channel_ids', 'in', self.ids)]`
- `name` → `"Mass Mail Course Members"`
