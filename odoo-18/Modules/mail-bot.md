---
Module: mail_bot
Version: Odoo 18
Type: Core
Tags: #odoo, #odoo18, #mail-bot, #chatbot, #messaging, #onboarding
---

# mail_bot — OdooBot for Mail

OdooBot (`mail.bot`) is an `AbstractModel` that implements a rule-based bot responding to user messages in private DM channels. It guides new users through a 5-step onboarding tour and provides canned responses, help redirects, and Easter eggs.

> **Technical depth:** L4 (fully read from source)
> **Source:** `~/odoo/odoo18/odoo/addons/mail_bot/models/`

---

## Architecture Overview

```
mail.bot (AbstractModel) — core bot logic
    _apply_logic(record, values, command)
        → _get_answer(record, body, values, command)
            → state machine: onboarding_emoji → onboarding_command → onboarding_ping → onboarding_attachement → onboarding_canned → idle
            → Easter egg responses
            → Help redirect responses

discuss.channel (EXTENDED)
    execute_command_help()
        → mail.bot._apply_logic(command="help")
    _message_post_after_hook()
        → mail.bot._apply_logic(values=msg_vals)

res.users (EXTENDED)
    odoobot_state: Selection — tracks onboarding progress
    odoobot_failed: Boolean — prompts repeat hints
    _init_odoobot() — bootstraps DM channel with OdooBot
    _on_webclient_bootstrap() — triggers _init_odoobot on first load
```

**Bot identity:** OdooBot is `base.partner_root` (XML-ID: `base.partner_root`, typically ID=1). All bot messages are authored by this partner.

---

## mail.bot (AbstractModel)

The bot brain. Stateless per-call — all state is stored in `res.users.odoobot_state` on the responding user (not the bot user).

### Key Methods

#### `_apply_logic(record, values, command=None)`

Entry point for all bot responses. Called from:
- `discuss.channel._message_post_after_hook()` — on every new message in a DM channel
- `discuss.channel.execute_command_help()` — when user types `/help`

**Guard conditions (no response if):**
- Message author is `odoobot_id` (prevents bot from responding to itself)
- Message type is not `comment` AND no `command` provided (ignores system notifications)

**Logic flow:**
```python
body = values.get("body", "").replace("\xa0", " ").strip().lower().strip(".!")
if answer := self._get_answer(record, body, values, command):
    record.sudo().message_post(
        author_id=odoobot_id,
        body=answer,
        message_type="comment",
        silent=True,           # no notification sound
        subtype_xmlid="mail.mt_comment",
    )
```

`silent=True` means the message does not trigger push notifications or channel unread counters.

#### `_get_answer(record, body, values, command=False)`

Core decision tree. Returns HTML response string or `False` (no response).

**Prerequisites:** Must be in a DM chat (`channel_type == "chat"`) AND `odoobot` (partner_root) is a member of the channel.

### Onboarding State Machine

The bot guides new users through 5 interactions. State is stored on `env.user.odoobot_state`.

```
not_initialized / False
    ├─ user types "start the tour" (any state)
    └─ → state = 'onboarding_emoji'
         └─ user sends emoji (any emoji)
         └─ → state = 'onboarding_command'
              └─ user types /help
              └─ → state = 'onboarding_ping'
                   └─ user pings @OdooBot
                   └─ → state = 'onboarding_attachement'
                        └─ user sends attachment
                        └─ → state = 'onboarding_canned'
                             └─ user types : to use canned response
                             └─ → state = 'idle'
```

**State transitions:**

| Current State | Trigger | Response | Next State |
|---|---|---|---|
| `idle` / `not_initialized` / `False` | `"start the tour"` in body | "To start, try to send me an emoji :)" | `onboarding_emoji` |
| `onboarding_emoji` | `_body_contains_emoji(body)` == True | "Great! Now start with /" | `onboarding_command` |
| `onboarding_emoji` | anything else | Repeat emoji hint (sets `odoobot_failed=True`) | stays |
| `onboarding_command` | `command == 'help'` | "Ping someone with @username" | `onboarding_ping` |
| `onboarding_command` | anything else | Repeat / hint (`odoobot_failed=True`) | stays |
| `onboarding_ping` | `odoobot.id in values.partner_ids` | "Yep, I am here! Now send an attachment" | `onboarding_attachement` |
| `onboarding_ping` | anything else | Repeat ping hint (`odoobot_failed=True`) | stays |
| `onboarding_attachement` | `values.get("attachment_ids")` | "Wonderful! Type : to use canned responses. I created one for you." | `onboarding_canned` |
| `onboarding_attachement` | anything else | Repeat attachment hint (`odoobot_failed=True`) | stays |
| `onboarding_canned` | `context.get("canned_response_ids")` | "Good, you can customize canned responses... End of overview." | `idle` |
| `onboarding_canned` | anything else (not help) | "Not sure what you are doing. Type :" (`odoobot_failed=True`) | stays |

**At `onboarding_attachement`:** The bot also creates a `mail.canned.response` record:
```python
{
    "source": "Thanks",
    "substitution": "Thanks for your feedback. Goodbye!",
    "description": "This is a temporary canned response to see how canned responses work.",
}
```

**At `onboarding_canned`:** If the user correctly uses a canned response, the temp record is deleted:
```python
self.env["mail.canned.response"].search([
    ("create_uid", "=", self.env.user.id),
    ("source", "=", "Thanks"),
    ("description", "=", "This is a temporary canned response..."),
]).unlink()
```

### Easter Eggs

When `odoobot_state == "idle"`:

| Trigger | Response |
|---------|----------|
| `body` in `['❤️', 'i love you', 'love']` | "Aaaaaw that's really cute but, you know, bots don't work that way..." |
| `'fuck'` in body | "That's not nice! I'm a bot but I have feelings... 💔" |

### Help / Idle Fallback

When `odoobot_state == 'idle'` and user sends anything (or explicitly asks for help):
```python
_("Unfortunately, I'm just a bot 😞 I don't understand! If you need help discovering our product, "
  "please check our documentation or our videos.")
```
Links rendered via `_get_style_dict()`: `o_odoobot_command` span class for commands, anchor tags to `https://www.odoo.com/documentation` and `https://www.odoo.com/slides`.

---

## res.users (EXTENDED)

Tracks the bot interaction state per user.

### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `odoobot_state` | Selection | Current position in the onboarding tour |
| `odoobot_failed` | Boolean | Set to True when user makes a wrong step (triggers repeat hints) |

### `odoobot_state` Values

| Value | Label | Meaning |
|-------|-------|---------|
| `not_initialized` | Not initialized | User has never started the tour |
| `onboarding_emoji` | Onboarding emoji | Waiting for user to send an emoji |
| `onboarding_command` | Onboarding command | Waiting for user to type `/help` |
| `onboarding_ping` | Onboarding ping | Waiting for user to ping @OdooBot |
| `onboarding_attachement` | Onboarding attachment | Waiting for user to send attachment |
| `onboarding_canned` | Onboarding canned | Waiting for user to use a canned response |
| `idle` | Idle | Tour complete; normal bot behavior |
| `disabled` | Disabled | User opted out |

### Key Methods

#### `_on_webclient_bootstrap()`
Called on every full page load (`webclient_bootstrap` notification). If user is internal (`_is_internal()`) and `odoobot_state in [False, "not_initialized"]`, triggers `_init_odoobot()`.

#### `_init_odoobot()`
Creates or retrieves a DM channel between `odoobot` (partner_root) and the user. Posts the onboarding greeting:

```python
Markup("%s<br/>%s<br/><b>%s</b> <span class='o_odoobot_command'>:)</span>") % (
    "Hello,",
    "Odoo's chat helps employees collaborate efficiently. I'm here to help you discover its features.",
    "Try to send me an emoji"
)
```

Sets `odoobot_state = 'onboarding_emoji'`. Returns the channel.

---

## discuss.channel (EXTENDED)

Extends `discuss.channel` with two hooks that invoke the bot.

### Key Methods

#### `execute_command_help()`
Extends the standard `/help` command. Calls `super()` (standard help behavior) then also invokes `mail.bot._apply_logic(command="help")`. The kwargs (message body etc.) are passed but currently unused in `_apply_logic` for the command path.

#### `_message_post_after_hook(message, msg_vals)`
After every message is posted, calls `self.env["mail.bot"]._apply_logic(self, msg_vals)`. This is the primary trigger for bot responses.

---

## L4: Bot AI — Message Processing

### Input Processing

Before decision tree:
```python
body = values.get("body", "").replace("\xa0", " ").strip().strip(".!").lower()
```
- `\xa0` (non-breaking space) → normal space
- Strip whitespace and common punctuation from ends
- Lowercase for matching

### Emoji Detection (`_body_contains_emoji`)

Scans body against a large static list of Unicode emoji codepoints. The list includes:
- Ranges (e.g., `range(0x2600, 0x2605)` = sun symbols)
- Discrete lists (e.g., `[0x2328, 0x23cf, ...]`)
- Modern emoji blocks: Miscellaneous Symbols, Dingbats, Emoticons (U+1F300–U+1FA00)

Uses `chr(emoji) in body` to detect any emoji character. Returns `True` if found.

### Help Detection (`_is_help_requested`)

```python
def _is_help_requested(body):
    return any(token in body for token in ['help', translated('help'), '?']) \
           or self.env.user.odoobot_failed
```

Also triggers if `odoobot_failed=True` (user made a mistake and needs guidance).

### Bot Ping Detection (`_is_bot_pinged`)

```python
def _is_bot_pinged(self, values):
    odoobot_id = self._get('ir.model.data')._xmlid_to_res_id("base.partner_root")
    return odoobot_id in values.get('partner_ids', [])
```

Odoo chat messages include `partner_ids` (list of mentioned partners) in the message values. If `odoobot_id` is in that list, the user was specifically addressing the bot.

---

## L4: Canned Response Integration

### What are Canned Responses?

`mail.canned.response` records store:
- `source`: trigger phrase (typed by user, preceded by `:` in Odoo)
- `substitution`: replacement text
- `description`: optional description

### Bot's Role

The bot does not process canned responses directly. Instead, the frontend intercepts `:` prefix and shows autocomplete. The bot's role is:
1. **Creates a temporary canned response** during onboarding (`onboarding_attachement` state)
2. **Deletes it** once the user demonstrates correct usage (`onboarding_canned` state)
3. **Detects usage** via `context.get("canned_response_ids")` in `_get_answer`

The `canned_response_ids` context is set by the Discuss frontend when it processes a canned response substitution.

---

## L4: Channel Bootstrap Flow

```
1. User opens Discuss app
2. _on_webclient_bootstrap() fires
3. odoobot_state is False or 'not_initialized'?
   → YES: _init_odoobot()
       - channel_get([odoobot_id, user.partner_id.id])
         → creates or retrieves existing DM channel
       - message_post() from odoobot author
       - odoobot_state = 'onboarding_emoji'
4. User sees greeting message in DM with OdooBot
5. User sends emoji
6. discuss.channel._message_post_after_hook()
   → mail.bot._apply_logic()
       → odoobot_state == 'onboarding_emoji'
       → _body_contains_emoji(body) == True
       → response posted
       → odoobot_state = 'onboarding_command'
7. Repeat through state machine...
8. odoobot_state == 'idle'
   → Normal bot behavior: help, Easter eggs, fallbacks
```

---

## Style Dictionary (`_get_style_dict`)

Returns a `Markup` dict used to build styled HTML responses without `format()` concatenation issues:

```python
{
    "new_line": Markup("<br>"),
    "bold_start": Markup("<b>"),
    "bold_end": Markup("</b>"),
    "command_start": Markup("<span class='o_odoobot_command'>"),
    "command_end": Markup("</span>"),
    "document_link_start": Markup("<a href='https://www.odoo.com/documentation' target='_blank'>"),
    "document_link_end": Markup("</a>"),
    "slides_link_start": Markup("<a href='https://www.odoo.com/slides' target='_blank'>"),
    "slides_link_end": Markup("</a>"),
    "paperclip_icon": Markup("<i class='fa fa-paperclip' aria-hidden='true'/>"),
}
```

Used in `_get_answer()` via string formatting: `%(command_start)s...%(command_end)s`.

---

## Relationships Summary

```
mail.bot (AbstractModel — no table)
    applied via: discuss.channel._message_post_after_hook()
    applied via: discuss.channel.execute_command_help()

discuss.channel (EXTENDED)
    channel_type == 'chat': condition for bot activation
    _message_post_after_hook → mail.bot._apply_logic()
    execute_command_help → mail.bot._apply_logic(command="help")

res.users
    odoobot_state: onboarding progress tracker
    odoobot_failed: Boolean hint flag
    _init_odoobot(): creates DM with partner_root
    partner_id: used as channel member for DM

res.partner (base.partner_root)
    id=1 (or ir.model.data: base.partner_root)
    author of all bot messages
    member of all OdooBot DM channels
```

---

## Key Differences from im_livechat Chatbots

| Feature | im_livechat Chatbot | mail_bot OdooBot |
|---------|---------------------|------------------|
| Model | `chatbot.script` (persistent) | `mail.bot` AbstractModel |
| Session type | `discuss.channel` (`channel_type=livechat`) | `discuss.channel` (`channel_type=chat`) |
| Audience | Anonymous website visitors | Authenticated internal users |
| Script | Admin-designed multi-step flows | Fixed state machine (onboarding) |
| CRM integration | Can create leads/tickets (bridge modules) | No external integration |
| Routing | Operator assignment by load/country/lang | Not applicable (1:1 DM) |
| Trigger | Visitor sends first message | `_on_webclient_bootstrap` |
| Storage | `chatbot.message` records per step | `mail.message` for everything |
| State | Per-channel `chatbot_current_step_id` | Per-user `odoobot_state` |
