---
Module: mail_group
Version: Odoo 18
Type: Business
Tags: [mail,mail_group,alias,mass_mailing,moderation,portal]
Description: Mailing list server — public/private groups with email aliases, member management, optional moderation, and public archive portal.
See Also: [[mail]], [[mass_mailing]], [[Modules/mail]]
---

# mail_group — Mail Group / Mailing List Server

> **Source:** `~/odoo/odoo18/odoo/addons/mail_group/`
> **Depends:** `mail`, `portal`

The `mail_group` module provides Odoo-based mailing list management. Each group owns a **mail.alias**; incoming emails to that alias create `mail.group.message` records. Messages may be automatically accepted or held for moderation. Accepted messages are batch-delivered to all group members. Both members and public visitors can browse the message archive via the portal controller.

---

## Architecture

```
mail.group (inherits mail.alias.mixin)
  ├── alias_id (1-to-1 via _inherits → mail.alias)
  ├── mail.group.member (1-to-many)
  ├── mail.group.message (1-to-many)
  └── mail.group.moderation (1-to-many)

mail.group.message
  └── mail_message_id (1-to-1 → mail.message)
       author_id / body / subject / attachment_ids  (via related)

mail.alias (from base mail module)
  └── alias_name, alias_domain_id, alias_contact, alias_defaults, alias_force_thread_id
```

Key design decisions:
- `mail.group.message` does NOT use `_inherits` on `mail.message` because that would break `mail.message` cache performance. Instead it stores `mail_message_id` as a Many2one and re-exposes key fields (author_id, body, subject, attachment_ids) via `related` with `readonly=False`.
- `mail.group` does NOT inherit `mail.thread`; it implements a custom `message_post()` that manually creates `mail.message` then wraps it in `mail.group.message`.
- `alias_id` is required via `_inherits = {'mail.alias': 'alias_id'}`, so every group auto-creates its alias on record creation.

---

## Model: `mail.group` — The Mailing List

**File:** `models/mail_group.py`
**Inherits:** `mail.alias.mixin` (creates the required `alias_id` via delegation)
**L4 Note:** The mixin is the core extension point — `mail_group` adds group-specific fields and behavior on top of the standard alias infrastructure.

### Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Group display name, translateable |
| `description` | Text | Internal description |
| `image_128` | Image | Group icon |
| `active` | Boolean | Soft-disable (default True) |
| `moderation` | Boolean | If True, incoming messages require moderator approval |
| `moderator_ids` | Many2many(res.users) | Users who can approve/reject messages; default includes creator |
| `moderation_notify` | Boolean | Auto-send "pending moderation" email to sender |
| `moderation_notify_msg` | Html | Custom notification body |
| `moderation_guidelines` | Boolean | Auto-send guidelines to new members |
| `moderation_guidelines_msg` | Html | Guidelines HTML content |
| `moderation_rule_ids` | One2many(mail.group.moderation) | Per-group allow/ban rules |
| `moderation_rule_count` | Integer (compute) | Count of moderation rules |
| `mail_group_message_ids` | One2many(mail.group.message) | All messages in this group |
| `mail_group_message_count` | Integer (compute) | Total message count |
| `mail_group_message_moderation_count` | Integer (compute) | Pending-moderation count |
| `mail_group_message_last_month_count` | Integer (compute) | Accepted messages in last 30 days |
| `member_ids` | One2many(mail.group.member) | All members |
| `member_count` | Integer (compute) | Member count |
| `member_partner_ids` | Many2many(res.partner) (compute+search) | Partners of members |
| `is_member` | Boolean (compute) | Is current user a member (SUDO'd check) |
| `is_moderator` | Boolean (compute) | Is current user a moderator |
| `can_manage_group` | Boolean (compute) | Is admin or moderator |
| `access_mode` | Selection | `'public'` / `'members'` / `'groups'` |
| `access_group_id` | Many2one(res.groups) | Required when access_mode == 'groups' |

### Key Methods

#### Mail Gateway (Alias Binding)

```python
def _alias_get_creation_values(self):
    # Sets alias_model_id=mail.group, alias_force_thread_id=self.id
    # alias_defaults={} — no default field mapping needed
    return super()._alias_get_creation_values()

def message_new(self, msg_dict, custom_values=None):
    """Required by mail gateway, no-op for groups."""
    return

def message_update(self, msg_dict, update_vals=None):
    """Required by mail gateway, no-op for groups."""
    return
```

#### `message_post()` — Custom Posting Flow (not mail.thread)

```python
def message_post(self, body='', subject=None, email_from=None, author_id=None, **kwargs):
    """
    Flow:
      1. _message_compute_author() → resolve author_id + email_from
      2. Create mail.message (model=mail.group, res_id=self.id)
      3. Set reply_to = _get_reply_to() (makes replies go back to alias)
      4. Set message_id = generate_tracking_message_id(...)
      5. _process_attachments_for_post() → handle inline/attachment data
      6. mail.message.create([values])
      7. Find group_message_parent_id (if reply, find parent mail.group.message)
      8. Determine moderation_status: 'accepted' or 'pending_moderation'
      9. Create mail.group.message
     10. Check moderation_rule → auto-accept/ban/hold
     11. If not moderated: _notify_members(group_message)
    """
```

The `message_post` flow is entirely custom because `mail.group` does not inherit `mail.thread`. It bridges the mail gateway to the `mail.group.message` layer.

#### `_alias_get_error()` — Access Control for Incoming Mail

```python
def _alias_get_error(self, message, message_dict, alias):
    """
    Returns None (OK) or AliasError (reject).
    Checks access_mode:
      - 'groups': sender email must belong to access_group_id.users
      - 'members': sender email must be a group member
    Called by mail gateway before accepting bounce-processing email.
    """
```

#### `_notify_members()` — Batch Email Distribution

```python
def _notify_members(self, message):
    """
    Sends message to all members except the author.
    Batch size: read from ir.config_parameter 'mail.session.batch.size' (default 500).
    Per-batch: creates mail.mail records (auto_delete=True, state='outgoing').
    SMTP headers: List-Archive, List-Subscribe, List-Unsubscribe (One-Click RFC8058),
                  List-Id, List-Post, Precedence, X-Auto-Response-Suppress, In-Reply-To.
    Footer: rendered QWeb template 'mail_group.mail_group_footer' with
            group_url, unsub_url, mailto, unsub_label.
    """
```

#### Moderation Notifications

```python
def _notify_moderators(self):
    """Called by _cron_notify_moderators().
    Uses _read_group to count pending messages per group.
    Renders 'mail_group.mail_group_notify_moderation' template.
    Notifies via mail.thread.message_notify() to moderator.partner_id."""

@api.model
def _cron_notify_moderators(self):
    """Scheduled CRON: searches groups with moderation=True,
    calls _notify_moderators() for each."""
```

#### Membership

```python
def _join_group(self, email, partner_id=None):
    """Create or update mail.group.member.
    If moderation_guidelines=True: auto-send guidelines template."""

def _leave_group(self, email, partner_id=None, all_members=False):
    """unlink() member record. If all_members=True, removes all
    matches for email_normalized (not just one)."""

def _find_member(self, email, partner_id=None):
    """Return single mail.group.member for this group + email/partner.
    Uses _find_members() — batch-capable."""

def _find_members(self, email, partner_id):
    """
    Returns {group_id: mail.group.member}.
    Priority: partner match > email-only match.
    When partner_id given: partner_id DESC (partner match first).
    When no partner: partner_id ASC (no-partner first).
    Handles deduplication of multiple members with same email.
    """
```

#### Token Generation (HMAC-based)

```python
def _generate_action_token(self, email, action):
    """HMAC-SHA256 of (group_id, email_normalized, action) with key
    'mail_group-email-subscription'. Used for subscribe/unsubscribe
    confirmation URLs."""

def _generate_group_access_token(self):
    """HMAC of group_id with key 'mail_group-access-token-portal'.
    Used to bypass access rules in portal controller."""

def _generate_email_access_token(self, email):
    """HMAC of (group_id, email_normalized) with key
    'mail_group-access-token-portal-email'.
    Used for One-Click unsubscribe (RFC8058)."""

def _get_email_unsubscribe_url(self, email_to):
    """Builds /group/{id}/unsubscribe_oneclick?email=&token= URL."""
```

### Constraints

| Constraint | Rule |
|---|---|
| `_check_moderator_email` | All moderators must have an email address |
| `_check_moderator_existence` | Moderated groups must have at least one moderator |
| `_check_moderation_notify` | If moderation_notify=True, moderation_notify_msg must be set |
| `_check_moderation_guidelines` | If moderation_guidelines=True, moderation_guidelines_msg must be set |
| `_check_access_mode` | If access_mode=='groups', access_group_id must be set |

### Onchanges

| Onchange | Effect |
|---|---|
| `access_mode` → public | `alias_contact = 'everyone'` |
| `access_mode` → members/private | `alias_contact = 'followers'` |
| `moderation` → True | Auto-add current user to `moderator_ids` |

---

## Model: `mail.group.member` — Subscription Record

**File:** `models/mail_group_member.py`

Stores the subscription of an email (optionally linked to a `res.partner`) to a group.

### Fields

| Field | Type | Description |
|---|---|---|
| `email` | Char | Email address (computed from `partner_id.email` if set) |
| `email_normalized` | Char | Normalized email, stored, indexed |
| `mail_group_id` | Many2one(mail.group) | Target group, cascade delete |
| `partner_id` | Many2one(res.partner) | Optional linked partner |

### Computes

```python
@api.depends('partner_id.email')
def _compute_email(self):
    for member in self:
        member.email = member.partner_id.email if member.partner_id else member.email or False

@api.depends('email')
def _compute_email_normalized(self):
    for member in self:
        member.email_normalized = email_normalize(member.email)
```

### SQL Constraints

`UNIQUE(partner_id, mail_group_id)` — a partner can only subscribe once per group. Note: email is not in the constraint, allowing multiple email-address entries for the same group (same email with different partner_ids, or even no partner).

---

## Model: `mail.group.message` — Encapsulated Email

**File:** `models/mail_group_message.py`

Wraps a `mail.message` with mail-group-specific metadata (moderation, parent/child threading, normalization).

### Fields

| Field | Type | Description |
|---|---|---|
| `mail_group_id` | Many2one(mail.group) | Required, cascade delete |
| `mail_message_id` | Many2one(mail.message) | The underlying mail.message, cascade delete, indexed |
| `moderation_status` | Selection | `'pending_moderation'` / `'accepted'` / `'rejected'`, default `'pending_moderation'` |
| `moderator_id` | Many2one(res.users) | Who moderated this message |
| `author_moderation` | Selection | Computed: `'ban'` / `'allow'` from `mail.group.moderation` lookup |
| `is_group_moderated` | Boolean | Related → `mail_group_id.moderation` |
| `group_message_parent_id` | Many2one(mail.group.message) | Parent thread message (None for root messages) |
| `group_message_child_ids` | One2many(mail.group.message) | Replies to this message |
| `email_from_normalized` | Char | Normalized sender email, stored, indexed |
| `subject` | Char | Via related → `mail_message_id.subject` |
| `body` | Html | Via related → `mail_message_id.body` |
| `author_id` | Many2one(res.partner) | Via related → `mail_message_id.author_id` |
| `email_from` | Char | Via related → `mail_message_id.email_from` |
| `attachment_ids` | Many2many | Via related → `mail_message_id.attachment_ids` |
| `create_date` | Datetime | Via inherited create_date |

### `_primary_email = 'email_from'`

L4: The `_primary_email` class attribute tells Odoo which field to use for email-based deduplication / normalization. Here it points to `email_from` (the sender), not the group address.

### Key Methods

#### `create()` — Auto-creates `mail.message`

```python
def create(self, values_list):
    """For each vals without mail_message_id:
      1. Pop mail.thread-valid fields from vals
      2. Set res_id=mail_group_id, model='mail.group'
      3. sudo().create mail.message
      4. Replace mail_message_id in vals with created ID
    Then super().create(values_list)."""
```

This means callers can pass `body`, `subject`, `author_id` directly and the message is created automatically.

#### Moderation Actions

All actions call `_assert_moderable()` first (checks `moderation_status == 'pending_moderation'`).

| Method | Action |
|---|---|
| `action_moderate_accept()` | Set status='accepted', moderator_id=self.env.uid, call `_notify_members()` |
| `action_moderate_reject()` | Set status='rejected', moderator_id=self.env.uid |
| `action_moderate_reject_with_comment(subject, body)` | Send reject email via `_moderate_send_reject_email()`, then reject |
| `action_moderate_allow()` | Create 'allow' rule in `mail.group.moderation`, then accept all same-author pending messages |
| `action_moderate_ban()` | Create 'ban' rule, reject all same-author pending messages |
| `action_moderate_ban_with_comment(...)` | Ban + send ban email |

```python
def _get_pending_same_author_same_group(self):
    """Returns mail.group.message records matching:
      - Same mail_group_id AND same email_from_normalized as self
      - moderation_status = 'pending_moderation'
    Used by allow/ban to batch-process all pending from same sender."""

def _create_moderation_rule(self, status):
    """Upserts mail.group.moderation:
      - Updates existing rule with new status
      - Creates new rule for emails not yet in moderation table."""

def _moderate_send_reject_email(self, subject, comment):
    """Creates mail.mail (sudo, auto_delete=True, state='outgoing').
    body = append_content_to_html(comment_div, message.body).
    email_from = user.email_formatted or company.catchall_formatted.
    references = mail_message_id.message_id (for threading in MUA)."""
```

---

## Model: `mail.group.moderation` — Per-Group Allow/Ban Rules

**File:** `models/mail_group_moderation.py`

A lightweight rule table for sender-based moderation.

### Fields

| Field | Type | Description |
|---|---|---|
| `email` | Char | Normalized email address, required |
| `status` | Selection | `'allow'` (always approve) / `'ban'` (always reject) |
| `mail_group_id` | Many2one(mail.group) | Required, cascade delete |

### SQL Constraints

`UNIQUE(mail_group_id, email)` — one rule per email per group.

### Validation

`create()` and `write()` both call `email_normalize()`. If the result is falsy, raises `UserError`.

---

## Wizard: `mail.group.message.reject`

**File:** `wizard/mail_group_message_reject.py`

TransientModel launched from the group message rejection action.

| Field | Type | Description |
|---|---|---|
| `mail_group_message_id` | Many2one | Required, readonly — message being rejected |
| `action` | Selection | `'reject'` or `'ban'` |
| `subject` | Char | Pre-filled to `'Re: {subject}'` |
| `body` | Html | Optional comment |
| `send_email` | Boolean (compute) | True if body is not empty |

`action_send_mail()` dispatches to the appropriate moderation method with optional comment.

---

## Controller: `portal.PortalMailGroup`

**File:** `controllers/portal.py`

### Routes (all `website=True`, sitemap)

| Route | Auth | Description |
|---|---|---|
| `GET /groups` | public | Lists all groups; for logged-in users, shows membership status; supports `email` param and `token` (manager bypass) |
| `GET /groups/<group>` | public | Paginated message archive (20 per page) |
| `GET /groups/<group>/page/<int>` | public | Same with pagination |
| `GET /groups/<group>/<message>` | public | Single message view with prev/next navigation |
| `POST /groups/<group>/<message>/get_replies` | public | JSON — lazy-load replies (5 per page) |
| `POST /group/<id>/unsubscribe_oneclick` | public (csrf=False) | RFC8058 one-click unsubscribe, checks email token |
| `POST /group/subscribe` | public | JSON — join group (auto for logged, email confirmation for public) |
| `POST /group/unsubscribe` | public | JSON — leave group (same logic) |
| `GET /group/subscribe-confirm` | public | Confirm URL from email → calls `_join_group()` |
| `GET /group/unsubscribe-confirm` | public | Confirm URL from email → calls `_leave_group()` |

### Subscription Flow (Public Users)

```
1. POST /group/subscribe → _send_subscribe_confirmation_email(email)
2. Email contains: /group/subscribe-confirm?group_id=&email=&token=
3. GET /group/subscribe-confirm → _generate_action_token(email, 'subscribe')
   token verified → _join_group(email, partner_id=None)
4. Renders confirmation_subscription template (subscribing=True)
```

### Token Verification

- `subscribe/unsubscribe` tokens: `_generate_action_token(email, action)` — HMAC with key `mail_group-email-subscription`, 3-minute expiry
- `group_access_token` (manager URL): `_generate_group_access_token()` — HMAC with key `mail_group-access-token-portal`
- One-click unsubscribe: `_generate_email_access_token(email)` — HMAC with key `mail_group-access-token-portal-email`, compared via `hmac.compare_digest` (timing-safe)

---

## L4: Mail Group Routing Flow

```
1. Incoming email → To: <alias>@<domain>
2. Mail gateway route_matches alias → creates mail.message via message_new/message_update
   (actually: message_post on the mail.group record)
3. message_post() on mail.group:
   a. Create mail.message (model='mail.group', res_id=group.id)
   b. Set reply_to to group alias reply-to address
   c. Set message_id tracking header
   d. Handle attachments
   e. Create mail.group.message (moderation_status determined by group.moderation flag)
4. Check mail.group.moderation rule for sender:
   - 'allow' → action_moderate_accept() → _notify_members()
   - 'ban'  → action_moderate_reject()
   - None + moderation=True → send notification email, leave pending
   - None + moderation=False → _notify_members() directly
5. _notify_members():
   a. Collect {email_normalized: email} for all member_ids
   b. Split into batches of 500 (configurable)
   c. For each member (not author):
      - Add List-* headers (RFC8058 unsubscribe)
      - Render group footer template
      - Create mail.mail record (auto_delete, outgoing)
6. Replies to group emails:
   - References/In-Reply-To header → mail.message.parent_id set
   - message_post() on same group finds group_message_parent_id from parent mail_message_id
   - Sets group_message_parent_id on new mail.group.message
   - Portal shows threading via group_message_parent_id / group_message_child_ids
```

---

## Security

- `mail_group.group_mail_group_manager` group: full admin access to all groups
- Moderators can manage members, send guidelines, moderate messages
- Portal access controlled by `access_mode`:
  - `'public'`: anyone can view archive
  - `'members'`: must be subscribed
  - `'groups'`: must be in `access_group_id` user list
- Bounce emails rejected for non-public aliases via `_alias_get_error()`
- One-click unsubscribe requires valid HMAC token (timing-safe compare)
- CSRF disabled on one-click unsubscribe (MUA compatibility, POST-only)

---

## Cron Jobs

| Cron | Model | Frequency | Action |
|---|---|---|---|
| `mail_group_cron_notify_moderators` | `mail.group` | Not seen in data — defined in `data/ir_cron_data.xml` | Calls `_cron_notify_moderators()` → `_notify_moderators()` per moderated group |