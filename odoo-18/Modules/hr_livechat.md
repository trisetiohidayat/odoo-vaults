---
Module: hr_livechat
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_livechat
---

## Overview
Bridge module between HR and Livechat. Links livechat channels (im_livechat) to employees so that the employee's channel_operator partner can be associated with their HR employee record. This enables showing the HR employee card/info alongside livechat sessions. `auto_install=True`.

## Models
**No Python model files defined.** The module has no `models/` directory. The bridge is entirely implemented through view XML (`views/discuss_channel_views.xml`) which adds a Many2one field `operator_id` (pointing to `hr.employee`) to the livechat channel form.

## Views
File: `views/discuss_channel_views.xml` — extends `discuss.channel` form to add:
- `operator_id` Many2one → `hr.employee` on the channel form
- This allows linking a livechat operator to their employee record

## Security
- Standard `im_livechat` and `hr` ACLs apply
- No custom ir.rules or ACL CSVs in this module

## Critical Notes
- **No Python models** — pure XML bridge; the field is added by the view inheritance XML
- **auto_install=True** — auto-installed when both `hr` and `im_livechat` are present
- The actual operator linking is done via `channel.livechat_operator_id` (from im_livechat) → `hr.employee.work_contact_id`
- **v17→v18:** No model changes; same architecture
