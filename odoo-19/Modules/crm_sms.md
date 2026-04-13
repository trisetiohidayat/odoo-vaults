---
type: module
module: crm_sms
tags: [odoo, odoo19, crm, sms, messaging, lead]
created: 2026-04-06
updated: 2026-04-11
l4: true
---

# crm_sms — SMS in CRM

## Module Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `crm_sms` |
| **Version** | `1.1` |
| **Category** | `Sales/CRM` |
| **Summary** | Add SMS capabilities to CRM |
| **Depends** | `crm`, `sms` |
| **Auto-install** | `True` (triggers when both `crm` and `sms` are installed) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Purpose

`crm_sms` bridges the [Modules/sms](sms.md) gateway with [Modules/crm](CRM.md) leads and opportunities. It adds SMS action buttons and security rules so CRM users can send individual and mass SMS directly from lead/opportunity views. **It defines no new Python models** — it is a pure view/data extension layer.

## Dependencies

```
sms ─────────────────────────────────────────────► crm_sms
  └── provides sms.composer, sms.template
  └── provides _sms_get_recipients_info()
  └── provides phone blacklisting, IAP credits

crm ─────────────────────────────────────────────► crm_sms
  └── provides crm.lead, crm.lead.actions
  └── provides mail.thread.phone → phone_sanitized
```

### Dependency Chain

```
sms.composer (sms/wizard/sms_composer.py)
    ├── default_get: reads active_id / active_ids from context
    ├── _get_records(): resolves res_model + res_id(s) → crm.lead recordset
    ├── _action_send_sms_comment(): calls record._message_sms()
    └── _action_send_sms_mass(): calls record._message_log_batch() + creates sms.sms records

crm.lead (crm/models/crm_lead.py)
    ├── inherits mail.thread.phone → provides phone_sanitized
    ├── _sms_get_recipients_info(): inherited from BaseModel (sms/models/models.py)
    └── _message_sms(): inherited from mail.thread (sms/models/mail_thread.py)
```

---

## Models — No Local Models

`crm_sms` introduces **zero Python model classes**. All behavior lives in the base `sms` and `crm` modules. The module registers:

- XML action bindings (two `ir.actions.act_window` records for the SMS wizard)
- XML view extensions (three view inheritance patches)
- CSV security row for `sms.template`
- One `ir.rule` for `sms.template`

---

## Action Bindings — SMS Composer Invocation

Two `ir.actions.act_window` records are registered globally but only appear in the CRM context due to `binding_model_id` targeting `crm.model_crm_lead`.

### `crm_lead_act_window_sms_composer_single` — Mass Mode (List/Kanban)

```
binding_view_types: list, kanban
binding_model_id: crm.model_crm_lead
res_model: sms.composer
composition_mode: mass        (pre-set via context)
mass_keep_log: True          (pre-set via context)
default_res_ids: active_ids  (pre-set via context)
target: new                  (modal popup)
```

**When triggered:** Opens the [Modules/sms](sms.md) composer in **mass batch mode** for all selected leads in a list/kanban view. The `mass_keep_log: True` causes `sms.composer._action_send_sms_mass()` to call `_message_log_batch()` on each lead, writing an HTML note into each lead's chatter after the SMS is queued.

**Behavior in composer:**
- `recipient_valid_count` / `recipient_invalid_count` are computed by calling `crm.lead._sms_get_recipients_info()` for each selected lead
- Blacklisted numbers are automatically skipped (`failure_type: sms_blacklist`)
- Duplicates (same sanitized number sent previously in this batch) are skipped (`failure_type: sms_duplicate`)
- If `mass_force_send` is False (default), SMS records are created in `outgoing` state and the IAP cron scheduler fires them

### `crm_lead_act_window_sms_composer_multi` — Comment Mode (Form)

```
binding_view_types: form
binding_model_id: crm.model_crm_lead
composition_mode: comment     (pre-set via context)
default_res_id: active_id     (pre-set via context)
target: new
```

**When triggered:** Opens the composer in **single-document comment mode** for one specific lead's form view. Displays the recipient's name and validated phone number inline in the composer.

**Behavior in composer:**
- `comment_single_recipient = True` → `recipient_single_valid` governs whether the Send button is enabled
- If the user edits `recipient_single_number_itf` to a different number, that corrected number is **written back to the lead's phone field** via `_action_send_sms_comment_single()`
- A `mail.message` of type `sms` (subtype `mail.mt_note`) is created on the lead's chatter

---

## View Extensions (XML Inheritance)

### `crm_lead.list.opportunity.inherit.sms` — Extends List View

Injects two SMS buttons into the list view header:

```xml
<!-- Always-visible button in header — triggers mass mode for current selection -->
<button name="%(crm_sms.crm_lead_act_window_sms_composer_single)d" type="action" string="SMS" />

<!-- Dropdown button after "Send Email" — triggers comment mode for ONE lead -->
<button name="%(crm_sms.crm_lead_act_window_sms_composer_multi)d"
        type="action"
        string="SMS"
        icon="fa-comments"
        invisible="won_status == 'lost'" />
```

The second button is **hidden if the lead is in `lost` state** (`won_status == 'lost'`). This prevents SMS outreach to dead leads from the list view. This rule does **not** apply to the header button, so a user can still force-send from the header.

### `crm_lead.list.opportunity.reporting.inherit.sms` — Extends Reporting List View

Replaces the `crm_lead_act_window_sms_composer_multi` button reference in the reporting-style list view with the `crm_sms` version, ensuring the reporting view also gets the SMS action. This is a replace operation, not an insert.

---

## Security Architecture

### CSV Access Control

File: `security/ir.model.access.csv`

```
id                              | name                                  | model_id:id           | group_id:id                  | R W C D
access_sms_template_sale_manager| access.sms.template.sale.manager      | sms.model_sms_template| sales_team.group_sale_manager| 1 1 1 1
```

**What it does:** Grants the Sales Manager group full CRUD access to `sms.template` records. This row exists in the base `sms` security; `crm_sms` duplicates it here because the `ir.rule` below requires the group to exist for `perm_write` / `perm_create` / `perm_unlink` to function on CRM-scoped templates.

### Record Rule — `ir_rule_sms_template_sale_manager`

File: `security/sms_security.xml` (noupdate=1)

```xml
<record id="ir_rule_sms_template_sale_manager" model="ir.rule">
  <field name="name">SMS Template: sale manager CUD on opportunity / partner templates</field>
  <field name="model_id" ref="sms.model_sms_template"/>
  <field name="groups" eval="[(4, ref('sales_team.group_sale_manager'))]"/>
  <field name="domain_force">[('model_id.model', 'in', ('crm.lead', 'res.partner'))]</field>
  <field name="perm_read" eval="False"/>
</record>
```

**Domain:** `[('model_id.model', 'in', ('crm.lead', 'res.partner'))]`

**What it does:**

- **Applies only to `sale_manager` group members** — the rule is only active when evaluated in their security context
- **No read access** (`perm_read: False`) — sale managers cannot browse SMS templates list; they must access them only through CRM action menus or sidebar buttons which pre-filter the template
- **Full CUD** (create/update/delete) — allowed because `perm_write: True`, `perm_create: True`, `perm_unlink: True` (default)
- The domain limits write/delete to templates whose `model_id.model` is `crm.lead` or `res.partner` — sale managers cannot modify system-level templates

**Why two models (`crm.lead` AND `res.partner`)?**

When a CRM user creates an SMS template from a lead's form (via the sidebar action created by `sms.template.action_create_sidebar_action()`), the template's `model_id` is set to the active model's IR record. If the user opens it from a lead record, the template's model is `crm.lead`. However, Odoo also allows SMS from partner forms — the security rule covers templates for both models since both are reachable from the CRM context.

**Performance note:** This rule runs on every `sms.template` write/unlink as a record rule. The domain involves a `.model` char field lookup (not a join since it's stored on `model_id` as `model` char). Acceptable at template-count scale.

---

## Tests

File: `tests/test_crm_lead.py`

### Class: `TestCRMLead` (inherits `TestCrmCommon`)

#### `test_phone_mobile_update`

**Purpose:** Verifies that the `mail.thread.phone` mixin's phone sanitization and update logic works correctly on `crm.lead` records when the `crm_sms` module is installed.

**Setup:** Creates a lead with `country_id: us` and a raw `phone` value from `test_phone_data[0]`.

**Assertions:**

1. `lead.phone == test_phone_data[0]` — raw phone is stored as-is
2. `lead.phone_sanitized == test_phone_data_sanitized[0]` — the computed field (via `mail.thread.phone` mixin) formats and stores the E.164 version of the number

**Step 2:** `write({'phone': False})` clears the phone

3. `lead.phone == False`
4. `lead.phone_sanitized == False` — no number to sanitize

**Step 3:** `write({'phone': test_phone_data[1]})` sets a different raw number

5. `lead.phone == test_phone_data[1]`
6. `lead.phone_sanitized == test_phone_data_sanitized[1]` — re-computed from new value

**Why this test lives in `crm_sms`:** The `mail.thread.phone` mixin is already tested in `crm` tests. This test specifically validates that the mixin's behavior is preserved when `crm_sms` is loaded, and confirms the phone fields are accessible for SMS recipient lookups via `_sms_get_recipients_info()`.

---

## Cross-Module Integration Map

```
crm_lead_views.xml (crm_sms)
       │
       ├─► binding: crm.model_crm_lead (list, kanban)
       │         └─► triggers: crm_lead_act_window_sms_composer_single
       │                     └─► context: { default_composition_mode: 'mass',
       │                                  default_mass_keep_log: True,
       │                                  default_res_ids: active_ids }
       │                     └─► opens: sms.composer (mass mode)
       │
       ├─► binding: crm.model_crm_lead (form)
       │         └─► triggers: crm_lead_act_window_sms_composer_multi
       │                     └─► context: { default_composition_mode: 'comment',
       │                                  default_res_id: active_id }
       │                     └─► opens: sms.composer (comment mode)
       │
       └─► inherits: crm.crm_case_tree_view_oppor (list)
                 └─► injects SMS header button + dropdown button

sms_security.xml (crm_sms)
       └─► ir.rule on sms.template
           └─► domain: model_id.model IN ('crm.lead', 'res.partner')
           └─► groups: sales_team.group_sale_manager
           └─► no read, full CUD

ir.model.access.csv (crm_sms)
       └─► access: sale_manager → sms.template (full CRUD)
```

---

## Key Behavioral Details

### SMS Button Visibility by View

| View | Button | Mode | `won_status == 'lost'` hide? |
|------|--------|------|-------------------------------|
| List (tree) | Header button | `sms.composer` mass, `res_ids` from selection | No (always visible) |
| List (tree) | Dropdown button (after email) | `sms.composer` comment, `res_id` from single row | Yes (hidden when lost) |
| Kanban | Header button | mass | No |
| Form | Button in action menu | comment | No |
| Reporting list | Replaced button | comment | Yes (inherited from base replace) |

### Recipient Resolution Path

When `sms.composer._compute_recipients()` runs for `crm.lead`:

```
crm.lead._sms_get_recipients_info(force_field=None, partner_fallback=True)
    │
    ├─► Step 1: Look at crm.lead.phone and crm.lead.mobile
    │         └─► _phone_format(fname='phone') → E.164 if country set
    │         └─► If valid number found → return { sanitized, number, partner: lead.partner_id }
    │
    ├─► Step 2: No valid number on lead → fall back to partner
    │         └─► For lead.partner_id: check partner.phone and partner.mobile
    │         └─► partner_store=True, field_store='phone' or 'mobile'
    │
    └─► Step 3: No number at all → return { sanitized: False, number: raw_value }
```

This means: if a lead has no phone but has a linked partner with a phone, the SMS still goes to the partner's number.

### Mass SMS Failure States

When `sms.composer._prepare_mass_sms_values()` processes a lead record:

| Condition | SMS State | `failure_type` |
|-----------|-----------|---------------|
| Number on blacklist | `canceled` | `sms_blacklist` |
| Number opted out | `canceled` | `sms_optout` |
| Same number already processed in this batch | `canceled` | `sms_duplicate` |
| Number invalid / unparseable | `canceled` | `sms_number_format` |
| No number at all | `canceled` | `sms_number_missing` |
| Valid number | `outgoing` | `''` |

The `sms_duplicate` check is **per-batch only** — it does not query previously sent SMS from prior campaigns. This is a within-run deduplication, not a global deduplication.

### Phone Format Per Country

`crm.lead` inherits `mail.thread.phone` which provides `_compute_phone_state()` and `_onchange_phone_validation()`. The phone is formatted using `country_id` as the locale hint. If `country_id` is not set, the phone is stored as-is without E.164 normalization.

**Impact on SMS:** If `country_id` is missing on a lead with an international phone number, `_phone_format()` may return `False` (unrecognized format), causing `recipient_invalid_count` to increment and the SMS to be canceled with `sms_number_format`. Users must ensure leads have their country set for international SMS campaigns.

---

## Performance Considerations

- **`phone_sanitized` index:** The field has `index='btree_not_null'` on `crm.lead` (inherited from `mail.thread.phone`). This speeds up duplicate detection and blacklist lookups during mass SMS.
- **Batch size:** `sms.sms.create()` triggers the IAP scheduler (`ir_cron_sms_scheduler_action`) on every create batch. For very large campaigns (>10,000 leads), consider pre-filtering using the valid/invalid recipient counts displayed in the composer before sending.
- **Blacklist check:** `_get_blacklist_record_ids()` loads all blacklist numbers into memory (`sudo().search([]).mapped('number')`). For installations with large blacklists, this is a potential memory spike during mass sends.

---

## Odoo 18 → 19 Changes

`crm_sms` itself had minimal changes between Odoo 18 and 19. The module structure was already minimal (XML + security). Key changes in the underlying `sms` module that affect `crm_sms`:

- **Failure type additions:** `sms_registration_needed` added in Odoo 19 as a failure type for country-specific SMS registration requirements. This appears in the failure type dropdown on SMS records sent from CRM leads.
- **`_filter_out_and_handle_revoked_sms_values()` hook:** Added to `SmsComposer` in Odoo 19 for overriding by downstream modules (e.g., `mass_mailing_sms`) to filter revoked consent recipients. `crm_sms` does not override this.
- **`mail.tracking.duration.mixin` added to `crm.lead` in Odoo 19** — the lead model now tracks duration in stage, which does not directly interact with SMS but means the chatter timeline (where SMS log notes appear) has new tracking UI.

---

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/crm](CRM.md) | Parent; provides `crm.lead` model, views, workflow |
| [Modules/sms](sms.md) | Provider; `sms.composer` wizard, `sms.template`, IAP gateway |
| [Modules/mass_mailing_sms](mass_mailing_sms.md) | Extends `crm_sms`; adds consent-gated mass SMS with `mail.mass_mailing` |
| [Modules/mass_mailing_crm_sms](mass_mailing_crm_sms.md) | Bridges mass_mailing and CRM SMS capabilities |
| [Modules/website_crm_sms](website_crm_sms.md) | Adds SMS capture from website lead forms |
| [Modules/crm_mail_plugin](crm_mail_plugin.md) | Outlook/Thunderbird plugin; does not interact with SMS directly |

## Related

- [Modules/crm](CRM.md)
- [Modules/sms](sms.md)
- [Modules/mass_mailing_sms](mass_mailing_sms.md)
- [Modules/mass_mailing_crm](mass_mailing_crm.md)