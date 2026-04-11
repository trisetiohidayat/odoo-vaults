---
Module: website_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sms #sms #website
---

## Overview

**Module:** `website_sms`
**Depends:** `sms`, `website` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/website_sms/`
**License:** LGPL-3
**Purpose:** Enables SMS composition from website visitor records in the backend. Adds a "Send SMS" button to the visitor detail view; requires the visitor to have a linked partner with a phone or mobile number.

---

## Models

### `website.visitor` (models/website_visitor.py, 8–41)

Inherits: `website.visitor`

| Method | Line | Description |
|---|---|---|
| `_check_for_sms_composer()` | 11 | Returns `bool(self.partner_id and (self.partner_id.mobile or self.partner_id.phone))`. Used to gate the SMS action. The docstring notes this is overridable for inheritance (e.g., leads that update visitor model). |
| `_prepare_sms_composer_context()` | 17 | Returns dict: `default_res_model='res.partner'`, `default_res_id=self.partner_id.id`, `default_composition_mode='comment'`, `default_number_field_name='mobile'` or `'phone'` (prefers mobile). |
| `action_send_sms()` | 25 | `ensure_one()`. Validates `_check_for_sms_composer()` → raises `UserError` if no contact/number. Opens `sms.composer` form in `target='new'` modal with visitor's partner context. |

---

## Architecture

The SMS composer is opened in `'comment'` mode (direct send, no template selection). The number is taken from `partner_id.mobile` if available, falling back to `partner_id.phone`. The composer targets `res.partner` (the visitor's partner), not the visitor record itself.

---

## Security / Data

No `ir.model.access.csv`. No data XML files.

---

## Critical Notes

- Visitor must have a linked `partner_id` with at least one of `mobile` or `phone` to send SMS.
- `_check_for_sms_composer` is designed for inheritance override — subclasses (e.g., CRM lead visitors) can customize the check.
- v17→v18: No breaking changes.