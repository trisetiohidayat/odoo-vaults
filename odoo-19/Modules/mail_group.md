# Mail Group (`mail_group`)

## Overview

The `mail_group` module provides a full-featured **mailing list** system built on top of Odoo's mail infrastructure. Users send emails to a group alias, and the system distributes them to all subscribed members. The module supports three privacy modes, moderation workflows, member management, per-member unsubscription tokens, and a public-facing portal archive view.

**Module ID:** `mail_group`
**Depends:** `mail`, `portal`
**Author:** Odoo S.A.
**License:** LGPL-3
**Version:** 1.1 (Odoo 19 default)

---

## Module Architecture

```
mail_group/
├── models/
│   ├── mail_group.py          # Main mailing group + membership + email routing
│   ├── mail_group_member.py   # Per-group member (email or partner)
│   ├── mail_group_message.py  # Group message + moderation actions
│   └── mail_group_moderation.py # Black/whitelist rules per email per group
├── controllers/
│   └── portal.py             # Public portal: browse groups, subscribe, archive
├── wizard/
│   └── mail_group_message_reject.py  # Reject/ban with optional email to author
├── security/
│   ├── ir.model.access.csv   # ACL per model per group
│   └── mail_group_security.xml # ir.rule records
├── data/
│   ├── ir_cron_data.xml      # Daily moderator notification cron
│   ├── res_groups.xml         # group_mail_group_manager definition
│   └── mail_templates.xml     # Subscribe/unsubscribe/guidelines/notify templates
└── views/
    ├── mail_group_views.xml
    ├── mail_group_member_views.xml
    ├── mail_group_message_views.xml
    ├── mail_group_moderation_views.xml
    ├── mail_compose_message_views.xml
    └── portal_templates.xml
```

---

## Data Models

### 1. `mail.group` — The Mailing Group

The central model. Inherits from `mail.alias.mixin` so every group gets an email alias automatically.

#### Class Definition

```python
class MailGroup(models.Model):
    _name = 'mail.group'
    _description = 'Mail Group'
    _inherit = ['mail.alias.mixin']
    _order = 'is_closed ASC, create_date DESC, id DESC'
```

#### Field Reference (L2)

| Field | Type | Default | Purpose |
|---|---|---|---|
| `name` | `Char` | required | Display name of the group, `translate=True` (translatable across languages) |
| `description` | `Text` | — | Free-text description shown on the portal listing page |
| `image_128` | `Image` | — | Group avatar/thumbnail, max 128x128px, stored as binary |
| `active` | `Boolean` | `True` | Toggle active/archived; archived groups remain accessible but cannot receive emails |
| `is_closed` | `Boolean` | `False` | Closed groups bounce all incoming emails with a styled HTML bounce message via `mail_group.email_template_mail_group_closed`; toggled via `action_close()` / `action_open()` |
| `moderation` | `Boolean` | `False` | When `True`, incoming emails enter `pending_moderation` status and are NOT distributed until a moderator accepts them |
| `moderator_ids` | `Many2many(res.users)` | — | Users who can moderate messages and manage members. Domain restricted to users in `base.group_user`. When `moderation=True` is set, `_onchange_moderation()` automatically adds the current user as moderator |
| `moderation_notify` | `Boolean` | `False` | When `True`, sends an automatic notification email to authors when their message is pending moderation (requires `moderation_notify_msg`) |
| `moderation_notify_msg` | `Html` | — | Body of the automatic moderation-notification email sent to authors |
| `moderation_guidelines` | `Boolean` | `False` | When `True`, new members receive the guidelines email automatically upon joining via `action_send_guidelines(member)` inside `_join_group()` (requires `moderation_guidelines_msg`) |
| `moderation_guidelines_msg` | `Html` | — | Content of the guidelines email sent to new members |
| `moderation_rule_ids` | `One2many` | — | Inverse of `mail.group.moderation`; lists all black/white rules for this group |
| `moderation_rule_count` | `Integer` | computed | Count of moderation rules |
| `access_mode` | `Selection` | `'public'` | Privacy mode: `'public'` (everyone), `'members'` (subscribers only), `'groups'` (selected `res.groups` only) |
| `access_group_id` | `Many2one(res.groups)` | `base.group_user` | When `access_mode == 'groups'`, specifies which `res.groups` can access the group |
| `mail_group_message_ids` | `One2many` | — | All `mail.group.message` records belonging to this group (shown as "Pending Messages" on form) |
| `mail_group_message_count` | `Integer` | computed | Total accepted + pending + rejected message count |
| `mail_group_message_last_month_count` | `Integer` | computed | Number of **accepted** messages in the last 30 days; used for group activity stats |
| `mail_group_message_moderation_count` | `Integer` | computed | Number of messages in `pending_moderation` status; shown as "To Review" stat button |
| `member_ids` | `One2many` | — | All `mail.group.member` records subscribed to this group |
| `member_partner_ids` | `Many2many(res.partner)` | computed | Resolved partners from all members; used in ir.rule for `access_mode == 'members'` |
| `member_count` | `Integer` | computed | Count of subscribed members |
| `is_member` | `Boolean` | computed | `True` if the current user (`uid`) is subscribed; uses `sudo()` to bypass ACLs in the search; computed via `_compute_is_member` with `@api.depends_context('uid')` |
| `is_moderator` | `Boolean` | computed | `True` if the current user is in `moderator_ids`; computed via `_compute_is_moderator` with `@api.depends_context('uid')` |
| `can_manage_group` | `Boolean` | computed | `True` if `is_moderator` OR `group_mail_group_manager`; controls visibility of action buttons in the UI |

#### Inherited from `mail.alias.mixin`

| Field | Source | Description |
|---|---|---|
| `alias_id` | `mail.alias.mixin` | The `mail.alias` record auto-created for this group |
| `alias_name` | alias_id | Email alias local part (e.g., `test.mail.group`) |
| `alias_domain_id` | alias_id | Email domain |
| `alias_email` | computed | Full email address (`alias_name@alias_domain`) |
| `alias_defaults` | alias_id | Defaults dict passed to `mail.message` on inbound emails |
| `alias_contact` | — | Controls who can email the alias: `'everyone'` or `'followers'`; auto-set via `_onchange_access_mode()` — set to `'everyone'` when `access_mode == 'public'`, otherwise `'followers'` |

#### Constraints

| Constraint | Error Message | Description |
|---|---|---|
| `@api.constrains('moderator_ids')` | `'Moderators must have an email address.'` | Every user in `moderator_ids` must have a non-empty email on their `res.users` record |
| `@api.constrains('moderation_notify', 'moderation_notify_msg')` | `'The notification message is missing.'` | If `moderation_notify` is `True`, the notification message must be non-empty |
| `@api.constrains('moderation_guidelines', 'moderation_guidelines_msg')` | `'The guidelines description is missing.'` | If `moderation_guidelines` is `True`, the guidelines message must be non-empty |
| `@api.constrains('moderator_ids', 'moderation')` | `'Moderated group must have moderators.'` | A group with `moderation == True` must have at least one moderator |
| `@api.constrains('access_mode', 'access_group_id')` | `'The "Authorized Group" is missing.'` | When `access_mode == 'groups'`, `access_group_id` must be set |

#### Onchange Methods

| Method | Trigger | Behavior |
|---|---|---|
| `_onchange_access_mode()` | `access_mode` changed | Sets `alias_contact` to `'everyone'` for `'public'`, else `'followers'` |
| `_onchange_moderation()` | `moderation` changed | If `moderation` becomes `True` and current user is not yet a moderator, adds current user to `moderator_ids` |

#### Computed Fields — Implementation Details (L3)

**`_compute_mail_group_message_last_month_count`** — Uses `_read_group` with a `relativedelta.relativedelta(months=1)` lookback, filtered on `moderation_status == 'accepted'`. Returns a dictionary keyed by `mail_group.id` for O(1) lookup in the loop.

**`_compute_mail_group_message_count`** — Uses `_read_group` with only `mail_group_id` as the groupby and `['__count']` aggregate, then maps results into a dict. Avoids individual `search_count` calls.

**`_compute_mail_group_message_moderation_count`** — Same pattern as above, adding `moderation_status == 'pending_moderation'` to the domain.

**`_compute_member_count`** — Simple `len(group.member_ids)`, no batch optimization. Note: in recordsets with many groups, this triggers N+1 reads of the One2many. Not stored, so recomputes on every access.

**`_compute_is_member`** — Uses `sudo()` on the member search to bypass ACLs. Returns a dict mapping group IDs to boolean membership status. The `self.env.user._is_public()` guard ensures public users are never marked as members.

**`_compute_member_partner_ids`** — Directly assigns `group.member_ids.partner_id` (a One2many-derived Many2many). Triggers a read of all member partner records.

**`_search_member_partner_ids`** — Custom search method enabling `partner_id` to be searched on `mail.group` via the One2many inverse. Uses `sudo()` on the inner member search to avoid permission errors when non-privileged users search.

**`_compute_is_moderator`** — Checks `self.env.user.id in group.moderator_ids.ids`. The `@api.depends('moderator_ids')` is redundant with `@api.depends_context('uid')`; the former recomputes on moderator changes, the latter on user change.

**`_compute_can_manage_group`** — Evaluates `self.env.user.has_group('mail_group.group_mail_group_manager') or self.env.su`. The `su` flag means superuser mode bypasses this check entirely and always returns `True`.

---

### 2. `mail.group.member` — Group Member

Represents a subscription. A member is identified by either a `res.partner` (logged-in user) or a raw email address (public user). The model deliberately allows multiple members with the same email but no partner (useful for testing, migrations, or external systems that subscribe the same address multiple times with different metadata).

#### Class Definition

```python
class MailGroupMember(models.Model):
    _name = 'mail.group.member'
    _description = 'Mailing List Member'
    _rec_name = 'email'
```

#### Field Reference (L2)

| Field | Type | Default | Description |
|---|---|---|---|
| `email` | `Char` | required on create | Email address of the member. `compute='_compute_email'` with `readonly=False, store=True` — writable when no partner is linked, auto-synced from `partner_id.email` when a partner exists |
| `email_normalized` | `Char` | computed, stored | Normalized form using `email_normalize()` from `odoo.tools.mail`; `index=True` for fast lookups in `_find_members()` |
| `mail_group_id` | `Many2one(mail.group)` | required | The mailing group this member belongs to; `ondelete='cascade'` — deleting the group removes all member records |
| `partner_id` | `Many2one(res.partner)` | — | Optional link to a `res.partner`; when set, `email` is kept in sync via `_compute_email` |

#### Constraint

```python
_unique_partner = models.Constraint(
    'UNIQUE(partner_id, mail_group_id)',
    'This partner is already subscribed to the group',
)
```

Enforced at the database level (SQL constraint). The constraint is on `partner_id` only — not on email — because the same email can have multiple partners across different Odoo instances, test data, etc. This means the same **partner** cannot be subscribed twice to the same group. However, multiple members with the same email but no partner can exist simultaneously.

#### Computed Fields — Implementation Details (L3)

**`_compute_email`** — If `partner_id` is set, mirrors `partner_id.email`. If no partner and no existing email, sets `False`. The `email` field is free to edit only when there is no linked partner.

**`_compute_email_normalized`** — Calls `email_normalize(moderation.email)` — note the variable name `moderation` is a holdover; it refers to the member record itself. Uses `email_normalize` which strips whitespace, lowercases the domain, handles `+` addressing, strips display names, and more.

---

### 3. `mail.group.message` — Group Message

Encapsulates an email received by the group. Does **not** inherit from `mail.message` via `_inherits` (unlike Odoo 18 and earlier) — this was changed in Odoo 19 to avoid ORM cache penalties. Instead, fields are mirrored via `related='mail_message_id.field_name'` with `readonly=False`. This means the model has its own table (`mail_group_message`), separate from `mail_message`.

#### Class Definition

```python
class MailGroupMessage(models.Model):
    _name = 'mail.group.message'
    _description = 'Mailing List Message'
    _rec_name = 'subject'
    _order = 'create_date DESC'
    _primary_email = 'email_from'
```

#### Field Reference (L2)

| Field | Type | Default | Description |
|---|---|---|---|
| `mail_group_id` | `Many2one(mail.group)` | required | Which group this message belongs to; `ondelete='cascade'` |
| `mail_message_id` | `Many2one(mail.message)` | required | The underlying `mail.message` record; `copy=False`, `index=True` |
| `subject` | `Char` (related) | readonly=False | Mirrors `mail_message_id.subject` |
| `email_from` | `Char` (related) | readonly=False | Mirrors `mail_message_id.email_from` — the raw From header, including display name |
| `email_from_normalized` | `Char` | computed, stored | Normalized version of `email_from`; used for moderation lookups |
| `author_id` | `Many2one` (related) | readonly=False | Mirrors `mail_message_id.author_id` (the partner matched from email_from via `_primary_email`) |
| `body` | `Html` (related) | readonly=False | Mirrors `mail_message_id.body` |
| `attachment_ids` | `Many2many` (related) | readonly=False | Mirrors `mail_message_id.attachment_ids` |
| `moderation_status` | `Selection` | `'pending_moderation'` | `'pending_moderation'` / `'accepted'` / `'rejected'`; `index=True`, `copy=False` |
| `moderator_id` | `Many2one(res.users)` | — | The moderator who last acted on this message (accept/reject/ban) |
| `author_moderation` | `Selection` | computed | `'ban'` / `'allow'` — resolved by searching `mail.group.moderation` for the author's normalized email; drives badge display in the message form view |
| `is_group_moderated` | `Boolean` | related | Mirrors `mail_group_id.moderation` |
| `group_message_parent_id` | `Many2one` | — | Parent `mail.group.message` in a thread; enables reply threading; `store=True, index=True` |
| `group_message_child_ids` | `One2many` | — | Inverse of `group_message_parent_id`; all direct replies to this message |
| `create_date` | `Datetime` | — | Set to the actual posting time for portal archive ordering |

#### Constraint

```python
@api.constrains('mail_message_id')
def _constrains_mail_message_id(self):
    # Ensures mail_message_id.model == 'mail.group'
    # Ensures mail_message_id.res_id == mail_group_id.id
```

Prevents linking a `mail.group.message` to a `mail.message` that belongs to a different model or a different group record. This is critical because the `_inherits`-less design means the parent `mail.message` could theoretically be associated with any model.

#### `create()` — Custom Message Creation Flow

The `mail.message` is created first (via the mail gateway), then the mail gateway calls `message_post()` on the group. Inside `message_post()`, the method:

1. Creates a `mail.message` via `_message_create([values])`
2. Searches for the parent `mail.group.message` by matching `mail_message_id` if `mail_message_id.parent_id` exists
3. Sets `moderation_status = 'accepted'` if `not group.moderation`, else `'pending_moderation'`
4. Looks up a `mail.group.moderation` rule for the sender's normalized email:
   - If rule exists with `status == 'allow'`: immediately calls `action_moderate_accept()`
   - If rule exists with `status == 'ban'`: immediately calls `action_moderate_reject()`
   - If no rule and `moderation_notify`: sends a notification to the author

This means messages from whitelisted senders bypass the moderation queue entirely, and messages from banned senders are immediately rejected without moderator intervention.

#### `copy_data()` — Message Duplication

Copies the underlying `mail.message` as well, so duplicates are independent messages. This matters because `mail_message_id` has `copy=False`, so each `mail.group.message` copy must also copy its associated `mail.message`.

#### Moderation Actions — Full Reference (L3 Escalation)

| Action Method | Behavior |
|---|---|
| `action_moderate_accept()` | Sets `moderation_status = 'accepted'`, `moderator_id = uid`. Calls `group._notify_members(message)` to distribute to all members |
| `action_moderate_reject()` | Sets `moderation_status = 'rejected'`, `moderator_id = uid`. No distribution |
| `action_moderate_reject_with_comment(subject, comment)` | Calls `_moderate_send_reject_email()` then `action_moderate_reject()` |
| `action_moderate_allow()` | Calls `_create_moderation_rule('allow')` to whitelist the author, then finds and accepts all pending messages from the same author in the same group via `_get_pending_same_author_same_group()` |
| `action_moderate_ban()` | Calls `_create_moderation_rule('ban')` to blacklist the author, then rejects all pending messages from the same author |
| `action_moderate_ban_with_comment(subject, comment)` | Same as ban, plus sends a rejection email to the author via `_moderate_send_reject_email()` |

**`_get_pending_same_author_same_group()`** — Uses `Domain.OR()` to build a domain matching all (group, email) pairs from the current recordset. This enables batch moderation: a moderator can select multiple messages from the same author and whitelist/ban them all at once. The `Domain` class is used instead of raw Python lists for cleaner AND/OR composition.

**`_create_moderation_rule(status)`** — Performs an upsert: existing rules for the same (email, group) pair are updated to the new status; new rules are created for emails not yet in the table. Uses `email_normalize()` on every message's `email_from`. Deduplicates by `(email_normalized, mail_group_id)` using a Python set before calling `create()`. The `status` parameter is validated: only `'ban'` and `'allow'` are accepted; any other value raises `ValueError`.

**`_moderate_send_reject_email(subject, comment)`** — Appends the rejection comment to the original message body using `append_content_to_html()`, replaces local links via `_replace_local_links()`, and sends a `mail.mail` (via `sudo()`) to the message author. Sets `auto_delete=True` so the mail is deleted after sending.

**`_assert_moderable()`** — Guard method used by all moderation actions. Raises `UserError` if any message in the set does not have `moderation_status == 'pending_moderation'`. This prevents moderators from re-accepting or re-rejecting already-processed messages.

---

### 4. `mail.group.moderation` — Moderation Rule

A per-group blacklist/whitelist entry. One record per `(mail_group_id, email_normalized)` pair. Email addresses are normalized on create and write, ensuring the SQL unique constraint is always satisfied regardless of input format.

#### Class Definition

```python
class MailGroupModeration(models.Model):
    _name = 'mail.group.moderation'
    _description = 'Mailing List black/white list'
```

#### Field Reference (L2)

| Field | Type | Default | Description |
|---|---|---|---|
| `email` | `Char` | required | Normalized email address (normalized on create/write via `email_normalize()`) |
| `status` | `Selection` | `'ban'` | `'allow'` (always accept) or `'ban'` (always reject) |
| `mail_group_id` | `Many2one(mail.group)` | required | Which group this rule applies to; `ondelete='cascade'` |

#### Constraint

```python
_mail_group_email_uniq = models.Constraint(
    'UNIQUE(mail_group_id, email)',
    'You can create only one rule for a given email address in a group.',
)
```

Enforced at the database level. This is why normalization on create/write is critical — it prevents bypassing the rule by changing email casing, adding whitespace, or wrapping in display names.

#### `create()` / `write()` — Email Normalization

Both methods call `email_normalize(values['email'])` before writing to the database. If normalization fails (returns `False`/`None`), a `UserError` is raised: `'Invalid email address "%s"'`. This ensures the constraint is always satisfied regardless of how the email is entered (with display name, uppercase, whitespace, `+` tag, etc.).

---

### 5. `mail.group.message.reject` — Reject Wizard (Transient Model)

A wizard for rejecting/ban-ning a message with an optional comment to send to the author. This is a transient model (not stored in a persistent table); it exists only for the duration of the wizard session.

#### Class Definition

```python
class MailGroupMessageReject(models.TransientModel):
    _name = 'mail.group.message.reject'
    _description = 'Reject Group Message'
```

#### Field Reference (L2)

| Field | Type | Default | Description |
|---|---|---|---|
| `mail_group_message_id` | `Many2one` | required, readonly | The message being rejected/ban-ned |
| `action` | `Selection` | required | `'reject'` or `'ban'` |
| `subject` | `Char` | computed | Default `"Re: {message.subject}"` via `_compute_subject`; stored, readonly=False |
| `body` | `Html` | `''` | Rejection/ban comment; `sanitize_style=True` |
| `email_from_normalized` | `Char` | related | Display-only; shows the message author's email in the wizard form |
| `send_email` | `Boolean` | computed | `True` if `body` is non-empty HTML (not just whitespace); computed in `_compute_send_email` |

#### `action_send_mail()` — Dispatch Logic

```python
def action_send_mail(self):
    # reject + email → reject_with_comment
    # reject + no email → reject
    # ban + email → ban_with_comment
    # ban + no email → ban
```

The wizard's four buttons (`"Reject Silently"` / `"Send & Reject"` / `"Ban"` / `"Send & Ban"`) are conditionally shown via `invisible` modifiers based on `action` and `send_email`. This means the wizard form is a shared UI for both reject and ban workflows, differentiated only by the action passed from the calling context.

---

## Key Workflows

### Email Posting Flow

```
Incoming email → mail gateway → MailGroup.message_post()
    ├── Create mail.message (body sanitized via _clean_email_body)
    ├── Find parent mail.group.message (via mail_message_id.parent_id)
    ├── Create mail.group.message
    │   ├── moderation_status = 'accepted' if not moderated
    │   └── moderation_status = 'pending_moderation' if moderated
    ├── Check mail.group.moderation rule for sender's email
    │   ├── allow rule  → action_moderate_accept() → _notify_members()
    │   ├── ban rule    → action_moderate_reject()
    │   └── no rule     → if moderation_notify: send notification email
    └── return mail.message
```

### `_clean_email_body()` — HTML Sanitization

Strips the `o_mg_message_footer` div from incoming HTML before storing, using `lxml.html.fromstring` to parse and `etree.tostring` to reserialize. The footer contains per-recipient unsubscribe links and is stripped from the archived message body (it is re-added per-recipient in `_notify_members()`). This is necessary because the footer is member-specific and cannot be stored once for all.

### `_notify_members()` — Batch Email Distribution

For each accepted message, the group distributes to all members in batches of `mail.session.batch.size` (default: 500, configurable via `ir.config_parameter`). For each batch:

1. Builds a dict of `{email_normalized: email_raw}` to avoid sending duplicate emails (the same address can have multiple member records with different partners)
2. Filters out the message author from recipients (lines 433-435)
3. Generates per-recipient SMTP headers:
   - `List-Archive`: archive URL for the group
   - `List-Subscribe`: subscription URL with the recipient's email
   - `List-Unsubscribe`: one-click unsubscribe URL
   - `List-Unsubscribe-Post: One-Click` (RFC 8058 compliance)
   - `List-Id`: the group's alias email
   - `List-Post`: `mailto:` link to the group alias
   - `X-Forge-To`: sets the To: header to the group name and alias
   - `In-Reply-To`: the original message's Message-ID for threading
   - `X-Auto-Response-Suppress: OOF`: suppresses out-of-office replies from MS Exchange and similar servers
4. Renders the group footer (`mail_group.mail_group_footer`) with unsubscribe and group URLs
5. Appends footer to the message body
6. Creates `mail.mail` records in bulk via `sudo()` (required for the system to send from the group's email address)
7. The `auto_delete=True` flag means each mail is deleted from `mail_mail` table after successful send

### Subscription Confirmation Flow (RFC 8058 Compliant)

For **public (non-logged-in) users**, subscribe/unsubscribe requires email confirmation:

```
Public user → POST /group/subscribe
    → _group_subscription_get_group() [validates token if provided]
    → _send_subscribe_confirmation_email() [sends email with token URL]
    → returns 'email_sent'

User clicks confirm link → GET /group/subscribe-confirm
    → _group_subscription_confirm_get_group() [validates HMAC token]
    → _join_group(email, partner_id=None)
    → renders confirmation page

One-click unsubscribe (RFC 8058):
    → POST /group/{id}/unsubscribe_oneclick
    → Validates HMAC email access token
    → Calls _leave_group(email, all_members=True)
    → Returns HTTP 200
```

### Token Generation

All tokens are HMAC-SHA256 signatures using `tools.hmac(env(su=True), 'mail_group-email-subscription', data)` where `data` is a tuple. Three token variants:

| Token | HMAC Message | Purpose |
|---|---|---|
| Group access token | `(group_id,)` | Validates user has the subscription URL from the portal |
| Action token | `(group_id, email_normalized, action)` | Validates subscribe/unsubscribe confirmation links |
| Email access token | `(group_id, email_normalized)` | Validates per-recipient unsubscribe URLs; email is part of the hash to prevent cross-user unsubscription |

### `_routing_check_route()` — Closed Group Bounce

When the mail gateway evaluates routing for an incoming email, `_routing_check_route()` is called. If the group is closed (`is_closed == True`), it renders the `mail_group.email_template_mail_group_closed` template and calls `_routing_create_bounce_email()` to send a styled HTML bounce notification back to the sender. This replaces older plain-text bounce responses.

---

## Security Architecture

### Access Control Lists (`ir.model.access.csv`)

| Model | Group | Read | Write | Create | Unlink |
|---|---|---|---|---|---|
| `mail.group` | `base.group_public` | 1 | 0 | 0 | 0 |
| `mail.group` | `base.group_portal` | 1 | 0 | 0 | 0 |
| `mail.group` | `base.group_user` | 1 | 1 | 1 | 1 |
| `mail.group.member` | `base.group_user` | 1 | 1 | 1 | 1 |
| `mail.group.message` | `base.group_public` | 1 | 0 | 0 | 0 |
| `mail.group.message` | `base.group_portal` | 1 | 0 | 0 | 0 |
| `mail.group.message` | `base.group_user` | 1 | 1 | 1 | 1 |
| `mail.group.moderation` | `base.group_user` | 1 | 1 | 1 | 1 |
| `mail.group.message.reject` | `base.group_user` | 1 | 1 | 1 | 1 |

### Record Rules (`mail_group_security.xml`)

#### `mail_group_rule_read_all`
Applies to: `base.group_user`, `base.group_portal`, `base.group_public`
```python
domain_force = [
    '|', '|', '|',
        ('moderator_ids', 'in', user.id),           # Moderators see all groups
        ('access_mode', '=', 'public'),               # Everyone sees public groups
        ('access_mode', '=', 'groups') & ('access_group_id', 'in', user.all_group_ids.ids),
        ('access_mode', '=', 'members') & ('member_partner_ids', 'in', [user.partner_id.id]),
]
# Perms: read=True, write=False, create=False, unlink=False
```

#### `mail_group_rule_write_all`
Applies to: `base.group_user` (all employees)
```python
domain_force = [('moderator_ids', 'in', user.id)]
# Perms: read=False, write=True, unlink=True, create=False
```

#### `mail_group_rule_administrator`
Applies to: `mail_group.group_mail_group_manager`
```python
domain_force = [(1, '=', 1)]  # All records unconditionally
# Full access: read, write, create, unlink
```

#### `mail_group_message_rule_public`
Applies to: `base.group_public`, `base.group_portal`
```python
# Only accepted messages accessible; plus access_mode checks
# Uses moderation_status == 'accepted' AND access_mode logic
# Full CRUD (create needed for message ingestion via gateway)
```

#### `mail_group_message_rule_user`
Applies to: `base.group_user`
```python
# Accepted messages OR (moderation_status != 'accepted' AND user is moderator)
# Same access_mode checks as mail.group rules
```

#### `mail_group_message_rule_administrator`
Applies to: `mail_group.group_mail_group_manager`
```python
domain_force = [(1, '=', 1)]  # All messages
```

#### `mail_group_member_rule_user`
Applies to: `base.group_user`
```python
domain_force = [('mail_group_id.moderator_ids', 'in', user.id)]
# Only moderators can see/manipulate member lists
```

#### `mail_group_member_rule_administrator`
Applies to: `mail_group.group_mail_group_manager`
```python
domain_force = [(1, '=', 1)]  # All members
```

#### `mail_group_moderation_rule_user`
Applies to: `base.group_user`
```python
domain_force = [('mail_group_id.moderator_ids', 'in', user.id)]
```

#### `mail_group_moderation_rule_administrator`
Applies to: `mail_group.group_mail_group_manager`
```python
domain_force = [(1, '=', 1)]
```

### Group Hierarchy

```xml
<!-- res_groups.xml -->
<record id="group_mail_group_manager" model="res.groups">
    <field name="name">Mail Group Administrator</field>
</record>
<record id="base.group_system" model="res.groups">
    <field name="implied_ids" eval="[(4, ref('mail_group.group_mail_group_manager'))]"/>
</record>
```

This creates a `Mail Group Administrator` group that is implied by `base.group_system`. All internal users with system administrator rights automatically get full mail group management access.

---

## Portal Controller (`controllers/portal.py`)

### Routes

| Route | Type | Auth | Description |
|---|---|---|---|
| `/groups` | `http` | `public` | Group listing page with subscribe/leave buttons |
| `/groups/{group}` | `http` | `public` | Group message archive (thread or flat mode, paginated) |
| `/groups/{group}/page/{page}` | `http` | `public` | Paginated archive |
| `/groups/{group}/{message}` | `http` | `public` | Single message view with next/prev navigation |
| `/groups/{group}/{message}/get_replies` | `jsonrpc` | `public` | AJAX load more replies |
| `/group/{id}/unsubscribe_oneclick` | `http` POST | `public` | RFC 8058 one-click unsubscribe |
| `/group/subscribe` | `jsonrpc` | `public` | Subscribe action (logged-in auto-joins; public sends email) |
| `/group/unsubscribe` | `jsonrpc` | `public` | Unsubscribe action |
| `/group/subscribe-confirm` | `http` | `public` | Confirmation page for subscribe |
| `/group/unsubscribe-confirm` | `http` | `public` | Confirmation page for unsubscribe |

### `_get_archives()` — Time-Based Grouping

Uses `_read_group` with `groupby=['create_date:month']` to group messages by month, then counts threads (messages without a parent) per month. Returns:
- `threads_count`: total number of top-level threads
- `threads_time_data`: list of `{date, date_begin, date_end, messages_count}` per month

The `babel.dates.format_datetime` call localizes month labels using `get_lang(request.env).code`.

### Token Validation in Portal

Two token schemes, each with distinct threat models:

1. **Group access token** (`_generate_group_access_token`): HMAC of group ID alone. Validates that the user has the URL (prevents guessing group IDs for subscription links on the portal listing page).

2. **Email access token** (`_generate_email_access_token`): HMAC of `(group_id, email_normalized)`. Used in per-recipient unsubscribe URLs embedded in each delivered email. The HMAC includes the email address, so an attacker cannot unsubscribe other people by changing the email parameter.

---

## Cron Jobs

| Cron | Model | Schedule | Description |
|---|---|---|---|
| `Mail List: Notify group moderators` | `mail.group` | Daily (`interval_type: days`, `priority=1000`) | Runs `_cron_notify_moderators()` which finds all groups with pending moderation items and sends `mail.message` (inbox notification) to each moderator via `message_notify()` |

The low `priority=1000` means it runs after other system crons.

---

## Odoo 18 to Odoo 19 Changes (L4)

### 1. Removal of `_inherits` from `mail.group.message`

In Odoo 18 and earlier, `mail.group.message` used `_inherits = {'mail.message': 'mail_message_id'}`, meaning it was a true child table with delegated fields. In Odoo 19, the model no longer uses `_inherits`. Instead, fields are mirrored via `related='mail_message_id.field_name'` with `readonly=False`. The comment in the code explains this was done to avoid "the ORM [making] one more SQL query to be able to update the `<mail.group.message>` cache." With `_inherits`, accessing a field on `mail.group.message` that exists on `mail.message` requires an additional JOIN to fetch the parent record's data into the cache. By dropping `_inherits`, the two tables are fully independent, and accessing `author_id` or `body` on a `mail.group.message` no longer incurs that penalty.

### 2. `_clean_email_body()` Addition

The footer-stripping logic (`o_mg_message_footer` div removal) was added in Odoo 19. Previously, this was handled differently or the footer was not stripped from stored messages.

### 3. `Domain` Class Usage

`Domain.AND()`, `Domain.OR()`, and `Domain()` are used throughout for domain expression composition, replacing raw Python list concatenation. This is a broader Odoo 19 pattern that provides better readability and potentially better performance for complex domain trees.

### 4. `batch_size` Parameterization

The `mail.session.batch.size` `ir.config_parameter` allows overriding the hardcoded `GROUP_SEND_BATCH_SIZE = 500` constant. This lets administrators tune performance based on their SMTP server's capacity without code changes.

### 5. Bounce Email Uses QWeb Template

The closed-group bounce mechanism now renders `mail_group.email_template_mail_group_closed` (a QWeb template) instead of a plain-text string. This allows styled HTML bounce messages.

### 6. `_primary_email = 'email_from'`

Declared on the `mail.group.message` model. This supports Odoo's new "author email matching" system for partner resolution on incoming emails — when a new `mail.message` is created with an email_from, Odoo can look up the matching `res.partner` based on this field.

### 7. `message_notify()` for Moderator Notifications

Moderator notifications now use `message_notify()` instead of `message_post()`. This delivers to the moderator's Odoo inbox rather than the document's chatter thread on the group record.

### 8. Database Schema Impact of `_inherits` Removal

| Aspect | Odoo 18 (with `_inherits`) | Odoo 19 (without `_inherits`) |
|--------|---------------------------|------------------------------|
| Table structure | `mail_group_message` + `mail_message` (joined) | `mail_group_message` standalone + `mail_message` reference |
| ORM reads | 2 queries per field access (join through `_inherits`) | 1 query (direct field on own table via `related=`) |
| Write behavior | Writes propagate to `mail_message` table | Writes target own table; `related=` fields have `readonly=False` |
| `copy()` | Copies `mail_message` via `_inherits` | Must explicitly copy `mail_message_id` in `copy_data()` |
| `mail_message_id` constraint | Implicit via `_inherits` | Explicit `@api.constrains` added |

### 9. `all_members` Parameter in `_leave_group()`

Added in Odoo 19: when unsubscribing via RFC 8058 one-click, `all_members=True` is passed so that all member records with the same email are removed (not just one). This handles the case where the same email has multiple member records.

---

## Performance Considerations (L4)

### N+1 Query Risks

1. **`_notify_members()`** — Iterates over `self.member_ids` and calls `email_normalize(member.email)` for each member. The `member_ids` are pre-fetched via the One2many, so this is one query. However, the per-recipient footer rendering (`ir.qweb._render('mail_group.mail_group_footer', ...)`) happens inside the loop, meaning QWeb rendering is called once per recipient. For large member lists, this is the primary performance bottleneck.

2. **`_compute_author_moderation`** — Calls `self.env['mail.group.moderation'].search()` with all group IDs from `self`, then builds a dict from the result. This is one query for all messages being computed. The dict lookup is O(1) per message.

3. **`_get_pending_same_author_same_group()`** — Uses `Domain.OR()` over all message (group, email) pairs. If moderating 100 messages from 100 different authors in 100 different groups, this generates an OR domain with 100 clauses. The ORM converts this to a SQL `IN` clause, which is efficient.

4. **`_find_members()`** — Always calls `sudo()` and performs a search with ordering. The ordering `partner_id ASC/DESC` ensures the "best match" (member with matching partner_id first) is returned.

### Batch Sizing

The `split_every` utility from `odoo.tools` splits an iterable into chunks of the specified size. Default 500 means a group with 10,000 members generates 20 `mail.mail` CREATE operations. The `auto_delete=True` flag means each mail is deleted from the `mail_mail` table after successful send, keeping the table small.

### Indexes

| Field | Type | Purpose |
|---|---|---|
| `mail.group.member.email_normalized` | B-tree index | Fast lookup in `_find_members()` |
| `mail.group.member.mail_group_id` | B-tree index | Fast cascade delete; member lookup by group |
| `mail.group.moderation.mail_group_id` | B-tree index | Fast rule lookup on email ingestion |
| `mail.group.message.mail_group_id` | B-tree index | Message listing per group |
| `mail.group.message.mail_message_id` | B-tree index | Cross-reference to mail.message |
| `mail.group.message.group_message_parent_id` | B-tree index | Thread reply hierarchy |
| `mail.group.message.moderation_status` | B-tree index | Fast pending-moderation queue filtering |

### Unsubscribe Token Computation

Each delivered email has a List-Unsubscribe URL that is unique per recipient. Generating the HMAC token requires `su=True` context to access the secret. Since the token function is deterministic for `(group_id, email)`, it could be optimized by generating tokens outside the loop if the function call overhead is significant. The current implementation recomputes the HMAC for each member even though the group is the same — but HMAC-SHA256 is fast enough that this is not a practical bottleneck.

### Scalability by Group Size

| Group Size | Sync Round Trip | Primary Bottleneck |
|---|---|---|
| Small (<500 members) | < 1 second | SMTP relay speed |
| Medium (500-5000) | 1-10 seconds | Batch rendering + SMTP queuing |
| Large (5000-50000) | 10-60 seconds | QWeb rendering per recipient |
| Very large (>50000) | Minutes | Consider splitting into multiple groups |

### `_inherits` Removal — Performance Impact (L4)

The decision to remove `_inherits` from `mail.group.message` in Odoo 19 deserves deeper analysis:

**Before (with `_inherits`):**
When Odoo's ORM accesses a delegated field on a `_inherits` child model, it performs a SQL JOIN to the parent `mail_message` table. For `mail.group.message` which may have hundreds of thousands of records in active mailing lists, every read of `author_id`, `body`, or `subject` triggered this JOIN. The ORM also maintains a separate cache for the parent table.

**After (without `_inherits`):**
The `mail.group.message` table stores its own copies of these fields (via `related=` with `readonly=False`). Writes update the `mail_group_message` table directly. The `mail_message_id` field maintains the cross-reference. For read operations, no JOIN is needed — the fields are on the local table. For write operations, both tables must be updated: the `mail_message` (by the mail gateway) and the `mail_group_message` fields (by the related field mechanism).

The trade-off is storage duplication: subject, body, author_id, email_from, and attachments now exist in both `mail_message` and `mail_group_message` tables. For high-volume mailing lists, this is a deliberate space-for-speed exchange.

---

## Security Concerns (L4)

### Token Security

All subscription/unsubscription tokens are HMAC-SHA256 signatures computed with `tools.hmac(self.env(su=True), ...)`. The `su=True` means it uses the system-wide Odoo secret key (from `ir.config_parameter` `database.secret`), not a module-specific key. The secret is shared with other Odoo subsystems, but the HMAC includes the action type and email as part of the message tuple, providing namespace isolation.

### Email Enumeration Risk

The `group_unsubscribe` and `group_subscribe` endpoints return `'is_already_member'` or `'is_not_member'` as JSON-RPC responses. An attacker can enumerate valid group IDs by observing these responses. However, if a valid token is provided (e.g., from a previously delivered email), the access rule is bypassed — this is by design for the unsubscribe URL. Without a token, the endpoint calls `group.check_access('read')`, which enforces the record rule.

### Moderation Bypass via Email Normalization

The moderation constraint is on `email_normalized`, but the initial rule lookup uses `email_normalize()`. If the normalization library has a bug, an attacker could potentially bypass ban rules. The constraint on `mail.group.moderation` stores only the normalized form, preventing duplicate rules for the same logical email.

### CSRF on Portal Endpoints

The portal controller uses `csrf=True` for all `type='http'` routes except `/group/{id}/unsubscribe_oneclick` and `/group/subscribe` (which use `csrf=False`). The unsubscribe endpoint disables CSRF because it must be callable by mail user agents via RFC 8058 one-click unsubscribe POST commands, which do not carry CSRF tokens. The `POST` method requirement provides protection against CSRF for browser-based attacks.

### Mass Mailing Risk

There is no rate limiting on message posting via the email gateway. A malicious moderator could use `message_post()` to send a very large number of emails. The `auto_delete=True` on outgoing `mail.mail` records means individual mail records are deleted after sending, but the SMTP relay may still queue large volumes. For high-volume deployments, consider implementing rate limiting at the SMTP level or adding a cap on `_notify_members()` for very large member lists.

### Moderator Elevation Risk

The `mail_group_rule_write_all` record rule grants write access to all group members (via `moderator_ids` domain). A user who is a moderator for **any** group can write to all fields of **any** group message in the system (including messages from other groups). This is a known design trade-off — moderation must be able to act on all messages visible to them. Consider carefully which users are granted moderator rights.

### Attachment Security

Attachments are mirrored from `mail.message` via `related=`. When a message is distributed, attachments are sent along. Odoo does not scan attachments for malicious content at the mail_group level — this is delegated to the `mail` module's attachment handling and any configured antivirus scanning at the SMTP level.

---

## Tags

`#odoo`, `#odoo19`, `#modules`, `#mail`, `#mail_group`, `#mailing_list`, `#moderation`, `#security`, `#portal`
