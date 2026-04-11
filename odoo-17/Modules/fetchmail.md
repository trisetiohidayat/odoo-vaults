---
tags: [odoo, odoo17, module, fetchmail]
---

# Fetchmail Module

**Status: NOT PRESENT in Odoo 17**

In Odoo 17, the `fetchmail` module has been removed. Incoming email functionality has been consolidated into the `mail` module.

## Historical Context

In Odoo versions prior to 17, `fetchmail` was a standalone module that:
- Connected to IMAP/POP3 servers via `fetchmail.server`
- Created `mail.message` / `mail.thread` records from incoming emails
- Supported linking emails to `crm.lead`, `helpdesk.ticket`, etc.

## Odoo 17 Replacement

In Odoo 17, email fetching is handled entirely within the **`mail`** module:

| Old `fetchmail` Concept | Odoo 17 Location |
|------------------------|-------------------|
| `fetchmail.server` (IMAP/POP) | `ir.mail_server` (in `mail` module) |
| Incoming mail processing | `mail.mail` / `mail.message` inbound processing |
| Email-to-lead | `crm.lead` (via `mail.thread` mixin) |
| Email-to-ticket | `helpdesk.ticket` (via `mail.thread` mixin) |

## See Also
- [[Modules/Mail]] — Email integration in Odoo 17
- [[Modules/CRM]] — Lead management
