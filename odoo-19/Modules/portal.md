---
uid: portal
title: "Customer Portal"
description: Base controller, mixin, and wizard for customer portal access, document sharing, and portal user management
date: 2026-04-11
tags: [odoo, odoo19, portal, customer-access, document-sharing, portal-mixin, wizard]
model access: portal.mixin (abstract, no ACL), portal.wizard (base.group_partner_manager), portal.wizard.user (base.group_partner_manager), portal.share (base.group_partner_manager)
depends: web, html_editor, http_routing, mail, auth_signup
license: LGPL-3
---

# portal — Customer Portal

**Module:** `portal`
**Category:** Hidden
**Sequence:** 9000
**Depends:** `web`, `html_editor`, `http_routing`, `mail`, `auth_signup`
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

The `portal` module provides the foundational infrastructure for Odoo's customer-facing portal. It was refactored from `website_portal` (Odoo v10) to allow portal display without requiring the website editor. It does **not** depend on `website`, making it available in Odoo Online/Enterprise without full website functionality.

Key responsibilities:
1. **Portal Mixin** (`portal.mixin`) — grants any model an `access_url`, `access_token`, and share URL generation
2. **Portal User Management** — `portal.wizard` / `portal.wizard.user` for granting/revoking `base.group_portal` access
3. **Document Sharing** — `portal.share` wizard for emailing portal access links to partners
4. **Customer Address Management** — full billing/delivery address CRUD via `/my/address`
5. **Portal Chatter** — portal-aware message posting, reactions, and avatar fetching
6. **API Key Support** — allows portal users to generate API keys via `res.users.apikeys`

---

## Architecture

```
portal
├── models/
│   ├── portal_mixin.py       # Abstract mixin: access_url, access_token, share URL
│   ├── mail_thread.py        # Extends mail.thread: portal notify groups, _sign_token
│   ├── mail_message.py       # Portal message format, attachment token handling
│   ├── res_partner.py        # Frontend-writable fields, delivery address domain
│   ├── res_config_settings.py  # portal.allow_api_keys config parameter
│   ├── ir_http.py            # Adds portal to frontend translation modules
│   ├── ir_ui_view.py         # customize_show flag for portal-specific view inherits
│   ├── ir_qweb.py            # Portal-specific template rendering (is_html_empty, languages)
│   └── res_users_apikeys_description.py  # Portal users can generate API keys
├── controllers/
│   ├── portal.py             # CustomerPortal controller: /my/* routes, address forms
│   ├── mail.py               # Overrides MailController: redirect to portal fallback
│   ├── portal_thread.py      # Portal-aware message posting and editing
│   ├── thread.py             # Portal chatter init/fetch routes
│   ├── message_reaction.py   # Portal-aware reaction authorship
│   └── web.py                # Home redirect for portal users: /my
├── wizard/
│   ├── portal_wizard.py       # Grant/revoke portal access, create users, send invites
│   └── portal_share.py        # Email share links to partners (signup vs. public link)
├── utils.py                  # validate_thread_with_hash_pid, validate_thread_with_token, get_portal_partner
├── data/mail_templates.xml   # portal_share_template (invitation email)
└── security/ir.model.access.csv  # ACL for portal.share, portal.wizard, portal.wizard.user
```

---

## L1: How Portal Access Works — Core Concepts

### The Portal Access Model

Portal access in Odoo 19 operates on a **token-based, cookie-free authentication** model for shared links. The system allows unauthenticated (public) users to access specific records through time-limited, cryptographically secured URLs.

The access flow works as follows:

```
1. Backend user clicks "Share" on a sale order
   ↓
2. Backend calls record._get_share_url() → generates URL with access_token
   ↓
3. URL emailed to customer: /my/orders/123?access_token=uuid-v4-string
   ↓
4. Customer visits URL → MailController._redirect_to_record() validates token
   ↓
5. If token valid → record._get_access_action() redirects to /my/orders/123
   ↓
6. Chatter on the portal page allows message posting via portal token auth
```

### `portal.mixin` — The Foundation

`portal.mixin` is an `AbstractModel` — it has no database table of its own. Any concrete model that inherits from it gains three fields and a suite of methods without changing its own table structure.

```python
class PortalMixin(models.AbstractModel):
    _name = 'portal.mixin'
    _description = 'Portal Mixin'
```

The mixin is **not** a `models.Mixin` in the Python multiple-inheritance sense — it is a standalone abstract class. Models extend it via `_inherit = ['sale.order', 'portal.mixin']` (Python's prototype inheritance).

**File:** `~/odoo/odoo19/odoo/addons/portal/models/portal_mixin.py`

#### Fields

| Field | Type | Default | Storage | Description |
|---|---|---|---|---|
| `access_url` | `Char` | computed `'#'` | Stored (compute) | Customer portal URL for this record. Override `_compute_access_url()` in extending models. |
| `access_token` | `Char` | `False` | Stored | UUID-v4 security token for unauthenticated access via shared links. `copy=False` — never copied on record duplicate. Generated lazily on first share. |
| `access_warning` | `Text` | `''` | Computed | Warning displayed when the partner has restricted access. Empty by default; override `_compute_access_warning()` for custom logic. |

### `access_token` Deep Dive

The `access_token` is the core security primitive of portal sharing. It is:

1. **Lazy-generated**: Not created on record creation — only when `_portal_ensure_token()` is called (typically when a share URL is first requested).
2. **UUIDv4**: Uses Python's `uuid.uuid4()` — cryptographically random, 122 bits of entropy. Not a sequential ID or predictable hash.
3. **Written via `sudo()`**: The write bypasses access rights because the share URL is generated by a backend user (who has rights), not the portal user.
4. **Cache-invalidated**: The method does `self.sudo().write({'access_token': str(uuid.uuid4())})` followed by returning the new token. Without the `write`, the ORM cache would return the old value (`False`) on subsequent reads in the same transaction.
5. **`copy=False`**: Copying a record (e.g., duplicate SO) does NOT copy the token. The new record gets a new token when first shared.

```python
def _portal_ensure_token(self):
    if not self.access_token:
        self.sudo().write({'access_token': str(uuid.uuid4())})
    return self.access_token
```

### Res.users Extensions for Portal

**File:** `~/odoo/odoo19/odoo/addons/portal/models/res_users_apikeys_description.py`

Portal users get a specialized API key flow. The `check_access_make_key()` override:
- Tries the parent method first (which allows internal users by default).
- On `AccessError`, checks `portal.allow_api_keys` config parameter.
- If `True` and user is portal (`_is_portal()`), allows silently.
- If `True` but user is internal, raises: `"Only internal and portal users can create API keys"`.
- If `False`, re-raises the original `AccessError`.

This allows B2B portal customers to integrate Odoo data via the API without sharing login credentials.

---

## L2: Field Types, Defaults, Constraints

### Field Type Analysis

#### `access_token` — Char Field

```python
access_token = fields.Char('Security Token', copy=False)
```

- **Type**: `Char` (VARCHAR in PostgreSQL)
- **`copy=False`**: Explicitly prevents copying the token when the record is duplicated. Each record must have its own token.
- **No constraint**: No `required=True` — the field is empty until first share. This is intentional: generating tokens for all records wastes storage and creates security surface.
- **Index**: Not indexed — tokens are looked up by equality, not range queries.
- **Security note**: UUIDv4 is resistant to enumeration attacks but not brute-force. Tokens should be treated as secrets — never log them, never include in URL path (only query string), always use HTTPS.

#### `access_url` — Computed Char

```python
access_url = fields.Char(
    'Portal Access URL', compute='_compute_access_url',
)
```

- **Type**: `Char`, computed, NOT stored by default.
- **`_compute_access_url()`**: Default implementation returns `'#'` for all records. Each extending module must override this.
- **Performance note**: Because it is computed (not stored), every read of `access_url` triggers the compute method. For list views showing many records, this can cause N computes. Extending models should consider `store=True` if the portal URL is accessed frequently.

#### `access_warning` — Computed Text

```python
access_warning = fields.Text("Access warning", compute="_compute_access_warning")
```

- **Type**: `Text`, computed.
- **Default**: Returns `''` for all records in the base implementation.
- **Override pattern**: Modules like `sale_portal` override this to show warnings about draft state, zero totals, or other conditions.

### Wizard Field Constraints

#### `portal.wizard.user.email_state` — Selection

```python
email_state = fields.Selection([
    ('ok', 'Valid'),
    ('ko', 'Invalid'),
    ('exist', 'Already Registered')],
    string='Status', compute='_compute_email_state', default='ok')
```

Computed selection field with three mutually exclusive states:
- **`'ok'`**: Email is valid format AND not already registered to another user.
- **`'ko'`**: Email fails `email_normalize()` — bad format.
- **`'exist'`**: Email is valid but belongs to a different existing user (`login` matches, user ID differs).

The `_compute_email_state()` method uses `sudo()` to search `res.users` because the wizard operator may not have read access to all user records.

---

## L3: Cross-Module Integration, Override Patterns, Workflow Triggers

### Cross-Module: Portal-Enabled Models

Any model can become portal-enabled by inheriting `portal.mixin`. The following Odoo modules extend this:

| Module | Model | Portal URL | Notes |
|---|---|---|---|
| `sale` | `sale.order` | `/my/orders/<id>` | Via `sale_portal` module |
| `sale` | `sale.order.line` | Inherited via order | Parent-delegated sharing |
| `purchase` | `purchase.order` | `/my/purchases/<id>` | Via `purchase_portal` |
| `stock` | `stock.picking` | `/my/picking/<id>` | Via `stock_portal` |
| `account` | `account.move` | `/my/invoices/<id>` | Via `account_portal` |
| `project` | `project.task` | `/my/tasks/<id>` | Via `project_portal` |
| `helpdesk` | `helpdesk.ticket` | `/my/tickets/<id>` | Via `helpdesk_portal` |

The pattern in each case:
```python
class SaleOrder(models.Model):
    _inherit = ['sale.order', 'portal.mixin']

    def _compute_access_url(self):
        for order in self:
            order.access_url = f'/my/orders/{order.id}'
```

### Override Patterns

#### Pattern 1: Custom Portal URL

```python
# In extending module
class MyDocument(models.Model):
    _inherit = ['my.document', 'portal.mixin']

    def _compute_access_url(self):
        for doc in self:
            doc.access_url = f'/my/documents/{doc.id}'
```

#### Pattern 2: Custom Access Warning

```python
def _compute_access_warning(self):
    for doc in self:
        if doc.state == 'draft':
            doc.access_warning = _('This document has not been approved yet.')
        elif not doc.partner_id:
            doc.access_warning = _('No customer is linked to this document.')
        else:
            doc.access_warning = ''
```

#### Pattern 3: Parent-Delegated Sharing (Order Lines)

```python
# Allows sharing a sale.order.line using the parent order's token
class SaleOrderLine(models.Model):
    _inherit = ['sale.order.line', 'portal.mixin']

    def _portal_get_parent_hash_token(self, pid):
        return self.order_id._sign_token(pid)
```

#### Pattern 4: Custom Share URL Parameters

```python
def _get_share_url(self, redirect=False, signup_partner=False, pid=None, share_token=True):
    url = super()._get_share_url(redirect, signup_partner, pid, share_token)
    return f"{url}&signature={self._generate_custom_param()}"
```

### Workflow Trigger: Portal Invitation

The full invitation workflow triggered from `portal.share` wizard:

```
1. User clicks "Share" on a sale order
   → portal.wizard opened via action_share()
   ↓
2. User selects partners, adds note, clicks "Send"
   → portal_share.action_send_mail()
   ↓
3. For partners WITH user accounts:
   → _send_public_link(): generates URL with access_token + pid + hash
   → message_post_with_source('portal.portal_share_template')
   ↓
4. For partners WITHOUT user accounts:
   → _send_signup_link(): generates signup URL
   → message_post_with_source() with signup URL
   ↓
5. Email delivered via mail template
   → Customer clicks link in email
   ↓
6. MailController._redirect_to_record() validates access_token
   → Redirects to /my/orders/<id>?access_token=...
   ↓
7. Customer views portal page (read access via portal group)
   → Can post messages via portal_thread controller
```

### Workflow Trigger: Access Token Generation

```
1. Backend user requests share URL (no token exists yet)
   ↓
2. record._get_share_url()
   → record._portal_ensure_token()
   → self.sudo().write({'access_token': uuid.uuid4()})
   → DB write, cache invalidation
   → Returns token
   ↓
3. Token embedded in URL: /my/orders/123?access_token=abc...
   → Emailed to customer
   ↓
4. Customer visits URL
   → MailController._redirect_to_record()
   → consteq(access_token, record.access_token)
   → if match: _get_access_action(force_website=True)
   → Redirects to portal page
   ↓
5. Portal page loads
   → Chatter initialized via /portal/chatter_init
   → _get_thread_with_access() validates token for message posting
```

### Failure Modes

| Failure Mode | Cause | Behavior |
|---|---|---|
| Token mismatch | Token in URL doesn't match record | `AccessError` → falls back to parent `_get_access_action` (backend form) |
| Partner mismatch | `pid` + `hash` don't match | `validate_thread_with_hash_pid()` returns `False` → no chatter auth |
| Expired signup | Partner signup token expired (7 days) | User must request new invitation |
| Archived portal user | User account set `active=False` | Cannot log in, must re-grant access via wizard |
| Missing `partner_id` | Record has no `partner_id` field | `_send_signup_link()` silently skips; `_send_public_link()` still works |
| Non-portal model | `isinstance(res_model, portal.mixin)` returns False | `share_link` stays `False`, wizard shows no link |

---

## L4: Performance, Security, Share Mechanism, Odoo 18->19 Changes

### Performance Analysis

#### 1. `access_url` Compute on Bulk Loads

When the portal page or list view loads many records, each record triggers `_compute_access_url()`. The default implementation returns `'#'`, which is negligible. However, extending modules that compute complex URLs (with company lookups, translations, or multi-company URLs) will see cumulative compute time.

**Mitigation**: Use `store=True` on the compute and narrow `@api.depends`:
```python
@api.depends('name', 'company_id')
def _compute_access_url(self):
    for order in self:
        order.access_url = f'/my/orders/{order.id}'
```

#### 2. `_portal_ensure_token()` Cold-Start Write

On first access to a share URL (for a record that hasn't been shared yet), a database `write()` is executed. This is a synchronous write, meaning the first visitor to each shared link triggers one additional SQL query. For bulk sharing (portal.share wizard with many partners), this is triggered once per unique record, not once per partner.

#### 3. `website_message_ids` Lambda Domain

```python
website_message_ids = fields.One2many(
    'mail.message', 'res_id',
    domain=lambda self: [
        ('model', '=', self._name),
        ('message_type', 'in', ('comment', 'email', 'email_outgoing', 'auto_comment', 'out_of_office'))
    ],
    bypass_search_access=True,
)
```

The lambda domain is evaluated in Python on every record load. For recordsets with thousands of records in memory, this adds per-record overhead. The `bypass_search_access=True` prevents access errors but does not eliminate the domain evaluation cost.

#### 4. `portal_message_format()` Attachment Reads

```python
attachments_sudo = self.sudo().attachment_ids
```

Attachments are read via `sudo()` in a separate query. For threads with many messages and many attachments, this creates N+1 query patterns. The attachments are read in one query (`read()` on all attachment IDs), but the message-to-attachment mapping loop (`message_to_attachments`) still processes them per-message in Python.

#### 5. Share Email Batching

```python
def _send_public_link(self, partners=None):
    for partner in partners:
        share_link = ...
        self.resource_ref.message_post_with_source(...)  # One DB transaction + email per partner
```

Both `_send_public_link()` and `_send_signup_link()` loop over partners, calling `message_post_with_source()` and email delivery per iteration. For large partner lists (50+), consider overriding to batch or queue.

#### 6. `_validate_address_values()` — VIES SOAP Call

When `account` module is installed, VAT validation calls the EU VIES SOAP service:
```python
if hasattr(ResPartnerSudo, '_check_vat'):
    partner_vat_check = Partner.with_user(SUPERUSER_ID).create({'_check_vat': (country_code, vat)})
```
This is a synchronous network call (3-5 seconds timeout). The `hasattr` guard prevents the call if the account module is not installed.

### Security Analysis

#### Token Security Properties

| Property | Implementation | Risk |
|---|---|---|
| Unpredictability | `uuid.uuid4()` — 122-bit cryptographically random | Very low brute-force risk |
| Timing safety | `consteq()` for all token comparisons | Prevents timing attacks |
| Token scope | Per-record, not per-user | A token grants access to one specific record |
| Token lifecycle | Persistent (no expiry built-in) | Token valid until record deleted or token regenerated |
| HMAC signing | `hmac.new(secret, repr((dbname, token, pid)), sha256)` | One-way, requires `database.secret` |
| Database secret | Server-side only, not exposed | Cannot be recovered from client-side code |

**Token Expiry**: The `access_token` does not expire by default. For short-lived shares, implement a custom expiry mechanism:
```python
def _get_share_url(self, ...):
    url = super()._get_share_url(...)
    if self.share_expiry_date:
        url += f"&expires={self.share_expiry_date}"
    return url
```

#### ACL Isolation

```
portal.share        → base.group_partner_manager only
portal.wizard       → base.group_partner_manager only
portal.wizard.user  → base.group_partner_manager only
portal.mixin        → No ACL (abstract model)
```

The `portal.mixin` itself has no ACL because it is an abstract model — it contributes fields to concrete models. The concrete models must define their own `ir.rule` records to scope portal access.

#### Portal User Isolation Guarantees

1. **Backend access blocked**: `Home.index()`, `web_client()`, and `_login_redirect()` all check `is_user_internal()`. Non-internal users (including portal) are redirected to `/my`.

2. **Record access via `ir.rule`**: Portal users typically have `ir.rule` records that scope reads to `['|', ('partner_id', '=', user.partner_id.id), ('partner_id', 'child_of', user.commercial_partner_id.id)]`. This ensures portal users only see their own records.

3. **Commercial field protection**: The address form's `_parse_form_data()` only accepts fields in `_get_frontend_writable_fields()`. Commercial fields (`name`, `email`, `vat`) on child addresses are silently excluded from `address_values` before write.

4. **VAT edit restriction**: `can_edit_vat()` returns `False` for child contacts. The `_validate_address_values()` method raises `UserError` if VAT is submitted for a non-commercial partner.

5. **Internal notes hidden**: `is_internal` flag on `mail.message` is respected in `_get_non_empty_message_domain()`, preventing internal discussions from appearing on the portal.

### Share Mechanism — Complete Flow

```
SHARING SIDE (Backend User):
  portal.share wizard (opened via action_share on any portal.mixin record)
       ↓
  action_send_mail():
       ├─ partners with users OR record has access_token
       │    → _send_public_link(): URL = access_url?access_token=...&pid=...&hash=...
       │    → message_post_with_source('portal.portal_share_template')
       │    → Email with "View Document" button (links to /mail/view?model=...&res_id=...&access_token=...)
       │
       └─ partners without users (and signup enabled)
            → _send_signup_link(): URL = /web/auth/signup?signup_token=...&redirect=/my/orders/...
            → message_post_with_source('portal.portal_share_template')
            → Email with "Accept Invitation" button

RECEIVING SIDE (Customer):
  Customer clicks link in email
       ↓
  MailController._redirect_to_record():
       ├─ If no session (public user): switches to base.public_user
       ├─ Checks: access_token matches record.access_token (consteq)
       ├─ If match: _get_access_action(force_website=True)
       │    → Returns ir.actions.act_url to record.access_url
       │    → Redirects to /my/orders/<id>?access_token=...
       ├─ If pid + hash: appends to URL for chatter auth
       │
       └─ If token invalid: falls back to generic _redirect_to_generic_fallback()

PORTAL PAGE LOAD:
  /my/orders/<id>?access_token=...
       ↓
  portal_page_loads_with_token_in_query()
       ↓
  Chatter init (/portal/chatter_init):
       ├─ portal_thread_fetch() domain: model=..., res_id=..., subtype_id=mail.mt_comment
       ├─ get_portal_partner() validates hash+pid OR token
       └─ Returns portal_formatted messages

MESSAGE POSTING (from portal page):
  Customer types message → POST /mail/message/post
       ↓
  PortalThreadController._prepare_message_data():
       ├─ If public user: overrides author_id to portal_partner
       └─ If registered user: standard auth
```

### Odoo 18 → 19 Changes

| Feature | Odoo 18 | Odoo 19 | Impact |
|---|---|---|---|
| **Portal chatter** | Server-rendered templates (QWeb) | Full JavaScript `Store`-powered frontend component | Chatter loads faster; supports reactions, real-time |
| **`website_message_ids`** | Defined on specific models | Added to `mail.thread` level via portal override | Available on all thread-enabled models |
| **`portal.assets_chatter` bundle** | Not present | New asset bundle for JS/SCSS | Chatter frontend assets modularized |
| **`ir.qweb._prepare_frontend_environment()`** | Not present | Added in Odoo 19 | `is_html_empty` and `frontend_languages` available in portal templates |
| **API keys for portal users** | Not supported | `portal.allow_api_keys` + `res.users.apikeys.description` override | Portal customers can use API integration |
| **Portal message reactions** | Not supported | `PortalMessageReactionController` added | Portal users can react to messages |
| **`_portal_get_parent_hash_token()`** | Not present | New hook | Enables hierarchical portal sharing (e.g., sharing a line via the order's token) |
| **`customize_show` on `ir.ui.view`** | Existed | More fully utilized for portal-specific view inherits | Portal views can be hidden/shown via website builder |
| **Home redirect** | Basic | `Home.index()`, `web_client()`, `_login_redirect()` all redirect non-internal to `/my` | Cleaner separation between portal and backend users |

---

## Models

### `portal.mixin` — Abstract Model

Inherits from nothing. Mixed into models like `sale.order`, `purchase.order`, `stock.picking` to add portal capabilities.

**File:** `~/odoo/odoo19/odoo/addons/portal/models/portal_mixin.py`

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `access_url` | `Char` | computed `'#'` | Customer portal URL for this record. Override `_compute_access_url()` in extending models. Base implementation returns `'#'`. |
| `access_token` | `Char` | `False` | Security token for unauthenticated access via shared links. `copy=False` — never copied on record duplicate. |
| `access_warning` | `Text` | `''` (computed) | Warning displayed when the partner has restricted access to this record. Override `_compute_access_warning()` for custom logic. |

#### Methods

**`def _compute_access_warning(self)`**
> Sets `access_warning = ''` by default. Override in extending models to provide record-specific warnings (e.g., `"This quote has not been confirmed yet."`).

**`def _compute_access_url(self)`**
> Computed Char. Default returns `'#'` for all records. Extending modules override this to return the actual portal route (e.g., `/my/orders/<id>`).

**`def _portal_ensure_token(self) -> str`**
> Lazily generates a `access_token` using `uuid.uuid4()`. The token is written via `sudo()` to bypass access restrictions. The `write` is required to clear the Odoo cache before returning — without it, `return self.access_token` would return `False` in the same transaction.
>
> Returns: the `access_token` string.
> Side effect: writes to `access_token` via `sudo()` on first call.

**`def _get_share_url(self, redirect=False, signup_partner=False, pid=None, share_token=True) -> str`**
> Builds the portal share URL with authentication parameters. Parameter logic:
>
> | Parameter | Type | Description |
> |---|---|---|
> | `redirect` | `bool` | If `True`, wraps URL in `/mail/view` (used in emails to allow access checks before showing the record). If `False`, returns direct `access_url`. |
> | `signup_partner` | `bool` | If `True` and `partner_id` exists on the record, adds signup auth params (`signup_token`, `signup_validity`) via `partner_id.signup_get_auth_param()`. |
> | `pid` | `int` | Partner ID — adds `pid` and `hash` parameters for chatter authentication on redirect. The hash is `_sign_token(pid)`. |
> | `share_token` | `bool` | If `False`, omits the `access_token` param entirely. Defaults `True`. |
>
> Logic flow:
> 1. If `redirect=True`, params include `model` and `res_id` for the mail/view controller to check access.
> 2. If `share_token=True` and model has `access_token` field, calls `check_access('read')` then adds `access_token`.
> 3. If `pid` is provided, adds `pid` and `hash = _sign_token(pid)` for secure chatter auth.
> 4. If `signup_partner=True` and `partner_id` exists, merges `signup_get_auth_param()` output into params.
> 5. Returns `'%s?%s' % (url, url_encode(params))`.

**`def _get_access_action(self, access_uid=None, force_website=False) -> dict`**
> Overrides the backend "View" button to redirect portal users to the web portal instead of the backend form view.
>
> Logic:
> - If `access_uid` is provided, switches to that user's context and checks read access.
> - If current user is a `share` user (portal) **or** `force_website=True`:
>   - Attempts read access; if denied and `force_website=True`, returns `{'type': 'ir.actions.act_url', 'url': record.access_url, ...}`.
>   - If access granted, returns a URL to `_get_share_url()`.
> - Otherwise falls back to the parent class's `_get_access_action` (backend form).
>
> This is the mechanism by which the "View" button in the backend for a Sale Order opens the portal page for portal users.

**`def get_portal_url(self, suffix=None, report_type=None, download=None, query_string=None, anchor=None) -> str`**
> Convenience wrapper that appends `access_token`, `report_type`, `download`, `query_string`, and `anchor` as query string parameters to `access_url`. Designed for report download links (PDF, HTML) from the portal.

**`@api.model def action_share(self)`**
> Server action entry point. Opens the `portal.share` wizard in the context of the current model/res_id by reading `active_model` and `active_id` from the action context.

---

### `portal.wizard` — Grant Portal Access

TransientModel. Manages the complete portal invitation workflow from the backend.

**File:** `~/odoo/odoo19/odoo/addons/portal/wizard/portal_wizard.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `partner_ids` | `Many2many res.partner` | Partners selected for portal access. Default from context `default_partner_ids` or `active_ids`. On load, expands each partner to include their contact-type children. |
| `user_ids` | `One2many portal.wizard.user` | Computed from `partner_ids` — one line per partner with `partner_id` and `email` pre-populated. |
| `welcome_message` | `Text` | Custom invitation message included in the email sent to new portal users. Rendered in `auth_signup.portal_set_password_email`. |

**`_default_partner_ids()`** — gets partner IDs from context (`default_partner_ids` or `active_ids`); expands each partner to include contact children (`type in ('contact', 'other')`) to ensure all relevant contacts are included.

**`_compute_user_ids()`** — for each partner in `partner_ids`, creates a `portal.wizard.user` line with `partner_id` and `email` pre-filled from the partner record.

**`action_open_wizard()`** — factory method that creates the wizard record then calls `_action_open_modal()`. The server action pattern is required because one2many `user_ids` records need IDs before button actions can fire on them — without a server action, the buttons would be disabled on new wizard records.

---

### `portal.wizard.user` — Portal User Configuration Line

TransientModel. One record per partner in the wizard. This is the line where access is granted/revoked per contact.

#### Fields

| Field | Type | Description |
|---|---|---|
| `wizard_id` | `Many2one portal.wizard` | Parent wizard, required, `ondelete='cascade'`. |
| `partner_id` | `Many2one res.partner` | Partner record. Required, readonly. |
| `email` | `Char` | Editable email for the portal user account. Normalized on write. |
| `user_id` | `Many2one res.users` | Computed from `partner_id.user_ids` (with `active_test=False`). Returns first user or `False`. |
| `login_date` | `Datetime` | Related to `user_id.login_date`. Shows last authentication time. |
| `is_portal` | `Boolean` | Computed: `True` if `user_id._is_portal()` (member of `base.group_portal`). |
| `is_internal` | `Boolean` | Computed: `True` if `user_id._is_internal()` (has internal-level access). |
| `email_state` | `Selection` | `'ok'` (valid), `'ko'` (invalid format), `'exist'` (already registered). Computed from normalized `email` against `res.users`. |

**`_compute_email_state()`** logic:
1. Normalizes email via `email_normalize()`.
2. Records that fail normalization → `email_state = 'ko'`.
3. For valid emails: searches `res.users` (with `active_test=False`.sudo()) for matching login. If found with a different user ID → `'exist'`. Otherwise → `'ok'`.

#### Action Methods

**`action_grant_access()`** — grants portal access to the partner:
1. Calls `_assert_user_email_uniqueness()` — raises `UserError` if email is invalid or duplicate.
2. Rejects if partner already has portal or internal access.
3. If no `user_id` exists: creates a new user via `_create_user()` with normalized email as both login and email, in the current company.
4. Writes `active=True` and updates group assignments: adds `group_portal`, removes `group_public`.
5. Calls `partner_id.signup_prepare()` to generate a signup token valid for 7 days.
6. Sends invitation email via `_send_email()` with `force_send=True`.
7. Refreshes the modal via `_action_open_modal()`.

**`action_revoke_access()`** — removes portal access:
1. Rejects if partner is not a portal user.
2. Updates groups: removes `group_portal`, adds `group_public`.
3. Sets `active=False` on the user (archives rather than deletes).
4. Clears `signup_type` on the partner to invalidate any pending signup tokens.
5. Refreshes the modal.

**`action_invite_again()`** — re-sends the invitation email:
1. Validates email uniqueness.
2. Rejects if partner is not already a portal user.
3. Re-sends the invitation email.
4. Refreshes the modal.

**`_create_user()`** — calls `res.users._create_user_from_template()` with normalized email/login. Uses `no_reset_password=True` context to prevent Odoo's standard password reset email from conflicting with the portal invitation flow.

**`_send_email()`** — uses the `auth_signup.portal_set_password_email` template. Renders with `lang` from the user, `welcome_message` from the wizard, `dbname`, `medium='portalinvite'`. Uses `force_send=True` for synchronous delivery so the server action completes after the email is sent.

**`_assert_user_email_uniqueness()`** — raises `UserError` if `email_state` is `'ko'` (invalid format) or `'exist'` (login already taken by a different user).

**`_update_partner_email()`** — writes normalized email to the partner if `email_state == 'ok'` and the normalized email differs from the current partner email.

---

### `portal.share` — Document Sharing Wizard

TransientModel. Allows emailing share links for any `portal.mixin` record to selected partners.

**File:** `~/odoo/odoo19/odoo/addons/portal/wizard/portal_share.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `res_model` | `Char` (required) | Model name of the record being shared. Populated from context `active_model`. |
| `res_id` | `Integer` (required) | Record ID being shared. Populated from context `active_id`. |
| `resource_ref` | `Reference` | Computed Reference field dynamically linking to the actual record using `'_selection_target_model'` selection method. |
| `partner_ids` | `Many2many res.partner` (required) | Recipients of the sharing email. |
| `note` | `Text` | Extra content appended to the invitation email body (rendered as `white-space: pre-wrap`). |
| `share_link` | `Char` | Computed full URL: `record.get_base_url() + record._get_share_url(redirect=True)`. |
| `access_warning` | `Text` | Mirrors `record.access_warning` for display in the wizard dialog. |

**`_compute_share_link()`** — only computes if `res_model` is a `portal.mixin` instance via `isinstance(res_model, self.pool['portal.mixin'])`. Leaves `share_link` as `False` for non-portal models.

#### Sending Methods

**`action_send_mail()`** — main action:
1. Reads `auth_signup.invitation_scope` config parameter. If `'b2c'`, signup is enabled.
2. Splits partners based on two conditions:
   - Partners **with existing users** (has `user_ids`) **or** records **with `access_token`**: send via `_send_public_link()`.
   - Partners **without users** (no `user_ids`) and signup enabled: send via `_send_signup_link()`.
3. If signup is not enabled (not `b2c`), all partners receive the public link.

**`_send_public_link(partners)`** — for partners with user accounts or when the record has an `access_token`:
- Generates share URL with `pid=partner.id` (adds `hash` for chatter auth).
- Iterates partners, switching `lang` context per partner.
- Posts message via `resource_ref.message_post_with_source('portal.portal_share_template', ...)` with `subtype_xmlid='mail.mt_note'` (internal note, not an email).

**`_send_signup_link(partners)`** — for partners without existing user accounts:
- Filters to partners without `user_ids`.
- Calls `partner.signup_get_auth_param()` and `partner._get_signup_url_for_action(action='/mail/view', ...)` to generate per-partner signup URLs.
- Posts the same `portal.portal_share_template` with the individual signup URL.

---

### `mail.thread` Extensions

**File:** `~/odoo/odoo19/odoo/addons/portal/models/mail_thread.py`

#### Class Attribute

**`_mail_post_token_field = 'access_token'`**
> Overrides the parent class attribute. Tells the mail thread which field to use as the token for external posting/authentication. Any model with `portal.mixin` has this field.

#### Fields

**`website_message_ids`** — `One2many('mail.message', 'res_id')`:
- Domain: `[('model', '=', self._name), ('message_type', 'in', ('comment', 'email', 'email_outgoing', 'auto_comment', 'out_of_office'))]`
- `bypass_search_access=True` — allows portal users to search within this relation without triggering access rights errors on non-visible messages.
- Used by portal chatter to display only website-relevant communication history.

#### Methods

**`_notify_get_recipients_groups()`** — override:
> When the model implements `portal.mixin`, injects a `portal_customer` notification group with a direct portal URL button. The group is only added when a customer partner is found in `_mail_get_partners()`. The portal notification group includes `access_token`, `pid`, `hash`, and signup auth params so the customer can access the portal directly from the email. Activates the generic `portal` group with `has_button_access = True`.

**`_sign_token(pid) -> str`** — HMAC-SHA256 signature:
> ```python
> secret = self.env["ir.config_parameter"].sudo().get_param("database.secret")
> token = (self.env.cr.dbname, self[self._mail_post_token_field], pid)
> return hmac.new(secret.encode('utf-8'), repr(token).encode('utf-8'), hashlib.sha256).hexdigest()
> ```
> Signs `(dbname, access_token, pid)` using `database.secret`. The `repr()` call serializes the tuple. Used to verify that the portal user opening the link is the intended recipient. Raises `NotImplementedError` if the model lacks the token field.

**`_portal_get_parent_hash_token(pid) -> str | False`** — hook for hierarchical sharing:
> Overridden in models with a parent field (e.g., sale order line sharing via the parent order's signature). Returns `False` by default. When overridden, returns the parent's `_sign_token(pid)` result, allowing a child record to be shared using the parent's signature.

**`_get_thread_with_access(thread_id, hash=None, pid=None, token=None)`** — override:
> Falls back to portal-style validation if the parent method finds no access:
> 1. First calls the parent's `_get_thread_with_access()` — standard auth, session, read rule checks.
> 2. If that returns a thread, returns it immediately.
> 3. If not, tries portal validation: `validate_thread_with_hash_pid()` (HMAC signature) then `validate_thread_with_token()` (access token).
> 4. If either succeeds, returns a `sudo()`-ed thread record.
> 5. Otherwise returns an empty browse record.

**`_get_allowed_access_params()`** — override:
> Adds `{'hash', 'pid', 'token'}` to the parent's allowed params set. These parameters are permitted to be passed via the request to authenticate portal users.

---

### `mail.message` Extensions

**File:** `~/odoo/odoo19/odoo/addons/portal/models/mail_message.py`

#### `_compute_is_current_user_or_guest_author()` Override

Extends the parent method. For portal threads, additionally sets `is_current_user_or_guest_author = True` when `portal_partner` from context equals the message's `author_id` and the message belongs to the portal thread. This grants the portal user edit/delete rights on their own messages.

The portal `portal_data` context is set by `portal_message_fetch()`: `{"portal_partner": portal_partner, "portal_thread": thread}`.

#### `portal_message_format(options=None) -> list[dict]` — Public API

Entry point for portal frontend message formatting. Calls `check_access('read')` first, then delegates to `_portal_message_format()` with default portal properties.

#### `_portal_get_default_format_properties_names(options=None) -> set`

Returns the set of fields/properties included in portal message formatting:
```python
{'attachment_ids', 'author_avatar_url', 'author_id', 'author_guest_id', 'body',
 'date', 'id', 'is_internal', 'is_message_subtype_note', 'message_type',
 'model', 'published_date_str', 'res_id', 'starred', 'subtype_id'}
```

#### `_portal_message_format(properties_names, options=None) -> list[dict]` — Private

Core formatting logic. Key behaviors:

1. **Attachments**: If `attachment_ids` in properties, reads via `sudo()` and maps to messages. Safari-specific mimetype conversion for video attachments (`application/octet-stream`). Each attachment gets `raw_access_token` from `_get_raw_access_token()`. If the user is the message author (`is_current_user_or_guest_author`), also adds `ownership_token` for delete capability.

2. **Body**: Wrapped in `["markup", values["body"]]` — marks the HTML as safe for the frontend HTML renderer.

3. **Author avatar URL**: Depends on URL params in `options`:
   - With `token`: `/mail/avatar/mail.message/<id>/author_avatar/50x50?access_token=<token>`
   - With `hash` + `pid`: `/mail/avatar/mail.message/<id>/author_avatar/50x50?_hash=<hash>&pid=<pid>`
   - Otherwise: `/web/image/mail.message/<id>/author_avatar/50x50`

4. **Reactions**: Groups `mail.message.reaction` records by content using `itertools.groupby`. Computes counts and lists guest/partner participants.

5. **`is_message_subtype_note`**: Resolves `mail.mt_note` XMLID and compares `subtype_id[0]`.

6. **`published_date_str`**: Formatted via `format_datetime()` using the env's locale and timezone.

---

### `res.partner` Extensions

**File:** `~/odoo/odoo19/odoo/addons/portal/models/res_partner.py`

#### `_get_frontend_writable_fields() -> set`

Returns the set of fields portal users can edit on their own contact/address records:
```python
{'name', 'phone', 'email', 'street', 'street2', 'city', 'state_id',
 'country_id', 'zip', 'zipcode', 'vat', 'company_name'}
```
Note: `zipcode` is an alias for `zip` used in the address form — both map to the same `zip` field.

#### `_can_edit_country() -> bool`

Always returns `True`. Country changes are blocked at the validation layer (`_validate_address_values`) if documents have been issued, not here.

#### `can_edit_vat() -> bool`

Returns `True` only when `parent_id` is falsy (partner is the commercial entity). Child contacts inherit VAT from their commercial parent and cannot edit it directly.

#### `_can_be_edited_by_current_customer(**kwargs) -> bool`

Returns `True` if:
- The partner is the current user's partner (`self == current_partner`).
- OR the partner is a child address (type `invoice`, `delivery`, or `other`) of the current user's commercial partner.

Used by the portal address form to gate edit/create access. The commercial partner check uses `id child_of commercial_partner_id.id` to include all descendants.

#### `_get_current_partner(**kwargs) -> res.partner`

Returns `request.env.user.partner_id` for logged-in users, or an empty recordset for public users. The `**kwargs` parameter allows this method to be called with context from the request.

#### `_get_delivery_address_domain() -> Domain`

Returns a `Domain` object matching delivery and "other" type addresses under the partner and the partner itself:
```python
Domain([
    ('id', 'child_of', self.ids),
    '|', ('type', 'in', ['delivery', 'other']), ('id', '=', self.id),
])
```
Used by the address management controller to scope delivery address queries.

---

### `res.config.settings` Extensions

**File:** `~/odoo/odoo19/odoo/addons/portal/models/res_config_settings.py`

#### `portal_allow_api_keys` — Boolean backed by `ir.config_parameter`

| Method | Behavior |
|---|---|
| `compute` | Reads `portal.allow_api_keys` from `ir.config_parameter` |
| `inverse` | Writes to `ir.config_parameter` (not stored on the settings record itself) |
| `get_values()` | Adds `portal_allow_api_keys` to the result with `bool()` wrapper |

This setting gates whether portal users can generate API keys via `res.users.apikeys`.

---

### `res.users.apikeys.description` Extension

**File:** `~/odoo/odoo19/odoo/addons/portal/models/res_users_apikeys_description.py`

**`check_access_make_key()`** override:
- Tries the parent method first.
- If it raises `AccessError`, checks `portal.allow_api_keys` config parameter.
- If the parameter is `True` and the user is a portal user (`_is_portal()`), allows key generation silently.
- If `True` but the user is not portal (internal), raises: `"Only internal and portal users can create API keys"`.
- If the parameter is `False`, re-raises the original `AccessError`.

---

### `ir.http` Extension

**File:** `~/odoo/odoo19/odoo/addons/portal/models/ir_http.py`

`_get_translation_frontend_modules_name()` adds `'portal'` to the list so portal module strings are included in frontend (JavaScript) translation files.

---

### `ir.ui.view` Extension

**File:** `~/odoo/odoo19/odoo/addons/portal/models/ir_ui_view.py`

`customize_show = fields.Boolean("Show As Optional Inherit", default=False)` — marks views as optional portal-specific view inherits. Submodules like `sale_portal`, `purchase_portal` use this flag on their view extensions so the website builder can show/hide portal views via the customization panel.

---

### `ir.qweb` Extension

**File:** `~/odoo/odoo19/odoo/addons/portal/models/ir_qweb.py`

`_prepare_frontend_environment(values)` injects into the template rendering context:
- `is_html_empty`: alias for `odoo.tools.is_html_empty` (checks if HTML content is empty/placeholder)
- `frontend_languages`: lazy lambda returning `res.lang._get_frontend()` (active languages for the website)

These allow portal templates to conditionally render content and render language selectors.

---

## Controllers

### `CustomerPortal` (`portal.py`)

The main portal controller. All routes require `auth="user"` and `website=True` unless noted.

**File:** `~/odoo/odoo19/odoo/addons/portal/controllers/portal.py`

#### Key Routes

| Route | Method | Auth | Description |
|---|---|---|---|
| `/my`, `/my/home` | GET | user | Portal home dashboard |
| `/my/counters` | JSON | user, readonly | Returns record counts for dashboard badge display |
| `/my/account` | GET/POST | user | Edit main account contact details |
| `/my/addresses` | GET | user, readonly | List all billing/delivery addresses |
| `/my/address` | GET | user, readonly | View/edit single address form |
| `/my/address/submit` | POST | user | Create or update address |
| `/my/address/archive` | JSON | user | Archive an address |
| `/my/address/country_info/<country>` | JSON | public | Get country-specific address fields and states |
| `/my/security` | GET/POST | user | Change password |
| `/my/deactivate_account` | POST | user | Deactivate portal account, log out |
| `/portal/attachment/remove` | JSON | public | Remove pending (unlinked) attachments |

#### Address Form Validation (`_validate_address_values()`)

Comprehensive server-side validation of submitted address data:
1. **Country change**: blocked if `_can_edit_country()` returns `False`. Raises: `"Changing your country is not allowed once document(s) have been issued"`.
2. **Name/email change**: blocked for any partner that has a non-portal (internal) user. Raises: `"If you are ordering for an external person..."` — prevents internal users from editing contacts via the portal.
3. **Commercial field changes on child addresses**: blocked for all commercial fields (name, email, VAT, phone, street, etc.). Raises: `"The field_name is managed on your company account"`.
4. **VAT change on commercial partner**: blocked if `can_edit_vat()` returns `False`. Raises: `"Changing VAT number is not allowed once document(s) have been issued"`.
5. **Email format**: `single_email_re` regex validation.
6. **VAT syntax**: if `account` module is installed, creates a dummy partner with the VAT data and calls `_check_vat()`.
7. **Required fields**: based on country (`state_required`, `zip_required`) and address type (billing/delivery). If any address fields are partially filled, all mandatory address fields become required (prevents partial addresses).
8. **Partial address guard**: if `country_id` is set and `street`, `city`, or `country_id` have values, the full address becomes required.

#### `_create_or_update_address()` Logic

- **New address**: calls `res.partner.create()` with `tracking_disable=True` (no mail tracking) and `no_vat_validation=True` (already validated). Triggers `_onchange_phone_validation()` if `phone_validation` module is installed.
- **Existing address**: skips write if values are unchanged (`_are_same_addresses()`). If name is changed, pops it from address_values to avoid affecting bank account holder name. Triggers `_onchange_phone_validation()` on phone changes.
- **Company name sync**: if the address belongs to a commercial partner that is a company, and `company_name` is submitted, updates the parent company's `name`.

---

### `PortalChatter` (extends `mail.controllers.thread.ThreadController`)

**File:** `~/odoo/odoo19/odoo/addons/portal/controllers/portal.py`

| Route | Auth | Description |
|---|---|---|
| `/portal/chatter_init` | public | Initializes `Store` data for the portal chatter widget |
| `/mail/chatter_fetch` | public | Fetches messages for a portal thread |
| `/mail/update_is_internal` | user | Updates message `is_internal` flag |
| `/mail/avatar/...` | public | Serves message author avatars with token/hash auth |

**`portal_message_fetch()`** domain construction:
```python
Domain(self._setup_portal_message_fetch_extra_domain(kw))
& Domain(field.get_comodel_domain(model))   # from website_message_ids field
& Domain("res_id", "=", thread_id)
& Domain("subtype_id", "=", mail.mt_comment)
& self._get_non_empty_message_domain()
```
The `_get_non_empty_message_domain()` excludes messages with empty bodies (`'<span class="o-mail-Message-edited"></span>'` — the edited marker) and messages without attachments.

For public users, `request.update_context(portal_data={"portal_partner": ..., "portal_thread": ...})` is set so message formatting can attribute authorship correctly.

---

### `PortalThreadController` (extends `mail.controllers.thread.ThreadController`)

**File:** `~/odoo/odoo19/odoo/addons/portal/controllers/portal_thread.py`

**`_prepare_message_data()`** — for public users with valid portal auth, overrides `author_id` in the post data to the portal partner rather than the public user. This ensures messages posted via shared links are correctly attributed.

**`_can_edit_message()`** — for public users, allows editing only if the message `author_id` matches the portal partner authenticated via the share link parameters.

---

### `PortalMessageReactionController` (extends `mail.controllers.message_reaction.MessageReactionController`)

**File:** `~/odoo/odoo19/odoo/addons/portal/controllers/message_reaction.py`

When a public user reacts to a message on a portal thread, `_get_reaction_author()` checks `get_portal_partner()`. If found, returns the portal partner with a guest ID of `mail.guest` empty recordset. This allows portal-authenticated reactions.

---

### `MailController` Override

**File:** `~/odoo/odoo19/odoo/addons/portal/controllers/mail.py`

**`_redirect_to_record()`** — when the user lacks backend access but provides a valid `access_token`, and the model implements `portal.mixin`:
1. Switches to `base.public_user` if no session.
2. Calls `record.check_access('read')` (may raise `AccessError`).
3. If access denied and `consteq(access_token, record.access_token)` succeeds, calls `record._get_access_action(force_website=True)`.
4. If `pid` and `hash` are in kwargs, appends them to the redirect URL query string (sorted, encoded).

**`_redirect_to_generic_fallback()`** — for share users with no specific record access, redirects to `/my` instead of the backend fallback.

---

### `Home` Override

**File:** `~/odoo/odoo19/odoo/addons/portal/controllers/web.py`

Redirects non-internal users away from the backend:
- `index()`, `web_client()`, `_login_redirect()` — all check `is_user_internal(uid)`. Non-internal users are redirected to `/my`.

---

## Utils (`portal/utils.py`)

**File:** `~/odoo/odoo19/odoo/addons/portal/utils.py`

### `validate_thread_with_hash_pid(thread, _hash, pid) -> bool`

Timing-safe comparison of HMAC signature. If `_hash` and `pid` match `_sign_token(pid)`, returns `True`. Also checks `_portal_get_parent_hash_token()` — allows sharing child records (like order lines) using the parent record's (order's) signature.

### `validate_thread_with_token(thread, token) -> bool`

Timing-safe comparison via `consteq(token, thread[thread._mail_post_token_field])`. The `thread._mail_post_token_field` resolves to `'access_token'`.

### `get_portal_partner(thread, _hash, pid, token) -> res.partner`

Returns the authenticated portal partner from URL parameters. Priority:
1. `hash` + `pid` validation — most secure (used for shared invitation links).
2. `token` validation with partner from `_mail_get_partners()` — for registered portal users clicking a share link.
3. Empty recordset — anonymous/unauthenticated.

---

## Security

### Access Control (ir.model.access.csv)

| Model | Group | R | W | C | D |
|---|---|---|---|---|---|
| `portal.share` | `base.group_partner_manager` | 1 | 1 | 1 | 0 |
| `portal.wizard` | `base.group_partner_manager` | 1 | 1 | 1 | 0 |
| `portal.wizard.user` | `base.group_partner_manager` | 1 | 1 | 1 | 0 |

`portal.mixin` is abstract — no ACL entries. Extending models must define their own `ir.rule` records for portal access scoping.

### Token Security

- `access_token` uses `uuid.uuid4()` — cryptographically unpredictable.
- All token comparisons use `consteq()` (timing-safe string comparison) to prevent timing attacks.
- HMAC signing uses `database.secret` — server-side only, not exposed to clients.
- Share URLs with `pid` + `hash` allow chatter authentication without a session cookie.
- The `hash` is a one-way HMAC; it cannot be reversed to recover the secret.

### Portal User Isolation

- Portal users are redirected from `/web` (backend) to `/my` (portal home).
- Portal users see only records within their commercial partner hierarchy via `ir.rule`.
- Address editing is scoped to the partner's own commercial partner and its child addresses.
- Internal notes (`is_internal=True`) are hidden from portal users in message fetching.
- Commercial fields on child addresses cannot be modified through the portal form — all commercial fields are silently stripped from `address_values` during write.
- VAT changes are blocked on commercial partners after documents have been issued (`can_edit_vat()` check).

---

## Extending the Portal

### Adding Portal Access to a Model

```python
from odoo import models, api

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'portal.mixin']

    def _compute_access_url(self):
        for order in self:
            order.access_url = f'/my/orders/{order.id}'
```

### Custom Share URL Parameters

Override `_get_share_url()` to add custom parameters to the share URL:

```python
def _get_share_url(self, redirect=False, signup_partner=False, pid=None, share_token=True):
    url = super()._get_share_url(redirect, signup_partner, pid, share_token)
    return f"{url}&custom_param=value"
```

### Custom Access Warnings

Override `_compute_access_warning()` to add model-specific access warnings:

```python
def _compute_access_warning(self):
    for record in self:
        if record.state == 'draft':
            record.access_warning = _('This quote has not been confirmed yet.')
        elif record.amount_total == 0:
            record.access_warning = _('This order has no total.')
        else:
            record.access_warning = ''
```

### Parent-Delegated Sharing

To allow sharing a child record (e.g., `sale.order.line`) using the parent record's (`sale.order`) access token and signature:

```python
from odoo import models

class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'portal.mixin']

    def _portal_get_parent_hash_token(self, pid):
        return self.order_id._sign_token(pid)
```

### Registering Portal Dashboard Counters

Override `_prepare_home_portal_values()` in the extending controller to add record counts:

```python
from odoo.addons.portal.controllers.portal import CustomerPortal

class CustomPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'my_records' in counters:
            values['my_records_count'] = self._my_records_count()
        return values

    def _my_records_count(self):
        return self.env['my.model'].search_count([
            ('partner_id', 'child_of', self.env.user.partner_id.commercial_partner_id.id)
        ])
```

---

## See Also

- [[Core/API]] — `@api.depends`, `@api.onchange` decorators used in portal models
- [[Patterns/Security Patterns]] — ACL CSV, `ir.rule`, portal security model
- [[Modules/Sale]] — `sale.portal` extends this module for sales orders
- [[Modules/Purchase]] — `purchase.portal` extends this module for purchase orders
- [[Modules/Stock]] — `stock.portal` provides portal access to pickings
