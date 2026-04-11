---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #livechat
  - #chatbot
  - #im_livechat
  - #website
---

# website_livechat

## Table of Contents

- [Overview](#overview)
- [Module Hierarchy and Dependencies](#module-hierarchy-and-dependencies)
- [im_livechat Models](#im_livechat-models)
  - [im_livechat.channel](#im_livechatchannel)
  - [im_livechat.channel.rule](#im_livechatchannelrule)
  - [chatbot.script](#chatbotscript)
  - [chatbot.script.step](#chatbotscriptstep)
  - [chatbot.script.answer](#chatbotscriptanswer)
  - [chatbot.message](#chatbotmessage)
  - [discuss.channel (Livechat Extension)](#discusschannel-livechat-extension)
  - [discuss.channel.member (Livechat Extension)](#discusschannelmember-livechat-extension)
  - [im_livechat.channel.member.history](#im_livechatchannelmemberhistory)
  - [im_livechat.expertise](#im_livechatexpertise)
  - [im_livechat.conversation.tag](#im_livechatconversationtag)
  - [im_livechat.report.channel](#im_livechatreportchannel)
  - [res.partner (Livechat Extension)](#respartner-livechat-extension)
  - [res.users (Livechat Extension)](#resusers-livechat-extension)
  - [res.users.settings (Livechat Extension)](#resuserssettings-livechat-extension)
  - [mail.message (Livechat Extension)](#mailmessage-livechat-extension)
  - [rating.rating (Livechat Extension)](#ratingrating-livechat-extension)
- [website_livechat Models](#website_livechat-models)
  - [im_livechat.channel (Website Extension)](#im_livechatchannel-website-extension)
  - [discuss.channel (Website Extension)](#discusschannel-website-extension)
  - [chatbot.script (Website Extension)](#chatbotscript-website-extension)
  - [chatbot.script.step (Website Extension)](#chatbotscriptstep-website-extension)
  - [website.visitor (Livechat Extension)](#websitevisitor-livechat-extension)
  - [website (Livechat Extension)](#website-livechat-extension)
  - [ir.http (Livechat Extension)](#irhttp-livechat-extension)
  - [website.page (Livechat Extension)](#websitepage-livechat-extension)
- [Key Business Flows](#key-business-flows)
  - [Channel Creation and Session Initiation](#channel-creation-and-session-initiation)
  - [Operator Assignment Logic](#operator-assignment-logic)
  - [Chatbot Script Execution](#chatbot-script-execution)
  - [Session Closure and Rating](#session-closure-and-rating)
  - [Forwarding to Human Operator](#forwarding-to-human-operator)
- [L3: Edge Cases and Escalation Scenarios](#l3-edge-cases-and-escalation-scenarios)
  - [Cross-Model Interactions](#cross-model-interactions)
  - [Operator Override Patterns](#operator-override-patterns)
  - [Workflow Triggers](#workflow-triggers)
  - [Failure Modes](#failure-modes)
- [L4: Performance, Historical Changes, and Security](#l4-performance-historical-changes-and-security)
  - [Odoo 18 to Odoo 19 Changes](#odoo-18-to-odoo-19-changes)
  - [Performance Considerations](#performance-considerations)
  - [Security Model](#security-model)
  - [Garbage Collection](#garbage-collection)
  - [Buffer Time Mechanism](#buffer-time-mechanism)

---

## Overview

`website_livechat` is a composite module covering two logical layers:

- **`im_livechat`** (core livechat engine): Handles channel management, operator routing, chatbot scripting, conversation history, analytics reporting, and visitor/agent session tracking. Depends on `mail`, `rating`, `digest`, and `utm`.
- **`website_livechat`** (website integration layer): Bridges `im_livechat` with the `website` module, enabling the livechat widget on website pages, visitor tracking, and chat request initiation from the operator side. Depends on `website` and `im_livechat`.

This document uses the convention `im_livechat.*` for the core module's models and `website_livechat.*` for the website integration layer's models.

---

## Module Hierarchy and Dependencies

```
mail
 └── im_livechat              (website/livechat)
      ├── chatbot.script
      ├── chatbot.script.step
      ├── chatbot.script.answer
      ├── chatbot.message
      ├── im_livechat.channel         ← channel config + operator routing
      ├── im_livechat.channel.rule    ← URL/country-based routing rules
      ├── im_livechat.expertise       ← operator skill/topic tagging
      ├── im_livechat.conversation.tag ← conversation tagging
      ├── im_livechat.channel.member.history ← session history/analytics
      ├── im_livechat.report.channel  ← reporting (read-only SQL)
      ├── discuss.channel             ← livechat conversation sessions
      ├── discuss.channel.member      ← member metadata (type, expertise)
      ├── discuss.channel.rlc_session
      ├── discuss.call.history
      ├── res.partner (extend)
      ├── res.users (extend)
      ├── res.users.settings (extend)
      ├── mail.message (extend)
      └── rating.rating (extend)

website
 └── website_livechat          (website/livechat)
      ├── im_livechat.channel (extend) ← links channel to website
      ├── discuss.channel (extend)      ← website visitor tracking
      ├── chatbot.script (extend)       ← test action
      ├── chatbot.script.step (extend)  ← visitor data enrichment
      ├── website.visitor (extend)      ← livechat session tracking
      ├── website (extend)              ← channel-per-website config
      ├── website.page (extend)        ← livechat info injection
      └── ir.http (extend)             ← frontend translation inclusion
```

---

## im_livechat Models

### im_livechat.channel

**`im_livechat.channel`** is the central configuration model for a livechat service. It defines operators, UI branding (colors, button text), session limits, and aggregates channel statistics.

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `Char` | required | Channel display name |
| `button_text` | `Char` | `"Need help? Chat with us."` | Label on the livechat widget button |
| `default_message` | `Char` | `"How may I help you?"` | Automated welcome message shown when the chat window opens |
| `header_background_color` | `Char` | `"#875A7B"` | CSS color for the channel header |
| `title_color` | `Char` | `"#FFFFFF"` | CSS color for the title text in the header |
| `button_background_color` | `Char` | `"#875A7B"` | CSS color for the button background |
| `button_text_color` | `Char` | `"#FFFFFF"` | CSS color for the button text |
| `max_sessions_mode` | `Selection` | `"unlimited"` | `"unlimited"` or `"limited"` — controls per-operator session caps |
| `max_sessions` | `Integer` | `10` | Maximum concurrent sessions per operator (only when mode is `"limited"`) |
| `block_assignment_during_call` | `Boolean` | `False` | When `True`, operators currently in a call are excluded from new session assignment |
| `review_link` | `Char` | `False` | Optional URL — visitors who leave a positive rating are redirected here |
| `web_page` | `Char` (computed) | readonly | Static support page URL: `{base_url}/im_livechat/support/{id}` |
| `are_you_inside` | `Boolean` (computed) | readonly | `True` if the current user is an operator in this channel |
| `available_operator_ids` | `Many2many res.users` (computed) | readonly | Operators currently online and within session capacity |
| `script_external` | `Html` (computed) | readonly | Embeddable `<script>` tag for external (non-Odoo) websites |
| `nbr_channel` | `Integer` (computed) | readonly | Total count of all-time conversation sessions on this channel |
| `user_ids` | `Many2many res.users` | current user | List of operators assigned to this channel |
| `channel_ids` | `One2many discuss.channel` | | All livechat sessions ever created on this channel |
| `chatbot_script_count` | `Integer` (computed) | readonly | Number of chatbot scripts associated via channel rules |
| `rule_ids` | `One2many im_livechat.channel.rule` | | URL/country routing rules for this channel |
| `ongoing_session_count` | `Integer` (computed) | readonly | Current number of active sessions (open `livechat_end_dt IS NULL`) |
| `remaining_session_capacity` | `Integer` (computed) | readonly | Available capacity = `(max_sessions * len(online_users)) - ongoing_sessions` |

#### Constraints

```python
_max_sessions_mode_greater_than_zero = models.Constraint(
    "CHECK(max_sessions > 0)",
    "Concurrent session number should be greater than zero."
)
```

#### Key Methods

**`_get_livechat_discuss_channel_vals(...)`** — Constructs the `discuss.channel` record values when a visitor initiates a livechat session. Handles:
- Creating member records for both the operator and the visitor (or guest)
- Setting `livechat_operator_id`, `livechat_channel_id`, `livechat_status`
- Setting the `chatbot_current_step_id` to the last welcome step if a chatbot script is attached
- Deriving the channel name from visitor/guest + operator names

Signature:
```python
def _get_livechat_discuss_channel_vals(
    self, /, *, chatbot_script=None, agent=None,
    operator_partner, operator_model, **kwargs
) -> dict
```

**`_get_operator_info(...)`** — Determines which operator (or chatbot) will handle the incoming session based on routing priority:
1. If a `chatbot_script_id` is provided and valid in channel rules → chatbot takes over
2. Otherwise → calls `_get_operator(...)` to select a human agent

Signature:
```python
def _get_operator_info(
    self, /, *, lang, country_id, previous_operator_id=None, chatbot_script_id=None, **kwargs
) -> dict  # {'agent', 'chatbot_script', 'operator_partner', 'operator_model'}
```

**`_get_operator(...)`** — Core operator selection algorithm. Accepts optional `lang`, `country_id`, `expertises`, and `users` filters. Uses a preference hierarchy:

1. Same language + all expertises match
2. Same language + one expertise match
3. Same language only
4. Same country + all expertises
5. Same country + one expertise
6. Same country only
7. All expertises
8. One expertise
9. Any operator (fallback)

Within each tier, prefers operators with fewer active chats. Excludes operators who are:
- Not online (`presence_ids.status != "online"`)
- At their session cap (`max_sessions_mode == "limited"`)
- In a call when `block_assignment_during_call == True`

Also applies a **buffer time** (`BUFFER_TIME = 120s`): an operator who was just assigned a session within the last 2 minutes is deprioritized unless they are the only qualified match.

Signature:
```python
def _get_operator(
    self, previous_operator_id=None, lang=None,
    country_id=None, expertises=None, users=None
) -> res.users
```

**`_get_less_active_operator(...)`** — Helper that selects from a filtered set of operators, preferring those with no active sessions, then sorting by `(active_session_count ASC, in_call ASC)`. Random selection among equals to distribute load.

**`_get_available_operators_by_livechat_channel(...)`** — Returns a mapping of `{livechat_channel: available_users}` based on online status and session capacity.

**`_get_ongoing_session_count_by_agent_livechat_channel(...)`** — Returns `{ (partner, channel): session_count }` using `_read_group` on `discuss.channel.member`, counting members where `livechat_end_dt IS NULL` and `last_interest_dt >= "-15M"`. Optionally filters to only online agents.

**`get_livechat_info(username=None)`** — Public API for the livechat widget. Returns:
```python
{
    'available': bool,           # has chatbot or operators
    'server_url': str,
    'websocket_worker_version': str,
    'options': {                  # only if available
        'header_background_color', 'button_background_color',
        'title_color', 'button_text_color', 'button_text',
        'default_message', 'channel_name', 'channel_id', 'review_link',
        'default_username'
    }
}
```

**`_is_livechat_available()`** — Returns `True` if `chatbot_script_count > 0` or `len(available_operator_ids) > 0`.

---

### im_livechat.channel.rule

**`im_livechat.channel.rule`** defines URL-pattern and country-based routing for a livechat channel. Rules determine whether and how the livechat button appears on a given webpage.

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `regex_url` | `Char` | `False` | Regular expression matched against the visitor's current URL |
| `action` | `Selection` | `"display_button"` | `"display_button"` / `"display_button_and_text"` / `"auto_popup"` / `"hide_button"` |
| `auto_popup_timer` | `Integer` | `0` | Seconds before auto-opening the chat window (requires `action='auto_popup'`) |
| `chatbot_script_id` | `Many2one chatbot.script` | `False` | Optional chatbot script for this rule |
| `chatbot_enabled_condition` | `Selection` | `"always"` | `"always"` / `"only_if_no_operator"` / `"only_if_operator"` |
| `channel_id` | `Many2one im_livechat.channel` | required | The channel this rule belongs to |
| `country_ids` | `Many2many res.country` | `False` | Countries for which this rule applies (empty = all countries) |
| `sequence` | `Integer` | `10` | Rule matching priority — lowest sequence wins |

#### Key Method: `match_rule(channel_id, url, country_id=False)`

Finds the first matching rule for a given channel, URL, and optional country. Matching logic:
1. If `country_id` provided, search country-specific rules first
2. Fall back to rules without countries
3. Within each set, iterate in sequence order; first match wins
4. If `chatbot_script_id` is set, it must be `active` and have steps
5. If `chatbot_enabled_condition` is set, operator availability is checked

```python
def match_rule(self, channel_id, url, country_id=False) -> 'im_livechat.channel.rule'
```

---

### chatbot.script

**`chatbot.script`** defines an automated conversation flow (bot) with multiple steps. Each script is tied to an operator partner who acts as the bot persona.

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `title` | `Char` | required, translatable | Bot display name (mirrored to `operator_partner_id.name`) |
| `active` | `Boolean` | `True` | Whether the script can be used in livechat rules |
| `image_1920` | `Image` | readonly (related) | Avatar image, sourced from `operator_partner_id.image_1920` |
| `script_step_ids` | `One2many chatbot.script.step` | | Ordered steps in the script |
| `operator_partner_id` | `Many2one res.partner` | required | Partner record representing the bot (auto-created on script creation if not provided) |
| `livechat_channel_count` | `Integer` (computed) | readonly | Number of livechat channels using this script |
| `first_step_warning` | `Selection` (computed) | `False` | `"first_step_operator"` or `"first_step_invalid"` if the script's first interactive step is misconfigured |

#### Constraints

```python
@api.constrains("script_step_ids")
def _check_question_selection(self):
    for step in self.script_step_ids:
        if step.step_type == "question_selection" and not step.answer_ids:
            raise ValidationError("Step of type 'Question' must have answers.")
```

#### Key Methods

**`_get_welcome_steps()`** — Returns the subset of `script_step_ids` that constitute "welcoming steps" — all steps before the first interactive step (non-`text` type). Welcome messages are posted as a batch when the visitor first interacts with the bot, without being persisted as individual `mail.message` records initially. This avoids bloating channels with bot messages when the visitor never responds.

**`_post_welcome_steps(discuss_channel)`** — Iterates through welcome steps, posting each as a `mail.message` with the bot as author. Sets `chatbot_current_step_id` on each iteration so downstream hooks see the correct step.

**`_get_chatbot_language()`** — Returns the language code based on the `frontend_lang` cookie, falling back to the system default.

**`action_view_livechat_channels()`** — Returns an action window for all `im_livechat.channel` records that have a rule referencing this chatbot script.

**`create(vals_list)`** — Auto-creates a `res.partner` record for the bot if `operator_partner_id` is not provided, naming it after the script `title` and setting `active=False`.

**`write(vals)`** — Syncs `operator_partner_id.name` when `title` changes.

**`copy(default=None)`** — Deep-copies the script, including all steps and answers. Special handling is needed for `triggering_answer_ids` because references must point to the cloned answers, not the originals. Uses `zip()` to match original and clone steps in creation order.

---

### chatbot.script.step

**`chatbot.script.step`** represents a single node in a chatbot script. Steps can display text, ask questions, collect email/phone, or trigger a transfer to a human operator.

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `Char` (computed) | readonly | Auto-generated display name: `"{title} - Step {sequence}"` |
| `message` | `Html` (translatable) | | The bot's message content |
| `sequence` | `Integer` | auto-incremented | Order within the script |
| `chatbot_script_id` | `Many2one chatbot.script` | required, cascade delete | Parent script |
| `step_type` | `Selection` | `"text"` | `"text"` / `"question_selection"` / `"question_email"` / `"question_phone"` / `"forward_operator"` / `"free_input_single"` / `"free_input_multi"` |
| `answer_ids` | `One2many chatbot.script.answer` | | Available answers (only for `"question_selection"`) |
| `triggering_answer_ids` | `Many2many chatbot.script.answer` | | Conditional: show this step only if all of these answers were selected |
| `is_forward_operator` | `Boolean` (computed) | readonly | `True` if `step_type == "forward_operator"` |
| `is_forward_operator_child` | `Boolean` (computed) | readonly | `True` if this step is a descendant of a forward-operator step in the script tree |
| `operator_expertise_ids` | `Many2many im_livechat.expertise` | | When forwarding, prioritize operators with these expertises |

#### Computed Logic

**`_compute_is_forward_operator_child`** — Traverses the script step tree to determine if the current step is reachable only after a forward-to-operator step. This affects how the UI handles the transition and is used in analytics.

**`_compute_triggering_answer_ids`** — On write, automatically removes any triggering answers that belong to steps at the same or later sequence (prevents circular/forward dependencies).

**`_compute_name`** — Generates `"Chatbot Title - Step N"` for display in the script editor.

#### Key Methods

**`create(vals_list)`** — Auto-assigns sequences. For each chatbot, finds the current max sequence and increments from there. Manual sequence values in `vals` are respected (and become the new baseline).

**`_fetch_next_step(selected_answer_ids)`** — Core navigation logic. Finds the next step after the current one:
- If `triggering_answer_ids` is empty → returns the first step with higher sequence
- If `triggering_answer_ids` is set → evaluates AND/OR logic across steps:
  - Multiple triggering answers from the **same step** → OR condition
  - Multiple triggering answers from **different steps** → AND condition

**`_is_last_step(discuss_channel=False)`** — Returns `True` if:
1. `step_type != "question_selection"` AND
2. `_fetch_next_step(...)` returns empty

**`_process_answer(discuss_channel, message_body)`** — Called when a visitor responds to a step:
- Validates email format for `"question_email"` steps
- Stores raw answer HTML for text-input steps (`question_email`, `question_phone`, `free_input_single`, `free_input_multi`)
- Returns the next `_fetch_next_step(...)` result

**`_process_step(discuss_channel)`** — Called when execution reaches a step:
- `"forward_operator"` → calls `discuss_channel._forward_human_operator(...)`
- Otherwise → posts the `message` as a `mail.message` from the bot's partner

**`_chatbot_prepare_customer_values(discuss_channel, create_partner=True, update_partner=True)`** — Extracts customer data (email, phone, description) from chatbot message history and creates/updates a `res.partner` accordingly:
- Public user → creates a new partner named after the email
- Authenticated user → updates the current user's partner (if not already set)
- Returns `{'partner', 'email', 'phone', 'description'}` for use in CRM leads, helpdesk tickets, etc.

**`_find_first_user_free_input(discuss_channel)`** — Scans chatbot messages to find the first user response to a `free_input` step. Used when forwarding to ensure the human operator sees what the visitor typed.

**`_get_parent_step(all_parent_steps)`** — Traverses backward through the script to find the nearest qualifying parent step. Used by `_compute_is_forward_operator_child`.

---

### chatbot.script.answer

**`chatbot.script.answer`** represents a selectable option within a `"question_selection"` step.

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `Char` (translatable) | required | Answer text shown to the visitor |
| `sequence` | `Integer` | `1` | Display order within the step |
| `redirect_link` | `Char` | `False` | URL opened when visitor clicks this answer (only works for same-origin links) |
| `script_step_id` | `Many2one chatbot.script.step` | required, cascade delete | Parent step |
| `chatbot_script_id` | `Many2one` (related) | readonly | Convenience reference to parent script |

#### Display Logic

**`_compute_display_name`** — When `chatbot_script_answer_display_short_name` is in context, shows only the answer text. Otherwise, prepends the step's message truncated to 26 characters: `"What do you want...: Create Lead"`.

---

### chatbot.message

**`chatbot.message`** stores the relationship between a `mail.message` in a livechat channel and the `chatbot.script.step` that generated it, plus the visitor's selected answer or typed input.

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `mail_message_id` | `Many2one mail.message` | required | The actual chat message record |
| `discuss_channel_id` | `Many2one discuss.channel` | required, cascade delete | Channel this message belongs to |
| `script_step_id` | `Many2one chatbot.script.step` | index (btree_not_null) | Step that generated this message |
| `user_script_answer_id` | `Many2one chatbot.script.answer` | set null | Visitor's selected answer |
| `user_raw_script_answer_id` | `Integer` | | ID of the answer record at creation time (preserved even if answer is deleted, for analytics) |
| `user_raw_answer` | `Html` | | Raw HTML of the visitor's free-text input (email/phone/free input steps) |

#### Constraints

```python
_unique_mail_message_id = models.Constraint(
    'unique (mail_message_id)',
    'A mail.message can only be linked to a single chatbot message',
)
_channel_id_user_raw_script_answer_id_idx = models.Index(
    "(discuss_channel_id, user_raw_script_answer_id) WHERE user_raw_script_answer_id IS NOT NULL",
)
```

---

### discuss.channel (Livechat Extension)

The `discuss.channel` model is extended from `mail.discuss.channel` to add livechat-specific fields, status tracking, and business logic. A `discuss.channel` with `channel_type = 'livechat'` represents a single visitor-operator conversation session.

#### Fields Added for Livechat

| Field | Type | Description |
|---|---|---|
| `channel_type` | `Selection` (extended) | Adds `"livechat"` option with `ondelete='cascade'` |
| `duration` | `Float` (computed) | Session length in hours: `(livechat_end_dt - create_date) / 3600` |
| `livechat_lang_id` | `Many2one res.lang` | Language preference of the visitor |
| `livechat_end_dt` | `Datetime` | When the session was closed |
| `livechat_channel_id` | `Many2one im_livechat.channel` | The channel configuration used |
| `livechat_operator_id` | `Many2one res.partner` | The assigned operator's partner |
| `livechat_channel_member_history_ids` | `One2many im_livechat.channel.member.history` | Historical session data |
| `livechat_expertise_ids` | `Many2many im_livechat.expertise` (stored) | Expertises relevant to this conversation |
| `livechat_agent_history_ids` | `One2many` (computed/searchable) | Filtered: `livechat_member_type == "agent"` |
| `livechat_bot_history_ids` | `One2many` (computed/searchable) | Filtered: `livechat_member_type == "bot"` |
| `livechat_customer_history_ids` | `One2many` (computed/searchable) | Filtered: `livechat_member_type == "visitor"` |
| `livechat_agent_partner_ids` | `Many2many res.partner` (stored) | All agent partners who ever served this session |
| `livechat_bot_partner_ids` | `Many2many res.partner` (stored) | All bot partners in this session |
| `livechat_customer_partner_ids` | `Many2many res.partner` (stored) | Customer partner(s) in this session |
| `livechat_customer_guest_ids` | `Many2many mail.guest` (computed) | Unauthenticated visitor guests |
| `livechat_agent_requesting_help_history` | `Many2one` (computed, stored) | The first agent in an escalated session |
| `livechat_agent_providing_help_history` | `Many2one` (computed, stored) | The final agent in an escalated session |
| `livechat_note` | `Html` | Internal operator notes (group-restricted) |
| `livechat_status` | `Selection` (computed, writable) | `"in_progress"` / `"waiting"` / `"need_help"` |
| `livechat_outcome` | `Selection` (computed, stored) | `"no_answer"` / `"no_agent"` / `"no_failure"` / `"escalated"` |
| `livechat_conversation_tag_ids` | `Many2many im_livechat.conversation.tag` | Conversation classification tags |
| `livechat_start_hour` | `Float` (computed, stored) | Hour of day the session started (0-23) |
| `livechat_week_day` | `Selection` (computed, stored) | Day of week (`"0"=Monday` ... `"6"=Sunday`) |
| `livechat_matches_self_lang` | `Boolean` (computed, searchable) | Does session language match current operator's lang? |
| `livechat_matches_self_expertise` | `Boolean` (computed, searchable) | Does session expertise match current operator's? |
| `chatbot_current_step_id` | `Many2one chatbot.script.step` | Active step in the chatbot flow |
| `chatbot_message_ids` | `One2many chatbot.message` | All chatbot messages in this session |
| `country_id` | `Many2one res.country` | Visitor's country |
| `livechat_failure` | `Selection` | `"no_answer"` / `"no_agent"` / `"no_failure"` |
| `livechat_is_escalated` | `Boolean` (computed, stored) | `True` if more than one agent has served this session |
| `rating_last_text` | `Selection` (stored) | Cached rating text label |

#### Database Constraints

```python
_livechat_operator_id = models.Constraint(
    "CHECK((channel_type = 'livechat' and livechat_operator_id is not null) or "
    "(channel_type != 'livechat'))",
    'Livechat Operator ID is required for a channel of type livechat.',
)
_livechat_end_dt_status_constraint = models.Constraint(
    "CHECK(livechat_end_dt IS NULL or livechat_status IS NULL)",
    "Closed Live Chat session should not have a status.",
)
```

#### Indexes

```python
_livechat_end_dt_idx = models.Index("(livechat_end_dt) WHERE livechat_end_dt IS NULL")
_livechat_failure_idx = models.Index(
    "(livechat_failure) WHERE livechat_failure IN ('no_answer', 'no_agent')"
)
_livechat_is_escalated_idx = models.Index(
    "(livechat_is_escalated) WHERE livechat_is_escalated IS TRUE"
)
_livechat_channel_type_create_date_idx = models.Index(
    "(channel_type, create_date) WHERE channel_type = 'livechat'"
)
```

#### Key Methods

**`_close_livechat_session(**kwargs)`** — Ends the session:
1. Leaves any active RTC call
2. Sets `livechat_end_dt = now()`
3. Posts a system notification message (visitor left / cancelled)
4. Broadcasts `livechat_end_dt` via the bus channel

**`_chatbot_find_customer_values_in_messages(step_type_to_field)`** — Scans `chatbot_message_ids` to extract email/phone from question steps. Used by CRM/helpdesk integrations to pre-populate lead/ticket fields.

**`_forward_human_operator(chatbot_script_step=None, users=None)`** — Escalation handler:
1. Calls `_get_human_operator(...)` to find an available operator (respecting expertise preferences from `chatbot_script_step.operator_expertise_ids`)
2. Posts the current chatbot step message
3. Adds the human operator as a channel member with `livechat_member_type = "agent"`
4. Removes the bot member
5. Updates channel name, operator, and expertise tags
6. Sets `livechat_failure = "no_answer"` if no operator is found (the chatbot continues running)

**`_get_human_operator(users, chatbot_script_step)`** — Wrapper around `livechat_channel_id._get_operator(...)`, passing expertise preferences from the chatbot step.

**`_add_members(...)`** (override) — When a new operator joins a `"need_help"` channel, automatically transitions `livechat_status` back to `"in_progress"`.

**`_message_post_after_hook(message, msg_vals)`** — After every message posted:
- Creates a `chatbot.message` record linking the message to the current step
- Updates `author_history.message_count`
- Records `response_time_hour` for the first agent message
- Updates `livechat_status` from `"waiting"` to `"in_progress"` when the visitor responds
- Sets `livechat_failure = "no_failure"` when an agent first messages
- Sets `selected_answer_id` on the question's chatbot message

**`_action_unfollow(...)`** (override) — When the last operator leaves an open livechat, automatically sets `livechat_end_dt = now()`.

**`_chatbot_restart(chatbot_script)`** — Resets the bot: clears `chatbot_current_step_id`, `livechat_end_dt`, and deletes all `chatbot_message` records.

**`_rating_get_parent_field_name()`** — Returns `'livechat_channel_id'` so ratings are grouped by channel for reporting.

**`_email_livechat_transcript(email)`** — Renders and sends a transcript email to the visitor using the `im_livechat.livechat_email_template` QWeb template. Uses the customer's timezone for display.

**`_get_channel_history()`** — Formats all non-notification messages as plaintext HTML for display in transcripts and notifications.

**`_get_visitor_leave_message(operator=False, cancel=False)`** — Returns the system message shown when a visitor leaves. Returns `"Visitor left the conversation."` (or operator name if known) or `"Visitor started a conversation with X. The chat request has been cancelled"` for chat requests.

#### Garbage Collection (autovacuum)

**`_gc_empty_livechat_sessions()`** — Deletes livechat channels that:
- Have no messages, AND
- Are older than 1 hour, AND
- Have a `livechat_channel_id` set

**`_gc_bot_only_ongoing_sessions()`** — Closes sessions that:
- Have no agent members, AND
- Have been inactive for more than 1 day (`last_interest_dt <= "-1d"`), AND
- Have no `livechat_end_dt`

---

### discuss.channel.member (Livechat Extension)

**`discuss.channel.member`** is extended to track livechat-specific metadata per member: visitor/agent/bot classification, chatbot script assignment, and expertise tags.

#### Fields Added

| Field | Type | Description |
|---|---|---|
| `livechat_member_history_ids` | `One2many im_livechat.channel.member.history` | Historical session records for this member |
| `livechat_member_type` | `Selection` (computed/writable) | `"agent"` / `"visitor"` / `"bot"` |
| `chatbot_script_id` | `Many2one chatbot.script` (computed/writable) | Active chatbot for bot members |
| `agent_expertise_ids` | `Many2many im_livechat.expertise` (computed/writable) | Expertises of agent members |

#### Key Method: `create(vals_list)`

Auto-classifies new members:
- If a guest is reconciling with a previous session → `"visitor"`
- If the member is the operator → `"agent"`
- If the member is the bot partner → `"bot"`

Guest reconciliation: after a public visitor logs in, the guest cookie is still present, allowing Odoo to match the logged-in user to their previous guest session.

#### Key Method: `_create_or_update_history(values_by_member)`

Manages the `livechat_channel_member_history` record lifecycle:
- If no history exists for this `(channel, partner/guest)` pair → creates one
- If history exists but is linked to a different member record → updates the existing history's `member_id`
- Otherwise → updates the existing history with new values

#### Garbage Collection (autovacuum)

**`_gc_unpin_livechat_sessions()`** — Unpins livechat sessions with no activity for at least 1 day and zero unread messages. Sets `unpin_dt` and `livechat_end_dt`, then broadcasts `"close_chat_window": True` to the operator's bus channel.

#### RTC / Video Call Integration

**`_get_rtc_invite_members_domain(...)`** (override) — For livechat channels, excludes the chatbot operator from RTC invites.

**`_get_excluded_rtc_members_partner_ids()`** — Returns the bot's `partner_id` if the current step is a forward-operator step.

---

### im_livechat.channel.member.history

**`im_livechat.channel.member.history`** is the central analytics and history model. Each record represents one persona's participation in one livechat session. It is the primary data source for the reporting model and for digest emails.

#### Fields

| Field | Type | Description |
|---|---|---|
| `member_id` | `Many2one discuss.channel.member` (index, btree_not_null) | Current or most recent member record |
| `livechat_member_type` | `Selection` (computed, stored) | `"agent"` / `"visitor"` / `"bot"` |
| `channel_id` | `Many2one discuss.channel` (computed, stored, cascade) | Session this history belongs to |
| `guest_id` | `Many2one mail.guest` (computed, stored) | Guest visitor (if not authenticated) |
| `partner_id` | `Many2one res.partner` (computed, stored) | Authenticated visitor or agent |
| `chatbot_script_id` | `Many2one chatbot.script` (computed, stored) | Bot script used |
| `agent_expertise_ids` | `Many2many im_livechat.expertise` (computed, stored) | Expertise tags of the agent |
| `conversation_tag_ids` | `Many2many` (related) | Tags from the channel |
| `avatar_128` | `Binary` (computed) | Avatar from partner or guest |

**Reporting Fields (aggregated on `channel_id`):**

| Field | Type | Description |
|---|---|---|
| `session_country_id` | `Many2one res.country` | Visitor's country |
| `session_livechat_channel_id` | `Many2one im_livechat.channel` | Channel used |
| `session_outcome` | `Selection` | `"no_answer"` / `"no_agent"` / `"no_failure"` / `"escalated"` |
| `session_start_hour` | `Float` (computed, aggregator=`avg`) | Hour of session start |
| `session_week_day` | `Selection` (computed) | Day of week (`"0"=Monday`) |
| `session_duration_hour` | `Float` (computed, stored, aggregator=`avg`) | Time from history creation to channel end (or now if ongoing) |
| `rating_id` | `Many2one rating.rating` (computed, stored) | Rating record for this agent/bot |
| `rating` | `Float` (related) | Numeric rating value |
| `rating_text` | `Selection` (related) | `"Happy"` / `"Neutral"` / `"Unhappy"` |
| `call_history_ids` | `Many2many discuss.call.history` | Video call records |
| `has_call` | `Float` (computed, aggregator=`sum`/`avg`) | `1` if session had a call |
| `call_count` | `Float` (related) | Count of calls |
| `call_percentage` | `Float` (related) | % of sessions with calls |
| `call_duration_hour` | `Float` (computed, aggregator=`sum`) | Total call duration |
| `message_count` | `Integer` (aggregator=`avg`) | Avg messages per session |
| `help_status` | `Selection` (computed, stored) | `"requested"` / `"provided"` |
| `response_time_hour` | `Float` (aggregator=`avg`) | Avg time from session start to first agent message |

#### Constraints

```python
_member_id_unique = models.Constraint("UNIQUE(member_id)", ...)
_channel_id_partner_id_unique = models.UniqueIndex(
    "(channel_id, partner_id) WHERE partner_id IS NOT NULL", ...
)
_channel_id_guest_id_unique = models.UniqueIndex(
    "(channel_id, guest_id) WHERE guest_id IS NOT NULL", ...
)
_partner_id_or_guest_id_constraint = models.Constraint(
    "CHECK(partner_id IS NULL OR guest_id IS NULL)", ...
)
```

#### Computed Logic

**`_compute_session_duration_hour`** — For ongoing sessions (no `livechat_end_dt`), uses `last_message.create_date` as the end time to avoid counting idle time. For closed sessions, uses `livechat_end_dt`.

**`_compute_rating_id`** — Finds the rating where `rated_partner_id == history.partner_id`. Livechats only allow one rating per agent.

**`_compute_help_status`** — Used in escalated sessions:
- `"requested"` → the first agent in the session
- `"provided"` → the last agent in the session

**`_constraint_channel_id`** — Ensures history records can only be created for `channel_type == "livechat"` channels.

---

### im_livechat.expertise

**`im_livechat.expertise`** models operator skills/topics. Used in the operator routing algorithm to match visitors with agents who have relevant knowledge.

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `Char` | required, translatable | Expertise name (e.g., "Billing", "Technical Support") |
| `user_ids` | `Many2many res.users` (computed/inverse) | | Users with this expertise |

#### Inverse Logic

**`_inverse_user_ids`** — When expertise is added/removed from a user:
- Calls `user.sudo().livechat_expertise_ids` with `Command.link` or `Command.unlink`
- This writes through to `res.users.settings.livechat_expertise_ids` (the actual storage)

**`_get_users_by_expertise()`** — Reverse lookup: searches `res.users.settings` for all users with a given expertise, returns `{expertise: users}` mapping.

---

### im_livechat.conversation.tag

**`im_livechat.conversation.tag`** provides operator-applied labels to classify livechat sessions (e.g., "billing", "sales inquiry", "complaint").

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `Char` | required | Tag name |
| `color` | `Integer` | random 1-11 | Tag color for UI display |
| `conversation_ids` | `Many2many discuss.channel` | | Channels with this tag |

#### Cascade Cleanup

**`_unlink_sync_conversation()`** — When a tag is deleted, removes it from all associated channels via `Command.unlink`.

---

### im_livechat.report.channel

**`im_livechat.report.channel`** is a read-only SQL model ( `_auto = False` ) that provides aggregated analytics over livechat sessions. It is the model behind the Livechat reporting dashboard.

#### Fields (all readonly, aggregated)

| Field | Type | Aggregator | Description |
|---|---|---|---|
| `uuid` | `Char` | — | Channel UUID |
| `channel_id` | `Many2one discuss.channel` | — | Session record |
| `channel_name` | `Char` | — | Channel name |
| `livechat_channel_id` | `Many2one im_livechat.channel` | — | Channel config |
| `start_date` | `Datetime` | — | Session creation time |
| `start_hour` | `Char` | — | Hour string (`"HH24"`) |
| `start_date_minutes` | `Char` | — | Datetime truncated to hour (`"YYYY-MM-DD HH:MI:SS"`) |
| `day_number` | `Selection` | — | Day of week (`"0"=Sunday`) |
| `time_to_answer` | `Float` | `avg` | Hours from session start to first agent message |
| `duration` | `Float` | `avg` | Session duration in minutes |
| `nbr_message` | `Integer` | `avg` | Message count per session |
| `country_id` | `Many2one res.country` | — | Visitor country |
| `lang_id` | `Many2one res.lang` | — | Session language |
| `rating` | `Integer` | `avg` | Numeric rating (1/3/5) |
| `rating_text` | `Char` | — | `"Happy"` / `"Neutral"` / `"Unhappy"` |
| `partner_id` | `Many2one res.partner` | — | Operator partner |
| `handled_by_bot` | `Integer` | `sum` | Sessions with bot but no agent |
| `handled_by_agent` | `Integer` | `sum` | Sessions with an agent |
| `visitor_partner_id` | `Many2one res.partner` | — | Customer partner |
| `call_duration_hour` | `Float` | `avg` | Video call duration |
| `has_call` | `Float` | `sum`/`avg` | Sessions with a call |
| `session_outcome` | `Selection` | — | `"no_answer"` / `"no_agent"` / `"no_failure"` / `"escalated"` |
| `chatbot_script_id` | `Many2one chatbot.script` | — | Bot used |
| `chatbot_answers_path` | `Char` | — | IDs of answers selected (`"id1 - id2 - id3"`) |
| `chatbot_answers_path_str` | `Char` | — | Localized answer names joined with `" - "` |
| `session_expertises` | `Char` | — | Expertise names joined with `" - "` |
| `session_expertise_ids` | `Many2many im_livechat.expertise` | — | Expertise records |

#### Query Architecture

The report uses five `LEFT JOIN LATERAL` subqueries against `discuss_channel`:

1. **`channel_member_history`** — Determines `has_agent`, `has_bot`, `visitor_partner_id`, `chatbot_script_id`
2. **`message_vals`** — Counts messages and finds first agent message datetime (using `livechat_member_type` from history to distinguish agent from bot messages)
3. **`call_history_data`** — Aggregates call durations from `discuss_call_history`
4. **`chatbot_answer_history`** — Aggregates answer path as `"id - id - id"` string using `STRING_AGG`
5. **`expertise_history`** — Aggregates expertise names per session

**Duration calculation nuances:**
- If the session ended **before** the first agent message → `NULL` (invalid data)
- If the session had **both bot and agent** → duration = first agent message - last bot message (time spent with bot)
- If only agent → duration = first agent message - session start
- If only bot (legacy) → duration = first agent message (as reported by operator field) - session start

**Time-to-answer calculation nuances:**
- Same logic as duration: excludes sessions where the agent message came after the session ended
- For bot+agent sessions: measured from last bot message to first agent message

**Day ordering** — `_read_group_orderby` handles locale-aware week start: uses `MOD(7 - first_week_day + day_number, 7)` to order days starting from Monday (or Sunday depending on locale).

---

### res.partner (Livechat Extension)

#### Fields Added

| Field | Type | Description |
|---|---|---|
| `user_livechat_username` | `Char` (computed) | The livechat username of the associated user |
| `chatbot_script_ids` | `One2many chatbot.script` | Scripts where this partner is the operator |
| `livechat_channel_count` | `Integer` (computed) | Number of distinct livechat channels this partner has served as a visitor |

#### Key Methods

**`_search_for_channel_invite_to_store(store, channel)`** — Enriches partner data sent to the Discuss client for livechat channels. Adds:
- `invite_by_self_count` — how many times this partner was invited by the current user
- `is_available` — whether the partner is an active livechat operator
- `lang_name` — partner's language
- `livechat_expertise` — list of expertise names
- `livechat_languages` — additional languages the partner handles
- `user_livechat_username` — display name for the channel
- `is_in_call` — whether currently in a call

**`_get_store_livechat_username_fields()`** — Returns store fields for displaying the partner in livechat: uses `livechat_username` if set, otherwise falls back to `name`.

**`_compute_display_name()`** — When `im_livechat_hide_partner_company` is in context, portal partners show only their name (not the company name) to protect privacy.

**`action_view_livechat_sessions()`** — Returns a filtered `discuss.channel` action showing only sessions where this partner was a visitor.

---

### res.users (Livechat Extension)

#### Fields Added

| Field | Type | Groups | Description |
|---|---|---|---|
| `livechat_channel_ids` | `Many2many im_livechat.channel` | — | Channels this user is an operator for |
| `livechat_username` | `Char` | `im_livechat_group_user`, `base.group_erp_manager` | Display name in livechat conversations |
| `livechat_lang_ids` | `Many2many res.lang` | same | Additional languages the operator handles |
| `livechat_expertise_ids` | `Many2many im_livechat.expertise` | same | Operator skill tags |
| `livechat_ongoing_session_count` | `Integer` (computed) | `im_livechat_group_user` | Active session count, context-filtered by `im_livechat_channel_id` |
| `livechat_is_in_call` | `Boolean` (computed) | same | Whether the operator is in a video call |
| `has_access_livechat` | `Boolean` (computed, readonly) | — | Whether user belongs to the livechat group |

#### Computed Logic

**`_compute_livechat_username`** — Reads from `res.users.settings.livechat_username` via sudo.

**`_compute_livechat_ongoing_session_count`** — Uses `_read_group` on `im_livechat.channel.member.history`:
- Counts active sessions (no `livechat_end_dt`) from the last 15 minutes
- Context-filtered by `im_livechat_channel_id` when set

**`_compute_livechat_is_in_call`** — Returns `user.sudo().is_in_call` if the user is in any livechat channel.

**`write(vals)`** — When a user is removed from the `im_livechat_group_user` group, they are automatically unlinked from all livechat channels (`user_ids`).

#### Store Initialization

**`_init_store_data(store)`** — Adds `has_access_livechat` and `is_livechat_manager` flag to the initial Discuss store payload.

---

### res.users.settings (Livechat Extension)

Stores per-user livechat preferences that were previously on `res.users` directly.

#### Fields Added

| Field | Type | Description |
|---|---|---|
| `livechat_username` | `Char` | Display name shown to livechat visitors |
| `livechat_lang_ids` | `Many2many res.lang` | Secondary language preferences |
| `livechat_expertise_ids` | `Many2many im_livechat.expertise` | Operator skill tags |

---

### mail.message (Livechat Extension)

#### Store Extension

**`_to_store_defaults(target)`** — Adds `"chatbot_current_step"` to the default store fields for livechat messages.

**`_to_store(store, fields, **kwargs)`** — For livechat channel messages from the chatbot operator:
- Finds the associated `chatbot.message` record
- Adds `ChatbotStep` model data including:
  - `selectedAnswer` — if the visitor chose a predefined option
  - `rawAnswer` — if the visitor typed free text (email/phone/free input steps)
- Links the step data to the message via `chatbotStep`

**`_get_store_partner_name_fields()`** — For livechat channel messages, uses `_get_store_livechat_username_fields()` instead of the standard partner name, so the chatbot operator appears under its `livechat_username`.

---

### rating.rating (Livechat Extension)

#### Overrides

**`_compute_res_name()`** — For `discuss.channel` ratings, sets `res_name` to `"{channel_name} / {channel_id}"` instead of the default channel display name (which is the channel UUID for livechat channels, making it unreadable).

**`action_open_rated_object()`** — For livechat channels, redirects to the Discuss client (`mail.action_discuss`) with the channel as `active_id`, instead of opening the channel form view.

---

## website_livechat Models

### im_livechat.channel (Website Extension)

Extends `im_livechat.channel` to integrate with the website configuration and create default chatbot rules.

#### Overrides

**`_get_livechat_discuss_channel_vals(...)`** — After calling the parent method:
1. Attaches the `website.visitor` record to the channel via `livechat_visitor_id`
2. Cancels any pending operator-initiated chat requests for the same visitor to prevent conflicts between the two flows

**`create(vals_list)`** — When `create_from_website` is in context:
1. Sets the created channel as the current website's default channel
2. Creates a default rule with the welcome chatbot (`im_livechat.chatbot_script_welcome_bot`)
3. Sends a success notification to the operator

---

### discuss.channel (Website Extension)

Extends `discuss.channel` to track the `website.visitor` who initiated the session and support operator-initiated chat requests.

#### Fields Added

| Field | Type | Description |
|---|---|---|
| `is_pending_chat_request` | `Boolean` | `True` when the operator has initiated the chat but the visitor has not yet responded |
| `livechat_visitor_id` | `Many2one website.visitor` (index, btree_not_null) | The visitor who started or is linked to this session |

#### Key Methods

**`channel_pin(pinned=False)`** — Override: if an operator unpins an **empty** livechat channel, the channel is deleted. This allows operators to send a chat request, then cancel it without leaving an orphan channel.

**`_to_store_defaults(target)`** — Adds the full `livechat_visitor_id` subtree to the store, including:
- `country_id`, `display_name`, `page_visit_history`, `lang_id`, `partner_id`, `website_id`
- `requested_by_operator` — computed predicate: `True` if the channel creator is in the agent's history

**`_get_livechat_session_fields_to_store()`** — Appends to the parent's fields: includes the last 5 sessions for this visitor (last 7 days) as `livechat_visitor_id.discuss_channel_ids`.

**`message_post(**kwargs)`** — Override: when a visitor posts a message, their `last_visit` timestamp is updated via `visitor._update_visitor_last_visit()`.

**`_get_visitor_leave_message(operator=False, cancel=False)`** — Returns visitor-aware messages:
- `"Visitor #123 left the conversation."` when a known visitor leaves
- `"Visitor left the conversation."` for anonymous visitors
- `"Visitor started a conversation with Operator. The chat request has been cancelled"` for cancelled chat requests

---

### chatbot.script (Website Extension)

**`action_test_script()`** — Returns an action to open the chatbot in test mode at `/chatbot/{id}/test`.

---

### chatbot.script.step (Website Extension)

Extends `_chatbot_prepare_customer_values` from the parent step: when called from a website livechat, automatically enriches the customer values with data already known about the visitor:
- `email` — from `visitor.email` if not captured in the chatbot
- `phone` — from `visitor.mobile` if not captured
- `country` — from `visitor.country_id`

This allows CRM/helpdesk integrations to pre-populate more fields without requiring the visitor to retype information.

---

### website.visitor (Livechat Extension)

Extends `website.visitor` to track livechat sessions and active operator assignment.

#### Fields Added

| Field | Type | Description |
|---|---|---|
| `livechat_operator_id` | `Many2one res.partner` (computed, stored) | Operator the visitor is currently chatting with |
| `livechat_operator_name` | `Char` (related) | Convenience name field |
| `discuss_channel_ids` | `One2many discuss.channel` | All livechat channels for this visitor |
| `session_count` | `Integer` (computed) | Number of sessions with messages |

#### Computed Logic

**`_compute_livechat_operator_id`** — Uses `search_read` to find active sessions (no `livechat_end_dt`) and maps `livechat_visitor_id → livechat_operator_id`. Stored in the `website_visitor` table via `_auto_init` with a conditional `create_column` migration check.

**`_compute_session_count`** — Counts `discuss.channel` records with at least one message, grouped by `livechat_visitor_id`.

#### Key Methods

**`action_send_chat_request()`** — Operator-initiated chat request:
1. Validates visitor availability (no active session)
2. Validates the website has a livechat channel
3. Adds the operator to the channel's user list
4. Creates `discuss.channel` with `is_pending_chat_request = True`
5. Creates a `mail.guest` for the visitor if not authenticated
6. Opens the channel in the operator's Discuss view with `open_chat_window = True`

Called from the website visitor list view when an operator clicks "Chat with visitor."

**`_merge_visitor(target)`** — When merging secondary visitors into a main one:
1. Moves all `discuss_channel_ids` to the target visitor
2. Removes `base.public_partner` from channel membership
3. Adds the target's `partner_id` to channel membership

**`_upsert_visitor(access_token, force_track_values=None)`** — After a visitor is upserted (created or updated):
- If there is a guest in context with livechat channels, those channels are linked to the new visitor record
- Country is synced from visitor to guest channels

**`_get_visitor_history()`** — Returns the last 3 page visits (`website.track` records) as `(page_name, datetime_string)` tuples, used in the livechat widget to show the visitor's recent browsing history.

---

### website (Livechat Extension)

#### Fields Added

| Field | Type | Description |
|---|---|---|
| `channel_id` | `Many2one im_livechat.channel` | Default livechat channel for this website |

#### Method

**`_get_livechat_channel_info()`** — Returns the livechat channel info dict for the current website (button text, colors, availability). Uses `@add_guest_to_context` decorator to allow anonymous guest access.

---

### ir.http (Livechat Extension)

**`_get_translation_frontend_modules_name()`** — Adds `'im_livechat'` to the list of modules whose strings are extracted for frontend (website) translations.

---

### website.page (Livechat Extension)

**`_post_process_response_from_cache(request, response)`** — After serving a cached page response, preloads the livechat channel info for the current website so the widget renders immediately on the client side without an extra HTTP request.

---

## Key Business Flows

### Channel Creation and Session Initiation

```
Visitor clicks livechat button
  → frontend calls /im_livechat/get_session
  → im_livechat.channel.rule#match_rule(url, country_id)
    → finds applicable chatbot or continues to human routing
  → im_livechat.channel#get_livechat_info()
    → available if chatbot OR operators online
  → im_livechat.channel#get_operator_info(chatbot_script_id?, lang, country)
    → chatbot priority: chatbot_script_id in rule → chatbot script
    → human priority: _get_operator(lang, country, expertise, previous_operator)
      → buffer time check (120s cooldown)
      → preference hierarchy (lang+expertise → lang → country+expertise → ...)
      → random selection among least-loaded operators
  → im_livechat.channel#get_livechat_discuss_channel_vals()
    → creates discuss.channel with operator + visitor members
    → sets chatbot_current_step_id to last welcome step
  → discuss.channel created with channel_type='livechat'
  → chatbot.script#_post_welcome_steps()
    → posts welcome messages as mail.message from bot
  → visitor sees chat window open
```

### Operator Assignment Logic

The `_get_operator` method implements a weighted preference system:

1. **Previous operator continuity** — If the visitor has a `previous_operator_id` and that operator has < 2 active sessions and is not in a call, they get priority
2. **Buffer time** — Operators assigned within the last 120 seconds are deprioritized unless they are the only match
3. **Load balancing** — Among equal candidates, the operator with fewest active chats is chosen
4. **Preference tiers** (in priority order):
   - Same language + all expertises match
   - Same language + one expertise match
   - Same language only
   - Same country + all expertises
   - Same country + one expertise
   - Same country only
   - All expertises
   - One expertise
   - Any operator

### Chatbot Script Execution

```
Visitor submits first interaction
  → discuss.channel#message_post()
  → discuss.channel#_message_post_after_hook()
    → creates chatbot.message record
  → chatbot.script.step#_process_answer(message_body)
    → validates email format (if question_email)
    → stores raw answer HTML
    → _fetch_next_step(selected_answer_ids)
      → evaluates triggering_answer_ids conditions
      → AND between steps, OR within same step
    → returns next step
  → chatbot.script.step#_process_step(discuss_channel)
    → if forward_operator: _forward_human_operator()
    → else: _chatbot_post_message(message)
  → chatbot.script.step#_is_last_step()
    → no next step found → conversation can end
```

### Session Closure and Rating

```
Visitor or operator closes chat
  → discuss.channel#_close_livechat_session()
    → leaves RTC call if active
    → sets livechat_end_dt = now
    → posts system notification
    → broadcasts livechat_end_dt via bus
  → Rating request sent to visitor (via rating.mixin)
  → Visitor submits rating (1/3/5 stars)
  → rating.rating record created with rated_partner_id = operator
  → im_livechat.channel.member.history#_compute_rating_id
    → links rating to the agent's history record
  → Digest email aggregates session data next day
```

### Forwarding to Human Operator

```
Visitor reaches forward_operator step
  → chatbot.script.step#_process_step()
  → discuss.channel#_forward_human_operator(chatbot_script_step)
    → _get_human_operator(users, chatbot_script_step)
      → uses step.operator_expertise_ids for routing
    → if no operator found:
        → sets livechat_failure = "no_agent"
        → chatbot continues running (visitor can retry)
    → if operator found:
        → posts step message from bot
        → adds operator as member (livechat_member_type="agent")
        → sets agent_expertise_ids from step
        → removes bot from channel
        → updates channel name to include operator
        → sets livechat_failure = "no_answer"
        → broadcasts to new operator's bus channel
  → livechat_is_escalated = True (computed: len(agent_history) > 1)
  → Operator sees "need_help" session in their queue
```

---

## L3: Edge Cases and Escalation Scenarios

### Cross-Model Interactions

**Visitor identity reconciliation**: When a public visitor later authenticates, the guest cookie still exists. During `discuss.channel.member` creation, the system matches the logged-in user to their previous guest session using `guest in channel.livechat_customer_guest_ids`, setting `livechat_member_type = "visitor"`. This preserves conversation continuity.

**Channel merge on visitor upsert**: When a visitor is upserted (created from first visit or updated), any guest-linked livechat channels are re-parented to the new visitor record via `_upsert_visitor`.

**Chat request conflicts**: When a visitor-initiated session starts, any pending operator-initiated chat requests for the same visitor are cancelled (`_close_livechat_session(cancel=True)`) to prevent two concurrent sessions.

**Bot-only session closure**: `_gc_bot_only_ongoing_sessions` closes sessions that have been idle for >1 day with no human operator. This prevents stale bot sessions from consuming resources.

**Visitor merge**: When two website visitors are merged (`_merge_visitor`), all their livechat channels are moved to the target visitor, and the `base.public_partner` is replaced with the target's authenticated partner.

### Operator Override Patterns

**Operator in call**: When `block_assignment_during_call = True`, operators currently in an RTC call are excluded from `_get_available_operators_by_livechat_channel`. The `livechat_is_in_call` field on `res.users` tracks this status.

**Max sessions per operator**: When `max_sessions_mode = "limited"`, `_get_ongoing_session_count_by_agent_livechat_channel` counts active sessions per operator, and `_get_operator` excludes operators at their cap.

**Buffer time (120s)**: After being assigned a session, an operator has a 120-second grace period before they can be assigned another. This prevents a single operator from being flooded when multiple requests arrive simultaneously.

**Same operator continuity**: If a visitor has previously chatted with an operator and that operator is available (has < 2 active sessions, not in a call), they are prioritized. This provides a personalized experience.

### Workflow Triggers

| Event | Trigger | Side Effects |
|---|---|---|
| First visitor message | `message_post` | `livechat_status` changes from `"waiting"` to `"in_progress"` |
| Agent joins `"need_help"` channel | `_add_members` | `livechat_status` changes to `"in_progress"` |
| Operator leaves, last member | `_action_unfollow` | `livechat_end_dt` set automatically |
| Visitor closes chat | `_close_livechat_session` | `livechat_end_dt` set, notification posted |
| Operator unpins empty channel | `channel_pin(pinned=False)` | Channel deleted |
| Rating submitted | rating.mixin | `rating_last_text` cached on channel |
| Bot forwards to operator | `_forward_human_operator` | `livechat_is_escalated = True`, `livechat_failure = "no_answer"` |
| Operator requests help | `livechat_status = "need_help"` | Bus notification sent to all livechat users |
| Visitor last visit update | `message_post` | `livechat_visitor_id._update_visitor_last_visit()` |

### Failure Modes

| Failure | Detection | Outcome |
|---|---|---|
| No operator available | `_get_operator` returns empty | `livechat_failure = "no_agent"` |
| Visitor never responds | Auto-close after inactivity | Garbage-collected by `_gc_bot_only_ongoing_sessions` |
| Invalid email in chatbot | `email_normalize` fails | Validation error shown, step re-displayed |
| Operator disconnects mid-session | `_action_unfollow`, last member | `livechat_end_dt` set |
| Channel has no messages | `_gc_empty_livechat_sessions` | Channel deleted after 1 hour |
| Bot-only session stale | `_gc_bot_only_ongoing_sessions` | `livechat_end_dt` set after 1 day idle |
| Unread session after 1 day | `_gc_unpin_livechat_sessions` | Unpinned from operator view |

---

## L4: Performance, Historical Changes, and Security

### Odoo 18 to Odoo 19 Changes

1. **`livechat_channel_member_history` replaces denormalized fields on `discuss.channel`**: In Odoo 18, agent/customer/bot partner IDs were stored as multi-valued fields directly on `discuss.channel`. In Odoo 19, these are computed from `im_livechat.channel.member.history`, enabling a proper many-to-many relationship where the same agent can participate in multiple sessions of the same channel.

2. **Introduction of `livechat_status` field**: New `in_progress` / `waiting` / `need_help` status enables the "request help" operator flow where an agent can escalate to a colleague mid-conversation.

3. **`livechat_matches_self_lang` and `livechat_matches_self_expertise`**: New computed searchable fields allow operators to filter their session list by language and expertise match, improving the operator's home dashboard.

4. **`res.users.settings` as preference storage**: `livechat_username`, `livechat_lang_ids`, and `livechat_expertise_ids` moved from `res.users` to `res.users.settings`, following Odoo's general trend of separating user preferences into a dedicated settings model.

5. **Chatbot `triggering_answer_ids` computed with store**: In Odoo 18, triggering answers were manually maintained. In Odoo 19, `_compute_triggering_answer_ids` auto-prunes answers from future steps on write.

6. **Buffer time constant**: `BUFFER_TIME = 120` is explicitly defined at module level in Odoo 19. In earlier versions this was a magic number in the `_get_operator` SQL query.

7. **`is_forward_operator_child` computed field**: New field that traces the chatbot script tree to determine if a step is a descendant of a forward-to-operator step, used for UI and analytics purposes.

8. **`session_expertise_ids` on report model**: Expertise tracking added to the analytics report, allowing per-expertise performance dashboards.

9. **`_get_visitor_history` on `website.visitor`**: New method returning recent page visits for display in the livechat widget header.

10. **Operator-initiated chat requests**: `is_pending_chat_request` and `action_send_chat_request` are new in Odoo 19, allowing operators to proactively reach out to website visitors.

11. **Visitor operator attribution**: `livechat_operator_id` on `website.visitor` is a new stored computed field tracking which operator a visitor is currently chatting with.

### Performance Considerations

1. **`livechat_channel_member_history_ids` as One2many (not computed)**: Unlike other history lookups, this is stored as an actual one2many rather than computed, avoiding repeated queries during message posting. The `_create_or_update_history` method batch-creates and updates history records.

2. **Operator availability uses `sudo()`**: `_get_available_operators_by_livechat_channel` calls `user.sudo().presence_ids.status` and `user.sudo().is_in_call` to check presence without triggering full ACL checks.

3. **`_get_ongoing_session_count_by_agent_livechat_channel` uses `_read_group`**: Aggregates counts at the database level rather than in Python, returning a single query result.

4. **Operator selection SQL is a raw query**: The `_get_operator` method uses a raw SQL `WITH` query joining `discuss_channel_rtc_session` and `im_livechat_channel_member_history` to efficiently compute per-operator active session counts and in-call status in one round trip.

5. **`_gc_unpin_livechat_sessions` as autovacuum**: Runs as a scheduled action, processing in batches via `search()` rather than on every request.

6. **`search_read` for visitor operator map**: `_compute_livechat_operator_id` uses `search_read` to fetch `(livechat_visitor_id, livechat_operator_id)` pairs in one query, then builds a Python dict for fast lookups.

7. **Report model uses lateral joins**: The `im_livechat.report.channel` SQL uses `LEFT JOIN LATERAL` subqueries to avoid N+1 joins — all aggregates are computed in a single table scan of `discuss_channel`.

8. **`BOTTLENECK_SKIP` in raw SQL**: The raw SQL query in `_get_operator` uses `COUNT(DISTINCT h.channel_id) < 2 OR rtc.nbr IS NULL DESC` to efficiently skip operators who are at capacity without subquery overhead.

### Security Model

1. **ACLs via `im_livechat.im_livechat_group_user`**: Users must belong to the `im_livechat_group_user` group to access livechat operator features. Group membership is tracked via `res_groups`.

2. **`sudo()` calls are targeted and documented**: Every `sudo()` call in the livechat models is accompanied by a comment explaining why elevation is acceptable:
   - Reading presence/availability is allowed for all authenticated users
   - Writing history records is allowed because the user is either the channel creator or the subject of the history
   - Guest access to their own channel messages is allowed

3. **`livechat_note` field groups**: Restricted to `base.group_user`, preventing portal/website visitors from seeing operator internal notes.

4. **`im_livechat_conversation_tag_ids` groups**: Only `im_livechat_group_user` can see and modify conversation tags.

5. **`livechat_username` and expertise fields**: Group-restricted to `im_livechat_group_user` and `base.group_erp_manager` on `res.users`, preventing regular employees from viewing operator preferences.

6. **Website visitor data**: `livechat_visitor_id` is stored on the channel, linking the livechat session to the website visitor record. Access to visitor data is controlled by `website.visitor` ACLs.

7. **Chat request from operator**: `action_send_chat_request` validates that the operator belongs to the website's channel before creating a channel, preventing unauthorized operator-initiated sessions.

8. **Review link URL validation**: `_check_review_link` validates that `review_link` uses `http` or `https` scheme, preventing `javascript:` URI injection.

### Garbage Collection

Three autovacuum methods keep the system lean:

| Method | Trigger | Action |
|---|---|---|
| `_gc_empty_livechat_sessions` | hourly | Delete channels with no messages, older than 1 hour |
| `_gc_bot_only_ongoing_sessions` | hourly | Close sessions with no agent, idle >1 day |
| `_gc_unpin_livechat_sessions` | autovacuum | Unpin inactive sessions, close if no unread messages |

### Buffer Time Mechanism

The `BUFFER_TIME = 120` constant prevents operator overload during traffic spikes:

```python
BUFFER_TIME = 120  # Time in seconds between two sessions assigned to the same operator.
                  # Not enforced if the operator is the best suited.

agents_failing_buffer = {
    group[0] for group in
    im_livechat.channel.member.history._read_group(
        [("livechat_member_type", "=", "agent"),
         ("partner_id", "in", users.partner_id.ids),
         ("channel_id.livechat_end_dt", "=", False),
         ("create_date", ">",
          fields.Datetime.now() - timedelta(seconds=BUFFER_TIME))],
        groupby=["partner_id"],
    )
}
```

Within each preference tier, operators in the buffer are deprioritized unless they are the only available match. This distributes load evenly while respecting operator expertise preferences.
