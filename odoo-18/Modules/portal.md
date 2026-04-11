---
Module: portal
Version: Odoo 18
Type: Integration
---

# portal — Customer Portal and Access Control

## Overview

The `portal` module (`addons/portal/`) is a **core integration module** that enables external customers to access specific Odoo records through a secure, read-only or partially-editable web interface. It provides the infrastructure for portal-based document sharing, access token management, portal chatter, and the portal wizard that grants customers access to the system.

**Core responsibilities**:
1. **`portal.mixin`** — Abstract mixin any model can inherit to become portal-accessible
2. **Access tokens** — UUID-based tokens for sharing records without login
3. **HMAC-signed hash** — Partner-authenticated portal chatter posting
4. **Portal wizard** — Grant/revoke portal access to contacts
5. **Portal share wizard** — Share records with specific partners via email
6. **Controllers** — `/my/*` routes for portal pages and chatter
7. **Portal chatter** — Website-optimized messaging on shared records

**Depends**: `web`, `web_editor`, `http_routing`, `mail`, `auth_signup`
**Category**: Hidden
**License**: LGPL-3

---

## Module Structure

```
portal/
├── __manifest__.py
├── __init__.py
├── utils.py                        # Token/hash validation helpers
├── controllers/
│   ├── __init__.py
│   ├── portal.py                   # CustomerPortal controller (main /my/* routes)
│   ├── mail.py                    # PortalChatter + MailController override
│   ├── thread.py                  # ThreadController override (portal posting)
│   ├── attachment.py              # PortalAttachmentController (delete own attachments)
│   ├── message_reaction.py        # PortalMessageReactionController
│   └── web.py                    # Home controller override (portal → /my redirect)
├── models/
│   ├── __init__.py
│   ├── portal_mixin.py           # portal.mixin abstract model
│   ├── mail_thread.py            # mail.thread extension (website_message_ids, _sign_token)
│   ├── mail_message.py           # mail.message extension (portal_message_format)
│   ├── ir_http.py               # ir.http extension (translation modules)
│   ├── ir_ui_view.py            # ir.ui.view extension (customize_show field)
│   ├── ir_qweb.py               # ir.qweb extension (portal frontend env)
│   ├── res_partner.py           # res.partner extension (_can_edit_name, can_edit_vat)
│   ├── res_config_settings.py   # Portal API keys config toggle
│   └── res_users_apikeys_description.py  # API key creation for portal users
├── wizard/
│   ├── __init__.py
│   ├── portal_wizard.py         # Portal access grant/revoke wizard
│   ├── portal_wizard_views.xml
│   ├── portal_share.py         # Record sharing wizard
│   └── portal_share_views.xml
├── views/
│   ├── portal_templates.xml
│   ├── mail_templates_public.xml
│   └── res_config_settings_views.xml
└── security/
    └── ir.model.access.csv       # ACLs for portal.share, portal.wizard, portal.wizard.user
```

---

## Models

### `portal.mixin` — `models/portal_mixin.py`

**The foundational mixin** that makes any Odoo model portal-accessible. Inherit from this mixin to give a model portal URL generation, access tokens, and the sharing infrastructure.

```python
class PortalMixin(models.AbstractModel):
    _name = "portal.mixin"
    _description = 'Portal Mixin'
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `access_url` | Char (computed) | The portal URL for this record. Override `_compute_access_url` in your model. Default is `'#'`. |
| `access_token` | Char (copy=False) | UUID security token. Generated on first access via `_portal_ensure_token()`. |
| `access_warning` | Text (computed) | Warning shown if access is restricted. Default empty string. |

#### Key Methods

**`_compute_access_url()`** — Default returns `'#'`. Override in your model:
```python
def _compute_access_url(self):
    for order in self:
        order.access_url = f'/my/orders/{order.id}'
```

**`_portal_ensure_token()`** — Lazy token generator:
```python
def _portal_ensure_token(self):
    if not self.access_token:
        self.sudo().write({'access_token': str(uuid.uuid4())})
    return self.access_token
```
Called automatically when generating share URLs. Uses `sudo()` and returns the token for use in URLs. Tokens are never regenerated once created (stable URLs).

**`_get_share_url(redirect=False, signup_partner=False, pid=None, share_token=True)`** — Builds the shareable URL:

| Param | Effect |
|-------|--------|
| `redirect=True` | Returns `/mail/view?model=...&res_id=...` — used in emails so Odoo can log the read |
| `signup_partner=True` | Adds signup auth params for partners without portal accounts |
| `pid=<partner_id>` | Adds `pid` and `hash` params for portal chatter authentication |
| `share_token=True` | Includes `access_token` in URL |

Returns the URL string directly (not a controller redirect).

**`_get_access_action(access_uid=None, force_website=False)`** — Called when opening a record from the backend:
- If the current user is a portal user (`user.share = True`) or `force_website=True`, redirects to the portal URL instead of the backend form view
- Falls back to the standard form view for internal users

**`get_portal_url(suffix=None, report_type=None, download=None, query_string=None, anchor=None)`** — Convenience wrapper around `_get_share_url()` with extra params for reports and downloads.

**`action_share()`** — Server action that opens the `portal.share` wizard for the current record.

#### L4 — How portal access actually works

```
Portal user clicks /my/orders/123?access_token=abc...
         ↓
PortalController.home() or /my/* route runs
         ↓
Controller calls record.check_access('read') as portal user
  → Fails with AccessError if no rights
         ↓ OR succeeds
Record has portal.mixin → has access_url + access_token
         ↓
Portal template renders the record data
```

The portal.mixin does NOT bypass access checks. It only provides the URL infrastructure. Actual read/write access is controlled by:
1. The partner's relationship to the record (e.g., `partner_id = request.env.user.partner_id`)
2. Record rules on the model
3. The access token as a fallback for public sharing

---

### `mail.thread` — `models/mail_thread.py`

Extends `mail.thread` to add portal-specific notification routing and thread access validation.

```python
class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'
    _mail_post_token_field = 'access_token'  # token field for portal posting
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `website_message_ids` | One2many(`mail.message`) | Messages on this record that are visible on the portal. Domain filters to `message_type in ('comment', 'email', 'email_outgoing', 'auto_comment')`. |

#### Key Methods

**`_notify_get_recipients_groups(message, model_description, msg_vals=None)`** — Adds a `portal_customer` notification group:
- Generates `access_token`, `pid`, `hash` params for the notification email link
- Ensures portal users receive buttons in notification emails
- Uses `signup_get_auth_param()` to embed signup tokens for partners without portal accounts

**`_sign_token(pid)`** — HMAC-SHA256 signature for portal chatter:
```python
def _sign_token(self, pid):
    secret = self.env["ir.config_parameter"].sudo().get_param("database.secret")
    token = (self.env.cr.dbname, self.access_token, pid)
    return hmac.new(secret.encode('utf-8'), repr(token).encode('utf-8'), hashlib.sha256).hexdigest()
```
The hash proves the recipient opened their own link. It binds the access token + database name + partner ID. Validated by `validate_thread_with_hash_pid()` in `utils.py`.

**`_get_thread_with_access(thread_id, mode="read", **kwargs)`** — Three-layer access check:
1. Standard access check via `super()`
2. HMAC hash validation: `validate_thread_with_hash_pid(thread, hash, pid)`
3. Token validation: `validate_thread_with_token(thread, token)`

#### L4 — How portal chatter posting works

```
1. Partner opens /my/orders/123?access_token=...&pid=42&hash=abc
2. PortalChatter.portal_chatter_init() is called
3. get_portal_partner(thread, hash, pid, token) resolves the partner
4. ThreadController._prepare_post_data() is called
   → _prepare_post_data checks get_portal_partner()
   → If hash/pid valid: sets post_data["author_id"] = partner.id
   → If token valid: allows read-only access
5. Message is created with the portal partner as author
```

---

### `mail.message` — `models/mail_message.py`

Extends `mail.message` with portal-oriented formatting and editability checks.

#### Key Methods

**`portal_message_format(options=None)`** — Public API. Checks read access, then calls `_portal_message_format()`. Returns a list of formatted message dicts for the frontend.

**`_portal_message_format(properties_names, options=None)`** — Formats messages for the portal frontend:
- Computes `attachment_ids` with access tokens
- Generates `author_avatar_url` with token/hash support for privacy
- Resolves reactions and groups them
- Detects `is_message_subtype_note` for note vs. comment display
- Adds `published_date_str` (localized datetime string)

**`_is_editable_in_portal(**kwargs)`** — Determines if a portal user can edit their own message:
- Returns `True` if the message author is the portal partner
- Used by `thread.py` controller to allow editing

#### Default Format Properties

```python
{
    'attachment_ids', 'author_avatar_url', 'author_id', 'author_guest_id',
    'body', 'date', 'id', 'is_internal', 'is_message_subtype_note',
    'message_type', 'model', 'published_date_str', 'res_id', 'starred',
    'subtype_id', 'reactions', 'author', 'thread'
}
```

---

### `res.partner` — `models/res_partner.py`

Portal-specific partner overrides for portal self-service.

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _can_edit_name(self):
        """ Name can be changed more often than VAT. Portal users can always edit name. """
        self.ensure_one()
        return True

    def can_edit_vat(self):
        """ VAT is a commercial field synced to the commercial entity.
        Only the commercial partner (no parent) can edit it. """
        self.ensure_one()
        return not self.parent_id
```

**L4**: `_can_edit_name()` always returns `True` — portal users can update their display name. `can_edit_vat()` mirrors the backend commercial partner logic: only the top-level commercial entity (no `parent_id`) can edit VAT. This prevents child contact records from editing VAT, which is synced upward to the company.

---

### `ir.http` — `models/ir_http.py`

```python
class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        mods = super()._get_translation_frontend_modules_name()
        return mods + ['portal']
```

Includes `portal` in the list of modules whose translations are loaded on the frontend. This ensures portal page labels are translatable.

---

### `ir.ui.view` — `models/ir_ui_view.py`

```python
class View(models.Model):
    _inherit = "ir.ui.view"
    customize_show = fields.Boolean("Show As Optional Inherit", default=False)
```

The `customize_show` field allows portal optional-inherit views (Views → Customize menu) to appear as togglable options in the portal theme editor.

---

### `ir.qweb` — `models/ir_qweb.py`

```python
class IrQWeb(models.AbstractModel):
    _inherit = "ir.qweb"

    def _prepare_frontend_environment(self, values):
        irQweb = super()._prepare_frontend_environment(values)
        values.update(
            is_html_empty=is_html_empty,
            frontend_languages=lazy(lambda: irQweb.env['res.lang']._get_frontend())
        )
        return irQweb
```

Injects portal-specific template globals for rendering portal pages. `frontend_languages` is a lazy-loaded list of active website languages.

---

### `res.config.settings` — `models/res_config_settings.py`

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    portal_allow_api_keys = fields.Boolean(
        string='Customer API Keys',
        compute='_compute_portal_allow_api_keys',
        inverse='_inverse_portal_allow_api_keys',
    )
```

Toggles the `portal.allow_api_keys` ir.config_parameter. When enabled, portal users can create API keys (via `res.users.apikeys.description`).

---

### `res.users.apikeys.description` — `models/res_users_apikeys_description.py`

Extends the standard API key description check:

```python
class APIKeyDescription(models.TransientModel):
    _inherit = 'res.users.apikeys.description'

    def check_access_make_key(self):
        try:
            return super().check_access_make_key()
        except AccessError:
            if self.env['ir.config_parameter'].sudo().get_param('portal.allow_api_keys'):
                if self.env.user._is_portal():
                    return  # portal users can create keys
                raise AccessError(_("Only internal and portal users can create API keys"))
            raise
```

---

## Wizard: `portal.wizard` — `wizard/portal_wizard.py`

**Purpose**: Grant or revoke portal (`base.group_portal`) access for one or more partners. The wizard is opened from a partner list view's action.

### `portal.wizard` (TransientModel)

```python
class PortalWizard(models.TransientModel):
    _name = 'portal.wizard'
    _description = 'Grant Portal Access'
```

| Field | Type | Description |
|-------|------|-------------|
| `partner_ids` | Many2many(`res.partner`) | Partners selected in the wizard. Defaults to `active_ids` from context. Expands to include child contact records. |
| `user_ids` | One2many(`portal.wizard.user`) | Per-partner wizard lines, computed from `partner_ids` |
| `welcome_message` | Text | Custom invitation text appended to the standard welcome email |

**`_compute_user_ids`**: Dynamically generates a `portal.wizard.user` line for each partner in `partner_ids`.

### `portal.wizard.user` (TransientModel)

```python
class PortalWizardUser(models.TransientModel):
    _name = 'portal.wizard.user'
    _description = 'Portal User Config'
```

| Field | Type | Description |
|-------|------|-------------|
| `wizard_id` | Many2one(`portal.wizard`) | Parent wizard |
| `partner_id` | Many2one(`res.partner`) | Contact to configure |
| `email` | Char | Email for portal login (may differ from partner email) |
| `user_id` | Many2one(`res.users`) (computed sudo) | Existing user linked to this partner |
| `login_date` | Datetime (related) | Last login time of the portal user |
| `is_portal` | Boolean (computed) | True if partner's user is in `base.group_portal` |
| `is_internal` | Boolean (computed) | True if partner's user is internal |
| `email_state` | Selection (computed) | `'ok'`, `'ko'` (invalid email), or `'exist'` (email already taken) |

#### Wizard Actions

**`action_grant_access()`** — Grant portal access:
```
1. Validate email uniqueness (raises if 'ko' or 'exist')
2. If no user exists → create one via _create_user_from_template()
3. Add user to base.group_portal, remove from base.group_public
4. Set user.active = True
5. Call partner_id.signup_prepare() to generate signup token
6. Send portal welcome email via _send_email()
7. Refresh the modal
```

**`action_revoke_access()`** — Revoke portal access:
```
1. Set partner.signup_type = None (invalidate any signup tokens)
2. Remove user from base.group_portal, add back to base.group_public
3. Set user.active = False (archive the user, don't delete)
```

**`action_invite_again()`** — Resend the welcome email to an existing portal user.

**`_create_user()`** — Creates a new `res.users` via `_create_user_from_template()`:
```python
def _create_user(self):
    return self.env['res.users'].with_context(no_reset_password=True)._create_user_from_template({
        'email': email_normalize(self.email),
        'login': email_normalize(self.email),
        'partner_id': self.partner_id.id,
        'company_id': self.env.company.id,
        'company_ids': [(6, 0, self.env.company.ids)],
    })
```

**`_send_email()`** — Sends `portal.mail_template_data_portal_welcome`:
- Uses the portal user's language for localization
- Calls `partner.signup_prepare()` then `signup_get_url_for_action()`
- Renders template with `portal_url` and `lang` context

#### L4 — Portal wizard flow

```
Backend user selects partners → runs "Grant Portal Access" action
         ↓
portal.wizard.action_open_wizard() creates the wizard + opens form
         ↓
Backend user reviews each line (email, existing/new user status)
         ↓
Clicks "Grant Access" on individual lines
  → Creates res.users if needed (email = login)
  → Adds to base.group_portal
  → Sends invitation email with signup link
         ↓ OR clicks "Revoke Access"
  → Archives user, removes from portal group
         ↓
Partner receives email → clicks link → creates password → accesses /my/*
```

---

## Wizard: `portal.share` — `wizard/portal_share.py`

**Purpose**: Share a specific record with selected partners via email, with or without requiring a portal account.

```python
class PortalShare(models.TransientModel):
    _name = 'portal.share'
    _description = 'Portal Sharing'
```

| Field | Type | Description |
|-------|------|-------------|
| `res_model` | Char | Target model (from context `active_model`) |
| `res_id` | Integer | Target record ID (from context `active_id`) |
| `resource_ref` | Reference | Computed reference field for display |
| `partner_ids` | Many2many(`res.partner`) | Recipients to share with |
| `note` | Text | Optional message to include in the email |
| `share_link` | Char (computed) | The generated share URL |
| `access_warning` | Text (computed) | Access warning from the record |

#### `_send_public_link(partners)` — For partners with portal accounts (or `auth_signup.invitation_scope != 'b2c'`):
- Generates a share URL with `redirect=True`, `pid=partner.id`
- Sends via `message_post_with_source('portal.portal_share_template')`
- Subscribes the partner to the record

#### `_send_signup_link(partners)` — For partners without portal accounts:
- Triggers `signup_get_auth_param()` to generate signup tokens
- Sends a signup URL with embedded redirect to the record
- Used when `auth_signup.invitation_scope = 'b2c'` (public signup allowed)

#### `action_send_mail()` — Dispatches sharing:
```python
# If record has access token OR signup is not b2c → public link
# Otherwise → individual signup links for partners without users
self._send_public_link(partner_ids)
self._send_signup_link(self.partner_ids - partner_ids)
self.resource_ref.message_subscribe(partner_ids=self.partner_ids.ids)
```

---

## Controllers

### `portal/controllers/portal.py` — `CustomerPortal`

Main controller. Auth: `auth="user", website=True` (portal users are authenticated Odoo users).

#### Routes

| Route | Auth | Method | Description |
|-------|------|--------|-------------|
| `/my`, `/my/home` | user | `home()` | Portal home dashboard |
| `/my/counters` | user | `counters()` | JSON, returns badge counts (lazy-loaded) |
| `/my/account` | user | `account()` | Partner's own details form (GET/POST) |
| `/my/security` | user | `security()` | Password change (GET/POST) |
| `/my/deactivate_account` | user | `deactivate_account()` | Self-deactivation with password |
| `/portal/attachment/remove` | public | `attachment_remove()` | Remove pending attachments via JSON |

#### Account Update

`account()` POST handler:
- Validates required fields: `name`, `phone`, `email`, `street`, `city`, `country_id`
- Validates VAT if `check_vat` is available and partner can edit VAT
- Calls `on_account_update(values, partner)` hook (empty, for overriding)
- Writes to `partner.sudo()` (portal users cannot write to partner directly)

#### Mandatory vs Optional Fields

```python
def _get_mandatory_fields(self):
    return ["name", "phone", "email", "street", "city", "country_id"]

def _get_optional_fields(self):
    return ["street2", "zipcode", "state_id", "vat", "company_name"]
```

Override `_get_mandatory_fields()` in a custom module to add/remove required fields.

---

### `portal/controllers/web.py` — `Home` (extends `WebHome`)

Portal users who somehow reach `/`, `/web`, or `/web/webclient` are redirected to `/my` instead of the backend:

```python
class Home(WebHome):
    def index(self, *args, **kw):
        if request.session.uid and not is_user_internal(request.session.uid):
            return request.redirect_query('/my', query=request.params)
        return super().index(*args, **kw)

    def _login_redirect(self, uid, redirect=None):
        if not redirect and not is_user_internal(uid):
            redirect = '/my'
        return super()._login_redirect(uid, redirect=redirect)
```

Portal users never see the Odoo backend UI. `is_user_internal()` checks `not user.share`.

---

### `portal/controllers/mail.py` — `PortalChatter`

Provides portal-optimized chatter via JSON endpoints.

#### Routes

| Route | Auth | Method | Description |
|-------|------|--------|-------------|
| `/portal/chatter_init` | public | `portal_chatter_init()` | Initialize portal chatter store |
| `/mail/chatter_fetch` | public | `portal_message_fetch()` | Fetch messages for a thread |
| `/mail/update_is_internal` | user | `portal_message_update_is_internal()` | Toggle message internal flag |
| `/mail/avatar/...` | public | `portal_avatar()` | Serve avatar image with token auth |

**`portal_chatter_init()`**: Returns a `Store` with thread data, portal partner info, and access flags. Uses `get_portal_partner()` to resolve the partner from token/hash/pid.

**`portal_message_fetch()`**: Uses `website_message_ids` domain. Non-employees only see non-internal messages. Token-based access bypasses record rules via `sudo()`.

**`MailController._redirect_to_record()`**: When an email link is clicked for a portal-accessible model:
- Uses `force_website=True` to redirect to the portal view
- Injects `pid` and `hash` into the URL for chatter authentication

---

### `portal/controllers/thread.py` — `ThreadController`

Extends `mail.controllers.thread.ThreadController`:

```python
class ThreadController(thread.ThreadController):
    def _prepare_post_data(self, post_data, thread, **kwargs):
        post_data = super()._prepare_post_data(post_data, thread, **kwargs)
        if request.env.user._is_public():
            if partner := get_portal_partner(thread, kwargs.get("hash"), kwargs.get("pid"), kwargs.get("token")):
                post_data["author_id"] = partner.id
        return post_data

    def _is_message_editable(self, message, **kwargs):
        if message._is_editable_in_portal(**kwargs):
            return True
        return super()._is_message_editable(message, **kwargs)
```

Public (not-logged-in) portal users posting to a thread are identified by the HMAC hash or token, and their message is attributed to their partner.

---

### `portal/controllers/attachment.py` — `PortalAttachmentController`

Extends `mail.controllers.attachment.AttachmentController`:

```python
class PortalAttachmentController(AttachmentController):
    def _is_allowed_to_delete(self, message, **kwargs):
        if message._is_editable_in_portal(**kwargs):
            return True
        return super()._is_allowed_to_delete(message, **kwargs)
```

Allows portal users to delete attachments on messages they authored (identified by hash/pid), not just internal users.

---

### `portal/controllers/message_reaction.py` — `PortalMessageReactionController`

Extends `mail.controllers.message_reaction.MessageReactionController`:

```python
class PortalMessageReactionController(MessageReactionController):
    def _get_reaction_author(self, message, **kwargs):
        partner, guest = super()._get_reaction_author(message, **kwargs)
        if not partner and message.model and message.res_id:
            thread = request.env[message.model].browse(message.res_id)
            if partner := get_portal_partner(thread, kwargs.get("hash"), kwargs.get("pid"), kwargs.get("token")):
                guest = request.env["mail.guest"]
        return partner, guest
```

Portal users can react to messages on shared records, identified by hash/pid.

---

## Utility: `portal/utils.py`

```python
def validate_thread_with_hash_pid(thread, _hash, pid):
    if not _hash or not pid: return False
    pid = int(pid)
    if consteq(_hash, thread._sign_token(pid)): return True
    parent_sign_token = thread._portal_get_parent_hash_token(pid)
    return parent_sign_token and consteq(_hash, parent_sign_token)

def validate_thread_with_token(thread, token):
    return token and consteq(token, thread[thread._mail_post_token_field])

def get_portal_partner(thread, _hash, pid, token):
    if validate_thread_with_hash_pid(thread, _hash, pid):
        return thread.env["res.partner"].sudo().browse(int(pid))
    if validate_thread_with_token(thread, token):
        if partner := thread._mail_get_partners()[thread.id][:1]:
            return partner
    return thread.env["res.partner"]
```

**L4 — Three access modes**:

| Mode | Condition | Partner Resolution |
|------|-----------|-------------------|
| HMAC hash | `hash` + `pid` params match `_sign_token(pid)` | Direct partner browse |
| Access token | `token` param equals record's `access_token` | Via `_mail_get_partners()` |
| Neither | — | Returns empty partner |

---

## ACLs

| Record | Name | Model | Group | R | W | C | D |
|--------|------|-------|-------|---|---|---|---|
| `access_portal_share` | Portal Share | `model_portal_share` | `base.group_partner_manager` | 1 | 1 | 1 | 0 |
| `access_portal_wizard` | Portal Wizard | `model_portal_wizard` | `base.group_partner_manager` | 1 | 1 | 1 | 0 |
| `access_portal_wizard_user` | Portal Wizard User | `model_portal_wizard_user` | `base.group_partner_manager` | 1 | 1 | 1 | 0 |

Only partner managers (and above) can open the portal wizard or share wizard. Portal users themselves never see these wizards.

---

## L4: How Portal Access Control Works End-to-End

### Scenario: Customer views their Sales Order

```
1. SO is confirmed → sale.order inherits portal.mixin + mail.thread
2. Salesrep clicks "Share" → portal.share wizard opens
3. Backend user selects partner → action_send_mail() fires
   → If partner has user: _send_public_link()
     URL: /my/orders/123?access_token=abc&pid=42&hash=hmac
   → If no user + b2c signup: _send_signup_link()
     URL: /auth/signup?token=signup_token&redirect=/my/orders/123
4. Partner receives email → clicks link
5. Email link goes to /mail/view → MailController._redirect_to_record()
   → record._get_access_action(force_website=True)
   → Redirects to /my/orders/123?access_token=abc&pid=42&hash=hmac
6. CustomerPortal.home() renders /my/orders/123
   → sale_order.check_access('read') as portal user
     → Record rule: partner_id = user.partner_id → ALLOWED
   → Template uses access_token in URLs for PDF download
7. Customer posts a message:
   → /mail/chatter_fetch → portal_message_fetch()
   → /mail/post → ThreadController._prepare_post_data()
     → get_portal_partner(thread, hash, pid, token)
     → Validates hash → returns partner.id
     → Sets post_data["author_id"] = partner.id
   → Message created, attributed to customer partner
```

### Scenario: Portal user self-deactivates

```
1. /my/security → POST to /my/deactivate_account
2. Password verified
3. request.env.user._deactivate_portal_user(request_blacklist=True)
   → phone_validation.res_users._deactivate_portal_user() fires
     → Formats all phone numbers on partner
     → Adds to phone.blacklist if request_blacklist=True
   → super() archives the user, removes from portal group
4. Session logged out → redirect to /web/login?message=Account deleted
```

---

## Tags

`#odoo` `#odoo18` `#modules` `#portal` `#access.control` `#sharing` `#mail.thread` `#access_token`
