---
Module: sms_twilio
Version: 18.0.0
Type: addon
Tags: #odoo18 #sms_twilio #sms
---

## Overview

`sms_twilio` integrates Odoo with Twilio's SMS API as an alternative to Odoo's own IAP SMS service. Enables per-company SMS provider configuration. Twilio-specific tracking uses `sms_twilio_sid` on the tracker record. Includes a `sms.twilio.number` model for managing multiple sender numbers with country routing. Supports tokenized SMS send with Twilio status callbacks.

## Models

### res.company (extends base)
**Inheritance:** `res.company` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| sms_provider | Selection | `'iap'` (default, Send via Odoo) or `'twilio'` (Send via Twilio) |
| sms_twilio_account_sid | Char | Twilio Account SID, must start with 'AC' and be 34 chars alphanumeric (groups=base.group_system) |
| sms_twilio_auth_token | Char | Twilio Auth Token (groups=base.group_system) |
| sms_twilio_number_ids | One2many | `sms.twilio.number` records linked to company |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_sms_api_class | self | class | Returns `SmsApiTwilio` if `sms_provider=='twilio'`, else delegates to `super()` |
| _assert_twilio_sid | self | None | Validates Account SID format: must be 'AC' + 32 alphanumeric chars. Raises `UserError` if invalid |
| _action_open_sms_twilio_account_manage | self | dict (action) | Opens `sms.twilio.account.manage` wizard form |

### sms.twilio.number
**Inheritance:** Standalone model (`_name = 'sms.twilio.number'`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| company_id | Many2one | `res.company`, required, cascade delete, default=env.company |
| sequence | Integer | Ordering (default=1) |
| number | Char | Twilio phone number, required |
| country_id | Many2one | `res.country`, required |
| country_code | Char | Related from country_id.code (readonly) |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_display_name | self | None | Sets display_name = `"{number} ({country_name})"` |
| action_unlink | self | dict (action) | Deletes the number record and returns to account management wizard |

### sms.sms (extends base)
**Inheritance:** `sms.sms` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| sms_twilio_sid | Char | Related from `sms_tracker_id.sms_twilio_sid` (computed, depends on `sms_tracker_id`) |
| record_company_id | Many2one | `res.company` — company for routing (populated from `record_company_id` or `mail_message_id.record_company_id` or `_get_sms_company()`) |

**Additional failure_type values:**
- `twilio_authentication` — Authentication error
- `twilio_callback` — Incorrect callback URL
- `twilio_from_missing` — Missing From number
- `twilio_from_to` — From/To identical

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| create | vals_list | recordset | Sets `record_company_id` from context or `self.env.company` |
| fields_get | allfields, attributes | dict | **Safe selection update:** In stable versions, selection values may be missing; this method dynamically adds `twilio_*` failure types to the selection by calling `ir.model.fields.selection._update_selection()` and clearing the registry cache |
| _split_by_api | self | generator | Overrides to route Twilio SMS to `SmsApiTwilio`. Groups SMS by company; if `company.sms_provider == 'twilio'` → uses `SmsApiTwilio`, else passes to `super()` for IAP fallback. Yields `(sms_api, company_sms)` tuples |
| _get_sms_company | self | recordset | Returns `mail_message_id.record_company_id` or `record_company_id` or `super()` fallback |
| _get_batch_size | self | int | If any company uses Twilio, returns `ir.config_parameter` batch size (default 10), else `super()` |
| _handle_call_result_hook | self, results | None | Stores `sms_twilio_sid` from API response onto `sms_tracker_id` record. Processes Twilio results separately from non-Twilio |

### sms.tracker (extends base)
**Inheritance:** `sms.tracker` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| sms_twilio_sid | Char | Twilio SMS SID (readonly) |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _action_update_from_twilio_error | self, sms_status, error_code, error_message | None | Maps Twilio error codes to failure types: 30002→expired, 30003→invalid_destination, 30004→rejected, 30005→invalid_destination, 30006→not_allowed, 30007→rejected, 30008→not_delivered. Passes error message as known failure reason context |

### mail.notification (extends base)
**Inheritance:** `mail.notification` (classic `_inherit`)

**Additional failure_type values:** Same four Twilio-specific values as `sms.sms`.

**Notes:** Same `fields_get` safe selection update pattern as `sms.sms`.

### sms.composer (extends base)
**Inheritance:** `sms.composer` (classic `_inherit`)

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _prepare_mass_sms_values | self, records | list | Extends parent to set `record_company_id` on each SMS value dict, picking company from `record.company_id` or `record.record_company_id` or `self.env.company` |

### res.config.settings (extends base)
**Inheritance:** `res.config.settings` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| sms_provider | Selection | Related from `company_id.sms_provider` (required, readonly=False) |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| action_open_sms_twilio_account_manage | self | dict | Delegates to `company_id._action_open_sms_twilio_account_manage()` |

## Security / Data

**Security:** `sms_twilio_account_sid`, `sms_twilio_auth_token` fields restricted to `base.group_system`. SMS Twilio number records accessible to all users within the company.

**Data:** None.

## Critical Notes

- **Multi-company routing:** SMS are grouped by company and routed to Twilio or IAP based on each company's `sms_provider` setting.
- **Twilio SID tracking:** Each SMS's tracker record stores the Twilio Message SID (`sms_twilio_sid`), enabling Twilio status callbacks to update the correct tracker.
- **Country-based sender routing:** `get_twilio_from_number()` selects the appropriate Twilio sender number based on the destination country's prefix.
- **Status callbacks:** Twilio POSTs status updates to `/sms_twilio/status/{uuid}` which update the tracker state.
- **Batch size control:** Twilio SMS uses configurable batch size (default 10) via `ir.config_parameter('sms_twilio.session.batch.size')` — lower than IAP default to respect Twilio rate limits.
- **v17→v18:** No breaking changes. `fields_get` safe update pattern prevents crashes when backporting.
- **fields_get safe updates:** The dynamic selection update in `fields_get` is specifically noted as a workaround for stable branch backports where selection values may be missing from translations.
