# Website Mail

`website_mail` is a thin integration layer that bridges the public website with Odoo's mail follower system. It exposes JSON-RPC endpoints for the frontend Follow widget and does not introduce any persistent models of its own.

**Module flags**: `auto_install: True` — silently installed when both `website` and `mail` are present.

---

## Module Profile

| Attribute | Value |
|---|---|
| **Category** | Website/Website |
| **Depends** | `website`, `mail` |
| **Version** | 0.1 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **installable** | True |

**Data files loaded**: `views/website_mail_templates.xml`

**Static assets bundled**:

| Asset | Bundle | Purpose |
|---|---|---|
| `static/src/interactions/follow.js` | `web.assets_frontend` | `Follow` Interaction — the runtime click handler for subscribe/unsubscribe |
| `static/src/css/website_mail.scss` | `web.assets_frontend` | CSS toggle: shows/hides the Follow/Unfollow button based on `data-follow` attribute |
| `website_mail/static/src/interactions/follow.edit.js` (via `website`) | `web.assets_inside_builder_iframe` | Edit-mode handler for the Follow snippet in the Website Builder |

---

## Models

The module defines no persistent models. It extends two abstract/framework models:

### Extended: `ir.http` (Abstract)

**File**: `models/ir_http.py`
**Inheritance**: Classic (`_inherit = 'ir.http'`)

```python
@classmethod
def _get_translation_frontend_modules_name(cls) -> list[str]:
```

**Purpose**: Appends `'mail'` to the list of module names whose strings are harvested for frontend translation. Without this, translatable strings from the `mail` addon (e.g. "Follow", "Unsubscribe" in the follow template) would not appear in the website's inline translation UI.

**L3 — Why this matters**: `_get_translation_frontend_modules_name` is called by `ir.translation` when collecting `.qweb` and JS strings for the website editor's live translation sidebar. Adding `'mail'` here allows content editors to translate the Follow widget labels without needing a full PO/MO file edit.

---

### Extended: `publisher_warranty.contract` (Abstract)

**File**: `models/update.py`
**Inheritance**: Classic (`_inherit = 'publisher_warranty.contract'`)

```python
@api.model
def _get_message(self) -> dict:
```

**Purpose**: Injects `'website': True` into the dictionary returned by `super()._get_message()`, which is the payload sent in Odoo Online update heartbeat pings (`/publisher/cgi/publisher/index`). This signals to Odoo's SaaS infrastructure that this instance has the website module enabled.

---

## Controllers

Controller class: `WebsiteMail` in `controllers/main.py`
**Inheritance**: Inherits from `odoo.http.Controller`
**Auth**: `website=True` on all routes — forces `request.website` context resolution; fallback to `request.website.user_id` (the public user) when the visitor has no session.

---

### Route: `POST /website_mail/follow`

```python
@http.route(['/website_mail/follow'], type='jsonrpc', auth="public", website=True)
def website_message_subscribe(
    self,
    id: int | str,
    object: str,               # e.g. "event.event", "crm.lead", "product.product"
    message_is_follower: str, # "on"  → currently following → call message_unsubscribe
                              # "off" → not following → call message_subscribe
    email: str,
    **post                  # captures recaptcha_token_response, turnstile_captcha
) -> bool:
```

**Full execution logic**:

```
1. res_id = int(id)               # coerce; raises ValueError on bad input
2. record = request.env[object].browse(res_id).exists()
   if not record: return False    # silently fail if record was deleted
3. record.check_access('read')    # access check before any mutation

4. Determine partner:
   ├─ If request.env.user != request.website.user_id
   │   └─ partner_ids = request.env.user.partner_id.ids
   │       → logged-in or portal user; uses their existing partner record
   └─ Else (public user):
       ├─ Try request.env['ir.http']._verify_request_recaptcha_token('website_mail_follow')
       │   ├─ Success  → no_create = False  (partner may be created)
       │   └─ Exception → no_create = True (partner creation blocked)
       └─ partner_ids = record.sudo()._partner_find_from_emails_single([email], no_create=no_create).ids

5. Toggle follower state:
   ├─ If message_is_follower == "on"   # user is currently following
   │   └─ record.sudo().message_unsubscribe(partner_ids)
   │       return False                # means: now unfollowed
   └─ Else (user is NOT following)
       ├─ request.session['partner_id'] = partner_ids[0]
       │   → Persists partner ID in session so is_follower can identify the anonymous user
       └─ record.sudo().message_subscribe(partner_ids)
           return True                 # means: now following
```

**L3 — The subscribe/unsubscribe inversion**: The logic is deliberately inverted. When the UI sends `message_is_follower="on"` (meaning "I am currently following"), the server *unfollows*. This is because the widget's action is "toggle the opposite of the current state" — the button label says what clicking it *will do*, not what state it currently reflects. The `data-follow` attribute on the DOM element tracks the actual subscription state as determined by the `is_follower` check on page load.

**L3 — Partner creation via `_partner_find_from_emails_single`**: Implemented in `mail.models.mail_thread`. When `no_create=False`, it calls `res.partner._find_or_create_from_emails()`, which will create a new `res.partner` with `name=email` (split via email parsing) and `email_normalized=...`. If `no_create=True` (reCAPTCHA failed), it only searches existing partners and returns empty if no match. The partner is assigned to the session via `request.session['partner_id']` so subsequent `is_follower` calls can identify the anonymous subscriber.

**L3 — Why `.sudo()` before `message_subscribe/unsubscribe`**: The public user lacks ACL to write to `mail.followers` (the relation table). `sudo()` bypasses record-level security but still respects model-level access rights. It does not bypass `ir.rule` — Odoo's record rules on `mail.followers` may still filter results, but since those rules typically allow "create if you are the partner," this works for self-subscription.

**L4 — Performance implications**:

- Each `message_subscribe`/`message_unsubscribe` call triggers `mail.followers` create or delete + potentially `mail.notification` records. Under heavy load, consider batching.
- `_partner_find_from_emails_single` with `no_create=False` issues a `res.partner` create in a public-facing context — throttling or CAPTCHA rate limiting is the caller's responsibility (handled by `google_recaptcha`/`website_cf_turnstile`).
- The `check_access('read')` on line 3 is a live ACL check for the `object` model, not `mail.followers`. It prevents public users from discovering the internal IDs of records they cannot access.

**L4 — Edge cases / failure modes**:

| Scenario | Behavior |
|---|---|
| Record deleted between page load and follow click | `record.exists()` returns empty recordset → `if not record: return False`. The frontend receives `false` and no DOM update occurs. |
| Email fails validation regex `/.+@.+/` | JS `onToggleFollowClick` returns early; no RPC call made |
| `request.session['partner_id']` set to deleted partner ID | `is_follower` route checks with `sudo()` and `.exists()` — stale session ID gracefully degrades to no-match |
| ReCAPTCHA token invalid/missing | `no_create=True` prevents partner creation; if no existing partner matches the email, empty list → `IndexError` on `partner_ids[0]`. Fixed in Odoo 19 by the `try/except` — if `_verify_request_recaptcha_token` raises, `no_create=True` is forced |
| `record._partner_find_from_emails_single` called on non-`MailThread` model | Falls back to generic `MailThread` implementation via duck-typing: `hasattr(record, '_partner_find_from_emails_single')` check in the method body |
| Multiple tabs with conflicting follow state | No locking; last write wins |

---

### Route: `POST /website_mail/is_follower` (readonly)

```python
@http.route(['/website_mail/is_follower'], type='jsonrpc', auth="public", website=True, readonly=True)
def is_follower(self, records: dict[str, list[int]], **post) -> list:
    """ Returns follower status for a batch of records across multiple models.

    :param records: {
            'crm.lead': [10, 20, 30],
            'product.product': [5],
        }
    :returns: [
        {   'is_user': bool,    # True if authenticated (not public user)
            'email': str,       # partner email or ""
        },
        {   'crm.lead': [20],           # list of res_ids the partner follows
            'product.product': [5],
        }
    ]
    """
```

**Full execution logic**:

```
1. user = request.env.user
   public_user = request.website.user_id

2. Identify partner:
   ├─ If user != public_user
   │   └─ partner = request.env.user.partner_id
   └─ Elif 'partner_id' in session
       └─ partner = request.env['res.partner'].sudo().browse(session_pid)

3. For each (model, res_ids) in records:
   └─ mail_followers_ids = request.env['mail.followers'].sudo()._read_group([
            ('res_model', '=', model),
            ('res_id', 'in', res_ids),
            ('partner_id', '=', partner.id)
        ], ['res_id'])
     res[model].extend(res_id for [res_id] in mail_followers_ids)

4. Return [{is_user, email}, res]
```

**L3 — `_read_group` used instead of `search`**: `_read_group` returns a flat list of `[res_id]` tuples directly, avoiding ORM object instantiation. This is more efficient when only the `res_id` field is needed, which is the case here. The `_read_group` call is `sudo()` because the public user cannot read `mail.followers` (field group: `base.group_user`).

**L3 — Why `readonly=True`**: The `readonly=True` route flag is an Odoo security hint — it tells the CSRF middleware that this route should not mutate server state. It is advisory, not enforced, but signals intent and prevents accidental CSRF token requirement on GET-equivalent calls.

**L4 — Performance implications**:

- `_read_group` on `mail.followers` with `partner_id` and `res_id` domain is well-indexed (composite index on `(res_model, res_id, partner_id)` is created by the `mail` module's `ir.module.constraint`).
- The partner lookup for session-based users uses `sudo()` — acceptable here because the session partner ID is already validated.
- Batch resolution in a single RPC call avoids N round-trips. However, if `records` contains many models with thousands of IDs each, the `mail.followers` table can become a bottleneck.

**L4 — Edge cases**:

| Scenario | Behavior |
|---|---|
| `records` is `{}` (empty dict) | Loop body never executes; returns `[{is_user, email}, {}]` — safe |
| Unknown model name in `records` | `_read_group` returns empty for that model; no error raised |
| Session `partner_id` was never set | `request.session.get('partner_id')` returns `None` → falsy → `partner = None` → no subscription data returned |
| Record exists but partner is not a follower | That `res_id` absent from the model's list in the response |
| Model has no `message_follower_ids` field | No error raised; `_read_group` on `mail.followers` is a direct table read, not a computed field |

---

## QWeb Template

**File**: `views/website_mail_templates.xml`

**Template ID**: `website_mail.follow`

```xml
<div t-attf-class="input-group js_follow #{div_class}"
     t-att-data-id="object.id"
     t-att-data-object="object._name"
     t-att-data-follow="object.id and object.message_is_follower and 'on' or 'off'"
     t-att-data-unsubscribe="'unsubscribe' if 'unsubscribe' in request.params else None">
    <input type="email" name="email" class="js_follow_email form-control"
           placeholder="your email..."/>
    <div t-if="icons_design and not request.env.user._is_public()" class="js_follow_icons_container">
        <!-- inline icon buttons (icons_design mode) -->
        <button class="btn text-reset js_unfollow_btn"><small>Unfollow</small><i class="fa fa-fw ms-1"/></button>
        <button class="btn text-reset js_follow_btn"><small>Follow</small><i class="fa fa-fw ms-1"/></button>
    </div>
    <t t-else="">
        <!-- standard Bootstrap button pair -->
        <button class="btn btn-secondary js_unfollow_btn">Unsubscribe</button>
        <button class="btn btn-primary js_follow_btn">Subscribe</button>
    </t>
</div>
```

**Context variables**:

| Variable | Type | Source | Purpose |
|---|---|---|---|
| `object` | `mail.thread` record | Caller | The record being followed; provides `object._name` and `object.id` as `data-*` attributes |
| `div_class` | `str` | Caller | Optional extra CSS classes for the wrapper |
| `icons_design` | `bool` | Caller | Switches between icon-buttons and standard Bootstrap button pair |
| `request.env.user._is_public()` | bool | Odoo | Detects if current user is the public visitor |

**L3 — How the template drives the JS Interaction**: The `Follow` Interaction in `follow.js` attaches via `static selectorHas = ".js_follow"` — it activates on any `#wrapwrap` element that contains a `.js_follow` div. The template's `data-id`, `data-object`, and `data-follow` attributes are the primary communication channel between the QWeb-rendered HTML and the Odoo Interaction JS class.

**L3 — Two rendering modes**:

1. **`icons_design=True` + logged-in user**: Renders inline FontAwesome bell icon (`\f0f3`) and an active unfollow icon (`\f1f6` on hover). Used in header/footer bars where space is constrained.
2. **Default**: Renders standard Bootstrap-styled `Subscribe`/`Unsubscribe` buttons. Used in main page content.

**CSS toggle mechanism** (`website_mail.scss`):
- `[data-follow='on'] .js_follow_btn, [data-follow='off'] .js_unfollow_btn` → `display: none`
- This is a pure CSS state machine driven by the `data-follow` attribute, which the JS Interaction updates after each successful RPC call.

---

## JavaScript Interaction (`follow.js`)

**Class**: `Follow extends Interaction`
**Registry**: `public.interactions` as `"website_mail.follow"`

**L4 — Architecture decision — Odoo Interactions vs legacy `$.ajax`**: The module uses the Odoo 18+ Interaction registry pattern instead of jQuery AJAX. This means the Follow behavior participates in Odoo's interaction lifecycle (`willStart`, `willEdit`, etc.) and is editable via the Website Builder's snippet panel. The legacy `website_mail` in older Odoo versions used inline `<script>` tags with `$.post()`.

**`willStart()` — page load initialization**:
1. Collects all `.js_follow` elements on the page
2. Groups them by model name into `records`
3. Fires parallel RPCs: `is_follower` (for all records) and `recaptcha.loadLibs()` (to warm the reCAPTCHA widget)
4. Updates each `.js_follow` element's `data-follow` attribute via `toggleSubscription`

**`onToggleFollowClick()` — subscribe/unsubscribe**:
1. Validates email with regex `/.+@.+/
2. Fetches reCAPTCHA token via `recaptcha.getToken("website_mail_follow")` and optionally Turnstile (`website_cf_turnstile`) token
3. Calls `POST /website_mail/follow` with all tokens
4. Calls `toggleSubscription` with the returned boolean to update `data-follow` and DOM state

**L4 — `ReCaptcha` dependency**: The interaction imports `ReCaptcha` from `@google_recaptcha/js/recaptcha`. If the `google_recaptcha` module is not installed, `loadLibs()` is a no-op and `getToken()` returns an empty token. The server catches this via `_verify_request_recaptcha_token` — if it raises (module missing or token invalid), `no_create=True` prevents partner creation.

---

## Cross-Module Integration Map

```
website_mail
  ├── depends: website
  │     ├── ir.http               → adds 'mail' to frontend translations
  │     ├── website.layout         → provides #wrapwrap context for Follow interaction
  │     └── website builder       → loads follow.edit.js for snippet editing
  │
  ├── depends: mail
  │     ├── mail.thread            → provides message_is_follower, message_subscribe,
  │     │                              message_unsubscribe, _partner_find_from_emails_single
  │     ├── mail.followers         → relation table written/read by the controller
  │     ├── res.partner            → created/found by _partner_find_from_emails_single
  │     ├── google_recaptcha      → optional: _verify_request_recaptcha_token
  │     └── website_cf_turnstile   → optional: turnstile_captcha token support
  │
  └── consumed by: website_event, website_mass_mailing, website_blog, etc.
        (those modules include website_mail's follow template on their pages)
```

**Modules that re-use this infrastructure** (include the `website_mail.follow` template or call `/website_mail/follow`):
- `website_event` — event pages with "Follow Event" widget
- `website_mass_mailing` — newsletter subscription (has its own controller with same pattern)
- `website_blog` — blog posts with follow buttons
- `website_sale` — product pages (optional, depending on config)

---

## Security Analysis

| Surface | Access level | Mitigation |
|---|---|---|
| `POST /website_mail/follow` | `auth="public"` | `check_access('read')` on target record; reCAPTCHA/Turnstile tokens |
| `POST /website_mail/is_follower` | `auth="public"` | `readonly=True`; no data revealed beyond subscription status |
| `mail.followers` table | Hidden from public (`base.group_user`) | All reads use `.sudo()`; only own-follower records affect the response |
| Partner creation | Via `_partner_find_from_emails_single` | Blocked if reCAPTCHA fails; `no_create=True` |
| Email harvest via follow | Public user can probe email→follower mapping | Partner email only returned if user is already following or is logged in |

**L4 — Information disclosure risk**: An attacker could iterate over `res_id` values to probe whether a given partner follows a specific record. The response only reveals the partner's email if they are following *something* on the page (determined in `is_follower` response), and only for records rendered on that page. Mass enumeration requires rendering each page, limiting the practical attack surface. Rate limiting at the WSGI/reverse-proxy layer is the recommended additional control.

**L4 — CSRF**: The `jsonrpc` route type in Odoo uses a session-based token for CSRF. However, `auth="public"` combined with JSON-RPC can be served without CSRF tokens when the session is anonymous and the route is marked `website=True`. reCAPTCHA token binding provides an indirect CSRF mitigation for the follow action specifically.

---

## Historical Changes (Odoo 17 → 18 → 19)

| Change | Version | Impact |
|---|---|---|
| Replaced jQuery AJAX with Odoo `Interaction` class | Odoo 18 | Follow widget now participates in Website Builder editing. `follow.js` rewritten as ES6 class with `registry.category("public.interactions")` |
| reCAPTCHA token enforcement via `_verify_request_recaptcha_token` | Odoo 18 | Prevents anonymous partner creation without solving a CAPTCHA; previously email-only |
| `message_is_follower` field added to `mail.thread` | Odoo 18 | The `data-follow` attribute on the template now reads `object.message_is_follower` instead of computing it inline |
| `_partner_find_from_emails_single` added to `mail.thread` | Odoo 18 | Unified partner-finding utility used by both `mail` and `website_mail`; replaces fragmented `partner_find` methods |
| Turnstile support via `turnstile_captcha` parameter | Odoo 19 | Added alongside reCAPTCHA; the `Follow` JS interaction collects both token types |
| `is_follower` route switched to `_read_group` | Odoo 19 | Replaced `search + mapped` — avoids ORM instantiation overhead for large record batches |
| `publisher_warranty.contract._get_message` extension | Odoo 17+ | Stable; unchanged purpose across versions |

---

## Tags

`#modules` `#website` `#mail` `#website_mail` `#follow` `#subscription`

---

## Related

- [Modules/website](Modules/website.md) — Base website, provides `website.layout`, `#wrapwrap`, and `request.website`
- [Modules/mail](Modules/mail.md) — Core messaging: `mail.thread`, `mail.followers`, `message_subscribe`
- [Modules/website_mass_mailing](Modules/website_mass_mailing.md) — Newsletter subscription with similar CAPTCHA + subscribe pattern
- [Modules/website_event](Modules/website_event.md) — Event follow widget using `website_mail.follow` template
