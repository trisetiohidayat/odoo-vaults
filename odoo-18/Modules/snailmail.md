---
Module: snailmail
Version: 18.0.0
Type: addon
Tags: #odoo18 #snailmail #postal
---

## Overview

`snailmail` sends physical letters via postal mail through Odoo's IAP snailmail service. Converts any report to a PDF, applies A4 formatting and margin whitewashing for postal standards, optionally adds a cover page, and submits to `iap-snailmail.odoo.com` for printing and postage. Tracks letter state (pending/sent/error/canceled) with associated mail.message thread notifications.

## Models

### snailmail.letter
**Inheritance:** Standalone model (`_name = 'snailmail.letter'`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| user_id | Many2one | `res.users` — who sent the letter |
| model | Char | Model name of the related document (required) |
| res_id | Integer | ID of the related document (required) |
| partner_id | Many2one | `res.partner` — recipient (required) |
| company_id | Many2one | `res.company` — sending company (required, readonly, default=self.env.company.id) |
| report_template | Many2one | `ir.actions.report` — optional report to attach |
| attachment_id | Many2one | `ir.attachment` — generated PDF attachment (cascade delete, indexed) |
| attachment_datas | Binary | Related from `attachment_id.datas` |
| attachment_fname | Char | Related from `attachment_id.name` |
| color | Boolean | Print in color (default from `company_id.snailmail_color`) |
| cover | Boolean | Add cover page (default from `company_id.snailmail_cover`) |
| duplex | Boolean | Print both sides (default from `company_id.snailmail_duplex`) |
| state | Selection | `pending` (default), `sent`, `error`, `canceled` — readonly |
| error_code | Selection | Error code from ERROR_CODES list |
| info_msg | Html | Information/human-readable error message |
| reference | Char | Computed `model,res_id` string (readonly, stored=False) |
| message_id | Many2one | `mail.message` — associated status message (indexed) |
| notification_ids | One2many | `mail.notification` records (inverse on `letter_id`) |
| street, street2, zip, city | Char | Letter address fields (copied from partner at creation time) |
| state_id | Many2one | `res.country.state` |
| country_id | Many2one | `res.country` |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_display_name | self | None | Sets `display_name = attachment.name + partner.name` if attachment exists, else partner name |
| _compute_reference | self | None | Sets `reference = model,res_id` |
| create | vals_list | recordset | **Overridden:** Auto-creates `mail.message` (type='snailmail'), copies address from partner, creates `mail.notification` entries for each letter. Calls `attachment_id.check('read')` |
| write | vals | bool | Calls `super()`, re-checks attachment read access if `attachment_id` changed |
| _fetch_attachment | self | ir.attachment | Generates PDF from `report_template` or context `report_name`. Handles A4 format validation, external layout override (converts bubble/wave/folder layouts to standard for postal compatibility), white margin overwrite, cover page append. Stores report as binary attachment |
| _count_pages_pdf | bin_pdf | int | Counts PDF pages via regex on `/Count` object |
| _snailmail_create | route | dict | Builds the IAP request payload: `account_token`, `dbuuid`, `documents[]` (each with letter_id, res_model, res_id, address, return_address, pdf_bin/pages, company_logo), `options` (color, cover, duplex, currency_name). Skips letters with invalid recipient name |
| _get_error_message | error | str | Maps error codes to human-readable messages with IAP credit links |
| _get_failure_type | error | str | Maps error codes to `failure_type` values for notifications |
| _snailmail_print | immediate=True | None | Validates addresses, then calls `_snailmail_print_valid_address()` for valid letters. Invalid ones get `_snailmail_print_invalid_address()` |
| _snailmail_print_invalid_address | self | None | Marks letter as error with `MISSING_REQUIRED_FIELDS`, updates notifications to exception state, calls `_notify_message_notification_update()` |
| _snailmail_print_valid_address | self | None | Calls IAP endpoint, handles response: success → sets sent state + notification sent; error → sets error state + notification exception. Commits after each letter to prevent double-send on rollback |
| snailmail_print | self | None | Sets state to pending, updates notification status, triggers immediate print if single letter |
| cancel | self | None | Sets state to canceled, updates notification status, calls `_notify_message_notification_update()` |
| _snailmail_cron | autocommit=True | None | Searches pending letters + retryable errors (TRIAL_ERROR, CREDIT_ERROR, ATTACHMENT_ERROR, MISSING_REQUIRED_FIELDS), processes each, breaks on CREDIT_ERROR to prevent spam |
| _is_valid_address | record | bool | Returns True if all of `street`, `city`, `zip`, `country_id` are present |
| _get_cover_address_split | self | list | Splits partner display name by newline for German formatting (street + street2 combined if DE) |
| _append_cover_page | invoice_bin | bytes | Prepends cover page with recipient address on white background using ReportLab. Adds blank page for duplex |
| _overwrite_margins | invoice_bin | bytes | Fills margins white for postal validation |

### mail.thread (extends base)
**Inheritance:** `mail.thread` (abstract mixin)

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _notify_cancel_snail | self | None | Cancels all snail letters for current user that are not sent/canceled/pending |
| notify_cancel_by_type | self, notification_type | bool | Calls `_notify_cancel_snail` when `notification_type == 'snail'` |

### res.company (extends base)
**Inheritance:** `res.company` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| snailmail_color | Boolean | Default color printing (default=True) |
| snailmail_cover | Boolean | Default cover page (default=False) |
| snailmail_duplex | Boolean | Default duplex printing (default=False) |

### ir.actions.report (extends base)
**Inheritance:** `ir.actions.report` (classic `_inherit`)

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| retrieve_attachment | record | ir.attachment | **Override:** Returns False when `context.get('snailmail_layout')` is set — forces re-rendering for snailmail |
| get_paperformat | self | ir.paperformat | Returns `base.paperformat_euro` when `context.get('snailmail_layout')` and not `l10n_de` paperformat |

### mail.message (extends base)
**Inheritance:** `mail.message` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| snailmail_error | Boolean | Computed: True if any letter in `letter_ids` has state='error' (searchable) |
| letter_ids | One2many | `snailmail.letter` records linked to this message |
| message_type | Selection | Adds `'snailmail'` type; ondelete sets to 'comment' |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_snailmail_error | self | None | Sets `snailmail_error = True` for snailmail-type messages with any error-state letter |
| _search_snailmail_error | operator, operand | domain | Search domain: `letter_ids.state='error' AND letter_ids.user_id=current_user` |
| cancel_letter | self | None | Calls `letter_ids.cancel()` |
| send_letter | self | None | Calls `letter_ids._snailmail_print()` |

### res.partner (extends base)
**Inheritance:** `res.partner` (classic `_inherit`)

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| write | vals | bool | If address fields change and partner has pending snail letters, updates those letters' address fields too |
| _get_country_name | self | str | Returns English country name from `country_utils.py SNAILMAIL_COUNTRIES` mapping when in `snailmail_layout` context |
| _get_address_format | self | str | **Override for snailmail:** Germany: `"%(street)s // %(street2)s\n%(zip)s %(city)s\n%(country_name)s"`. Other countries: `"%(street)s, %(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s"`. In standard context, delegates to `super()` |

### mail.notification (extends base)
**Inheritance:** `mail.notification` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| notification_type | Selection | Adds `'snail'` type with `ondelete='cascade'` |
| letter_id | Many2one | `snailmail.letter` (cascade delete, indexed) |
| failure_type | Selection | Adds snailmail-specific failure types: `sn_credit`, `sn_trial`, `sn_price`, `sn_fields`, `sn_format`, `sn_error` |

### res.config.settings (extends base)
**Inheritance:** `res.config.settings` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| snailmail_color | Boolean | Related to `company_id.snailmail_color` |
| snailmail_cover | Boolean | Related to `company_id.snailmail_cover` |
| snailmail_duplex | Boolean | Related to `company_id.snailmail_duplex` |
| snailmail_cover_readonly | Boolean | Computed: True if layout is boxed/bold/striped (cover forced on) |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _is_layout_cover_required | self | bool | Returns True if `external_report_layout_id` is one of boxed, bold, striped |
| _onchange_layout | self | None | Auto-enables cover page if layout requires it |
| _compute_cover_readonly | self | None | Sets `snailmail_cover_readonly = True` when layout forces cover |

## Security / Data

**Security:** `ir.model.access.csv` grants user-level access to `snailmail.letter` (read/write/create, no unlink) and system-level access (full). Two wizard models also have user-level access.

**Data:** `snailmail_data.xml` — IAP service configuration. `res.company` letter defaults.

## Critical Notes

- **Letter address snapshot:** Address fields are frozen at letter creation time (copied from partner). If partner address changes, pending letters are updated via `res.partner.write()` hook.
- **A4 enforcement:** Only A4 paper format accepted. Custom formats raise `UserError`. External layouts (bubble/wave/folder) are converted to standard for postal compatibility.
- **Margin whitewashing:** PDF margins are overwritten with white rectangles to pass postal validation checks.
- **Cover page:** Optional cover page prepends recipient address on white background. German address formatting: street + street2 combined on single line.
- **Address validation:** Letters with invalid addresses are immediately marked error with `MISSING_REQUIRED_FIELDS`, notifications updated.
- **Retry scheduling:** Cron `_snailmail_cron` retries `CREDIT_ERROR`, `TRIAL_ERROR`, `ATTACHMENT_ERROR`, `MISSING_REQUIRED_FIELDS` letters. CREDIT_ERROR breaks the loop to prevent IAP spam.
- **l10n_de special handling:** German DIN 5008 layout bypasses right-address requirement for Pingen compatibility.
- **v17→v18:** No breaking changes observed.
