# sale_async_emails — Sale Async Emails

**Tags:** #odoo #odoo18 #sale #email #async #workflow
**Odoo Version:** 18.0
**Module Category:** Sale / Email Notification
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_async_emails` introduces a pending email queue for sale order notifications. When a sale order is confirmed, the notification email is not sent immediately — instead it is queued via `pending_email_template_id` and sent asynchronously via a scheduled cron job. This prevents email floods from bulk order confirmations and provides a reliable delivery mechanism.

**Technical Name:** `sale_async_emails`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_async_emails/`
**Depends:** `sale`
**Inherits From:** `sale.order`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/sale_order.py` | `sale.order` | Pending email tracking, async send, cron job |

---

## Models Reference

### `sale.order` (models/sale_order.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `pending_email_template_id` | Many2one (`mail.template`) | Email template queued for async sending, readonly |

#### Methods

| Method | Decorators | Behavior |
|--------|-----------|----------|
| `_send_order_notification_mail()` | — | Called by `action_confirm()`: sets `pending_email_template_id` to the order confirmation template; does NOT send immediately |
| `_cron_send_pending_emails()` | `@api.model` | Cron job: searches SOs with `pending_email_template_id`, calls `_send_order_notification_mail()` for each, then clears the pending template |

#### Critical Flow

```
SO Confirmed (action_confirm)
  → _send_order_notification_mail()
    → pending_email_template_id = mail_template_sale_confirmation
    → returns WITHOUT sending email

Cron: _cron_send_pending_emails() (scheduled, runs independently)
  → browse SOs with pending_email_template_id set
  → for each SO: _send_order_notification_mail() (which sends now)
  → clear pending_email_template_id
```

**Note**: `_send_order_notification_mail()` is the same method called immediately in the base `sale` module. In `sale_async_emails`, the first call (during `action_confirm`) only stores the template ID — the second call (from the cron) actually triggers the email.

---

## Security File

No security file (`security/` directory does not exist in this module).

---

## Data Files

| File | Content |
|------|---------|
| `data/ir_actions_server.xml` | `_cron_send_pending_emails` scheduled action (runs daily at 9:00 AM) |

---

## Critical Behaviors

1. **Email Queuing**: Instead of sending the confirmation email immediately on SO confirmation, the template is stored as pending. This decouples order confirmation from email delivery.

2. **Same Method Reuse**: `_send_order_notification_mail()` is idempotent — calling it from the cron with `pending_email_template_id` already set sends the email, then clears the pending state.

3. **Bulk Protection**: If 1000 SOs are confirmed in a batch import, the emails are deferred rather than sent all at once, preventing SMTP throttling or reputation damage from burst sending.

4. **Retry on Failure**: If the email send fails during the cron run, `pending_email_template_id` remains set, and the next cron run retries.

---

## v17→v18 Changes

No significant changes from v17 to v18 identified. Module structure and logic remain consistent.

---

## Notes

- This module is minimal (1 file, ~30 lines of actual logic) but provides important production stability for high-volume order processing
- The `pending_email_template_id` field acts as both a queue marker and a retry flag
- The cron runs daily but can be triggered manually or on-demand if faster delivery is needed
- Compatible with all email templates on `sale.order` (confirmation, cancellation, etc.)
