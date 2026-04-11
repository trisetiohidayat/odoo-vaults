---
tags: [odoo, odoo17, module, mail]
---

# Mail Module

## Overview

The `mail` module is Odoo's internal communication and collaboration framework. It provides the Chatter system (message walls), email routing, followers/subscriptions, notifications, activities (calendar-based tasks), and real-time discussion channels (Discuss/Chat).

In Odoo 17 the old `mail.channel` model was renamed to `discuss.channel`; the module files live in `~/odoo/odoo17/odoo/addons/mail/models/` and its subdirectory `models/discuss/`.

## Key Models

| Model | File | Lines | Description |
|-------|------|-------|-------------|
| `mail.thread` | `models/mail_thread.py` | 4,679 | Abstract mixin providing email integration and message tracking |
| `mail.message` | `models/mail_message.py` | 1,295 | Core message record (email, comment, notification) |
| `mail.mail` | `models/mail_mail.py` | 777 | RFC2822 email message to send (`_inherits mail.message`) |
| `mail.followers` | `models/mail_followers.py` | 525 | Subscription records linking partners to documents |
| `mail.notification` | `models/mail_notification.py` | 142 | Per-recipient delivery status tracking |
| `mail.activity` | `models/mail_activity.py` | 828 | Kanban-style to-do activities |
| `mail.alias` | `models/mail_alias.py` | 538 | Email-to-record routing and bounce handling |
| `mail.blacklist` | `models/mail_blacklist.py` | 112 | Email blacklist with normalized search |
| `mail.thread.cc` | `models/mail_thread_cc.py` | 52 | Carbon-copy mixin |
| `mail.composer.mixin` | `models/mail_composer_mixin.py` | 187 | Template-based composer mixin with QWeb rendering |
| `mail.tracking.duration.mixin` | `models/mail_tracking_duration_mixin.py` | 107 | JSON field computing time spent in each stage value |
| `discuss.channel` | `models/discuss/discuss_channel.py` | large | Discussion channel (chat, group, or channel) |
| `mail.compose.message` | `wizard/mail_compose_message.py` | large | Message composition wizard |

## mail.thread (Mixin)

**File:** `~/odoo/odoo17/odoo/addons/mail/models/mail_thread.py`
**Lines:** 4,679 (the single largest file in the module)
**Class definition:** Line 49

```python
class MailThread(models.AbstractModel):
    _name = 'mail.thread'
    _description = 'Email Thread'
    _mail_flat_thread = True      # flatten the discussion history
    _mail_post_access = 'write'   # access required on the document to post
    _primary_email = 'email'       # Must be set for models that can be created by alias
```

The `mail.thread` mixin provides email integration and message tracking to any model that inherits from it (e.g. `sale.order`, `project.task`). It is an `AbstractModel` — no database table is created.

### Class-level Configuration

| Attribute | Default | Purpose |
|----------|---------|---------|
| `_mail_flat_thread` | `True` | All messages without `parent_id` attach to the first message |
| `_mail_post_access` | `'write'` | Access right required on the document to post a message |
| `_primary_email` | `'email'` | Field name used for email-based record creation via alias |

### Fields Defined by mail.thread (Lines 93-122)

```python
message_is_follower = fields.Boolean(
    'Is Follower', compute='_compute_message_is_follower',
    search='_search_message_is_follower', compute_sudo=False)
message_follower_ids = fields.Many2many(
    'res.partner', 'mail_followers_rel',
    'res_id', 'partner_id',
    string='Followers', copy=False,
    groups="base.group_user")
message_partner_ids = fields.Many2many(
    'res.partner', 'mail_message_res_partner_rel',
    'res_id', 'partner_id',
    string='Followers (Partners)',
    groups="base.group_user", index=True)
message_ids = fields.One2many(
    'mail.message', 'res_id',
    string='Messages',
    domain=lambda self: [('model', '=', self._name)], auto_join=True)
has_message = fields.Boolean(compute='_compute_has_message', search='_search_has_message')
message_needaction = fields.Boolean(
    'Action Needed',
    compute='_compute_message_needaction', search='_search_message_needaction',
    compute_sudo=False)
message_needaction_counter = fields.Integer(
    'Number of Actions',
    compute='_compute_message_needaction_counter', compute_sudo=False)
message_has_error = fields.Boolean(
    'Message Delivery Error',
    compute='_compute_message_has_error', search='_search_message_has_error',
    compute_sudo=False)
message_has_error_counter = fields.Integer(
    'Number of Errors',
    compute='_compute_message_has_error_counter', compute_sudo=False)
message_attachment_count = fields.Integer(
    'Attachment Count',
    compute='_compute_message_attachment_count', compute_sudo=False)
```

### message_post() — Lines 2086-2254

The primary API for posting a message to a document.

```python
def message_post(self, *, message_type='comment', ...):
```

**Parameters:**
- `body` — HTML content of the message
- `subject` — Subject line (used for email notifications)
- `author_id` — Partner who wrote the message (defaults to current user)
- `email_from` — SMTP From address (overrides author_id email)
- `message_type` — One of: `email`, `comment`, `notification`, `auto_comment`, `user_notification`, `email_outgoing`
- `parent_id` — Parent message ID for threading replies (if `_mail_flat_thread=False`)
- `subtype_id` — `mail.message.subtype` record — triggers notifications if it has `track_recipients=True`
- `subtype` — XML ID of subtype (resolved to `subtype_id`)
- `partner_ids` — Additional explicit recipients
- `attachment_ids` — Existing `ir.attachment` record IDs to attach
- `attachments` — List of `(filename, raw_data)` tuples — creates new attachments
- `body_has_html_content` — Set to True if body already contains HTML (skip HTML sanitization)
- `guest_channel_id` — Guest (public user) channel for Discuss
- `channel_ids` — `discuss.channel` records to broadcast to
- `add_sign` — Prepend company salutation text (default True)
- `disable_routing` — Skip notification routing (for internal logs)
- `mail_server_id` — Force specific outgoing mail server

**Flow:**
1. Validate parameters, resolve `subtype_id` from `subtype` XML ID
2. Compute author — prefer `author_id.partner_id`, fallback to `email_from`, then `self.env.user.partner_id`
3. Auto-assign `message_id` (UUID-based RFC 2397 Message-ID header)
4. Process attachments via `_process_attachments_for_post()` — handles inline CIDs, creates new `ir.attachment` records with access tokens, replaces local `/web/image/` URLs with public access URLs
5. Create the `mail.message` record via `_message_create()`
6. Call `_message_post_after_hook()` (empty by default, override for custom post-processing)
7. Call `_notify_thread()` to route notifications
8. Return the `mail.message` record

### _message_create() — Lines 2050-2084

```python
def _message_create(self, values_list):
    # values_list: list of dicts or single dict
    # Returns: mail.message recordset
```

Wraps `self.env['mail.message'].create()` with:
- Automatic `mail_message_id` (ID of the parent message for flat threads)
- Setting `model`/`res_id` to this model's name and record IDs
- Returning an empty recordset if called with no values (guards against empty writes)

### _notify_thread() — Lines 3112-3163

Main notification dispatcher called after every `message_post()`.

```python
def _notify_thread(self, message, msg_vals=False, **kwargs):
```

**Flow:**
1. `msg_vals` carries values from `message_post()` to avoid re-reading from DB
2. Call `_notify_get_recipients()` to compute recipient groups (user, portal, follower, customer)
3. Call `_notify_thread_by_inbox()` — creates inbox notifications + bus notifications
4. Call `_notify_thread_by_email()` — creates `mail.mail` records and sends via SMTP
5. Call `_notify_thread_by_web_push()` — Cloud push notifications via VAPID

### _notify_thread_by_email() — Lines 3212-3359

Email notification sender with batching.

**Key algorithm:**
- Groups recipients by language and access level (internal vs portal/external)
- Further splits by recipient partner using `_notify_get_recipients_groups()` → 4 groups: `user` (employees), `portal` (portal users), `follower` (customers following), `customer` (customers not following)
- Creates `mail.mail` records via `self.env['mail.mail'].create(mail_values_list)`
- Batch size: **50 emails per batch**
- Forces immediate send if total emails < 100 (via `force_send=True`)
- Otherwise queues emails for background sending
- Calls `_notify_by_email_render_layout()` to produce final HTML email body

### _notify_get_recipients() — Lines 3675-3757

Computes all notification recipients for a message. Calls `mail.followers._get_recipient_data()` to fetch follower data, then filters:
- Removes the message author from notifications (unless `notify_author=True`)
- Filters by access rights: `mail_blacklist` check, `mail.message.filter_domain()` security
- Classifies into groups via `_notify_get_recipients_groups()`

### _notify_get_recipients_groups() — Lines 3759-3837

Returns 4 notification groups as tuples `(group_id, group_data)`:

| Group ID | Description | Access |
|----------|-------------|--------|
| `user` | Internal employees (not share) | Full message, attachments, actions |
| `portal` | Portal users | Full message, attachments |
| `follower` | Customer followers | Full message, attachments |
| `customer` | Non-follower customers | Plain text message, no attachments |

### _notify_by_email_get_base_mail_values() — Lines 3594-3654

Computes RFC2822 email headers for each outgoing mail:

```python
def _notify_by_email_get_base_mail_values(self, message, target_pid):
    # Returns dict of mail.mail field values
```

Key values set:
- `mail_message_id` — the `mail.message` ID
- `mail_server_id` — selected via `_notify_get_mail_server_id()`
- `email_from` — from address: `mail_server_id.email_from` or `message.author_id.email_formatted`
- `recipient_ids` — `[target_pid]`
- `references` — Last 3 ancestor Message-IDs (for email threading)
- `reply_to` — alias reply-to or company catchall
- `headers` — dict including `Return-Path`, X-Odoo-Objects, `list-archive`
- Auto-sets `is_archive` True for records in `mail.message.render-message` state

### Notification Batching

Email batching is implemented in `_notify_thread_by_email()` (lines 3212-3359):

```python
# Pseudocode for batching logic:
for recipient_group in recipient_groups:
    batch_size = 50
    for i in range(0, len(recipients), batch_size):
        batch = recipients[i:i + batch_size]
        if i + batch_size >= len(recipients):
            force_send = True  # last batch: force send
        else:
            force_send = False  # queue rest
        # create mail.mail records and send/queue
```

**Batch size constant: 50** (not a named constant — inline in the loop).

### Precommit Hooks for Change Tracking (Lines 493-543)

`mail.thread` uses `cr.precommit.add()` to defer tracking computation until just before commit.

#### _track_prepare() — Lines 493-509

Called at the start of `write()`. Stores initial field values in `cr.precommit.data`:

```python
def _track_prepare(self):
    self.ensure_one()
    tracking_values = {}
    for field_name in self._track_get_fields():
        tracking_values[field_name] = self[field_name]
    if tracking_values:
        self.env.cr.precommit.data.setdefault(
            f'mail.tracking.{self._name}', {}
        )[self.id] = tracking_values
```

Key: `f'mail.tracking.{self._name}'` — a dict keyed by record ID, value is `{field_name: old_value}`.

#### _track_finalize() — Lines 526-543

Called via precommit hook after `write()` succeeds and after `flush()`:

```python
def _track_finalize(self):
    tracking_data = self.env.cr.precommit.data.pop(
        f'mail.tracking.{self._name}', {}
    )
    for record in self:
        initial_values = tracking_data.get(record.id, {})
        if initial_values:
            record._message_track(initial_values, record._cache)
```

The `pop()` ensures tracking runs once per transaction. Any exception here rolls back cleanly.

### _message_track() — Lines 600-656

Core tracking method that compares initial vs current values and creates tracking records.

```python
def _message_track(self, initial_values, current_values):
```

**Logic:**
1. Loop over tracked fields (`self._track_get_fields()` — fields with `tracking=True`)
2. For each field, compare `initial_values[field]` vs `current_values[field]`
3. If changed, create a `mail.tracking.value` record via `_track_cache_to_values()`
4. Determine whether to post a message or just log:
   - If there is a subtype with `track_recipients=True` → `message_post()` with that subtype (creates notification)
   - Otherwise → `_message_log()` (internal note, no notification)
5. After tracking, call `_message_track_post_template()` (empty by default — override to send a message based on tracked change)

**Subtype selection** (for tracked field changes):
```python
subtype = field_value.sudo().tracking_value_ids.filtered(
    lambda r: r.field_id.model == self._name and r.field_id.name == fname
).subtype_id
```
The subtype to notify is read from the first tracking value's `subtype_id`.

### Auto-subscribe on create() and write() (Lines 254-329, 4156-4223)

#### create() — Lines 254-314

```python
def create(self, vals):
    # 1. Auto-subscribe current user
    if self._context.get('mail_post_autofollow') and self.env.user._is_internal():
        vals['message_follower_ids'] = ...
    # 2. Call _message_auto_subscribe() for subtypes
    # 3. Create record
    # 4. Log creation message via _message_auto_subscribe()
    # 5. Set up precommit tracking hooks
    # 6. Return record
```

#### write() — Lines 316-329

```python
def write(self, vals):
    # 1. Call _track_prepare() — store initial values for tracking
    # 2. Perform the write
    # 3. Call _track_finalize() via precommit hook
    # 4. Call _message_auto_subscribe() for subtype-based auto-follow
    return True
```

#### _message_auto_subscribe() — Lines 4156-4223

Handles automatic follower subscription when field values change.

```python
def _message_auto_subscribe(self, updated_values, followers_existing_policy='skip'):
```

**Logic:**
1. Collect all tracked fields (`self._track_get_fields()`)
2. For each tracked field, look for subtypes that have `subscription_ids` where `partner_id` should be added
3. Call `_message_auto_subscribe_followers()` with the computed follower partner IDs
4. The method handles `followers_existing_policy`: `skip` (default), `force` (add even if already following), `replace` (remove old, add new)

The auto-subscribe chain: field change → `_message_track()` creates tracking value → `mail.tracking.value` has `subtype_id` → `_message_auto_subscribe()` reads `subscription_ids` on the subtype → adds those partners as followers.

### Mail Gateway Routing (Lines 1078-1280, 1360-1421)

#### message_process() — Lines 1360-1421

Entry point for all incoming emails (called by `mailgateway` plugin or fetchmail).

```python
def message_process(self, model, message, custom_values=None,
                    save_original=False, thread_id=None,
                    smtp_session_id=None):
```

**Flow:**
1. Parse the email via `mail.message.parse()` (from `email.message`)
2. Optional: save original raw email as attachment
3. Extract `thread_id` — either from Route.custom_values, `In-Reply-To` header lookup, or `message_id` fallback
4. Call `self.routing_map()` to get `{model: aliases}` routing table
5. Route the message via `message_route()` (finds correct model + record)
6. Dispatch to the matched model's `message_process()` override

#### message_route() — Lines 1078-1280

The routing engine. Returns a list of route tuples `[(model, thread_id, custom_values, user_id, alias)]`.

**Routing algorithm:**
1. Extract email addresses from `To`, `CC`, `Delivered-To` headers
2. **Reply detection**: Extract `In-Reply-To` or `References` → try to find existing thread via `mail.message` search by `message_id`
3. **Alias matching**: For each route, check if the address matches any `mail.alias`:
   - `alias_name` must match local part (case-insensitive)
   - Alias domain must match
   - Alias model must match
4. **Fallback**: If no alias matches, use the default model (`model` param)
5. **Thread ID**: If not already known, try to extract from address format (e.g. `alias+thread_id@example.com`)
6. Validate each route via `_routing_check_route()`

#### _routing_check_route() — Lines 797-893

Validates each routed message.

```python
def _routing_check_route(self, message, route, raise_exception=True):
```

Checks:
- `alias_contact` security: `everyone` (no check), `partners` (recipient must be a partner), `followers` (recipient must follow the thread)
- `alias_incoming_local` — if True, only allow local addresses (no external domain in To)
- `alias_allow_private` — if False on the alias, reject private addresses
- Record exists and is not archived (active test)
- User has write access on the document

### _detect_loop_sender() — Lines 957-1040

Mail loop prevention. Uses a moving time window.

```python
def _detect_loop_sender(self, email_from):
    # Threshold: 20 emails
    # Window: 120 minutes (2 hours)
```

Logic:
1. Look up `mail.mail` records where `email_from` matches, sent within the last 120 minutes
2. If count >= 20, flag as a loop
3. If loop detected, route to the bounce handler alias or discard

### message_subscribe() — Lines 4012-4036 (Public API)

```python
def message_subscribe(self, partner_ids=None, subtype_ids=None,
                      channel_ids=None):
    # Checks: write access on document, partner read access
    # Delegates to _message_subscribe()
```

### _message_subscribe() — Lines 4038-4064 (Private API)

```python
def _message_subscribe(self, partner_ids=None, subtype_ids=None,
                        channel_ids=None, existing_policy='skip'):
    # Delegates to mail.followers._insert_followers()
```

`existing_policy`: `skip` (default — leave existing), `force` (update subtype), `replace` (remove then re-add), `update` (add missing subtypes).

### _get_mail_thread_data() — Lines 4381-4422

Provides all thread data needed by the web client in one method. Returns dict with:
- `id`, `name`, `model`, `types`
- `isMailLocked` — prevents reply if thread is locked
- `isChatterOpened`
- `display_order`, `avatar`, `company`
- `following`, `hasWriteAccess`, `hasReadAccess`
- `message_unread`, `message_unread_counter`
- `failureTypes` — list of notification failure types
- `activityData` — via `_get_activity_data()`
- `attachments` — via `self.env['ir.attachment']._format_for_web_client()`
- `activities` — via `activity_ids.activity_format()`
- `followers` — via `message_follower_ids.sorted().partner_ids`
- `suggestedRecipients`
- `trackingValues` — via `message_ids.tracking_value_ids`
- `canPostReadAccessWaiver`

### _process_attachments_for_post() — Lines 2268-2405

Handles attachments during message posting.

**Steps:**
1. Split attachments into two lists:
   - Existing `ir.attachment` records (by `attachment_ids` parameter)
   - New `(fname, fcontent, mime)` tuples (from `attachments` parameter)
2. For existing attachments: verify `res_model`/`res_id` are unset or match this record
3. For new attachments: create `ir.attachment` records with:
   - `datas` — base64-encoded content
   - `mimetype`
   - `name`
   - `res_model='mail.message'`, `res_id=message.id` (after message is created)
   - `access_token` — for public URLs
4. **CID replacement**: For inline attachments with `Content-ID` headers:
   - Replace `cid:xxx` references in body with full image URLs using access token
   - Add attachments as `cid:xxx` content IDs in the message
5. **Local URL replacement**: Replace `/web/image/<id>` URLs with public URLs using attachment's `access_token`

### message_get_followers() — Lines 4225-4240

Public API to retrieve followers.

```python
def message_get_followers(self, partner_ids=None, channel_ids=None):
    # Returns: list of dicts with follower data
```

Filters by optional `partner_ids` (return only those partners' subscriptions) and `channel_ids`.

---

## mail.message

**File:** `~/odoo/odoo17/odoo/addons/mail/models/mail_message.py`
**Lines:** 1,295

### Model Definition

```python
class MailMessage(models.Model):
    _name = 'mail.message'
    _description = 'Message'
    _order = 'id DESC'
    _rec_name = 'record_name'
```

`_inherits` is on `mail.mail` — `mail_message_id` is a Many2one to `mail.message` itself, creating a shared table pattern.

### Fields (Lines 85-191)

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `subject` | Char | Message subject |
| `date` | Datetime | Creation timestamp |
| `body` | Html | HTML content |
| `description` | Char | Short description (max 180 chars, auto-truncated from body) |
| `preview` | Char | Plain-text preview (max 1000 chars) |
| `link_preview_ids` | One2many | Link previews (metadata fetched from URLs in body) |
| `reaction_ids` | One2many | Emoji reactions |
| `attachment_ids` | Many2many | Attachments |
| `parent_id` | Many2one | Parent message for threading |
| `child_ids` | One2many | Reply messages |
| `model` | Char | Target document model (e.g. `sale.order`) |
| `res_id` | Many2oneReference | Target document ID |
| `record_name` | Char | Cached name of the target document |
| `record_alias_domain_id` | Many2one | Alias domain of the target record |
| `record_company_id` | Many2one | Company of the target record |
| `message_type` | Selection | See below |
| `subtype_id` | Many2one | `mail.message.subtype` — drives notifications |
| `is_internal` | Boolean | Internal message (hidden from portal) |
| `email_from` | Char | SMTP From address |
| `author_id` | Many2one | Partner who authored (nullable for system) |
| `author_guest_id` | Many2one | Guest (public user) who authored |
| `partner_ids` | Many2many | Explicit additional recipients |
| `notification_ids` | One2many | Per-recipient notification records |
| `starred_partner_ids` | Many2many | Partners who starred this message |
| `tracking_value_ids` | One2many | Field change tracking values |
| `message_id` | Char | RFC 2397 Message-ID header (UUID-based) |
| `reply_to` | Char | Override Reply-To address |
| `mail_ids` | One2many | `mail.mail` records sent for this message |
| `is_current_user_or_guest_author` | Boolean | Is the current user/guest the author? |

### message_type Values (Lines 115-130)

| Value | Meaning |
|-------|---------|
| `email` | Email sent or received (routed via gateway) |
| `comment` | User comment in Chatter (default for `message_post()`) |
| `notification` | System-generated notification |
| `auto_comment` | Automatically generated comment (e.g. stage change) |
| `user_notification` | Direct notification to a user |
| `email_outgoing` | Email generated by the system (outbound only) |

### Custom Access Rights — check_access_rule() (Lines 364-591)

`mail.message` overrides the standard Odoo ACL system with custom rules because messages span multiple documents.

**Read access:**
- ACL: `read` on `mail.message`
- Allowed if ANY of:
  - `author_id` = current partner
  - `author_id` is in `message_partner_ids` (recipient)
  - Document identified by `(model, res_id)` gives `read` access
  - `is_internal=False` and subtype allows public access
  - `guest_channel_id` is set (public channel)

**Write access:**
- ACL: `write` on `mail.message`
- Allowed if ANY of:
  - `author_id` = current partner
  - Document `(model, res_id)` gives `write` access
  - `guest_channel_id` is set and guest has write access

**Unlink access:**
- ACL: `unlink` on `mail.message`
- Allowed if document `(model, res_id)` gives `write` access (or is admin)

### _search() Override (Lines 272-346)

Custom search implementing access rights filtering:

```python
def _search(self, domain, limit=None, order=None, access_mode='read'):
```

**Logic:**
1. Separate domain into `mail.message`-specific terms and document-related terms
2. For `access_mode='read'`:
   - Split partners into "can read" (internal employees) and "cannot read" (external/public)
   - Internal employees: see all messages where they have document read access OR are author/recipient
   - External users: only non-internal messages with a readable subtype
3. JOINs used:
   - `mail_notification` table to check recipient status
   - `mail_message_res_partner_rel` for explicit recipient list
4. Returns a domain to apply on `mail_message.id`

### Portal / External User Visibility

External users (non-employees, `partner_share=True`) can only see:
- Non-internal messages (`is_internal=False`)
- Messages whose `subtype_id` has `internal=False`
- This is enforced via the SQL domain in `_search()`

---

## mail.mail

**File:** `~/odoo/odoo17/odoo/addons/mail/models/mail_mail.py`
**Lines:** 777

### Model Definition

```python
class MailMail(models.Model):
    _name = 'mail.mail'
    _description = 'Outgoing Mail'
    _inherits = {'mail.message': 'mail_message_id'}
    _order = 'id DESC'
```

`_inherits` means `mail.mail` stores its own fields in `mail_mail` table but also presents all `mail.message` fields. A `mail.mail` record IS a `mail.message` record.

### State Machine (Lines 65-71)

```
outgoing → sent → received → exception → cancel
          ↗         ↗
          └─────────┘  (also goes to exception/sent from outgoing)
```

| State | Meaning |
|-------|---------|
| `outgoing` | Created, not yet sent; queued for delivery |
| `sent` | Successfully delivered to SMTP |
| `received` | Delivered and opened/read (tracked via tracking pixel) |
| `exception` | SMTP delivery failed |
| `canceled` | Manually canceled (e.g. unsubscribed) |

### failure_type Values (Lines 72-85)

| Value | Meaning |
|-------|---------|
| `unknown` | Unclassified error |
| `mail_email_invalid` | Recipient email address is invalid |
| `mail_email_missing` | No email address on recipient partner |
| `mail_from_invalid` | From address is invalid |
| `mail_from_missing` | No from address configured |
| `mail_smtp` | SMTP server connection failed |
| `mail_bl` | Recipient is on email blacklist |
| `mail_optout` | Recipient opted out of this mailing |
| `mail_dup` | Duplicate recipient in the same mass mailing |

### send() — Lines 546-777

Main sending method.

```python
def send(self, auto_commit=False, raise_exception=False):
    # auto_commit: commit transaction after each batch (for long-running sends)
    # raise_exception: re-raise SMTP exceptions
```

**Flow:**
1. Filter to only `outgoing` state records
2. Group by mail server configuration via `_split_by_mail_configuration()`
3. For each group:
   - Get or create SMTP connection (`IAP.to_smtp_gateway()` or direct SMTP)
   - Send emails via `smtp.sendmail()` in batches
4. On success: call `_postprocess_sent_message()` to update notification statuses
5. On failure: set state to `exception`, record `failure_type`/`failure_reason`

### _split_by_mail_configuration() — Lines 493-544

Groups outgoing emails to minimize SMTP connections:

```python
def _split_by_mail_configuration(self):
    # Returns: list of mail.mail record batches
```

Grouping keys: `(mail_server_id, alias_domain_id, email_from)`
Rationale: Each group can use one SMTP connection (one envelope sender).

### _postprocess_sent_message() — Lines 260-297

Post-send processing after SMTP delivery.

```python
def _postprocess_sent_message(self, mail_values, success_pids, failure_reason_per_pid):
```

For each successfully sent recipient:
1. Set `mail_notification.notification_status = 'sent'`
2. Set `mail_notification.mail_mail_id = mail.id` (link notification to mail record)
3. Handle auto-delete: if `auto_delete=True` on the message, mark mail for deletion

For each failed recipient:
1. Set `mail_notification.notification_status = 'exception'`
2. Set `mail_notification.failure_type` and `failure_reason`

Then: `mail.unlink()` for auto-delete records (schedule them for deletion via `ir.actions.server`).

### _prepare_outgoing_list() — Lines 371-491

Builds the list of email dictionaries for SMTP sending.

```python
def _prepare_outgoing_list(self):
    # Returns: list of dicts with email headers and body for each recipient
```

For each `mail.mail`:
1. Resolve recipient email from `recipient_ids` (partners)
2. Render email subject and body (use layout template if configured)
3. Build attachments list with Content-ID for inline images
4. Add list-unsubscribe headers
5. Add personalizations: unfollow links (`email_distinct_fetch_mail_udpate` URL)
6. Add tracking pixel (`/mail/tracking_pixel/<mail_mail_id>`) for open tracking
7. Return dict: `{email_to, subject, body, attachments, headers, ...}`

---

## mail.followers

**File:** `~/odoo/odoo17/odoo/addons/mail/models/mail_followers.py`
**Lines:** 525

### Model Definition

```python
class MailFollowers(models.Model):
    _name = 'mail.followers'
    _description = 'Document Followers'
    _table = 'mail_followers'
```

### SQL Constraint (Line 70)

```sql
ALTER TABLE mail_followers ADD CONSTRAINT unique_mail_followers
    UNIQUE (res_model, res_id, partner_id);
```

A given partner can only follow a given document once. Also has partial unique index on `channel_id`.

### _get_recipient_data() — Lines 104-332

**The most complex method in mail.followers.** Single-query batch fetcher for follower recipient information.

```python
def _get_recipient_data(self, records, company_id=None):
    # Returns: list of dicts per recipient
```

Uses a `WITH sub_followers AS` CTE, then LATERAL joins to:
- `res_partner` — for partner data (email, name, lang, share status)
- `mail_alias` — for alias domains
- `res_users` — for user data (notification preferences)

**Output fields per recipient:**
```python
{
    'id': partner.id,
    'name': partner.name,
    'email': email_normalized or partner.email,  # normalized
    'lang': partner.lang,
    'type': 'user' if internal else 'portal',
    'partner': partner,  # browse record
    'user': user or self.env.user,  # active user for this partner
    'notif': user.notification_type or 'email',
    'is_follower': True,  # always True for this method
    'reason': None,
}
```

### _insert_followers() — Lines 390-422

Main internal method for creating/updating followers.

```python
def _insert_followers(self, res_model, res_id, partner_ids, subtype_ids,
                       existing_policy='skip'):
```

| `existing_policy` | Behavior |
|-------------------|----------|
| `skip` | Leave existing follower records unchanged (default) |
| `force` | Update existing records' subtype_ids to given subtype_ids |
| `replace` | Delete existing, then insert new |
| `update` | Add missing subtype_ids to existing records |

### _add_default_followers() — Lines 424-447

Called from `mail.thread.create()` to set up initial followers.

```python
def _add_default_followers(self, res_model, res_id, partner_ids, channel_ids,
                           ref_partner_ids=None, ref_model=None, ref_res_ids=None):
```

Logic:
1. Compute default subtypes to subscribe to (via `subtype_ids` or `mail.message.subtype` defaults)
2. Detect customer followers: partners where `partner_share=True` are marked as `customer`
3. Handle partner-specific subtypes: certain subtypes only apply to internal users
4. Insert followers with `existing_policy='add'`

---

## mail.notification

**File:** `~/odoo/odoo17/odoo/addons/mail/models/mail_notification.py`
**Lines:** 142

### Model Definition

```python
class MailNotification(models.Model):
    _name = 'mail.notification'
    _table = 'mail_notification'
    _log_access = False  # no create_uid, create_date, write_uid, write_date
    _rec_name = 'res_partner_id'
```

### notification_status Values

| Value | Meaning |
|-------|---------|
| `ready` | Created, not yet processed |
| `process` | Being processed by intermediary (e.g. IAP for SMS) |
| `pending` | Sent (used for SMS; mail does not use this) |
| `sent` | Successfully delivered |
| `bounce` | Recipient email bounced |
| `exception` | Delivery failed |
| `canceled` | Canceled before sending |

### failure_type Values

| Value | Meaning |
|-------|---------|
| `unknown` | Unknown error |
| `mail_bounce` | Email bounced |
| `mail_email_invalid` | Invalid email address |
| `mail_email_missing` | Missing email address |
| `mail_from_invalid` | Invalid from address |
| `mail_from_missing` | Missing from address |
| `mail_smtp` | SMTP connection failure |

### Database Indexes (Lines 63-75)

```sql
-- Composite index for inbox notification queries
CREATE INDEX mail_notification_res_partner_id_is_read_notification_status_mail_message_id
    ON mail_notification (res_partner_id, is_read, notification_status, mail_message_id);

-- Partial index for bounce/exception notifications (author tracking)
CREATE INDEX mail_notification_author_id_notification_status_failure
    ON mail_notification (author_id, notification_status)
    WHERE notification_status IN ('bounce', 'exception');

-- Unique partial index for partner notifications
CREATE UNIQUE INDEX unique_mail_message_id_res_partner_id_if_set
    ON mail_notification (mail_message_id, res_partner_id)
    WHERE res_partner_id IS NOT NULL;
```

### _filtered_for_web_client() — Lines 122-131

Filters notifications shown in the web client:

```python
def _filtered_for_web_client(self):
    # Excludes:
    # - Bounce/exception/canceled notifications for internal users
    # - Notifications from "unimportant" subtypes (subtype.track_recipients=False)
    return self.filtered(lambda n:
        n.notification_status not in ['bounce', 'exception', 'canceled']
        or n.res_partner_id.partner_share
        or n.mail_message_id.subtype_id.track_recipients
    )
```

### _notification_format() — Lines 133-142

Returns JSON-serializable list for web client:

```python
def _notification_format(self):
    return [{
        'id': notif.id,
        'notification_type': notif.notification_type,
        'notification_status': notif.notification_status,
        'failure_type': notif.failure_type,
        'persona': {
            'id': notif.res_partner_id.id,
            'displayName': notif.res_partner_id.display_name,
            'type': "partner"
        } if notif.res_partner_id else False,
    } for notif in self]
```

---

## mail.activity

**File:** `~/odoo/odoo17/odoo/addons/mail/models/mail_activity.py`
**Lines:** 828

### Model Definition

```python
class MailActivity(models.Model):
    _name = 'mail.activity'
    _description = 'Activity'
    _order = 'date_deadline ASC, id ASC'
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `res_model_id` | Many2one | Target model (e.g. `sale.order`) |
| `res_id` | Many2oneReference | Target record ID |
| `activity_type_id` | Many2one | `mail.activity.type` — defines category and icon |
| `summary` | Char | Short label (overrides type's default) |
| `note` | Html | Activity description/notes |
| `date_deadline` | Date | Due date |
| `user_id` | Many2one | Assigned user (responsible) |
| `request_partner_id` | Many2one | Requester (optional) |
| `state` | Selection | Computed: `overdue`, `today`, `planned`, `done` |
| `automated` | Boolean | Created automatically (vs manually by user) |
| `attachment_ids` | Many2many | Attachments on this activity |
| `chaining_type` | Selection | `redirect` (recommended) or `suggest` (next activity) |

### State Computation — _compute_state() (Lines 148-169)

```python
def _compute_state(self):
    # Uses user timezone for deadline comparison
    today = fields.Date.context_today(self, self.env.user)
    for record in self:
        if record.date_deadline < today:
            record.state = 'overdue'
        elif record.date_deadline == today:
            record.state = 'today'
        else:
            record.state = 'planned'
```

### _action_done() — Lines 525-599

Marks an activity as done and handles chaining.

```python
def _action_done(self, feedback=False, subtype=False):
```

**Flow:**
1. Create a `mail.message` with `mail.message.subtype` if `subtype` provided
2. Create "next activities" if the activity type has `default_next_type_id`
3. Handle chained activities: if `chaining_type='suggest'`, copy suggested activities to the record
4. Mark current activity as done (archive or unlink based on `activity_type_id.auto_delete`)
5. Return the created message (if any)

### _calculate_date_deadline() (Lines 188-208)

Computes the initial deadline based on activity type's `delay_count` and `delay_unit`.

```python
def _calculate_date_deadline(self, activity_type):
    # delay_unit: week, day, hour, working_hours, working_days
    # Returns: fields.Date.today() + offset
```

### get_activity_data() — Lines 631-764

Complex aggregation method for the Kanban activity view.

Returns activity grouped by:
- Model
- User
- Stage/deadline

Includes: activity type counts, earliest deadline per group, grouping info for dashboard display.

---

## mail.alias

**File:** `~/odoo/odoo17/odoo/addons/mail/models/mail_alias.py`
**Lines:** 538

### Model Definition

```python
class MailAlias(models.Model):
    _name = 'mail.alias'
    _description = 'Email Alias'
    _order = 'alias_name'
```

### Unique Index (Lines 96-103)

```sql
CREATE UNIQUE INDEX mail_alias_unique_name
    ON mail_alias (alias_name, COALESCE(alias_domain_id, 0));
```

`alias_name` is unique per alias domain. `COALESCE(..., 0)` allows one record with `alias_domain_id=NULL`.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `alias_name` | Char | Local part of the email (e.g. `sales`) |
| `alias_full_name` | Char | Full email: `alias_name@alias_domain.name` |
| `alias_domain_id` | Many2one | `mail.alias.domain` record |
| `alias_model_id` | Many2one | Target model to create records in |
| `alias_defaults` | Text | Python dict of default values for new records |
| `alias_force_thread_id` | Integer | Force all emails to attach to this record |
| `alias_parent_model_id` | Many2one | Parent model (for reply-to routing) |
| `alias_contact` | Selection | Security: `everyone`, `partners`, `followers` |
| `alias_incoming_local` | Boolean | Only accept emails from local domain |
| `alias_allow_private` | Boolean | Allow emails from private addresses |

### alias_contact Security Levels

| Value | Meaning |
|-------|---------|
| `everyone` | Accept from anyone (public aliases) |
| `partners` | Only accept if recipient is a known partner |
| `followers` | Only accept if sender follows the target record |

### _routing_create_bounce_email() — Lines 713-736

Creates a bounce notification when an email is rejected.

```python
def _routing_create_bounce_email(self, message_dict, body=False):
    # Creates mail.mail in exception state
    # Sends back to sender with bounce message
```

### _alias_bounce_incoming_email() — Lines 513-538

Handles bounce processing for incoming emails.

```python
def _alias_bounce_incoming_email(self, message, message_dict):
    # If alias_contact=followers and sender is not a follower:
    #   → sends security warning email to sender
    #   → optionally marks alias as invalid (if recurring)
```

---

## mail.blacklist

**File:** `~/odoo/odoo17/odoo/addons/mail/models/mail_blacklist.py`
**Lines:** 112

### Model Definition

```python
class MailBlackList(models.Model):
    _name = 'mail.blacklist'
    _description = 'Mail Blacklist'
    _inherit = ['mail.thread', 'mail.blacklist.mixin']
```

### _search() Override (Lines 57-68)

The key feature of `mail.blacklist`:

```python
def _search(self, args):
    # Normalizes all email searches to lowercase before querying
    args = list(args)
    for i, arg in enumerate(args):
        if arg[0] == 'email' and arg[1] in ('=', 'ilike', 'like', 'not ilike'):
            args[i] = (arg[0], arg[1], tools.email_normalize(arg[2]))
    return super()._search(args)
```

This ensures blacklist lookups are case-insensitive — `john@example.com` and `JOHN@EXAMPLE.COM` both match the same record.

### _add() / _remove() (Lines 70-100)

Toggle blacklist entries:

```python
def _add(self, email, message=None):
    # Create blacklist record
    # Post an "unsubscribed" message on the record if message param provided

def _remove(self, email, message=None):
    # Unlink or archive the blacklist record
    # Post a "re-subscribed" message if message param provided
```

Both methods accept `email` (unnormalized) and handle the normalization internally via `email_normalize()`.

---

## mail.thread.cc

**File:** `~/odoo/odoo17/odoo/addons/mail/models/mail_thread_cc.py`
**Lines:** 52

### Model Definition

```python
class MailCCMixin(models.AbstractModel):
    _name = 'mail.thread.cc'
    _inherit = 'mail.thread'
    _description = 'Email CC management'
```

Mixin class. Adds `email_cc` field and CC handling to any model that inherits from `mail.thread`.

### Fields

```python
email_cc = fields.Char('Email cc')
```

### _mail_cc_sanitized_raw_dict() — Lines 14-21

```python
def _mail_cc_sanitized_raw_dict(self, cc_string):
    '''return a dict of sanitize_email:raw_email from a string of cc'''
    if not cc_string:
        return {}
    return {
        tools.email_normalize(email): tools.formataddr(
            (name, tools.email_normalize(email))
        )
        for (name, email) in tools.email_split_tuples(cc_string)
    }
```

Returns: `{normalized_email: formatted_email}` where formatted includes name.

### message_update() — Lines 33-44

Merges incoming CC with existing CC on the record:

```python
def message_update(self, msg_dict, update_vals=None):
    new_cc = self._mail_cc_sanitized_raw_dict(msg_dict.get('cc'))
    if new_cc:
        old_cc = self._mail_cc_sanitized_raw_dict(self.email_cc)
        new_cc.update(old_cc)  # merge: new wins for duplicates
        cc_values['email_cc'] = ", ".join(new_cc.values())
```

---

## mail.composer.mixin

**File:** `~/odoo/odoo17/odoo/addons/mail/models/mail_composer_mixin.py`
**Lines:** 187

### Model Definition

```python
class MailComposerMixin(models.AbstractModel):
    _name = 'mail.composer.mixin'
    _description = 'Mail Composer Mixin'
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `subject` | Char | Email subject |
| `body` | Html | Email body (QWeb-rendered) |
| `template_id` | Many2one | Source `mail.template` |
| `lang` | Char | Computed language code |
| `is_mail_template_editor` | Boolean | Is current user a template editor? |
| `can_edit_body` | Boolean | Can user edit the rendered body? |

### Auto-computed Fields (from template)

```python
# All three compute from template_id:
_compute_body()       # self.template_id.body_html or body
_compute_subject()   # self.template_id.subject
_compute_lang()      # self.template_id.lang or partner.lang
```

When `template_id` is set, `subject`, `body`, and `lang` auto-fill from the template.

### _render_field() — Lines 115-187

Renders a QWeb template field safely:

```python
def _render_field(self, field, template_xmlid):
    # 1. Switch to SUPERUSER to bypass record rules
    # 2. Use mail.template's QWeb rendering engine
    # 3. Sanitize output HTML (allow Odoo-specific tags)
    # 4. Return rendered string
```

Rendered in sudo mode to allow template access to restricted records.

---

## mail.tracking.duration.mixin

**File:** `~/odoo/odoo17/odoo/addons/mail/models/mail_tracking_duration_mixin.py`
**Lines:** 107

### Model Definition

```python
class MailTrackingDurationMixin(models.AbstractModel):
    _name = "mail.tracking.duration.mixin"
    _description = "Mixin to compute the time a record has spent in each value a many2one field can take"
```

### Field

```python
duration_tracking = fields.Json(
    string="Status time", compute="_compute_duration_tracking",
    help="JSON that maps ids from a many2one field to seconds spent")
    # e.g. {"1": 1230, "2": 2220, "5": 14}
```

### Required Class Attribute

The implementing model MUST define:

```python
class MyModel(models.Model):
    _track_duration_field = "stage_id"  # the many2one field to track

    stage_id = fields.Many2one('stage.model', tracking=True)
```

Without this, `_compute_duration_tracking()` raises `ValueError`.

### _compute_duration_tracking() — Lines 14-64

Single SQL query joining `mail_tracking_value` and `mail_message`:

```sql
SELECT m.res_id, v.create_date, v.old_value_integer
  FROM mail_tracking_value v
  LEFT JOIN mail_message m ON m.id = v.mail_message_id
 WHERE v.field_id = %(field_id)s
   AND m.model = %(model_name)s
   AND m.res_id IN %(record_ids)s
ORDER BY v.id
```

For each record, calculates:
- Time spent in each stage value = sum of deltas between consecutive tracking dates
- Adds a "fake" tracking entry at the end to account for time in the current value

---

## discuss.channel

**File:** `~/odoo/odoo17/odoo/addons/mail/models/discuss/discuss_channel.py`
**Lines:** large (discuss subdirectory)

### Model Definition

```python
class DiscussChannel(models.Model):
    _name = 'discuss.channel'
    _inherit = ['mail.thread', 'mail.alias.mixin']
    _mail_flat_thread = False     # NOT flat — messages threaded by parent_id
    _mail_post_access = 'read'     # Only read access needed to post
    _description = 'Discussion Channel'
```

### channel_type Values

| Value | Meaning | Constraints |
|-------|---------|-------------|
| `chat` | Direct message / 1-on-1 chat | Max 2 members |
| `channel` | Public channel | No member limit |
| `group` | Private group | No member limit |

### Chat Constraint — Lines 91-96

```python
@api.constraint
def _check_member_limit(self):
    for channel in self:
        if channel.channel_type == 'chat' and len(channel.channel_member_ids) > 2:
            raise ValidationError("A chat channel cannot have more than 2 members.")
```

### Avatar Generation

Channel avatars are auto-generated SVG:
- `image_128` — base64-encoded SVG avatar (256x256)
- `avatar_128` — rounded avatar_128 for display
- Generated via `_generate_avatar()` using channel name initials

### channel_member_ids → discuss.channel.member

Discuss channels track members via `discuss.channel.member` model (separate file in `models/discuss/`). This stores:
- `partner_id` — the member
- `channel_id` — the channel
- `seen_message_id` — last read message
- `fetched_message_id` — last fetched message (for sync)
- `RTCSessionIDs` — active real-time communication sessions

### Invitation URL

Channels generate invite URLs via `action_get_share_url()` — returns a URL with access token for sharing.

---

## mail.compose.message Wizard

**File:** `~/odoo/odoo17/odoo/addons/mail/wizard/mail_compose_message.py`
**Lines:** large (1,400+)

### Model Definition

```python
class MailComposeMessage(models.TransientModel):
    _name = 'mail.compose.message'
    _inherit = 'mail.composer.mixin'
    _description = 'Email composition wizard'
```

`TransientModel` — records are automatically deleted after use.

### composition_mode

| Value | Meaning |
|-------|---------|
| `comment` | Reply/note on existing records (Chatter composer) |
| `mass_mail` | Send to many records via template (Mail Merge) |

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `composition_mode` | Selection | `comment` or `mass_mail` |
| `model` | Char | Target model (e.g. `sale.order`) |
| `res_ids` | Text | Comma-separated record IDs (for mass_mail) |
| `res_id` | Integer | Single record ID (for comment) |
| `partner_ids` | Many2many | Additional recipients |
| `attachment_ids` | Many2many | Attachments |
| `auto_delete` | Boolean | Delete emails after sending |
| `auto_delete_message` | Boolean | Delete chatter messages after sending |
| `mail_server_id` | Many2one | Force specific outgoing server |
| `scheduled_date` | Char | Schedule sending (e.g. `+1d` for tomorrow) |
| `reply_to` | Char | Override Reply-To |

### send_mail() Action

Called when user clicks "Send". Iterates over `res_ids`, renders template for each recipient (with personalization), creates `mail.mail` records, and sends.

### onchange_template_id()

When template is changed, auto-fills `subject`, `body`, `partner_ids`, `email_from`, `mail_server_id` from the template. Disables editing of these fields unless user explicitly overrides.

---

## Summary: Notification Lifecycle

```
User calls message_post()
  │
  ├─► _message_create()         → mail.message record
  │       │
  │       └─► _notify_thread()
  │             │
  │             ├─► _notify_get_recipients()
  │             │     └─► mail.followers._get_recipient_data()
  │             │
  │             ├─► _notify_thread_by_inbox()
  │             │     └─► mail.notification (type=inbox, status=ready)
  │             │
  │             ├─► _notify_thread_by_email()
  │             │     ├─► Batch by language × access level (size=50)
  │             │     ├─► mail.mail.create() (state=outgoing)
  │             │     └─► mail.mail.send() → SMTP → state=sent
  │             │           │
  │             │           └─► _postprocess_sent_message()
  │             │                 └─► mail.notification (status=sent)
  │             │
  │             └─► _notify_thread_by_web_push()
  │                   └─► Push via VAPID (batched if >5 devices)
  │
  └─► _track_finalize() (precommit hook)
        └─► _message_track() → mail.tracking.value records
              └─► auto-subscribe new followers via subtype subscriptions
```

## Summary: Mail Gateway Routing Flow

```
Inbound email arrives at SMTP server
  │
  ├─► fetchmail / mailgateway plugin
  │     └─► mail.thread.message_process()
  │           │
  │           ├─► message_route()
  │           │     ├─► Extract addresses from To/CC
  │           │     ├─► Reply detection (In-Reply-To → existing thread)
  │           │     ├─► Alias matching (alias_name + alias_domain)
  │           │     └─► _routing_check_route() (alias_contact security)
  │           │
  │           └─► Route to correct model's message_new() or message_update()
  │                 ├─► _track_prepare() + write()
  │                 ├─► _track_finalize() via precommit
  │                 └─► _notify_thread() → notifications
  │
  └─► _detect_loop_sender() (rejects if >20 emails/120min from same sender)
```

## SQL Tables

| Table | Model | Notes |
|-------|-------|-------|
| `mail_message` | `mail.message` | Core message table |
| `mail_mail` | `mail.mail` | `_inherits mail.message` — additional email fields |
| `mail_followers` | `mail.followers` | `UNIQUE(res_model, res_id, partner_id)` |
| `mail_notification` | `mail.notification` | Per-recipient delivery status |
| `mail_activity` | `mail.activity` | Kanban activities |
| `mail_alias` | `mail.alias` | Inbound email routing |
| `mail_blacklist` | `mail.blacklist` | Blocked email addresses |
| `mail_tracking_value` | `mail.tracking.value` | Field change tracking |
| `mail_tracking_duration` | (computed) | JSON stored on record via `mail.tracking.duration.mixin` |
| `discuss_channel` | `discuss.channel` | Channels, chats, groups |
| `discuss_channel_member` | `discuss.channel.member` | Channel membership + seen/fetched tracking |
| `mail_alias_domain` | `mail.alias.domain` | Domain-level alias management |
| `mail_message_subtype` | `mail.message.subtype` | Notification subtypes |
| `mail_activity_type` | `mail.activity.type` | Activity categories |

## Key Precommit Hooks in mail.thread

| Hook Key | Purpose | Registered In |
|----------|---------|---------------|
| `f'mail.tracking.{self._name}'` | Defer tracking field comparison until after flush | `_track_prepare()` via `write()` |
| `f'mail.tracking.{self._name}'` | Execute tracking comparison and create tracking values | `_track_finalize()` via precommit callback |

The pattern:
```python
# write():
self._track_prepare()       # store initial values
self.write(vals)             # actual write
self.env.cr.precommit.add(self._track_finalize)  # schedule tracking

# _track_finalize() (called just before commit):
tracking_data = self.env.cr.precommit.data.pop(f'mail.tracking.{self._name}', {})
for record in self:
    record._message_track(initial, current)
```

This ensures:
1. Field values are flushed to DB before comparison
2. Tracking runs after all writes but before commit
3. Any exception causes transaction rollback (no orphaned tracking records)
