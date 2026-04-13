---
type: module
module: mail
tags: [odoo, odoo19, mail, messaging, notifications, email, chatter]
created: 2026-04-06
updated: 2026-04-11
---

# Mail Module (mail)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Discuss |
| **Technical Name** | `mail` |
| **Category** | Productivity/Discuss |
| **Version** | 1.19 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description

Core messaging system with email integration, notifications, followers, activities, and Chatter. Provides the communication backbone for all Odoo apps. The module implements a thread-based messaging architecture where every record that inherits from `mail.thread` gains access to message posting, follower management, email notifications, and activity scheduling.

## Dependencies

- `base` -- Core ORM and base models
- `base_setup` -- Initial configuration
- `bus` -- Real-time event bus for WebSocket notifications
- `web_tour` -- Interactive guided tours
- `html_editor` -- Rich-text HTML editing for message bodies

## Key Models

| Model | Technical Name | Purpose |
|-------|----------------|---------|
| Mail Thread Mixin | `mail.thread` | Core mixin enabling Chatter on any model |
| Message | `mail.message` | Stores individual messages and notifications |
| Outbound Email | `mail.mail` | RFC2822 email queue, inherits mail.message |
| Notification | `mail.notification` | Delivery status tracking per recipient |
| Document Followers | `mail.followers` | Subscription management for threads |
| Activity | `mail.activity` | Task/workflow activities with deadlines |
| Email Alias | `mail.alias` | Inbound email gateway routing |
| Email Blacklist | `mail.blacklist` | Block list for suppressing email delivery |
| Activity Type | `mail.activity.type` | Activity category definitions |
| Message Subtype | `mail.message.subtype` | Notification subtype for follower tuning |
| Tracking Value | `mail.tracking.value` | Field change audit trail |
| Mail Template | `mail.template` | Email template with QWeb rendering |
| Discussion Channel | `discuss.channel` | Live chat / channel / group |
| Channel Member | `discuss.channel.member` | Channel membership and RTC sessions |
| Mail Guest | `mail.guest` | Anonymous chat user identity |
| Mail Render Mixin | `mail.render.mixin` | Abstract rendering engine for templates |
| Mail Composer Mixin | `mail.composer.mixin` | Email composition from templates |
| Mail Activity Mixin | `mail.activity.mixin` | Activity scheduling on document models |
| Mail Alias Domain | `mail.alias.domain` | Domain-level alias configuration |
| Mail Alias Mixin | `mail.alias.mixin` | Mixin providing alias_id field and helpers |
| Mail Thread Blacklist | `mail.thread.blacklist` | Blacklist checking within thread posting |
| Mail Thread CC | `mail.thread.cc` | Carbon-copy handling for threads |
| Mail Thread Main Attachment | `mail.thread.main.attachment` | Main attachment handling |
| Mail Presence | `mail.presence` | User online/away presence tracking |
| Mail Push | `mail.push` | Push notification infrastructure |
| Mail Scheduled Message | `mail.scheduled.message` | Scheduled message queuing |
| Mail Message Schedule | `mail.message.schedule` | Delayed message posting |
| Mail Message Reaction | `mail.message.reaction` | Emoji reactions on messages |
| Mail Message Translation | `mail.message.translation` | Message content translations |
| Mail Link Preview | `mail.link.preview` | OGP/link preview metadata |
| Mail Message Link Preview | `mail.message.link.preview` | Per-message link previews |
| Mail Canned Response | `mail.canned.response` | Saved reply snippets |
| Discuss RTC Session | `discuss.channel.rtc.session` | Real-time communication session |
| Discuss Voice Metadata | `discuss.voice.metadata` | Voice message metadata |
| Discuss Call History | `discuss.call.history` | Historical call records |
| Discuss GIF Favorite | `discuss.gif.favorite` | Saved animated GIFs |

---

## mail.thread (Mail Thread Mixin)

**File:** `models/mail_thread.py`

**Type:** Abstract model -- never stored, used as a mixin via `_inherit`

**Inherits:** None directly; concrete models (like `mail.mail`, `discuss.channel`, `mail.blacklist`) inherit this mixin to gain messaging capabilities.

### Class-Level Configuration

```python
_name = 'mail.thread'
_mail_flat_thread = True        # Thread replies flat (True) or nested (False)
_mail_thread_customer = False   # Customer-facing thread tracking
_mail_post_access = 'write'     # Access right required to post messages
_primary_email = 'email'        # Field to use for email address resolution
```

- `_mail_flat_thread = True`: New replies are added as sibling messages (flat), not nested under parent. Only `discuss.channel` sets this to `False`.
- `_mail_post_access`: Controls which access right is checked before allowing `message_post()`. Values: `'read'`, `'write'`, `'create'`, or `'unlink'`. Default is `'write'`.
- `_primary_email`: Model field used as email address source for `_message_auto_subscribe()`.

### Context Keys Controlling Behavior

| Context Key | Effect |
|-------------|--------|
| `mail_create_nosubscribe` | Do not subscribe the creating user as follower |
| `mail_create_nolog` | Suppress automatic "Document created" log message |
| `mail_notrack` | Disable field-value change tracking for this operation |
| `tracking_disable` | Disable all MailThread features (fastest path, skips all overhead) |
| `mail_notify_force_send` | Bypass queue; send notifications directly via SMTP |
| `mail_post_autofollow` | Automatically subscribe all message recipients as followers |
| `mail_post_autofollow_author_skip` | Do not subscribe the message author as follower |
| `mail_message_force_log` | Force creation of a log message even when subtype is comment |
| `mail.message.post.default_type` | Override the default message type |

### Fields

#### Follower / Subscription Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `message_follower_ids` | One2many (`mail.followers`) | -- | Inverse of follower records; cascade-deleted with document |
| `message_partner_ids` | Many2many (`res.partner`) | -- | Computed shorthand: all follower partners (not guests) |
| `message_is_follower` | Boolean | Computed | Whether the current user/guest is a follower |

#### Message Count Fields

| Field | Type | Description |
|-------|------|-------------|
| `message_needaction` | Boolean | Has unread notifications for current user |
| `message_needaction_counter` | Integer | Count of unread notifications |
| `message_has_error` | Boolean | Has at least one failed notification |
| `message_has_error_counter` | Integer | Count of failed notifications |
| `has_message` | Boolean | Record has any messages at all |
| `message_attachment_count` | Integer | Total attachments across all messages |

### Key Methods

#### `message_post(..., message_type='comment', subtype_xmlid=None, ...)`

**L3 -- Override Pattern:** This is the primary entry point for all message creation through Chatter. Override to intercept or modify message data before storage.

Parameters:
- `message_type`: `'comment'` (user message), `'notification'` (system), `'email'` (inbound), `'email_outgoing'` (outbound), `'auto_comment'` (automated note), `'out_of_office'` (OOTO reply), `'user_notification'` (targeted to specific user)
- `subtype_xmlid`: XML ID of `mail.message.subtype` (e.g., `'mail.mt_note'`, `'mail.mt_comment'`) -- controls which followers receive notifications
- `parent_id`: For threaded replies (ignored when `_mail_flat_thread = True`)
- `attachments`: List of `(name, raw_content, mime_type)` tuples or `ir.attachment` records
- `attachment_ids`: Existing attachment IDs to link
- `email_layout_xmlid`: XML ID of email notification template

**L3 -- Workflow Trigger:** Calling `message_post()` with `subtype_xmlid` triggers:
1. Follower notification (via `mail.notification` records)
2. Field tracking if enabled (`track_visibility` on fields)
3. Email sending if `email_from` or recipients are set
4. Bus notification for real-time web client updates

**L3 -- Failure Mode:** If `_notify_thread()` throws, the message is still created but notifications fail silently (logged). Email delivery failures are recorded on `mail.notification` with `failure_type` and `failure_reason`.

```python
# Pattern: Override message_post for custom behavior
def message_post(self, message_type='comment', subtype=None, **kwargs):
    if self.env.context.get('my_custom_flag'):
        # Pre-process or transform content
        body = kwargs.get('body', '')
        kwargs['body'] = self._my_transform(body)
    return super().message_post(message_type=message_type, subtype=subtype, **kwargs)
```

#### `_message_auto_subscribe(updated_values, followers_existing_policy='replace')`

**L3 -- Cross-Model:** Called automatically by the ORM's `create()` and `write()` when tracked field values change. By default, follows partner fields (`res.partner`) that change value and subscribes the new partner.

Override to implement custom auto-subscription logic. Receives `updated_values` dict of changed fields. Return `dict` of `{partner_id: subtype_ids}` to add custom followers.

**L3 -- Override Pattern:**

```python
def _message_auto_subscribe(self, updated_values, followers_existing_policy='replace'):
    # Auto-subscribe sales person when user_id changes
    if 'user_id' in updated_values:
        new_user = self.env['res.users'].browse(updated_values['user_id'])
        if new_user.partner_id:
            return {new_user.partner_id.id: []}  # empty list = default subtypes
    return super()._message_auto_subscribe(updated_values, followers_existing_policy)
```

**L4 -- Performance:** This method fires per-record on `create()` and `write()`. Uses SQL bulk operations via `mail.followers._insert_followers()` to minimize round-trips. When `followers_existing_policy='replace'`, existing follower records are updated rather than deleted/recreated.

#### `_notify_thread(recipients, record, ...)`

**L3 -- Cross-Model:** Called after `message_post()` saves the message. Dispatches notifications to followers based on their subtype subscriptions and notification preferences.

Flow:
1. Fetch followers via `mail.followers._get_recipient_data()`
2. Check partner blacklist (`mail.blacklist`)
3. Check user notification preferences (`res.users.settings`)
4. Create `mail.notification` records (inbox or email)
5. For email recipients: call `_notify_by_email_store_body()` to render email body
6. Push to bus (`bus.bus.sendone`) for real-time web updates

**L4 -- Performance:** Email body rendering (`_notify_by_email_store_body`) is deferred via `mail.message.schedule` when `scheduled_date` is set. The method batches notification creation and uses raw SQL for bulk insert in high-volume scenarios.

#### `_notify_by_email_store_body(message, recipients, ...)` (static method)

**L4 -- Performance:** Renders email HTML body for all recipients. This is the single most expensive operation in the notification pipeline. Uses `mail.template` rendering with per-language batch classification via `_classify_per_lang()`. Rendering is cached per (template_id, lang) combination when the template has no dynamic fields.

**L4 -- Historical Change (Odoo 18->19):** In Odoo 19, this method was refactored to use the new `mail.render.mixin` QWeb engine instead of the legacy `jinja` engine. The `render_engine='qweb'` field attribute replaced inline template syntax.

#### `_track_post_template(message, tracking_value_ids, ...)` (static method)

**L3 -- Cross-Model:** Called when field tracking produces changes. Creates a system notification message summarizing all tracked field changes, formatted using `mail.tracking.value._tracking_value_format()`.

#### `_track_prepare(values, ...)` / `_track_finalize(tracking_values)`

**L3 -- Override Pattern:** `_track_prepare()` collects field changes before write and returns tracked field names. Override to add custom tracked fields or skip tracking for specific values. `_track_finalize()` writes `mail.tracking.value` records after commit.

**L3 -- Performance:** Tracking is batched across the write operation. Only fields with `track_visibility` set are monitored. Skipping tracking via `tracking_disable` context avoids the entire tracking pipeline.

#### `_routing_check_route(message_dict, route, ...)`

**L3 -- Security:** Validates an incoming email route for the mail gateway. Checks:
- Alias exists and is valid
- Sender has permission per `alias_contact` (everyone / partners / followers)
- No bounce loop (sender not in recent bounce list)
- Route doesn't exceed maximum bounce count (`MAX_BOUNCE_LIMIT = 10`)

**L3 -- Failure Mode:** Returns `(False, error_message, bounce_body)` if validation fails. Bounce email is sent back to sender. Alias `alias_status` is set to `'invalid'` if misconfiguration detected.

#### `message_route(message_dict, ...)` / `message_process(message_dict, ...)` / `message_parse(message)` (static methods)

**L3 -- Override Pattern:** These are the core mail gateway entry points:
- `message_parse()`: RFC2822 email parsing, returns a `message_dict`
- `message_route()`: Route the parsed message to the correct model/record
- `message_process()`: High-level dispatcher that orchestrates parse + route
- `message_new()`: Called when no existing thread matches (creates new record)
- `message_update()`: Called when existing thread found (updates record)

Override `message_route()` to add custom routing rules. Override `message_new()` / `message_update()` to customize document creation from inbound emails.

**L4 -- Security:** `message_parse()` sanitizes all incoming email content. `message_route()` validates sender against `mail.blacklist` and `mail.alias.contact` rules. No SQL injection risk because all routing uses ORM methods.

#### `message_subscribe(partner_ids=None, subtype_ids=None, ...)` / `message_unsubscribe(partner_ids, ...)` / `message_get_followers()`

**L3 -- Override Pattern:** `message_subscribe()` calls `mail.followers._add_followers()` internally. Override `_add_followers()` to modify subscription logic (e.g., enforce minimum follower count, add mandatory subtypes).

**L3 -- Performance:** Uses bulk SQL operations. `message_unsubscribe()` does not cascade-delete notifications; existing notifications remain in the inbox.

#### `_message_compute_author(author_id, email_from, ...)` (static method)

**L3 -- Helper:** Resolves the author `res.partner` from various input sources. Priority: explicit `author_id` > matched partner by email > guest > public user.

### L4 -- Performance Considerations

| Operation | Complexity | Optimization |
|-----------|-----------|-------------|
| `message_post()` | O(n) where n = follower count | `tracking_disable` context skips tracking |
| `_notify_by_email_store_body()` | O(m) where m = email recipients | Deferred rendering via `mail.message.schedule` |
| `_message_auto_subscribe()` | O(k) where k = changed partner fields | Bulk SQL via `mail.followers._insert_followers()` |
| `message_subscribe()` on many records | O(r * f) | `_add_followers()` batches by model |
| `_track_prepare()` | O(t) where t = tracked fields | Reads old values only for tracked fields |

**N+1 Risk:** `_tracking_value_format()` calls `model._fields_get()` per unique model in the tracking set. Batching by model mitigates this.

### L4 -- Odoo 18 to 19 Changes

- **QWeb rendering:** Template body_html now uses `render_engine='qweb'` instead of `jinja2`. Legacy inline templates (`{{ }}`) still work but are rendered via the regex-based `_render_template_inline_template_regex()` path.
- **`_mail_post_access`:** New in Odoo 19, replacing the less flexible `_mail_post_access` check that previously lived in `mail.message`.
- **`mail.message.subtype` registry caching:** `_get_auto_subscription_subtypes()` and `_default_subtypes()` now use `ormcache` decorators with model-name keys.
- **Bus notification refactor:** Real-time notifications now flow through the `Store` class (`mail.tools.discuss.Store`) instead of direct `bus.bus.sendone()` calls in many places.
- **`discuss.channel` separate from `mail.thread`:** Channel message threading changed from flat to nested in Odoo 19 for live chat (`_mail_flat_thread = False` on channel).

---

## mail.message (Message)

**File:** `models/mail_message.py`

**Inherits:** `bus.listener.mixin` -- enables WebSocket broadcast on create/write

### Message Types

| Value | Description | Use Case |
|-------|-------------|----------|
| `email` | Incoming email via gateway | Inbound mail processing |
| `comment` | User-generated comment | Regular Chatter posts |
| `email_outgoing` | Outbound email | Emails sent from Odoo |
| `notification` | System-generated notification | Track changes, auto-log |
| `auto_comment` | Automated targeted notification | Automated workflow notes |
| `out_of_office` | OOO reply | Vacation autoresponder |
| `user_notification` | User-specific notification | Targeted at single user |

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `subject` | Char | -- | Message subject line |
| `date` | Datetime | `now()` | Message creation datetime |
| `body` | Html | Required | Sanitized HTML message content |
| `preview` | Char | Computed | First 200 chars of body (plaintext) |
| `message_type` | Selection | `comment` | Origin type (see above) |
| `subtype_id` | Many2one (`mail.message.subtype`) | -- | Notification subtype; controls follower delivery |
| `email_from` | Char | -- | RFC2822 From address |
| `author_id` | Many2one (`res.partner`) | -- | Author partner (nullable for guests/anonymous) |
| `author_avatar` | Binary | Computed | Author profile picture (gravatar fallback) |
| `author_guest_id` | Many2one (`mail.guest`) | -- | Author if anonymous (guest) |
| `is_current_user_or_guest_author` | Boolean | Computed | Convenience for UI display conditions |
| `partner_ids` | Many2many (`res.partner`) | -- | Direct recipients (for email messages) |
| `notified_partner_ids` | Many2many (`res.partner`) | Computed | Partners with notifications |
| `model` | Char | -- | Target document model (e.g., `'crm.lead'`) |
| `res_id` | Integer | -- | Target document ID |
| `record_name` | Char | Computed | Display name of target document |
| `record_alias_domain_id` | Many2one (`mail.alias.domain`) | -- | Company alias domain used |
| `record_company_id` | Many2one (`res.company`) | -- | Company of the target record |
| `parent_id` | Many2one (`mail.message`) | -- | Parent message for threading |
| `child_ids` | One2many (`mail.message`) | -- | Reply messages |
| `attachment_ids` | Many2many (`ir.attachment`) | -- | Linked attachments |
| `linked_message_ids` | Many2many (`mail.message`) | -- | Cross-linked related messages |
| `message_link_preview_ids` | One2many | -- | OGP previews of URLs in body |
| `reaction_ids` | One2many | -- | Emoji reactions |
| `tracking_value_ids` | One2many (`mail.tracking.value`) | -- | Field change tracking values |
| `is_internal` | Boolean | Computed | True if subtype is internal (employee-only) |
| `needaction` | Boolean | Computed | Has notification for current user |
| `has_error` | Boolean | Computed | Has failed notification |
| `notification_ids` | One2many (`mail.notification`) | -- | Notification records |
| `starred_partner_ids` | Many2many | -- | Partners who starred this message |
| `starred` | Boolean | Computed | Current user has starred |
| `pinned_at` | Datetime | -- | When message was pinned to channel |
| `reply_to_force_new` | Boolean | False | If True, replies go to `reply_to` address instead of threading |
| `message_id` | Char | Computed | RFC2822 Message-ID header value |
| `reply_to` | Char | Computed | Reply-To address for email threading |
| `mail_server_id` | Many2one (`ir.mail_server`) | -- | Outgoing server to use |
| `email_layout_xmlid` | Char | -- | Email notification template XML ID |
| `mail_ids` | One2many (`mail.mail`) | -- | Outbound email records |
| `scheduled_date` | Char | -- | Deferred send date (placeholder expression) |
| `mail_activity_type_id` | Many2one (`mail.activity.type`) | -- | Linked activity type (for activity creation) |

### Constraints

| Constraint | Condition | Error |
|------------|-----------|-------|
| `mail_message_author_guest` | Exactly one of `author_id` / `author_guest_id` must be set | "Message author must be a guest or a partner" |

### Key Methods

#### `check_can_message_entity()` / `_check_discuss_access()`

**L3 -- Security:** Access control for posting. `check_can_message_entity()` verifies the user can post on the target record (based on `_mail_post_access`). `_check_discuss_access()` additionally checks internal message visibility.

#### `_message_compute_author()` / `_message_compute_subject()` (static methods)

**L3 -- Helper:** Resolve author from email and compute RFC2822-compliant subject. `_message_compute_subject()` strips "Re: " / "Fwd: " prefixes before prepending them based on message type.

#### `_update_messageseo()` (static method)

**L3 -- Helper:** Updates search preview metadata on messages after creation or modification.

### L4 -- Performance

- `author_avatar` is computed on-the-fly from `author_id` partner or generated from name hash
- `record_name` and `record_company_id` use `browse()` prefetching to avoid N+1
- `message_id` (RFC2822 Message-ID) is generated using `tools.generate_tracking_message_id()`
- `_tracking_value_format()` batches per model to minimize schema lookups

### L4 -- Security

- Internal messages (`is_internal = True`) filter out non-employee recipients in `_notify()`
- `author_id` write access restricted after creation; only admins can reassign authorship
- Attachment access filtered by `ir.attachment._filtered_access()` to respect record ACLs

---

## mail.mail (Outbound Email)

**File:** `models/mail_mail.py`

**Inherits:** `mail.message` via `_inherits = {'mail.message': 'mail_message_id'}`

### State Machine

```
outgoing → sent → received
            ↘ exception
            ↘ cancel
```

### Email State Values

| Value | Description |
|-------|-------------|
| `outgoing` | Queued in the mail spool, not yet sent |
| `sent` | Successfully delivered to SMTP |
| `received` | Received via inbound mail (rare) |
| `exception` | SMTP delivery failed |
| `cancel` | Manually cancelled or blacklisted |

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mail_message_id` | Many2one | Required | Inherited message record (cascade delete) |
| `body_html` | Text | -- | Rich-text HTML content to send |
| `body_content` | Html | Computed | Alias for `body_html` |
| `references` | Text | -- | RFC2822 References header |
| `headers` | Text | -- | Custom SMTP headers (JSON-encoded) |
| `email_to` | Text | -- | Raw To addresses (multiple, comma-separated) |
| `email_cc` | Char | -- | CC addresses |
| `recipient_ids` | Many2many (`res.partner`) | -- | Partner recipients (incl. inactive) |
| `restricted_attachment_count` | Integer | Computed | Attachments the user cannot access |
| `unrestricted_attachment_ids` | Many2many | Computed | Attachments the user can access |
| `is_notification` | Boolean | Auto | True if created from existing `mail.message` (notification) |
| `state` | Selection | `outgoing` | Current email state |
| `failure_type` | Selection | -- | Failure category |
| `failure_reason` | Text | -- | SMTP error details |
| `auto_delete` | Boolean | False | Permanently delete after sending |
| `scheduled_date` | Datetime | -- | Deferred send datetime (UTC) |
| `fetchmail_server_id` | Many2one | -- | Inbound server that received this |
| `mail_server_id` | Many2one | Inherited | Preferred SMTP server |
| `mail_message_id_int` | Integer | Computed | Integer cast of `mail_message_id.id` (for SQL) |

### Key Methods

#### `send(auto_commit=False, raise_exception=False, ...)` (static method)

**L3 -- Override Pattern:** Main send dispatcher. Iterates over `self` and:
1. Fetches SMTP server (`_get_mail_server()`)
2. Builds RFC2822 email via `_prepare_email()`
3. Sends via SMTP (`ir.mail_server.send_email()`)
4. On success: sets `state='sent'`, calls `_postprocess_sent_message()`
5. On failure: sets `state='exception'`, records `failure_type` / `failure_reason`
6. On cancel: sets `state='cancel'`

**L3 -- Performance:** The `auto_commit` parameter controls whether to commit the database transaction after each email. For the cron job (`process_email_queue()`), `auto_commit=True` ensures partial failures don't roll back the entire batch. For single `send()` calls from the UI, `auto_commit=False`.

**L4 -- Historical Change:** In Odoo 19, `send()` was refactored to use the new `ir.mail_server.send_email()` API with STARTTLS support. The old `email_msg.send()` wrapper was removed.

#### `process_email_queue(email_ids=(), batch_size=1000)` (static method, cron)

**L4 -- Performance:** Runs as a scheduled cron job. Fetches up to `batch_size` outgoing emails ordered by ID. Triggers `send()` on each. For large batches, commits after every email (via `auto_commit=True`). Progress is tracked via `ir.cron._commit_progress()`.

Config parameter: `mail.mail.queue.batch.size` (default 1000).

#### `_postprocess_sent_message(mail_values, ...)` (static method)

**L3 -- Hook:** Called after successful email send. Default implementation:
- Creates inbound mail record if `is_notification=True` (for threading)
- Updates push notification tokens
- Processes link previews

Override to add post-send behavior (e.g., update external systems).

#### `_get_mail_server()` (static method)

**L3 -- Override Pattern:** Selects the SMTP server. Priority:
1. Template-specified server (`mail_server_id` on message)
2. Company-level default server
3. Highest-priority active server from `ir.mail_server`

Override to implement custom routing (e.g., per-domain server selection).

#### `_prepare_email()` / `_prepare_outgoing_email()` (static methods)

**L3 -- Helper:** Constructs the RFC2822 email dict from `mail.mail` and `mail.message` fields. Handles BCC compression, multi-recipient splitting, and attachment inclusion.

### L4 -- Security

- `recipient_ids` includes inactive partners (for audit trail of who was intended)
- `failure_reason` stores raw SMTP response, may contain server IPs / hostnames
- `is_notification=True` emails are cascade-protected: unlinking the `mail.mail` does not delete the parent `mail.message`

---

## mail.notification (Notification)

**File:** `models/mail_notification.py`

### Notification Types

| Value | Description |
|-------|-------------|
| `inbox` | In-app notification (visible in Chatter) |
| `email` | Physical email sent via SMTP |

### Notification Status Values

| Value | Description | Transitions |
|-------|-------------|-------------|
| `ready` | Queued for sending | to `process`, `sent`, `exception` |
| `process` | Being processed by intermediary (e.g., IAP SMS) | to `pending`, `exception` |
| `pending` | Accepted by intermediary | to `sent` |
| `sent` | Delivered to recipient | terminal (or `bounce`) |
| `bounce` | Recipient mail server rejected | terminal |
| `exception` | Delivery failed | to `ready` (retry), `canceled` |
| `canceled` | Cancelled (e.g., unsubscribed) | terminal |

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `author_id` | Many2one (`res.partner`) | -- | Author of the notification |
| `mail_message_id` | Many2one (`mail.message`) | Required | Parent message; cascade delete |
| `mail_mail_id` | Many2one (`mail.mail`) | -- | Outbound email record (for email type) |
| `res_partner_id` | Many2one (`res.partner`) | -- | Recipient partner |
| `mail_email_address` | Char | -- | Email address for mass mail without partner |
| `notification_type` | Selection | `inbox` | Delivery channel |
| `notification_status` | Selection | `ready` | Current delivery state |
| `is_read` | Boolean | False | Has recipient read this |
| `read_date` | Datetime | -- | When recipient opened |
| `failure_type` | Selection | -- | Failure category |
| `failure_reason` | Text | -- | Error details |

### Constraints

| Constraint | Condition | Purpose |
|------------|-----------|---------|
| `mail_notification_partner_required` | Inbox requires partner | Ensures inbox notifications are user-linked |
| `mail_notification_partner_or_email_required` | Email requires partner or email address | Ensures email notifiy has a target |

### Indexes

| Index | Columns | Type | Purpose |
|-------|---------|------|---------|
| `(res_partner_id, is_read, notification_status, mail_message_id)` | -- | B-tree | Fast unread inbox count |
| `(author_id, notification_status)` | WHERE status IN ('bounce', 'exception') | Partial | Failed notification lookup |
| `(mail_message_id, res_partner_id)` | WHERE partner not null | Unique | Prevent duplicate notifications |

### Key Methods

#### `_filtered_for_web_client()`

**L3 -- Cross-Model:** Returns the subset of notifications visible in the web client. Filters out:
- Bounce / exception / canceled notifications (shown separately as failures)
- Partner-share notifications (external users don't see in-app notifications)
- Mass mail notifications with email address only (no partner)

**L3 -- Performance:** Uses `filtered()` with a closure, which is O(n) per notification. For large sets, this can be a bottleneck. Consider pre-filtering at the query level in custom overrides.

#### `_gc_notifications(max_age_days=180)`

**L4 -- Performance:** Autovacuum cron job that cleans old read notifications. Targets only:
- Read notifications (`is_read = True`)
- Older than 180 days
- From internal users (`partner_share = False`)
- With status `sent` or `canceled`

Batch size: `GC_UNLINK_LIMIT = 10000` (from `odoo.tools.constants`).

### L4 -- Performance Considerations

- The `(res_partner_id, is_read, notification_status, mail_message_id)` composite index covers the most common inbox query patterns
- `_filtered_for_web_client()` is called on every notification fetch; large record sets benefit from SQL-level pre-filtering
- Notification creation is batched in `mail.thread._notify_thread()` via multi-create

### L4 -- Security

- `author_id` is stored for display purposes; does not grant special access
- `mail_email_address` allows mass mailing without partner records; must be normalized
- Admins can update `mail_message_id` / `res_partner_id`; regular users cannot

---

## mail.followers (Document Followers)

**File:** `models/mail_followers.py`

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `res_model` | Char | Required | Document model (e.g., `'crm.lead'`) |
| `res_id` | Integer | Required | Document record ID |
| `partner_id` | Many2one (`res.partner`) | Required | Follower partner |
| `subtype_ids` | Many2many (`mail.message.subtype`) | All defaults | Subscribed notification subtypes |
| `name` | Char | Related | Partner display name (cached) |
| `email` | Char | Related | Partner email (cached) |
| `is_active` | Boolean | Related | Partner active state (cached) |

### Constraints

| Constraint | Condition | Purpose |
|------------|-----------|---------|
| Unique | `(res_model, res_id, partner_id)` | One follower record per partner per document |
| `mail_followers_partner_required` | `partner_id IS NOT NULL` | No anonymous followers on this model |

### Key Methods

#### `_insert_followers(res_model, res_id, partner_ids, subtype_ids, ...)` (static method)

**L3 -- Performance:** Core bulk-insert method. Performs:
1. DELETE existing followers for the given partners on the given document
2. INSERT new follower records
3. Returns `(created_subtypes, deleted_subtypes)` for further processing

Uses raw SQL for maximum performance. Handles up to millions of follower records per batch.

**L3 -- Override Pattern:** Override to add custom post-subscription actions (e.g., create initial notifications, sync to external systems).

#### `_add_default_followers(res_model, res_ids, partner_ids, ...)` (static method)

**L3 -- Cross-Model:** Called from `create()` and `write()` of thread models to add followers on document creation. Uses `_insert_followers()` internally.

Logic:
- On create: adds document owner as follower with all default subtypes
- On write: adds newly assigned responsible users (e.g., `user_id` changes)
- Skips if context `mail_create_nosubscribe=True`

#### `_add_followers(res_model, res_ids, partner_ids, subtype_ids, ...)` (static method)

**L3 -- Cross-Model:** Public API for adding followers to existing documents. Resolves default subtypes via `mail.message.subtype.default_subtypes()`. Returns dict of `{res_id: follower_id}`.

**L3 -- Override Pattern:**

```python
# Example: Always notify manager when partner follows a document
@api.model
def _add_followers(self, res_model, res_ids, ...):
    result = super()._add_followers(res_model, res_ids, ...)
    # Custom post-processing
    return result
```

#### `_get_subscription_data(res_ids, ...)` (static method)

**L3 -- Performance:** Optimized reader for subscription data. Returns a list of dicts with `{id, partner_id, res_id}` for all followers of the given documents. Uses SQL join with `res_partner` to fetch names in a single query (avoiding N+1).

#### `_get_recipient_data(records, ...)` (static method)

**L3 -- Cross-Model:** Used by `mail.thread._notify_thread()` to fetch follower notification data. Returns a dict of `{record_id: [(partner, subtype_ids, notif_data), ...]}`. Uses raw SQL join with `mail.message.subtype` and `res_partner`.

**L4 -- Performance:** This is the primary performance bottleneck for large follower sets. The SQL query joins across `mail_followers`, `mail.message.subtype`, `res_partner`, and `res_users`. It filters out:
- Inactive partners
- Blacklisted emails
- Users with disabled email notifications
- Partners with no notification preferences

### L4 -- Security

- Follower subscription does not grant document read access; access is still controlled by the document's ACLs
- `_get_recipient_data()` respects `mail.tracking.value._filter_free_field_access()` for tracking data privacy
- Followers of internal documents are not automatically visible to non-employees

### L4 -- Historical Change (Odoo 18->19)

- Follower data was moved partially to raw SQL in Odoo 19 for better performance
- `_insert_followers()` now uses `ON CONFLICT DO UPDATE` for upsert behavior (previously separate delete + insert)
- `subtype_ids` defaults are now cached per model via `_default_subtypes()` ormcache

---

## mail.activity (Activity)

**File:** `models/mail_activity.py`

### Activity State Machine

```
State is computed from date_deadline relative to current date:

  overdue     -- deadline < today
  today        -- deadline == today
  planned      -- deadline > today

Activities transition to 'done' via action_done() / action_feedback().
Activities can be cancelled via action_cancel().
Done activities are typically archived (active=False) rather than deleted.
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `res_model_id` | Many2one (`ir.model`) | Required | Target model |
| `res_model` | Char | Related | Model name |
| `res_id` | Integer | Required | Target record ID |
| `res_name` | Char | Computed | Target record display name |
| `activity_type_id` | Many2one (`mail.activity.type`) | Required | Activity category |
| `activity_category` | Selection | Related | Category (default/upload_file/phonecall) |
| `activity_decoration` | Selection | Related | Decoration (warning/danger) |
| `icon` | Char | Related | FontAwesome icon name |
| `summary` | Char | -- | Short description / title |
| `note` | Html | -- | Detailed activity notes (rich text) |
| `date_deadline` | Date | Required | Due date |
| `date_done` | Date | -- | When marked as done |
| `feedback` | Text | -- | Completion feedback |
| `automated` | Boolean | False | Created by automated action (vs. user) |
| `user_id` | Many2one (`res.users`) | Required | Assigned user |
| `state` | Selection | Computed | Activity state (overdue/today/planned) |
| `previous_activity_type_id` | Many2one | -- | Previous activity in chaining |
| `recommended_activity_type_id` | Many2one | -- | Suggested next activity type |
| `can_write` | Boolean | Computed | Current user can write this activity |
| `active` | Boolean | True | Inactive when done/cancelled |
| `request_partner_id` | Many2one | -- | Partner who requested this activity |

### Key Methods

#### `action_done(feedback=False, ...)` / `action_feedback(feedback, attachment_ids=None, ...)`

**L3 -- Workflow Trigger:** Marks activity as done. `action_done()` calls `_action_done()` which:
1. Sets `date_done = today`
2. Creates chained activity if `activity_type_id.triggered_next_type_id` is set
3. Posts a notification message on the target document
4. Sends email notification based on activity type template

**L3 -- Override Pattern:** Override `_action_done()` to customize the completion workflow. Return the next activity record if chaining is desired.

#### `action_feedback_schedule_next(feedback, ...)` / `action_reschedule_*()`

**L3 -- Workflow Trigger:** Convenience actions for common scheduling operations:
- `action_reschedule_today()`: Sets `date_deadline = today`
- `action_reschedule_tomorrow()`: Sets `date_deadline = tomorrow`
- `action_reschedule_nextweek()`: Sets `date_deadline = next Monday`
- `action_feedback_schedule_next()`: Marks done + schedules recommended next activity

#### `_action_done(callback=False, ...)` (static method)

**L3 -- Override Pattern:** The core done-processing logic. Key steps:
1. Verify write access (`_check_access('write')`)
2. Archive the activity
3. Create `mail.message` notification on the document
4. If chaining (`triggered_next_type_id`): create next activity via `_create_next_activity()`
5. Return the newly created chained activity (if any)

```python
# Override to add custom behavior on activity completion
def _action_done(self, feedback=False, attachment_ids=None):
    result = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
    if result:
        # Send a confirmation to the customer
        self._notify_activity_done()
    return result
```

#### `_check_access(operation)` (static method)

**L3 -- Security:** Access check for activity operations:
- `write` / `unlink`: check if user is assigned user (`user_id`) or document owner
- Falls back to checking document-level access if no specific activity user

**L3 -- Failure Mode:** Raises `AccessError` if user lacks permission. Does not fall back to sudo unless the activity has no specific assignee.

#### `get_activity_data(groupby_type=False, ...)`

**L3 -- Cross-Model:** Aggregates activity data for dashboard views. Returns dict of `{res_id: activity_info}`. Used by the Activity Kanban widget.

**L4 -- Performance:** Uses SQL GROUP BY on `mail_activity` table with timezone-aware date comparison. Prefetches activity types to avoid N+1 in the kanban rendering loop.

#### `_mail_activity_calendar_key(date_deadline)`

**L4 -- Performance:** Generates Redis/calendar key for deadline-based queries. Used for scheduling and deadline-based grouping.

### L4 -- Performance

- `activity_state` is computed via `_compute_activity_state()` with date comparison; does not query the database
- Activity type data is prefetched via `mapped('activity_ids.activity_type_id')` to avoid N+1 in kanban views
- `_action_done()` uses `flush()` to ensure the document is saved before creating notifications

### L4 -- Security

- Automated activities (`automated=True`) skip certain user-level permission checks
- `can_write` is computed per-record; returns True if user can modify that specific activity
- Internal model access (`ir.model`) is restricted to system admins; activity type model filtering uses `sudo()` with domain restriction

---

## mail.activity.type (Activity Type)

**File:** `models/mail_activity_type.py`

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | Required | Display name |
| `summary` | Char | -- | Default summary when creating activities |
| `sequence` | Integer | 10 | Ordering position |
| `active` | Boolean | True | Archived types are hidden in UI |
| `delay_count` | Integer | 0 | Days/weeks/months until deadline |
| `delay_unit` | Selection | `days` | Time unit for delay |
| `delay_label` | Char | Computed | Human-readable delay (e.g., "3 days") |
| `delay_from` | Selection | `previous_activity` | Delay reference point |
| `icon` | Char | -- | FontAwesome icon |
| `decoration_type` | Selection | -- | UI decoration (warning/danger) |
| `res_model` | Selection | -- | If set, type only applies to this model |
| `triggered_next_type_id` | Many2one | -- | Auto-chained next activity type |
| `chaining_type` | Selection | `suggest` | 'suggest' or 'trigger' next activity |
| `suggested_next_type_ids` | Many2many | -- | Suggested next types |
| `previous_type_ids` | Many2many | -- | Valid preceding activity types |
| `category` | Selection | `default` | Action category (default/upload_file/phonecall) |
| `mail_template_ids` | Many2many | -- | Email templates sent on activity completion |
| `default_user_id` | Many2one | -- | Default assigned user |
| `default_note` | Html | -- | Default note content |

### Key Methods

#### `_get_date_deadline()` / `_get_date_deadline_from_previous(prev_deadline)`

**L3 -- Helper:** Computes the deadline for an activity of this type. Respects `delay_unit` and `delay_from`:
- `delay_from = 'current_date'`: deadline = today + delay
- `delay_from = 'previous_activity'`: deadline = previous_activity.date_deadline + delay

**L3 -- Override Pattern:** Override to implement custom deadline computation (e.g., business hours adjustment).

#### `_get_model_info_by_xmlid()` (static method)

**L3 -- Security:** Returns a dict of master activity type XML IDs with their protected status (`unlink: bool`). Certain types (`mail_activity_data_call`, `mail_activity_data_meeting`, `mail_activity_data_todo`) cannot be deleted if they are referenced in business flows.

### L3 -- Activity Type Chaining

Two chaining modes:
- **Suggest**: User is shown suggested activities but must manually create them
- **Trigger**: Next activity is automatically created when current one is marked done

When `chaining_type = 'trigger'`, `suggested_next_type_ids` must be empty (mutual exclusion enforced via compute).

### L4 -- Odoo 18->19 Changes

- `triggered_next_type_id` replaces the older `triggered_next_type_id` + `suggested_next_type_ids` mutual exclusion pattern (now enforced via compute methods instead of `selection_default`)
- The `category` field was expanded to include `'upload_file'` and `'phonecall'`
- Master type deletion protection (`_unlink_except_todo()`) was strengthened to check more business flow references

---

## mail.message.subtype (Message Subtype)

**File:** `models/mail_message_subtype.py`

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | Required | Display name (translated) |
| `description` | Text | -- | Additional description (translated) |
| `internal` | Boolean | False | If True, only employees see this subtype |
| `parent_id` | Many2one | -- | Parent subtype for auto-subscription |
| `relation_field` | Char | -- | Field linking related model for auto-sub |
| `res_model` | Char | -- | Model this subtype applies to |
| `default` | Boolean | True | Enabled by default when subscribing |
| `sequence` | Integer | 1 | Ordering |
| `hidden` | Boolean | False | Hide from follower subscription UI |
| `track_recipients` | Boolean | False | Always show all recipients in notification |

### Caching

`_get_auto_subscription_subtypes(model_name)` and `_default_subtypes(model_name)` are both cached via `@tools.ormcache`. Cache is cleared on any subtype create/write/unlink via `self.env.registry.clear_cache()`.

**L4 -- Performance:** Cache key includes `model_name` (string). For multi-company setups with custom subtypes, cache invalidation is triggered globally (all subtypes) on any change.

### Key Methods

#### `_get_auto_subscription_subtypes(model_name)` (ormcache)

**L3 -- Cross-Model:** The core auto-subscription engine. For a given child model, returns:
- `child_ids`: All subtypes applicable to this model (generic or model-specific)
- `def_ids`: Default subtype IDs for auto-enabling
- `all_int_ids`: All internal subtype IDs
- `parent`: Dict mapping child subtype ID -> parent subtype ID
- `relation`: Dict mapping parent model -> relation field names

**L3 -- Example (Project/Task):**

```
Task "New" subtype: res_model=project.task
  Parent: Project "Task Created": res_model=project.project, relation_field=project_id

Result: When a task is created, followers of the project who have
        "Task Created" subtype will auto-subscribe to the task
        with the "New" subtype (via relation_field lookup).
```

#### `default_subtypes(model_name)` (ormcache)

**L3 -- Helper:** Returns three recordset groups for a model:
1. All default subtypes
2. Internal-only defaults
3. External defaults

Used by `_add_default_followers()` to set initial subscription subtypes.

### L4 -- Odoo 18->19 Changes

- Cache decorators changed from `ormcache()` with positional args to `ormcache('model_name')` with keyword notation
- `track_recipients` field added to allow always-showing recipients for specific subtypes

---

## mail.tracking.value (Field Tracking)

**File:** `models/mail_tracking_value.py`

### Purpose

Stores the before/after values of a field change when `track_visibility` is set on a field. Used by `mail.thread` tracking and property field tracking.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `field_id` | Many2one (`ir.model.fields`) | Tracked field (nullable for removed fields) |
| `field_info` | Json | Metadata for removed/property fields (name, type, desc) |
| `old_value_integer` | Integer | Old value for integer/boolean/many2one fields |
| `old_value_float` | Float | Old value for float/monetary fields |
| `old_value_char` | Char | Old value for char/selection/many2one-name/m2m/o2m |
| `old_value_text` | Text | Old value for text fields |
| `old_value_datetime` | Datetime | Old value for date/datetime fields |
| `new_value_integer` | Integer | New value (same type mapping) |
| `new_value_float` | Float | New value |
| `new_value_char` | Char | New value |
| `new_value_text` | Text | New value |
| `new_value_datetime` | Datetime | New value |
| `currency_id` | Many2one (`res.currency`) | For monetary field tracking |
| `mail_message_id` | Many2one (`mail.message`) | Parent message (cascade delete) |

### Key Methods

#### `_create_tracking_values(initial_value, new_value, col_name, col_info, record)` (static method)

**L3 -- Override Pattern:** The central factory for tracking values. Dispatches based on field type:

| Field Type | Storage Method |
|-------------|---------------|
| `integer` | `old_value_integer` / `new_value_integer` |
| `float` | `old_value_float` / `new_value_float` |
| `char` | `old_value_char` / `new_value_char` |
| `text` | `old_value_text` / `new_value_text` |
| `datetime` | `old_value_datetime` / `new_value_datetime` |
| `date` | Converted to datetime, stored in `old/new_value_datetime` |
| `boolean` | Stored as integer (0/1) in `old/new_value_integer` |
| `selection` | Stored as translated label in `old/new_value_char` |
| `many2one` | ID in `old/new_value_integer`, display name in `old/new_value_char` |
| `monetary` | Float in `old/new_value_float` with `currency_id` |
| `one2many` / `many2many` / `tags` | Comma-joined display names in `old/new_value_char` |

**L3 -- Cross-Model:** The `record` parameter provides context for:
- Looking up `currency_field` for monetary fields
- Getting display names for many2one/many2many records

#### `_tracking_value_format()` / `_tracking_value_format_model()`

**L3 -- Performance:** Formats tracking values for display in the Chatter UI. Groups trackings by model (for cross-model tracking) and sorts by:
1. Field sequence (from `_mail_track_order_fields()`)
2. Whether it's a property field (non-property first)
3. Field name

**L4 -- Performance:** Calls `model._fields_get()` per unique model in the tracking set. Use of `model_map` to batch avoids redundant schema queries.

#### `_format_display_value(field_type, new=True)`

**L3 -- Helper:** Formats a single tracking value for display. Handles type-specific formatting:
- `date`: Converts datetime back to Date for display
- `datetime`: Appends 'Z' suffix (indicating UTC)
- `boolean`: Converts integer to Python bool
- Other types: Returns raw stored value

### L4 -- Security

- `_filter_has_field_access()` restricts which tracking values are visible to which users based on the tracked field's access groups
- `_filter_free_field_access()` returns trackings for fields without group restrictions (used in email notifications)
- Removed fields (`field_id = False`) are only visible to `base.group_system` members

### L4 -- Odoo 18->19 Changes

- `_create_tracking_values_property()` was added to handle the new Properties field type
- Field sequence ordering now uses `_mail_track_order_fields()` instead of a static list
- Tracking for `selection` fields now stores the translated label (not just the key) for better notification readability

---

## mail.template (Email Template)

**File:** `models/mail_template.py`

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | -- | Template name (translated) |
| `description` | Text | -- | Internal usage description |
| `active` | Boolean | True | Inactive templates are hidden |
| `template_category` | Selection | Computed | `base_template` / `hidden_template` / `custom_template` |
| `model_id` | Many2one (`ir.model`) | Required | Target model |
| `model` | Char | Related | Model technical name |
| `subject` | Char | -- | Email subject (supports placeholders) |
| `email_from` | Char | -- | From address (supports placeholders) |
| `user_id` | Many2one (`res.users`) | -- | Template owner (for access control) |
| `use_default_to` | Boolean | True | Use default recipients from record |
| `email_to` | Char | -- | Static or dynamic To addresses |
| `partner_to` | Char | -- | Partner IDs (placeholder expression) |
| `email_cc` | Char | -- | CC addresses (placeholder expression) |
| `reply_to` | Char | -- | Reply-To address |
| `body_html` | Html | -- | Email body (QWeb template, translated) |
| `attachment_ids` | Many2many | -- | Static attachments |
| `report_template_ids` | Many2many | -- | Dynamic report attachments |
| `email_layout_xmlid` | Char | -- | Email notification layout template |
| `mail_server_id` | Many2one | -- | Preferred outgoing server |
| `scheduled_date` | Char | -- | Deferred send expression |
| `auto_delete` | Boolean | True | Delete email after sending |
| `ref_ir_act_window` | Many2one | -- | Sidebar action for template |
| `can_write` | Boolean | Computed | Current user can edit |
| `is_template_editor` | Boolean | Computed | User is in template editor group |

### Key Methods

#### `send_mail(res_id, force_send=False, ...)` / `send_mail_batch(res_ids, ...)`

**L3 -- Override Pattern:** The main email dispatch API.

Steps for `send_mail_batch()`:
1. Access check: `_send_check_access(res_ids)`
2. Template rendering: `_generate_template(res_ids, render_fields, ...)`
3. `mail.mail` creation with rendered values
4. Optional immediate send: `mail_mail.send()` if `force_send=True`

**L3 -- Performance:** Batch mode (`send_mail_batch`) is significantly more efficient than calling `send_mail()` in a loop because template rendering is batched per language via `_classify_per_lang()`. The `force_send=True` flag bypasses the email queue cron.

**L4 -- Historical Change:** In Odoo 19, `send_mail()` was split into `send_mail()` (single record) and `send_mail_batch()` (multiple records). The batch method was added for performance optimization of mass mailing workflows.

#### `_generate_template(res_ids, render_fields, ...)` / `_generate_template_attachments()` / `_generate_template_recipients()` / `_generate_template_scheduled_date()`

**L3 -- Cross-Model:** These methods render template fields and produce a dict of `{res_id: {field: value}}`.

- `_generate_template_attachments()`: Handles both static `attachment_ids` and dynamic `report_template_ids`. Report generation uses `ir.actions.report._render_qweb_pdf()` which can be slow for complex reports.
- `_generate_template_recipients()`: Resolves `partner_to` expression, finds or creates partners, and sets `partner_ids` and `email_to`. When `use_default_to=True`, falls back to `_message_get_default_recipients()`.
- `_generate_template_scheduled_date()`: Parses and validates the `scheduled_date` expression, converting it to UTC naive datetime.

**L3 -- Failure Mode:** If `partner_to` contains invalid IDs, they are silently ignored (set intersection with existing partners). If `scheduled_date` cannot be parsed, it is set to False.

#### `_check_can_be_rendered()`

**L3 -- Security / Validation:** Validates that all dynamic fields in the template can be rendered for at least one existing record. This catches broken placeholders before the template is saved and used in production.

### L4 -- Performance

- Dynamic report generation (`report_template_ids`) is the slowest part; each report is generated per record via `_render_qweb_pdf()`
- `_classify_per_lang()` batches records by language to minimize template re-renders
- `auto_delete=True` (default) reduces database growth but prevents email body archival

### L4 -- Security

- `_has_unsafe_expression()` checks for dangerous QWeb/expressions before rendering
- `is_template_editor` field gates write access for non-admin users
- `can_write` returns True only if the user is either the template owner or an admin

---

## mail.render.mixin (Render Mixin)

**File:** `models/mail_render_mixin.py`

**Type:** Abstract model -- used as mixin for `mail.template`, `mail.composer.mixin`

### Rendering Engines

Three engines supported, selected via `render_engine` field attribute:

| Engine | Description | Safety |
|--------|-------------|--------|
| `inline_template` | `{{ object.field }}` syntax | Safe with regex fallback (no eval) |
| `qweb` | Full QWeb / OWL template syntax | Restricted unless `mail.group_mail_template_editor` |
| `qweb_view` | Reference to an `ir.ui.view` QWeb template | Restricted unless `mail.group_mail_template_editor` |

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `lang` | Char | Placeholder expression for per-recipient language |

### Key Methods

#### `_render_template(template_src, model, res_ids, engine, ...)` (static method)

**L3 -- Core Renderer:** Entry point for all template rendering. Dispatches to engine-specific methods.

**L4 -- Performance:** The `qweb_regex` path (used when the template contains only safe expressions) avoids the full QWeb compilation step and uses regex substitution instead. This is significantly faster for simple templates.

**L4 -- Security:** Unsafe expressions trigger `raise_on_forbidden_code_for_model` in the QWeb engine, raising `AccessError` unless the user is a template editor.

#### `_render_eval_context()` (static method)

**L3 -- Helper:** Builds the evaluation context available in all template engines. Exposes:
- `object`: The current record
- `user`: Current user record
- `ctx`: Current context dict
- `format_addr`, `format_date`, `format_datetime`, `format_time`, `format_amount`, `format_duration`
- `is_html_empty`, `slug`, `env`

#### `_render_template_postprocess(model, rendered)` (static method)

**L3 -- Helper:** Post-processes rendered HTML to convert relative URLs to absolute URLs using `web.base.url` as the base. Also strips comments if `preserve_comments` option is not set.

#### `_render_encapsulate(layout_xmlid, html, ...)` (static method)

**L3 -- Helper:** Wraps rendered content in an email layout template (e.g., `mail_notification_layout`). Used by the notification system to add headers, footers, and action buttons.

### L4 -- Security Model

Two rendering modes based on `_unrestricted_rendering`:
- **Restricted** (`_unrestricted_rendering = False`, default): Requires `mail.group_mail_template_editor` membership for QWeb rendering of templates with unsafe expressions. Used by `mail.composer.mixin`.
- **Unrestricted** (`_unrestricted_rendering = True`): Full QWeb rendering allowed. Used by `mail.template`.

---

## mail.composer.mixin (Composer Mixin)

**File:** `models/mail_composer_mixin.py`

**Type:** Abstract model -- mixin for email composition wizards

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `subject` | Char | Computed | From template or blank |
| `body` | Html | Computed | From template or blank |
| `body_has_template_value` | Boolean | Computed | True if body matches template |
| `template_id` | Many2one | -- | Source template |
| `lang` | Char | Computed | From template or blank |
| `is_mail_template_editor` | Boolean | Computed | User is template editor |
| `can_edit_body` | Boolean | Computed | User can modify body content |

### Key Methods

#### `_render_field(field, res_ids, ...)` / `_render_lang(res_ids, ...)`

**L3 -- Override Pattern:** These methods provide sudo-based rendering for non-editors. When a non-template-editor user opens a composer pre-filled from a template, they cannot modify the template-sourced content. The mixin forces the template value and enters sudo mode for rendering.

```python
# Non-editor editing body that's from template:
# 1. Body is locked to template value
# 2. Rendering uses sudo (template editor permissions)
# 3. Non-editor can only change non-template fields
```

**L3 -- Security:** Prevents non-editors from injecting custom content into template-rendered bodies while still allowing them to use the template for sending.

---

## mail.activity.mixin (Activity Mixin)

**File:** `models/mail_activity_mixin.py`

**Type:** Abstract model -- mixin for document models that use activities

### Fields

| Field | Type | Group | Description |
|-------|------|-------|-------------|
| `activity_ids` | One2many | `base.group_user` | All activities on this record |
| `activity_state` | Selection | `base.group_user` | Computed state (overdue/today/planned) |
| `activity_user_id` | Many2one | `base.group_user` | User of most recent activity |
| `activity_type_id` | Many2one | `base.group_user` | Type of most recent activity |
| `activity_type_icon` | Char | `base.group_user` | Icon of activity type |
| `activity_date_deadline` | Date | `base.group_user` | Deadline of most urgent activity |
| `my_activity_date_deadline` | Date | `base.group_user` | Current user's most urgent activity |
| `activity_summary` | Char | `base.group_user` | Summary of most recent activity |
| `activity_exception_decoration` | Selection | `base.group_user` | UI decoration based on exception |
| `activity_exception_icon` | Char | `base.group_user` | Icon for exception decoration |

### Key Methods

#### `activity_schedule(act_type_xmlid='', date_deadline=None, ...)` / `activity_feedback()` / `activity_unlink()` / `activity_reschedule()`

**L3 -- Workflow Trigger:** These are the primary activity management API for document models.

`activity_schedule()`:
1. Resolves `act_type_xmlid` to `activity_type_id`
2. Validates model compatibility (`activity_type.res_model == self._name`)
3. Sets `automated=True` for all created activities
4. Uses `activity_type.default_user_id` if no user specified
5. Respects `mail_activity_automation_skip` context to skip automation

**L3 -- Override Pattern:** Override `activity_schedule()` to inject custom activity creation logic (e.g., auto-assign based on record state).

```python
# Example: Auto-assign to sales team leader
def activity_schedule(self, act_type_xmlid='', date_deadline=None, **act_values):
    if not act_values.get('user_id'):
        act_values['user_id'] = self.team_id.leader_id.user_id.id
    return super().activity_schedule(act_type_xmlid=act_type_xmlid,
                                     date_deadline=date_deadline, **act_values)
```

#### `_search_activity_state()` / `_search_activity_user_id()` / `_read_group_groupby('activity_state')`

**L3 -- Performance:** These methods implement search domain support for computed activity fields. They use raw SQL with timezone-aware date comparison for `_search_activity_state()`.

**L4 -- Performance:** The SQL implementation for `_search_activity_state()` computes state on-the-fly using `SIGN(EXTRACT(day from date_deadline - current_date))`. This avoids storing computed state but requires a subquery for filtering.

#### `_read_group_groupby('activity_state')`

**L4 -- Performance:** When grouping a list view by `activity_state`, Odoo creates a lateral join with a SQL subquery that computes the minimum state per record. This is significantly faster than computing the state for each record individually.

---

## mail.alias (Email Alias)

**File:** `models/mail_alias.py`

### Alias Contact Security Levels

| Value | Description | Access Control |
|-------|-------------|---------------|
| `everyone` | Anyone can email this alias | No restriction |
| `partners` | Only authenticated partners | Must have partner account |
| `followers` | Only document followers | Must be follower of target record |

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `alias_name` | Char | -- | Local part (e.g., 'jobs') |
| `alias_full_name` | Char | Computed, Stored | Full email (e.g., 'jobs@example.com') |
| `alias_domain_id` | Many2one | Company default | Alias domain |
| `alias_domain` | Char | Related | Domain name |
| `alias_model_id` | Many2one | Required | Target model (must have `message_ids` field) |
| `alias_defaults` | Text | `{}` | Default field values for new records |
| `alias_force_thread_id` | Integer | -- | Force all messages to this record |
| `alias_parent_model_id` | Many2one | -- | Owner model for the alias |
| `alias_parent_thread_id` | Integer | -- | Owner record ID |
| `alias_contact` | Selection | `everyone` | Contact security policy |
| `alias_incoming_local` | Boolean | False | Use local-part only for routing |
| `alias_bounced_content` | Html | -- | Custom bounce message |
| `alias_status` | Selection | Computed | `not_tested` / `valid` / `invalid` |

### Key Methods

#### `_routing_check_route(message_dict, route, ...)` (static method, via `mail.thread`)

**L3 -- Security:** Validates that the sender is authorized for this alias based on `alias_contact`. If the sender is not authorized, `_alias_bounce_incoming_email()` is called to send a bounce message and set `alias_status = 'invalid'`.

#### `_alias_bounce_incoming_email(message, message_dict, set_invalid=True)`

**L3 -- Failure Mode:** Called when a message is rejected by the alias routing rules:
- `set_invalid=True`: Alias is misconfigured; sets `alias_status='invalid'`, sends bounce to sender
- `set_invalid=False`: Sender is not authorized; sends bounce but does not mark alias invalid

**L4 -- Localization:** Bounce emails are sent in the author's language when `author_id` is available.

#### `_sanitize_alias_name(name, is_email=False)` (static method)

**L3 -- Security:** Cleans alias names per RFC5322:
- Converts to ASCII (removes accents)
- Removes leading/trailing dots and consecutive dots
- Rejects non-ASCII characters (except a subset of atext: `!#$%&'*+\-/=?^_`{|}~` and `.`)
- For `is_email=True`, extracts and re-attaches the domain part

### L4 -- Security

- `_check_alias_is_ascii()` validates RFC5322 compliance on create/write
- `_check_alias_domain_clash()` prevents aliases from using bounce/catchall addresses
- `_check_alias_domain_id_mc()` validates multi-company domain consistency
- `alias_defaults` is evaluated via `ast.literal_eval()` (safe; not `eval()`)

### L4 -- Performance

- `alias_full_name` is stored and indexed (`btree_not_null`) for fast routing lookups
- Alias validation uses SQL unique index on `(alias_name, COALESCE(alias_domain_id, 0))`

---

## mail.blacklist (Email Blacklist)

**File:** `models/mail_blacklist.py`

**Inherits:** `mail.thread`

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `email` | Char | Required | Normalized email address |
| `active` | Boolean | True | Archived = removed from blacklist |

### Constraints

| Constraint | Condition |
|------------|-----------|
| Unique | `email` is unique (case-insensitive, normalized) |

### Key Methods

#### `_add(email, message=None)` / `_remove(email, message=None)`

**L3 -- Cross-Model:** These are the canonical methods for managing the blacklist.

- `_add()`: Normalizes email, creates or unarchives the blacklist entry, optionally posts a Chatter note
- `_remove()`: Archives the entry (soft delete), optionally posts a Chatter note

**L3 -- Override Pattern:** Override `_add()` to add custom processing (e.g., notify administrators, sync to external spam filters).

#### `_search(domain, ...)` / `_search()`

**L3 -- Performance:** Overrides the ORM search to normalize email queries. Any domain search on the `email` field automatically normalizes the search value via `tools.email_normalize()` before executing.

```python
# Searching for 'John.Doe@Example.COM' automatically normalizes to 'john.doe@example.com'
# and finds the matching blacklist entry
```

### L4 -- Security

- Email normalization is consistent: `tools.email_normalize()` handles Unicode, dots in Gmail addresses, and plus-addressing
- Blacklist checks are skipped for certain system email addresses (e.g., postmaster)
- Blacklisted email addresses cannot be unsubscribed via standard means

---

## discuss.channel (Discussion Channel) -- L4 Upgrade

**File:** `models/discuss/discuss_channel.py`

**Inherits:** `mail.thread`, `bus.listener.mixin`

**Key Difference from mail.thread:** Sets `_mail_flat_thread = False` -- replies are nested under parent messages. Also sets `_mail_post_access = 'read'` (lower than default `write`).

### Channel Types

| Value | Description | Behavior |
|-------|-------------|----------|
| `chat` | Private 1-on-1 DM | Exactly 2 members; Odoo auto-deduplicates by partner pair via SQL; members not auto-added via group |
| `group` | Private group | Multiple members, invite-only, member-based naming, leave posts notification |
| `channel` | Public channel | Can be freely joined (subject to `group_public_id` restriction); auto-subscription via `group_ids` |

### Fields (Complete)

| Field | Type | Default | L2 Notes |
|-------|------|---------|----------|
| `name` | Char | Required | Computed from `channel_name_member_ids` (first 3 members) if unset; display name uses `format_list()` for localization |
| `active` | Boolean | True | Soft-delete; inactive channels hidden from UI but not purged |
| `channel_type` | Selection | `channel` | Readonly after create; chat/group cannot be upgraded to channel |
| `is_editable` | Boolean | Computed | Checks `has_access('write')`; channels are editable by any member |
| `default_display_mode` | Selection | -- | Only value: `'video_full_screen'`; used when opening from invitation link |
| `description` | Text | -- | Only displayed on `channel`/`group` types |
| `image_128` | Image | -- | Custom channel avatar; max 128x128; takes precedence over generated SVG avatar |
| `avatar_128` | Image | Computed | Generated from `channel_avatar`/`group_avatar` SVG with HSL color from `uuid` hash; cached |
| `avatar_cache_key` | Char | Computed | SHA512 hex of `avatar_128`; invalidates CDN/browser cache when avatar changes |
| `channel_partner_ids` | Many2many | Computed | Inverse of `channel_member_ids.partner_id`; allow `6` command to replace all members |
| `channel_member_ids` | One2many | -- | Cascade-deleted with channel; cascading to parent channel on member creation |
| `parent_channel_id` | Many2one | -- | Sub-channel creation; `ondelete='cascade'`; readonly after create |
| `sub_channel_ids` | One2many | -- | Child channels; computed from parent |
| `from_message_id` | Many2one | -- | Message this sub-channel was created from; unique per channel; validates message belongs to parent chain |
| `pinned_message_ids` | One2many | -- | Domain: `model='discuss.channel' AND pinned_at IS NOT NULL`; not a stored inverse |
| `sfu_channel_uuid` | Char | -- | System-only; SFU server channel ID; `base.group_system` only |
| `sfu_server_url` | Char | -- | System-only; SFU server base URL; `base.group_system` only |
| `rtc_session_ids` | One2many | -- | Active WebRTC sessions; `base.group_system` only; cascade-deleted |
| `call_history_ids` | One2many | -- | Historical call records |
| `is_member` | Boolean | Computed | Search on `self_member_id` existence; uses separate query to avoid bad SQL plan |
| `self_member_id` | Many2one | Computed sudo | Current user's member record; sudo for performance |
| `invited_member_ids` | One2many | Computed sudo | Members with active `rtc_inviting_session_id` (ringing) |
| `member_count` | Integer | Computed | `_read_group` count of `channel_member_ids`; refreshes on member add/remove |
| `message_count` | Integer | Computed | Count of non-notification messages; excludes `user_notification` type |
| `last_interest_dt` | Datetime | `now() - 1s` | Indexed; drives channel ordering in sidebar; updated on user-initiated message post |
| `group_ids` | Many2many | -- | Auto-subscribe members of these groups; only valid for `channel` type |
| `uuid` | Char | Random 10-char token | Shared on invitation links; uses non-ambiguous chars (no `l`, `I`, `O`, `1`); unique constraint |
| `group_public_id` | Many2one | Default `base.group_user` | Authorization group; only for `channel` type; inherited by sub-channels; prevents public access |
| `invitation_url` | Char | Computed | Format: `/chat/{id}/{uuid}`; used for invite links |
| `channel_name_member_ids` | One2many | Computed via SQL LATERAL | First 3 members used for auto-naming; fetched via LATERAL JOIN for performance |

### SQL Constraints

| Constraint | Condition | Purpose |
|------------|-----------|---------|
| `from_message_id UNIQUE` | Only one sub-channel per origin message | Prevents duplicate thread creation |
| `uuid UNIQUE` | Channel UUID must be unique | Invitation link integrity |
| `channel_type = 'channel' OR group_public_id IS NULL` | Group auth only on channels | Prevents misconfiguration on chat/group |

### Python Constraints

| Method | Validation |
|--------|-----------|
| `_constraint_from_message_id` | `sudo()`; message must belong to parent channel or its sub-channels |
| `_constraint_parent_channel_id` | Parent cannot have a parent, must be `channel`/`group`, type must match |
| `_constraint_partners_chat` | `sudo()`; chat channels cannot exceed 2 members |
| `_constraint_group_id_channel` | `sudo()`; `group_public_id`/`group_ids` only allowed on `channel` type |

### Key Methods -- L3/L4 Detail

#### `_get_or_create_chat(partners_to, pin=True)` -- L3/L4

**L3 -- Cross-Model:** Returns canonical chat channel between exactly 2 partners. Uses raw SQL `ARRAY_AGG(DISTINCT ... ORDER BY ...)` to match existing chats by exact partner set.

**L3 -- Workflow Trigger:**
1. Checks existing chat via SQL (matches by sorted partner IDs, ignores non-partner members)
2. If found: pins current user (`unpin_dt=False`), broadcasts header to all members
3. If not found: creates new chat, pins current user only (`unpin_dt=False`), leaves correspondent unpinned (chat hidden until message sent)

**L4 -- Performance:** Uses `flush_model()` before SQL to ensure consistency. `FOR NO KEY UPDATE SKIP LOCKED` on `fetched_message_id` update avoids serialization errors on concurrent tab opens.

#### `_add_members(partners=None, guests=None, users=None, ...)` -- L3

**L3 -- Cross-Model:** Core membership addition. Key behaviors:
- Skips existing members (deduplication by partner_id/guest_id)
- Creates member records; if parent channel exists and is writable, uses `sudo()` for the create
- Posts "joined the channel" notification for non-chat channels
- For invite: sends `discuss.channel/joined` bus event to new member's user/guest
- Broadcasts member add to channel via `Store.Many('channel_member_ids', mode='ADD')`

#### `_action_unfollow(partner=None, guest=None, post_leave_message=True)` -- L3

**L3 -- Workflow Trigger:** Leaves channel. For non-chat: posts "left the channel" notification as the departing user (sudo). Unpins chat window via `Store`. Cascades unfollow to sub-channel memberships using the same partner/guest.

#### `_subscribe_users_automatically()` / `_subscribe_users_automatically_get_members()` -- L3

**L3 -- Cross-Model:** After channel create, adds all active partners in `group_ids` who are not already members. Uses `sudo()` for the create. Broadcasts new members via Store.

#### `message_post(message_type="notification", ...)` -- L3

**L3 -- Override:** Updates `last_interest_dt` on user-initiated messages (not notification type). Strips `mail_post_autofollow` (channels use member model, not followers). Handles `special_mentions` containing `"everyone"` to mention all channel members.

#### `_message_post_after_hook(message, msg_vals)` -- L3

**L3 -- Workflow Trigger:** Two behaviors:
1. Auto-sets author's message as seen for themselves (updates `seen_message_id` + `new_message_separator`)
2. For sub-channels: if parent channel exists and message mentions partners, invites mentioned partners to the parent channel

#### `set_message_pin(message_id, pinned)` -- L3

**L3 -- Workflow Trigger:** Uses raw SQL `UPDATE ... SET pinned_at=...` to avoid updating `write_date` on message. Posts channel notification when pinning. Broadcasts via `Store.add(message_to_update, "pinned_at")`.

#### `invite_by_email(emails)` -- L3/L4

**L3 -- Security:** Requires internal user with read access; `channel_type` must be group or public channel without `group_public_id`. Normalizes emails, excludes existing members. Signs invite token via `hash_sign()` with `"mail.invite_email"` context.

**L4 -- Failure Mode:** Catches `MailDeliveryException`; differentiates connection refused (bad server config) from general delivery failure.

#### `_notify_get_recipients(message, msg_vals, **kwargs)` -- L3/L4

**L3 -- Cross-Model:** Completely overrides mail.thread. Channels have no followers; notifications go to members. Two recipient sets:
- Direct `partner_ids` on message (for mentions): filtered by access rules, excludes author, excludes bounce count >= 10
- Channel members: filtered by `mute_until_dt`, busy status, custom notification preference, user settings

**L4 -- Performance:** Uses raw SQL to join `res_partner`, `res_users`, and `res_users_settings` in one query. Web push recipients get `notif='web_push'`; direct mention recipients inherit user notification type.

#### `_notify_thread(message, msg_vals, **kwargs)` -- L4

**L4 -- Override:** Calls `super()` then sends `discuss.channel/new_message` bus event via `_bus_send()`. Supports `temporary_id` context for optimistic message IDs.

#### `_notify_by_web_push_prepare_payload(message, msg_vals, ...)` -- L4

**L4 -- Performance:** Formats push notification title differently per channel type:
- `chat`: `"Author Name"`
- `channel`: `"#channel_name - Author Name"`
- `group`: `"Member1, Member2 and Author Name - Author Name"`

#### `execute_command_help()` / `execute_command_who()` / `execute_command_leave()` -- L3

**L3 -- Channel Commands:** Built-in slash commands:
- `/help`: Displays contextual help (channel name for public, member list for group/chat, alone message for DM)
- `/who`: Lists first 30 members with links; appends "more" if exceeding limit, "you" if exact count
- `/leave`: Calls `action_unfollow()` for channel/group; calls `channel_pin(False)` for chat (unpin rather than leave)

#### `channel_fetched()` -- L4

**L4 -- Performance:** Updates `fetched_message_id` using `FOR NO KEY UPDATE SKIP LOCKED` to handle concurrent tabs. Broadcasts `discuss.channel.member/fetched` event to channel. Only runs on `chat` and `whatsapp` channel types.

#### `_create_sub_channel(from_message_id=None, name=None)` -- L3

**L3 -- Workflow Trigger:** Creates sub-channel inheriting parent type. Uses message body (stripped, truncated to 30 chars) as default name, or "This message has been removed" if empty. Adds author and message author as members (not current user). Posts notification on parent channel.

#### `_get_channels_as_member()` -- L4

**L4 -- Performance:** Uses two separate searches to avoid bad OR query plans. Returns public channels/groups where user is member + private chats/groups where user is pinned member.

### L4 -- Store Class Integration

The `Store` class (`mail.tools.discuss.Store`) is the primary mechanism for WebSocket notifications on channel changes. Key patterns:

**Sync field names (`_sync_field_names()`)** return per subchannel:
```python
res[None] = ["channel_type", "create_uid", "last_interest_dt", "member_count", "name", "uuid", ...]
# with predicates: avatar_cache_key only for channel/group, group_ids/group_public_id only for channel
```

**Write diff detection:** On any `write()`, compares old vs new field values and broadcasts only changed fields via `Store.add(channel, diff)`. Uses `Store.Attr`, `Store.One`, `Store.Many` descriptors for complex field sync.

**Member list sync:** Member add/remove broadcasts `Store.Many('channel_member_ids', mode='ADD'/'DELETE')`. Channel name computed from members broadcasts `Store.Many('channel_name_member_ids', sort='id')`.

### L4 -- Security

- `_get_allowed_message_partner_ids()`: For channels with `group_public_id`, only partners whose `all_group_ids` intersect with that group can be mentioned. For chat/group, only existing members can be mentioned.
- `invite_by_email()`: Requires `_is_internal()` user with read access; email tokens are HMAC-signed with server key.
- Public users redirected to `/discuss/channel/{id}` (public page); internal users redirected to `action-discuss?active_id={id}`.
- `sfu_channel_uuid` and `sfu_server_url` are `base.group_system` only -- not exposed to regular users even via Store.

### L4 -- Odoo 18 to 19 Changes

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| Threading | Flat (`_mail_flat_thread=True`) | Nested for discuss.channel |
| Channel notification bus | Direct `bus.bus.sendone()` per field | `Store` class batching |
| Chat deduplication | ORM domain search | Raw SQL with `ARRAY_AGG(DISTINCT ORDER BY)` |
| Member list sync | `channel_partner_ids` direct inverse | `Store.Many` with mode='ADD'/'DELETE' |
| Sub-channel creation | Not available | `from_message_id` + `parent_channel_id` |
| Mute scheduling | None | `mute_until_dt` + cron `_cleanup_expired_mutes` |
| Custom notification per member | Not available | `custom_notifications` on member |
| Pinning | ORM write | Raw SQL to preserve `write_date` |

---

## discuss.channel.member (Channel Member) -- L4 Upgrade

**File:** `models/discuss/discuss_channel_member.py`

**Inherits:** `bus.listener.mixin`

### Fields (Complete)

| Field | Type | Default | L2 Notes |
|-------|------|---------|----------|
| `partner_id` | Many2one | -- | Member partner; `ondelete='cascade'`; indexed; exclusive with `guest_id` |
| `guest_id` | Many2one | -- | Member guest; `ondelete='cascade'`; indexed; exclusive with `partner_id` |
| `is_self` | Boolean | Computed | Current user/guest matches this member; searchable via `_search_is_self()` |
| `channel_id` | Many2one | Required | Target channel; `ondelete='cascade'`; `bypass_search_access=True` |
| `custom_channel_name` | Char | -- | Member's personal nickname for this channel |
| `custom_notifications` | Selection | -- | Per-member override: `'all'` / `'mentions'` / `'no_notif'`; falls back to `res.users.settings`; only applied to channels |
| `mute_until_dt` | Datetime | -- | Mute notification until this datetime; `-1` sentinel means indefinitely |
| `fetched_message_id` | Many2one | -- | Last message the member has fetched (for "seen" indicator); `btree_not_null` index |
| `seen_message_id` | Many2one | -- | Last message the member has seen; used for unread count + "seen" indicator |
| `new_message_separator` | Integer | 0 | Message ID threshold for unread separator display; `required=True` |
| `message_unread_counter` | Integer | Computed | Count of messages with `id >= new_message_separator` and type not in (`notification`, `user_notification`); computed via raw SQL |
| `is_pinned` | Boolean | Computed | True if not unpinned OR last_interest_dt >= unpin_dt OR channel.last_interest_dt >= unpin_dt; searchable via `_search_is_pinned()` with custom SQL domain |
| `unpin_dt` | Datetime | -- | When user unpinned the channel; if set, `is_pinned` is False unless activity after unpin |
| `last_interest_dt` | Datetime | `now() - 1s` | Indexed; updated on create/join/pin; drives sidebar ordering |
| `last_seen_dt` | Datetime | -- | When member was last online; used for presence display |
| `rtc_session_ids` | One2many | -- | Active RTC (voice/video) sessions for this member |
| `rtc_inviting_session_id` | Many2one | -- | Currently ringing session for this member; triggers push notification + UI ring |
| `display_name` | Char | Computed | Format: `"<member_name>" in "<channel_name>"` |

### Constraints

| Constraint | Condition | Purpose |
|------------|-----------|---------|
| Unique index | `(channel_id, partner_id)` WHERE partner_id NOT NULL | One partner membership per channel |
| Unique index | `(channel_id, guest_id)` WHERE guest_id NOT NULL | One guest membership per channel |
| SQL CHECK | `(partner_id IS NOT NULL AND guest_id IS NULL) OR (partner_id IS NULL AND guest_id IS NOT NULL)` | Exactly one identity type |
| `_contrains_no_public_member` | No partner with a public user | Public users cannot be channel members |

### SQL Indexes

| Index | Columns | Type | Purpose |
|-------|---------|------|---------|
| `_seen_message_id_idx` | `(channel_id, partner_id, seen_message_id)` | B-tree | Fast "seen" sync queries |
| `_partner_unique` | `(channel_id, partner_id)` WHERE partner_id NOT NULL | Partial unique | Enforce one partner per channel |
| `_guest_unique` | `(channel_id, guest_id)` WHERE guest_id NOT NULL | Partial unique | Enforce one guest per channel |

### Key Methods -- L3/L4 Detail

#### `create(vals_list)` -- L3/L4

**L3 -- Cross-Model:** On create, cascades member to parent channel via `_add_members()`. For chat channels: rejects creation if any existing members exist (enforces 2-person limit). After create: invalidates `partner_id.channel_ids` and `guest_id.channel_ids` to keep inverse caches fresh. Broadcasts `Store.Many('channel_name_member_ids')` if name-computing members changed.

**L4 -- Performance:** When `mail_create_bypass_create_check` context matches `_bypass_create_check` (set during `discuss.channel` create with partners), runs as `sudo()` to bypass ACLs.

**L4 -- Edge Case:** If channel creation includes `channel_partner_ids` (via `6` command), creates members before channel so channel is not yet public when members join.

#### `write(vals)` -- L3

**L3 -- Override:** Prevents changing `channel_id`, `partner_id`, or `guest_id` after creation. Detects field changes via `_sync_field_names()` and broadcasts diffs via `Store.add(member, diff)`. If `message_unread_counter` changed, also sends `message_unread_counter_bus_id` from bus.

#### `_sync_field_names()` -- L3

Returns syncable fields: `custom_channel_name`, `custom_notifications`, `last_interest_dt`, `message_unread_counter`, `mute_until_dt`, `new_message_separator`, `rtc_inviting_session_id` (sudo), `unpin_dt`.

#### `unlink()` -- L3

**L3 -- Workflow Trigger:** Cascades to sub-channel members with same partner/guest (calls `_action_unfollow` on each). Unlinks own `rtc_session_ids` via sudo first (ensures unlink overrides run). Broadcasts `Store.Many('channel_member_ids', mode='DELETE')` for all affected channels.

#### `_notify_typing(is_typing)` -- L3

Broadcasts `Store.Attr(member, {isTyping, is_typing_dt})` to channel. Called by channel controller when user starts/stops typing.

#### `_notify_mute()` -- L3

**L3 -- Workflow Trigger:** If `mute_until_dt` is set and not `-1`, triggers `ir_cron_discuss_channel_member_unmute` at that datetime. The cron job calls `_cleanup_expired_mutes()` which resets `mute_until_dt=False` and broadcasts notification.

#### `_cleanup_expired_mutes()` (cron) -- L4

**L4 -- Performance:** Searches all members with expired `mute_until_dt`, batches write, then broadcasts via `_notify_mute()`. Runs as a scheduled cron job.

#### `_mark_as_read(last_message_id)` / `_set_last_seen_message(message, notify=True)` -- L3/L4

**L3 -- Workflow Trigger:** Sets `seen_message_id`, `fetched_message_id`, `last_seen_dt`. Only sends bus notification for `chat`/`group` types (via `_types_allowing_seen_infos()`). If `notify=False` (called from own message post), skips bus send to avoid self-notification.

**L4 -- Edge Case:** Uses `max(self.fetched_message_id.id, message.id)` so `fetched_message_id` never moves backwards.

#### `_set_new_message_separator(message_id)` -- L4

**L4 -- Performance:** Only sends bus notification if value actually changed. Broadcasts `Store` with `message_unread_counter`, `new_message_separator`, and `message_unread_counter_bus_id` (from `bus.bus._bus_last_id()`).

#### `_compute_message_unread()` -- L4

**L4 -- Performance:** Raw SQL `COUNT(*) ... GROUP BY discuss_channel_member.id`. Flushes `mail.message` and `channel_id`/`new_message_separator` before query. Handles empty recordset by setting all counters to 0.

#### `_search_is_pinned(operator, operand)` -- L4

**L4 -- Performance:** Uses `Domain.custom(to_sql=...)` with a SQL predicate that joins to `discuss_channel` via LATERAL LEFT JOIN. The predicate checks: `unpin_dt IS NULL OR last_interest_dt >= unpin_dt OR channel.last_interest_dt >= unpin_dt`. This allows the ORM to use the index on `unpin_dt` for filtering.

#### `_gc_unpin_outdated_sub_channels()` -- L4

**L4 -- Autovacuum:** Runs via `@api.autovacuum`. Finds sub-channel members where:
- No recent activity (last_interest_dt < 2 days ago)
- Channel also has no recent activity
- No messages have arrived since the member's separator

Sets `unpin_dt = now()` and sends `Store.add(channel, {close_chat_window: True})` to close the chat window.

#### `_to_store_persona(fields=None)` -- L3

**L3 -- Bus Integration:** Serializes member identity for web client. Returns `Store.Attr` for `partner_id` (sudo, with mention fields) and `guest_id` (sudo). Uses `predicate` to exclude null sides. When `fields == "avatar_card"`, uses `avatar_128`, `im_status`, `name` for compact display.

#### `_to_store_defaults(target)` -- L3

**L3 -- Bus Integration:** Returns fields for the current-user member record: `channel_id` (as thread), `create_date`, `fetched_message_id`, `last_seen_dt`, `seen_message_id`, plus persona fields.

#### RTC Methods -- L3

`(_rtc_join_call)`: Creates session, syncs existing sessions, joins SFU if threshold met. `(_join_sfu)`: Calls SFU server with JWT signed with `mail.sfu_local_key` (created on-demand). `(_rtc_leave_call(session_id=None))`: If session_id given, removes only that session; otherwise removes all. `(_rtc_invite_members(member_ids=None))`: Sets `rtc_inviting_session_id` on eligible members, sends push notification with call invite. Eligibility: not already in call, not busy, not a guest with stale presence.

### L4 -- Guest vs Partner Identity

The model supports two mutually exclusive identity types. The `_bus_channel()` method returns `self.partner_id.main_user_id or self.guest_id` -- the user's primary user or the guest. This is the bus channel for real-time notifications.

**L4 -- Edge Case:** A partner record can exist with no user (no `user_ids`). In this case `_contrains_no_public_member` checks `partner_id.user_ids` for `_is_public()`. Partners without users always pass this check.

### L4 -- Odoo 18 to 19 Changes

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| Pin/unpin state | Boolean `is_pinned` field | `unpin_dt` + computed `is_pinned`; pin timestamp preserved |
| Sub-channel auto-unpin | None | `_gc_unpin_outdated_sub_channels()` autovacuum |
| Unread counter | ORM compute | Raw SQL COUNT with message type filter |
| Typing indicator | Direct bus.sendone | Store.Attr with timestamp |
| Custom member name | Not available | `custom_channel_name` field |
| Per-member notifications | Not available | `custom_notifications` with user settings fallback |
| Mute scheduling | Not available | `mute_until_dt` + cron cleanup |

### L4 -- Performance Considerations

- `message_unread_counter` uses SQL aggregation -- avoids loading all messages into memory
- `_search_is_pinned` uses custom SQL domain with LATERAL JOIN -- enables index usage that ORM cannot generate
- `_gc_unpin_outdated_sub_channels` uses raw SQL subquery with `NOT EXISTS` for efficient cleanup
- Store serialization (`_to_store_persona`, `_to_store_defaults`) uses `sudo()` and prefetches partner/guest in batch
- `channel_fetched` uses `FOR NO KEY UPDATE SKIP LOCKED` to prevent serialization on concurrent tab writes

---

## mail.guest (Anonymous Guest)

**File:** `models/discuss/mail_guest.py`

**File:** `models/discuss/mail_guest.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Guest display name |
| `access_token` | Char | Cookie-based authentication token |
| `country_id` | Many2one | Guest country |
| `email` | Char | Optional guest email |
| `lang` | Char | Preferred language |
| `timezone` | Char | Preferred timezone |
| `channel_ids` | Many2many | Channels the guest is member of |

### Key Methods

#### `_get_guest_from_token()` (static method)

**L3 -- Security:** Resolves the guest from the `dgid` cookie token. Returns a sudo-guest record. Used by the web controller to authenticate anonymous users in live chat.

#### `_get_or_create_guest()` (static method)

**L3 -- Cross-Model:** Gets or creates a guest record for the current session. Called on first access to a live chat channel.

#### `_set_auth_cookie()` / `_update_country()`

**L3 -- Helper:** Sets the `dgid` cookie on the response for subsequent session recognition. Updates guest country based on IP geolocation.

### L4 -- Security

- Guest authentication is token-based (no password)
- `access_token` is a random string generated via `secrets.token_hex()`
- Guests can only access channels they are members of

---

## mail.alias.domain (Alias Domain)

**File:** `models/mail_alias_domain.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Domain name (e.g., 'example.com') |
| `company_ids` | Many2many | Companies using this domain |
| `bounce_alias` | Char | Bounce address local part (e.g., 'bounce') |
| `catchall_alias` | Char | Catchall address local part (e.g., 'catchall') |
| `default_from_alias` | Char | Default From address local part |

### Key Methods

#### `_alias_routing_numerical(...)` (static method)

**L4 -- Performance:** Generates the RFC2822 `From` address by combining `default_from_alias` with the domain. Used by `_message_get_default_from()`.

---

## mail.thread.blacklist / mail.thread.cc / mail.thread.main.attachment

These are mixin models that extend `mail.thread` with specific feature sets:

### `mail.thread.blacklist`

- Adds blacklist checking to `_notify_thread()` and `_message_auto_subscribe()`
- Overrides `_notify_record_by_email()` to skip blacklisted recipients
- Key method: `_is_blacklisted_communication(partners)` -- checks if any partner is on the blacklist

### `mail.thread.cc`

- Adds CC field handling to `message_post()` and `_notify_thread()`
- Parses and validates CC addresses from the `email_cc` parameter
- Adds CC recipients as `partner_ids` if they match existing partners

### `mail.thread.main.attachment`

- Adds `main_attachment_id` field to the document model
- Provides `_message_set_main_attachment_id()` helper to update the main attachment
- Used by CRM, Project, and other modules to designate a primary document attachment

---

## Model Relationships

```
mail.message (1) ──────────────────────────────────────────────────────────────┐
      │                                                                        │
      ├─── (1) mail.mail (inherits via _inherits)                             │
      │         └─ mail.mail.mail_message_id ── (N) mail.message             │
      │                                                                          │
      ├─── (*) mail.notification ── (1) res.partner (recipient)               │
      │         └─ mail.notification.mail_mail_id ── (N) mail.mail           │
      │                                                                          │
      ├─── (*) mail.followers                                                 │
      │         res_model + res_id ───────────────────────────────────────────┤
      │         └─ (1) res.partner (follower)                                 │
      │         └─ (*) mail.message.subtype (subtypes)                        │
      │                                                                          │
      ├─── (*) mail.tracking.value ── (1) ir.model.fields (tracked field)    │
      │                                                                          │
      └─── (*) mail.message.subtype (subtype_id)                              │
                                                                            │
mail.activity (N) ───────────────────────────────────────────────────────────┤
      ├─ (1) ir.model (res_model_id)                                         │
      ├─ (1) res.users (user_id)                                             │
      ├─ (1) mail.activity.type (activity_type_id)                           │
      └─ (res_model + res_id) ────────────────────────────────────────────────┘

discuss.channel ── (*) discuss.channel.member ── (1) res.partner
                                              └─ (1) mail.guest
      └─ (*) discuss.channel.rtc.session ── (1) discuss.channel.member

mail.alias (N) ─── (1) ir.model (alias_model_id)
              └─ (N) mail.alias.domain ── (N) res.company

mail.blacklist ── (N) res.company (via alias_domain_id)

mail.template (N) ── (1) ir.model (model_id)
               └─ (*) ir.attachment (attachment_ids)
               └─ (*) ir.actions.report (report_template_ids)
```

---

## L4 -- Performance Patterns

### Bus Notification Efficiency

Real-time updates in the web client flow through the `Store` class (`mail.tools.discuss.Store`). The Store batches field updates and sends a single WebSocket message per user action, rather than one per field change. Key patterns:

```python
# Instead of multiple bus.sendone() calls:
Store(bus_channel=channel).add(
    channel,
    {'field_a': value_a, 'field_b': value_b}
).bus_send()

# Channel member sync uses Store.Many for list fields:
Store(bus_channel=channel).add(
    channel,
    Store.Many("channel_name_member_ids", sort="id")
).bus_send()
```

### Batch Rendering for Email

`_classify_per_lang()` groups template recipients by language, minimizing the number of template render passes. For 100 records in 3 languages, this generates 3 render passes instead of 100.

### Raw SQL for Bulk Operations

Follower insertion (`_insert_followers()`), notification creation, and garbage collection use raw SQL for maximum throughput. ORM overhead is eliminated for these high-volume operations.

---

## L4 -- Security Considerations

### Access Control Hierarchy

1. **Document ACLs** -- Control read/write/unlink on the target record (e.g., `crm.lead`)
2. **`_mail_post_access`** -- Controls who can post messages (default: `write` access on document)
3. **Message internal flag** -- Controls who can read the message content (`is_internal` → `internal` subtype)
4. **Notification visibility** -- `_filtered_for_web_client()` filters out notifications for external users
5. **Template rendering** -- `_has_unsafe_expression()` prevents code injection via QWeb

### Injection Risks

| Area | Risk | Mitigation |
|------|------|------------|
| `alias_defaults` evaluation | Python code injection | Uses `ast.literal_eval()` only |
| Email address normalization | Email spoofing | All emails normalized before storage/query |
| QWeb rendering | Server-side code execution | `raise_on_forbidden_code_for_model` restricts access |
| Inline template expressions | Arbitrary attribute access | Regex engine restricts to safe expressions |
| Message body (HTML) | XSS | HTML sanitized with `sanitize_html()` using `email_outgoing` policy |

### Information Disclosure

- `author_avatar` generates avatars from name hash for users without photos
- `failure_reason` may contain SMTP server details visible to all message viewers
- Tracking values for removed fields (`field_info` JSON) are visible only to system administrators

---

## L4 -- Odoo 18 to 19 Migration Reference

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| Template rendering engine | Jinja2 (`{{ }}`) | QWeb (`render_engine='qweb'`) |
| Message notification bus | Direct `bus.bus.sendone()` | `Store` class batching |
| Channel threading | Flat (`_mail_flat_thread=True`) | Nested for discuss.channel |
| Notification model | Direct `mail.notification` creation | Deferred via `mail.message.schedule` |
| Activity chaining | Separate fields + write | `triggered_next_type_id` compute pattern |
| Tracking display | Static ordering | `_mail_track_order_fields()` with ormcache |
| Follower insertion | Delete + Insert | `ON CONFLICT DO UPDATE` (upsert) |
| Email queue processing | Per-email commits | Configurable batch size via ICP |
| Mail gateway routing | `message_route()` | Enhanced `_routing_check_route()` with bounce counting |
| Guest authentication | Session-based | Cookie-based `dgid` token with `access_token` field |
| Activity search | ORM domain | Raw SQL with timezone-aware date comparison |
| Template editing | Open template editor | Restricted via `is_template_editor` field |

---

## discuss.channel -- Channel Commands, Sub-Channels, and Advanced Patterns

### Channel Commands

Odoo channels support built-in slash commands processed by `execute_command_*` methods. Commands are invoked by typing `/command_name` in the message input.

| Command | Method | Behavior |
|---------|--------|----------|
| `/help` | `execute_command_help()` | Shows contextual help: channel name for public channels, member list for group/chat, "alone" for empty DM |
| `/who` | `execute_command_who()` | Lists up to 30 channel members with HTML links; appends "more" if additional members exist, "you" if list is complete |
| `/leave` | `execute_command_leave()` | For channel/group: calls `action_unfollow()` (full unfollow). For chat: calls `channel_pin(False)` (unpin only, preserves conversation) |

**L3 -- Override Pattern:** Custom commands can be registered in `discuss.channel.command` model (see `discuss_channel_command.py` in the discuss models). Commands receive the channel and keyword arguments from the message parsing.

### Sub-Channel / Thread Creation

**L3 -- Workflow Trigger:** Sub-channels (`parent_channel_id` set) allow splitting a conversation. Created via `_create_sub_channel(from_message_id, name)`:

1. Resolves the source message; strips HTML tags and truncates to 30 chars as default name
2. If message body is empty: name = "This message has been removed"
3. Creates new channel with same `channel_type` as parent, sets `from_message_id` and `parent_channel_id`
4. Adds both the current user and the message's author as initial members
5. Posts a notification on the parent channel with a link to the new sub-channel

**L4 -- Constraint:** `from_message_id` is unique per channel (SQL unique constraint). The `_constraint_from_message_id` Python constraint (sudo) ensures the message belongs to the parent channel or one of its sub-channels. Sub-channels cannot change their `parent_channel_id` or `from_message_id` after creation.

**L4 -- Edge Case:** Sub-channel's `group_public_id` is automatically inherited from its parent via `_compute_group_public_id`. Sub-channels cannot override `group_public_id` (write blocked).

### Public Channel Authorization

**L3 -- Security:** Public channels (`channel_type='channel'`) can be restricted to a specific user group via `group_public_id`. The channel is visible in the UI but joining requires membership in that group.

- When `group_public_id` is set: only partners whose `user_ids.all_group_ids` intersect with it can be mentioned (`_get_allowed_message_partner_ids()`)
- When `group_public_id` is unset: any authenticated user can join
- Sub-channels inherit the parent's `group_public_id` automatically
- Default: new channels default to `base.group_user` (all internal users)

**L3 -- Auto-Subscription:** The `group_ids` field causes members of those groups to be automatically added as members on channel creation or when `group_ids` changes (via `_subscribe_users_automatically()`). This runs after channel creation via `_mail_post_init` hook and when `group_ids` is written.

### SFU (Selective Forwarding Unit) for RTC

**L4 -- Performance:** When a channel has 3+ active RTC sessions (`SFU_MODE_THRESHOLD = 3`), Odoo switches from peer-to-peer to SFU mode:

1. `_join_sfu()` obtains a channel UUID and URL from the configured SFU server
2. Signs a JWT with `mail.sfu_local_key` (auto-created as `ir.config_parameter` if not set) using `iss: {base_url}:channel:{channel_id}`
3. The SFU server URL and channel UUID are stored in `sfu_server_url` and `sfu_channel_uuid` (both `base.group_system` only)
4. All existing sessions receive a `discuss.channel.rtc.session/sfu_hot_swap` event with fresh server info
5. New joiners use `_get_rtc_server_info()` to get their JWT claims (`session_id`, `ice_servers`) signed with the same key, 8-hour TTL

**L4 -- Security:** SFU key is stored server-side only. Clients never see the signing key. JWTs are short-lived (8h) and scoped to a specific session ID.

### Presence and Typing

**L4 -- Integration:** Typing indicators are sent via `_notify_typing(is_typing)` on the member, which broadcasts `Store.Attr(member, {isTyping, is_typing_dt})` to the channel. This is called from the web controller on message input events.

**L4 -- Presence:** `last_seen_dt` on channel member is updated when `_set_last_seen_message()` is called, indicating the user has viewed the channel. The `mail.presence` model tracks global user online/away status, used by `_get_rtc_invite_members_domain()` to filter out busy users from call invites.

### Message Pinning

**L3 -- Workflow Trigger:** `set_message_pin(message_id, pinned)` uses raw SQL to set `pinned_at` without updating `write_date`. On pin: posts a notification message listing the pinners. Broadcasts `Store.add(message, 'pinned_at')` for real-time UI update. Pinned messages are listed via the `pinned_message_ids` one2many (domain-filtered).

---

## discuss.channel -- Extended RTC and Push Notifications

### RTC Session Lifecycle

**L3 -- Cross-Model:** `discuss.channel.rtc.session` (defined in `discuss_channel_rtc_session.py`) tracks active WebRTC sessions. A session belongs to one `channel_member_id`. The session carries `is_camera_on`, `is_screen_sharing_on`, `is_deaf`, and write-to-talk state.

**Key flows:**
- **Join call** (`_rtc_join_call`): Creates session, deletes any existing sessions for same user, cancels any ringing invitations, syncs existing sessions, joins SFU if threshold met, invites eligible members
- **Leave call** (`_rtc_leave_call`): If `session_id` given, deletes only that session. Otherwise deletes all sessions for this member and cancels their invitations
- **Sync sessions** (`_rtc_sync_sessions`): Deletes inactive sessions, returns current sessions and any given `check_rtc_session_ids` that no longer exist

**L4 -- Edge Case:** Multiple browser tabs sharing the same user each create a separate RTC session. All are valid and shown in the call UI.

### Web Push Notifications

**L4 -- Integration:** Channel notifications use web push for offline users. `_notify_thread_by_web_push()` filters recipients to `notif='web_push'` only (inbox notifications handled separately). Push payload is formatted by `_notify_by_web_push_prepare_payload()` with channel-type-specific title formatting.

**L4 -- Call push notifications:** When `_rtc_invite_members()` is called, it sends push notifications with `PUSH_NOTIFICATION_TYPE.CALL` and actions "Accept"/"Decline". The payload is generated per-recipient language using `_classify_per_lang()` pattern.

### Invite by Email with Token

**L4 -- Security:** `invite_by_email()` signs an invite token using `hash_sign(env(su=True), "mail.invite_email", addr)` which produces an HMAC-SHA256 signature. The token is embedded in the email template (`mail.discuss_channel_invitation_template`) as part of the invitation URL. The signature is verified when the recipient accesses the link.

---

## Key Cross-Model Relationships (Channel Ecosystem)

```
discuss.channel (1) ────── (*) discuss.channel.member
                                  │
                    ┌─────────────┴──────────────┐
               (1) res.partner              (1) mail.guest
                                                  │
                                    (*) discuss.channel.member
                                              (via guest_id)

discuss.channel ──── (1) discuss.channel (parent)
                      └───── (*) discuss.channel (sub_channels)

discuss.channel.member (1) ────── (*) discuss.channel.rtc.session
                                         └───── (1) discuss.channel.member
                                                    (channel_member_id)

discuss.channel ──── (N) mail.message (via model='discuss.channel', res_id=id)
                           └───── (*) mail.message (parent_id = message, for threads)

discuss.channel (N) ──── (N) res.groups (group_ids = auto-subscribe)
```

---

## L4 -- Performance Patterns for Channel Operations

| Operation | Strategy |
|-----------|----------|
| Member add to large channel | `Store.Many('channel_member_ids', mode='ADD')` batched; no flush of channel fields |
| Unread counter update | Raw SQL COUNT grouped by member ID; flushes message table before query |
| Is_pinned search | Custom SQL domain with LATERAL JOIN; uses `unpin_dt` index |
| Chat deduplication | Raw SQL `ARRAY_AGG(DISTINCT ORDER BY)` with HAVING clause |
| Chat pin (unpin) | Sets `unpin_dt` directly; bus notification closes chat window |
| Member-based channel naming | LATERAL subquery LIMIT 3; only for `group` type channels |
| Sub-channel auto-unpin | Autovacuum SQL with NOT EXISTS subquery; avoids ORM overhead |
| Message pin | Raw SQL UPDATE preserves `write_date`; no ORM write triggered |
| `channel_fetched` | `FOR NO KEY UPDATE SKIP LOCKED` avoids serialization on concurrent tabs |
| RTC session sync | Deletes inactive first, then returns current + outdated sessions |

---

## L4 -- Security Patterns for Channel Operations

| Area | Mechanism |
|------|-----------|
| Chat creation | Only 2 partners allowed; SQL unique constraint on sorted partner pair |
| Channel member access | Public users cannot be members; constraint check on `partner_id.user_ids._is_public()` |
| Mention authorization | Channel: must be in `group_public_id` if set; Group/chat: must be existing member |
| Email invite | HMAC-signed token with per-address signing key; internal user + read access required |
| SFU credentials | Server-side only; clients receive short-lived JWTs scoped to session ID |
| Sub-channel creation | Only from messages belonging to parent chain; `from_message_id` unique per channel |
| Group authorization | SQL CHECK constraint: `channel_type = 'channel' OR group_public_id IS NULL` |

---

## L4 -- Odoo 18 to 19 Full Migration Reference (Channel Ecosystem)

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| Threading model | Flat (`_mail_flat_thread=True`) | Nested for discuss.channel only |
| Member model | `mail.channel.partner` (old) | `discuss.channel.member` (new) |
| Channel model | `mail.channel` (merged) | `discuss.channel` (split from mail.thread) |
| Bus notifications | Direct `bus.bus.sendone()` per field | `Store` class batching + diff detection |
| Chat deduplication | ORM `search()` with partner domain | Raw SQL `ARRAY_AGG` with HAVING |
| Pin state | Boolean `is_pinned` | `unpin_dt` + computed `is_pinned`; preserves pin timestamp |
| Unread counter | ORM compute on message count | Raw SQL COUNT with message type exclusion |
| Typing indicator | Direct bus notification | `Store.Attr` with datetime |
| Custom member name | Not available | `custom_channel_name` field |
| Per-member notifications | User-level only | `custom_notifications` with user settings fallback |
| Mute scheduling | None | `mute_until_dt` + cron `_cleanup_expired_mutes` |
| Sub-channel creation | Not available | `parent_channel_id` + `from_message_id` |
| Group authorization | Not available | `group_public_id` Many2one |
| Auto-subscribe via groups | Not available | `group_ids` on channel |
| SFU architecture | P2P only | SFU threshold at 3+ sessions |
| Guest identity | `mail.guest` with session auth | `mail.guest` with cookie token (`access_token`) |

---

## Related

- [Modules/bus](Modules/bus.md) -- Real-time event bus (WebSocket)
- [Core/API](Core/API.md) -- @api.depends, @api.onchange patterns
- [Patterns/Security Patterns](Patterns/Security-Patterns.md) -- ACL, ir.rule, field groups
- [Modules/res.partner](Modules/res.partner.md) -- Contact model (author/recipient)
- [Modules/calendar](Modules/calendar.md) -- Calendar integration with activities
- [Modules/Project](Modules/Project.md) -- Project/task with activity and follower management
- [Modules/CRM](Modules/CRM.md) -- CRM leads with email gateway routing
