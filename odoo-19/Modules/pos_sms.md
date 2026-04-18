---
tags:
  - odoo
  - odoo19
  - modules
  - pos
  - sms
  - point_of_sale
  - notification
created: 2026-04-11
updated: 2026-04-14
description: Sends SMS receipts to customers from the Point of Sale when orders are closed. Integrates with the SMS module via the sms.composer API.
---

# POS SMS (`pos_sms`)

> Sends a product-specific SMS receipt to the customer when a Point of Sale order is finalized. The cashier enters the customer's phone number in the POS frontend, and Odoo dispatches an SMS based on a configurable template.

**Module:** `pos_sms` | **Path:** `odoo/addons/pos_sms/` | **Version:** 19.0
**Category:** Point of Sale | **Depends:** `point_of_sale`, `sms` | **License:** LGPL-3
**Author:** Odoo S.A.

---

## Overview

`pos_sms` is a thin bridge module that connects two existing systems:

- **[Modules/point_of_sale](Modules/point_of_sale.md):** POS sessions, orders, and the `action_sent_message_on_sms` JS trigger
- **[Modules/sms](Modules/sms.md):** SMS templates, the `sms.composer` API, and the SMS delivery engine

The module does **not** implement its own SMS sending logic. It uses the standard `sms.composer` to render and dispatch template-based SMS. This means it inherits the full delivery reliability, error handling, and queue management of the `sms` module with zero additional infrastructure.

---

## Module File Structure

```
pos_sms/
├── __init__.py
├── __manifest__.py               # depends: point_of_sale, sms
├── models/
│   ├── __init__.py
│   ├── pos_config.py             # pos.config extension: sms_receipt_template_id
│   ├── pos_order.py              # pos.order extension: action_sent_message_on_sms()
│   └── res_config_settings.py    # res.config.settings: related sms_receipt_template_id
├── data/
│   ├── sms_data.xml              # Default SMS template definitions
│   └── point_of_sale_data.xml   # POS data (possibly default config flags)
├── views/
│   └── res_config_settings_views.xml  # Settings form integration
└── static/
    ├── src/                      # Frontend JS for phone input / trigger
    │   └── js/...                # (POS JS widget that calls action_sent_message_on_sms)
    └── tests/
        └── tours/                # AutofillTour — pos_sms integration test
```

---

## L1: Business Flow — How an SMS Receipt Gets Sent

### End-to-End Sequence

```
1. POS Session opened
   → Cashier has module_pos_sms = True on pos.config
   → sms_receipt_template_id set on pos.config
   ───────────────────────────────────────────────
2. Order closed in POS
   → Frontend JS shows phone number entry field (AutofillTour)
   → Customer provides their mobile number
   ───────────────────────────────────────────────
3. Frontend calls action_sent_message_on_sms(phone, _, basic_image)
   → JS method on pos.order recordset
   → Passes: phone (string), _, basic_image (bool, unused)
   ───────────────────────────────────────────────
4. Server: pos.order.action_sent_message_on_sms()
   → Guard: module_pos_sms enabled AND template set AND phone truthy
   → Creates sms.composer in 'comment' mode
   → Renders sms.template against pos.order record
   → Dispatches SMS to the phone number
   → Writes phone to pos.order.mobile (customer contact)
   ───────────────────────────────────────────────
5. SMS delivered to customer
   → sms module handles Twilio/GSMA/endpoint routing
   → Delivery status tracked in sms.sms record
```

### Activation Checklist

For SMS receipts to fire, all of the following must be true:

| Requirement | Where to check |
|---|---|
| `pos_sms` module installed | Apps |
| `point_of_sale` module installed | Apps |
| `sms` module installed | Apps |
| SMS provider configured | SMS > SMS Providers |
| `module_pos_sms` = True on pos.config | POS > Configuration > Point of Sales > [POS] > General |
| `sms_receipt_template_id` set on pos.config | POS > Configuration > [POS] > Receipt SMS Template |
| Customer provides phone number at POS | Frontend during order closing |

---

## L2: Models and Key Methods

### `pos.config` — Extended

**File:** `models/pos_config.py`

```python
class PosConfig(models.Model):
    _inherit = 'pos.config'

    sms_receipt_template_id = fields.Many2one(
        'sms.template',
        string="Sms Receipt template",
        domain=[('model', '=', 'pos.order')],
        help="SMS will be sent to the customer based on this template"
    )
```

**Field properties:**

| Property | Value |
|---|---|
| Type | `Many2one` |
| Relation | `sms.template` |
| Domain | `model == 'pos.order'` — only POS-order templates selectable |
| Scope | Per-POS config — different POS terminals can use different templates |
| Groups | None — visible to all POS managers |

**Why domain `model == 'pos.order'`?** The `sms.template` model is generic and can be used for any model (crm.lead, res.partner, etc.). The domain restricts the selector to templates that are designed for the POS order context, so the template author can use `object` (the `pos.order`) in QWeb/body expressions.

### `pos.order` — Extended

**File:** `models/pos_order.py`

```python
class PosOrder(models.Model):
    _inherit = 'pos.order'

    def action_sent_message_on_sms(self, phone, _, basic_image=False):
        if not (self and self.config_id.module_pos_sms
                and self.config_id.sms_receipt_template_id and phone):
            return
        self.ensure_one()
        sms_composer = self.env['sms.composer'].with_context(
            active_id=self.id
        ).create({
            'composition_mode': 'comment',
            'numbers': phone,
            'recipient_single_number_itf': phone,
            'template_id': self.config_id.sms_receipt_template_id.id,
            'res_model': 'pos.order'
        })
        self.mobile = phone
        sms_composer.action_send_sms()
```

**Method signature analysis:**

| Parameter | Type | Purpose |
|---|---|---|
| `self` | `pos.order` recordset | The order being closed |
| `phone` | `str` | Customer's mobile number (entered in POS frontend) |
| `_` | (ignored) | Placeholder, possibly for an old parameter |
| `basic_image` | `bool` | Unused in the Python implementation |

**Guard conditions (all must be true):**

```python
self                  # Recordset is not empty
self.config_id.module_pos_sms              # POS config has SMS enabled
self.config_id.sms_receipt_template_id    # Template is set
phone                # Phone number is non-empty
```

If any guard fails, the method returns `None` silently — no error, no traceback. This is intentional: an SMS failure should not block POS operations.

**`sms.composer` creation details:**

```python
composition_mode = 'comment'    # Template rendered against self (pos.order),
                                # sent to single recipient. Not 'mass' (no
                                # recipient list) and not 'first' (no fallback).
numbers = phone                 # The recipient phone number string
recipient_single_number_itf = phone  # Interface field for single-recipient SMS
template_id = template.id       # The configured SMS template
res_model = 'pos.order'         # Template render context model
```

**Post-send side effect:**

```python
self.mobile = phone  # Writes phone number to pos.order.mobile (contact phone)
```

The `mobile` field on `pos.order` stores the customer's contact phone. This enables future SMS sends to the same customer without re-entering the number. The POS form can use this for "autofill" on subsequent orders for the same customer.

### `res.config.settings` — Extended

**File:** `models/res_config_settings.py`

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_sms_receipt_template_id = fields.Many2one(
        'sms.template',
        related='pos_config_id.sms_receipt_template_id',
        readonly=False
    )
```

This is the standard Odoo settings pattern: a `res.config.settings` field with `related=` and `readonly=False` creates a "smart" settings widget in the POS configuration form. When the user saves settings, Odoo's `res.config.settings` logic writes back through the related field to the `pos.config` record.

---

## L3: Frontend Integration and Trigger

### The JS Trigger

The Python method `action_sent_message_on_sms` is called from the POS JavaScript frontend. The frontend:

1. Presents a phone number entry field to the cashier during order closing
2. Validates the phone number format
3. Calls `this.pos.get_order().action_sent_message_on_sms(phone)` via the ORM JSON-RPC bridge
4. The server-side method executes (as shown above)
5. The frontend shows a success/failure notification

### The `AutofillTour` Test

**File:** `tests/test_frontend.py`

```python
@tagged('post_install', '-at_install')
class TestAutofill(TestPointOfSaleHttpCommon):

    def test_01_pos_number_autofill(self):
        self.partner_full.write({'phone': '9876543210'})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.main_pos_config.module_pos_sms = True
        self.start_tour(
            "/pos/ui?config_id=%d" % self.main_pos_config.id,
            'AutofillTour',
            login="pos_user",
        )
```

The tour validates that:
1. When a partner with a phone number is selected in the POS
2. And `module_pos_sms` is enabled
3. The phone number is correctly passed to `action_sent_message_on_sms`
4. The SMS is dispatched (tested indirectly via SMS composer creation)

---

## L4: Cross-Module Integration

### Dependency Chain

```
pos_sms
    ├── point_of_sale         (depends)
    │       └── pos.config    (sms_receipt_template_id field)
    │       └── pos.order     (action_sent_message_on_sms trigger)
    │       └── pos.session   (calls action_sent_message_on_sms from JS)
    │
    └── sms                   (depends)
            └── sms.template  (sms_receipt_template_id relation)
            └── sms.composer  (API used for sending)
            └── sms.sms       (delivery tracking)
            └── sms.api       (SMS gateway: Twilio, Gsma, etc.)
```

### SMS Template Context

When the `sms.template` body is rendered via `sms.composer`, the render context is the `pos.order` record. This means template authors can use:

```
{{ object.name }}              → "Order 00042"
{{ object.partner_id.name }}   → "Alice Johnson"
{{ object.date_order }}         → "2026-04-14 10:30:00"
{{ object.lines[0].product_id.name }}  → "Cappuccino"
```

Note: The SMS body is plain text, not QWeb HTML. The `sms.template` body uses `{{ ... }}` Jinja-style substitution, not QWeb `t-out`.

### How `action_sent_message_on_sms` is Called from JS

The POS JavaScript invokes this method via `do_action` or direct RPC:

```javascript
// Simplified JS pseudocode
const phone = document.getElementById('customer_phone').value;
const order = this.pos.get_order();
order.action_sent_message_on_sms(phone);
```

The ORM bridges the call to `pos.order.action_sent_message_on_sms()` on the server, which then calls `sms.composer.action_send_sms()`.

---

## Failure Modes and Diagnostics

| Failure | Symptom | Root Cause | Resolution |
|---|---|---|---|
| SMS not sent | No SMS after order close | `module_pos_sms` disabled | Enable in POS config |
| SMS not sent | No SMS after order close | No template selected | Set `sms_receipt_template_id` |
| SMS not sent | No SMS, no error | Phone number empty | Cashier must enter phone |
| SMS not sent | Error in server log | SMS provider not configured | Configure SMS provider in SMS > SMS Providers |
| SMS not sent | Twilio/GSMA error | Insufficient SMS credits | Top up SMS credits |
| Order blocked | POS freezes | SMS composer throws | Guard `if not (self and ...)`: should prevent, but check SMS module health |
| Phone not stored | `mobile` field stays empty | Method guard failed | Check that all three conditions are met |

### Debugging Tips

```python
# Quick check from Python console
order = env['pos.order'].browse(<id>)
print(order.config_id.module_pos_sms)
print(order.config_id.sms_receipt_template_id.name)
print(order.mobile)

# Force SMS send
order.action_sent_message_on_sms('+6281234567890')
```

---

## Version Changes: Odoo 18 to 19

`pos_sms` has been stable across Odoo 18 and 19 with no breaking changes.

Key observations:

1. **`sms.composer` API:** The `composition_mode='comment'`, `numbers=`, `template_id=`, and `action_send_sms()` interface is unchanged. This API was stabilized in Odoo 15.

2. **`action_sent_message_on_sms` signature:** The method accepts a third `basic_image` parameter (Python-side) that is not used. This parameter is passed from the frontend JS but is a vestigial interface element — the SMS composer does not accept an image parameter in this call path.

3. **`module_pos_sms` naming:** The `module_` prefix on field names in `pos.config` is Odoo's convention for configuration flags that control module-related behavior. The field is a plain `Boolean` on `pos.config`, not a `module` relationship.

4. **Template domain:** `domain=[('model', '=', 'pos.order')]` on the `sms_receipt_template_id` field ensures only relevant templates appear in the selector. This prevents accidentally assigning a CRM lead template to a POS config.

5. **Auto-install:** `pos_sms` is not `auto_install=True`. It requires explicit installation because the SMS provider must be configured before use.

---

## Security Considerations

| Concern | Risk | Assessment |
|---|---|---|
| Phone number stored in `mobile` | Privacy | The phone number is stored on the order record, which follows standard partner/order ACL. Cashiers can see it; portal customers see their own orders. |
| SMS sent without explicit consent | Compliance | Odoo does not enforce SMS consent. The business must obtain customer consent per applicable regulations (GDPR, TCPA, etc.). |
| SMS credits abuse | Financial | No per-user SMS limits in `pos_sms`. Limits should be configured at the `sms` provider level. |
| XSS in SMS template | Low | `sms.template` body is plain text; no HTML rendering. Jinja substitution is escaped. |
| SQL injection | Safe | All queries use ORM; no raw SQL. |

---

## See Also

- [Modules/point_of_sale](Modules/point_of_sale.md) — `pos.config`, `pos.order`, POS sessions
- [Modules/sms](Modules/sms.md) — SMS templates, `sms.composer`, SMS delivery
- [Core/API](Core/API.md) — ORM field patterns, `@api.model`, `@api.constrains`
- [Modules/mail](Modules/mail.md) — Email receipt alternative to SMS
