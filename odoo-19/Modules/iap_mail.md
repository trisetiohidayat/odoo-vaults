---
title: IAP Mail
description: Bridge between IAP and mail. Adds bus-based real-time notifications and mail.thread to iap.account, enabling toast notifications for credit alerts and operation status.
tags: [odoo19, iap, mail, notification, bus, toast, module]
model_count: 2
models:
  - iap.account (inherits mail.thread)
dependencies:
  - iap
  - mail
category: Hidden/Tools
source: odoo/addons/iap_mail/
created: 2026-04-14
uuid: e8a1f5c4-7d3b-4e9a-8f6c-2b0d5e7f1a9c
---

# IAP Mail

## Overview

**Module:** `iap_mail`
**Category:** Hidden/Tools
**Depends:** `iap`, `mail`
**Auto-install:** True
**License:** LGPL-3
**Author:** Odoo S.A.

`iap_mail` bridges Odoo's IAP (In-App Purchase) infrastructure and the [Modules/mail](Modules/mail.md) module. It does two fundamental things:

1. **Real-time bus notifications** -- Adds four class methods to `iap.account` that send real-time toast notifications to the Odoo web client via the Odoo bus (WebSocket). This enables IAP services to immediately alert users when credits run low, when an enrichment operation succeeds, or when it fails.

2. **Mail thread on IAP accounts** -- Inherits `mail.thread` on `iap.account`, enabling chatter, activity tracking, and field change tracking on IAP account forms. This gives administrators a full audit trail of changes to account configuration.

The module is the foundational notification layer for all IAP-based services in Odoo. Any module that uses IAP (CRM lead enrichment, partner autocomplete, email try-and-buy, SMS delivery, etc.) depends on `iap_mail` for user-facing status communication.

## Module Structure

```
iap_mail/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── iap_account.py     # mail.thread + bus notification methods
├── data/
│   └── mail_templates.xml # Optional email templates for IAP account comms
├── views/
│   └── iap_views.xml       # Form view with chatter
└── static/
    └── src/
        ├── js/
        │   └── services/
        │       └── iap_notification_service.js  # Frontend bus listener
        └── scss/
            ├── iap_mail.scss
            └── iap_mail.dark.scss
```

## Extended Models

### `iap.account` (inherits)

File: `models/iap_account.py`

The `iap.account` model is the core of Odoo's IAP infrastructure. Each IAP service (SMS, Email Try & Buy, CRM Enrichment, etc.) has an associated `iap.account` record that tracks credits, thresholds, and notification preferences.

**Inheritance:**

```python
class IapAccount(models.Model):
    _name = 'iap.account'
    _inherit = ['iap.account', 'mail.thread']
```

By inheriting `mail.thread`, the model gains:
- `message_ids` -- One2many to `mail.message` (chatter thread)
- `message_follower_ids` -- Many2many to `mail.followers`
- `activity_ids` -- One2many to `mail.activity`
- Tracking metadata: `message_main_attachment_id`, `website_message_ids`

**New / Modified Fields:**

| Field | Change | Description |
|-------|--------|-------------|
| `company_ids` | Added `tracking=True` | Tracks changes to the authorized companies list |
| `warning_threshold` | Added `tracking=True` | Tracks changes to the low-credit alert threshold |
| `warning_user_ids` | Added `tracking=True` | Tracks changes to who receives low-credit alerts |

The `tracking=True` attribute means any time one of these fields is modified, a chatter message is automatically posted documenting the change: "Warning Threshold changed from 100 to 50."

**Notification Methods:**

All four notification methods follow a consistent pattern: they construct a payload dictionary and call `self.env.user._bus_send()` to push it through the Odoo WebSocket bus.

---

**`_send_success_notification`:**

```python
@api.model
def _send_success_notification(self, message, title=None):
    self._send_status_notification(message, 'success', title=title)
```

Called when an IAP operation completes successfully. The `message` is displayed as a success toast. Optional `title` overrides the default "Success" label.

---

**`_send_error_notification`:**

```python
@api.model
def _send_error_notification(self, message, title=None):
    self._send_status_notification(message, 'danger', title=title)
```

Called when an IAP operation fails. The `danger` type renders a red error toast. Use this for recoverable errors (e.g., "Enrichment service temporarily unavailable").

---

**`_send_status_notification`:**

```python
@api.model
def _send_status_notification(self, message, status, title=None):
    params = {
        'message': message,
        'type': status,
    }
    if title is not None:
        params['title'] = title
    self.env.user._bus_send("iap_notification", params)
```

The core bus send method. It pushes a notification payload to the current user (`self.env.user`) on the `"iap_notification"` bus channel. The Odoo web frontend listens on this channel and renders the notification as a toast.

The payload structure:
```python
{
    'message': 'Your lead was enriched successfully',  # Toast body text
    'type': 'success',                                # Toast style: success|danger|warning|info
    'title': 'Enrichment Complete'                    # Optional header
}
```

---

**`_send_no_credit_notification`:**

```python
@api.model
def _send_no_credit_notification(self, service_name, title):
    params = {
        'title': title,
        'type': 'no_credit',
        'get_credits_url': self.env['iap.account'].get_credits_url(service_name),
    }
    self.env.user._bus_send("iap_notification", params)
```

The most important notification for user experience. When an IAP operation fails due to insufficient credits, this method sends a special `'no_credit'` notification that includes:
- A configurable title (e.g., "Insufficient Credits for Lead Enrichment")
- The URL to the IAP credits purchase page (`get_credits_url()`), generated from the IAP account's `get_credits_url()` method

The frontend renders `'no_credit'` notifications with a prominent "Buy Credits" button linked to the `get_credits_url`.

## Frontend Integration

### JavaScript: `iap_notification_service.js`

File: `static/src/js/services/iap_notification_service.js`

The Odoo web frontend registers a bus listener that consumes `"iap_notification"` messages:

```javascript
// Conceptual overview (not actual code):
busService.addChannel("iap_notification");
busService.on("notification", this, (message) => {
    if (message.type === "no_credit") {
        // Show special "Buy Credits" toast with button
        this.displayNoCreditToast(message.title, message.get_credits_url);
    } else {
        // Show standard toast: success / danger / warning / info
        this.displayToast(message.message, message.type, message.title);
    }
});
```

The JavaScript service decodes the payload and renders appropriate UI elements:
- `success` / `danger` / `warning` / `info` → Standard Odoo notification toasts
- `no_credit` → Special toast with "Buy Credits" action button

### SCSS: `iap_mail.scss`

Styling for notification components. Includes:
- Toast positioning and animation
- Special styling for the "no credit" notification (distinct from regular toasts)
- Dark mode support in `iap_mail.dark.scss`

## IAP Account Form View

The `views/iap_views.xml` adds a `<chatter/>` component to the IAP account form:

```xml
<record id="iap_account_view_form" model="ir.ui.view">
    <field name="name">iap.account.view.form</field>
    <field name="model">iap.account</field>
    <field name="inherit_id" ref="iap.iap_account_view_form"/>
    <field name="arch" type="xml">
        <xpath expr="//sheet" position="after">
            <chatter/>
        </xpath>
    </field>
</record>
```

The `<chatter/>` component (a QWeb template from `mail`) renders the full messaging interface: message thread, followers, activities, and the "Log note / Schedule activity" input area. With `tracking=True` on the key fields, every configuration change is automatically logged.

## Notification Type Reference

| Type | Trigger Condition | Payload | Frontend Rendering |
|------|-----------------|---------|-------------------|
| `success` | IAP operation succeeded | `{message, type: 'success', title?}` | Green toast |
| `danger` | IAP operation failed | `{message, type: 'danger', title?}` | Red toast |
| `warning` | Non-critical warning | `{message, type: 'warning', title?}` | Yellow toast |
| `no_credit` | Insufficient IAP credits | `{title, type: 'no_credit', get_credits_url}` | Red toast with "Buy Credits" button |

## IAP Account Credits System

The `iap.account` model (from the base `iap` module) manages credit pools per service:

- Each IAP service (SMS, enrichment, etc.) has a service name
- Credits are debited per API call
- The `warning_threshold` triggers a notification when credits fall below this level
- `warning_user_ids` specifies who gets notified (not just the account creator)

The `iap_mail` notification methods are typically called in the context of:
1. `credit.run_out()` check before an IAP call
2. Post-call to report success or failure
3. Background cron job monitoring thresholds

## How Other Modules Use `iap_mail`

```
crm_iap_enrich:
  └─ on enrichment success → _send_success_notification()
  └─ on enrichment failure → _send_error_notification()
  └─ on no credits → _send_no_credit_notification()

partner_autocomplete:
  └─ on lookup success → _send_success_notification()
  └─ on lookup failure → _send_error_notification()
  └─ on no credits → _send_no_credit_notification()

iap_sms:
  └─ on SMS send failure → _send_error_notification()
  └─ on no SMS credits → _send_no_credit_notification()

iap_email:
  └─ on email send failure → _send_error_notification()
  └─ on no email credits → _send_no_credit_notification()
```

## Cross-Module Dependencies

| Module | Role | Integration Point |
|--------|------|-------------------|
| [Modules/iap](Modules/iap.md) | IAP account model | `iap.account` is the base model being extended |
| [Modules/mail](Modules/mail.md) | Mail thread and bus | `mail.thread` mixin + Odoo bus system |
| [Modules/iap_crm](Modules/iap_crm.md) | CRM + IAP bridge | Depends on `iap_mail` for notifications |
| [Modules/crm_iap_enrich](Modules/crm_iap_enrich.md) | Lead enrichment | Uses `iap_mail` notification methods |
| [Modules/partner_autocomplete](Modules/partner_autocomplete.md) | Partner data autocomplete | Uses `iap_mail` notification methods |

## Extension Points

| Extension Point | How to Extend |
|-----------------|---------------|
| Custom notification types | Add new type strings (e.g., `'rate_limit'`) and handle them in the JS service |
| Notification aggregation | Override `_send_status_notification()` to batch multiple notifications into one |
| Email fallback | If bus is unavailable, fall back to `mail.message` posting via `mail.thread` |
| Service-specific thresholds | Add per-service threshold fields to `iap.account` and update the cron that checks them |

## Related

- [Modules/iap](Modules/iap.md) -- IAP infrastructure and account management
- [Modules/mail](Modules/mail.md) -- Mail thread, bus, and notification rendering
- [Modules/iap_crm](Modules/iap_crm.md) -- CRM+IAP bridge; depends on `iap_mail`
- [Modules/crm_iap_enrich](Modules/crm_iap_enrich.md) -- Lead enrichment; uses `iap_mail` notifications
- [Modules/partner_autocomplete](Modules/partner_autocomplete.md) -- Partner autocomplete; uses `iap_mail` notifications


## Deep Dive: The Odoo Bus System

The real-time notifications in `iap_mail` rely on the Odoo Bus (WebSocket) system. Understanding how the bus works clarifies why these notifications appear instantly without page refresh.

### The Odoo Bus Architecture

The Odoo Bus is a server-side notification dispatcher backed by PostgreSQL's `LISTEN/NOTIFY` mechanism. When a client (web browser) connects to Odoo, it establishes a long-polling connection to `/bus/im_invalidate` and `/bus/poll`. The server holds the connection open until a notification is pushed.

The flow for an IAP notification:

```
1. IAP service encounters an error or low-credit condition
   └─ e.g., crm_iap_enrich._reveal_lead() fails with "Insufficient credits"

2. Module code calls iap.account._send_no_credit_notification()
   └─ self.env.user._bus_send("iap_notification", params)

3. _bus_send() writes a notification record to the bus
   └─ PostgreSQL NOTIFY 'bus_broadcast' channel

4. All connected Odoo web clients receive the notification
   └─ Via the long-polling /bus/poll endpoint

5. JavaScript service iap_notification_service.js handles the payload
   └─ Renders as a toast notification in the UI

6. User sees the "Buy Credits" toast immediately
   └─ No page refresh, no manual reload
```

### Why Use the Bus Instead of Email or Chatter?

| Mechanism | Latency | User Experience | Context |
|----------|---------|----------------|--------|
| Odoo Bus (toast) | Instant (<1s) | Non-intrusive; can be dismissed | During active session |
| Mail message (chatter) | Seconds to minutes | Persistent; requires navigation | After the fact |
| Email | Minutes to hours | External; requires email client | Important but not urgent |

The bus is the right choice for IAP notifications because:
1. The user is actively working in Odoo when the notification fires
2. Speed matters -- "no credits" errors should interrupt the current workflow
3. The notification is contextual and actionable (click "Buy Credits")

### The `get_credits_url` Method

The `get_credits_url()` method on `iap.account` is defined in the base `iap` module. It returns a URL pointing to Odoo's IAP credit purchase page for the specific service:

```python
# Conceptual:
def get_credits_url(self, service_name):
    return (
        f"https://iap.odoo.com/iap/1/credits"
        f"?service={service_name}"
        f"&acquirer=odoo"
    )
```

This URL is embedded in the `'no_credit'` notification payload. When the user clicks "Buy Credits" in the toast, they are redirected to Odoo's IAP portal to purchase additional credits.

### Credit Threshold Monitoring

The `warning_threshold` and `warning_user_ids` fields enable proactive alerting:

```
Credit balance: 47 / 100 threshold
    |
    v
Background cron runs daily
    |
    v
iap.account._check_credits()  # in base iap module
    |
    v
If credits < warning_threshold:
    |
    v
_send_no_credit_notification()  # Proactive alert
    |
    v
User sees toast: "Running low on enrichment credits (47 remaining)"
```

This proactive approach prevents users from hitting "no credits" errors mid-workflow.

## Notification Styling

### SCSS Architecture

The `iap_mail.scss` file defines the visual presentation of IAP notifications:

```scss
// Conceptual SCSS structure:
.iap_notification {
    // Base toast styles
    display: flex;
    align-items: center;
    padding: 12px 16px;
    border-radius: 4px;

    // Type-specific colors
    &--success { background: $success-color; }
    &--danger   { background: $danger-color; }
    &--warning  { background: $warning-color; }

    // No-credit special styling
    &--no_credit {
        background: $danger-color;
        .o_buy_credits_button {
            background: white;
            color: $danger-color;
        }
    }
}
```

The dark mode variant (`iap_mail.dark.scss`) uses CSS custom properties for theme-aware colors, ensuring notifications remain readable in Odoo's dark mode.

### Toast Positioning

Notifications appear in the top-right corner of the Odoo web client (standard Odoo toast position), layered above all other UI elements. They auto-dismiss after a configurable timeout for success/info types, but `no_credit` and `danger` notifications typically require manual dismissal.

## How IAP Services Consume These Notifications

Every module that uses IAP integrates with `iap_mail` through a consistent pattern:

### Pattern: Before IAP Call

```python
# In crm_iap_enrich, partner_autocomplete, etc.:
def _call_iap_service(self, service_name, params):
    account = self.env['iap.account'].sudo().search([
        ('service_name', '=', service_name)
    ], limit=1)

    if not account:
        return {'error': 'No IAP account configured'}

    # Check credits before making the call
    credits = account._get_credits(service_name)
    if credits <= 0:
        account._send_no_credit_notification(
            service_name,
            title=_("No Credits for %s", service_name)
        )
        return {'error': 'Insufficient credits'}

    try:
        result = iap_jsonrpc(endpoint, params=params)
        account._send_success_notification(
            message=_("Operation completed successfully")
        )
        return result
    except Exception as e:
        account._send_error_notification(str(e))
        return {'error': str(e)}
```

### Pattern: Service-Specific Notifications

Some IAP services send richer notifications:

```python
# CRM enrichment sends specific messages:
account._send_success_notification(
    message=_("Lead '%s' enriched with company data", lead.name),
    title=_("Enrichment Complete")
)

# SMS service sends delivery reports:
account._send_status_notification(
    message=_("SMS delivered to %s", recipient),
    status='success'
)
```

## Security: Who Receives Notifications?

The notifications are sent to `self.env.user` -- the current user making the IAP request. This means:
- Notifications go to the specific user who triggered the IAP call
- Other users working simultaneously on the same database do not receive irrelevant notifications
- Users without IAP account access do not receive notifications

The `warning_user_ids` field on `iap.account` provides a secondary delivery mechanism: specified users also receive notifications even if they didn't directly trigger the IAP call. This is useful for managers or IT admins who want visibility into IAP credit usage across the organization.

## Troubleshooting Notification Issues

### Notifications Not Appearing

If users report that IAP notifications are not showing up:

1. **WebSocket connection** -- Check if the Odoo web client is connected to the longpolling bus (`/longpolling/poll`). If the bus is down, notifications queue up until the next page refresh.
2. **JavaScript errors** -- Open browser DevTools and check for errors in `iap_notification_service.js`.
3. **Missing `mail_bot`** -- The `notification_alert` widget requires the `mail_bot` module to be installed.
4. **User permissions** -- The user must have access to the `iap.account` record being used.
