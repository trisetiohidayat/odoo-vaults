---
Module: mail_bot_hr
Version: 18.0
Type: addon
Tags: #mail, #bot, #hr, #odoobot, #employee
---

# mail_bot_hr — OdooBot HR Bridge

Bridge module between `hr` and `mail_bot`. Adds OdooBot state and notification fields to the HR employee user form, enabling OdooBot conversation features for HR users.

**Depends:** `mail_bot`, `hr`

**Source path:** `~/odoo/odoo18/odoo/addons/mail_bot_hr/`

## Key Extension

### `res.users` (extends via `hr`)

This module extends the user form (from `hr` module) with OdooBot fields:
- OdooBot state (online/away/offline)
- OdooBot notification preferences for HR employees

The primary contribution is the XML view extension in `views/res_users_views.xml` which adds OdooBot presence fields to the HR user form sheet.

**Note:** This is a thin bridge — the main logic lives in `mail_bot` and `hr`. This module only links them together with view additions and ensures OdooBot works correctly for users managed by HR.
