---
uid: im_livechat
title: Live Chat
type: module
category: Website/Live Chat
version: 19.0.1.0.0
created: 2026-04-06
modified: 2026-04-11
dependencies:
  - mail
  - rating
  - digest
  - utm
  - bus
  - website
author: Odoo S.A.
license: LGPL-3
summary: Real-time chat with website visitors via instant messaging widgets
lifecycle:
  installable: true
  application: true
---

# Live Chat (im_livechat)

## Overview

The **im_livechat** module enables real-time chat communication between website visitors and support operators. It provides a complete live chat infrastructure including:

- Configurable chat widgets embeddable on any website page via external JavaScript loader
- Operator management with availability rules, session limits, and in-call blocking
- Intelligent visitor-to-operator routing based on language, expertise, country, and load balancing
- AI-powered chatbot scripting for automated responses with conditional branching
- Session history tracking, analytics, reporting fields, and customer satisfaction ratings
- "Need help" escalation workflow where agents can request assistance from colleagues
- Conversation tagging for classification
- Real-time WebSocket (bus) notifications for typing indicators, message delivery, session end

Live chat sessions are implemented as specialized `discuss.channel` records with `channel_type = 'livechat'`, integrating deeply with the Odoo messaging system. Anonymous visitors are represented by `mail.guest` records persisted via browser cookie.

## Module Architecture

### Directory Structure

```
im_livechat/
├── __manifest__.py          # Dependencies: mail, rating, digest, utm; asset bundles
├── models/
│   ├── __init__.py
│   ├── im_livechat_channel.py        # im_livechat.channel + im_livechat.channel.rule
│   ├── im_livechat_channel_member_history.py  # Reporting/history base
│   ├── im_livechat_conversation_tag.py
│   ├── im_livechat_expertise.py
│   ├── discuss_channel.py            # discuss.channel livechat extension
│   ├── discuss_channel_member.py     # discuss.channel.member livechat extension
│   ├── discuss_channel_rtc_session.py
│   ├── discuss_call_history.py
│   ├── chatbot_script.py             # chatbot.script
│   ├── chatbot_script_step.py        # chatbot.script.step
│   ├── chatbot_script_answer.py      # chatbot.script.answer
│   ├── chatbot_message.py           # chatbot.message (bot message ↔ mail.message link)
│   ├── mail_message.py              # mail.message livechat extension
│   ├── res_partner.py              # res.partner livechat extensions
│   ├── res_users.py                # res.users livechat extensions
│   ├── res_users_settings.py       # res.users.settings livechat extensions
│   ├── res_groups.py               # res.groups livechat extension
│   ├── rating_rating.py
│   ├── digest.py
│   ├── ir_binary.py
│   └── ir_websocket.py
├── controllers/
│   ├── main.py        # get_session, feedback, history, transcript, visitor_leave_session
│   ├── channel.py    # Note/status/tags/expertise update endpoints
│   ├── chatbot.py    # chatbot_restart, chatbot_trigger_step, validate_email
│   ├── rtc.py        # WebRTC session handling
│   ├── thread.py     # Thread message handling
│   ├── attachment.py
│   ├── webclient.py
│   ├── cors.py       # Cross-origin support for external websites
├── views/            # Form, tree, kanban, search views for all models
├── security/
│   ├── im_livechat_channel_security.xml  # Groups + ir.rule
│   └── ir.model.access.csv
├── data/
│   ├── im_livechat_channel_data.xml   # Default channel demo data
│   ├── im_livechat_chatbot_data.xml   # Default chatbot scripts
│   ├── mail_templates.xml
│   └── digest_data.xml
├── report/           # PDF transcript report
└── static/
    ├── src/embed/   # External website widget (external/, cors/, common/)
    ├── src/core/    # Shared livechat JS (public_web/, web/)
    ├── src/views/   # Backend livechat views (Kanban, list, form)
    └── tests/
```

### Key Dependencies

| Module | Purpose |
|--------|---------|
| `mail` | Core messaging (`mail.message`, `discuss.channel`, `mail.guest`) |
| `rating` | Customer satisfaction ratings |
| `bus` | Real-time WebSocket notifications via `ir.websocket` |
| `website` | Website widget integration (`website_livechat` extends this) |
| `digest` | KPI digest reporting |
| `utm` | Campaign tracking via `utm.source.mixin` on chatbots |

### Asset Bundles (manifest)

The module defines 10+ named asset bundles for fine-grained loading:
- `im_livechat.assets_embed_core`: Shared JS for both embedded and external modes (includes mail, bus, rating)
- `im_livechat.assets_embed_external`: Full external standalone page (Bootstrap + web frontend)
- `im_livechat.assets_embed_cors`: External mode with cross-origin support for third-party websites
- `im_livechat.assets_livechat_support_tours`: Backend operator UI test tours

This separation allows the external chat widget to run as a fully isolated shadow-DOM page, completely independent of the host website's CSS and JavaScript.

---

## Core Model: im_livechat.channel

**File:** `models/im_livechat_channel.py`
**Inherits:** `rating.parent.mixin`
**Mixins:** `image.mixin` (via chatbot_script)
**Rating Parent Field:** `livechat_channel_id` (via `rating.mixin._rating_get_parent_field_name`)
**_rating_satisfaction_days = 14** — only ratings from the last 14 days count toward satisfaction percentage

The central configuration model for live chat channels. Each channel corresponds to one chat widget with a unique ID, operators, rules, and chatbot scripts.

### Fields

#### Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required | Channel name displayed in backend |
| `button_text` | Char | "Need help? Chat with us." | Text on chat button; translatable |
| `default_message` | Char | "How may I help you?" | Welcome message shown on chat open; translatable |
| `header_background_color` | Char | "#875A7B" | Widget header background color |
| `title_color` | Char | "#FFFFFF" | Widget header title text color |
| `button_background_color` | Char | "#875A7B" | Chat button background color |
| `button_text_color` | Char | "#FFFFFF" | Chat button text color |
| `review_link` | Char | False | URL redirect for visitors leaving positive ratings |

**L2 Details:**
- `review_link`: Only triggered for positive ratings (typically 4-5 stars). Used to send satisfied customers to a review platform or feedback form. Validated to require `http://` or `https://` scheme with a valid network location via `_check_review_link`.
- Button colors use CSS color values (hex, rgb, named colors). These are rendered inline on the widget.

#### Session Capacity Management

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_sessions_mode` | Selection | "unlimited" | "unlimited" or "limited" per operator |
| `max_sessions` | Integer | 10 | Max concurrent sessions per operator (when mode=limited) |
| `block_assignment_during_call` | Boolean | False | Block new chats when operator is in a WebRTC call |

**L3 Details:**
- `max_sessions_mode = "limited"`: Enforced in `_compute_available_operator_ids` and `_compute_remaining_session_capacity`. Operators over their individual limit are excluded from routing even if `available_operator_ids` includes them.
- `block_assignment_during_call`: Checked via `user.sudo().is_in_call`. The operator's RTC session status is determined by `discuss.channel.rtc.session` records joined through `discuss.channel.member`.

**Constraint:**
```python
_max_sessions_mode_greater_than_zero = models.Constraint(
    "CHECK(max_sessions > 0)",
    "Concurrent session number should be greater than zero."
)
```

#### Computed Fields (all use `compute_sudo=True` implicitly via ORM)

| Field | Type | Description |
|-------|------|-------------|
| `web_page` | Char | Static page URL: `{base}/im_livechat/support/{id}` |
| `are_you_inside` | Boolean | Current `request.env.user` is in `user_ids` |
| `available_operator_ids` | Many2many(res.users) | Online operators under session capacity; sudo-accessed |
| `script_external` | Html | Rendered QWeb template `im_livechat.external_loader` with dbname, channel_id, base URL |
| `nbr_channel` | Integer | Total count of all `discuss.channel` records linked to this channel |
| `ongoing_session_count` | Integer | Active sessions (no `livechat_end_dt`) across all operators |
| `remaining_session_capacity` | Integer | Sum of `(max_sessions * available_user_count) - used_slots`, floored at 0 |
| `chatbot_script_count` | Integer | Count of distinct chatbot scripts linked via `rule_ids.chatbot_script_id` |

**L3 Details — `available_operator_ids` computation chain:**
```
_compute_available_operator_ids
  └─ calls _get_available_operators_by_livechat_channel(users=None)
       ├─ for each channel: filters `user_ids` by presence=="online"
       ├─ applies capacity check (if max_sessions_mode=="limited"):
       │    └─ _get_ongoing_session_count_by_agent_livechat_channel(filter_online=True)
       │         └─ _read_group on discuss.channel.member:
       │              domain: livechat_end_dt=False AND last_interest_dt >= "-15M"
       │              groupby: [partner_id, livechat_channel_id]
       └─ applies block_assignment_during_call check
```

**L4 — Performance Note:** `available_operator_ids` is computed fresh on every read. The underlying `_get_ongoing_session_count_by_agent_livechat_channel` uses a `_read_group` aggregation — not a SQL query — making it efficient for moderate operator counts. However, on channels with many operators (50+), the per-channel SQL aggregation may add latency. The 15-minute `last_interest_dt` window prevents stale sessions from inflating counts.

#### Relational Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_ids` | Many2many(res.users) | Channel operators/agents; assigned via `_default_user_ids` = current user |
| `channel_ids` | One2many(discuss.channel) | All sessions ever created on this channel |
| `rule_ids` | One2many(im_livechat.channel.rule) | URL/country matching rules, ordered by `sequence` |

---

### Key Methods

#### Operator Assignment

```python
def _get_operator(self, previous_operator_id=None, lang=None,
                  country_id=None, expertises=None, users=None) -> res.users
```

**Purpose:** Return an available operator using intelligent multi-criteria routing.

**Buffer Time Constant:** `BUFFER_TIME = 120` seconds. Operators assigned a new session within the last 2 minutes get lower priority (unless they are the only match), preventing all new visitors from flooding a recently-contacted operator.

**Active Session Window:** A session is considered "active" if `last_interest_dt > now() - 30 minutes`. Sessions older than 30 minutes without activity do not count toward load.

**Routing Logic (preference tiers — first match wins):**

| Priority | Language | Expertise | Country |
|----------|----------|-----------|---------|
| 1 | Same | All required | — |
| 2 | Same | One required | — |
| 3 | Same | None | — |
| 4 | Any | All required | Same |
| 5 | Any | One required | Same |
| 6 | Any | None | Same |
| 7 | Any | All required | Any |
| 8 | Any | One required | Any |
| 9 (fallback) | — | — | — → least loaded |

**Buffer time filtering:** Within each tier, operators assigned within `BUFFER_TIME` seconds are deprioritized. If all operators in a tier are in the buffer window, the least-loaded among them is returned.

**SQL query for operator status (raw):**
```sql
WITH operator_rtc_session AS (
    SELECT COUNT(DISTINCT s.id) as nbr, member.partner_id
      FROM discuss_channel_rtc_session s
      JOIN discuss_channel_member member ON (member.id = s.channel_member_id)
  GROUP BY member.partner_id
)
SELECT COUNT(DISTINCT h.channel_id) AS active_chats,
       COALESCE(rtc.nbr, 0) > 0 AS in_call,
       h.partner_id
  FROM im_livechat_channel_member_history h
  JOIN discuss_channel c ON h.channel_id = c.id
  LEFT OUTER JOIN operator_rtc_session rtc ON rtc.partner_id = h.partner_id
 WHERE c.livechat_end_dt IS NULL
   AND c.last_interest_dt > ((now() at time zone 'UTC') - interval '30 minutes')
   AND h.partner_id IN %s
GROUP BY h.partner_id, rtc.nbr
ORDER BY COUNT(DISTINCT h.channel_id) < 2 OR rtc.nbr IS NULL DESC,
         COUNT(DISTINCT h.channel_id) ASC,
         rtc.nbr IS NULL DESC
```

**L4 — Load Balancing Logic:** The ORDER BY places operators with fewer than 2 active chats first, preferring those not in a call. The `COUNT < 2 OR rtc.nbr IS NULL` clause ensures that operators with zero or one chat always rank above operators with 2+ chats who happen to not be in a call. Random selection via `random.choice()` among tied operators prevents thundering-herd when multiple operators have identical load.

**Failure Modes:**
- Returns `self.env["res.users"]` (empty recordset) if no operators are available
- **FIXME comment in source:** Inactive RTC sessions are not garbage-collected before routing, so operators flagged as "in call" may actually have ended the call. `_gc_inactive_sessions()` is called at the start of `_get_operator` to mitigate this.

---

```python
def _get_less_active_operator(self, operator_statuses, operators) -> res.users
```

Selects operator with the lowest active chat count, not currently in a call. Falls back to least-loaded among all candidates.

```python
def _get_operator_info(self, /, *, lang, country_id,
                       previous_operator_id=None, chatbot_script_id=None, **kwargs) -> dict
```

Orchestrates operator selection: first checks if a chatbot script is configured and active (priority), otherwise calls `_get_operator`. Returns `{'agent', 'chatbot_script', 'operator_partner', 'operator_model'}`.

**operator_model** can be `'chatbot.script'` or `'res.users'`. This determines whether a bot or human handles the session.

---

#### Channel Creation

```python
def _get_livechat_discuss_channel_vals(self, /, *, chatbot_script=None, agent=None,
                                        operator_partner, operator_model, **kwargs) -> dict
```

Builds the vals dict for creating a new livechat `discuss.channel`. Key behaviors:

- Creates operator member with `livechat_member_type='agent'` (human) or `'bot'` (chatbot), with `unpin_dt=now` so operator doesn't see pinned notification
- For public (anonymous) users: creates a `mail.guest` member with `livechat_member_type='visitor'`
- For logged-in users: creates a partner member with `livechat_member_type='visitor'`
- `livechat_failure` is set to `'no_answer'` when `operator_model=='res.users'` (human), meaning no failure. For chatbots, it is not set (implicitly `no_failure`)
- `chatbot_current_step_id` is set to the last welcome step if using a chatbot

```python
def _get_agent_member_vals(self, /, ..., chatbot_script, operator_partner, operator_model, ...) -> dict
```

Returns the channel member vals for the operator/bot side of the session. Note: `unpin_dt=now` is set here to prevent the operator from receiving a pinned notification when added.

```python
def _get_channel_name(self, /, ..., visitor_user, guest, agent, chatbot_script, operator_model, ...) -> str
```

For chatbot sessions: channel name = chatbot title. For human sessions: `"{visitor_name} {operator_name}"`.

---

#### Availability and Info

```python
def _is_livechat_available(self) -> bool
    return self.chatbot_script_count or len(self.available_operator_ids) > 0
```

A channel is "available" if it has at least one chatbot script OR at least one online operator within capacity.

```python
def get_livechat_info(self, username=None) -> dict
```

Public endpoint response for the chat widget loader. Returns:
```python
{
    'available': bool,
    'server_url': str,           # get_base_url()
    'websocket_worker_version': str,
    'options': {                # only if available
        'header_background_color', 'button_background_color',
        'title_color', 'button_text_color', 'button_text',
        'default_message', 'channel_name', 'channel_id', 'review_link',
        'default_username': username or 'Visitor'
    }
}
```

```python
def _get_channel_infos(self) -> dict
```

Returns channel styling and branding options as a dict (used by `get_livechat_info`).

```python
def _get_available_operators_by_livechat_channel(self, users=None) -> dict
```

Returns `{livechat_channel: available_users}` mapping. This is the core of availability checking.

```python
def _get_ongoing_session_count_by_agent_livechat_channel(self, users=None,
                                                          filter_online=False) -> dict
```

Returns `{(partner, livechat_channel): count}`. The `filter_online=True` path filters to operators whose `presence_ids.status == "online"` before counting. The 15-minute `last_interest_dt` window is critical: it means operators who have not interacted for 15 minutes are treated as having no active sessions for routing purposes.

---

## Channel Rule Model: im_livechat.channel.rule

**File:** `models/im_livechat_channel.py`

Defines URL pattern and country-based routing rules for a channel. Rules are evaluated in `sequence` ascending order.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `regex_url` | Char | False | Regular expression for URL matching (Python `re.search`) |
| `action` | Selection | "display_button" | Show/Show+Notification/Auto-Popup/Hide |
| `auto_popup_timer` | Integer | 0 | Seconds before auto-open (only if action='auto_popup') |
| `chatbot_script_id` | Many2one(chatbot.script) | False | Chatbot to activate for matching pages |
| `chatbot_enabled_condition` | Selection | "always" | Always / Only if no operator / Only if operator available |
| `channel_id` | Many2one(im_livechat.channel) | required | Parent channel |
| `country_ids` | Many2many(res.country) | False | Country restrictions (empty = all countries) |
| `sequence` | Integer | 10 | Rule priority (lower = higher priority) |

**L2 Details:**
- `chatbot_enabled_condition` controls chatbot activation based on human operator availability:
  - `"always"`: Chatbot always active
  - `"only_if_no_operator"`: Chatbot active only when `available_operator_ids` is empty
  - `"only_if_operator"`: Chatbot active only when at least one operator is available
- `action` options map to frontend behaviors: `"display_button"` shows the widget, `"display_button_and_text"` shows a floating notification bubble, `"auto_popup"` opens the chat panel, `"hide_button"` suppresses the widget.

### Matching Logic

```python
def match_rule(self, channel_id, url, country_id=False) -> im_livechat.channel.rule | empty
```

**Algorithm:**
1. If `country_id` is provided (GeoIP resolved): search rules with matching `country_ids` first, sorted by `sequence`
2. If no country-specific rule matches: fall back to rules with no `country_ids` restriction
3. Within each rule set: iterate in sequence order, applying `re.search(rule.regex_url or "", url or "")`
4. Skip rules whose `chatbot_script_id` is inactive or has no steps
5. Skip rules failing `chatbot_enabled_condition` check
6. Return first matching rule, or empty recordset

**L3 Edge Cases:**
- If `url` is `None` (e.g., from `Referer` header on initial page): rule matches if `regex_url` is empty/falsy
- Multiple rules with same `sequence`: indeterminate order; rules should have unique sequences
- Country matching requires GeoIP to be installed and configured on the Odoo server (`request.geoip`)

---

## Discuss Channel Extension

**File:** `models/discuss_channel.py`
**Inherits:** `['rating.mixin', 'discuss.channel']`
**Model:** `discuss.channel`

Extends `discuss.channel` with livechat-specific fields, computed tracking fields, and chatbot integration.

### Livechat-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `channel_type` | Selection | Extended: now includes "livechat" option; `ondelete='cascade'` removes livechat channels when parent record deleted |
| `livechat_channel_id` | Many2one(im_livechat.channel) | Back-reference to parent channel config; indexed `btree_not_null` |
| `livechat_operator_id` | Many2one(res.partner) | Assigned operator; indexed `btree_not_null` |
| `livechat_lang_id` | Many2one(res.lang) | Visitor's detected/selected language |
| `livechat_end_dt` | Datetime | Session close timestamp; null while active |
| `livechat_failure` | Selection | "no_answer", "no_agent", "no_failure" — set at creation and potentially updated on forward |
| `livechat_status` | Selection | Computed: "in_progress", "waiting", "need_help"; cleared when `livechat_end_dt` is set |
| `livechat_outcome` | Selection | Computed: "escalated" if `livechat_is_escalated`, else `livechat_failure` |
| `livechat_note` | Html | Internal operator note, sanitized; `groups=base.group_user` |
| `livechat_conversation_tag_ids` | Many2many | Tags for session classification; `groups=im_livechat_group_user` |
| `livechat_start_hour` | Float | Hour of day (0-23) session started; computed+stored |
| `livechat_week_day` | Selection | Day of week (0=Monday..6=Sunday); computed+stored |
| `livechat_is_escalated` | Boolean | Computed+stored: True if more than one agent in `livechat_agent_history_ids` |
| `livechat_matches_self_lang` | Boolean | Searchable: session language matches current user's lang or `livechat_lang_ids` |
| `livechat_matches_self_expertise` | Boolean | Searchable: session expertise overlaps current user's `livechat_expertise_ids` |

**Participant tracking (computed+stored Many2many):**

| Field | Target | Description |
|-------|--------|-------------|
| `livechat_agent_history_ids` | im_livechat.channel.member.history | Filtered: `livechat_member_type='agent'` |
| `livechat_bot_history_ids` | im_livechat.channel.member.history | Filtered: `livechat_member_type='bot'` |
| `livechat_customer_history_ids` | im_livechat.channel.member.history | Filtered: `livechat_member_type='visitor'` |
| `livechat_agent_partner_ids` | res.partner | Partner records from agent histories |
| `livechat_bot_partner_ids` | res.partner | Partner records from bot histories |
| `livechat_customer_partner_ids` | res.partner | Partner records from visitor histories |
| `livechat_customer_guest_ids` | mail.guest | Guest records from visitor histories |

**Escalation tracking (computed+stored):**

| Field | Type | Description |
|-------|------|-------------|
| `livechat_agent_requesting_help_history` | Many2one(history) | First agent in history (earliest create_date) — the agent who requested help |
| `livechat_agent_providing_help_history` | Many2one(history) | Last agent in history — the agent who took over |

**Chatbot fields:**

| Field | Type | Description |
|-------|------|-------------|
| `chatbot_current_step_id` | Many2one(chatbot.script.step) | Current position in the chatbot script |
| `chatbot_message_ids` | One2many(chatbot.message) | All bot messages with user answer tracking |
| `country_id` | Many2one(res.country) | Visitor's GeoIP country |
| `livechat_expertise_ids` | Many2many(im_livechat.expertise) | Expertise tags for routing/helping; stored |
| `rating_last_text` | Selection | Stored: last rating text (great/ok/ko) |

### Computed Tracking Methods

```python
def _compute_duration(self):
    """Duration = (livechat_end_dt or now()) - create_date in hours"""
```

```python
def _compute_livechat_status(self):
    """If livechat_end_dt is set, livechat_status is cleared (null)."""
```

```python
def _compute_livechat_is_escalated(self):
    """True if livechat_agent_history_ids has more than one record."""
```

### Database Constraints

```python
_livechat_operator_id = models.Constraint(
    "CHECK((channel_type = 'livechat' and livechat_operator_id is not null) "
    "or (channel_type != 'livechat'))",
    'Livechat Operator ID is required for a channel of type livechat.'
)
# Ensures every livechat channel has exactly one operator.

_livechat_end_dt_status_constraint = models.Constraint(
    "CHECK(livechat_end_dt IS NULL or livechat_status IS NULL)",
    "Closed Live Chat session should not have a status."
)
# Ensures closed sessions (with end_dt) don't have a live status value.
```

### Partial Indexes (Performance)

```sql
CREATE INDEX idx_livechat_end_dt ON discuss_channel (livechat_end_dt) WHERE livechat_end_dt IS NULL;
-- Optimizes queries for active sessions (e.g., operator load calculation)

CREATE INDEX idx_livechat_failure ON discuss_channel (livechat_failure)
  WHERE livechat_failure IN ('no_answer', 'no_agent');
-- Optimizes reporting on failed sessions

CREATE INDEX idx_livechat_is_escalated ON discuss_channel (livechat_is_escalated)
  WHERE livechat_is_escalated IS TRUE;
-- Optimizes escalation audit queries

CREATE INDEX idx_livechat_channel_type_create_date ON discuss_channel (channel_type, create_date)
  WHERE channel_type = 'livechat';
-- Optimizes time-based reporting queries
```

**L4 — Write Hook:** The `write()` override only fires on `livechat_status` or `livechat_expertise_ids` changes. It emits `im_livechat.looking_for_help/update` bus notifications when status transitions to/from "need_help". This is the primary mechanism for real-time "escalation" notifications to other operators.

### Chatbot Methods

```python
def _chatbot_post_message(self, chatbot_script, body) -> mail.message
```

Posts a message as the chatbot's operator partner. Used for both scripted bot messages and email validation errors.

```python
def _chatbot_find_customer_values_in_messages(self, step_type_to_field) -> dict
```

Scans `chatbot_message_ids` for user inputs matching specific step types. Used by bridge modules (e.g., `crm`) to extract email/phone collected by chatbot `question_email`/`question_phone` steps.

```python
def _chatbot_restart(self, chatbot_script) -> mail.message
```

Clears `chatbot_current_step_id`, `livechat_end_dt`, and deletes all `chatbot_message_ids`, then posts a "Restarting conversation..." notification. Allows visitors to restart a bot conversation from scratch.

```python
def _forward_human_operator(self, chatbot_script_step=None, users=None) -> mail.message
```

The escalation action. Replaces the chatbot with a human operator:
1. Calls `_get_human_operator()` with optional expertise filtering from `chatbot_script_step.operator_expertise_ids`
2. Posts the forwarding step's message if present
3. Adds human operator as channel member with `livechat_member_type='agent'`
4. Removes the bot member
5. Updates `livechat_operator_id`, channel name, and `livechat_failure='no_answer'`
6. Sets expertise tags on the channel from the step
7. If no operator found: sets `livechat_failure='no_agent'`

```python
def _get_human_operator(self, users, chatbot_script_step) -> res.users
```

Wrapper that calls `livechat_channel_id._get_operator()` with expertise from `chatbot_script_step.operator_expertise_ids`.

---

## Channel Member Extension

**File:** `models/discuss_channel_member.py`
**Inherits:** `discuss.channel.member`

Tracks livechat-specific member properties. The member record is the central identity for each participant in a session.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `livechat_member_history_ids` | One2many(history) | All history records for this member |
| `livechat_member_type` | Selection | "agent", "visitor", "bot"; computed from history, with inverse |
| `chatbot_script_id` | Many2one(chatbot.script) | Active chatbot; computed from history, with inverse |
| `agent_expertise_ids` | Many2many(im_livechat.expertise) | Expertise tags for this agent; computed from history, with inverse |

### Member Type Assignment (`create` override)

```python
@api.model_create_multi
def create(self, vals_list):
    members = super().create(vals_list)
    guest = self.env["mail.guest"]._get_guest_from_context()
    for member in members.filtered(
        lambda m: m.channel_id.channel_type == "livechat" and not m.livechat_member_type
    ):
        if (guest and member.is_self and
            guest in member.channel_id.livechat_customer_guest_ids):
            member.sudo().livechat_member_type = "visitor"
        else:
            member.sudo().livechat_member_type = "agent"
    return members
```

**L3 — Guest Reconciliation:** The `mail.guest` cookie persists after visitor login. When a logged-in user visits, the newly created member record matches against `livechat_customer_guest_ids` (computed from history). If the guest matches, the member is typed as "visitor" rather than "agent", preserving the visitor identity through authentication.

**L3 — `_create_or_update_history`:** This method handles the history creation/update logic when `livechat_member_type`, `chatbot_script_id`, or `agent_expertise_ids` are written on the member. It uses `Domain.OR` to batch-query existing histories and creates missing records in a single `create()` call — important for performance when creating multiple member histories.

### Auto-Unpin Garbage Collection

```python
@api.autovacuum
def _gc_unpin_livechat_sessions(self):
    """Unpin sessions inactive for 24+ hours with no unread messages."""
    members = self.env['discuss.channel.member'].search([
        ('is_pinned', '=', True),
        ('last_seen_dt', '<=', datetime.now() - timedelta(days=1)),
        ('channel_id.channel_type', '=', 'livechat'),
    ])
    sessions_to_be_unpinned = members.filtered(lambda m: m.message_unread_counter == 0)
    sessions_to_be_unpinned.write({'unpin_dt': fields.Datetime.now()})
    sessions_to_be_unpinned.channel_id.livechat_end_dt = fields.Datetime.now()
    for member in sessions_to_be_unpinned:
        Store(bus_channel=member._bus_channel()).add(
            member.channel_id,
            {"close_chat_window": True, "livechat_end_dt": fields.Datetime.now()},
        ).bus_send()
```

**L4 — Session End Triggers:** Sessions are closed when:
1. Visitor explicitly leaves (`visitor_leave_session` controller endpoint)
2. Last agent leaves (in `_action_unfollow`)
3. Auto-unpin GC runs after 24h inactivity with zero unread messages

### RTC / Call Exclusion

```python
def _get_rtc_invite_members_domain(self, *a, **kw):
    domain = super()._get_rtc_invite_members_domain(*a, **kw)
    if self.channel_id.channel_type == "livechat":
        domain &= Domain("partner_id", "not in",
                         self._get_excluded_rtc_members_partner_ids())
    return domain

def _get_excluded_rtc_members_partner_ids(self):
    chatbot = self.channel_id.chatbot_current_step_id.chatbot_script_id
    return [chatbot.operator_partner_id.id] if chatbot else []
```

**L3 — Purpose:** Prevents the chatbot operator from being invited to WebRTC calls. Only human participants should appear in the call invite UI.

---

## Session History Model

**File:** `models/im_livechat_channel_member_history.py`
**Model:** `im_livechat.channel.member.history`

The reporting and history backbone. One record per member per session, created via `_create_or_update_history`. All reporting fields are computed/aggregated from this table.

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `member_id` | Many2one(discuss.channel.member) | Unique per-member link; `index='btree_not_null'` |
| `livechat_member_type` | Selection | "agent", "visitor", "bot"; stored compute |
| `channel_id` | Many2one(discuss.channel) | Parent session; cascade delete; stored compute |
| `partner_id` | Many2one(res.partner) | For agent/visitor with account; `index='btree_not_null'` |
| `guest_id` | Many2one(mail.guest) | For anonymous visitors; `index='btree_not_null'` |
| `chatbot_script_id` | Many2one(chatbot.script) | Active chatbot; `index='btree_not_null'` |
| `agent_expertise_ids` | Many2many(im_livechat.expertise) | Expertise tags; stored compute |
| `avatar_128` | Binary | Computed from `partner_id.avatar_128` or `guest_id.avatar_128` |

**Constraint — XOR on partner/guest:**
```python
_partner_id_or_guest_id_constraint = models.Constraint(
    "CHECK(partner_id IS NULL OR guest_id IS NULL)",
    "History should either be linked to a partner or a guest but not both"
)
```
This ensures clean separation between authenticated and anonymous visitor records.

### Reporting / Aggregatable Fields

These fields use Odoo's `aggregator` attribute (e.g., `aggregator="avg"`, `aggregator="sum"`) enabling GROUP BY reporting through `_read_group`.

| Field | Type | Aggregator | Description |
|-------|------|------------|-------------|
| `session_country_id` | Many2one(res.country) | — | Related from channel |
| `session_livechat_channel_id` | Many2one | — | Related from channel |
| `session_outcome` | Selection | — | Related from channel |
| `session_start_hour` | Float | avg | Related from channel (0-23) |
| `session_week_day` | Selection | — | Related from channel |
| `session_duration_hour` | Float | avg | `(end_dt or last_msg_dt or now) - create_date` / 3600 |
| `rating_id` | Many2one(rating.rating) | — | For agent/bot members only |
| `rating` | Float | avg | Related from rating_id |
| `rating_text` | Selection | — | "great", "ok", "ko" |
| `call_history_ids` | Many2many | — | Linked call history records |
| `has_call` | Float | sum/avg | 1 if `call_history_ids` not empty |
| `call_count` | Float | sum | Related from `has_call` |
| `call_percentage` | Float | avg | % sessions with a call |
| `call_duration_hour` | Float | sum | Sum of linked call history durations |
| `message_count` | Integer | avg | Messages posted by this member |
| `help_status` | Selection | — | "requested" (first agent) or "provided" (last agent) |
| `response_time_hour` | Float | avg | Time from history creation to first agent message |

**L3 — Rating Assignment:** `_compute_rating_id` filters to ratings where `rated_partner_id == history.partner_id`. Live chats only allow one rating per session, enforced in the feedback controller (`# limit the creation: only ONE rating per session`).

**L3 — Help Status Logic:**
```python
# First agent (earliest create_date) → "requested" (they were asked for help)
# Last agent (latest create_date) → "provided" (they took over the session)
# Non-agent histories → help_status = None
```

### Constraints

```python
_member_id_unique = models.Constraint(
    "UNIQUE(member_id)",
    "Members can only be linked to one history"
)
# A single channel member can only have one history record.

_channel_id_partner_id_unique = models.UniqueIndex(
    "(channel_id, partner_id) WHERE partner_id IS NOT NULL",
    "One partner can only be linked to one history on a channel"
)
_channel_id_guest_id_unique = models.UniqueIndex(
    "(channel_id, guest_id) WHERE guest_id IS NOT NULL",
    "One guest can only be linked to one history on a channel"
)
# Partial unique indexes: one history per persona per channel.
```

**L3 — Constraint Violation:** The `_constraint_channel_id` Python constraint validates that history records are only created for livechat channels. Raises `ValidationError` if a non-livechat channel is somehow linked. This is a second layer of defense; the SQL constraint is the primary protection.

---

## Chatbot Models

### chatbot.script

**File:** `models/chatbot_script.py`
**Inherits:** `['image.mixin', 'utm.source.mixin']`
**Rec Name:** `title`

Configures automated chatbot conversations. Creating a chatbot automatically creates an inactive `res.partner` record (`active=False`) as the bot operator.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | Char | Bot display name; `rec_name`; translatable |
| `active` | Boolean | Overall active flag |
| `image_1920` | Image | Bot avatar; related to `operator_partner_id.image_1920` with `readonly=False` |
| `script_step_ids` | One2many(chatbot.script.step) | Script steps; ordered by sequence |
| `operator_partner_id` | Many2one(res.partner) | Bot operator partner (auto-created if not provided) |
| `livechat_channel_count` | Integer | Distinct channels using this bot via rules |
| `first_step_warning` | Selection | Validation warning: "first_step_operator" or "first_step_invalid" |

**L2 — `image_1920`:** Setting `image_1920` writes directly to the related `operator_partner_id.image_1920`. Deleting the chatbot does not delete the partner record due to `ondelete='restrict'` on the field.

**L3 — `first_step_warning` validation:**
```python
# Allowed first interactive step types:
['question_selection', 'question_email', 'question_phone',
 'free_input_single', 'free_input_multi']
# If the last welcome step is 'forward_operator' → 'first_step_operator'
# If the last welcome step is 'text' (no user input expected) → 'first_step_invalid'
```

#### `create` Override — Auto-Create Operator Partner

```python
@api.model_create_multi
def create(self, vals_list):
    operator_partners_values = [{
        'name': vals['title'],
        'image_1920': vals.get('image_1920', False),
        'active': False,   # Inactive partner: not a real user
    } for vals in vals_list
     if 'operator_partner_id' not in vals and 'title' in vals]
    operator_partners = self.env['res.partner'].create(operator_partners_values)
    for vals, partner in zip([...], operator_partners):
        vals['operator_partner_id'] = partner.id
    return super().create(vals_list)
```

**L3 — Why inactive partner?** The bot operator partner is not a real user — it has no login credentials, cannot access Odoo, and is never "online" in the traditional sense. However, `author_id` on messages is set to this partner, so it appears as the message sender. Making it inactive prevents it from appearing in partner search results for regular operations.

#### `copy` Override — Triggering Answer Preservation

```python
def copy(self, default=None):
    # Post-process: remap triggering_answer_ids from original steps to clone steps
    for old_script, new_script in zip(self, new_scripts):
        answers_map = {
            original_answer: clone_answer
            for clone_step, original_step in zip(clone_steps, original_steps)
            for clone_answer, original_answer in zip(clone_step.answer_ids,
                                                      original_step.answer_ids)
        }
        for clone_step, original_step in zip(clone_steps, original_steps):
            clone_step.triggering_answer_ids = [
                (4, answers_map[original_answer].id)
                for original_answer in original_step.triggering_answer_ids
            ]
    return new_scripts
```

**L3 — Why special handling?** `triggering_answer_ids` stores Many2many IDs. A standard copy would link clone steps to original script's answers. The override builds an ID remapping table after the copy and fixes the references.

#### Key Methods

```python
def _get_welcome_steps(self) -> chatbot.script.step recordset
```

Returns all steps before the first interactive (non-"text") step. Used to pre-display bot welcome messages. These welcome messages are **not** saved as `mail.message` records — they are stored only in memory and rendered directly in the frontend, avoiding database bloat for sessions where the visitor never interacts.

```python
def _post_welcome_steps(self, discuss_channel) -> mail.message recordset
```

Posts welcome step messages to the channel after visitor's first interaction. Each step sets `chatbot_current_step_id` before posting so the message hook (`_message_post_after_hook`) creates the correct `chatbot.message` record.

```python
def _get_chatbot_language(self) -> str
```

Returns the language code from the `frontend_lang` cookie via `get_lang()`. Used to set `mail.message` context for multilingual chatbots.

```python
def _validate_email(self, email_address, discuss_channel) -> dict
```

Validates email using `email_normalize()`. If invalid, posts an error message as the chatbot and returns `{'success': False, 'posted_message', 'error_message'}`.

---

### chatbot.script.step

**File:** `models/chatbot_script_step.py`
**Order:** `sequence, id`

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | computed | "{chatbot_title} - Step {sequence}"; translatable |
| `message` | Html | required | Bot message content; translatable |
| `sequence` | Integer | auto | Step order; auto-assigned incrementally on create |
| `chatbot_script_id` | Many2one | required | Parent chatbot; `ondelete='cascade'` |
| `step_type` | Selection | "text" | See step types below |
| `answer_ids` | One2many(chatbot.script.answer) | — | Options for `question_selection`; cleared on type change |
| `triggering_answer_ids` | Many2many(chatbot.script.answer) | — | Conditional display: show only if all these answers were selected |
| `is_forward_operator` | Boolean | computed | `step_type == 'forward_operator'` |
| `is_forward_operator_child` | Boolean | computed | This step is downstream of a forward step |
| `operator_expertise_ids` | Many2many(im_livechat.expertise) | — | Expertise required when forwarding to human |

#### Step Types

| Type | User Input | Description |
|------|-----------|-------------|
| `text` | None | Display-only message; welcome message type |
| `question_selection` | Button click | Multiple choice with `answer_ids`; creates `user_script_answer_id` on chatbot.message |
| `question_email` | Free text | Email validation via `email_normalize`; stored in `user_raw_answer` |
| `question_phone` | Free text | Phone number; stored in `user_raw_answer` |
| `free_input_single` | Free text | Single-line input; stored in `user_raw_answer` |
| `free_input_multi` | Free text | Multi-line input; stored in `user_raw_answer` |
| `forward_operator` | None | Triggers `_forward_human_operator()` on the channel |

#### Triggering Answer Logic

```python
def _fetch_next_step(self, selected_answer_ids) -> chatbot.script.step | empty
```

Conditional branching engine:
- Within the same step: multiple selected answers = OR
- Across different steps: must have selected answers from ALL prerequisite steps = AND
- If no `triggering_answer_ids` → unconditional step (default next step)

**Example from source:**
```
Step 1: [A, B]
Step 2: [C, D]
Step 3: [E]
Step 4: Only If [A, B, C, E]
→ To reach Step 4: (A or B) AND C AND E must all be selected
```

#### `create` Override — Auto-Sequence Assignment

```python
@api.model_create_multi
def create(self, vals_list):
    # Group by chatbot_id, find max existing sequence per chatbot
    # Auto-assign sequence = max + 1, +2, etc. for steps without explicit sequence
    # Manual sequence values take precedence
```

**L3 — Purpose:** Ensures steps are always in a predictable order. If a user creates 5 steps without specifying sequence, they get 1, 2, 3, 4, 5. If they create steps with sequences 10 and 20, the next auto-assigned is 21.

#### `_process_answer` — Input Validation

```python
def _process_answer(self, discuss_channel, message_body) -> chatbot.script.step
```

Called when visitor submits input:
- `question_email`: validates via `email_normalize`, raises `ValidationError` if invalid (step does not advance)
- `question_phone`, `free_input_single`, `free_input_multi`: writes `user_raw_answer` to existing `chatbot.message`
- All types: calls `_fetch_next_step()` to find the next step

#### `_process_step` — Step Execution

```python
def _process_step(self, discuss_channel) -> mail.message
```

Executes the current step:
- `forward_operator`: calls `discuss_channel._forward_human_operator(chatbot_script_step=self)`
- All other types: calls `discuss_channel._chatbot_post_message(self.chatbot_script_id, self.message)`

---

### chatbot.script.answer

**File:** `models/chatbot_script_answer.py`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Answer text shown on button; translatable |
| `sequence` | Integer | Display order |
| `redirect_link` | Char | URL opened on click (external links end the script) |
| `script_step_id` | Many2one(chatbot.script.step) | Parent step; `ondelete='cascade'` |
| `chatbot_script_id` | Many2one | Computed from parent |

**`display_name` computed field:**
- Without `chatbot_script_answer_display_short_name` context: `"{shortened_parent_message}: {answer_name}"`
- With context: just `name`
- Shortening uses `textwrap.shorten(message, width=26)`

**`_search_display_name` override:** Searches on both `name` AND `script_step_id.message` when using `ilike` operator.

---

### chatbot.message

**File:** `models/chatbot_message.py`
**Model:** `chatbot.message`

Links bot step messages to `mail.message` records and stores visitor responses.

| Field | Type | Description |
|-------|------|-------------|
| `mail_message_id` | Many2one(mail.message) | The posted message; `unique` constraint |
| `discuss_channel_id` | Many2one(discuss.channel) | Parent session; `index=True`, `ondelete='cascade'` |
| `script_step_id` | Many2one(chatbot.script.step) | Which step generated this message; `index='btree_not_null'` |
| `user_script_answer_id` | Many2one(chatbot.script.answer) | Selected answer for `question_selection` steps |
| `user_raw_script_answer_id` | Integer | Frozen ID of the answer at time of response (survives answer deletion) |
| `user_raw_answer` | Html | Raw user text for `question_email/phone/free_input` steps |

**Why `user_raw_script_answer_id`?** When an answer is deleted from the script (e.g., a product is discontinued), the historical response data is preserved. The answer ID is stored as an integer field rather than a Many2one to avoid FK constraint failures.

**Partial Index:**
```sql
CREATE INDEX idx_channel_answer_raw
  ON chatbot_message (discuss_channel_id, user_raw_script_answer_id)
  WHERE user_raw_script_answer_id IS NOT NULL;
-- Optimizes reporting queries that group by raw answer ID
```

---

## Operator User Extensions

### res.users

**File:** `models/res_users.py`
**Inherits:** `res.users`

Adds livechat-specific preferences and computed tracking fields to the user record.

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `livechat_channel_ids` | Many2many | — | Channels this user is assigned to |
| `livechat_username` | Char | livechat_user, erp_manager | Display name in livechat; stored in settings |
| `livechat_lang_ids` | Many2many(res.lang) | livechat_user, erp_manager | Additional languages beyond main user lang |
| `livechat_expertise_ids` | Many2many(im_livechat.expertise) | livechat_user, erp_manager | Skill tags for routing |
| `livechat_ongoing_session_count` | Integer | livechat_user | Active session count (context-sensitive to `im_livechat_channel_id`) |
| `livechat_is_in_call` | Boolean | livechat_user | Whether user has an active RTC session |
| `has_access_livechat` | Boolean | (all) | Whether user is in `im_livechat_group_user` |

**L3 — Context-sensitive session count:** When `im_livechat_channel_id` is in context (e.g., from channel form), `livechat_ongoing_session_count` filters to only count sessions for that specific channel. Without context, it counts all livechat sessions.

**`write` override — Group membership sync:** When a user gains `im_livechat_group_user` (via `group_ids` write), they are automatically added to all livechat channels' `user_ids`. When they lose the group, they are removed from all channels.

**`_init_store_data` override:** Adds `has_access_livechat` to the global store values and `is_livechat_manager` (lambda checking `im_livechat_group_manager`) to the current user record.

---

### res.users.settings

**File:** `models/res_users_settings.py`
**Inherits:** `res.users.settings`

Stores per-user livechat preferences. The actual storage is here; `res.users` fields are computed/inverse proxies.

| Field | Type | Description |
|-------|------|-------------|
| `livechat_username` | Char | Display name in chat sessions |
| `livechat_lang_ids` | Many2many(res.lang) | Additional routing languages |
| `livechat_expertise_ids` | Many2many(im_livechat.expertise) | Skill tags |

**L3 — Why settings instead of direct user fields?** This pattern (Odoo 16+) allows livechat preferences to be stored per-device/per-session via `res.users.settings` records, which are tied to the user's browser session rather than globally on the user. It also allows for future per-device language preferences.

---

## Expertise Model

**File:** `models/im_livechat_expertise.py`
**Model:** `im_livechat.expertise`

Tags for categorizing operator skills, used in both chatbot forwarding and operator routing.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Unique expertise name; translatable |
| `user_ids` | Many2many(res.users) | Computed/inverse: operators with this expertise |

**Inverse mechanism:** When `user_ids` is written on an expertise, it uses `_inverse_user_ids` to write `livechat_expertise_ids` on the corresponding `res.users.settings` records (not directly on `res.users`). This is an indirect Many2many through settings.

**`_get_users_by_expertise`:** Searches `res.users.settings` for all users whose settings include each expertise, then resolves back to `res.users` via the settings→user relationship. Uses `with_prefetch()` for efficient batch loading.

---

## Conversation Tags

**File:** `models/im_livechat_conversation_tag.py`
**Model:** `im_livechat.conversation.tag`

Optional classification labels for livechat sessions.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Unique tag name; translatable |
| `color` | Integer | Random default (1-11); used for Kanban view coloring |
| `conversation_ids` | Many2many(discuss.channel) | Sessions tagged with this tag |

**`color` default:** `randint(1, 11)` — generates a random pastel-ish color for visual differentiation in Kanban views. Regenerated on each tag creation.

**`_unlink_sync_conversation`:** On tag deletion, removes the tag from all linked channels via `livechat_conversation_tag_ids` unlink command.

---

## Discuss Call History Extension

**File:** `models/discuss_call_history.py`
**Inherits:** `discuss.call.history`

| Field | Type | Description |
|-------|------|-------------|
| `livechat_participant_history_ids` | Many2many(im_livechat.channel.member.history) | Link to session participant histories |

**L3 — Purpose:** When a WebRTC call is started in a livechat session, this link allows aggregating call duration statistics per agent history record. Created in `discuss.channel.rtc.session` `create` override.

---

## Mail Message Extension

**File:** `models/mail_message.py`
**Inherits:** `mail.message`

Two overrides:

```python
def _to_store_defaults(self, target) -> list:
    return super()._to_store_defaults(target) + ["chatbot_current_step"]
```

```python
def _to_store(self, store, fields, **kwargs):
    # For messages in livechat channels where author == chatbot operator
    # and current step exists: inject chatbot step data into the store
    # Enables frontend to show answer buttons, input fields, operatorFound flag
```

`_get_store_partner_name_fields` override: for livechat messages, returns `res.partner._get_store_livechat_username_fields()` (prefers `user_livechat_username` over `name`).

---

## Rating Extension

**File:** `models/rating_rating.py`
**Inherits:** `rating.rating`

`_compute_res_name` override: for livechat sessions (`res_model='discuss.channel'`), sets `res_name` to `"{channel_name} / {channel_id}"` — the default `mail.message` rec_name would use the message body, which is unsuitable for session-level ratings.

`action_open_rated_object` override: redirects to the mail client action (`mail.action_discuss`) instead of the standard form view.

---

## Digest Extension

**File:** `models/digest.py`
**Inherits:** `digest.digest`

Four KPI fields for the digest:

| Field | Type | Description |
|-------|------|-------------|
| `kpi_livechat_rating` | Boolean | Enable "% of Happiness" KPI |
| `kpi_livechat_rating_value` | Float | % great ratings in period |
| `kpi_livechat_conversations` | Boolean | Enable "Conversations handled" KPI |
| `kpi_livechat_conversations_value` | Integer | Count of livechat sessions created |
| `kpi_livechat_response` | Boolean | Enable "Time to answer (sec)" KPI |
| `kpi_livechat_response_value` | Float | Average `time_to_answer` from `im_livechat.report.channel` |

**L3 — Time to Answer:** Reads from `im_livechat.report.channel` (a SQL view or reporting model), specifically the `time_to_answer:avg` aggregate. This requires the `im_livechat_report_channel` model to be accessible.

---

## Bus / WebSocket Extensions

### ir.websocket

**File:** `models/ir_websocket.py`
**Inherits:** `ir.websocket`

```python
def _build_bus_channel_list(self, channels) -> list:
    # If 'im_livechat.looking_for_help' is in channels:
    #   - add (im_livechat_group_user, 'LOOKING_FOR_HELP') subchannel
    #   - remove the string channel (it's replaced by the group-based channel)
    return super()._build_bus_channel_list(channels)
```

**L3 — `im_livechat.looking_for_help` subchannel:** Operators subscribe to this bus channel to receive real-time notifications when sessions enter "need_help" status. The channel is `(group, 'LOOKING_FOR_HELP')` rather than a string channel, ensuring only users in the livechat group receive these notifications.

### discuss.channel._close_livechat_session

Sets `livechat_end_dt = now()` and sends `{"close_chat_window": True}` bus notification to close the visitor's chat widget.

### discuss.channel._action_unfollow Override

When the last operator leaves a livechat session (member_count == 1 after unfollow), automatically closes the session by setting `livechat_end_dt`. This handles the case where an operator closes their Odoo tab without explicitly ending the session.

---

## Security Model

### Groups

| Group | ID | Implied Groups | Purpose |
|-------|-----|---------------|---------|
| `im_livechat.group_livechat_user` | `im_livechat_group_user` | `base.group_user` | Chat as operator, view sessions, manage expertise |
| `im_livechat.group_livechat_manager` | `im_livechat_group_manager` | `group_livechat_user` + `mail.group_mail_canned_response_admin` | Full channel CRUD, chatbot management, delete sessions |
| `im_livechat.privilege_live_chat` | Internal | `base.module_category_website` | Category privilege (used by both above) |

### Record Rules (ir.rule)

| Rule | Model | Groups | Force | Domain |
|------|-------|--------|-------|--------|
| `ir_rule_discuss_channel_im_livechat_group_user` | `discuss.channel` | `group_livechat_user` | read | `channel_type = 'livechat'` |
| `ir_rule_discuss_channel_member_im_livechat_group_user` | `discuss.channel.member` | `group_livechat_user` | read, unlink | `channel_id.channel_type = 'livechat'` |
| `ir_rule_discuss_call_history_im_livechat_group_user` | `discuss.call.history` | `group_livechat_user` | read | `channel_id.channel_type = 'livechat'` |

**L4 — Security Design:**
- Livechat users can only READ livechat channels (no create/write/unlink via ir.rule)
- Portal users (public website visitors) have no ir.rule access — they access via controller endpoints with `auth='public'`
- The `livechat_note` field has `groups='base.group_user'`: visible to all internal users with channel access, not just livechat operators
- `livechat_conversation_tag_ids` has `groups='im_livechat_group_user'`: tagging requires operator role

### ACL Entries (ir.model.access.csv)

| ACL Name | Model | Group | Create | Read | Write | Unlink |
|----------|-------|-------|--------|------|-------|--------|
| `access_livechat_channel_user` | `im_livechat.channel` | `group_livechat_user` | 0 | 0 | 0 | 0 |
| `access_livechat_channel_manager` | `im_livechat.channel` | `group_livechat_manager` | 1 | 1 | 1 | 1 |
| `access_livechat_channel_rule_user` | `im_livechat.channel.rule` | `group_livechat_user` | 1 | 1 | 1 | 0 |
| `access_livechat_channel_rule_manager` | `im_livechat.channel.rule` | `group_livechat_manager` | 1 | 1 | 1 | 1 |
| `access_livechat_expertise_internal_user` | `im_livechat.expertise` | `base.group_user` | 0 | 0 | 0 | 0 |
| `access_livechat_expertise_livechat_manager` | `im_livechat.expertise` | `group_livechat_manager` | 1 | 1 | 1 | 1 |
| `access_livechat_conversation_tag_livechat_user` | `im_livechat.conversation.tag` | `group_livechat_user` | 1 | 1 | 1 | 0 |
| `access_chatbot_script_user` | `chatbot.script` | `group_livechat_manager` | 1 | 1 | 1 | 1 |
| `access_chatbot_script_step_user` | `chatbot.script.step` | `group_livechat_manager` | 1 | 1 | 1 | 1 |
| `access_chatbot_script_answer` | `chatbot.script.answer` | (public) | 0 | 0 | 0 | 0 |
| `access_chatbot_script_answer_user` | `chatbot.script.answer` | `group_livechat_manager` | 1 | 1 | 1 | 1 |
| `access_chatbot_message_user` | `chatbot.message` | `group_livechat_manager` | 1 | 1 | 1 | 1 |
| `access_im_livechat_channel_member_history_user` | `history` | `group_livechat_user` | 0 | 0 | 0 | 0 |

**L4 — Notable:** `im_livechat.channel` has no create/write ACL for `group_livechat_user` — only managers can create/modify channels. Regular operators can only be assigned to existing channels. `chatbot.script.answer` with no group ACL: only accessible through the manager ACL or via the Many2one relationship from steps.

### res.groups Override

**File:** `models/res_groups.py`

When a group that implies `im_livechat_group_user` loses that implication (user demoted from livechat role), the `write` override removes the user from all livechat channel `user_ids`.

---

## Controllers

### main.py — LivechatController

#### `get_session` (`/im_livechat/get_session`)

Primary session creation endpoint. Called when visitor clicks the chat button.

**Auth:** `auth='public'` — accessible by anonymous website visitors.

**Flow:**
1. Resolve `im_livechat.channel` (sudo)
2. Determine visitor country: logged-in user's `country_id` or GeoIP
3. Call `livechat_channel._get_operator_info()` to select operator/bot
4. If `not persisted` (temporary widget): return non-persisted channel info with welcome steps
5. If persisted: create `mail.guest` for anonymous, then `discuss.channel`
6. Post welcome steps if chatbot
7. Broadcast to operator (add operator's partner to channel)
8. Return store data + `channel_id`

**GeoIP dependency:** `request.geoip.country_code` must be available (requires GeoIP database on server).

#### `feedback` (`/im_livechat/feedback`)

**Auth:** `auth='public'`
**Limit:** One rating per session (enforced in code). Updates existing rating if re-submitted.

#### `history_pages` (`/im_livechat/history`)

**Auth:** `auth='public'` — but validates that `pid` is in channel's members before sending history.

#### `download_transcript` (`/im_livechat/download_transcript/<id>`)

**Auth:** `auth='public'` — but `mail.guest` cookie or session validates channel access. Renders `im_livechat.action_report_livechat_conversation` as inline PDF.

#### `visitor_leave_session` (`/im_livechat/visitor_leave_session`)

**Auth:** `auth='public'`
Calls `_close_livechat_session()`: sets `livechat_end_dt`, notifies operator, posts "Visitor left" message.

---

### channel.py — LivechatChannelController

Session management endpoints for internal users (require `auth='user'`).

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `livechat_session_update_note` | POST | Update `livechat_note` |
| `livechat_session_update_status` | POST | Update `livechat_status` |
| `livechat_conversation_update_tags` | POST | Add/remove conversation tags |
| `livechat_conversation_write_expertises` | POST | Update `livechat_expertise_ids` on channel |
| `livechat_conversation_create_and_link_expertise` | POST | Create new expertise + link to channel |

All require `auth='user'` and reject share (portal) users.

---

### chatbot.py — LivechatChatbotScriptController

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `chatbot_restart` | public | Clear state, restart script |
| `chatbot_save_answer` | public | Save selected answer to `chatbot.message` |
| `chatbot_trigger_step` | public | Process visitor input, advance script |
| `chatbot_validate_email` | public | Validate email input, post error if invalid |

**`chatbot_trigger_step` return behavior:** If `next_step` is falsy (end of script), closes the channel (`livechat_end_dt = now()`), sends `resolve_data_request()` to frontend (closing the input UI), and returns `None`. The frontend receives this and closes the chat window.

---

## Garbage Collection

Two `@api.autovacuum` methods handle cleanup:

### `_gc_unpin_livechat_sessions` (discuss.channel.member)

- Runs on the `discuss.channel.member` model
- Threshold: 24 hours of inactivity (`last_seen_dt <= now - 1 day`)
- Condition: `is_pinned=True` AND `message_unread_counter == 0`
- Action: sets `unpin_dt`, sets `livechat_end_dt` on channel, sends `close_chat_window` bus notification

### `_gc_empty_livechat_sessions` (discuss.channel)

- Threshold: 1 hour old, no messages
- Action: `unlink()` — permanent deletion

### `_gc_bot_only_ongoing_sessions` (discuss.channel)

- Threshold: 1 day of inactivity, no agent members
- Action: sets `livechat_end_dt = now()` (closes session)
- Catches bot-only sessions where the bot ran but the visitor never converted

### discuss.channel.rtc.session `_gc_inactive_sessions`

Called at the start of `_get_operator()` to clean up stale WebRTC sessions. This is the mitigation for the FIXME noted in the operator routing code regarding inactive RTC sessions blocking operator availability.

---

## "Need Help" Escalation Workflow

The `livechat_status = 'need_help'` field enables peer-to-peer escalation:

1. **Agent requests help:** Calls `livechat_session_update_status` with `livechat_status='need_help'`
2. **Bus notification sent:** `im_livechat.looking_for_help/update` published to `(group, 'LOOKING_FOR_HELP')` subchannel
3. **Other operators subscribed:** Via `ir.websocket._build_bus_channel_list` adding the group subchannel
4. **Frontend displays banner:** Other operators see the waiting session in their UI
5. **Another agent joins:** `_add_members` is called; `livechat_status` auto-resets to `'in_progress'`
6. **Expertise tagging:** Agents can tag the escalated session with expertise (`livechat_expertise_ids`) to attract the right helpers

**L4 — Bus channel security:** The `LOOKING_FOR_HELP` subchannel is scoped to `im_livechat_group_user`. Portal users and non-livechat internal users cannot subscribe, preventing information leakage.

---

## Store API / Realtime Sync

`discuss.channel` overrides `_sync_field_names` and `_to_store_defaults` to inject livechat fields into the Odoo Discuss Store (the JSON payload sent to the frontend WebSocket client):

**Internal users receive:**
- `livechat_channel_id`, `livechat_note`, `livechat_status`, `livechat_outcome`
- `livechat_expertise_ids` (names), `livechat_conversation_tag_ids` (names + colors)
- `description` (channel description field)

**All users (including public/guest) receive:**
- `livechat_operator_id` (with avatar and livechat username)
- `country_id` (code + name)
- `livechat_end_dt`

**`livechat_member_type` in member store:** `_to_store_defaults` adds `livechat_member_type` to the store for livechat channel members, enabling the frontend to render visitor/agent/bot badges.

---

## Odoo 18 → 19 Changes

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| **Operator preferences** | Direct fields on `res.users` | Indirect via `res.users.settings` (computed/inverse) |
| **Guest identification** | `mail.guest` was less integrated | Full `mail.guest` cookie + guest reconciliation in member create |
| **History model** | Likely simpler tracking | Central `im_livechat.channel.member.history` with full reporting aggregates |
| **Group security** | Implied groups mechanism | `im_livechat_group_user`/`_manager` with `privilege_live_chat` |
| **IR rules** | Basic read rules | Record rules on channel, member, call history |
| **"need_help" status** | Not present | New `livechat_status='need_help'` + bus subchannel |
| **Session capacity** | Basic operator count | `max_sessions_mode` + `block_assignment_during_call` + `remaining_session_capacity` |
| **Bot avatar** | Stored on chatbot | Related to `operator_partner_id.image_1920` with readonly=False |
| **Embedded assets** | Single bundle | Three separate bundles: core, external, CORS |
| **Chatbot branching** | Basic next-step | `triggering_answer_ids` with AND/OR conditional logic |
| **Welcome steps** | All steps as messages | Memory-only welcome steps; only interactive steps create DB messages |

---

## Access Control Summary

| Actor | Access Level |
|-------|-------------|
| Anonymous website visitor | Initiate chat (via `get_session`), submit feedback, interact with chatbot |
| Authenticated portal user | Same as anonymous + view own session history |
| `im_livechat_group_user` | View all livechat channels, chat as operator, update status/tags/expertise |
| `im_livechat_group_manager` | Full CRUD on channels, rules, chatbots, expertise, tags |
| `base.group_user` (non-livechat) | Cannot access livechat channels (ir.rule blocks non-livechat users) |
| `base.group_public` | Read-only on expertise (no write) |

---

## Related Modules

| Module | Relationship |
|--------|-------------|
| `website_livechat` | Website-specific widget integration; depends on `im_livechat` |
| `im_livechat_mail_channel` | Email-to-chat gateway (not in core) |
| `crm` / `helpdesk` | Bridge modules extend `chatbot.script.step` with `create_lead` / `create_ticket` step types |
| `mail` | Core dependency: `discuss.channel`, `mail.message`, `mail.guest` |
| `rating` | Rating submission and satisfaction tracking |
| `bus` | Real-time WebSocket notifications |
| `digest` | KPI reporting |
| `utm` | Campaign attribution for chatbot-initiated leads |

---

## See Also

- [Modules/mail](Modules/mail.md) — Core messaging
- [Modules/rating](Modules/rating.md) — Customer ratings
- [Modules/im_livechat](Modules/im_livechat.md) — Discussion channels
- [Modules/bus](Modules/bus.md) — WebSocket bus system
- [Core/API](Core/API.md) — @api.model, @api.depends, computed fields
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) — State machine patterns
