---
type: module
module: sale_sms
tags: [odoo, odoo19, sale, sms, notifications, marketing]
created: 2026-04-06
uuid: b2a1e3c4-5d6f-7890-abcd-ef1234567890
---

# Sale SMS

## Overview

| Property | Value |
|----------|-------|
| **Name** | Sale - SMS |
| **Technical** | `sale_sms` |
| **Category** | Sales/Sales |
| **Depends** | `sale`, `sms` |
| **Auto-install** | True |
| **License** | LGPL-3 |
| **Version** | 1.0 |

## What It Does

`sale_sms` is a thin **bridge module** that links two independent subsystems -- the [Modules/Sale](Modules/Sale.md) order management subsystem and the [Modules/sms](Modules/sms.md) SMS notification subsystem -- without adding any Python model code of its own. It grants the `sales_team.group_sale_manager` group access to `sms.template` records scoped to `sale.order` and `res.partner` models, and registers a global record rule so sale managers can Create/Read/Write/Delete SMS templates that apply to the sales domain. The actual SMS sending logic (triggering sends on state transitions, rendering templates, calling the SMS gateway) lives entirely inside the `sms` module.

## Module Structure

```
sale_sms/
├── __init__.py              # Empty -- no Python code in this module
├── __manifest__.py          # Metadata: depends sale + sms, auto_install=True
├── security/
│   ├── ir.model.access.csv  # ACL: Sales Manager full CRUD on sms.template
│   └── security.xml         # ir.rule: domain restriction on sms.template
```

### `__manifest__.py`

```python
{
    'name': "Sale - SMS",
    'summary': "Ease SMS integration with sales capabilities",
    'description': "Ease SMS integration with sales capabilities",
    'category': 'Sales/Sales',
    'version': '1.0',
    'depends': ['sale', 'sms'],        # Both sale and sms must be installed
    'data': [
        'security/ir.model.access.csv',  # ACL records
        'security/security.xml',         # Record rules
    ],
    'auto_install': True,              # Installs automatically when deps are met
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

The `auto_install: True` flag means that when a database has both `sale` and `sms` installed (but not `sale_sms`), Odoo automatically installs `sale_sms` to fill the missing security linkage. This is the standard Odoo pattern for "glue" modules.

## Models

This module does **not** define any Python model classes. It purely manipulates access control records for the `sms.template` model defined by the `sms` module.

### `sms.template` (security granted by this module)

| Field | Value |
|-------|-------|
| **Model** | `sms.template` |
| **Package** | `sms` module |
| **ACL Group** | `sales_team.group_sale_manager` |
| **Permissions Granted** | Read, Write, Create, Unlink |

## Access Control

### `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sms_template_sale_manager,access.sms.template.sale.manager,
  sms.model_sms_template,sales_team.group_sale_manager,1,1,1,1
```

- Grants `sales_team.group_sale_manager` **full CRUD** (Create, Read, Write, Unlink) on `sms.template` records.
- Without this ACL, sale managers would have no permission to manage SMS templates, even if `sms` is installed.
- Note the `group_id:id` column uses external ID `sales_team.group_sale_manager`, which is defined by the `sales_team` module (part of the `sale` dependency chain).

### `security/security.xml`

```xml
<record model="ir.rule" id="ir_rule_sms_template_so_sale_manager">
    <field name="name">SMS Template: sale manager CUD on sale orders</field>
    <field name="model_id" ref="sms.model_sms_template"/>
    <field name="groups" eval="[(4, ref('sales_team.group_sale_manager'))]"/>
    <!-- Only allow templates whose model is sale.order or res.partner -->
    <field name="domain_force">
        [('model_id.model', 'in', ('sale.order', 'res.partner'))]
    </field>
    <field name="perm_read" eval="False"/>
</record>
```

Key attributes:
- **`perm_read` = False**: The rule does **not** restrict read access. All users who have read access (via the ACL above, which grants full CRUD) can read any `sms.template`. The record rule only restricts Create, Write, and Unlink.
- **`domain_force`**: Limits CUD operations to SMS templates whose `model_id.model` is either `sale.order` or `res.partner`. This prevents sale managers from accidentally modifying SMS templates intended for other models (e.g., `hr.applicant`, `crm.lead`).
- **Applied to `groups`**: The rule only applies to `sales_team.group_sale_manager`. Other groups (e.g., `base.group_system`) are unaffected and retain full access.

## How SMS Sending Works (Downstream from this Module)

This module alone does not send any SMS. The actual sending is orchestrated by the `sms` module and triggered from the `sale` or `sale_management` modules. The typical flow is:

1. **SMS Template Created** (by a sale manager via Access Rights granted by this module): The template has `model_id = sale.order` and a body containing Jinja2 merge fields like `{{ object.partner_id.name }}` and `{{ object.amount_total }}`.

2. **State Transition Occurs**: When a `sale.order` moves through states:
   - `draft` -> `sent`: triggered by `action_quotation_send()` in `sale_management`
   - `sent` -> `sale`: triggered by `action_confirm()` in `sale`
   - Each action calls `template._send_sms()` (from the `sms` module)

3. **Template Rendering**: The `sms` module's `sms.template._send_sms()` method renders the template body by evaluating Jinja2 expressions against the `sale.order` record, producing the final SMS text.

4. **SMS Gateway Dispatch**: The `sms` module submits the rendered text to the configured SMS gateway (e.g., Twilio, OVH, or a generic gateway) via its `sms.sms` model.

5. **Delivery Tracking**: Delivery status (sent, delivered, failed) is tracked in `sms.sms` records and optionally displayed on the `sale.order` chatter.

### State-to-Template Mapping

To send an SMS on a specific state transition, an administrator creates `sms.template` records with the appropriate `model_id = sale.order` and assigns them to trigger via the Odoo's SMS composer accessed from the **Communication** tab of the sale order form. The `sale_sms` module does not auto-create these templates -- it simply ensures the sale manager has the security rights to create and manage them.

## Integration Points

### Upstream Dependencies

| Module | Role |
|--------|------|
| `base` | Provides `ir.model.access`, `ir.rule`, `ir.config_parameter` |
| `sale` | Provides `sale.order` model; triggers SMS via `action_confirm` |
| `sale_management` | Provides `action_quotation_send`; extends sale order views |
| `sms` | Provides `sms.template`, `sms.sms`, SMS composer, gateway integration |

### Downstream Consumers

| Module | Usage |
|--------|-------|
| `sale_management` | Calls `template._send_sms()` from `sale.order` communication |
| Custom modules | Can call `env['sms.template'].browse(id)._send_sms()` from Python code |

### Inheritance Chain

The `sale.order` model itself is **not modified** by `sale_sms`. The `sale` module provides the base order; `sale_management` extends it with the quotation-send action; `sale_sms` merely ensures SMS templates for `sale.order` are manageable by sale managers.

## Security Considerations

- The ACL grants full CRUD to `sales_team.group_sale_manager`, which is a **significant permission**. Users with this role can create, modify, and delete any SMS template. Since SMS is a billed service, a malicious sale manager could create many templates that send SMS at high volume.
- The record rule restricts CUD to templates scoped to `sale.order` or `res.partner`, but this is a soft restriction -- `perm_read` is False, so a sale manager could still **read** (but not modify) SMS templates for other models.
- SMS sending itself is subject to the SMS gateway's own rate limits and cost controls, which are configured at the gateway level (outside Odoo in the gateway provider's dashboard).

## Related

- [Modules/Sale](Modules/Sale.md) -- `sale.order` model, state machine, action methods
- [Modules/sale_management](Modules/sale_management.md) -- Quotation send, sale order template
- [Modules/sms](Modules/sms.md) -- SMS template, composer, gateway dispatch, delivery tracking
- [Modules/mail](Modules/mail.md) -- Email notification pattern (analogous to SMS)
- [Modules/portal](Modules/portal.md) -- Customer portal for order tracking

## Common Use Cases

### Use Case 1: Order Confirmation SMS

An administrator creates an SMS template for `sale.order`:
- **Template name**: "Order Confirmed"
- **Model**: `sale.order`
- **Body**: "Hi {{ object.partner_id.name }}, your order {{ object.name }} for {{ object.currency_id.symbol }}{{ object.amount_total }} has been confirmed. Track at: {{ object.get_portal_url() }}"
- **Trigger**: The template is manually selected from the Communication tab of a confirmed sale order, or linked via an automated action triggered by `state = 'sale'`.

### Use Case 2: Quotation Sent SMS

A lighter notification sent when a quotation is emailed to the customer:
- **Template name**: "Quotation Sent"
- **Body**: "{{ object.partner_id.name }}, we have sent you quotation {{ object.name }}. Valid until {{ object.validity_date }}. Reply STOP to unsubscribe."

### Use Case 3: Delivery Arranged SMS

When the stock picking linked to the sale order is validated:
- A server action on `stock.picking` (after `button_validate`) triggers an SMS template on the related `sale.order` via the `sale_id` Many2one field on `stock.picking`.

## SMS Template Model (from the `sms` Module)

Understanding the `sms.template` model -- the model whose security is managed by `sale_sms` -- is essential for getting full value from this bridge module.

### `sms.template` Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Template name (internal label) |
| `model_id` | Many2one | The Odoo model this template is for (`sale.order`, `res.partner`, etc.) |
| `body` | Text | Jinja2 template body. Use `{{ object.field }}` for field interpolation |
| `lang` | Char | Language code for translation (e.g., `en_US`) |
| `state` | Selection | `draft`, `test`, `code` -- in production, must be `test` or `code` |
| `gateway_id` | Many2one | SMS gateway/account to use for sending |
| `user_id` | Many2one | Responsible user for audit trail |
| `active` | Boolean | Whether the template is active (archived templates are hidden) |

### Jinja2 Template Syntax

The `body` field supports Jinja2 templating with the `sale.order` record as `object`:

```jinja2
{# Comment syntax #}
{{ object.partner_id.name }}          {# Customer name #}
{{ object.name }}                    {# Order reference #}
{{ object.currency_id.symbol }}{{ object.amount_total }}  {# Total amount #}
{{ object.date_order.strftime('%d %b %Y') }}  {# Formatted date #}
{{ object.partner_id.phone }}         {# Customer phone #}
{% for line in object.order_line %}  {# Loop over order lines #}
  - {{ line.product_id.name }}: {{ line.product_uom_qty }}x
{% endfor %}
```

### Triggering SMS from the Communication Tab

The standard way to use SMS templates on sale orders is through the **Communication** tab on the sale order form view:

1. Open a `sale.order` record.
2. Navigate to the **Communication** tab.
3. Click **SMS** to open the SMS composer.
4. Select an active `sms.template` from the dropdown.
5. Optionally override the template body for this specific send.
6. Click **Send** -- the `sms` module renders the template and dispatches via the configured gateway.

This workflow requires no code and is accessible to any user with `sales_team.group_sale_manager` rights.

### Automated SMS via Server Actions

For automated sends (without manual intervention), create an **Automated Action** (via `base.action.rule` or the newer `ir.actions.server`):

```python
# Automated Action configuration
# Model: sale.order
# Trigger condition: State changes to 'sale'
# Action: Execute Python code
# Python code:
model = env['sale.order'].browse(env.context.get('active_id'))
template = env['sms.template'].search([
    ('model_id.model', '=', 'sale.order'),
    ('name', '=', 'Order Confirmed'),
], limit=1)
if template:
    template.with_context(
        lang=model.partner_id.lang or 'en_US'
    )._send_sms(res_ids=model.ids)
```

This approach allows fully automated SMS sending on order confirmation, without any user action.

## Why a Thin Bridge Module?

Odoo's architecture encourages separation of concerns, which is why `sale_sms` is intentionally minimal:

1. **`sale` module** owns the business logic of sale orders (states, confirmations, deliveries). It does not depend on `sms`.
2. **`sms` module** owns SMS sending infrastructure (templates, gateways, delivery tracking). It is a general-purpose module usable by any model.
3. **`sale_sms` module** bridges them by granting security rights. It deliberately does NOT add SMS-sending logic to `sale.order` because that would create a hard dependency from `sale` on `sms`.

This design allows:
- Installations without SMS needs to run `sale` without `sms` (no unwanted dependencies).
- Installations with SMS to use `sms` for any model, not just sales.
- Third-party SMS providers to integrate by simply configuring the `sms` module's gateway settings.

## Comparison: SMS vs. Email Notifications

| Aspect | SMS (`sale_sms` + `sms`) | Email (`sale` + `mail`) |
|--------|-------------------------|------------------------|
| **Reach** | Mobile phone number required | Email address required |
| **Open rate** | ~98% (higher than email) | ~20-30% |
| **Cost** | Per-SMS charges via gateway | Minimal (email is cheap) |
| **Character limit** | 160 characters (standard SMS) | No practical limit |
| **Delivery guarantee** | Gateway-dependent (delivery receipts available) | Best-effort (no guarantees) |
| **Opt-out** | By replying STOP | By clicking unsubscribe link |
| **Use case** | Urgent: order confirmation, delivery alerts | Detailed: quotation PDF, contracts |
| **Template management** | `sms.template` (managed by sale_sms ACL) | `mail.template` (in `sale` module) |

A well-configured Odoo sales installation uses both: SMS for immediate, high-priority notifications (order confirmed, shipped), and email for rich content (quotation PDF, contracts, marketing).

## Configuration Checklist

To enable SMS notifications on sale orders:

1. Install the `sale`, `sms`, and `sale_sms` modules.
2. Configure an SMS gateway: **Settings > SMS > SMS Gateway** (or install a gateway-specific module like `sms_ Twilio`).
3. Verify the SMS account has sufficient credits.
4. As a user with `sales_team.group_sale_manager` rights, navigate to **SMS > Templates** and create a template for `sale.order`.
5. Set the template state to `test` (or `code` for production).
6. Assign the template to the appropriate trigger (manual via Communication tab, or automated via server action).
7. Test by sending an SMS from the Communication tab of a sale order.

