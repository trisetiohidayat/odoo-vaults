---
Module: product_email_template
Version: 18.0.0
Type: addon
Tags: #odoo18 #product #email #invoice
---

## Overview

Attaches optional email templates to product templates. When a customer invoice is validated, an email is automatically sent to the customer for each line product that has an email template configured.

**Depends:** `product`, `mail`

**Key Behavior:** Triggers on `_post()` (invoice validation), sends one email per line with a linked `email_template_id`. Automatically subscribes the invoice partner.

---

## Models

### `product.template` (Inherited)

**Inherited from:** `product.template`

| Field | Type | Note |
|-------|------|------|
| `email_template_id` | Many2one `mail.template` | Email template to send on invoice validation |

### `account.move` (Inherited)

**Inherited from:** `account.move`

| Method | Returns | Note |
|--------|---------|------|
| `invoice_validate_send_email()` | Boolean | Iterates invoice lines; if `product_id.email_template_id` exists, calls `message_post_with_source` |
| `_post(soft=True)` | recordset | Overrides to call `invoice_validate_send_email()` after posting |

**Behavior:** Only sends on `out_invoice` move type. Subscribes partner before sending. Runs as `SUPERUSER_ID`.
