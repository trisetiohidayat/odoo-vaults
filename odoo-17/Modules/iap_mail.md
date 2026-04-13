---
tags: [odoo, odoo17, module, iap, notifications, bus]
research_depth: medium
---

# IAP Mail — IAP Status Notifications via Bus

**Source:** `addons/iap_mail/models/`

## Overview

Provides real-time in-app notification helpers for IAP service operations. When an IAP service call succeeds, fails, or runs out of credits, this module sends a notification via Odoo's bus (websocket/polling) to the current user. Used by `crm_iap_enrich` and other IAP-dependent modules to give users immediate feedback without page reload.

## Key Model

### iap.account — Notification Dispatchers

**File:** `iap_account.py`

Extends `iap.account` with four notification methods that push to the Odoo bus:

#### `_send_status_notification(message, status, title=None)`

Low-level method that sends a bus notification to the current user:
```python
self.env['bus.bus']._sendone(
    self.env.user.partner_id,
    'iap_notification',
    {'message': ..., 'type': status, 'title': title}
)
```
The `type` field controls the notification styling (e.g., `success`, `danger`, `info`).

#### `_send_success_notification(message, title=None)`

Convenience method for successful IAP operations. Sends `type='success'`.

#### `_send_error_notification(message, title=None)`

Convenience method for failed IAP operations. Sends `type='danger'`.

#### `_send_no_credit_notification(service_name, title)`

Sends a no-credit notification with a "Buy Credits" URL:
```python
{
    'title': title,
    'type': 'no_credit',
    'get_credits_url': self.env['iap.account'].get_credits_url(service_name)
}
```

The `no_credit` type triggers the frontend to show a special "top up credits" banner with a direct link to the IAP purchase page.

## Bus Notification Architecture

```
IAP Service Error
  → iap.account._send_error_notification(...)
  → bus.bus._sendone(partner_id, 'iap_notification', {...})
  → Odoo Bus (polling/websocket)
  → Frontend JavaScript receives event
  → Toast notification shown to user
```

## See Also

- [Modules/iap](odoo-18/Modules/iap.md) — IAP account and credit framework
- [Modules/crm_iap_enrich](odoo-17/Modules/crm_iap_enrich.md) — uses these notifications during lead enrichment
- [Modules/bus](odoo-18/Modules/bus.md) — Odoo real-time bus / pub-sub system