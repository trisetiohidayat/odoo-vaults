---
uid: mail_bot
title: OdooBot
type: module
category: Productivity/Discuss
version: "1.2"
created: 2026-04-06
modified: 2026-04-11
dependencies:
  - mail
author: Odoo S.A.
license: LGPL-3
summary: Interactive OdooBot chatbot for user onboarding and chat assistance in Discuss
auto_install: true
tags:
  - odoo
  - odoo19
  - chatbot
  - mail
  - discuss
  - bot
  - odoobot
  - onboarding
---

# mail_bot — OdooBot

> **Injects:** `/Users/tri-mac/odoo/odoo19/odoo/addons/mail_bot/`

`mail_bot` provides the **OdooBot** — a guided onboarding chatbot embedded in the Discuss (mail) module. It walks new internal users through five Discuss features (emoji, slash commands, @mentions, attachments, canned responses) and provides static fallback responses when it cannot understand a message. The bot has **no external AI or IAP dependency**.

---

## Module Manifest

**`__manifest__.py`**

```python
{
    'name': 'OdooBot',
    'version': '1.2',
    'category': 'Productivity/Discuss',
    'summary': 'Add OdooBot in discussions',
    'website': 'https://www.odoo.com/app/discuss',
    'depends': ['mail'],           # discuss.channel, mail.message, mail.canned.response
    'auto_install': True,          # activates automatically when mail is installed
    'installable': True,
    'data': [
        'views/res_users_views.xml',
        'data/mailbot_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mail_bot/static/src/scss/odoobot_style.scss',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

**Design decisions:**
- `depends: ['mail']` only — `discuss.channel` is provided by the `mail` module. No explicit `discuss` dependency needed.
- `auto_install: True` — no manual installation step; OdooBot activates the moment `mail` is present.
- No security CSV file — ACLs are inherited from `mail`. OdooBot posts as `base.partner_root` (system partner), bypassing ACLs via `sudo()`.

---

## Models

### `mail.bot` — AbstractModel

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/mail_bot/models/mail_bot.py`

```python
class MailBot(models.AbstractModel):
    _name = 'mail.bot'
    _description = 'Mail Bot'
```

An **abstract mixin** — it is never instantiated directly. Subclasses (the `discuss.channel` and `res.users` extensions) call its methods via `self.env["mail.bot"]`.

---

#### `_apply_logic(channel, values, command=None) -> None`

> **Single entry point for all bot decisions.** Called from both message posting and the `/help` slash command.

Signature:
```python
def _apply_logic(self, channel, values, command=None) -> None
```

**Trigger paths:**

| Caller | When |
|---|---|
| `discuss.channel._message_post_after_hook` | Every `message_post` on any channel |
| `discuss.channel.execute_command_help` | User types `/help` in any channel |

**Parameters:**

| Param | Type | Description |
|---|---|---|
| `channel` | `discuss.channel` recordset | Must be single-record. Raises `AccessError` via `ensure_one()`. |
| `values` | `dict` | `msg_vals` from `message_post` (body, author_id, partner_ids, attachment_ids, message_type). |
| `command` | `str\|None` | Command name when triggered by slash-command dispatcher; `None` for regular messages. |

**Guard conditions — early return, no bot response:**

```python
if values.get("author_id") == odoobot_id:           # bot never replies to itself
    return
if values.get("message_type") != "comment" and not command:  # ignores system/notification messages
    return
```

**Body preprocessing:**

```python
body = values.get("body", "").replace("\xa0", " ").strip().lower().strip(".!")
```

- `\xa0` (non-breaking space) normalized to regular space — prevents copy-paste evasion.
- Case-folded and punctuation-stripped before keyword matching.
- Emoji detection uses Unicode code-point ranges, not string matching.

**Answer posting:**

```python
channel.sudo().message_post(
    author_id=odoobot_id,        # base.partner_root — system bot partner
    body=ans,
    message_type="comment",
    silent=True,                # suppresses inbox/email notification for bot messages
    subtype_xmlid="mail.mt_comment",
)
```

- `sudo()` bypasses ACLs — the bot must always be able to post.
- `silent=True` prevents notification spam on every bot reply.
- Returns `None` (void method); caller does not use the return value.

**L4 — Performance:** Runs synchronously in the HTTP request thread that posted the message. For high-volume channels, every `message_post` triggers `_apply_logic`. The `emoji_list` iteration in `_body_contains_emoji` uses a `itertools.chain` generator (constant memory). The `_is_help_requested` method performs a DB read of `self.env.user.odoobot_failed` on every non-onboarding message.

---

#### `_get_answer(channel, body, values, command=False) -> str | list[str] | bool`

> **State-machine dispatcher.** Returns `False` (no response), a single `str` (one reply), or a `list[str]` (multi-message sequence).

The bot only operates inside **1-on-1 chat channels** where `base.partner_root` is a member:

```python
if channel.channel_type == "chat" and odoobot in channel.channel_member_ids.partner_id:
    # ... all state transitions ...
return False
```

---

##### State Machine: `res.users.odoobot_state`

```
not_initialized ──("start the tour")──► onboarding_emoji
       ▲                                     │
       │                                     ▼ (emoji sent)
       │◄────────────(wrong input, odoobot_failed=True)
       │                              onboarding_command
       │                                     │
       │                                     ▼ (/help command)
       │◄────────────(wrong input)──── onboarding_ping
       │                                     │
       │                                     ▼ (@OdooBot ping)
       │◄────────────(wrong input)─── onboarding_attachement
       │                                     │
       │                                     ▼ (attachment sent)
       │◄────────────(wrong input)─── onboarding_canned
       │                                     │
       │                                     ▼ (:: canned response used)
       └──────────────────────(re-init)──── idle
```

**Complete transition table:**

| Current State | Trigger Condition | Next State | `odoobot_failed` | Bot Response |
|---|---|---|---|---|
| `onboarding_emoji` | `_body_contains_emoji(body)` → `True` | `onboarding_command` | `False` | "Great! To access special commands, start with `/`" |
| `onboarding_command` | `command == 'help'` | `onboarding_ping` | `False` | "Ping someone with @username..." |
| `onboarding_ping` | `odoobot.id in values.get("partner_ids", [])` | `onboarding_attachement` | `False` | "Now try sending an attachment..." |
| `onboarding_attachement` | `values.get("attachment_ids")` truthy | `onboarding_canned` | `False` | "Try typing `::`..." + creates temp `mail.canned.response` |
| `onboarding_canned` | `context.get("canned_response_ids")` set | `idle` | `False` | Multi-message: "Great! ... end of tour" |
| `onboarding_canned` | Wrong input, not canned response | `onboarding_canned` | `True` | Re-prompt: "Please type `::` and wait..." |
| `idle` | `"start the tour"` in body (case-insensitive) | `onboarding_emoji` | — | "To start, try to send me an emoji :)" |
| `idle` | body in `['❤️', 'i love you', 'love']` | `idle` | — | Easter egg: "Aaaaaw..." |
| `idle` | `('fuck' in body)` or `('fuck' in body.lower())` | `idle` | — | "That's not nice! I have feelings..." |
| `idle` / `not_initialized` / `False` | `_is_help_requested(body)` → `True` | unchanged | unchanged | Links to odoo.com/documentation and odoo.com/slides |
| `idle` / `not_initialized` | Any other message | unchanged | unchanged | Random fallback: "I'm not smart enough...", "Hmmm...", "I'm sleepy..." |
| `onboarding_emoji` | Wrong input | `onboarding_emoji` | `True` | "Not exactly. Send an emoji: `:)`" |
| `onboarding_attachement` | Wrong input | `onboarding_attachement` | `True` | "To send an attachment, click the 📎 icon..." |
| `onboarding_command` | Wrong input | `onboarding_command` | `True` | "Please type `/` and wait for propositions..." |
| `onboarding_ping` | Wrong input | `onboarding_ping` | `True` | "Sorry I'm not listening. Write `@OdooBot`..." |

**`odoobot_failed` purpose:** Forces `_is_help_requested()` to return `True` on the next message, short-circuiting the normal fallback path and triggering a **contextual re-prompt** that tells the user exactly what they should have done in the current onboarding step. Reset to `False` on every successful transition.

**L4 — `onboarding_canned` context dependency:** The final transition reads `self.env.context.get("canned_response_ids")` — a context key populated by the `mail` module when a canned response is applied. If this context is not set (e.g. mail module bug, context propagation failure), the transition never fires and the user remains stuck in `onboarding_canned`. The `mail.canned.response` created at the `onboarding_attachement` step is **unlinked** when the user completes the step, leaving no trace.

**L4 — IAP/AI absence:** In Odoo 16–17, `_get_answer` routed unclassified messages to an IAP endpoint for AI-generated replies. In Odoo 18 and 19, this is **gone entirely**. The bot has no external dependencies. When it does not understand a message, it returns one of three random static strings. This was a deliberate feature removal, not a regression.

---

#### `_body_contains_emoji(body) -> bool`

Detects any Unicode emoji in the body by iterating ~100 predefined Unicode code-point ranges and singletons.

```python
def _body_contains_emoji(self, body) -> bool:
    emoji_list = itertools.chain(
        range(0x231A, 0x231c),  # Watch, hourglass
        range(0x23E9, 0x23f4),  # Alarm clock, fast forward
        range(0x2600, 0x2605),  # Sun, cloud, zodiac
        range(0x2648, 0x2654),  # Zodiac signs
        range(0x1F300, 0x1FA00),  # Full emoji set (including skin-tone variants)
        # ... ~100 total ranges + 50 discrete singletons
    )
    if any(chr(emoji) in body for emoji in emoji_list):
        return True
    return False
```

**L4 — Unicode coverage:** Covers Emoji 1.0 through 13.1 blocks (`U+1F300–U+1F9E7`), transport symbols, clock emojis, weather, animals, food, activities, flags, and skin-tone modifiers. Singletons include the black heart (`U+2764`), heavy black heart (`U+1F493`), star (`U+2B50`), and the full face range.

**L4 — False-positive risk:** ASCII-only messages are safe. Emoji-zalgo text (combining characters) detection depends on how combining marks are encoded. `\xa0` is stripped before this function is called, so copy-pasted emoji from web sources pass correctly.

**L4 — Performance:** `itertools.chain` is a lazy generator. `any()` short-circuits on first match. For a 20-character body, this is O(n) with negligible constant factor. No memory allocation beyond the generator object.

---

#### `_is_help_requested(body) -> bool`

```python
def _is_help_requested(self, body) -> bool:
    return any(token in body for token in ['help', _('help'), '?']) or self.env.user.odoobot_failed
```

Returns `True` if:
1. Body contains `"help"`, the translated `"help"`, or `"?"` (case-sensitive, token-matched).
2. `odoobot_failed` is `True` on the current user.

**L4 — i18n note:** `_('help')` is resolved at Python import time against the current DB locale. The help trigger adapts to the user's language, but only for the single registered translation of `"help"`.

---

#### `_get_style_dict() -> dict[str, Markup]`

```python
@staticmethod
def _get_style_dict() -> dict[str, Markup]:
    return {
        "new_line":             Markup("<br>"),
        "bold_start":           Markup("<b>"),
        "bold_end":             Markup("</b>"),
        "command_start":        Markup("<span class='o_odoobot_command'>"),
        "command_end":          Markup("</span>"),
        "document_link_start":  Markup("<a href='https://www.odoo.com/documentation' target='_blank'>"),
        "document_link_end":    Markup("</a>"),
        "slides_link_start":    Markup("<a href='https://www.odoo.com/slides' target='_blank'>"),
        "slides_link_end":      Markup("</a>"),
        "paperclip_icon":       Markup("<i class='fa fa-paperclip' aria-hidden='true'/>"),
    }
```

Returns `markupsafe.Markup` fragments for rich formatting. All values are hardcoded strings — no user input is interpolated into HTML, so there is no XSS vector.

---

### `discuss.channel` — Inherited Model

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/mail_bot/models/discuss_channel.py`

```python
class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'
```

#### `execute_command_help(command=None, **kwargs) -> None`

Extends the built-in `/help` slash command. Calls `super()` (which renders the standard help banner) then invokes `mail.bot._apply_logic(..., command="help")`, appending the bot's contextual guidance below.

```python
def execute_command_help(self, **kwargs):
    super().execute_command_help(**kwargs)
    self.env['mail.bot']._apply_logic(self, kwargs, command="help")
```

**L4 — Why call `super()` first?** The Discuss framework dispatches `/help` to `execute_command_help`. By calling `super()` first, the standard framework help is posted before the bot adds its response. Both messages appear in sequence in the channel. If `super()` were omitted, only the bot response would show.

#### `_message_post_after_hook(message, msg_vals) -> None`

The critical integration hook — called **after** `message_post()` commits successfully.

```python
def _message_post_after_hook(self, message, msg_vals):
    self.env["mail.bot"]._apply_logic(self, msg_vals)
    return super()._message_post_after_hook(message, msg_vals)
```

**L4 — Execution timing:** Runs in the **same database transaction** as `message_post`. If `_apply_logic` raises an exception, the user's message is already committed. The bot's response (`message_post`) runs in the same transaction, so both succeed atomically.

**L4 — Override ordering:** `super()` is called last. This is the standard template-method pattern for post-commit hooks — subclass side-effects (logging, notification, etc.) fire after the primary operation.

**L4 — Thread safety / deadlock risk:** `message_post` acquires a write lock on the channel record. Bot logic then calls `channel.sudo().message_post()` on the same channel. In very high-throughput channels (multiple users posting simultaneously), there is marginal risk of lock contention. Odoo's message-posting implementation releases locks before post-commit hooks in most paths, so this is theoretical rather than observed.

---

### `res.users` — Inherited Model

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/mail_bot/models/res_users.py`

```python
class ResUsers(models.Model):
    _inherit = 'res.users'
```

#### `odoobot_state`

```python
odoobot_state = fields.Selection([
    ('not_initialized',           'Not initialized'),
    ('onboarding_emoji',          'Onboarding emoji'),
    ('onboarding_attachement',    'Onboarding attachment'),  # note: typo "attachement" in source
    ('onboarding_command',        'Onboarding command'),
    ('onboarding_ping',           'Onboarding ping'),
    ('onboarding_canned',         'Onboarding canned'),
    ('idle',                      'Idle'),
    ('disabled',                  'Disabled'),
], string="OdooBot Status", readonly=True, required=False)
```

- `readonly=True` — cannot be set directly by the user in the UI. Set exclusively by bot logic or admin DB operations.
- `required=False` — a falsy default (`False`) is used in addition to `"not_initialized"`. The init guard checks `in [False, "not_initialized"]`.
- Tracks the **last step the bot sent**, not the user's last action. Transitions are driven by detecting the correct next user input.

**L4 — Typo:** The selection label is `'Onboarding attachement'` (single `t`). This is present in Odoo 19 source and has not been corrected. It does not affect functionality.

#### `odoobot_failed`

```python
odoobot_failed = fields.Boolean(readonly=True)
```

Set `True` when the user sends an incorrect input during any onboarding step. Forces `_is_help_requested()` to return `True`, triggering a contextual re-prompt instead of a generic fallback.

**Reset pattern:** Set `False` on every successful state transition. A stuck user who types `help` at the right moment still advances (since `command == 'help'` triggers `onboarding_command` even with `odoobot_failed = True`).

#### `SELF_READABLE_FIELDS` (property override)

```python
@property
def SELF_READABLE_FIELDS(self):
    return super().SELF_READABLE_FIELDS + ['odoobot_state']
```

Exposes `odoobot_state` to the user's own session record, enabling the frontend to display the onboarding step indicator. `odoobot_failed` is intentionally excluded — users should not see this internal failure flag.

#### `_on_webclient_bootstrap() -> None`

Framework hook invoked when the web client initializes a user session. Fires on every full-page load or session refresh.

```python
def _on_webclient_bootstrap(self):
    super()._on_webclient_bootstrap()
    if self._is_internal() and self.odoobot_state in [False, "not_initialized"]:
        self._init_odoobot()
```

**Trigger condition:** The init guard `[False, "not_initialized"]` prevents re-initialization for users who completed the tour (`idle`) or explicitly disabled the bot (`disabled`). The tour can only be restarted via the `"start the tour"` keyword.

**L4 — Boot race condition:** `_on_webclient_bootstrap` fires on every page load. The guard prevents re-init, but during the first load, `_init_odoobot`'s `message_post` could theoretically race with the user's first message. The `author_id` guard in `_apply_logic` prevents the bot from responding to itself in this case.

#### `_init_odoobot() -> discuss.channel`

Creates a 1-on-1 DM with OdooBot and sends the welcome message.

```python
def _init_odoobot(self):
    self.ensure_one()
    odoobot_id = self.env['ir.model.data']._xmlid_to_res_id("base.partner_root")
    channel = self.env['discuss.channel']._get_or_create_chat([odoobot_id, self.partner_id.id])
    message = Markup("%s<br/>%s<br/><b>%s</b> <span class='o_odoobot_command'>:)</span>") % (
        _("Hello,"),
        _("Odoo's chat helps employees collaborate efficiently. I'm here to help you discover its features."),
        _("Try to send me an emoji")
    )
    channel.sudo().message_post(
        author_id=odoobot_id,
        body=message,
        message_type="comment",
        silent=True,
        subtype_xmlid="mail.mt_comment",
    )
    self.sudo().odoobot_state = 'onboarding_emoji'
    return channel
```

1. Resolves `base.partner_root` via XML ID lookup (`ir.model.data`).
2. Calls `discuss.channel._get_or_create_chat()` — if the chat already exists (e.g. previously completed and then restarted), it returns the existing channel instead of creating a duplicate.
3. Posts the greeting with HTML formatting — ` :)` is rendered as an `o_odoobot_command` pill badge.
4. Writes `odoobot_state = 'onboarding_emoji'` via `sudo()` to bypass the `readonly=True` ORM attribute (the bot's own code path sets this).

---

## Data File

**`data/mailbot_data.xml`**

```xml
<record id="base.user_root" model="res.users">
    <field name="odoobot_state">disabled</field>
</record>
```

Sets `odoobot_state = 'disabled'` for `base.user_root` (the system/pseudo-user). This prevents the bot from activating in public/portal contexts where `base.user_root` might appear as a message author.

**L4 — Why not `base.partner_root`?** `base.partner_root` is a `res.partner`, not a `res.users`. The `odoobot_state` field lives on `res.users`. Portal users are `res.users` records with `share=True`, but `_is_internal()` returns `False` for them, so `_on_webclient_bootstrap` never fires regardless.

---

## Views

**`views/res_users_views.xml`** — inherits `mail.view_users_form_mail`

```xml
<field name="notification_type" position="after">
    <field name="odoobot_state"
           groups="base.group_no_one"
           readonly="0"
           invisible="share"/>
</field>
```

- `groups="base.group_no_one"` — visible only to developers/admins (the "No One" group).
- `readonly="0"` — overrides the ORM `readonly=True` attribute for this view, allowing admins to manually reset a user's state via the form.
- `invisible="share"` — hidden for portal users, consistent with the `_is_internal()` guard.

---

## Assets

**`static/src/scss/odoobot_style.scss`**

```scss
.o_odoobot_command {
    background-color: $gray-200;
    border-radius: 4px;
    padding: 2px;
    padding-left: 10px;
    padding-right: 10px;
    font-weight: bold;
}
```

Renders inline command tokens (` :)`, `/help`, `@OdooBot`, `::`) as pill-style inline badges. The `o_odoobot_command` class is applied via the `_get_style_dict()` HTML fragments in `mail_bot.py`.

---

## Cross-Module Integration Map

```
mail_bot
 ├── depends: mail
 │
 ├── mail.bot (AbstractModel)
 │   ├── writes: mail.message              — bot response posts
 │   ├── writes: mail.canned.response      — creates/unlinks onboarding canned response
 │   ├── reads:  discuss.channel           — channel_type, channel_member_ids
 │   └── reads:  res.users                 — odoobot_state, odoobot_failed
 │
 ├── discuss.channel (Inherit)
 │   ├── overrides: _message_post_after_hook  ← called by mail.message.message_post()
 │   ├── overrides: execute_command_help      ← called by /help command dispatcher
 │   └── uses: discuss.channel._get_or_create_chat() (from mail)
 │
 └── res.users (Inherit)
     ├── extends: _on_webclient_bootstrap     ← web client bootstrap hook
     ├── field:  odoobot_state               — state machine value
     ├── field:  odoobot_failed              — failure flag
     └── uses: ir.model.data._xmlid_to_res_id("base.partner_root")
```

---

## Odoo 18 → 19 Changes

| Area | Change |
|---|---|
| **IAP/AI integration** | **Removed.** Odoo 16–17 routed unrecognized messages to an IAP endpoint. Odoo 18 and 19 use only static fallback strings. |
| **State machine** | No structural changes. `onboarding_attachement` label typo is present in both Odoo 18 and 19. |
| **`_message_post_after_hook`** | Hook mechanism existed in Odoo 16+; unchanged. |
| **`_on_webclient_bootstrap`** | Same trigger pattern in 18 and 19. |
| **`silent=True` on bot messages** | Consistent across all versions. |
| **`auto_install` flag** | `True` in both 18 and 19. |

---

## Security Considerations

| Concern | Assessment |
|---|---|
| **Bot identity** | OdooBot is `base.partner_root` — system partner with no login. Cannot be impersonated via UI. |
| **Message authorship** | All bot messages have `author_id = base.partner_root`. Any message with that author is a bot message. |
| **Emoji detection DoS** | `itertools.chain` generator is lazy. A 10,000-char message causes at most 10,000 `chr()` calls, not memory explosion. |
| **HTML injection** | Bot HTML is constructed from `markupsafe.Markup` hardcoded strings with `_()` translations. No user input flows into HTML. |
| **State tampering** | `odoobot_state` is `readonly=True` in the ORM. Only `sudo()` writes from within `mail_bot` code can change it. The view `readonly="0"` allows admin-level resets. |
| **Bot loop / re-entrancy** | `_apply_logic` returns immediately if `author_id == odoobot_id`. Bot never responds to itself. |
| **`sudo()` usage** | Two sites only: (1) `channel.sudo().message_post()` for bot replies, (2) `self.sudo().write({'odoobot_state': ...})` for state writes. Both confined to module's own code paths. |

---

## Performance Profile

| Operation | Cost | Trigger |
|---|---|---|
| `_message_post_after_hook` fires | Per message | Every `message_post` on any channel. Early-exits if `message_type != "comment"` or author is bot. |
| Emoji detection `_body_contains_emoji` | O(body_len), short-circuits | Only when `odoobot_state` is `onboarding_emoji`. |
| `_get_answer` DB reads | 2 reads per bot message | `odoobot_state` and `odoobot_failed` via `self.env.user`. |
| Bot response `message_post` | 1 `mail.message` INSERT + channel write | Only when `_get_answer` returns a truthy value. |
| `_on_webclient_bootstrap` | 1 channel + 1 message INSERT + 1 user WRITE | Once per eligible user session (guarded). |
| Canned response creation | 1 INSERT on `mail.canned.response` | Once during onboarding (`onboarding_attachement` step). |
| Canned response deletion | 1 DELETE on `mail.canned.response` | Once when `onboarding_canned` completes. |

---

## Failure Modes

| Failure | Result | Recovery |
|---|---|---|
| `ir.model.data._xmlid_to_res_id("base.partner_root")` fails | `ValueError`, bot silently does nothing | Install `base` module; check XML ID integrity. |
| `discuss.channel._get_or_create_chat()` returns `False` | `_init_odoobot` returns `False`, no message sent; user stays `not_initialized` | `_on_webclient_bootstrap` re-fires on next page load. |
| Canned response INSERT fails (access rights) | Bot sends `onboarding_canned` prompt; transition to `idle` never fires. User stuck. | Admin manually resets state to `idle`. |
| DB write to `odoobot_state` fails (concurrent update) | `OperationalError` propagates. User message committed, bot does not respond. | Next message retries. Partial state updates may cause step-skipping. |
| `onboarding_canned` transition: `canned_response_ids` context not set | Transition does not fire. User stuck in `onboarding_canned`. | Admin manually resets state to `idle`. |
| `base.user_root` state not set to `'disabled'` | Portal/public sessions might trigger bot init (though `_is_internal()` guard prevents `_on_webclient_bootstrap`). | Admin corrects data. |

---

## Related Documentation

- [Modules/mail](modules/mail.md) — `mail.message` posting lifecycle and `_message_post_after_hook` contract
- [Modules/im_livechat](modules/im_livechat.md) — `discuss.channel` and DM creation via `_get_or_create_chat`
- [Core/API](core/api.md) — `@api.model`, `@api.depends`, and stateful dispatch patterns
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — state machine pattern used for `odoobot_state`
- [Tools/ORM Operations](tools/orm-operations.md) — `sudo()`, `write()`, `message_post()` usage patterns

---

**Tags:** #odoo #odoo19 #modules #discuss #mail_bot #chatbot #onboarding
