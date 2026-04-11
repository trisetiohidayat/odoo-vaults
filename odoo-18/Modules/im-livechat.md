---
Module: im_livechat
Version: Odoo 18
Type: Business
Tags: #odoo, #odoo18, #livechat, #chatbot, #messaging, #customer-service
---

# im_livechat — Live Chat Channel

Live chat allows website visitors to chat in real-time with support operators or chatbots. The module extends `discuss.channel` with livechat-specific fields, implements a rule-based routing engine for operator assignment, and includes a full chatbot scripting system.

> **Technical depth:** L4 (fully read from source)
> **Source:** `~/odoo/odoo18/odoo/addons/im_livechat/models/`

---

## Architecture Overview

```
im_livechat.channel (channel config)
    ├── im_livechat.channel.rule (URL/country routing rules)
    │       └── chatbot.script (optional bot per rule)
    │               ├── chatbot.script.step (sequence of steps)
    │               │       └── chatbot.script.answer (options per step)
    │               └── chatbot.message (visitor answers in channel)
    │
    └── discuss.channel (livechat sessions)
            ├── chatbot_current_step_id → chatbot.script.step
            ├── livechat_channel_id → im_livechat.channel
            ├── livechat_operator_id → res.partner
            └── discuss.channel.member (EXTENDED: unpin gc)
```

**Visitor flow (anonymous):**
1. Visitor lands on page with livechat widget embedded via `script_external` (HTML snippet)
2. Widget calls `im_livechat.channel/get_livechat_info` — checks availability
3. `im_livechat.channel.rule/match_rule()` evaluates URL + GeoIP country
4. Matching rule determines: chatbot only, operator only, or chatbot until operator available
5. `_get_livechat_discuss_channel_vals()` creates `discuss.channel` with `channel_type='livechat'`
6. If chatbot: welcome steps posted as messages; if operator: `_get_operator()` assigns
7. Session runs until visitor leaves → `_close_livechat_session()` sets `livechat_active=False`
8. Autovacuum: `_gc_unpin_livechat_sessions` unpins stale sessions after 1 day of inactivity

---

## im_livechat.channel

`rating.parent.mixin` — channels are rateable (14-day satisfaction window).

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Channel display name |
| `button_text` | Char | Text on the livechat button (default: "Have a Question? Chat with us.") |
| `default_message` | Char | Auto-sent welcome message (default: "How may I help you?") |
| `input_placeholder` | Char | Prompt text inside the chat input box |
| `header_background_color` | Char | Hex color for channel header (default `#875A7B`) |
| `title_color` | Char | Hex color for title text (default `#FFFFFF`) |
| `button_background_color` | Char | Hex color for button (default `#875A7B`) |
| `button_text_color` | Char | Hex color for button text (default `#FFFFFF`) |
| `image_128` | Image | Channel logo/thumbnail |
| `user_ids` | Many2many res.users | Operators assigned to this channel |
| `available_operator_ids` | Many2many res.users (computed) | Operators currently online (`user._is_user_available()`) |
| `channel_ids` | One2many discuss.channel | All livechat sessions on this channel |
| `rule_ids` | One2many im_livechat.channel.rule | Routing rules for this channel |
| `nbr_channel` | Integer (computed) | Count of all sessions |
| `chatbot_script_count` | Integer (computed) | Distinct chatbot scripts referenced in rules |
| `web_page` | Char (computed) | Static page URL: `{base}/im_livechat/support/{id}` |
| `script_external` | Html (computed) | JS embed snippet rendered from `im_livechat.external_loader` QWeb template |
| `are_you_inside` | Boolean (computed) | Does current user belong to `user_ids`? |

### Key Methods

#### `_get_livechat_discuss_channel_vals()`
Creates the vals dict for a new `discuss.channel` session. Called by the web controller.

**Signature:**
```python
def _get_livechat_discuss_channel_vals(
    self, anonymous_name, previous_operator_id=None,
    chatbot_script=None, user_id=None, country_id=None, lang=None
) -> dict
```

**Logic:**
1. If `chatbot_script` given: use `chatbot_script.operator_partner_id` as the bot
2. Else: call `_get_operator()` to find the best available human operator
3. Build `channel_member_ids`: always includes the operator (or bot); includes the logged-in `user_id` as a member if provided and not the operator
4. Sets `channel_type='livechat'`, `livechat_active=True`, `anonymous_name` (if no user), `country_id`
5. If chatbot: `chatbot_current_step_id = chatbot_script._get_welcome_steps()[-1].id` (last welcome step becomes current step)

**Returns:** `False` if no operator available and no chatbot.

#### `_get_operator()`
Finds the best human operator for a livechat session. Core routing logic.

**Priority order:**
1. **Previous operator** — if visitor was chatting with someone recently (≤1 active chat or not in a call), prefer them
2. **Language match (main)** — operator whose `partner_id.lang` equals visitor's lang
3. **Language match (additional)** — operator whose `livechat_lang_ids` contains visitor's lang
4. **Country match** — operator whose `partner_id.country_id` matches visitor's country
5. **Random among least active** — calls `_get_less_active_operator()`

**SQL query** (raw SQL for performance):
- Counts livechat channels per operator created in last 24h with `livechat_active=True` and at least one message in last 30 minutes
- Filters out operators in active RTC (voice/video) sessions
- Orders by: `count < 2` first (new operators), then ascending count, then not in call

**`_get_less_active_operator()` scoring:**
- Prefer operators with 0 active chats (inactive operators)
- Among equal counts: prefer operators NOT in a call
- Random selection among top candidates (prevents always assigning same operator)

#### `action_join()` / `action_quit()`
Add or remove current user from `user_ids` using `Command.link`/`Command.unlink`. Pushes updated `are_you_inside` and `name` to the client store.

#### `get_livechat_info()`
Public endpoint for the livechat widget. Returns:
```python
{
    'available': bool,  # chatbot_script_count > 0 or available_operator_ids not empty
    'server_url': base_url,
    'websocket_worker_version': int,
    'options': { header/button/text config },
}
```

---

## im_livechat.channel.rule

URL-pattern and country-based routing rules. Applied when a visitor opens the livechat widget.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `channel_id` | Many2one im_livechat.channel | Parent channel |
| `regex_url` | Char | Regular expression for matching page URLs |
| `action` | Selection | `display_button`, `display_button_and_text`, `auto_popup`, `hide_button` |
| `auto_popup_timer` | Integer | Seconds before auto-open (requires `auto_popup` action) |
| `chatbot_script_id` | Many2one chatbot.script | Bot script for this rule |
| `chatbot_only_if_no_operator` | Boolean | Only activate bot if no human operator is online |
| `country_ids` | Many2many res.country | Countries this rule applies to (GeoIP-based) |
| `sequence` | Integer | Rule evaluation order (lowest first); lowest-matching rule wins |

### Key Methods

#### `match_rule(channel_id, url, country_id=False)`
Iterates over rules sorted by `sequence` and returns the first matching rule.

**Matching conditions:**
- URL matches `regex_url` (empty regex matches all)
- If `chatbot_script_id` is set: script must be `active` AND have `script_step_ids`
- If `chatbot_only_if_no_operator` is set: only match if `channel_id.available_operator_ids` is empty
- Country-specific rules evaluated first; then fallback to no-country rules

**Returns:** `im_livechat.channel.rule` or `False`

---

## discuss.channel (EXTENDED)

Livechat adds these fields to `discuss.channel`:

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `channel_type` | Selection (extends) | Adds `livechat` value; cascade delete for livechat channels |
| `anonymous_name` | Char | Visitor display name (e.g., "Visitor #1234") |
| `livechat_active` | Boolean | Is visitor still in the conversation? |
| `livechat_channel_id` | Many2one im_livechat.channel | Which livechat channel this session belongs to |
| `livechat_operator_id` | Many2one res.partner | The assigned operator (or bot partner) |
| `chatbot_current_step_id` | Many2one chatbot.script.step | Current position in the bot script |
| `chatbot_message_ids` | One2many chatbot.message | All chatbot message records for this session |
| `country_id` | Many2one res.country | Visitor's country (from GeoIP) |
| `duration` | Float (computed) | Session duration in hours (last message time minus first message time) |

### SQL Constraints

```python
('livechat_operator_id',
 "CHECK((channel_type = 'livechat' and livechat_operator_id is not null) or (channel_type != 'livechat'))",
 'Livechat Operator ID is required for a channel of type livechat.')
```

### Key Methods

#### `_close_livechat_session()`
Called when visitor leaves. Sets `livechat_active=False`, folds the channel, leaves any RTC call, and posts a system notification: "Visitor left the conversation."

#### `_chatbot_post_message(chatbot_script, body)`
Helper to post a bot-authored message: `sudo()`, `mail_create_nosubscribe=True`, `message_type='comment'`.

#### `_message_post_after_hook()`
After every message is posted in a chatbot session, this hook:
1. Checks if the message corresponds to a selected answer → updates `chatbot.message.user_script_answer_id`
2. Creates a `chatbot.message` record linking the mail message to the current script step

#### `_chatbot_restart(chatbot_script)`
Clears `chatbot_current_step_id`, reactivates `livechat_active`, deletes `chatbot_message_ids`, and posts "Restarting conversation..." system message.

#### `_email_livechat_transcript(email)`
Renders the `im_livechat.livechat_email_template` QWeb template and sends a mail to the visitor with the full conversation history.

#### `_get_channel_history()`
Returns all messages as plaintext-formatted HTML for transcript email.

#### Autovacuum: `_gc_empty_livechat_sessions()`
Deletes livechat channels older than 1 hour with zero messages and a `livechat_channel_id`.

---

## discuss.channel.member (EXTENDED)

### Key Methods

#### Autovacuum: `_gc_unpin_livechat_sessions()`
Runs daily via `@api.autovacuum`. Unpins livechat sessions inactive for ≥1 day with 0 unread messages. Sends `discuss.channel/unpin` bus notification.

#### `_to_store()`
Extends the store record for livechat members: adds `is_bot` boolean (True if member's partner is the chatbot operator for this channel).

#### `_get_store_partner_fields()`
For livechat channels: returns a restricted set of partner fields: `active`, `avatar_128`, `country`, `is_public`, `user_livechat_username`. Hides internal user fields from anonymous visitors.

#### `_get_rtc_invite_members_domain()`
For livechat with an active chatbot: excludes the chatbot operator partner from the RTC invite domain (cannot video-call the bot).

---

## chatbot.script

A bot script defines a linear/branching conversation flow. Each script has an associated `operator_partner_id` (an inactive `res.partner` created automatically on script creation) that serves as the bot's identity.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `title` | Char | Script name (mirrors `operator_partner_id.name`; UTM source override) |
| `active` | Boolean |  |
| `operator_partner_id` | Many2one res.partner | Bot's partner identity (auto-created inactive partner) |
| `image_1920` | Image | Related to `operator_partner_id.image_1920` |
| `script_step_ids` | One2many chatbot.script.step | Ordered steps in the script |
| `livechat_channel_count` | Integer (computed) | Channels using this script |
| `first_step_warning` | Selection (computed) | Warns if first non-text step is `forward_operator` or invalid type |

### Constraints

```python
@api.constrains("script_step_ids")
def _check_question_selection(self):
    # Steps of type 'question_selection' MUST have at least one answer
```

### Key Methods

#### `_get_welcome_steps()`
Returns all consecutive `text`-type steps from the beginning of the script. These are pre-displayed to the visitor without being saved as actual `mail.message` records (avoids bloating the channel with bot monologue messages).

**Rule:** Collect steps from the start while `step_type == 'text'`. Stop at first non-text step. That first non-text step (e.g., `question_selection`) is the last welcome step — but welcome steps are only the text ones before it.

#### `_post_welcome_steps(discuss_channel)`
Iterates welcome steps and posts each as a real `mail.message` authored by the bot partner. Sets `chatbot_current_step_id` on each iteration (needed by `_message_post_after_hook`).

#### `_validate_email(email_address, discuss_channel)`
Normalizes the email via `email_normalize()` and posts an error message in the channel if invalid.

#### `_get_chatbot_language()`
Reads visitor's `frontend_lang` cookie via `request.httprequest.cookies` to localize the bot script.

#### `copy()`
Deep-copies the script including all steps and answers, then fixes up `triggering_answer_ids` to point to the cloned answers (not original ones).

---

## chatbot.script.step

Each step in a chatbot script. Steps are sequenced by `sequence` (auto-assigned incrementally on creation).

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `message` | Text | Bot's message for this step |
| `sequence` | Integer | Order within script (auto-assigned by `create()`) |
| `chatbot_script_id` | Many2one chatbot.script | Parent script |
| `step_type` | Selection | `text`, `question_selection`, `question_email`, `question_phone`, `forward_operator`, `free_input_single`, `free_input_multi` |
| `answer_ids` | One2many chatbot.script.answer | Options for `question_selection` steps |
| `triggering_answer_ids` | Many2many chatbot.script.answer | Conditional: only show this step if all of these answers were selected |
| `is_forward_operator_child` | Boolean (computed) | True if this step is downstream of a `forward_operator` step |

### `step_type` Descriptions

| Type | Behavior |
|------|----------|
| `text` | Bot posts `message`; then advances to next step |
| `question_selection` | Bot posts `message` + renders answer buttons; visitor selects one |
| `question_email` | Bot collects email; validates via `email_normalize()`; error message on failure |
| `question_phone` | Bot collects phone number (free input, no validation) |
| `forward_operator` | Bot finds human operator via `_get_operator()`; adds them to channel; script ends |
| `free_input_single` | Bot accepts single-line text input; passes to `_process_answer()` |
| `free_input_multi` | Bot accepts multi-line text input |

### Key Methods

#### `_fetch_next_step(selected_answer_ids)`
Finds the next step after the current one. Logic:
- Filter steps with `sequence > current`
- Apply `triggering_answer_ids` filter: if set, step only valid if all triggering answers are in `selected_answer_ids`
- Multiple triggering answers from same step → OR; from different steps → AND
- Return first matching step with no triggering answers, or step where all conditions satisfied
- Returns empty recordset if no next step found

#### `_process_answer(discuss_channel, message_body)`
Called when visitor responds to a step. For email/phone steps: stores raw HTML answer in `chatbot.message.user_raw_answer`. Returns `_fetch_next_step()` result.

#### `_process_step(discuss_channel)`
Called when the bot reaches this step. Posts the step's message and handles special logic:
- `forward_operator`: calls `_process_step_forward_operator()`
- All others: calls `discuss_channel._chatbot_post_message()`

#### `_process_step_forward_operator(discuss_channel)`
Special processing for `forward_operator` steps:
1. Call `livechat_channel_id._get_operator()` with visitor's lang and country
2. If operator found (and not current user):
   - Post the step's text message (if any)
   - Call `_add_members(users=human_operator)` to add operator to channel
   - Rename channel to include operator name
   - Broadcast to operator's partner
   - Pin the channel (`channel_pin(pinned=True)`)
3. If no operator available: do nothing; script continues normally (allows adding email/ticket steps as fallback)

#### `_chatbot_prepare_customer_values(discuss_channel)`
Extracts email and phone from chatbot message records and:
- Creates a `res.partner` if the visitor is a public user
- Updates existing partner's email/phone if not set
- Returns a dict: `{partner, email, phone, description}` — suitable for creating leads or tickets

#### `_is_last_step(discuss_channel)`
Returns `True` if this is a non-question step AND `_fetch_next_step()` returns nothing.

---

## chatbot.script.answer

Individual answer options for `question_selection` steps.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Answer button text |
| `sequence` | Integer | Display order |
| `redirect_link` | Char | URL to open when clicked (external links end the script) |
| `script_step_id` | Many2one chatbot.script.step | Parent step |
| `chatbot_script_id` | Many2one (related) | Convenience link to parent script |

### Display Name

Computed as `{shortened_step_message}: {answer_name}`. Uses `textwrap.shorten(width=26)` on the step's message. This keeps dropdown/search lists readable.

---

## chatbot.message

Tracks the relationship between `mail.message` records and `chatbot.script.step` records within a livechat channel. Prevents bloating `mail.message` with chatbot-specific fields.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `mail_message_id` | Many2one mail.message | The posted message |
| `discuss_channel_id` | Many2one discuss.channel | Session channel |
| `script_step_id` | Many2one chatbot.script.step | Which step this message belongs to |
| `user_script_answer_id` | Many2one chatbot.script.answer | Visitor's selected answer (for question steps) |
| `user_raw_answer` | Html | Raw HTML from visitor's email/phone input |

### SQL Constraints

```python
('_unique_mail_message_id', 'unique (mail_message_id)',
 "A mail.message can only be linked to a single chatbot message")
```

---

## res.users (EXTENDED)

Livechat-specific user preferences stored via `res.users.settings`.

### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `livechat_username` | Char (computed/inverse) | Display name in livechat sessions (e.g., "Support John") |
| `livechat_lang_ids` | Many2many res.lang (computed/inverse) | Additional languages for operator assignment |
| `has_access_livechat` | Boolean (computed) | `True` if user is in `im_livechat.im_livechat_group_user` |

All three are stored in `res.users.settings` (not `res.users` directly) via inverse methods.

### Key Methods

#### `_is_user_available()`
Used by `im_livechat.channel._compute_available_operator_ids`. Checks if user is online/has im_status. Called in `_get_operator()`.

---

## res.users.settings (EXTENDED)

Stores per-user livechat preferences.

### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `livechat_username` | Char | Operator's public livechat display name |
| `livechat_lang_ids` | Many2many res.lang | Additional languages beyond the user's main `res.lang` |

---

## res.partner (EXTENDED)

### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `user_livechat_username` | Char (computed) | Derived from `user_ids.livechat_username` (first non-False value) |

### Key Methods

#### `_search_for_channel_invite_to_store()`
Extends partner search for livechat channels: adds `invite_by_self_count`, `is_available` (is this partner an active livechat operator?), and `lang_name`.

---

## mail.message (EXTENDED)

### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `parent_author_name` | Char (computed) | Author name of `parent_id` message |
| `parent_body` | Html (computed) | Body of `parent_id` message |

### `_to_store()` Extension

For livechat channel messages authored by the chatbot operator, this includes a `ChatbotStep` record in the store with:
- Step ID + message ID composite key
- Selected answer (if any)
- `operatorFound` flag (whether a human operator has been added)

### `_author_to_store()` Extension

For livechat messages: uses a restricted field set for the author (`avatar_128`, `is_company`, `user_livechat_username`, `user`) instead of the full partner record — prevents leaking internal user data to anonymous visitors.

---

## L4: Livechat Routing Deep Dive

### Operator Assignment Algorithm (`_get_operator`)

```
1. Garbage-collect inactive RTC sessions (sudo)
2. Raw SQL: count active livechat channels per operator in last 24h
   - Active = channel.create_date < 24h ago AND livechat_active=True
   - Has message in last 30 minutes
   - Not in an active RTC session
3. Build operator_statuses list: [(count, in_call, partner_id), ...]
4. Try previous operator:
   - If previous_operator_id in available_operator_ids
   - AND (no status OR count < 2 OR not in_call) → return them
5. Try language match (main lang):
   - Filter operators by partner.lang == visitor.lang
   - Call _get_less_active_operator()
6. Try language match (additional langs):
   - Filter by lang in livechat_lang_ids
7. Try country match:
   - Filter by partner.country_id == visitor.country_id
8. Fallback: random from all available operators
```

### `_get_less_active_operator` Scoring

```
Priority score = (count < 2, -count, in_call is False)
- count < 2 (True=1) wins: prefer operators with <2 active chats
- Then sort by ascending count
- Then prefer operators NOT in a call
- Random selection among top-scoring candidates
```

### Session Creation Flow

```
POST /im_livechat/get_session
  → im_livechat.channel._get_livechat_discuss_channel_vals()
      → chatbot_script in rules? → use bot
      → else → _get_operator() → use human
      → create discuss.channel vals
  → discuss.channel.create()
      → ChannelMember records created (operator + optionally visitor user)
      → chatbot._get_welcome_steps() → _post_welcome_steps()
      → WebSocket notification to operator
```

### Garbage Collection Schedule

| Job | Trigger | Condition | Action |
|-----|---------|-----------|--------|
| `_gc_unpin_livechat_sessions` | `@api.autovacuum` daily | `is_pinned=True`, `last_seen_dt ≤ 1 day ago`, `message_unread_counter=0` | Set `unpin_dt`, send unpin bus notification |
| `_gc_empty_livechat_sessions` | `@api.autovacuum` | `channel_type=livechat`, no messages, `livechat_channel_id` set, >1 hour old | `unlink()` channel |

---

## L4: Chatbot Script Execution Flow

```
1. Visitor sends first message (or widget auto-loads)
2. Rule matched → chatbot_script identified
3. discuss.channel created with chatbot_current_step_id = last welcome step
4. _post_welcome_steps() → bot messages displayed
5. Visitor sees question step → answers
6. Frontend sends answer → message_post with selected_answer_id in context
7. _message_post_after_hook() → chatbot.message created, user_script_answer_id set
8. Bot side: _process_answer() → _fetch_next_step()
9. Next step's _process_step() → posts bot message
10. Repeat until:
    - forward_operator step → human added → script ends
    - question step with no matching next step → script ends
    - visitor closes chat → _close_livechat_session()
```

### Triggering Answer Logic

```
STEP 1: A, B
STEP 2: C, D
STEP 3: (triggering: A, C) → only shown if both A AND C selected
STEP 4: (triggering: A OR B) → shown if A selected OR B selected
```

Multi-step triggering: answers from different parent steps are AND-ed; answers from same step are OR-ed.

---

## Relationships Summary

```
im_livechat.channel
    1:N im_livechat.channel.rule  (via rule_ids)
        → chatbot.script (via chatbot_script_id)
            1:N chatbot.script.step (via script_step_ids)
                1:N chatbot.script.answer (via answer_ids)
            1:N chatbot.message (via discuss_channel_id.chatbot_message_ids)

im_livechat.channel
    1:N discuss.channel  (via channel_ids)

discuss.channel (livechat)
    N:1 im_livechat.channel  (livechat_channel_id)
    N:1 res.partner  (livechat_operator_id)
    N:1 chatbot.script.step  (chatbot_current_step_id)
    1:N chatbot.message  (chatbot_message_ids)
    N:1 res.country  (country_id)
    N:1 res.users  (channel_member_ids → partner_id → user_id)

res.users
    1:1 res.users.settings  (res_users_settings_id)
        → livechat_username, livechat_lang_ids
```
