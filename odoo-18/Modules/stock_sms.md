# stock_sms — Stock SMS

**Tags:** #odoo #odoo18 #stock #sms #delivery #notification
**Odoo Version:** 18.0
**Module Category:** Stock + SMS Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`stock_sms` sends SMS notifications to customers upon delivery validation for outgoing pickings. It integrates with the `sms` module to send templated SMS messages using company-configurable templates, with optional pre-validation SMS confirmation prompts.

**Technical Name:** `stock_sms`
**Python Path:** `~/odoo/odoo18/odoo/addons/stock_sms/`
**Depends:** `stock`, `sms`
**Inherits From:** `stock.picking`, `res.company`, `res.config.settings`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/stock_picking.py` | `stock.picking` | SMS confirmation on delivery, pre-validation SMS check |
| `models/res_company.py` | `res.company` | SMS validation toggle, template assignment |
| `models/res_config_settings.py` | `res.config.settings` | Settings sync for SMS configuration |

---

## Models Reference

### `stock.picking` (models/stock_picking.py)

#### Methods

| Method | Decorators | Behavior |
|--------|-----------|----------|
| `_pre_action_done_hook()` | — | Overrides base hook: runs `_check_warn_sms()` to prompt SMS warning before done |
| `_check_warn_sms()` | — | Returns pickings needing SMS warning: outgoing, company has SMS enabled, partner has mobile/phone, not in test mode |
| `_action_generate_warn_sms_wizard()` | — | Opens wizard confirming SMS will be sent |
| `_send_confirmation_email()` | — | Calls `super()`, then sends SMS via `_message_sms_with_template()` for outgoing pickings |

#### Pre-Validation SMS Check

`_pre_action_done_hook()` intercepts the "Validate" action:

```python
def _pre_action_done_hook(self):
    res = super()._pre_action_done_hook()
    if res is True and not self.env.context.get('skip_sms'):
        pickings_to_warn_sms = self._check_warn_sms()
        if pickings_to_warn_sms:
            return pickings_to_warn_sms._action_generate_warn_sms_wizard()
    return res
```

This inserts a confirmation wizard step before the final validation, giving users a chance to cancel if they notice something wrong.

#### SMS Sending Logic

`_send_confirmation_email()` sends SMS after `_action_done()` (triggered in `_send_confirmation_email` after the parent call):

```python
pickings = self.filtered(
    lambda p: p.company_id.stock_move_sms_validation
              and p.picking_type_id.code == 'outgoing'
              and (p.partner_id.mobile or p.partner_id.phone)
)
for picking in pickings:
    template = picking.company_id.sudo().stock_sms_confirmation_template_id
    picking._message_sms_with_template(
        template=template,
        partner_ids=picking.partner_id.ids,
        put_in_queue=False  # sent immediately
    )
```

**Conditions for SMS:**
- `company_id.stock_move_sms_validation = True`
- `picking_type_id.code == 'outgoing'`
- Partner has `mobile` or `phone`

**Thread safety guards**: Wrapped in `threading.current_thread().testing` and `self.env.registry.in_test_mode()` checks to prevent unintended SMS in tests.

---

### `res.company` (models/res_company.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `stock_move_sms_validation` | Boolean | SMS confirmation toggle, default True |
| `stock_sms_confirmation_template_id` | Many2one | `sms.template` for delivery SMS |
| `has_received_warning_stock_sms` | Boolean | One-time flag to suppress repeat warnings |

#### Methods

| Method | Behavior |
|--------|----------|
| `_default_confirmation_sms_picking_template()` | Returns `stock_sms.sms_template_data_stock_delivery` template ID |

#### Default Template

The default template is `sms_template_data_stock_delivery` defined in the `stock_sms` module's data file. It uses the `stock.picking` model and typically includes variable fields like `object.display_name`, `object.partner_id.display_name`, etc.

---

## Security File: `security/sms_security.xml`

**ir.rule**: `ir_rule_sms_template_stock_manager`
- Model: `sms.template`
- Group: `stock.group_stock_manager`
- Domain: `[('model_id.model', '=', 'stock.picking')]`
- Perms: read=False, write=False, create=False, unlink=False

This rule allows stock managers to manage SMS templates linked to stock pickings while preventing access to templates for other models.

---

## Data Files

| File | Content |
|------|---------|
| `data/sms_data.xml` | `sms.template` record `sms_template_data_stock_delivery` with model `stock.picking` |

---

## Critical Behaviors

1. **Pre-Validation Warning**: `_pre_action_done_hook()` inserts a wizard step before validating outgoing pickings. The wizard warns that an SMS will be sent. The flag `has_received_warning_stock_sms` ensures this warning only fires once per company.

2. **Immediate SMS Sending**: Unlike email (which can be queued), SMS is sent immediately (`put_in_queue=False`) because carrier SMS queues are typically processed quickly and users expect delivery confirmation to arrive right away.

3. **Outgoing Pickings Only**: Only pickings with `picking_type_id.code == 'outgoing'` trigger SMS. Incoming receipts do not send confirmation SMS.

4. **Company-Level Control**: SMS confirmation is a per-company toggle via `stock_move_sms_validation`. Companies can disable it entirely without uninstalling the module.

5. **Template-Based**: The SMS body text is fully configurable via the `stock_sms_confirmation_template_id` template. Admins can customize message content, include tracking links, etc.

6. **Thread Safety**: Both `_check_warn_sms()` and `_send_confirmation_email()` check `threading.current_thread().testing` and `self.env.registry.in_test_mode()` to prevent accidental SMS sending during automated tests.

---

## v17→v18 Changes

- `has_received_warning_stock_sms` field added for one-time warning suppression
- SMS template defaults to `sms_template_data_stock_delivery` (new in v18)
- `_action_generate_warn_sms_wizard()` method added for pre-validation SMS confirmation wizard

---

## Notes

- `stock_sms` is lightweight (3 model files, ~120 lines of logic)
- The pre-validation SMS wizard is a UX safeguard, not a technical requirement
- Template is sent using `_message_sms_with_template()` from the `sms` module
- SMS is sent via the `sms` carrier configured on the company
