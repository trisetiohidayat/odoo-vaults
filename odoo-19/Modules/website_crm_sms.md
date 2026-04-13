# website_crm_sms

#odoo #odoo19 #module #website #crm #sms

## Overview

- **Module**: `website_crm_sms`
- **Name**: Send SMS to Visitor with leads
- **Category**: Website/Website
- **Summary**: Allows sending SMS to website visitors linked to a CRM lead, even without a partner contact
- **Version**: 1.0
- **Depends**: `website_sms`, `crm`
- **Sequence**: 54
- **Auto-install**: True
- **License**: LGPL-3
- **Source**: `odoo/addons/website_crm_sms/`

## Description

Bridges `website_sms` (SMS composer) and `crm` (lead management) by extending `website.visitor` to enable SMS composition when the visitor has a lead linked via `website_crm`, even if the visitor has no `partner_id`. Without this module, `website_sms` requires the visitor to have a `partner_id` with a phone number — many anonymous website form submitters never get a partner created, so they would be unreachable by SMS.

This module is intentionally minimal: 29 lines of Python in a single model file. It has no controllers, no views, no data files, and no security files. It purely overrides two hook methods on `website.visitor`.

## Module Structure

```
website_crm_sms/
├── __init__.py
├── __manifest__.py
└── models/
    ├── __init__.py
    └── website_visitor.py   # Only file — 2 overridden methods
```

---

## Models

### `website.visitor` — Visitor SMS Extension

**Inherits from**: `website.visitor` (via `website_sms`)
**Defined in**: `website_crm/models/website_visitor.py` (base) + `website_sms/models/website_visitor.py` (SMS hook methods) + `website_crm_sms/models/website_visitor.py` (this module, overrides)

**Class**: `WebsiteVisitor`
**Inherit chain**: `BaseModel` → `website.visitor` (core) → `website.visitor` (website_crm adds `lead_ids`) → `website.visitor` (website_sms adds SMS composer methods) → `website.visitor` (website_crm_sms overrides SMS composer methods)

**Security (inherited from `website_crm`)**: `lead_ids` field has `groups="sales_team.group_sale_salesman"` — only salespeople can see leads on visitors. The SMS button inherits the same group restriction from the view layer.

#### Field: `lead_ids` (inherited from `website_crm`)

```python
lead_ids = fields.Many2many('crm.lead', string='Leads', groups="sales_team.group_sale_salesman")
```

| Attribute | Value |
|-----------|-------|
| Type | `Many2many` |
| Target model | `crm.lead` |
| Groups | `sales_team.group_sale_salesman` (salespeople only) |

Set by `website_crm` when a website form submission creates a lead from a visitor. This field is the sole bridge between visitors and leads.

#### Field: `phone` (inherited from base `website.visitor`)

The visitor's own phone number, set via the `_compute_email_phone` method from `website_crm`. That compute method tries the visitor's `partner_id.phone` first, then falls back to `lead_ids[*].phone` (most recent lead). Because the fallback populates `visitor.mobile` (not `visitor.phone`), `website_crm_sms` may fail to match if the lead has no `phone` value — see Edge Cases below.

---

### Method: `_check_for_sms_composer()`

```python
def _check_for_sms_composer(self):
    check = super(WebsiteVisitor, self)._check_for_sms_composer()
    if not check and self.lead_ids:
        sorted_leads = self.lead_ids.filtered(
            lambda l: l.phone == self.phone
        )._sort_by_confidence_level(reverse=True)
        if sorted_leads:
            return True
    return check
```

**Purpose**: Determines whether the "Send SMS" button is visible on the visitor form/kanban/list views. Called by the `invisible` domain in `website_sms` views and by `action_send_sms()`.

**Logic flow**:

1. Calls the parent (`website_sms`) version: returns `True` if `self.partner_id.phone` is truthy
2. If parent returned `False` AND `self.lead_ids` is non-empty:
   - Filters leads where `l.phone == self.phone` (strict equality)
   - Sorts remaining leads by `_sort_by_confidence_level(reverse=True)`
   - If any leads survive → return `True` (button shown)
3. Otherwise returns `False` (button hidden)

**Phone match condition is strict**: Uses `==` not `sanitized_db`. If the visitor's phone is stored as `+1-555-1234` but the lead's phone is `+15551234`, they will not match. This is a known fragility — see Edge Cases.

**Short-circuit behavior**: If the parent method already returns `True` (visitor has a partner with a phone), the lead-based logic is never reached. This is correct — the partner path is preferred when available.

---

### Method: `_prepare_sms_composer_context()`

```python
def _prepare_sms_composer_context(self):
    if not self.partner_id and self.lead_ids:
        leads_with_number = self.lead_ids.filtered(
            lambda l: l.phone == self.phone
        )._sort_by_confidence_level(reverse=True)
        if leads_with_number:
            lead = leads_with_number[0]
            return {
                'default_res_model': 'crm.lead',
                'default_res_id': lead.id,
                'number_field_name': 'phone',
            }
    return super(WebsiteVisitor, self)._prepare_sms_composer_context()
```

**Purpose**: Builds the context dict passed to the `sms.composer` wizard when "Send SMS" is clicked. Controls what record the SMS composer targets and which field it reads as the phone number.

**Logic flow**:

1. Guard: only runs if `self.partner_id` is falsy (no partner) AND `self.lead_ids` is non-empty
2. Filters and sorts leads the same way as `_check_for_sms_composer()`
3. Returns a context dict:
   - `default_res_model = 'crm.lead'` — targets the lead, not `res.partner`
   - `default_res_id = lead.id` — the most confident matching lead's ID
   - `number_field_name = 'phone'` — tells the SMS composer to read the lead's `phone` field (NOT `mobile`)
4. Falls back to parent if conditions not met

**The `number_field_name` mechanism** (from `sms.composer`):

- `sms.composer.number_field_name` is a `Char` field on the composer wizard
- `_compute_recipient_single_stored()` reads `records._sms_get_recipients_info(force_field=composer.number_field_name, ...)` where `records` is the target model (`crm.lead`)
- `_sms_get_recipients_info` on `crm.lead` returns `{'sanitized': <lead.phone>, ...}`
- If `number_field_name` is absent, `website_sms` sets `default_number_field_name = 'phone'` instead — both keys are handled by the composer via `partner_fallback=True`

**Critical distinction**: This method only runs when `partner_id` is absent. If the visitor has a partner, `website_sms`'s parent method runs and the composer targets the partner instead. This is the intended behavior — partner-linked visitors use the partner record directly.

---

## How It Works

### Visitor-to-Lead SMS Flow

```
Salesperson opens visitor form
    │
    ├─ visitor.partner_id exists? ──yes──→ website_sms parent runs
    │   (targets res.partner, uses partner.phone, done)
    │
    └─no partner, but lead_ids exists? ──→ website_crm_sms override runs
        │
        ├─ any lead.phone == visitor.phone?
        │   (strict equality, no sanitization)
        │
        └─yes: SMS button shown, composer targets crm.lead
              with number_field_name='phone'
              → composer reads lead.phone as recipient
```

### Confidence Level Sorting (`_sort_by_confidence_level`)

Defined on `crm.lead` in `crm/models/crm_lead.py` (lines 1940-1962). Sort key:

```python
def opps_key(opportunity):
    return (
        opportunity.type == 'opportunity' or opportunity.active,  # not lost first
        opportunity.type == 'opportunity',                        # opportunity > lead
        opportunity.stage_id.sequence,                            # higher stage first
        opportunity.probability,                                 # higher probability first
        -opportunity._origin.id                                  # newer lead first (tiebreaker)
    )
```

**Interpretation**: Among leads with matching phone numbers, the most "confident" (advancing toward won) is selected. This gives preference to active opportunities in late stages over raw new leads.

### `_compute_email_phone` Fallback (from `website_crm`)

`website_crm` populates `visitor.mobile` from `lead.phone` when the visitor has no `partner_id`:

```python
if not visitor.mobile:
    visitor.mobile = next((lead.phone for lead in visitor_leads if lead.phone), False)
```

**Implication for `website_crm_sms`**: If the lead's phone is stored in `visitor.mobile` but `visitor.phone` is empty, `_check_for_sms_composer` will return `False` because `self.phone == ''` will not match `lead.phone`. The lead's phone is used to populate the visitor's `mobile` field, not the `phone` field — see Edge Cases.

---

## Dependency Chain

```
website_crm_sms
├── website_sms          # _inherit base + action_send_sms() + SMS view buttons
│   └── website_crm      # Provides lead_ids + lead_count on website.visitor
│       └── crm          # Provides crm.lead model
└── crm                  # Provides crm.lead model + _sort_by_confidence_level
```

**`website_sms`** contributes:
- `action_send_sms()` on `website.visitor` — calls `_check_for_sms_composer()` then `_prepare_sms_composer_context()`, opens `sms.composer` wizard in a modal
- Form/Kanban/List view buttons (with `invisible="not mobile"`) that call `action_send_sms()`
- Base `_check_for_sms_composer()`: returns `bool(self.partner_id.phone)`
- Base `_prepare_sms_composer_context()`: returns context targeting `res.partner` with `default_number_field_name = 'phone'`

**`website_crm`** contributes:
- `lead_ids` Many2many field on `website.visitor`
- `_compute_lead_count()` counter
- `_compute_email_phone()` which populates `visitor.mobile` from `lead.phone` as fallback
- `_check_for_message_composer()` for email composer
- `_inactive_visitors_domain()` override ensuring leads-linked visitors are never auto-deleted
- `_merge_visitor()` ensuring leads survive visitor merges

---

## Cross-Module Integration

### SMS Composer (`sms.smscomposer`)

| Composer field | `website_sms` value | `website_crm_sms` value |
|---------------|-------------------|------------------------|
| `default_res_model` | `'res.partner'` | `'crm.lead'` |
| `default_res_id` | `self.partner_id.id` | `sorted_leads[0].id` |
| `default_number_field_name` | `'phone'` | *(not set)* |
| `number_field_name` | *(not set by caller)* | `'phone'` |

Both context keys (`default_number_field_name` and `number_field_name`) are understood by the SMS composer. The composer stores whichever key is set in its `number_field_name` field, which then controls `_compute_recipients` and `_compute_recipient_single_stored`.

### `_sms_get_recipients_info` on `crm.lead`

The SMS composer calls `records._sms_get_recipients_info(force_field=number_field_name, ...)`. On `crm.lead`, this method uses the `phone` field as a fallback when `mobile` is used. If the lead has no `phone` value, no valid recipient is found and `recipient_valid_count == 0` — the Send button is disabled.

---

## Edge Cases

### 1. Phone number stored in `visitor.mobile` but not `visitor.phone`

`website_crm`'s `_compute_email_phone` populates `visitor.mobile` from `lead.phone`, but leaves `visitor.phone` empty if the visitor's partner has no phone. Since `website_crm_sms` filters on `self.phone`, no leads match → `_check_for_sms_composer()` returns `False` → SMS button is hidden even though a valid phone number exists in `lead.phone` (mirrored to `visitor.mobile`).

**Workaround**: Ensure the lead's phone is also recorded on the visitor's `phone` field (e.g., via a custom bridge or by ensuring the partner is created from the lead first).

### 2. Strict phone equality comparison

`l.phone == self.phone` performs exact string equality. Formatting differences (e.g., `+1 555 1234` vs `+15551234`, with/without dashes) will cause non-match. The Odoo phone sanitization (`phone_format`) is not applied in the filter.

**Risk**: High in production environments where CRM data is imported from external systems with inconsistent phone formatting. Leads may exist but not be reachable via SMS due to formatting mismatches.

### 3. Lead selection order differs between two methods

The filter-then-sort order is identical in both methods (filter first, then sort), but both read from the same `self.lead_ids`, so the first matching lead is the same record in practice. This is architecturally fragile — if a future change filters before sorting in one method but sorts before filtering in the other, they could select different leads.

### 4. Visitor without phone but with leads and partner

If the visitor has a `partner_id` but no phone on either the visitor or partner, `website_sms`'s parent `_check_for_sms_composer()` returns `False`. `website_crm_sms` then checks leads, but if `self.phone` is empty and no lead has an empty phone, `website_crm_sms` also returns `False`. The SMS button is hidden even though the lead might have a valid phone.

### 5. `lead_ids` group restriction

`lead_ids` is restricted to `sales_team.group_sale_salesman`. Non-sales users cannot see `lead_ids` on the visitor form. If a salesperson shares a visitor record with a customer service agent (who lacks the sales group), the agent sees no leads and the SMS button is invisible even if the visitor is legitimately linked to a lead.

### 6. Visitor merge drops SMS eligibility

`_merge_visitor` (from `website_crm`) transfers leads to the target visitor via `(4, lead.id)` commands. If two visitors both have leads with valid phone numbers, after merging into the target, the SMS logic still applies. However, if the merged visitor's `phone` field does not match any of the transferred leads' `phone` fields, SMS eligibility is lost.

---

## Security Considerations

- **No new access rights** introduced by this module. All security is inherited from `website_crm` and `website_sms`.
- **`lead_ids`** field has `groups="sales_team.group_sale_salesman"` — only users with the Sales: Show Leads on Website Visitors group can see or interact with leads on visitors.
- **SMS sending** is gated by the `sms` module's own access controls (`sms.sms_send` / `sms_sms_manager` group) — `website_crm_sms` does not grant any additional SMS permissions.
- **No data leakage risk**: The module does not expose any data via controllers or public endpoints.

---

## Performance Notes

- **No performance concerns**: The two overridden methods operate on already-loaded recordsets (`self.lead_ids` is a stored Many2many). Both use `filtered()` and `_sort_by_confidence_level()` which are standard Odoo recordset operations.
- **N+1 awareness**: If iterating over a large list of visitors in Python, each call to `_check_for_sms_composer()` triggers a filter + sort on that visitor's lead set. This is negligible — each visitor's lead count is typically small.
- **Auto-install** has no performance impact at runtime.

---

## L3 Summary: Method-by-Method Override Rationale

| Method | Parent does | This module adds |
|--------|-------------|-----------------|
| `_check_for_sms_composer()` | Returns `True` if `partner_id.phone` exists | Falls back to checking if any lead has a phone matching `self.phone` |
| `_prepare_sms_composer_context()` | Returns context targeting `res.partner` | Returns context targeting `crm.lead` with `number_field_name='phone'` when no partner exists |

---

## Related

- [Modules/website_sms](website_sms.md) — Base SMS on website visitors, provides `action_send_sms()` and SMS composer integration
- [Modules/website_crm](website_crm.md) — Website CRM lead capture, provides `lead_ids` on `website.visitor` and visitor/lead synchronization
- [Modules/CRM](CRM.md) — CRM lead/opportunity management, provides `_sort_by_confidence_level()` and `crm.lead` model
- [Modules/sms](sms.md) — Core SMS sending module, provides `sms.composer` wizard
- [Modules/website_crm_livechat](website_crm_livechat.md) — Links livechat sessions to CRM leads
