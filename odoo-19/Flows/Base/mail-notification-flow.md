---
type: flow
title: "Mail Notification Flow"
primary_model: mail.message
trigger: "System — message_post / activity_schedule"
cross_module: true
models_touched:
  - mail.message
  - mail.mail
  - mail.notification
  - mail.followers
  - mail.activity
  - bus.bus
  - ir.mail_server
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Sale/quotation-to-sale-order-flow](flows/sale/quotation-to-sale-order-flow.md)"
  - "[Flows/HR/leave-request-flow](flows/hr/leave-request-flow.md)"
  - "[Flows/Helpdesk/ticket-creation-flow](flows/helpdesk/ticket-creation-flow.md)"
  - "[Flows/Website/website-sale-flow](flows/website/website-sale-flow.md)"
related_guides:
  - "[Modules/mail](modules/mail.md)"
source_module: mail
source_path: ~/odoo/odoo19/odoo/addons/mail/models/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Mail Notification Flow

## Overview

This flow covers how Odoo generates and delivers email and in-app notifications when model events occur. The primary entry point is `mail.message.create()` (via `message_post()`), which creates a `mail.message` record, determines its followers from `mail.followers`, and triggers `_notify_thread()` — the central dispatcher that splits work between in-app notifications (`mail.notification` → `bus.bus` real-time push) and email delivery (`mail.mail` → `ir.mail_server` SMTP). A parallel entry point is `activity.schedule()`, which creates `mail.activity` records with deadline tracking. The flow is highly extensible via `mail.thread` mixin hooks and template rendering.

## Trigger Point

Multiple independent triggers can start this flow:

**Primary trigger:** `model.message_post()` called on any `mail.thread` model (sale.order, hr.leave, helpdesk.ticket, etc.). This is the universal notification entry point.

**Secondary trigger:** `mail.activity.schedule()` called when an activity (task, approval, reminder) is created.

**Alternative triggers:**
- **Email gateway:** `mail.gateway.process()` receives inbound emails and creates messages
- **Mass mailing:** `mail.mass_mailing.send()` creates batch messages via `mailing.trace`
- **Scheduled messages:** `mail.message.schedule` cron processes deferred messages
- **Workflow action:** Odoo workflow transitions that call `message_post()`
- **API / external:** `mail.message.create()` via RPC from external systems

---

## Complete Method Chain

```
=== ENTRY POINT A: message_post ===

1. any.model.message_post(body='...', subject='...', subtype_xmlid='mail.mt_comment')
   └─► 2. mail.message.create(vals)
         ├─► 3. message_type set (comment, notification, email_in, email_out)
         ├─► 4. @_DEFAULT_VALUES context — sets author, date, subtype
         └─► 5. mail.message.record_create()  [triggers notifications]
               └─► 6. _notify_thread()  [central dispatcher]
                     ├─► 7. _notify_record_by_inbox()  [in-app]
                     │      └─► 8. mail.notification.create([
                     │            {'mail_message_id': msg.id, 'res_partner_id': partner.id,
                     │             'notification_type': 'inbox', 'is_read': False}
                     │          ])
                     │            └─► 9. bus.bus.sendone(channel, notification_data)
                     │                  └─► 10. websocket push to connected clients
                     │
                     ├─► 11. _notify_record_by_email()  [email delivery]
                     │      ├─► 12. _notify_compute_by() → fetch follower partner records
                     │      │      └─► 13. mail.followers._followers_from_partners()
                     │      │            ├─► 14. Followers from `followers` relation
                     │      │            ├─► 15. Channels (mail.channel) where partner is member
                     │      │            └─► 16. Filter by `subtype_ids` (only matching subtypes)
                     │      │
                     │      ├─► 17. _template_to_generate_the_message() → render template
                     │      │      └─► 18. mail.template.send_mail() or inline body rendered
                     │      │            ├─► 19. mako template engine renders body_html
                     │      │            └─► 20. ir.qweb renders QWeb templates (if used)
                     │      │
                     │      └─► 21. mail.mail.create([{
                     │            'mail_message_id': msg.id,
                     │            'partner_ids': [follower.partner_id.id],
                     │            'subject': msg.subject,
                     │            'body_html': rendered_body,
                     │            'email_from': author.email,
                     │            'reply_to': reply_to,
                     │            'state': 'outgoing',
                     │            'is_notification': True
                     │          }])
                     │            └─► 22. mail.mail._postprocess_sent_message()  [empty hook]
                     │
                     └─► 23. _notify_record_by_web_push()  [optional, if web_push configured]
                           └─► 24. web push notification via push service

=== ENTRY POINT B: activity_schedule ===

25. any.model.activity_schedule(
     activity_type_id=type_id,
     date_deadline=deadline_date,
     summary='...',
     note='...',
     user_id=assignee.id
   )
   └─► 26. mail.activity.create({
         'res_model': self._name,
         'res_id': self.id,
         'activity_type_id': type_id,
         'date_deadline': deadline_date,
         'summary': summary,
         'note': note,
         'user_id': user_id,
         'create_uid': current_user.id
       })
         └─► 27. @api.depends('date_deadline') → deadline_display computed
         └─► 28. mail.activity._action_done_category_check()
               ├─► 29. bus.bus.sendone() → real-time notification of new activity
               └─► 30. mail.mail.create() → activity assignment email sent to user_id

=== EMAIL DELIVERY (async via cron) ===

31. ir.mail_server.send()  [via mail.mail.process_email_queue() cron]
   └─► 32. mail.mail.send()
         ├─► 33. _split_by_mail_configuration() → group by mail_server + alias_domain
         ├─► 34. ir.mail_server._connect__() → SMTP connection established
         ├─► 35. _send() → SMTP MAIL FROM / RCPT TO / DATA
         │      ├─► 36. _prepare_email() → build RFC-compliant MIME message
         │      ├─► 37. SMTP data sent via smtplib.SMTP.send_message()
         │      └─► 38. On success: write({'state': 'sent'})
         │
         └─► On failure:
               ├─► 39. write({'state': 'exception', 'failure_reason': error})
               └─► 40. _postprocess_sent_message(failure_type='mail_smtp')
                     └─► 41. mail.notification.write({
                           'notification_status': 'bounce',
                           'failure_reason': error
                         })
                     └─► 42. mail.mail._sendmail_fail_callback()  [audit log]

=== BUS REAL-TIME NOTIFICATION ===

43. bus.bus.sendone(channel='[Modules/mail](modules/mail.md), notification_type, message_dict')
   └─► 44. bus.bus table updated with notification row
         └─► 45. websocket long-polling push to Odoo web client
               └─► 46. JavaScript receives notification → updates inbox badge / toast
```

---

## Decision Tree

```
Event occurs (order confirmed, leave requested, ticket created)
│
├─► message_post() called
│   │
│   ├─► Determine recipients:
│   │  ├─► Followers of the record (mail.followers)
│   │  ├─► Partners in subscribed channels (mail.channel)
│   │  └─► Specific partner_ids passed explicitly
│   │
│   ├─► Determine channel:
│   │  ├─► subtype_xmlid = 'mail.mt_comment' → comment notification
│   │  ├─► subtype_xmlid = 'mail.mt_note' → internal note (no email)
│   │  └─► subtype_xmlid = 'mail.mt_*' → subtype-matched followers
│   │
│   ├─► Notification type for each recipient:
│   │  ├─► Follower + subtype allows email → email sent
│   │  ├─► Follower in channel → inbox notification
│   │  └─► subtype is internal note → inbox only, no email
│   │
│   └─► Template rendering:
│      ├─► Email template defined? → send_mail() with mako rendering
│      └─► No template? → inline body used as email body
│
├─► activity_schedule() called
│   ├─► mail.activity created
│   ├─► User assigned → bus.bus notification
│   └─► Email sent to assignee (if email_from set in template)
│
└─► mail.mail processed by cron:
   ├─► SMTP success → state = 'sent', notification = 'sent'
   ├─► SMTP failure → state = 'exception', notification = 'bounce'
   └─► Retry on next cron run (up to 3x typically)
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `mail_message` | Created | `model`, `res_id`, `message_type`, `subtype_id`, `body`, `author_id`, `subject`, `date`, `create_uid` |
| `mail_notification` | Created per recipient | `mail_message_id`, `res_partner_id`, `notification_type` ('inbox'/'email'), `notification_status` ('read'/'sent'/'bounce'), `failure_reason` |
| `mail_mail` | Created per batch | `mail_message_id`, `partner_ids`, `email_from`, `reply_to`, `body_html`, `state` ('outgoing'/'sent'/'exception'/'cancel'), `is_notification` |
| `mail_followers` | Created/Updated | `res_model`, `res_id`, `partner_id`, `channel_id`, `subtype_ids` |
| `mail_activity` | Created (activity entry) | `res_model`, `res_id`, `activity_type_id`, `user_id`, `date_deadline`, `summary`, `note` |
| `bus_bus` | Created (temporary) | `channel`, `message` — polled and deleted by websocket clients |
| `ir_attachment` | Created (if attachments) | Linked to `mail_message_id` via `attachment_ids` |
| `mail_mail_trace` | Created (mass mailing) | `mail_mail_id`, `model`, `res_id`, `trace_status` |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| SMTP server not configured | `mail.mail` state = 'exception' | `ir.mail_server` record missing or inactive; logged as failure |
| Invalid recipient email | Bounce — `notification_status = 'bounce'` | Mail returned by recipient MTA; tracked in `failure_reason` |
| Partner has no email | `mail.mail` not created for that partner | `partner_id.email` is empty; skipped in `_notify_compute_by()` |
| Follower not in allowed recipients | No notification created | ACL on `mail.followers` / `mail.group` restricts visibility |
| Message posted on non-mail.thread model | No-op or error | `mail.thread` mixin required; methods don't exist otherwise |
| Circular notification (author = recipient) | Skipped | `_notify_record_by_email()` excludes `author_id` from recipients |
| Mail server connection timeout | `MailDeliveryException` | `_connect__()` fails; `mail.mail` state = 'exception', retried |
| Activity deadline in past | Created anyway — warning shown | `date_deadline` can be any date; no automatic filtering |
| Blacklisted email | Skipped silently | `mail.blacklist` check in `_notify_record_by_email()` |
| Concurrent message_post | Normal ORM behavior | Each `create()` is atomic; no special deduplication |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| In-app inbox notification | `mail.notification` | Record created for each follower; appears in Odoo inbox |
| Real-time bus push | `bus.bus` | WebSocket push to Odoo web client; updates inbox badge live |
| Email queued for SMTP | `mail.mail` | `state = 'outgoing'`; processed by `process_email_queue()` cron |
| Email delivered via SMTP | `mail.mail` | `state = 'sent'`; `notification.notification_status = 'sent'` |
| Email bounced by MTA | `mail.mail` | `state = 'exception'`; `notification_status = 'bounce'` |
| Follower auto-subscribed | `mail.followers` | Follower added if not already present |
| Attachment stored | `ir_attachment` | Binary content stored in filestore; linked to message |
| Activity created | `mail.activity` | To-do created in user's activity dashboard |
| Out-of-office auto-reply | `mail.mail` | If Odoo receives inbound email and user is OOO |
| Message translation | `mail.message.translation` | Stored if `mail.message.translation` module active |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `message_post()` | Current user | Read/Write on `mail.thread` model | Author is current user; subtype checked |
| `mail.message.create()` | Current user | `mail.group` for posting in channels | `mail.message` ACL |
| `_notify_thread()` | `sudo()` internally | System | ORM uses `sudo()` to create notifications |
| `mail.followers.create()` | `sudo()` | System | Framework creates followers via `sudo()` |
| `_notify_record_by_email()` | `sudo()` | System | Bypasses ACL to send to all followers |
| `mail.mail.create()` | System | System | Queued for async delivery |
| `mail.mail.send()` | Cron (superuser) | `group_mail` | `process_email_queue()` runs as superuser |
| `_notify_record_by_inbox()` | `sudo()` | System | Writes notifications for all followers |
| `bus.bus.sendone()` | Public | System | Bus channel security via `channel` field |
| `activity_schedule()` | Current user | `mail.activity` create | Creates activity as current user |
| `mail.activity.create()` | `sudo()` | System | Activity created with `sudo()` in `schedule()` |
| `ir.mail_server` access | `group_mail` | `ir.mail_server` read | SMTP server credentials protected |

**Key principle:** `message_post()` runs as the current user, but the notification creation inside `_notify_thread()` uses `sudo()` internally to ensure all followers receive notifications regardless of access rights. The email is sent as the system (no "from" address attribution to the actual user unless explicitly set via `email_from`).

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside.*

```
Steps 1–6   ✅ INSIDE transaction  — mail.message created
Steps 7–30  ✅ INSIDE transaction  — _notify_thread() + mail.notification + mail.mail created
Steps 31–42 ❌ OUTSIDE transaction — mail.mail.send() via process_email_queue() cron
Step 43–46  ❌ OUTSIDE transaction — bus.bus table write + websocket push
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| `mail.message.create()` | ✅ Atomic | Rollback on validation error |
| `mail.notification.create()` | ✅ Atomic | Rolled back with parent transaction |
| `mail.mail.create()` | ✅ Atomic | Rolled back with parent transaction |
| `bus.bus.sendone()` | ❌ Outside transaction | Written to bus table; polled asynchronously |
| `mail.mail.send()` | ❌ Separate cron transaction | Runs in its own transaction; commits after batch |
| `_postprocess_sent_message()` | ❌ Within mail.mail.send() | Same transaction as send; rolled back on send failure |
| `mail.mail._sendmail_fail_callback()` | ❌ After send() | Runs in send() exception handler; separate from main flow |
| `activity_schedule()` | ✅ Atomic | mail.activity created within same transaction |

**Rule of thumb:** All `mail.message` and `mail.notification` records are created within the same transaction as the triggering event. The actual SMTP delivery happens later via cron and is independent — if the transaction rolls back after `message_post()`, no email is sent. If the transaction commits but the cron later fails to deliver email, `mail.mail.state = 'exception'` is recorded and retried.

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Double-post `message_post()` | Two separate `mail.message` records created — no deduplication |
| Same message ID on webhook | `mail.gateway` checks `message_id` (MIME Message-ID) for duplicates |
| `mail.mail.send()` re-run on already-sent mail | `send()` skips `state = 'sent'` records — no-op |
| `bus.bus.sendone()` called twice | Two rows in bus table; client handles duplicates |
| Activity scheduled twice (same activity) | Two `mail.activity` records created — no deduplication |
| Concurrent `message_post()` on same record | Two separate messages — each atomic, no conflict |
| SMTP retry after timeout | `mail.mail` re-sent; idempotent if provider is idempotent |
| Notification marked as read twice | Second `write({'is_read': True})` is no-op |

**Common patterns:**
- **Idempotent:** `mail.mail.send()` (checks `state`), `bus.bus.sendone()` (no conflict), `mail.notification.write()` (no-op on re-read)
- **Non-idempotent:** `mail.message.create()` (new record each time), `mail.activity.create()` (new record each time)
- **Deduplication at boundary:** Inbound email gateway uses `Message-ID` header to prevent duplicate imports

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 2 | `_message_create()` | Custom message creation | `vals_list` | Extend to add default fields |
| Step 6 | `_notify_thread()` | Master notification dispatcher | `message, msg_vals` | Redirect to custom channels |
| Step 7 | `_notify_record_by_inbox()` | Custom inbox notification logic | `message, recipients_data` | Add push notification logic |
| Step 11 | `_notify_record_by_email()` | Custom email notification logic | `message, recipients_data` | Add BCC, attachments, custom headers |
| Step 12 | `_notify_compute_by()` | Custom recipient resolution | `message, msg_vals` | Add recipient filtering logic |
| Step 17 | `_notify_template_to_generate()` | Custom template selection | `message, recipients` | Use custom template per model |
| Step 18 | `mail.template.send_mail()` | Template rendering | `template_id, res_id` | Override mako template rendering |
| Step 21 | `mail.mail.create()` | Pre-email creation hook | vals | Add custom headers or tracking pixels |
| Step 25 | `activity_schedule()` | Pre-activity creation hook | `activity_type_id, date_deadline` | Extend with custom defaults |
| Step 28 | `_action_done_category_check()` | Custom activity done logic | `self` | Add custom activity completion rules |
| Step 31 | `send()` | Custom SMTP delivery | `auto_commit` | Add custom SMTP headers or routing |
| Step 36 | `_prepare_email()` | Custom MIME message build | `mail, values` | Add custom MIME parts (inline images) |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def _notify_record_by_email(self, message, recipients_data):
    # your code

# CORRECT — extends with super()
def _notify_record_by_email(self, message, recipients_data, **kwargs):
    super()._notify_record_by_email(message, recipients_data, **kwargs)
    # your additional code
```

**Odoo 19 specific hooks:**
- `mail.thread` mixin provides `_notify_thread()`, `_notify_record_by_inbox()`, `_notify_record_by_email()`, and `_notify_record_by_web_push()` as the primary extension points
- `_message_post_after_hook()` called after `message_post()` completes — useful for side effects
- `mail.mail._preprocess_sent_message()` can be overridden to add tracking or modify email content before send
- `_notify_single_email()` controls how each individual recipient's email is rendered
- `activity_schedule()` accepts `chaining_type` to control what happens when the activity is marked done

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `mail.thread` model overrides of `message_post()` without calling `super()` — breaks notification chain
- Overriding `mail.mail.send()` without calling `super()` — breaks SMTP delivery entirely

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `mail.message.create()` | `unlink()` | `mail.message.unlink()` | Cascade deletes `mail.notification` + `mail.mail` (if outgoing) |
| `mail.notification` (unread) | `write({'is_read': True})` | Mark as read | Inbox notification cleared from unread |
| `mail.notification` (bounced) | Cannot reverse bounce | Manual re-queue | Must manually reset `notification_status` and re-send |
| `mail.mail` (outgoing, not sent) | `write({'state': 'cancel'})` | `cancel()` | Cancels email; not recoverable |
| `mail.mail` (sent) | Cannot recall email | External MTA | Must send apology email or correction |
| `mail.mail` (exception) | `write({'state': 'outgoing'})` + `retry()` | `action_retry()` | Re-queues for next cron run |
| `mail.activity` created | `unlink()` | `mail.activity.unlink()` | Only before activity is marked done |
| `bus.bus` notification | Cannot reverse | — | Bus is ephemeral — disappears on next poll |
| `mail.followers` subscribed | `unlink()` | `unfollow()` | Partner unsubscribed from record |
| Inbound message import | `unlink()` | `mail.message.unlink()` | Only if not linked to a record that must keep history |

**Important:** This flow is **partially reversible**:
- Outgoing mail (`state = 'outgoing'`) can be cancelled before cron sends it
- Once sent (`state = 'sent'`), the email is delivered and cannot be recalled — Odoo has no recall mechanism
- Bounced emails can be retried by resetting state to 'outgoing'
- Message deletion cascades to notifications — followers lose the message from their inbox
- Bus notifications are ephemeral and disappear from the bus table after polling

---

## Alternative Triggers

> *All the ways this flow can be initiated.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `message_post()` on any record | Interactive (UI) | Manual |
| User action | `activity_schedule()` | Interactive (UI) | Manual |
| System event | `action_confirm()` → `message_post()` | Automated | On order confirmation |
| Email gateway | `mail.gateway.process()` | Inbound email | On email received |
| Cron scheduler | `process_email_queue()` | Server | Every 5 minutes (configurable) |
| Cron scheduler | `mail.message.schedule` | Deferred message | At scheduled time |
| Mass mailing | `mail.mass_mailing.send()` | Marketing | Per campaign |
| Webhook | External system via `message_post` RPC | External | On external event |
| Automated action | `base.automation` rule | Rule triggered | On rule match |
| Workflow engine | `wkf_action()` → `message_post()` | Legacy workflows | On state transition |

---

## Related

- [Modules/mail](modules/mail.md) — Mail module reference
- [Modules/mail](modules/mail.md) — Activity module reference
- [Flows/Sale/quotation-to-sale-order-flow](flows/sale/quotation-to-sale-order-flow.md) — Sale order notification side effects
- [Flows/HR/leave-request-flow](flows/hr/leave-request-flow.md) — Leave request notification side effects
- [Flows/Helpdesk/ticket-creation-flow](flows/helpdesk/ticket-creation-flow.md) — Helpdesk notification side effects
- [Flows/Website/website-sale-flow](flows/website/website-sale-flow.md) — Website sale confirmation email
- [Modules/mail](modules/mail.md) — Email configuration guide
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — Workflow pattern reference
- [Core/API](core/api.md) — @api decorator patterns
