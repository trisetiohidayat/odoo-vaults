# Recruitment SMS (hr_recruitment_sms)

## Overview
- **Category:** Human Resources/Recruitment
- **Depends:** `hr_recruitment`, `sms`
- **Auto-install:** True
- **License:** LGPL-3

Adds SMS capability to the recruitment module. HR can send SMS messages to job applicants directly from the applicant form.

## Models

### `hr.applicant` (inherited via `hr_recruitment`)
The applicant form gets SMS action buttons via the `sms` module integration.

## Key Features
- SMS composer accessible from the applicant form view
- Mass SMS composition supported for bulk applicant outreach
- Works with `sms.template` for templated recruitment SMS
- Uses `mobile_phone` or `partner_phone` as the destination number field
- `mail.thread.phone` mixin (from `hr_recruitment`) provides phone number formatting and SMS sending capabilities

## Related
- [Modules/hr_recruitment](modules/hr_recruitment.md) — Recruitment base
- [Modules/sms](modules/sms.md) — SMS module
- [Modules/hr_recruitment_skills](modules/hr_recruitment_skills.md) — Recruitment + Skills
