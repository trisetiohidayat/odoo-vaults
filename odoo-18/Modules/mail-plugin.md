---
Module: mail_plugin
Version: Odoo 18
Type: Integration
Tags: [mail,plugin,outlook,gmail,RPC,res.partner,iap,enrichment]
Description: Mail plugin base — Outlook/Gmail sidebars, partner search, IAP enrichment, email logging. Provides the JSON-RPC bridge between mail clients and Odoo.
See Also: [mail](mail.md), [iap](iap.md), [Modules/crm_mail_plugin](modules/crm_mail_plugin.md), [Modules/crm_iap_enrich](modules/crm_iap_enrich.md)
---

# mail_plugin — Mail Plugin (Outlook / Gmail Sidebar)

> **Source:** `~/odoo/odoo18/odoo/addons/mail_plugin/`
> **Depends:** `web`, `contacts`, `iap`

The `mail_plugin` module provides a JSON-RPC API bridge between external mail clients (Outlook, Gmail browser extensions) and Odoo. It exposes partner search, creation, enrichment via IAP, email logging, and translation endpoints. Authentication uses the `outlook` auth method (API key scoped to `odoo.plugin.outlook`).

---

## Authentication Architecture

### `_auth_method_outlook()`

**File:** `models/ir_http.py`

```python
@classmethod
def _auth_method_outlook(cls):
    access_token = request.httprequest.headers.get('Authorization')
    if access_token.startswith('Bearer '):
        access_token = access_token[7:]
    user_id = request.env["res.users.apikeys"]._check_credentials(
        scope='odoo.plugin.outlook', key=access_token
    )
    request.update_env(user=user_id)
    request.update_context(**request.env.user.context_get())
```

L4: All `/mail_plugin/*` routes use `auth="outlook"`, which triggers this method. The `res.users.apikeys` table stores the API key; `_check_credentials` validates the key against the stored hash. The session switches to the API key owner's identity (`user_id`) and restores their context (company, lang, etc.).

### OAuth Flow (3-Legged)

**File:** `controllers/authenticate.py`

```
1. Plugin → GET /mail_plugin/auth?scope=outlook&friendlyname=...&redirect=...
   → renders 'mail_plugin.app_auth' (allow/deny form)

2. User allows → POST /mail_plugin/auth/confirm
   → _generate_auth_code(scope, name)
   → HMAC-SHA256 of {scope, name, timestamp, uid} with key 'mail_plugin'
   → returns auth_code (base64-encoded payload.signature)

3. Plugin → POST /mail_plugin/auth/access_token {auth_code}
   → _get_auth_code_data(): verifies HMAC, checks expiry (3 min)
   → _generate(api_key) with scope 'odoo.plugin.outlook', TTL 1 day
   → returns {access_token}

4. Plugin uses access_token in Authorization: Bearer <token> header
```

Old routes (`/mail_client_extension/*`) are maintained for backward compatibility with older plugin versions.

---

## Model: `res.partner` — Extended with Plugin Fields

**File:** `models/res_partner.py`
**Inheritance:** `_inherit = 'res.partner'`

### Plugin-Computed Fields

| Field | Type | Description |
|---|---|---|
| `iap_enrich_info` | Text | JSON string of IAP enrichment response (computed from `res.partner.iap`) |
| `iap_search_domain` | Char | Domain used to query IAP (computed from `res.partner.iap`) |

### Computed Logic

```python
def _compute_partner_iap_info(self):
    partner_iaps = self.env['res.partner.iap'].sudo().search([('partner_id', 'in', self.ids)])
    partner_iaps_per_partner = {p.partner_id: p for p in partner_iaps}
    for partner in self:
        if partner_iap := partner_iaps_per_partner.get(partner):
            partner.iap_enrich_info = partner_iap.iap_enrich_info
            partner.iap_search_domain = partner_iap.iap_search_domain
        else:
            partner.iap_enrich_info = False
            partner.iap_search_domain = False
```

### Write Handling

```python
def write(self, vals):
    # On write of iap_enrich_info or iap_search_domain:
    # - Update existing res.partner.iap records
    # - Create new res.partner.iap for partners without one
    # Done without inverse to avoid repeated searches per partner
```

L4: This design keeps the heavy JSON blob (IAP response) off `res.partner` itself, avoiding wide-column performance issues. The `res.partner.iap` model acts as a satellite store.

---

## Model: `res.partner.iap` — IAP Enrichment Satellite

**File:** `models/res_partner_iap.py`

Stores the raw IAP enrichment response per partner, enabling deduplication (never enrich the same company twice) and caching.

### Fields

| Field | Type | Description |
|---|---|---|
| `partner_id` | Many2one(res.partner) | Required, cascade delete |
| `iap_search_domain` | Char | Domain used in the IAP query (e.g. `@acme.com`) |
| `iap_enrich_info` | Text | Full JSON response from IAP server |

### SQL Constraints

`UNIQUE(partner_id)` — one IAP record per partner.

---

## Controller: `MailPluginController`

**File:** `controllers/mail_plugin.py`

All routes use `auth="outlook"` (→ `_auth_method_outlook()`), `cors="*"`, `csrf=False`.

### Endpoint Summary

| Route | Method | Description |
|---|---|---|
| `/mail_plugin/partner/get` | JSON | Get partner by email/name or by ID; auto-creates/enriches company |
| `/mail_plugin/partner/search` | JSON | Search partners by name/ref/email |
| `/mail_plugin/partner/create` | JSON | Create partner with email/name/company |
| `/mail_plugin/partner/enrich_and_create_company` | JSON | Create + enrich new company from contact email |
| `/mail_plugin/partner/enrich_and_update_company` | JSON | Enrich existing company with IAP data |
| `/mail_plugin/log_mail_content` | JSON | Log email body as note on any whitelisted model |
| `/mail_plugin/get_translations` | JSON | Return i18n strings for plugin JS |

### `partner/get` — Main Lookup Endpoint

```python
def res_partner_get(self, email=None, name=None, partner_id=None, **kwargs):
    """
    Logic:
      1. If partner_id: return _get_contact_data(partner)
      2. If email+name:
         a. Block notification email addresses (mail.alias.domain default_from_email)
         b. Search res.partner by email or email_normalized
         c. Return _get_contact_data(partner)
      3. If no partner found:
         a. Return placeholder {id: -1, email, name, enrichment_info: null}
         b. _find_existing_company(domain) → checks res.partner.iap cache first
         c. If no company and user can create → _create_company_from_iap()
         d. Return company data with enrichment_info
    """
```

### `partner/enrich_and_create_company` — New Contact Workflow

When a user clicks "create and enrich partner" from the plugin sidebar:

```python
def res_partner_enrich_and_create_company(self, partner_id):
    """
    1. Validate partner exists and has no parent_id
    2. Extract domain from email via email_normalize
    3. Call _create_company_from_iap(domain) → creates is_company=True partner
    4. Write partner.parent_id = company
    5. Return {enrichment_info, company: _get_company_data(company)}
    """
```

### `partner/enrich_and_update_company` — Update Existing

```python
def res_partner_enrich_and_update_company(self, partner_id):
    """
    For existing companies:
      1. Extract domain, call _iap_enrich(domain)
      2. If 'enrichment_info' key in response → error, return current data
      3. Update partner fields (phone, street, city, zip, website, logo)
         only if currently empty — preserves user-set data
      4. Download and store logo from iap_data['logo'] via requests.get
      5. Post message via 'iap_mail.enrich_company' template
      6. Return {enrichment_info: {type: 'company_updated'}, company}
    """
```

### `log_mail_content` — Email Logging

```python
def log_mail_content(self, model, res_id, message, attachments=None):
    """
    Whitelist: only 'res.partner' in base module (crm plugin extends this).
    attachments: list of (filename, base64_content) tuples.
    Calls: request.env[model].browse(res_id).message_post(body=Markup(message), attachments=...)
    """
```

### `_iap_enrich()` — IAP Bridge

```python
def _iap_enrich(self, domain):
    """
    1. Check domain against iap_tools._MAIL_PROVIDERS (gmail, outlook, etc.)
       → returns {enrichment_info: {type: 'missing_data'}} for consumer domains
    2. Call request.env['iap.enrich.api']._request_enrich({domain: domain})
    3. Handle InsufficientCreditError → return credits URL
    4. Handle other exceptions → return {type: 'other', info: 'Unknown reason'}
    5. If no data found → {type: 'no_data', info: '...'}
    """
```

### `_create_company_from_iap()` — Company Creation from Enrichment

```python
def _create_company_from_iap(self, email):
    """
    1. Extract domain, call _iap_enrich(domain)
    2. Build new_company_info from iap_data:
       - is_company=True, name=iap_data['name'] or domain
       - street, city, zip, phone (from phone_numbers[0])
       - website=iap_data['domain'], email=emails[0]
       - country_id from iap_data['country_code'] → res.country lookup
       - state_id from iap_data['state_code'] + country
       - logo from iap_data['logo'] via requests.get (2s timeout)
       - iap_search_domain, iap_enrich_info (JSON)
    3. Create res.partner with new_company_info
    4. Post iap_mail.enrich_company message (chatter note)
    5. Return new_company, {type: 'company_created'}
    """
```

### `_get_contact_data()` — Response Builder

```python
def _get_contact_data(self, partner):
    """
    Returns: {
        'partner': _get_partner_data(partner) + 'company': _get_company_data(parent)
        'user_companies': request.env.user.company_ids.ids,
        'can_create_partner': request.env['res.partner'].has_access('create'),
    }
    """
```

### `_get_partner_data()` — Per-Record Serialization

```python
def _get_partner_data(self, partner):
    """
    Fields: id, name, email, phone, mobile, is_company, image (image_128),
    title (→ function), enrichment_info (null), can_write_on_partner (ACL check).
    Name fallback: if partner.name empty, parse from email.
    """
```

### `_get_company_data()` — Company Serialization

```python
def _get_company_data(self, company):
    """
    Returns: {id, name, phone, mobile, email, website,
              address: {street, city, zip, country},
              additionalInfo: json.loads(company.iap_enrich_info) or {},
              image: company.image_1920}
    Access check: raises AccessError → returns {'id': company.id, 'name': _('No Access')}
    """
```

### `_find_existing_company()` — Deduplication

```python
def _find_existing_company(self, email):
    """
    1. _get_iap_search_term(email) → '@domain' or full email (if domain blacklisted)
    2. Search res.partner.iap with iap_search_domain=search_term
       → return partner_iap.partner_id if found (cache hit)
    3. Fallback: search res.partner with is_company=True,
       email_normalized LIKE '%@search_term'
    """
```

### `_get_iap_search_term()` — Domain vs. Email

```python
def _get_iap_search_term(self, email):
    domain = email_domain_extract(email)
    if domain not in iap_tools._MAIL_DOMAIN_BLACKLIST:
        return '@' + domain  # search by domain
    return email  # search by full address (blacklisted domain)
```

L4: `_MAIL_DOMAIN_BLACKLIST` is the union of `_MAIL_PROVIDERS` (gmail, hotmail, etc.) plus `'odoo.com'`. For consumer email providers, each address is considered unique. For corporate domains, the domain itself is used as the search key.

---

## Controller: `Authenticate`

**File:** `controllers/authenticate.py`

### Routes

| Route | Auth | Methods | Description |
|---|---|---|---|
| `/mail_plugin/auth` | user | GET | Render allow/deny form |
| `/mail_plugin/auth/confirm` | user | POST | Generate auth code, redirect to plugin |
| `/mail_plugin/auth/access_token` | none | POST/OPTIONS | Exchange auth code for API key |

### `auth_access_token` — Code Exchange

```python
def auth_access_token(self, auth_code=''):
    """
    1. Split auth_code → payload.base64 + signature.base64
    2. Verify HMAC with key 'mail_plugin'
    3. Check expiry: timestamp < 3 minutes old (UTC)
    4. Extract {scope, name, timestamp, uid}
    5. Generate API key: res.users.apikeys._generate(
          scope='odoo.plugin.' + scope, name=name, expiry=1 day)
    6. Return {access_token}
    """
```

---

## L4: Plugin Architecture — Data Flow

```
Outlook/Gmail Plugin (browser extension or Outlook add-in)
        │
        ▼ HTTP: GET /mail_plugin/auth?scope=outlook&redirect=...
    ┌────────────────────────────────────────────────────────┐
    │  Step 1: User Authentication (3-legged OAuth)           │
    │  GET /mail_plugin/auth → app_auth template (allow/deny)│
    │  POST /mail_plugin/auth/confirm → auth_code (3min JWT)  │
    │  POST /mail_plugin/auth/access_token → API key         │
    └────────────────────────────────────────────────────────┘
        │ Authorization: Bearer <api_key>
        ▼ HTTP: POST /mail_plugin/partner/get {email, name}
    ┌────────────────────────────────────────────────────────┐
    │  Step 2: Partner Resolution                             │
    │  1. Search res.partner by email                         │
    │  2. If not found: _find_existing_company(domain)        │
    │     - Check res.partner.iap cache                      │
    │     - Fallback: search res.partner (is_company)        │
    │  3. If no company and can_create: _create_company_from_iap │
    │  4. Return partner + company + can_write flag          │
    └────────────────────────────────────────────────────────┘
        │
        ▼ (optional) HTTP: POST /mail_plugin/log_mail_content
    ┌────────────────────────────────────────────────────────┐
    │  Step 3: Email Logging                                 │
    │  message_post on res.partner (or crm.lead in crm plugin)│
    │  with attachments                                      │
    └────────────────────────────────────────────────────────┘
```

---

## Extensibility Hooks

| Method | Purpose |
|---|---|
| `_mail_content_logging_models_whitelist()` | Override to add models (crm plugin adds `crm.lead`) |
| `_translation_modules_whitelist()` | Override to include additional modules' i18n strings |
| `_get_contact_data()` | Override to return additional partner-related data (e.g. CRM leads) |
| `_get_iap_search_term()` | Override to customize domain extraction behavior |

---

## Module Dependency Graph

```
mail_plugin
  ├── web (session/context)
  ├── contacts (res.partner)
  └── iap
        ├── iap.account
        ├── iap.service
        └── iap.enrich.api → iap_jsonrpc → iap.odoo.com
```

---

## Views

| View | Model | Description |
|---|---|---|
| `mail_plugin_login.xml` | — | App authorization template |
| `res_partner_iap_views.xml` | `res.partner.iap` | Form + list view for IAP enrichment cache |

Menu: `iap.iap_root_menu` → `IAP Partners` → `res.partner.iap` action. Only visible to users with IAP menu access.

---

## SQL Constraints

| Model | Constraint | Meaning |
|---|---|---|
| `res.partner.iap` | `unique_partner_id` | One IAP record per partner |