---
tags: [odoo, odoo17, module, portal]
---

# Portal Module

**Source:** `addons/portal/models/`

## Overview

Provides customer portal access, allowing external users to view and interact with records assigned to them (e.g., sale orders, invoices, support tickets). Portal users are `res.users` records with `share=True`.

## Key Models

| Model | File | Description |
|-------|------|-------------|
| `portal.mixin` | `portal_mixin.py` | Abstract mixin for portal-enabled models |
| `portal.wizard` | `portal_mixin.py` | Portal invitation wizard |
| `res.partner` | `res_partner.py` | Partner portal preferences |
| `mail.thread` | `mail_thread.py` | Portal chatter / message posting |

## portal.mixin

Abstract mixin (`_name = 'portal.mixin'`) that adds portal sharing capabilities to any model.

### Fields

- `access_url` — Portal-accessible URL (computed, defaults to `#`)
- `access_token` — UUID security token for share links
- `access_warning` — Access warning text (e.g., "Impossible to send emails...")

### Key Methods

- `_compute_access_url` — Override per model to return the website URL
- `_portal_ensure_token` — Generate/store UUID access token on first use
- `_get_share_url(redirect, signup_partner, pid, share_token)` — Build share URL with access_token and optional auth hash
- `_get_access_action(access_uid, force_website)` — Redirects portal users to website instead of backend form view
- `get_portal_url(suffix, report_type, download, query_string, anchor)` — Full portal URL with access token

### Mixin Usage

```python
class MyModel(models.Model):
    _inherit = 'portal.mixin'
    # Adds portal sharing to the model automatically
```

### Automatic Additions

When inheriting `portal.mixin`, the model automatically gains:
- `_message_get_default_recipients()` — For mail threading
- `_get_report_base_filename()` — For report naming

## Portal Sharing Flow

1. Backend user clicks "Share" on a portal-enabled record
2. `_get_share_url()` builds a URL with `access_token` parameter
3. Recipient visits URL — Odoo validates token and renders website view
4. If `signup_partner=True`, pre-filled account creation is offered

## See Also

- [Modules/mail](mail.md) — Mail threading and messaging
- [Modules/sale](sale.md) — Sale orders portal access
- [Modules/account](account.md) — Invoice portal access
