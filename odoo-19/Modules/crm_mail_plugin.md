---
type: module
module: crm_mail_plugin
tags: [odoo, odoo19, crm, mail, outlook, plugin]
created: 2026-04-06
---

# CRM Mail Plugin

## Overview
| Property | Value |
|----------|-------|
| **Name** | CRM Mail Plugin |
| **Technical** | `crm_mail_plugin` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Integrates CRM functionality into the Outlook/email mail plugin. Enables users to turn emails received in their mailbox into CRM leads and log email content as internal notes.

## Dependencies
- `crm`
- `mail_plugin`

## Models

### crm.lead
Inherits `crm.lead`. Extends lead with mail plugin support.

**Key Methods:**
- `_form_view_auto_fill()` — Deprecated method (kept for backward compatibility with older mail plugin versions); sets default `partner_id` from the email sender context

## Key Features

### Email to Lead Conversion
- Works with the `mail_plugin` module to inject CRM actions into email clients (Outlook, Gmail)
- Creates leads from incoming emails via the mail plugin UI
- Logs email content as internal notes (`mail.mt_note`) on the lead

### Compatibility
- `_form_view_auto_fill()` — deprecated since SaaS-14.3, kept for supporting older mail plugin versions

## Related
- [Modules/crm](odoo-18/Modules/CRM.md) — CRM base
- [Modules/mail_plugin](odoo-17/Modules/mail_plugin.md) — Mail plugin base
- [Modules/crm_livechat](odoo-17/Modules/crm_livechat.md) — CRM + Livechat
