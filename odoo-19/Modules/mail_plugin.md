# mail_plugin

> Integrates Odoo with email clients (Outlook, Gmail browser extensions). Provides partner enrichment via IAP, contact search from email, and email logging as internal notes — directly inside the mailbox UI.

**Category:** Sales/CRM
**Module:** `mail_plugin`
**Depends:** `web`, `contacts`, `iap`
**Author:** Odoo S.A.
**License:** LGPL-3
**Manifest version:** `1.0`

---

## Overview

The `mail_plugin` module exposes a JSON-RPC API consumed by the Outlook/Gmail browser add-in. It is designed to:

1. **Identify contacts** from incoming emails by email address
2. **Enrich partners** with company data fetched from Odoo IAP (company name, phone, address, logo, website)
3. **Log emails** as internal notes (`mail.mt_note`) on partner records
4. **Create companies** automatically from email domains when no match exists

The module is architected around a strict separation: IAP enrichment data is stored in a dedicated technical model (`res.partner.iap`) rather than bloating the `res.partner` record itself. This keeps the main contact model lean and avoids expensive field migrations.

---

## Manifest

```python
{
    'name': 'Mail Plugin',
    'version': '1.0',
    'category': 'Sales/CRM',
    'sequence': 5,
    'summary': 'Allows integration with mail plugins.',
    'description': "Integrate Odoo with your mailbox, get information about "
                   "contacts directly inside your mailbox, log content of emails "
                   "as internal notes",
    'depends': ['web', 'contacts', 'iap'],
    'data': [
        'views/mail_plugin_login.xml',
        'views/res_partner_iap_views.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

### Dependency Rationale

| Dependency | Role |
|---|---|
| `web` | Provides `res.users.apikeys` model (API key auth mechanism) |
| `contacts` | Supplies `res.partner` with `email_normalized`, `function`, `image_128` |
| `iap` | Provides `iap.enrich.api` endpoint and `iap.account` credit management |

---

## Architecture

```
Browser Extension (Outlook/Gmail)
        |
        |  Bearer Token (API key, scope: odoo.plugin.outlook)
        v
/mail_plugin/*  (MailPluginController)
        |
        |  _iap_enrich(domain)
        v
   IAP Service  (iap.enrich.api._request_enrich)
        |
        v
  res.partner.iap  (technical cache model)
        ^
        |  compute/write hooks
        |
  res.partner  (public fields: iap_enrich_info, iap_search_domain)
```

---

## Models

### `res.partner` — Extended by `mail_plugin`

**File:** `~/odoo/odoo19/odoo/addons/mail_plugin/models/res_partner.py`
**Inheritance:** `_inherit = 'res.partner'`

#### Fields Added by `mail_plugin`

##### `iap_enrich_info` — `fields.Text` (computed)

```
compute='_compute_partner_iap_info'
```

Stores the raw JSON response from the IAP enrichment API. This field is **computed** — it does not store data directly on `res.partner`. Instead, it reads from the related `res.partner.iap` record.

**Why a computed Text field instead of storing directly?** To keep `res.partner` lean. IAP responses can be large and are rarely needed for regular partner operations. Separating them avoids bloating the main table and makes it possible to purge enrichment data independently.

**Performance note:** The compute method runs `sudo().search()` on `res.partner.iap` for every partner in `self`. When called on large recordset batches (e.g., from `mail_plugin/partner/search` with `limit=30`), this is acceptable. However, calling it on thousands of partners will generate N+1 queries. The plugin's use of `limit=30` on search avoids this in normal operation.

##### `iap_search_domain` — `fields.Char` (computed)

```
compute='_compute_partner_iap_info'
```

The domain or full email used when the enrichment request was made. Stored in `res.partner.iap.iap_search_domain` and proxied through this computed field.

#### `_compute_partner_iap_info()`

```python
def _compute_partner_iap_info(self):
    partner_iaps = self.env['res.partner.iap'].sudo().search([
        ('partner_id', 'in', self.ids)
    ])
    partner_iaps_per_partner = {
        partner_iap.partner_id: partner_iap
        for partner_iap in partner_iaps
    }
    for partner in self:
        partner_iap = partner_iaps_per_partner.get(partner)
        if partner_iap:
            partner.iap_enrich_info = partner_iap.iap_enrich_info
            partner.iap_search_domain = partner_iap.iap_search_domain
        else:
            partner.iap_enrich_info = False
            partner.iap_search_domain = False
```

**L3 — Cross-record resolution:** A single `search()` call fetches all `res.partner.iap` records for the batch, then a dictionary lookup maps each to its partner. This avoids N individual queries when computing for many partners. The `sudo()` escalation is required because the API key user may not have read access to `res.partner.iap` directly (it is ACL-protected; only `base.group_system` can write it).

#### `create()` — Override

```python
@api.model_create_multi
def create(self, vals_list):
    partners = super().create(vals_list)
    partner_iap_vals_list = [{
        'partner_id': partner.id,
        'iap_enrich_info': vals.get('iap_enrich_info'),
        'iap_search_domain': vals.get('iap_search_domain'),
    } for partner, vals in zip(partners, vals_list)
      if vals.get('iap_enrich_info') or vals.get('iap_search_domain')]
    self.env['res.partner.iap'].sudo().create(partner_iap_vals_list)
    return partners
```

**Design decision — no inverse method:** The override deliberately avoids a `_inverse` method on the computed field. An inverse would trigger a `search()` for each partner write, resulting in N queries. By using `create` and `write` overrides, the batch operation does a single `search()` + single `create()` per group of partners.

#### `write()` — Override

```python
def write(self, vals):
    res = super(ResPartner, self).write(vals)
    if 'iap_enrich_info' in vals or 'iap_search_domain' in vals:
        partner_iaps = self.env['res.partner.iap'].sudo().search([
            ('partner_id', 'in', self.ids)
        ])
        missing_partners = self
        for partner_iap in partner_iaps:
            if 'iap_enrich_info' in vals:
                partner_iap.iap_enrich_info = vals['iap_enrich_info']
            if 'iap_search_domain' in vals:
                partner_iap.iap_search_domain = vals['iap_search_domain']
            missing_partners -= partner_iap.partner_id

        if missing_partners:
            self.env['res.partner.iap'].sudo().create([{
                'partner_id': partner.id,
                'iap_enrich_info': vals.get('iap_enrich_info'),
                'iap_search_domain': vals.get('iap_search_domain'),
            } for partner in missing_partners])
    return res
```

**L3 — Upsert pattern:** The write override implements a read-then-write / upsert pattern:
1. Search for existing `res.partner.iap` records for all partners being written
2. Update those found in-place
3. Create new `res.partner.iap` records for partners that are missing one

**Edge case:** When multiple partners in `self` share the same `partner_iap` (impossible, since the constraint enforces 1:1), the loop would update the first found. Since the DB constraint guarantees uniqueness, this is safe. The `missing_partners -= partner_iap.partner_id` set subtraction correctly identifies which partners need a new `res.partner.iap` created.

---

### `res.partner.iap` — Technical IAP Cache Model

**File:** `~/odoo/odoo19/odoo/addons/mail_plugin/models/res_partner_iap.py`
**Inheritance:** `_name = 'res.partner.iap'` (standalone, no `_inherit`)

#### Purpose

This is a **technical model** that acts as an IAP response cache. It exists to:
1. Avoid bloating `res.partner` with a large JSON text field
2. Allow purging IAP data without touching partner records
3. Enable deduplication of enrichment requests (same domain is not enriched twice)

It is **not intended for direct user editing**. It is accessible via a menu under `iap.iap_root_menu` (`IAP Partners`) for administrative inspection.

#### Fields

##### `partner_id` — `fields.Many2one('res.partner')`

```
ondelete='cascade', required=True
```

Links to the enriched partner. `ondelete='cascade'` means deleting the partner automatically deletes the IAP record — no orphaned cache entries.

##### `iap_search_domain` — `fields.Char`

```
help='Domain used to find the company'
```

Stores the domain or email used in the enrichment request (result of `_get_iap_search_term()`). Used by `_find_existing_company()` to check if a company was already enriched for this domain.

##### `iap_enrich_info` — `fields.Text`

```
help='IAP response stored as a JSON string', readonly=True
```

The raw JSON response from `iap.enrich.api._request_enrich()`. Stored as a JSON string (not a JSON field) for compatibility with the compute on `res.partner`. The `readonly=True` flag prevents manual editing through the form UI.

#### Database Constraint

```python
_unique_partner_id = models.Constraint(
    'UNIQUE(partner_id)',
    'Only one partner IAP is allowed for one partner',
)
```

Enforced as a PostgreSQL `UNIQUE` constraint. The test `test_res_partner_iap_constraint` verifies this raises `psycopg2.IntegrityError` on violation.

**L4 — Why a constraint and not just logic?** Because the `write()` override on `res.partner` would otherwise silently create duplicate `res.partner.iap` records when writing IAP fields on multiple contacts that somehow share the same partner (in case of a bug or race condition). The constraint is the last line of defense.

#### Security

Access is restricted to `base.group_system` via `ir.model.access.csv`:

```
mail_plugin.access_res_partner_iap,access_res_partner_iap,
mail_plugin.model_res_partner_iap,base.group_system,1,1,1,1
```

Regular users cannot read, write, create, or unlink these records. Only the `mail_plugin` controller (using `sudo()` internally) and system administrators interact with this model.

---

### `ir.http` — Auth Method Override

**File:** `~/odoo/odoo19/odoo/addons/mail_plugin/models/ir_http.py`
**Inheritance:** `_inherit = 'ir.http'`

#### `_auth_method_outlook()`

```python
@classmethod
def _auth_method_outlook(cls):
    access_token = request.httprequest.headers.get('Authorization')
    if not access_token:
        raise BadRequest('Access token missing')
    if access_token.startswith('Bearer '):
        access_token = access_token[7:]
    user_id = request.env["res.users.apikeys"]._check_credentials(
        scope='odoo.plugin.outlook', key=access_token
    )
    if not user_id:
        raise BadRequest('Access token invalid')
    request.update_env(user=user_id)
    request.update_context(**request.env.user.context_get())
```

**How it works:** All `/mail_plugin/*` routes use `auth="outlook"`. This triggers `_auth_method_outlook`, which:
1. Extracts the `Bearer` token from the `Authorization` header
2. Validates it against `res.users.apikeys` with scope `odoo.plugin.outlook`
3. Switches the request's environment to the API key's owning user
4. Applies that user's context (language, company, tz)

**L4 — Security considerations:**
- The API key scope `odoo.plugin.outlook` is specific to the mail plugin. An API key generated for a different scope (e.g., `odoo.plugin.other`) will not authenticate here.
- API keys are checked with constant-time comparison (`_check_credentials` uses HMAC internally), mitigating timing attacks.
- The auth method **does not** use `sudo()` — it explicitly switches to the real user identity. This ensures ACLs and record rules are enforced for all controller operations.
- Internal users (`_is_internal()`) are required in the OAuth confirmation flow; portal users cannot link their inboxes.
- `_check_credentials` may raise exceptions on key revocation, expiration, or DB changes — these propagate as `BadRequest` to the plugin.

---

## Controllers

### `Authenticate` — OAuth 2.0 Authorization Code Flow

**File:** `~/odoo/odoo19/odoo/addons/mail_plugin/controllers/authenticate.py`

The OAuth flow allows the browser extension to obtain an API key on behalf of the user.

#### Flow Overview

```
Browser Extension
    |
    | 1. Redirects user to /mail_plugin/auth?scope=outlook&redirect=...&friendlyname=...
    v
Authenticate.auth()  [GET /mail_plugin/auth]
    | Renders 'mail_plugin.app_auth' form
    v
User clicks "Allow"
    |
    | 2. POST /mail_plugin/auth/confirm
    v
Authenticate.auth_confirm()  [POST /mail_plugin/auth/confirm]
    | Generates HMAC-signed auth code (3-minute TTL)
    | Redirects to redirect URL with ?auth_code=...&success=1
    v
Browser Extension receives auth_code
    |
    | 3. POST /mail_plugin/auth/access_token
    v
Authenticate.auth_access_token()  [POST /mail_plugin/auth/access_token]
    | Validates HMAC signature + expiry
    | Generates permanent API key (scope: odoo.plugin.outlook, 1-day TTL)
    v
Returns {'access_token': api_key_string}
    |
    v
Browser Extension uses Bearer token in all subsequent calls
```

#### `_generate_auth_code(scope, name)`

```python
def _generate_auth_code(self, scope, name):
    if not request.env.user._is_internal():
        raise NotFound()
    auth_dict = {
        'scope': scope,
        'name': name,
        'timestamp': int(datetime.datetime.utcnow().timestamp()),
        'uid': request.env.uid,
    }
    auth_message = json.dumps(auth_dict, sort_keys=True).encode()
    signature = odoo.tools.misc.hmac(
        request.env(su=True), 'mail_plugin', auth_message
    ).encode()
    auth_code = "%s.%s" % (
        base64.b64encode(auth_message).decode(),
        base64.b64encode(signature).decode()
    )
    return auth_code
```

**L4 — Security properties:**
- **Auth code is a JWT-like structure** with `{data}.{signature}` where data is base64-encoded JSON containing `scope`, `name`, `timestamp`, `uid`.
- **HMAC-SHA256 signature** is computed using Odoo's `hmac()` tool with the server-specific secret key (`'mail_plugin'` hmac key). This secret is stored in `ir.config_parameter` and is unique per database.
- **3-minute TTL** on the auth code: `datetime.datetime.utcnow() - datetime.datetime.fromtimestamp(auth_message['timestamp']) > timedelta(minutes=3)`. This limits the window for replay attacks.
- **Scope binding:** The scope is embedded in the auth code and then used when generating the API key, preventing scope escalation.
- **Name from the plugin** (`friendlyname`): Included in the API key description for auditability (`auth_message['name']` becomes the API key's name in `res.users.apikeys`).

#### `_get_auth_code_data(auth_code)`

```python
def _get_auth_code_data(self, auth_code):
    data, auth_code_signature = auth_code.split('.')
    data = base64.b64decode(data)
    auth_code_signature = base64.b64decode(auth_code_signature)
    signature = odoo.tools.misc.hmac(
        request.env(su=True), 'mail_plugin', data
    ).encode()
    if not hmac.compare_digest(auth_code_signature, signature):
        return None  # Signature mismatch

    auth_message = json.loads(data)
    if datetime.datetime.utcnow() - datetime.datetime.fromtimestamp(
            auth_message['timestamp']) > datetime.timedelta(minutes=3):
        return None  # Expired

    return auth_message
```

Uses `hmac.compare_digest` (constant-time comparison) to prevent timing attacks on the signature check. Timestamp comparison uses UTC explicitly for cross-server compatibility.

#### `auth_access_token()` — API Key Generation

```python
def auth_access_token(self, auth_code='', **kw):
    if not auth_code:
        return {"error": "Invalid code"}
    auth_message = self._get_auth_code_data(auth_code)
    if not auth_message:
        return {"error": "Invalid code"}
    request.update_env(user=auth_message['uid'])
    scope = 'odoo.plugin.' + auth_message.get('scope', '')
    api_key = request.env['res.users.apikeys']._generate(
        scope,
        auth_message['name'],  # e.g., "Outlook: employee@company.com"
        datetime.datetime.now() + datetime.timedelta(days=1)
    )
    return {'access_token': api_key}
```

**L4 — API key lifetime:** The API key is valid for **1 day** (`days=1`). This is a balance between convenience (long enough for the user not to re-authorize constantly) and security (short enough that a leaked key has a limited window). The plugin must implement a refresh mechanism before expiry.

**Scope format:** `auth_message['scope']` (e.g., `"outlook"`) is prefixed with `'odoo.plugin.'` to produce `'odoo.plugin.outlook'`. This is the scope checked by `_auth_method_outlook`.

#### Route Summary

| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/mail_plugin/auth` | GET | `user` (session) | Renders OAuth consent form |
| `/mail_plugin/auth/confirm` | POST | `user` (session) | Processes allow/deny, generates auth code, redirects |
| `/mail_plugin/auth/access_token` | POST | `none` | Exchanges auth code for API key |
| `/mail_plugin/auth/check_version` | POST | `none` | Version compatibility check (returns `1`) |

Legacy aliases exist for all routes (e.g., `/mail_client_extension/auth`) for backward compatibility with older plugin versions (pre-saas-14.3).

---

### `MailPluginController` — Main Plugin API

**File:** `~/odoo/odoo19/odoo/addons/mail_plugin/controllers/mail_plugin.py`

All routes use `auth="outlook"` (custom auth via `_auth_method_outlook`) and `type="jsonrpc"`, `cors="*"`.

#### `res_partner_get(email, name, partner_id, **kwargs)`

```
POST /mail_plugin/partner/get
auth="outlook"
```

**Signature params:** `email=None, name=None, partner_id=None`

The primary lookup endpoint. Resolves a partner by ID or by email+name, with automatic company creation and enrichment.

**Resolution logic (L3 — decision tree):**

```
Input: partner_id given?
  YES → browse(partner_id), return _get_contact_data(partner)

  NO → Need email AND name
    email = tools.email_normalize(email)
    email in mail.alias.domain default_from_email?
      YES → return "Notification address" error

    partner = search(['|', ('email', 'in', [normalized, raw]),
                       ('email_normalized', '=', normalized)], limit=1)
    partner found?
      YES → return _get_contact_data(partner)

    partner NOT found (id = -1 in response):
      can_create_partner = res.partner.has_access('create')

      company = _find_existing_company(normalized_email)
        (checks res.partner.iap cache first, then is_company+email match)

      if not company AND can_create_partner:
        company, enrichment_info = _create_company_from_iap(email)
        response['partner']['enrichment_info'] = enrichment_info

      response['partner']['company'] = _get_company_data(company)
      return response
```

**L3 — Notification email detection:** The check against `mail.alias.domain.default_from_email` prevents the plugin from trying to match Odoo's own notification addresses (e.g., `no-reply@odoo.com`). These addresses are used for outgoing notification emails sent from Odoo itself and should not be linked to partner records.

**L4 — Idempotency via IAP cache:** `_find_existing_company()` first checks `res.partner.iap` by `iap_search_domain`. This means if someone previously enriched `bob@acme.com` (creating company `acme.com` with IAP data), a subsequent lookup for `alice@acme.com` will return the same cached company without calling IAP again. This avoids duplicate companies and conserves IAP credits.

**L4 — has_access('create') check:** The controller checks `request.env['res.partner'].has_access('create')` before creating a company. A user who can use the plugin (has an API key) but lacks create rights on partners will still get the full contact lookup experience but will not trigger company creation.

---

#### `res_partners_search(search_term, limit=30, **kwargs)`

```
POST /mail_plugin/partner/search
auth="outlook"
```

**Purpose:** Autocomplete / type-ahead search in the plugin's contact panel.

**Search domain construction:**

```python
normalized_email = tools.email_normalize(search_term)

if normalized_email:
    filter_domain = [('email_normalized', 'ilike', search_term)]
else:
    filter_domain = ['|', '|',
        ('complete_name', 'ilike', search_term),
        ('ref', '=', search_term),        # exact match on reference
        ('email', 'ilike', search_term)
    ]

partners = request.env['res.partner'].search(filter_domain, limit=limit)
```

**L3 — Email vs. name search split:** If `search_term` normalizes to a valid email, the query searches only `email_normalized` (fast, indexed). If it is not an email, it searches `complete_name` OR `ref` (exact) OR `email` (ILIKE) — a broader but slower three-way OR.

**L4 — `complete_name` vs `name`:** `complete_name` is a computed/concat field that includes the parent company name for contact records (`"Alice (Acme Corp)"`). Searching `complete_name` allows users to find contacts by typing the company name.

---

#### `res_partner_create(email, name, company)`

```
POST /mail_plugin/partner/create
auth="outlook"
```

Creates a new `res.partner` from the plugin UI. `company` param is the `parent_id` (company of the new contact).

**L4 — Notification email blocking:** Raises `Forbidden()` if the email normalizes to a known `mail.alias.domain.default_from_email`. This prevents creating partner records for Odoo's own notification addresses.

---

#### `res_partner_enrich_and_create_company(partner_id)`

```
POST /mail_plugin/partner/enrich_and_create_company
auth="outlook"
```

Used when the plugin user clicks "Create and enrich company" on a contact that has no parent company.

**Preconditions checked:**
1. Partner must exist (returns `{"error": "This partner does not exist"}`)
2. Partner must have no `parent_id` (returns `{"error": "The partner already has a company related to him"}`)
3. `partner.email_normalized` must exist (returns `{"error": "The email of this contact is not valid and we can not enrich it"}`)

---

#### `res_partner_enrich_and_update_company(partner_id)`

```
POST /mail_plugin/partner/enrich_and_update_company
auth="outlook"
```

Used when the plugin user clicks "Enrich company" on an existing company partner.

**Precondition:** `partner.is_company == True` (returns `{"error": "Contact must be a company"}`)

**Update strategy (L3 — non-destructive merge):**

```python
model_fields_to_iap_mapping = {
    'street': 'street_name',
    'city': 'city',
    'zip': 'postal_code',
    'website': 'domain',
}
partner_values.update({
    model_field: iap_data.get(iap_key)
    for model_field, iap_key in model_fields_to_iap_mapping.items()
    if not partner[model_field]  # only fill empty fields
})
```

**L3 — Selective field update:** All mapping fields are updated only if the partner currently has no value. This prevents IAP data from overwriting manually entered or more accurate data. The phone is handled separately (`if not partner.phone and phone_numbers`).

**L3 — Post-enrichment note:** A message is posted using `iap_mail.enrich_company` template with the raw IAP data as `render_values`. This creates an internal note on the partner's chatter, giving a full audit trail of what was enriched and when.

---

#### `log_mail_content(model, res_id, message, attachments=None)`

```
POST /mail_plugin/log_mail_content
auth="outlook"
```

Logs an email body as an internal note on a record.

**Parameters:**
- `model`: The model name (must be in the whitelist)
- `res_id`: The record ID
- `message`: HTML body of the email (wrapped in `Markup` to prevent XSS sanitization)
- `attachments`: List of `(filename, base64_content)` tuples

**Whitelist (`_mail_content_logging_models_whitelist`):**
```python
def _mail_content_logging_models_whitelist(self):
    return ['res.partner']
```

**L3 — Whitelist design:** The whitelist prevents the plugin from logging emails to arbitrary models (e.g., `res.users`, `ir.config_parameter`). Only `res.partner` is whitelisted by default; submodules (e.g., `crm` if installed) extend this by overriding `_mail_content_logging_models_whitelist()`.

**L4 — Attachment handling:** Attachments are base64-decoded before being passed to `message_post(attachments=...)`. The decoding is done in the controller before calling `message_post`, ensuring the message is already processed when it reaches the model layer.

**L4 — XSS protection:** `Markup(message)` is used (from `markupsafe`) to prevent Odoo's HTML sanitizer from stripping email body content (which may legitimately contain HTML formatting, images, etc.). The plugin is a trusted internal component, so the message content is considered safe.

---

#### `_iap_enrich(domain)`

```python
def _iap_enrich(self, domain):
    if domain in iap_tools._MAIL_PROVIDERS:
        return {'enrichment_info': {'type': 'missing_data'}}

    try:
        response = request.env['iap.enrich.api']._request_enrich({domain: domain})
    except iap_tools.InsufficientCreditError:
        enriched_data['enrichment_info'] = {
            'type': 'insufficient_credit',
            'info': request.env['iap.account'].get_credits_url('reveal')
        }
    except Exception:
        enriched_data["enrichment_info"] = {'type': 'other', 'info': 'Unknown reason'}
    else:
        enriched_data = response.get(domain)
        if not enriched_data:
            enriched_data = {'enrichment_info': {'type': 'no_data', ...}}
    return enriched_data
```

**L4 — `_MAIL_PROVIDERS` domain blacklist:** Imported from `iap_tools`, this set contains ~50 generic email providers (`gmail.com`, `outlook.com`, `yahoo.com`, etc. plus `example.com`). Enrichment is refused for these domains because they provide no meaningful company information.

**L4 — `_MAIL_DOMAIN_BLACKLIST` for search:** Separate from `_MAIL_PROVIDERS`, `_MAIL_DOMAIN_BLACKLIST = _MAIL_PROVIDERS | {'odoo.com'}` is used in `_get_iap_search_term()`. When the domain is blacklisted, the search term becomes the full email address (not just the domain), so `bob@gmail.com` searches for `bob@gmail.com` rather than `gmail.com`.

**Error handling tiers:**
- `InsufficientCreditError` → special `type: insufficient_credit` with a link to buy IAP credits
- Generic `Exception` → `type: other` with generic info (avoids leaking internal error details to the plugin UI)
- Empty response from IAP → `type: no_data`

---

#### `_get_iap_search_term(email)`

```python
def _get_iap_search_term(self, email):
    domain = tools.email_domain_extract(email)
    return ("@" + domain) if domain not in iap_tools._MAIL_DOMAIN_BLACKLIST else email
```

**L3 — Deduplication logic:** If the domain is not blacklisted (i.e., it is a real company domain), the search term is `@domain.com`. This means all employees of `acme.com` share the same IAP cache entry. If the domain IS blacklisted, the search term is the full email, ensuring each personal email account gets its own entry.

---

#### `_find_existing_company(email)`

```python
def _find_existing_company(self, email):
    search = self._get_iap_search_term(email)
    partner_iap = request.env["res.partner.iap"].sudo().search([
        ("iap_search_domain", "=", search)
    ], limit=1)
    if partner_iap:
        return partner_iap.partner_id.sudo(False)

    return request.env["res.partner"].search([
        ("is_company", "=", True),
        ("email_normalized", "=ilike", "%" + search)
    ], limit=1)
```

**L3 — Two-tier lookup:** First checks the IAP cache (`res.partner.iap`), then falls back to searching `res.partner` for an existing company with a matching email domain. The `sudo(False)` after the cache hit reverts to the normal user context for the partner lookup, ensuring ACLs are applied to the returned partner.

---

#### `_create_company_from_iap(email)`

Creates a new `res.partner` (company type) from IAP enrichment data.

**Steps:**
1. Extract domain from email via `tools.email_domain_extract()`
2. Call `_iap_enrich(domain)` to fetch company data
3. Map IAP response fields to `res.partner` fields using `model_fields_to_iap_mapping`
4. Resolve country/state by code (`res.country.code`, `res.country.state.code + country_id`)
5. Download and attach logo (2-second timeout, failures silently logged)
6. Store IAP search domain and full JSON response in `res.partner.iap`
7. Post `iap_mail.enrich_company` internal note on the new company

**L4 — Country/state resolution:** Country is resolved by ISO code (`'US'`), state by code within country scope. This prevents ambiguous state codes (e.g., `CA` = California USA vs `CA` = Canada) from resolving incorrectly.

---

#### `_get_contact_data(partner)`

```python
def _get_contact_data(self, partner):
    if partner:
        partner_response = self._get_partner_data(partner)
        if partner.company_type == 'company':
            partner_response['company'] = self._get_company_data(partner)
        elif partner.parent_id:
            partner_response['company'] = self._get_company_data(partner.parent_id)
        else:
            partner_response['company'] = self._get_company_data(None)
    else:
        partner_response = {}

    return {
        'partner': partner_response,
        'user_companies': request.env.user.company_ids.ids,
        'can_create_partner': request.env['res.partner'].has_access('create'),
    }
```

**L3 — Company resolution for contacts:**
- A **company-type partner** (`is_company=True`) has no separate parent — it IS the company. Its own data is returned as `company`.
- A **contact with `parent_id`** returns its parent as `company`.
- A **standalone contact** (no parent_id, not a company) returns `{'id': -1}` as the company.

**L3 — Override point for CRM:** This method is explicitly documented as overridable by other modules (e.g., `crm`) to add lead data to the response. The `crm` module extends this to include `lead_id`, `lead_name`, `lead_stage`, etc.

**L4 — `user_companies` in response:** Returns the IDs of all companies the authenticated user belongs to. The plugin UI uses this to display only relevant companies when creating a new partner.

---

#### `_get_partner_data(partner)`

```python
def _get_partner_data(self, partner):
    fields_list = ['id', 'name', 'email', 'phone', 'is_company']
    partner_values = dict((fname, partner[fname]) for fname in fields_list)
    partner_values['image'] = partner.image_128
    partner_values['title'] = partner.function  # 'Job Position'
    partner_values['enrichment_info'] = None

    try:
        partner.check_access('write')
        partner_values['can_write_on_partner'] = True
    except AccessError:
        partner_values['can_write_on_partner'] = False

    if not partner_values['name']:
        name, email_normalized = tools.parse_contact_from_email(
            partner_values['email']
        )
        partner_values['name'] = name or email_normalized

    return partner_values
```

**L3 — Write permission check:** The `can_write_on_partner` flag tells the plugin UI whether to show "Edit" or "Enrich" actions. This is a read-then-write pattern: `check_access('write')` is called first; if it raises `AccessError`, the flag is set to `False` and the exception is swallowed.

**L3 — Name fallback:** If `partner.name` is empty (possible for contacts created programmatically without a name), the email address is parsed to extract a display name using `tools.parse_contact_from_email()`. This handles formats like `"John Doe" <john@acme.com>` or raw `john@acme.com`.

---

#### `_get_company_data(company)`

```python
def _get_company_data(self, company):
    if not company:
        return {'id': -1}

    try:
        company.check_access('read')
    except AccessError:
        return {'id': company.id, 'name': _('No Access')}

    fields_list = ['id', 'name', 'phone', 'email', 'website']
    company_values = dict((fname, company[fname]) for fname in fields_list)
    company_values['address'] = {
        'street': company.street,
        'city': company.city,
        'zip': company.zip,
        'country': company.country_id.name if company.country_id else ''
    }
    company_values['additionalInfo'] = json.loads(
        company.iap_enrich_info
    ) if company.iap_enrich_info else {}
    company_values['image'] = company.image_1920

    return company_values
```

**L4 — AccessError handling:** If the API key user cannot read the company record (record rule restricting access), the company ID is still returned along with `'No Access'` as the name. This allows the plugin to show the contact but with a clear "no access" indicator on the company side, rather than silently hiding the company or failing the request.

**L4 — `additionalInfo`:** The full IAP JSON response is included as `additionalInfo`, allowing the plugin UI to display enriched fields not stored on `res.partner` (e.g., industry, employee count, revenue — whatever the IAP returns).

---

## Security Model

### ACL Summary

| Model | Access | Group |
|---|---|---|
| `res.partner.iap` | read, write, create, unlink | `base.group_system` |
| `res.partner` | Inherited from `contacts` module | Depends on user type |

### API Key Scopes

| Scope | Generated By | Used By |
|---|---|---|
| `odoo.plugin.outlook` | `auth_access_token()` | All `/mail_plugin/*` routes |

### Route Auth Methods

| Route Group | Auth Method | Notes |
|---|---|---|
| `/mail_plugin/auth*` (confirmation flow) | `auth="user"` (session cookie) | User must be logged in, must be internal |
| `/mail_plugin/partner/*` (data operations) | `auth="outlook"` (API key) | API key scoped to `odoo.plugin.outlook` |

### L4 — Attack Surface

1. **Auth code replay:** Mitigated by 3-minute TTL + HMAC signature. Even if intercepted, the auth code expires before it can be used.
2. **API key theft:** API keys are 1-day TTL. Leaked keys auto-expire. The scope restriction (`odoo.plugin.outlook`) prevents reuse of these keys against other APIs.
3. **IAP credit exhaustion:** `InsufficientCreditError` is caught and surfaced to the user as a readable message. A malicious actor with a valid API key could trigger enrichment requests, burning IAP credits. Mitigations: API key is per-user (auditable), IAP has rate limiting server-side.
4. **Company data poisoning:** An IAP provider returning malicious data cannot directly write to `res.partner` fields — all IAP data is stored as JSON text in `iap_enrich_info` and only specific whitelisted fields are mapped. The logo download has a 2-second timeout and failures are silent.
5. **Notification email registration:** The `mail.alias.domain` check prevents registering Odoo's own notification addresses as partner records, which could cause mail loop or tracking issues.
6. **Timing attacks on signature verification:** `hmac.compare_digest` is used throughout, ensuring constant-time comparison for both auth code signature validation and API key lookup.

---

## Odoo 17→18→19 Changes

- **Route naming:** Pre-saas-14.3, routes used the `/mail_client_extension/` prefix. All routes now also accept `/mail_plugin/` prefix. The old routes are maintained for backward compatibility with installed older plugin versions.
- **IAP response caching:** The `res.partner.iap` technical model was introduced to cache IAP responses. In earlier versions, enrichment was re-requested on every lookup. The cache is keyed by the IAP search domain, so repeated lookups for employees of the same company do not consume IAP credits.
- **OAuth flow:** The auth code + API key exchange replaced an earlier token mechanism. The HMAC-signed auth code pattern was hardened over multiple releases (adding TTL, scope embedding, `hmac.compare_digest`).

---

## Odoo 18→19 Changes

- No breaking changes to the `mail_plugin` module itself in Odoo 19. The module structure, API routes, and model fields remain consistent with Odoo 18.
- The `iap` module dependency is now formally declared, ensuring `iap_tools._MAIL_PROVIDERS` and `iap_tools._MAIL_DOMAIN_BLACKLIST` are always available.

---

## Extensibility Points

| Method | Override Purpose |
|---|---|
| `_mail_content_logging_models_whitelist()` | Add models (e.g., `crm.lead`) to the email logging whitelist |
| `_translation_modules_whitelist()` | Add modules whose strings should be included in the translation response |
| `_get_contact_data()` | Add fields to the partner response (e.g., CRM lead data) |
| `_iap_enrich()` | Intercept or mock IAP enrichment for testing |
| `_get_partner_data()` | Add fields to the per-partner data returned to the plugin |

---

## Views

### `mail_plugin_login.xml` — OAuth Consent Templates

Two QWeb templates rendered by the `Authenticate` controller:

- **`mail_plugin.app_auth`:** Renders a "Let [friendlyname] access your Odoo database?" form with Allow/Deny buttons. POSTs to `/mail_plugin/auth/confirm`.
- **`mail_plugin.app_error`:** Renders an error message (e.g., "Access Error: Only Internal Users can link their inboxes") using `web.login_layout`.

### `res_partner_iap_views.xml` — IAP Partner Administration Views

A minimal form + list view for the `res.partner.iap` technical model, accessible under `IAP Partners` menu under the `iap` root menu (`iap.iap_root_menu`). This is for administrative inspection only; the model is not designed for direct user editing (fields are `readonly=True` on the form).

---

## Tags

`#odoo` `#odoo19` `#modules` `#mail_plugin` `#iap` `#email-integration` `#contacts` `#crm` `#security`
