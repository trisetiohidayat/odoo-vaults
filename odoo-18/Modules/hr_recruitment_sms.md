---
Module: hr_recruitment_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_recruitment_sms
---

## Overview
Recruitment - SMS. Bridge module between `hr_recruitment` and `sms`. Enables sending SMS messages to job applicants and candidates directly from the HR Recruitment form. No Python models — purely a view/action bridge. `auto_install=True`.

## Models
**No Python model files.** The module provides only XML view extensions.

**What it does:**
- `views/hr_applicant_views.xml`: Adds SMS action button to `hr.applicant` form (links to `sms.sms_send_action`)
- `views/hr_candidate_views.xml`: Adds SMS action button to `hr.candidate` form

## Security
- Standard `hr_recruitment` and `sms` ACLs apply
- No custom ACL files or ir.rules in this module

## Critical Notes
- **Pure XML bridge** — no Python code, no data files beyond views
- **SMS sending:** Uses the standard `sms.sms_send_action` wizard; the candidate/applicant's phone is pre-filled from `partner_phone` or `mobile`
- **`auto_install=True`** — automatically installs when both `hr_recruitment` and `sms` are present
- **v17→v18:** No changes to this module's architecture
