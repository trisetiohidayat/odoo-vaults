# sale_sms — Sale SMS

**Tags:** #odoo #odoo18 #sale #sms #notification
**Odoo Version:** 18.0
**Module Category:** Sale + SMS Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_sms` provides SMS notification capabilities for sale orders. It extends `sale.order` with SMS messaging support so that order status updates (confirmation, cancellation, etc.) can be sent as text messages to customers who prefer SMS over email. This is a thin bridge module — all actual SMS logic lives in the `sms` core module.

**Technical Name:** `sale_sms`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_sms/`
**Depends:** `sale`, `sms`
**Inherits From:** (no Python models — pure data module)

---

## Module Structure

`sale_sms` is a **data-only module** with no Python model files:

```
addons/sale_sms/
├── __init__.py
├── __manifest__.py
├── security/
│   ├── ir.model.access.csv
│   └── security.xml
```

The module's sole contribution is adding SMS-related access rights and security rules for sale order SMS features. No new fields or methods are added — all SMS sending logic is inherited from the `sms` module.

---

## `__manifest__.py`

```python
{
    'name': "Sale - SMS",
    'summary': "Ease SMS integration with sales capabilities",
    'description': "Ease SMS integration with sales capabilities",
    'category': 'Hidden',
    'version': '1.0',
    'depends': ['sale', 'sms'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
    ],
    'auto_install': True,
    'license': 'LGPL-3',
}
```

**Key points:**
- `depends: ['sale', 'sms']` — bridges the two modules
- `auto_install: True` — automatically installed when both `sale` and `sms` are present
- Data files only: access control and security rules
- Hidden category — not visible in the Apps list

---

## Data Files

### `security/ir.model.access.csv`

Standard access control entries for any new models introduced by `sms` that are used by `sale.order`. Does not add new model access — only ensures `sale_sms` properly wires SMS permissions to sale users.

### `security/security.xml`

Record rules that allow SMS notifications to be sent from the context of a sale order. This ensures that users with sale order access can trigger SMS sends without needing explicit SMS module permissions.

---

## Critical Behaviors

1. **No Python Code**: `sale_sms` contributes no Python code. Its only role is wiring the security/permission layer so that SMS features work correctly in the sale order context.

2. **Auto-install**: With `auto_install: True`, the module activates automatically when both `sale` and `sms` are installed — no manual installation needed.

3. **SMS Templates for Sale**: The actual SMS templates (e.g., "Your order #SO001 has been confirmed") are managed in the `sms` module. `sale_sms` merely ensures the correct access rules are in place.

4. **Companion to `sale_email`**: In Odoo, SMS and email notifications for sales orders are handled by separate modules. `sale_sms` is the SMS counterpart to any email notification modules.

---

## v17→v18 Changes

- No significant changes from v17 to v18
- Module structure and data files remain consistent

---

## Notes

- `sale_sms` is a thin, passive module — its importance is structural (ensuring security wiring) rather than functional
- SMS templates for sale orders are created in the `sms` module under Settings > Custom > SMS Templates
- The `auto_install` flag ensures this module is present in any deployment with both `sale` and `sms`, without requiring explicit installation
