---
type: module
name: mail
version: Odoo 18
tags: [module, mail, messaging, notifications, email, chatter, discuss]
source: ~/odoo/odoo18/odoo/addons/mail/
---

# mail

Core messaging system — email integration, notifications, followers, activities, Chatter, and real-time Discuss.

**Source:** `addons/mail/`
**Depends:** `base`, `bus`, `html_editor`

---

## Key Models

| Model | Technical Name | Purpose |
|-------|--------------|---------|
| Mail Thread | `mail.thread` | Abstract mixin enabling Chatter on any model |
| Message | `mail.message` | Stored messages and notifications |
| Outbound Email | `mail.mail` | RFC2822 email queue (`_inherits mail.message`) |
| Notification | `mail.notification` | Per-recipient delivery status tracking |
| Document Followers | `mail.followers` | Subscription management |
| Activity | `mail.activity` | Tasks with deadlines and assignees |
| Email Alias | `mail.alias` | Inbound email gateway routing |
| Email Blacklist | `mail.blacklist` | Suppress email delivery |
| Activity Type | `mail.activity.type` | Activity category definitions |
| Message Subtype | `mail.message.subtype` | Per-follower notification tuning |
| Tracking Value | `mail.tracking.value` | Field change audit trail |
| Mail Template | `mail.template` | QWeb email templates |
| Discussion Channel | `discuss.channel` | Live chat / channel / group |
| Channel Member | `discuss.channel.member` | Channel membership + RTC sessions |
| Mail Guest | `mail.guest` | Anonymous chat user |
| Mail Alias Domain | `mail.alias.domain` | Domain-level alias config |

---

## `mail.thread` — Abstract Mixin

```python
class MailThread(models.AbstractModel):
    _name = 'mail.thread'
    _mail_flat_thread = True        # Flat replies (vs nested)
    _mail_post_access = 'write'     # Access right to post
    _primary_email = 'email'        # Field for email resolution
```

**Mixin Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `message_is_follower` | Boolean (compute/search) | Is current user following |
| `message_follower_ids` | One2many | All followers |
| `message_partner_ids` | Many2many | Writable follower partners |
| `message_ids` | One2many | All messages on record |
| `message_needaction_counter` | Integer (compute) | Unread count |
| `message_has_error_counter` | Integer (compute) | Error count |

**Key Methods:**
| Method | Description |
|--------|-------------|
| `message_post()` | Post a message — returns `mail.message` |
| `message_subscribe(partner_ids, subtype_ids)` | Subscribe followers |
| `message_unsubscribe(partner_ids)` | Unsubscribe |
| `message_notify()` | Send notification to followers |
| `message_track(fields_iter, initial)` | Track field changes |
| `message_route()` | Route inbound email via gateway |
| `message_process(model, message)` | Parse incoming RFC2822 email |

**Context Keys:**
- `mail_create_nosubscribe` — don't subscribe uid on create
- `mail_notrack` — disable tracking on write
- `tracking_disable` — disable all MailThread features

---

## `mail.message` — Message

```python
class Message(models.Model):
    _name = 'mail.message'
    _inherit = ["bus.listener.mixin"]
    _order = 'id desc'
    _rec_name = 'record_name'
```

**message_type values:**
```
email         → Incoming via gateway
comment       → User comment (Discuss/composer)
email_outgoing → Mass mailing
notification  → System-generated
auto_comment  → Automated targeted
user_notification → Targeted at specific user
```

**notification_status values:**
```
ready → Queued for sending
process → Being processed (e.g. SMS via IAP)
pending → Sent (SMS)
sent → Delivered
bounce → Rejected by MTA
exception → Delivery failed
canceled → Cancelled
```

**Access Control (custom `_check_access`):**
- **Read**: author, recipient, has notification, or read access on related doc
- **Create**: no model/res_id (private), author is follower, can read parent, or write access
- **Unlink**: requires write/create access on related document
- Internal messages (`is_internal=True`) hidden from non-employees

---

## `mail.mail` — Outbound Email

```python
class MailMail(models.Model):
    _name = 'mail.mail'
    _inherits = {'mail.message': 'mail_message_id'}
    # Delegates: subject, body, email_from, reply_to, author_id, date, message_type
```

**Lifecycle:**
```
outgoing → sent         (send() succeeds)
outgoing → exception    (send() fails)
outgoing → cancel      (cancel() called)
exception → outgoing    (action_retry)
any → cancel           (cancel())
```

**Key Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `body_html` | Text | RFC2822 HTML body |
| `is_notification` | Boolean | Notify about existing mail.message |
| `scheduled_date` | Datetime | Deferred send (naive UTC) |
| `recipient_ids` | Many2many | Partner recipients |
| `state` | Selection | outgoing/sent/exception/cancel |
| `failure_type` | Selection | mail_bounce, mail_email_invalid, etc. |

**Failure Modes:**
- `is_notification=False` unlink cascades to parent `mail.message`
- `unrestricted_attachment_ids` filters attachments user can read
- `is_notification` auto-defaults to `True` if `mail_message_id` provided

---

## `mail.notification` — Notification

```python
class MailNotification(models.Model):
    _name = 'mail.notification'
    _log_access = False
```

**notification_type:** `inbox` | `email`
**notification_status:** `ready` | `sent` | `bounce` | `exception` | `canceled`

**Key Methods:**
- `_filtered_for_web_client()` — strip inaccessible notifications
- `_to_store(store)` — serialize for front-end
- `_gc_notifications(max_age_days=180)` — cron: delete old read notifications

**Indexes:**
```sql
-- Efficient unread inbox queries
CREATE INDEX mail_notification_res_partner_id_is_read_notification_status_mail_message_id
    ON mail_notification (res_partner_id, is_read, notification_status, mail_message_id);
```

---

## `mail.followers` — Followers

```python
class Followers(models.Model):
    _name = 'mail.followers'
    _log_access = False
```

**Key:** Uses `res_model`/`res_id` generic references (no FK constraint) — enables following any model.

**_sql_constraints:**
```python
unique(res_model, res_id, partner_id)  -- cannot follow same object twice
```

**Key Methods:**
- `_get_recipient_data()` — raw SQL CTE for efficient notification targeting
- `_get_mail_recipients_follower_status()` — raw SQL for follower status

---

## `mail.activity` — Activity

```python
class MailActivity(models.Model):
    _name = 'mail.activity'
    _order = 'date_deadline ASC, id ASC'
```

**Key Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `res_model_id` | Many2one | Target model (cascade delete) |
| `res_id` | Integer | Target record ID — **SQL constraint: NOT NULL AND != 0** |
| `activity_type_id` | Many2one | Category (restrict delete) |
| `date_deadline` | Date | Due date (default=today) |
| `user_id` | Many2one | Assigned user (cascade) |
| `state` | Selection | Computed: overdue / today / planned / done |
| `chaining_type` | Selection | `suggest` (propose next) or `trigger` (auto-create next) |
| `automated` | Boolean | Auto-created activity |

**Key Actions:**
| Method | Returns | Description |
|--------|---------|-------------|
| `action_done()` | bool | Mark done |
| `action_feedback(feedback, attachment_ids)` | message.id | Done + optional note |
| `action_feedback_schedule_next()` | wizard action | Done + schedule next |
| `_action_done()` | (messages, next_activities) | Internal implementation |

**Custom Access:** Users can always mark their own activities done even without document write access.

---

## `mail.activity.type` — Activity Type

| Field | Key | Description |
|-------|-----|-------------|
| `name` | required, translate | Display name |
| `delay_count` | default=0 | Offset before deadline |
| `delay_unit` | default=days | days / weeks / months |
| `delay_from` | default=previous_activity | Reference for delay |
| `chaining_type` | default=suggest | suggest / trigger |
| `triggered_next_type_id` | Many2one | Auto-schedule next type |
| `suggested_next_type_ids` | Many2many | Propose these next |
| `mail_template_ids` | Many2many | Email templates on completion |

---

## `mail.activity.plan` / `mail.activity.plan.template`

Bulk activity scheduling templates.
- `mail.activity.plan` — container with steps
- `mail.activity.plan.template` — individual activity steps with `responsible_type` (officer/on_demand/using_template/generic_user_field)

---

## `mail.blacklist` — Email Blacklist

```python
class MailBlackList(models.Model):
    _name = 'mail.blacklist'
    _inherit = ['mail.thread']
```

**Email normalization:** Applied on create/write/search via `tools.email_normalize()` — case-insensitive, domain-stripped.

**_sql_constraints:**
```python
unique(email)
```

**Key Methods:**
- `_add(email)` — blacklist / unarchive
- `_remove(email)` — remove from blacklist / archive
- `action_add()` — UI action to blacklist current record's email

**Import-safe:** If duplicate emails in batch, returns existing record instead of creating.

---

## `mail.alias` — Email Alias

```python
class Alias(models.Model):
    _name = 'mail.alias'
    _inherits = {'mail.alias.domain': 'alias_domain_id'}
```

| Field | Description |
|-------|-------------|
| `alias_name` | Local part (e.g. `jobs`) |
| `alias_full_name` | Full email address (computed) |
| `alias_model_id` | Target `ir.model` |
| `alias_defaults` | Python dict for new record defaults |
| `alias_force_thread_id` | Force all emails to specific record |
| `alias_contact` | Security: everyone / partners / followers |
| `alias_status` | Computed: not_tested / valid / invalid |

**Routing Flow:**
1. **reply**: existing `message_id` → route to thread
2. **new via alias**: match on To header → create or update record
3. **fallback**: use provided `model`/`thread_id`
4. **catchall direct**: no alias match → bounce

**Loop Detection:** `_detect_loop_sender()` counts messages per author per model within `LOOP_MINUTES` window. Exceeds threshold → bounce + ignore.

---

## `mail.alias.domain` — Alias Domain

| Field | Description |
|-------|-------------|
| `name` | Domain name (e.g. `example.com`) |
| `bounce_alias` | Default `bounce` |
| `catchall_alias` | Default `catchall` |
| `default_from` | Default `notifications` |

**_sql_constraints:**
```python
unique(bounce_alias, name)
unique(catchall_alias, name)
```

---

## `mail.message.subtype` — Message Subtype

Per-follower notification tuning.

| Field | Description |
|-------|-------------|
| `name` | Internal name |
| `internal` | Hidden from non-employees |
| `parent_id` | Parent subtype for auto-subscription |
| `relation_field` | Field linking related model |
| `res_model` | Restrict to specific model |
| `track_recipients` | Track all vs important recipients |

**Cached:** `_get_auto_subscription_subtypes(model)` — returns for auto-subscription matching.

---

## `mail.tracking.value` — Field Change Tracking

Stores old/new values for tracked fields. Used by `_track` system.

```python
class MailTracking(models.Model):
    _name = 'mail.tracking.value'
```

Field type → value mapping:
- `old_value_integer` / `new_value_integer` — integer fields
- `old_value_float` / `new_value_float` — float/monetary
- `old_value_char` / `new_value_char` — Char
- `old_value_datetime` / `new_value_datetime` — Datetime

---

## `discuss.channel` — Discussion Channel

```python
class Channel(models.Model):
    _name = 'discuss.channel'
    _mail_flat_thread = False   # overrides mail.thread default
    _mail_post_access = 'read'  # overrides mail.thread default
    _inherit = ["mail.thread", "bus.listener.mixin"]
```

**channel_type:**
| Type | Public Join | Max Members | Constraint |
|------|------------|-------------|-----------|
| `chat` | No (2-person DM) | **2 max** | `_constraint_partners_chat` |
| `channel` | Yes (configurable) | Unlimited | `group_public_id` optional |
| `group` | No (invite only) | Unlimited | No auto-subscribe groups |

**Key Fields:**
| Field | Description |
|-------|-------------|
| `channel_member_ids` | Channel membership |
| `pinned_message_ids` | Pinned messages |
| `rtc_session_ids` | Active WebRTC calls |
| `sfu_channel_uuid` | SFU server ID (system only) |
| `uuid` | Unique invite token |

---

## `discuss.channel.member` — Channel Member

```python
class ChannelMember(models.Model):
    _name = "discuss.channel.member"
    _inherit = ["bus.listener.mixin"]
```

**_sql_constraints:**
```python
-- Partner XOR Guest (not both, not neither)
CHECK((partner_id IS NOT NULL AND guest_id IS NULL) OR
      (partner_id IS NULL AND guest_id IS NOT NULL))
```

**Key Fields:**
| Field | Description |
|-------|-------------|
| `fetched_message_id` | Last fetched message |
| `seen_message_id` | Last seen message |
| `message_unread_counter` | Unread count (computed via raw SQL) |
| `mute_until_dt` | Notification mute |
| `rtc_session_ids` | Active RTC sessions |

---

## `mail.guest` — Anonymous Guest

```python
class MailGuest(models.Model):
    _name = 'mail.guest'
    _inherit = ["avatar.mixin", "bus.listener.mixin"]
```

**Cookie format:** `"id|access_token"` (UUID)

---

## `mail.template` — Email Template

```python
class MailTemplate(models.Model):
    _name = "mail.template"
    _inherit = ['mail.render.mixin', 'template.reset.mixin']
    _unrestricted_rendering = True
```

| Field | Description |
|-------|-------------|
| `subject`, `email_from`, `reply_to` | Email headers |
| `body_html` | QWeb-rendered body |
| `email_to`, `partner_to`, `email_cc` | Recipients |
| `use_default_to` | Use record's email address |
| `attachment_ids` | Static attachments |
| `report_template_ids` | Dynamic report attachments |
| `scheduled_date` | Deferred send QWeb expression |
| `auto_delete` | Delete after sending (default True) |

---

## Architectural Flow

```
mail.message.create()
  └─→ mail.mail.create() via create() hook
        └─→ email_send() / email_queue_compute()
  └─→ mail.notification.create() per recipient
  └─→ _notify_thread() → bus.bus._sendone()
        └─→ ImDispatch.loop() → WebSocket → Frontend

message_post()
  └─→ _notify_thread()
        └─→ bus.bus._sendone('mail.message/...', payload)
  └─→ _track_template() → mail.tracking.value.create()
  └─→ bus notification via _bus_channel()

inbound email
  └─→ message_process()
        └─→ message_route() → alias matching
              └─→ create/update record
```

---

## Cross-Module Relations

| Module | Integration |
|--------|------------|
| `bus` | Real-time notifications via `bus.bus`, presence |
| `discuss` | Channel + member models |
| `html_editor` | Rich-text body rendering |
| `sale` | Chatter on `sale.order`, activities |
| `crm` | Lead/opportunity messaging |
| `project` | Task activities and messaging |
| `hr` | Employee activities |

---

## Related Links
- [Modules/bus](bus.md) — Real-time event bus
- [Core/API](API.md) — @api decorators
- [Patterns/Security Patterns](Security Patterns.md) — ACL and ir.rule
- [Modules/website](website.md) — Website email aliases
