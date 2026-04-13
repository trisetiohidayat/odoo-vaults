# website_sms

## Overview

| Attribute | Value |
|---|---|
| **Technical Name** | `website_sms` |
| **Display Name** | Send SMS to Visitor |
| **Category** | `Website/Website` |
| **Sequence** | 54 |
| **Summary** | Allows to send SMS to website visitor if the visitor is linked to a partner |
| **Version** | 1.0 |
| **Depends** | `website`, `sms` |
| **Data Files** | `views/website_visitor_views.xml` |
| **Auto-install** | `True` -- automatically installed when both `website` and `sms` are present |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Purpose

The `website_sms` module bridges the [Modules/website](Modules/website.md) visitor-tracking system with the [Modules/sms](Modules/sms.md) SMS sending infrastructure. It adds a **Send SMS** action button to `website.visitor` records in the Odoo backend UI (form, kanban, and list views), enabling backend users to contact a known website visitor via SMS -- but only when the visitor is linked to a `res.partner` record that carries a phone number.

The module does **not** own any models of its own. It exclusively extends the `website.visitor` model (from `website`) via `_inherit`.

## Architecture

```
website.visitor record
    (has partner_id -> res.partner record)
            |
            └── res.partner.phone  <- used as SMS target
                         |
                         v
            sms.composer wizard (composition_mode='comment')
                         |
                         v
                  sms.sms record -> SMS gateway -> mobile network
```

The module does not introduce new models, fields, or database tables. Its entire logic lives in three method overrides on `WebsiteVisitor` and three view inheritance patches in XML.

## Models

### `website.visitor` -- Extends `website.website_visitor`

**File:** `~/odoo/odoo19/odoo/addons/website_sms/models/website_visitor.py`

No new fields are added. The parent model's relevant fields are:

| Field | Type | Source | Notes |
|---|---|---|---|
| `partner_id` | `Many2one(res.partner)` | `website.visitor` | Computed from `access_token`. If the token is a 32-char SHA1 hash -> anonymous visitor, `partner_id` is False. If token is numeric (partner ID) -> logged-in user visitor. |
| `mobile` | `Char` | Computed from `partner_id.phone` | Defined on parent; populated by `_compute_email_phone`. This is the **UI visibility gate** for all SMS buttons. If empty, the Send SMS button is hidden. |
| `phone` | -- | Not a field on `website.visitor` | The actual phone number used for SMS is always sourced from `res.partner.phone`. The parent `mobile` field on `visitor` is just the display/guard value. |

#### `_check_for_sms_composer()`

```python
def _check_for_sms_composer(self):
    return bool(self.partner_id.phone)
```

**Purpose:** Pre-flight guard that determines whether the SMS action is viable for this visitor.

**L3 -- Cross-model relationship:** The check traverses `self.partner_id.phone`. This means:
- Anonymous visitors (no `partner_id`) always fail this check.
- Visitors linked to a partner that has no `phone` value on `res.partner` also fail.

**L3 -- Inheritance hook:** The docstring explicitly notes this method exists to be overridden by modules that extend `website.visitor` with lead/opportunity data (e.g., `crm` or `website_sale`). Those modules can override this method to pull phone numbers from their own models instead of `res.partner.phone`.

**L4 -- Edge case:** If `partner_id` is set but `phone` is `False`/`None`/empty string, `bool()` returns `False` and the SMS action is blocked. There is no fallback to `mobile` on the visitor record here -- only `partner_id.phone` is checked.

---

#### `_prepare_sms_composer_context()`

```python
def _prepare_sms_composer_context(self):
    return {
        'default_res_model': 'res.partner',
        'default_res_id': self.partner_id.id,
        'default_composition_mode': 'comment',
        'default_number_field_name': 'phone',
    }
```

**Purpose:** Builds the wizard context that launches the `sms.composer` in single-recipient `comment` mode, pointing at the visitor's `res.partner` record and its `phone` field.

**Key context values:**

| Context Key | Value | Effect |
|---|---|---|
| `default_res_model` | `'res.partner'` | Tells the composer to look up the partner record |
| `default_res_id` | `self.partner_id.id` | The specific partner's DB ID |
| `default_composition_mode` | `'comment'` | Single-recipient comment mode (not mass) |
| `default_number_field_name` | `'phone'` | The field on `res.partner` containing the destination number |

**L3 -- Why `res.partner` not `website.visitor`?** The `sms.composer` reads the number from a field on the model specified by `res_model`/`res_id`. The visitor's `mobile` is a transient computed field backed by `partner_id.phone` -- there is no stored `phone`/`mobile` field directly on `website.visitor`. Routing directly to `res.partner` is the correct, stable approach.

**L4 -- Security note:** The wizard opens with the current user's access rights on `res.partner`. Any ACLs on `res.partner` apply. Users who cannot normally read a partner's phone number would not see the Send SMS button in the first place (because `_check_for_sms_composer` already failed for them in a different code path).

---

#### `action_send_sms()`

```python
def action_send_sms(self):
    self.ensure_one()
    if not self._check_for_sms_composer():
        raise UserError(_("There are no contact and/or no phone or mobile numbers linked to this visitor."))
    visitor_composer_ctx = self._prepare_sms_composer_context()
    compose_ctx = dict(self.env.context)
    compose_ctx.update(**visitor_composer_ctx)
    return {
        "name": _("Send SMS"),
        "type": "ir.actions.act_window",
        "res_model": "sms.composer",
        "view_mode": 'form',
        "context": compose_ctx,
        "target": "new",
    }
```

**Purpose:** The primary action triggered by the **Send SMS** button in all three backend views.

**Workflow:**
1. `ensure_one()` -- enforces single-record context. The button is only shown on individual visitor records, not in multi-edit scenarios.
2. `_check_for_sms_composer()` -- guard; raises `UserError` if no partner/phone.
3. Merges the prepared composer context into the current environment context.
4. Returns a `ir.actions.act_window` that opens `sms.composer` as a modal (`target="new"`).

**L3 -- Error message semantics:** The error message says "no contact and/or no phone or mobile" -- this is slightly imprecise since `_check_for_sms_composer` only checks `partner_id.phone`. The `mobile` field on `website.visitor` is not tested here, but it is tested in the view's `invisible` domain, so the user never reaches the button if `mobile` is falsy.

**L4 -- `ensure_one()` on a potentially multi-record recordset:** The button is only rendered when `mobile` is truthy (via `invisible` domain), so in normal operation `self` is always a single-record recordset. However, there is no server-side constraint preventing the action from being called on a recordset of N visitors. In that case `ensure_one()` raises a `ValueError`. The `UserError` from `_check_for_sms_composer` would not be reached for N>1 because `ensure_one()` fires first.

**L4 -- Performance:** No database writes occur in this method. It is a pure read + navigation action. The SMS actually gets sent only when the user fills the composer form and clicks Send in the `sms.composer` wizard.

---

## Views -- `website_visitor_views.xml`

**File:** `~/odoo/odoo19/odoo/addons/website_sms/views/website_visitor_views.xml`

All three views extend the corresponding base views from the `website` module.

### Form View -- `website_visitor_view_form`

**View ID:** `website_sms.website_visitor_view_form`

Inherits from: `website.website_visitor_view_form`

```xml
<xpath expr="//header" position="inside">
    <button name="action_send_sms" type="object" class="btn btn-primary"
            invisible="not mobile" string="Send SMS"/>
</xpath>
```

Appends a **primary** `Send SMS` button into the `<header>` of the visitor form, alongside standard workflow buttons (e.g., Merge, Unlink).

**`invisible="not mobile"`** -- This is the view-level gate. `mobile` is the computed Char field on `website.visitor` (backed by `partner_id.phone`). The button is hidden if:
- The visitor has no `partner_id` (anonymous)
- The linked partner has no `phone` value
- `mobile` evaluates to falsy (empty string, False, None)

---

### Kanban View -- `website_visitor_view_kanban`

**View ID:** `website_sms.website_visitor_view_kanban`

Inherits from: `website.website_visitor_view_kanban`

Two modifications:

```xml
<field name="country_id" position="after">
    <field name="mobile" widget="phone"/>
</field>
```

Adds the `mobile` field (with phone-formatted display) to the kanban card, after `country_id`. This makes the phone number visible directly on the kanban card without opening the form.

```xml
<xpath expr="//div[hasclass('w_visitor_kanban_actions')]" position="inside">
    <button name="action_send_sms" type="object" class="btn btn-secondary"
            invisible="not mobile">SMS
    </button>
</xpath>
```

Adds a **secondary** `SMS` button inside the visitor's action dropdown area (the `w_visitor_kanban_actions` div). Same `invisible` domain as the form button.

---

### List/Tree View -- `website_visitor_view_tree`

**View ID:** `website_sms.website_visitor_view_tree`

Inherits from: `website.website_visitor_view_tree`

Two modifications:

```xml
<xpath expr="//field[@name='is_connected']" position="before">
    <field name="mobile" column_invisible="True"/>
</xpath>
```

Loads the `mobile` field into the view's evaluation context (as a column-invisible field) so the `invisible` domain on the button can reference it. Without this, the `invisible` domain would raise a "field not found" error.

```xml
<xpath expr="//button[@name='action_send_mail']" position="after">
    <button name="action_send_sms" type="object" icon="fa-mobile"
            invisible="not mobile" string="SMS"/>
</xpath>
```

Adds the SMS button after the existing `action_send_mail` button, using a `fa-mobile` icon. The sibling `action_send_mail` button is defined in the parent `website` module's tree view and serves the analogous email-sending function.

---

## SMS Composer -- `sms.composer` Integration

When `action_send_sms()` opens `sms.composer` with the prepared context, the following composer fields are auto-populated:

| Composer Field | Value from `website_sms` | Result |
|---|---|---|
| `composition_mode` | `'comment'` | Single-recipient, one SMS per partner |
| `res_model` | `'res.partner'` | Composer resolves the partner |
| `res_id` | `partner_id.id` | Targets the specific partner record |
| `number_field_name` | `'phone'` | Reads `res.partner.phone` as the destination |

The `sms.composer` then uses its `_sms_get_recipients_info()` method (called on `res.partner`) to:
1. Read the `phone` field from the partner.
2. Sanitize and validate the phone number (E.164 formatting).
3. Present the number in the composer form for optional editing.
4. On send: create an `sms.sms` record and dispatch via the configured SMS gateway.

If the user edits the phone number in the composer, the `sms.composer` can write the updated number back to `res.partner.phone` (via `_action_send_sms_comment_single` logic in `sms.composer`).

---

## Key Design Decisions

### Why `partner_id.phone` and not `website.visitor.mobile`?

The `mobile` field on `website.visitor` is a **transient computed, non-stored** field. Its value lives entirely in memory as a derivative of `partner_id.phone`. The SMS sender needs a stable, writable field to target. Routing through `res.partner.phone` is the correct approach because:
- `res.partner.phone` is stored and can be updated by the user in the composer.
- `website.visitor.mobile` cannot be written to directly.
- The composer is already a `res.partner`-centric wizard (`sms.composer` operates on document models).

### `_check_for_sms_composer` as an Inheritance Hook

The method is specifically designed to be overridable. The `website` module's analogous `_check_for_message_composer()` uses `partner_id.email`. The parallel structure in `website_sms` follows the same pattern. Third-party modules that extend `website.visitor` (e.g., to add a lead/CRM link) can override this method to pull the phone number from their own model instead of `res.partner`.

---

## Security Considerations

1. **Partner ACLs apply.** The `Send SMS` button is only actionable by users who have read access to the `res.partner` record linked to the visitor. The button itself is hidden when `mobile` is falsy, but a user with direct record access (e.g., via direct URL manipulation or API call) who calls `action_send_sms()` will hit the `UserError` guard.

2. **No new access rights.** The module does not define any `ir.model.access` records. All access is inherited from `website` and `sms`.

3. **SMS cost.** Sending SMS incurs costs (via the configured SMS gateway). There is no rate-limiting or quota enforcement at the `website_sms` level -- this is handled by the `sms` module's configuration and the SMS provider.

4. **No website visitor consent tracking.** The module does not track whether a visitor has consented to SMS communications. Operators must ensure compliance with applicable SMS regulations (e.g., TCPA in the US, GDPR in the EU for marketing SMS).

---

## Odoo 18 -> 19 Changes

The `website_sms` module in Odoo 19 is functionally equivalent to its Odoo 18 counterpart. No significant changes to the model logic, view structure, or integration pattern were introduced in Odoo 19. The module's simplicity -- three methods and three view patches -- has remained stable across versions.

The version in the manifest is `'1.0'`, and the module structure (single model file + single views file) has not changed between Odoo 18 and Odoo 19.

---

## Related Modules

- [Modules/website](Modules/website.md) -- defines `website.visitor`, `website.track`, visitor tracking, and the `access_token` mechanism
- [Modules/sms](Modules/sms.md) -- defines `sms.composer`, `sms.sms`, SMS templates, and the SMS gateway abstraction
- [Modules/crm](Modules/CRM.md) -- can extend `website.visitor` with CRM leads; `website_sms` is compatible with that extension via the `_check_for_sms_composer` hook
- `website_sale` -- may link visitors to e-commerce partners; the same hook allows phone-based SMS targeting

## Tags

#odoo #odoo19 #modules #website #sms #crm #security
