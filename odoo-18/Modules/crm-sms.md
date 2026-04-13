---
Module: crm_sms
Version: Odoo 18
Type: Integration
Tags: #crm #sms #marketing #integration
---

# CRM SMS Integration (`crm_sms`)

## Overview

**Path:** `~/odoo/odoo18/odoo/addons/crm_sms/`

The `crm_sms` module bridges the **SMS** and **CRM** modules. It is a lightweight UI/integration layer — it does **not** define new models. Instead it:

- Adds **SMS action buttons** (`Send SMS`) to `crm.lead` list and form views
- Registers **security rules** allowing Sale Managers to create SMS templates for `crm.lead` and `res.partner`
- Enables `crm.lead` records to be targeted by the `sms.composer` wizard in both single-record and batch modes

**Depends:** `crm`, `sms`
**Auto-install:** `True`
**Category:** Sales/CRM

---

## Architecture

`crm_sms` has no Python model file of its own. It operates entirely through:

1. **XML view extensions** — adding SMS buttons to lead views
2. **ir.actions.act_window** records — binding `sms.composer` wizard to `crm.lead`
3. **ir.rule records** — granting SMS template create/write access to Sale Managers

---

## Models Extended

### `crm.lead` (Extended via XML, inherits mixins from `crm` module)

The `crm.lead` model already inherits SMS capability through the `mail.thread.phone` mixin from the base CRM module. The `crm_sms` module adds the **UI layer** only.

#### Key Fields (from `crm` base, used by SMS)

| Field | Type | Description |
|-------|------|-------------|
| `phone` | Char | Primary phone number field; used as default SMS target |
| `mobile` | Char | Mobile number; used as SMS target fallback |
| `phone_sanitized` | Char | Auto-computed, stored sanitized phone number (indexed, `btree_not_null`) |
| `partner_id` | Many2one | Linked `res.partner`; SMS uses partner's mobile/phone if lead has none |

#### Phone/SMS Mixin Fields (from `mail.thread.phone`)

| Field | Type | Description |
|-------|------|-------------|
| `phone` | Char | Phone number with inverse writer |
| `phone_sanitized` | Char | Normalized E.164 phone number, stored and indexed |
| `phone_state` | Selection | Phone quality: `correct` / `incorrect` |

#### `message_has_sms_error` (from `mail.thread`)

| Field | Type | Description |
|-------|------|-------------|
| `message_has_sms_error` | Boolean | True if any SMS notification sent on this lead returned a delivery error. Computed via SQL join on `mail_notification` where `notification_type = 'sms'` and `notification_status = 'exception'` |

---

## Wizard: `sms.composer` (TransientModel)

**Defined in:** `addons/sms/wizard/sms_composer.py`

This is the core SMS sending engine. `crm_sms` registers two action bindings that invoke this wizard against `crm.lead` records.

### Composition Modes

| Mode | CRM Action Binding | Description |
|------|--------------------|-------------|
| `comment` | `crm_lead_act_window_sms_composer_multi` | Post SMS on a single lead's chatter (form view button). Creates a `mail.message` of type `sms`, logged on the lead. |
| `mass` | `crm_lead_act_window_sms_composer_single` | Send batch SMS to multiple selected leads (list view button). Creates `sms.sms` records directly, optionally logs each as a `mail.message`. |

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `composition_mode` | Selection | `numbers`, `comment`, or `mass` |
| `res_model` | Char | Set to `crm.lead` when invoked from CRM |
| `res_id` | Integer | Single record ID when `composition_mode = comment` |
| `res_ids` | Char | Python repr of ID list when `composition_mode = mass` |
| `template_id` | Many2one | `sms.template`; if set, `body` is pre-filled from template |
| `body` | Text | SMS message body (supports `{{ field }}` inline template syntax) |
| `mass_keep_log` | Boolean | If True, writes a `mail.message` log entry on each lead (default: True for CRM) |
| `mass_force_send` | Boolean | If True, sends immediately via cron-scheduled `sms.sms.send()` |
| `mass_use_blacklist` | Boolean | If True, skips numbers found in `phone.blacklist` (default: True) |
| `recipient_valid_count` | Integer | Computed count of leads with valid sanitized phone numbers |
| `recipient_invalid_count` | Integer | Computed count of leads with invalid/missing phone numbers |

### Key Methods

#### `_action_send_sms_mass(records)`
Processes a batch of `crm.lead` records:
1. Calls `_prepare_mass_sms_values()` → determines per-lead state (`outgoing`, `canceled` with failure type)
2. Creates `sms.sms` records via `_prepare_mass_sms()`
3. If `mass_keep_log` is True, calls `records._message_log_batch()` to write a log message on each lead
4. If `mass_force_send` is True, calls `send()` on all `sms.sms` records

#### `_prepare_mass_sms_values(records)`
Per-lead logic:
- **Valid number** → state: `outgoing`, creates `sms.sms` record
- **Blacklisted number** → state: `canceled`, failure_type: `sms_blacklist`
- **Opted-out** → state: `canceled`, failure_type: `sms_optout`
- **Duplicate (same number already sent)** → state: `canceled`, failure_type: `sms_duplicate`
- **Invalid format** → state: `canceled`, failure_type: `sms_number_format`
- **Missing number** → state: `canceled`, failure_type: `sms_number_missing`

---

## SMS Template: `sms.template` (Used with CRM)

**Defined in:** `addons/sms/models/sms_template.py`

SMS templates are the reusable message definitions. They are **not** created by `crm_sms` directly, but the module's security rule enables Sale Managers to manage them for `crm.lead`.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Template display name |
| `model_id` | Many2one | `ir.model`; domain restricted to `is_mail_thread_sms = True` |
| `model` | Char | The model name (e.g., `crm.lead`), derived from `model_id` |
| `body` | Char | SMS body text (translateable); supports Jinja2 `{{ }}` field interpolation |
| `sidebar_action_id` | Many2one | Optional sidebar action linking template to a button on the lead form |

### Methods

#### `action_create_sidebar_action()`
Creates an `ir.actions.act_window` that opens the SMS composer pre-filled with this template. Bound to `crm.lead` model via `binding_model_id`.

---

## View Extensions (XML)

### List View: `crm_case_tree_view_oppor` (Inherit)

Adds two **Send SMS** buttons to the lead/opportunity list view:

```xml
<!-- Header area -->
<button name="crm_lead_act_window_sms_composer_single" type="action" string="SMS" />
<!-- After "Email" button -->
<button name="crm_lead_act_window_sms_composer_multi" type="action" string="SMS" icon="fa-comments" />
```

### Reporting View: `crm_lead_view_tree_opportunity_reporting` (Inherit)

Removes the duplicate SMS button in the reporting/analysis list view.

---

## Security Rules

### `ir_rule`: `ir_rule_sms_template_sale_manager`

**Applies to:** `sms.template`
**Groups:** `sales_team.group_sale_manager`
**Domain:** `[('model_id.model', 'in', ('crm.lead', 'res.partner'))]`
**Permissions:** `perm_read = False`, `perm_write = True`, `perm_create = True`, `perm_unlink = True`

This rule restricts Sale Managers so they can only create/edit SMS templates that target `crm.lead` or `res.partner` models — not other models in the system.

---

## SMS Flow from CRM (L4)

### User Journey

1. **Open Lead List View** → sees "SMS" button in the header (batch mode)
2. **Select multiple leads** → clicks "SMS" → opens `sms.composer` in `mass` composition mode
3. **Composer pre-fills** `default_res_ids` from selected lead IDs, sets `mass_keep_log = True`
4. **User writes/pastes body** or selects a pre-configured `sms.template`
5. **Clicks "Send SMS"** → `_action_send_sms_mass()` is called
6. **Per-lead:** `_sms_get_recipients_info()` is called on each `crm.lead`:
   - Uses `phone_sanitized` if available
   - Falls back to `mobile` field
   - Falls back to `partner_id.mobile` / `partner_id.phone`
7. **`sms.sms` records created** in `outgoing` state (or `canceled` with failure type if invalid)
8. **If `mass_keep_log`:** each lead gets a `mail.message` entry of type `sms` via `_message_log_batch()`
9. **`sms.sms.send()`** dispatches via IAP SMS gateway → updates state to `pending` / `sent` / `error`
10. **Delivery status** tracked via `mail.notification` records with `notification_type = 'sms'`

### Single-Lead Flow (Form View)

1. Open a lead form → "SMS" button (with comment icon) in the header
2. Click → opens `sms.composer` in `comment` mode with `default_res_id = lead.id`
3. SMS sent via `_action_send_sms_comment_single()` → `record._message_sms()` → creates `mail.message` with `message_type = 'sms'`
4. Message appears in lead's chatter with SMS content

---

## UTM Integration

SMS campaigns sent from CRM use the standard **UTM framework**:

- `campaign_id` (Many2one `utm.campaign`) — links SMS sends to a UTM campaign (tracked in `crm_lead`)
- `source_id` (Many2one `utm.source`) — tracks which mailing/source generated the lead
- `medium_id` (Many2one `utm.medium`) — should be set to "SMS" for SMS campaigns

The UTM fields on `crm.lead` are inherited from the `utm.mixin` mixin (defined in the `crm` base module).

---

## Key Design Decisions

1. **No new models** — `crm_sms` is purely a view+security integration layer; all SMS logic lives in the `sms` module
2. **`_mailing_enabled = True` is NOT set on `crm.lead`** in this module — that flag is set by `mass_mailing_crm`, not `crm_sms`
3. **Blacklist checking** is done server-side in `_prepare_mass_sms_values()` against `phone.blacklist`
4. **Phone sanitization** uses `phone_validation` module to format numbers to E.164 before sending
5. **Log messages** use `_message_log_batch()` (not `_message_post()`) so they do not trigger notifications

---

## Related Documentation

- [Modules/CRM](odoo-18/Modules/CRM.md) — base CRM module
- [Modules/SMS](odoo-18/Modules/sms.md) — SMS framework (sms.template, sms.sms, sms.composer)
- [Modules/Mass Mailing CRM](odoo-18/Modules/mass-mailing-crm.md) — email marketing integration with CRM
