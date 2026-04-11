---
uid: snailmail
title: Snail Mail
type: module
category: Hidden/Tools
version: 19.0.1.0.0
created: 2026-04-06
modified: 2026-04-11
dependencies:
  - iap_mail
  - mail
author: Odoo S.A.
license: LGPL-3
summary: Send documents by physical post via IAP printing service
auto_install: true
tags:
  - #odoo
  - #odoo19
  - #modules
  - #iap
  - #postal
---

# Snail Mail (snailmail)

## Overview

The **snailmail** module sends physical letters via postal mail through Odoo's IAP (In-App Purchase) printing service. Documents are:

1. Rendered as PDF
2. Sent to the nearest printing facility via IAP
3. Printed and mailed with return address
4. Tracked for delivery status

This enables Odoo to send invoices, contracts, and other documents through traditional postal service alongside email and SMS notifications.

> **snailmail_account** module extends this with invoice tracking integration.

## Module Architecture

### Directory Structure

```
snailmail/
├── __manifest__.py
├── country_utils.py              # 250+ country name dictionary (snailmail_layout context)
├── models/
│   ├── __init__.py
│   ├── snailmail_letter.py       # Core letter model (560 lines)
│   ├── mail_message.py           # message_type extension + cancel/send actions
│   ├── mail_notification.py      # notification_type='snail' + failure_type enum
│   ├── mail_thread.py            # _notify_cancel_snail override
│   ├── res_partner.py           # Address sync + format override
│   ├── res_company.py            # Company printing defaults
│   ├── res_config_settings.py    # Settings form + layout auto-cover logic
│   └── ir_actions_report.py      # retrieve_attachment bypass + paperformat override
├── data/
│   ├── iap_service_data.xml      # iap.service record (integer_balance: True)
│   └── snailmail_data.xml         # Cron job (24h interval)
├── views/
│   ├── snailmail_views.xml       # list/form views + menu
│   └── report_assets.xml          # Bootstrap asset injection for snailmail PDF layout
├── security/
│   └── ir.model.access.csv
├── static/src/
│   ├── core/
│   │   ├── notification_model_patch.js
│   │   └── failure_model_patch.js
│   ├── core_ui/
│   │   ├── message_patch.js
│   │   └── snailmail_notification_popover.js
│   └── messaging_menu/
│       └── messaging_menu_patch.js
└── tests/
    └── test_attachment_access.py
```

### Key Dependencies

| Module | Purpose |
|--------|---------|
| `iap_mail` | IAP account management, credit tracking, JSON-RPC |
| `mail` | Mail.message integration, notifications, thread model |

The module does **not** explicitly depend on `report` in `__manifest__.py`, but `ir.actions.report` is used at runtime for PDF generation.

### IAP Service Endpoint

```
Endpoint: https://iap-snailmail.odoo.com
Route: /iap/snailmail/1/print
Timeout: 30 seconds (configurable via ir.config_parameter snailmail.timeout)
```

### Country Support

The `country_utils.py` module defines `SNAILMAIL_COUNTRIES` -- a 250+ entry dictionary mapping ISO 3166-1 alpha-2 country codes to English country names. This is used by `res.partner._get_country_name()` when the `snailmail_layout` context is set, ensuring the postal service receives standardized English country names regardless of the database locale.

**Supported countries include**: AC (Ascension), AD (Andorra) through ZW (Zimbabwe), covering all major postal destinations. Unsupported countries return `NO_PRICE_AVAILABLE` from the IAP service.

### IAP Service Registration

The `iap.service` record (defined in `data/iap_service_data.xml`) configures:
- `integer_balance: True` -- credits are whole numbers (stamps), not decimals
- `unit_name: 'Stamps'` -- human-readable unit label in the UI

---

## Core Model: snailmail.letter

**File:** `~/odoo/odoo19/odoo/addons/snailmail/models/snailmail_letter.py`

Represents a physical letter to be mailed. Each letter is linked to a document (invoice, etc.) and a recipient partner.

### Fields

#### Core Identification

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `user_id` | Many2one `res.users` | -- | User who initiated sending |
| `model` | Char | required | Document model name (e.g. `account.move`) |
| `res_id` | Integer | required | Document ID in the target model |
| `partner_id` | Many2one `res.partner` | required | Recipient partner |
| `company_id` | Many2one `res.company` | `self.env.company` | Sending company |
| `reference` | Char (computed) | -- | Formatted `"model,res_id"` string |

**Why `reference` exists**: Provides a human-readable link to the source document in the UI (displayed as a `reference` widget in the form view). Computed from `model` and `res_id`.

#### Report Configuration

| Field | Type | Description |
|-------|------|-------------|
| `report_template` | Many2one `ir.actions.report` | Optional report for PDF generation. If not set, resolved from context via `report_name`. |
| `attachment_id` | Many2one `ir.attachment` | Generated PDF attachment (indexed `btree_not_null`) |
| `attachment_datas` | Binary | Related from `attachment_id.datas` |
| `attachment_fname` | Char | Related from `attachment_id.name` |

**PDF generation flow**: If `attachment_id` is not set when the letter is printed, `_fetch_attachment()` generates the PDF from `report_template`. Once generated, the PDF is stored as an attachment linked to the letter.

#### Printing Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `color` | Boolean | `company.snailmail_color` | Color printing enabled |
| `cover` | Boolean | `company.snailmail_cover` | Add cover page with address window |
| `duplex` | Boolean | `company.snailmail_duplex` | Double-sided printing |

**Why `color` defaults from company**: Ensures consistency across all letters for a given company. Set per-company in `res.company` and exposed in Settings.

#### State Tracking

| Field | Type | Description |
|-------|------|-------------|
| `state` | Selection | One of: `pending`, `sent`, `error`, `canceled` |
| `error_code` | Selection | One of the 7 ERROR_CODES |
| `info_msg` | Html | Status message or error details shown in UI |
| `message_id` | Many2one `mail.message` | Thread message for status updates (indexed `btree_not_null`) |
| `notification_ids` | One2many `mail.notification` | Linked notification records |

**Why `info_msg` is Html**: Allows the error message to include a hyperlink to the IAP account for CREDIT_ERROR/TRIAL_ERROR. The `_get_error_message()` method returns formatted HTML.

#### Address Fields (Snapshot)

| Field | Type | Description |
|-------|------|-------------|
| `street` | Char | Street address |
| `street2` | Char | Street address line 2 |
| `zip` | Char | Postal code |
| `city` | Char | City |
| `state_id` | Many2one `res.country.state` | State/province |
| `country_id` | Many2one `res.country` | Country |

**Critical design note**: These fields are **copied from `partner_id` at letter creation time**. They represent a snapshot of the address at the moment the letter was created. If the partner's address changes later, pending letters retain the original address. This prevents sending to a wrong address if the partner moves. Only unsent letters (`state not in ['sent', 'canceled']`) are updated when partner address changes (via `res.partner.write()` override).

#### Computed Fields

| Field | Compute | Description |
|-------|---------|-------------|
| `display_name` | `_compute_display_name` | `"<attachment_name> - <partner_name>"` or just `"<partner_name>"` if no attachment |
| `reference` | `_compute_reference` | `"model,res_id"` string |

### State Machine

```
                    +--------------+
        create()    |   pending    |   snailmail_print()
        -----------+|              |+------------------+
                    +--------------+                    |
                           ^                           |
                           |                           v
                    +------+------+        +---------------------+
                    |    error     |        |  _snailmail_print   |
                    |              |<+-------|  _snailmail_print_valid_address  |
                    +-------------+  invalid   +---------------------+
                           ^          address            |
                           |                           v
                    +------+------+        +---------------------+
                    |  canceled  |        |       sent            |
                    |            |<+-------|                      |
                    +------------+  cancel()
```

### Letter Creation Flow -- `create()`

The `create()` method performs several critical operations atomically:

1. **Creates a `mail.message`** on the source document via `message_post()` with `message_type='snailmail'`. This adds the letter to the document's chatter.
2. **Snapshots address fields** from `partner_id` at creation time -- street, city, zip, state, country.
3. **Creates `mail.notification`** records with `notification_type='snail'` and `notification_status='ready'`. This enables tracking in the Odoo messaging UI.

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        msg_id = self.env[vals['model']].browse(vals['res_id']).message_post(
            body=_("Letter sent by post with Snailmail"),
            message_type='snailmail',
        )
        partner_id = self.env['res.partner'].browse(vals['partner_id'])
        vals.update({
            'message_id': msg_id.id,
            'street': partner_id.street,
            'street2': partner_id.street2,
            'zip': partner_id.zip,
            'city': partner_id.city,
            'state_id': partner_id.state_id.id,
            'country_id': partner_id.country_id.id,
        })
    letters = super().create(vals_list)
    # Create mail.notification records...
```

### Address Validation -- `_is_valid_address()`

```python
@api.model
def _is_valid_address(self, record):
    record.ensure_one()
    required_keys = ['street', 'city', 'zip', 'country_id']
    return all(record[key] for key in required_keys)
```

A valid address requires **all four fields** to be non-empty. If any are missing, the letter goes to error state with `MISSING_REQUIRED_FIELDS`.

### PDF Generation -- `_fetch_attachment()`

The PDF generation pipeline:

1. **Resolve report**: If `report_template` is set, use it. Otherwise resolve from `report_name` context.
2. **Validate paperformat**: Only A4 is accepted. Custom formats are rejected.
3. **Layout override**: If company uses unsupported layouts (bubble, wave, folder), temporarily switch to `external_layout_standard` for PDF generation.
4. **Render PDF**: Call `_render_qweb_pdf()` with `snailmail_layout=not self.cover` context.
5. **Margin overwrite**: `_overwrite_margins()` fills margins with white for postal validation.
6. **Cover page**: If `cover=True`, `_append_cover_page()` adds a pre-printed address window cover sheet.
7. **Store attachment**: Creates `ir.attachment` record linked to the letter.

**L4 -- Cover page address splitting**: The `_get_cover_address_split()` method handles German address formatting specially. For DE country, `street2` is appended to `street` with ` // ` separator. This is required by Pingen (the underlying print service) for German addresses.

**L4 -- PDF page counting**: Uses regex `rb"/Count\s+(\d+)"` to extract the `/Count` value from the PDF trailer. This counts pages without fully parsing the PDF.

### IAP Communication -- `_snailmail_create()`

The `_snailmail_create()` method builds the JSON payload for the IAP print endpoint:

```python
def _snailmail_create(self, route):
    account_token = self.env['iap.account'].get('snailmail').sudo().account_token
    dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
    # ...
    return {
        'account_token': account_token,
        'dbuuid': dbuuid,
        'documents': documents,  # Per-letter payload
        'options': {
            'color': self[0].color,
            'cover': self[0].cover,
            'duplex': self[0].duplex,
            'currency_name': 'EUR',
        },
        'batch': True,  # Suppress InsufficientCreditError
    }
```

**Critical fields per document:**
- `letter_id`, `res_model`, `res_id` for tracing
- `address` with recipient details (name, street, street2, zip, state, city, country_code)
- `return_address` with company sender details
- `pdf_bin` (base64-encoded) or `pages=1` for estimation
- `company_logo` for Pingen customization

### Error Handling -- `_get_error_message()` and `_get_failure_type()`

Maps IAP error codes to user-friendly messages and notification failure types:

| Error Code | User Message | Failure Type | Action |
|-----------|-------------|--------------|--------|
| `CREDIT_ERROR` | Link to IAP credits page | `sn_credit` | Top up credits |
| `TRIAL_ERROR` | Link to iap.odoo.com | `sn_trial` | Register for free credits |
| `NO_PRICE_AVAILABLE` | Country not covered | `sn_price` | Check country support |
| `MISSING_REQUIRED_FIELDS` | Empty required field | `sn_fields` | Fix address |
| `FORMAT_ERROR` | Attachment could not be processed | `sn_format` | Contact support |
| `ATTACHMENT_ERROR` | PDF generation failed | Internal | Regenerate PDF |
| `UNKNOWN_ERROR` | Generic error | `sn_error` | Contact support |

### Cron Processing -- `_snailmail_cron()`

```python
@api.model
def _snailmail_cron(self, autocommit=True):
    letters_send = self.search([
        '|',
        ('state', '=', 'pending'),
        '&',
        ('state', '=', 'error'),
        ('error_code', 'in', ['TRIAL_ERROR', 'CREDIT_ERROR', 'ATTACHMENT_ERROR', 'MISSING_REQUIRED_FIELDS'])
    ])
    for letter in letters_send:
        letter._snailmail_print()
        if letter.error_code == 'CREDIT_ERROR':
            break  # avoid spam
        if autocommit:
            self.env.cr.commit()
```

**L4 -- Retriable error codes**: Only `TRIAL_ERROR`, `CREDIT_ERROR`, `ATTACHMENT_ERROR`, and `MISSING_REQUIRED_FIELDS` are retried. Other errors (e.g., `FORMAT_ERROR`, `NO_PRICE_AVAILABLE`) are permanent failures and not retried.

**L4 -- Credit break**: If a `CREDIT_ERROR` is encountered, the cron stops processing to avoid spamming the IAP service with requests that will all fail.

**L4 -- Per-letter commits**: `self.env.cr.commit()` is called after each letter to prevent sending the same letter twice if the cron crashes mid-batch.

---

## Cross-Model Integration

### `mail.message` Extension

The `mail.message` model is extended with:

| Field/Method | Description |
|--------------|-------------|
| `snailmail_error` | Boolean computed field -- True if the letter is in error state |
| `letter_ids` | One2many to `snailmail.letter` via `message_id` |
| `message_type` | Added `'snailmail'` option; ondelete converts to `'comment'` |
| `cancel_letter()` | Cancels all linked letters |
| `send_letter()` | Triggers print for all linked letters |

```python
def _search_snailmail_error(self, operator, operand):
    if operator != 'in':
        return NotImplemented
    return ['&', ('letter_ids.state', '=', 'error'), ('letter_ids.user_id', '=', self.env.user.id)]
```

The search method for `snailmail_error` adds a **user filter** -- users only see errors on letters they personally sent. This prevents seeing other users' letter errors in shared searches.

### `mail.notification` Extension

| Field | Description |
|-------|-------------|
| `notification_type` | Added `'snail'` option with `ondelete='cascade'` |
| `letter_id` | Many2one to `snailmail.letter` (indexed `btree_not_null`) |
| `failure_type` | Added snailmail-specific failure types (`sn_credit`, `sn_trial`, `sn_price`, `sn_fields`, `sn_format`, `sn_error`) |

### `mail.thread` Extension

The `notify_cancel_by_type()` method is extended to handle `notification_type == 'snail'`:

```python
@api.model
def notify_cancel_by_type(self, notification_type):
    super().notify_cancel_by_type(notification_type)
    if notification_type == 'snail':
        self._notify_cancel_snail()
    return True
```

This ensures snailmail letters are cancelled when a user cancels a message notification of type 'snail'.

### `res.partner` Extension

Two critical overrides:

**1. Address sync on partner write:**
```python
def write(self, vals):
    address_fields = ['street', 'street2', 'city', 'zip', 'state_id', 'country_id']
    letter_address_vals = {k: v for k, v in vals.items() if k in address_fields}
    if letter_address_vals:
        letters = self.env['snailmail.letter'].search([
            ('state', 'not in', ['sent', 'canceled']),
            ('partner_id', 'in', self.ids),
        ])
        letters.write(letter_address_vals)
    return super().write(vals)
```

This ensures pending letters always reflect the latest address, even if the partner moves after letter creation.

**2. Country name override for snailmail:**
```python
def _get_country_name(self):
    if self.env.context.get('snailmail_layout') and country_code in SNAILMAIL_COUNTRIES:
        return SNAILMAIL_COUNTRIES.get(country_code)
    return super()._get_country_name()
```

Used to ensure the postal service receives English country names regardless of the database locale.

**3. Address format override for DE:**
```python
def _get_address_format(self):
    if self.env.context.get('snailmail_layout') and self.country_id.code == 'DE':
        # Germany requires single-line street+street2 for Pingen
        result = "%(street)s"
        if self.street2:
            result += " // %(street2)s"
        return result + "\n%(zip)s %(city)s\n%(country_name)s"
    return super()._get_address_format()
```

### `res.company` Extension

Company-level defaults for printing options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `snailmail_color` | Boolean | `True` | Default color printing |
| `snailmail_cover` | Boolean | `False` | Default cover page |
| `snailmail_duplex` | Boolean | `False` | Default double-sided printing |

### `ir.actions.report` Extension

```python
def retrieve_attachment(self, record):
    if self.env.context.get('snailmail_layout'):
        return False  # Force re-render for snailmail
    return super().retrieve_attachment(record)

def get_paperformat(self):
    res = super().get_paperformat()
    if self.env.context.get('snailmail_layout'):
        if res != self.env.ref('l10n_de.paperformat_euro_din', False):
            return self.env.ref('base.paperformat_euro')
    return res
```

**L4 -- Why override `retrieve_attachment`?** Normally, Odoo caches rendered PDFs as attachments to avoid re-rendering. For snailmail, the PDF must be re-rendered with `snailmail_layout` context (different margins, possibly different layout). The bypass ensures the snailmail-specific PDF is always fresh.

---

## Performance Considerations

### PDF Attachment Caching

The `_fetch_attachment()` method generates and stores the PDF once. Subsequent print attempts reuse the same attachment. This is efficient because:
- The document being printed (e.g., invoice) rarely changes after being posted.
- Generating PDFs is CPU-intensive.
- The attachment is small (typically < 100KB per page).

**When regeneration happens:**
- If the letter's `report_template` changes.
- If the snailmail_layout context produces a different output.

### Cron Batch Processing

The `_snailmail_cron()` method processes letters in a loop with per-letter commits. Key performance characteristics:
- Processes all pending + retriable-error letters in each cron run.
- Stops immediately on `CREDIT_ERROR` to avoid wasting IAP calls.
- Commits after each letter to survive cron restarts.

### IAP Call Efficiency

The `_snailmail_create('print')` method batches all letters into a single IAP call with `batch=True`. This:
- Reduces HTTP overhead (one request vs. N requests).
- Allows the IAP service to optimize print routing.
- Is why `options` like `color`, `cover`, `duplex` are taken from `self[0]` -- all letters in a batch share the same print options.

---

## Security Considerations

### IAP Credits

Snailmail sends letters through Odoo's IAP infrastructure, which uses a credit-based billing system. Key security points:
- **No direct postal API exposure**: The database UUID and IAP token are the only credentials.
- **Credit authorization**: Only users with IAP account access can configure credits.
- **Cost visibility**: Each letter costs credits; users see stamp prices before sending.
- **Trial mode**: New users get free trial credits before being charged.

### Attachment Access Control

The `create()` method includes:
```python
letters.attachment_id.check_access('read')
```
This ensures the user creating the letter has read access to the generated PDF attachment. If ACLs prevent reading the attachment, the letter creation fails atomically before any IAP call.

### Address Data Privacy

The letter stores a **snapshot** of the partner address. The postal service receives the address at time of sending. If the partner later exercises GDPR right to erasure, the postal service already has the printed letter -- this is a compliance limitation that must be considered.

### No Document Access Control on Print

Once a letter is created, the `_snailmail_print()` method does **not** re-check ACLs on the source document. The assumption is that if a user could create the letter, they had appropriate access at creation time. However:
- If document ACLs change after letter creation, the letter can still be printed.
- This is acceptable for postal mail (the letter is already in the queue).

---

## Odoo 18 -> 19 Changes

### Manifest Version Change

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| `category` | `Hidden/Tools` | `Hidden/Tools` (unchanged) |
| `version` in manifest | `0.3` | `0.4` |
| `auto_install` | `True` | `True` (unchanged) |

### Code Changes in Odoo 19

1. **Report assets injection** (`views/report_assets.xml`): Added Bootstrap SCSS variables include for consistent snailmail PDF styling. The snailmail PDF layout now uses the same Bootstrap grid system as web reports.

2. **`_get_cover_address_split()` addition**: The German address formatting logic (`street2` as `// ` concatenation) was present in Odoo 18 but the explicit `_get_cover_address_split()` method for Pingen compliance may have been refactored.

3. **Static JS patches**: The notification and messaging menu patches were reorganized in Odoo 19's web client. The module's JavaScript patches target `mail.model.Notification`, `mail.model.Failure`, `mail.model.Message`, and `im_livechat.model.MessagingMenu` -- these may have received API changes between versions.

4. **Error code `ATTACHMENT_ERROR`**: Added as a new retriable error code. In Odoo 18, attachment generation failures were not separately classified.

5. **Cron per-letter commits**: The `autocommit=True` parameter pattern was refined to ensure letters are not sent twice after a cron restart.

---

## Related Modules

- `snailmail_account` -- Integrates with account module; adds snailmail sending buttons to invoice forms and automatic letter creation on invoice validation.
- `iap_mail` -- Provides IAP account management used by snailmail for credit tracking.
- [[Modules/mail]] -- Core messaging; snailmail extends mail.message, mail.thread, and mail.notification.
- [[Modules/sms]] -- Parallel notification channel; snailmail and SMS are alternative channels for the same document.

## Tags

#odoo #odoo19 #modules #iap #postal #mail #integration
