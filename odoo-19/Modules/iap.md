---
title: IAP (In-App Purchase)
description: In-App Purchase infrastructure for Odoo. Manages IAP accounts, service registry, credit tracking, warning thresholds, RPC helpers, and the lead enrichment API for consuming paid Odoo IAP services.
tags: [odoo19, iap, infrastructure, credits, rpc, module, security]
model_count: 3
models:
  - iap.account (IAP account management, token auth, balance sync)
  - iap.service (service registry, technical name uniqueness)
  - iap.enrich.api (abstract model for lead enrichment via Clearbit)
dependencies:
  - web
  - base_setup
category: Hidden/Tools
source: odoo/addons/iap/
created: 2026-04-06
updated: 2026-04-11
l4_status: complete
---

# IAP (In-App Purchase)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `iap` |
| **Version** | 1.1 |
| **Category** | Hidden/Tools |
| **Depends** | `web`, `base_setup` |
| **Auto-install** | Yes |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Source Path** | `odoo/addons/iap/` |

### Purpose

IAP provides the shared infrastructure for all Odoo apps that consume paid services from Odoo's IAP platform. It centralizes account management, token-based authentication, credit tracking, email alert thresholds, and RPC communication so that consumer apps (CRM, Partner Autocomplete, Snailmail, etc.) do not duplicate this logic. It also ships the `iap.enrich.api` abstract model used by CRM for lead enrichment via Clearbit.

### Key Design Decisions

- **Singleton account per service+company** — `iap.account.get()` always returns exactly one account for a given service in the current company context. The cursor-based creation pattern prevents race conditions during rollback scenarios.
- **Token is never exposed to regular users** — `account_token` field carries `groups="base.group_system"`, so only superusers can read it. The test suite explicitly asserts this.
- **Balance is fetched on every web read** — `web_read()` triggers `_get_account_information_from_iap()` unless `disable_iap_fetch` is in context. The form view for an IAP account therefore always shows the live credit balance from the IAP server.
- **Separate-cursor creation pattern** — Two distinct `with self.pool.cursor() as cr` blocks isolate account deletion and account creation from the caller's transaction. This is critical because both paths can trigger rollbacks (e.g., `NoCreditError` during first use), and a rollback must not undo the account creation.
- **Neutralized databases** get a `+disabled` token suffix appended on create, which `_hash_iap_token()` strips before sending to the IAP server. The server then rejects the disabled token.
- **No `iap.account.threshold` model** — The threshold/alerts mechanism is implemented as two fields on `iap.account` itself: `warning_threshold` (Float) and `warning_user_ids` (Many2many res.users). There is no separate threshold model.

---

## Module Architecture

```
iap/
├── __manifest__.py              # Auto-install; depends on web + base_setup
├── models/
│   ├── __init__.py
│   ├── iap_account.py          # Main account model (267 lines)
│   ├── iap_service.py          # Service registry (20 lines)
│   └── iap_enrich_api.py       # Abstract enrichment helper (40 lines)
├── tools/
│   └── iap_tools.py            # iap_jsonrpc(), InsufficientCreditError, mail_prepare_for_domain_search()
├── data/
│   └── services.xml            # Pre-loaded "reveal" service (Lead Generation)
├── security/
│   ├── ir.model.access.csv      # ACLs for iap.account and iap.service
│   └── ir_rule.xml             # Company-scoped record rule for iap.account
├── views/
│   ├── iap_views.xml           # Form, list, action, menu for iap.account
│   └── res_config_settings.xml # Settings view integration
├── static/src/
│   └── action_buttons_widget/
│       ├── action_buttons_widget.js   # OWL component, "Buy More Credits" widget
│       └── action_buttons_widget.xml  # QWeb template
└── tests/
    ├── __init__.py
    ├── common.py                # MockIAPEnrich, test data builders for Clearbit responses
    └── test_iap.py              # Token access-control test (demo user vs admin)
```

---

## Model Details

### `iap.account`

**Technical Name:** `iap.account`
**Description:** Links a database to a specific IAP service, holds the authentication token, and synchronizes balance, state, and alert thresholds with the IAP server.

#### Fields

| Field | Type | Required | Groups | Description |
|-------|------|----------|--------|-------------|
| `name` | Char | No | — | Display name. Auto-set to `service_id.name` on `create()` if not explicitly provided. |
| `service_id` | Many2one `iap.service` | **Yes** | — | The IAP service this account is for. Once the account is confirmed server-side, this becomes read-only (locked by `service_locked = True`). |
| `service_name` | Char (related, readonly) | — | — | Read-only shortcut to `service_id.technical_name`. Used in domain filters and `get()`. |
| `service_locked` | Boolean | No | — | If `True`, the `service_id` field is read-only in the UI. Set to `True` by `_get_account_info()` after the IAP server confirms the account exists. Prevents accidental service reassignment. |
| `description` | Char (related, readonly) | — | — | Shortcut to `service_id.description`. |
| `account_token` | Char(43) | No | `base.group_system` | UUID-based authentication token. Generated via `uuid.uuid4().hex` on create. **Never readable by regular users.** `copy=False` prevents token duplication on record copy. |
| `company_ids` | Many2many `res.company` | No | — | Scoping companies. If empty (no records), the account is global and usable by all companies. Company-scoped accounts take precedence in `get()`. |
| `balance` | Char (readonly) | — | — | Human-readable balance string, e.g., `"42 Credits"`. Populated asynchronously by `_get_account_information_from_iap()` on every `web_read()`. |
| `warning_threshold` | Float | No | — | Credit level below which email alerts are triggered. Written back to the IAP server on change. Must be non-negative (enforced by `validate_warning_alerts()`). |
| `warning_user_ids` | Many2many `res.users` | No | — | Recipients of low-credit email alerts. All must have a non-empty `email` field (enforced by `validate_warning_alerts()`). |
| `state` | Selection | — | — | Account state: `unregistered`, `registered`, `banned`. Set by the IAP server via `_get_account_information_from_iap()`. |

#### Constraints

`validate_warning_alerts()` — `@api.constrains('warning_threshold', 'warning_user_ids')`

Raises `UserError` if:
1. `warning_threshold < 0`
2. Any user in `warning_user_ids` has no `email` address

This constraint fires on every `write()` that touches either field. It runs as the caller's user (no sudo), so the email-check query is subject to normal record rules on `res.users`.

#### Key Methods

##### `web_read(*args, **kwargs)` — Balance Sync Hook

Hooks into Odoo's web controller read path. This is the entry point for the live balance display in the IAP account form view.

```python
def web_read(self, *args, **kwargs):
    if not self.env.context.get('disable_iap_fetch'):
        self._get_account_information_from_iap()
    return super().web_read(*args, **kwargs)
```

**Performance implication:** This fires an HTTP POST to the IAP server on every form load and list view access for any `iap.account` record. In batched list views with many accounts, all accounts are fetched in a single batched call (`/iap/1/get-accounts-information`). The call is silent on failure — the old `balance` value is retained and a warning is logged.

**Context flag:** `disable_iap_fetch` suppresses the sync. This is set by `web_save()` to prevent a redundant round-trip after a save operation (since `write()` already handles alert-threshold sync separately).

##### `web_save(*args, **kwargs)`

Wraps the parent `web_save()` with `disable_iap_fetch=True` to prevent the IAP server call that `web_read()` would otherwise trigger after the save completes.

##### `write(vals)`

General `write()` override. If `warning_threshold` or `warning_user_ids` changed and `disable_iap_update` is not in context, it pushes those values to the IAP server via `POST /iap/1/update-warning-email-alerts`.

```python
def write(self, vals):
    res = super().write(vals)
    if (
        not self.env.context.get('disable_iap_update')
        and any(w in vals for w in ('warning_threshold', 'warning_user_ids'))
    ):
        for account in self:
            data = {
                'account_token': account.sudo().account_token,
                'warning_threshold': account.warning_threshold,
                'warning_emails': [{
                    'email': user.email,
                    'lang_code': user.lang or get_lang(self.env).code,
                } for user in account.warning_user_ids],
            }
            try:
                iap_jsonrpc(url, params=data)
            except AccessError as e:
                _logger.warning("Update of the warning email configuration has failed: %s", str(e))
    return res
```

**Key behaviors:**
- Runs with `sudo()` for the `account_token` read, but `warning_user_ids` as the caller's user (correct for email personalization).
- Language code from `user.lang` is included so the IAP server can send emails in the recipient's preferred language.
- Network failure on alert sync is non-fatal — the local change is kept and the error is logged.

##### `_get_account_information_from_iap()` — Server Balance Fetch

Called by `web_read()`. Fetches `balance`, `warning_threshold`, `state`, and sets `service_locked` from the IAP server.

```python
def _get_account_information_from_iap(self):
    if module.current_test:
        return  # Guards against live server calls during tests
    params = {
        'iap_accounts': [{
            'token': account.sudo().account_token,
            'service': account.service_id.technical_name,
        } for account in self if account.service_id],
        'dbuuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
    }
    accounts_information = iap_jsonrpc(url, params=params)
    for token, information in accounts_information.items():
        accounts = self.filtered(lambda acc: secrets.compare_digest(acc.sudo().account_token, token))
        for account in accounts:
            balance_amount = round(information['balance'],
                None if account.service_id.integer_balance else 4)
            balance = f"{balance_amount} {account.service_id.unit_name or ''}"
            account_info = self._get_account_info(account, balance, information)
            account.with_context(disable_iap_update=True, tracking_disable=True).write(account_info)
```

**Critical details:**
- **Timing-attack safe token matching:** Uses `secrets.compare_digest()` rather than `==` to prevent timing attacks when matching tokens returned from the server.
- **Batched:** Sends all account tokens in one request. The IAP server returns a dict keyed by token.
- **Balance rounding:** If `service_id.integer_balance` is `True`, Python's `round(x, None)` truncates to the nearest integer (banker's rounding via `ROUND_HALF_EVEN` equivalent). Otherwise, rounds to 4 decimal places.
- **`service_locked = True`:** Once the IAP server has confirmed the account exists, `service_locked` prevents further service reassignment in the UI.
- **`disable_iap_update=True`:** Prevents the `write()` override from attempting to push the already-synced threshold back to the server (avoiding a feedback loop).
- **`tracking_disable=True`:** Suppresses message-tracking chatter for this automated update.
- **Silently skips on failure:** `AccessError` from the RPC is caught and logged as a warning; the old field values are preserved.

##### `_get_account_info(account_id, balance, information)`

Builds the `write()` dict from server response. Override point for subclasses.

```python
def _get_account_info(self, account_id, balance, information):
    return {
        'balance': balance,
        'warning_threshold': information['warning_threshold'],
        'state': information['registered'],  # 'registered' | 'banned' | 'unregistered'
        'service_locked': True,
    }
```

The `state` value comes from the `registered` key in the server response (a string enum, not a boolean).

##### `create(vals_list)` — Multi-create + Neutralization

```python
@api.model_create_multi
def create(self, vals_list):
    accounts = super().create(vals_list)
    for account in accounts:
        if not account.name:
            account.name = account.service_id.name

    if self.env['ir.config_parameter'].sudo().get_param('database.is_neutralized'):
        for account in accounts:
            account.account_token = f"{account.account_token.split('+')[0]}+disabled"
    return accounts
```

- Uses `@api.model_create_multi` to support batch account creation efficiently.
- `name` auto-fill runs after the super call, using the newly-set `service_id` relationship.
- On neutralized databases, the `+disabled` suffix is appended. Note this happens in a separate SQL update rather than inline in vals, because `account_token` has `copy=False`.

##### `get(service_name, force_create=True)` — Singleton Getter (Most Critical Method)

Returns the IAP account for a service in the current company. This is the primary entry point used by all consumer modules.

**Domain construction:**
```python
domain = [
    ('service_name', '=', service_name),
    '|',
        ('company_ids', 'in', self.env.companies.ids),  # company-scoped accounts
        ('company_ids', '=', False)                       # global accounts
]
accounts = self.search(domain, order='id desc')
```

**Multi-company behavior:** `self.env.companies` is a recordset of all companies the current user has access to (based on `res.company` rules). The domain returns accounts for any of those companies plus global accounts. The `order='id desc'` ensures the most recently created account wins when multiple match — giving priority to company-specific accounts since those are typically created later than the global fallback.

**Two-phase cursor cleanup:**

1. **Stale account cleanup:** If accounts exist with no `account_token` (e.g., partially created during a prior failed request), they are deleted in a separate cursor. The `flush_all()` before the cursor switch ensures no pending writes cause a deadlock. This runs with `sudo()` because regular users lack `unlink` rights on `iap.account`.

2. **New account creation:** If no account exists and `force_create=True`, a new one is created in a separate cursor. This is essential because the creation may trigger a `NoCreditError` from the IAP server (e.g., the new account immediately tries to charge credits), which causes a rollback. Without the separate cursor, the rollback would also undo the account record that was just created.

**Cache injection pattern:**
```python
account_token = account.sudo().account_token
account = self.browse(account.id)
self.env.cache.set(account, IapAccount._fields['account_token'], account_token)
return account
```
After the separate cursor closes, `self` cannot see the newly created record (different transaction). `self.browse(account.id)` re-instantiates the record in the current transaction. The manual `cache.set()` pre-populates the `account_token` field cache so the very next call to `account_token` does not trigger a lazy SQL fetch (which would fail since the token was created in a different cursor).

##### `get_account_id(service_name)`

Convenience wrapper. Returns only the record ID rather than the full recordset. Used by the frontend widget (`action_buttons_widget.js`) to navigate directly to the account form.

```python
@api.model
def get_account_id(self, service_name):
    return self.get(service_name).id
```

##### `get_credits_url(service_name, account_token=None)`

Generates the credit purchase portal URL. Used by `action_buy_credits()` and called directly by consumer modules (snailmail, partner_autocomplete).

```python
@api.model
def get_credits_url(self, service_name, account_token=None):
    dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
    endpoint = iap_tools.iap_get_endpoint(self.env)
    route = '/iap/1/credit'
    base_url = url_join(endpoint, route)
    account_token = account_token or self.get(service_name).sudo().account_token
    hashed_account_token = self._hash_iap_token(account_token)
    d = {'dbuuid': dbuuid, 'service_name': service_name, 'account_token': hashed_account_token, 'hashed': 1}
    return '%s?%s' % (base_url, werkzeug.urls.url_encode(d))
```

The token is SHA-1 hashed before being embedded in the URL. This means even if the URL is intercepted, the raw token is never transmitted over the network.

##### `_hash_iap_token(key)`

```python
@api.model
def _hash_iap_token(self, key):
    key = (key or '').split('+')[0]  # strip +disabled suffix
    if not key:
        raise UserError(_('The IAP token provided is invalid or empty.'))
    return hashlib.sha1(key.encode('utf-8')).hexdigest()
```

The `+disabled` suffix from neutralized databases is stripped before hashing so that the hash still matches what the IAP server has on file for that token (the server stores the original hash without the suffix).

##### `get_credits(service_name)`

Returns the raw numeric credit balance for a service. Unlike `_get_account_information_from_iap()`, this does **not** update the record. Returns `-1` on any error (including `AccessError` from the RPC layer).

```python
@api.model
def get_credits(self, service_name):
    account = self.get(service_name, force_create=False)
    if not account:
        return 0
    credit = iap_jsonrpc('/iap/1/balance', params={...})
    return credit  # or -1 on error
```

Consumer modules use this for quick pre-flight checks ("do we have enough credits to proceed?") without persisting the result.

##### `get_config_account_url()`

Returns an internal Odoo URL to the IAP account form or list, depending on whether an account already exists. Used by the `partner_autocomplete` AJAX handler.

```python
@api.model
def get_config_account_url(self):
    account = self.env['iap.account'].get('partner_autocomplete')
    menu = self.env.ref('iap.iap_account_menu')
    if not self.env.user.has_group('base.group_no_one'):
        return False  # Only visible to technical users
    if account:
        return f"/odoo/action-iap.iap_account_action/{account.id}?menu_id={menu.id}"
    return f"/odoo/action-iap.iap_account_action?menu_id={menu.id}"
```

The `base.group_no_one` check restricts this URL to users with technical-access rights.

##### `action_buy_credits()`

Action button handler that opens the credit purchase portal in a new browser tab.

```python
def action_buy_credits(self):
    return {
        'type': 'ir.actions.act_url',
        'url': self.env['iap.account'].get_credits_url(
            account_token=self.sudo().account_token,
            service_name=self.service_name,
        ),
    }
```

Uses `sudo()` for the token read since `account_token` is group-restricted.

---

### `iap.service`

**Technical Name:** `iap.service`
**Description:** Registry of available IAP services. Acts as a master catalog; each service defines how its credits are denominated and displayed.

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | **Yes** | Display name shown in the UI (e.g., "Lead Generation") |
| `technical_name` | Char | **Yes** (readonly after create) | Unique identifier used in code and API calls (e.g., `reveal`, `partner_autocomplete`). Enforced unique via DB constraint. |
| `description` | Char | **Yes** | User-facing description, marked `translate=True` for i18n. |
| `unit_name` | Char | **Yes** | Balance unit name (e.g., `Credits`), marked `translate=True`. Included in the formatted `balance` string. |
| `integer_balance` | Boolean | **Yes** | If `True`, balance is rounded to an integer (`round(x, None)`); if `False`, rounded to 4 decimal places. Services with indivisible units (e.g., "SMS credits") should set this to `True`. |

#### Constraints

```python
_unique_technical_name = models.Constraint(
    'UNIQUE(technical_name)',
    'Only one service can exist with a specific technical_name',
)
```

Enforced at the PostgreSQL level. This prevents duplicate service definitions across modules.

#### Pre-loaded Service: `reveal`

Loaded via `data/services.xml` with `noupdate="1"` (won't be overwritten on upgrade):

| Property | Value |
|----------|-------|
| **technical_name** | `reveal` |
| **name** | `Lead Generation` |
| **description** | Get quality leads and opportunities: convert your website visitors into leads, generate leads based on a set of criteria and enrich the company data of your opportunities. |
| **unit_name** | `Credits` |
| **integer_balance** | `True` |

This service is defined in the `iap` module itself (rather than the CRM module) because multiple modules depend on it (CRM lead enrichment, website visitor tracking, etc.).

---

### `iap.enrich.api`

**Technical Name:** `iap.enrich.api`
**Description:** Abstract model providing lead/company enrichment via IAP Clearbit integration. Provides `_contact_iap()` and `_request_enrich()` helpers. CRM and other modules inherit from this to implement enrichment.

#### Key Methods

##### `_contact_iap(local_endpoint, params)`

Core RPC helper for enrichment calls. Injects authentication credentials and calls the enrichment endpoint.

```python
@api.model
def _contact_iap(self, local_endpoint, params):
    account = self.env['iap.account'].get('reveal')  # uses 'reveal' service
    dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
    params['account_token'] = account.sudo().account_token
    params['dbuuid'] = dbuuid
    base_url = self.env['ir.config_parameter'].sudo().get_param(
        'enrich.endpoint', self._DEFAULT_ENDPOINT  # https://iap-services.odoo.com
    )
    return iap_tools.iap_jsonrpc(base_url + local_endpoint, params=params, timeout=300)
```

- **`timeout=300`** — 5-minute timeout for enrichment requests. This is 20x longer than the default `iap_jsonrpc` timeout (15s), reflecting that enrichment operations can be slow (Clearbit lookups, multiple lead batches).
- **`enrich.endpoint`** — Configurable override via `ir.config_parameter`. Defaults to `https://iap-services.odoo.com` (distinct from the main IAP endpoint `https://iap.odoo.com`).
- The account is always fetched with `force_create=True` (default), so calling `_contact_iap` on a fresh database will create the `reveal` IAP account automatically.

##### `_request_enrich(lead_emails)`

Takes a dict of `{lead_id: email_address}` and calls the Clearbit enrichment endpoint.

```python
@api.model
def _request_enrich(self, lead_emails):
    params = {'domains': lead_emails}
    return self._contact_iap('/iap/clearbit/1/lead_enrichment_email', params=params)
```

**Return value:** A dict `{lead_id: company_data_dict}` where `company_data_dict` is `False` if no data was found for that email.

**Error handling:** `InsufficientCreditError` is raised directly from `iap_jsonrpc()` if the IAP server responds with that error type. The error payload includes:
```python
{
    "credit": 4.0,
    "service_name": "reveal",
    "base_url": "https://iap.odoo.com/iap/1/credit",
    "message": "You don't have enough credits on your account to use this service."
}
```

Consumer code should catch `InsufficientCreditError` and redirect the user to the credit purchase portal.

---

## RPC Layer: `iap_tools.py`

### `iap_jsonrpc(url, method='call', params=None, timeout=15)`

Core JSON-RPC 2.0 function used by all IAP communication.

```python
def iap_jsonrpc(url, method='call', params=None, timeout=15):
    payload = {
        'jsonrpc': '2.0',
        'method': method,
        'params': params,
        'id': uuid.uuid4().hex,
    }
    req = requests.post(url, json=payload, timeout=timeout)
    req.raise_for_status()
    response = req.json()
    if 'error' in response:
        name = response['error']['data'].get('name').rpartition('.')[-1]
        if name == 'InsufficientCreditError':
            raise InsufficientCreditError(response['error']['data'].get('message'))
        else:
            raise IAPServerError("An error occurred on the IAP server")
    return response.get('result')
```

**Error taxonomy:**

| Condition | Exception Type | User-Facing? |
|-----------|---------------|--------------|
| IAP server has insufficient credits | `InsufficientCreditError` (plain `Exception`) | Yes (consumer code catches and prompts to buy) |
| IAP server returns any other error | `IAPServerError` (plain `Exception`) | Yes (generic message) |
| HTTP timeout exceeded | `AccessError` | Yes ("request timed out") |
| HTTP network error | `AccessError` | Yes ("error reaching service") |
| Live server called during test | `AccessError` ("Unavailable during tests.") | N/A — test guard |

**Test guard:** The `modules.module.current_test` check prevents accidental live server calls during unit tests. This fires before any HTTP request is made.

**Timeout default:** 15 seconds. The enrichment endpoint override uses `timeout=300` (5 minutes).

### `iap_get_endpoint(env)`

Reads `ir.config_parameter` `iap.endpoint` with fallback to `https://iap.odoo.com`.

```python
def iap_get_endpoint(env):
    url = env['ir.config_parameter'].sudo().get_param('iap.endpoint', DEFAULT_ENDPOINT)
    return url
```

**L4 Note:** This is called with `sudo()` because `ir.config_parameter` is typically restricted to superuser write access. The `get()` method uses this to construct all account-info and balance URLs.

### `mail_prepare_for_domain_search(email, min_email_length=0)`

Normalizes an email and returns a domain-only search string for enrichment services.

```python
def mail_prepare_for_domain_search(email, min_email_length=0):
    email_tocheck = email_normalize(email, strict=False)
    email_domain = email_tocheck.rsplit('@', 1)[1]
    if email_domain not in _MAIL_DOMAIN_BLACKLIST:
        return '@' + email_domain  # Domain-wide search
    return email_tocheck           # Per-account search
```

**Blacklist logic:**
- Consumer email domains (gmail.com, hotmail.com, yahoo.com, outlook.com, etc. — 200+ entries) are blacklisted because searching by domain returns all employees at every Gmail/Outlook/etc. company, which is meaningless.
- `odoo.com` is also blacklisted (prevents enrichment of Odoo's own domain).
- `min_email_length` filter skips obviously fake/emtpy emails.

**Return values:**
- `bob@gmail.com` -> `bob@gmail.com` (returns full email; each Gmail account is treated independently)
- `john@acmecorp.com` -> `@acmecorp.com` (returns all employees at acmecorp.com)

### `_STATES_FILTER_COUNTRIES_WHITELIST`

Countries for which state/province filtering is available during lead mining requests. Used by `crm.iap.lead.mining.request` to build the state selector dropdown.

```python
_STATES_FILTER_COUNTRIES_WHITELIST = set(['AR', 'AU', 'BR', 'CA', 'IN', 'MY', 'MX', 'NZ', 'AE', 'US'])
```

This is a static set in `iap_tools.py` rather than a model field because it represents a hardcoded policy decision about which countries Clearbit supports state-level filtering for.

### Custom Exception Classes

```python
class InsufficientCreditError(Exception):
    pass  # Raised with a message string; .data holds the full server payload

class IAPServerError(Exception):
    pass  # Generic server error
```

Both inherit from `Exception` (not `odoo.exceptions.ValidationError` or similar), so consumer code must use plain `try/except` rather than Odoo's error catching mechanisms.

---

## Security Model

### Token Access Control

- `account_token` has `groups="base.group_system"` — only superusers (uid 2) or users with `base.group_system` can read it.
- The test `test_get_iap_account()` explicitly asserts that `user_demo` (regular user) gets `AccessError` on `account_token`, while `user_admin` (superuser context) can read it.
- All internal code uses `.sudo()` to read the token when constructing RPC payloads.

### Token in URLs (Hashed, Not Raw)

`get_credits_url()` sends a SHA-1 hash of the token, not the token itself:
```python
hashed_account_token = hashlib.sha1(account_token.encode('utf-8')).hexdigest()
```
The IAP server stores the same hash (computed from the original token at account creation) and compares hashes, not raw tokens. Even if a URL is intercepted, the raw token cannot be recovered from the hash.

### `+disabled` Suffix on Neutralized Databases

On a neutralized database (`database.is_neutralized = True`), `create()` appends `+disabled` to every new account token:
```python
account.account_token = f"{account.account_token.split('+')[0]}+disabled"
```
`_hash_iap_token()` strips the suffix before hashing, so the server's stored hash matches. However, the IAP server's comparison of the raw token (which it has stored from the create call) against a `+disabled` token fails, preventing any credit consumption.

### Record Rules

The `User IAP Account` rule on `iap.account` for `base.group_user`:
```
['|', ('company_ids', '=', False), ('company_ids', 'in', company_ids)]
```
- Global accounts (no `company_ids`) are visible to all users in all companies.
- Company-scoped accounts are only visible to users who belong to one of those companies.
- `unlink` is not permitted by either ACL (`access_client_iap_account_user` grants no `perm_unlink`).

### ACL Summary

| ACL | Model | Group | R | W | C | D |
|-----|-------|-------|---|---|---|---|
| `access_client_iap_account_manager` | `iap.account` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_client_iap_account_user` | `iap.account` | `base.group_user` | 1 | 0 | 1 | 0 |
| `access_iap_service_manager` | `iap.service` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_iap_service_user` | `iap.service` | `base.group_user` | 1 | 0 | 0 | 0 |

Key observations:
- Regular users (`base.group_user`) can **read** both models, **create** `iap.account` (to provision an account for a new service), but **cannot write or delete** `iap.account` and cannot write/create/delete `iap.service`.
- Only superusers (`base.group_system`) can manage services and fully manage accounts.
- The `web_save()` and `write()` methods run under the caller's user (not sudo), so regular users cannot modify `warning_threshold` or `warning_user_ids` — only view them.

### Timing Attack Prevention

Token comparison uses `secrets.compare_digest()` rather than `==`:
```python
accounts = self.filtered(lambda acc: secrets.compare_digest(acc.sudo().account_token, token))
```
This prevents an attacker who can measure response times from gradually inferring the token character by character.

---

## Performance Considerations

### Network Latency Per `web_read()`

Every `web_read()` on an `iap.account` triggers a synchronous HTTP POST to the IAP server. In a multi-account list view, all accounts are fetched in one batched call, but the latency is still incurred. If the IAP server is slow or unreachable, the form view load blocks for up to 15 seconds (default `iap_jsonrpc` timeout) before the silent failure kicks in.

Mitigations in the code:
- `timeout=15` caps the wait.
- Failure is non-fatal (logged warning; old balance preserved).
- `web_save()` sets `disable_iap_fetch=True` to prevent a second call after save.

### Cursor-Based Creation: Two Separate Transactions

`get()` uses two distinct `with self.pool.cursor() as cr:` blocks. Each creates a new database connection and transaction. This is intentional — it trades connection overhead for correctness:

- Block 1 (cleanup): If a prior request failed after `create()` but before `_get_account_information_from_iap()`, the account exists with no token. Deleting it in a separate cursor means the delete is committed independently of any future rollback in the main cursor.
- Block 2 (creation): If the new account immediately triggers a `NoCreditError`, the rollback only affects the creation cursor — the account record itself survives.

### Cache Injection After Separate-Cursor Create

```python
account_token = account.sudo().account_token  # read in creation cursor
account = self.browse(account.id)              # re-bind in caller's cursor
self.env.cache.set(account, IapAccount._fields['account_token'], account_token)
```

Without `cache.set()`, the next access to `account_token` in the caller's cursor would trigger a lazy SQL fetch, which would return `None` (the account was created in a different transaction and the caller's connection cannot see uncommitted rows). Pre-populating the cache avoids an extra SQL round-trip.

### Batch Balance Fetch

`_get_account_information_from_iap()` collects all account tokens in a single `iap_accounts` list and makes one RPC call, regardless of how many accounts are in `self`. The response is a dict keyed by token, matched back to records via `secrets.compare_digest()`. This avoids the N+1 RPC problem in list views.

---

## Edge Cases

### Concurrent `get()` Calls (Race Condition)

If two concurrent requests both call `get('reveal')` on a fresh database:
1. Both see no account.
2. Both attempt to create one in their own separate cursor.
3. PostgreSQL's row-level locking ensures only one succeeds.
4. The loser gets a unique constraint violation (if `account_token` were unique per service) or both succeed but with different tokens — which would be wrong.

However, since `technical_name` on `iap.service` is unique, and each service has exactly one canonical account, the actual uniqueness constraint should be on `(service_name, company_ids)` — but this is enforced by the `get()` logic (search + cleanup) rather than a DB constraint. Concurrent creates would result in duplicate `iap.account` rows for the same service. The cleanup phase in `get()` handles this on subsequent calls (deleting token-less accounts), but a window exists where duplicates can coexist. In practice this is rare and self-healing.

### Multi-Company: Account Priority

If a user belongs to companies A and B (via `res.users` `company_ids` field), and there exist:
- `account_X` scoped to company A
- `account_X` scoped to company B
- A global `account_X` (no `company_ids`)

`self.env.companies.ids` returns both A and B. The domain `('company_ids', 'in', [A, B])` matches both company-specific accounts. With `order='id desc'`, whichever has the higher ID wins. This is non-deterministic if both were created — the module assumes one canonical account per service.

### `InsufficientCreditError` Not Persisted

When the IAP server raises `InsufficientCreditError`, the exception payload includes `credit: 4.0` (the remaining balance), `service_name`, and a purchase URL. The error is raised as a plain `Exception` (not an `odoo.exceptions.UserError`), so:
- It does **not** automatically display a dialog.
- Consumer modules must explicitly catch it and call `raise UserError(...)` or redirect to the purchase URL.
- The `iap.account` `balance` field is **not** updated by the failed request (the balance fetch is a separate call).

### `email_normalize` Failure in `mail_prepare_for_domain_search`

If `email_normalize(email, strict=False)` returns `False` (invalid email format), the code falls back to `email.casefold()`. If the resulting domain is in the blacklist, the full email is returned (which is correct for consumer domains). If not in the blacklist and the domain extraction fails (no `@`), the full lowercase email is returned — which may still contain no useful domain.

### `integer_balance` and Decimal Precision

```python
balance_amount = round(information['balance'], None if account.service_id.integer_balance else 4)
```
`round(x, None)` in Python 3 uses banker's rounding (round half to even). For financial services this could cause off-by-0.5 credit discrepancies on odd balances ending in `.5`. The IAP server likely sends the raw float, so this client-side rounding is a display choice, not authoritative.

---

## Frontend: `iap_buy_more_credits` Widget

Registered as a view widget in the `view_widgets` category. Used by consumer modules to embed "Buy More Credits" buttons.

**OWL Component:** `IAPActionButtonsWidget`
**Template:** `iap.ActionButtonsWidget`
**Registry name:** `iap_buy_more_credits`

**Props:**
- `serviceName` (String) — from `attrs.service_name`
- `showServiceButtons` (Boolean) — false if `attrs.hide_service` is set

**Behavior:**
- `onViewServicesClicked()` — calls `ir.actions.act_window` for `iap.iap_account_action` (the IAP account list)
- `onManageServiceLinkClicked()` — calls `iap.account.get_account_id` via ORM, then opens the specific account form

The widget uses `orm.silent.call()` for `get_account_id` to suppress any access errors if the account doesn't exist yet (returns `False` in that case, and the fallback URL in `get_config_account_url` handles the redirect).

---

## IAP Server RPC Endpoints

| Endpoint | Method | Direction | Purpose |
|----------|--------|-----------|---------|
| `/iap/1/get-accounts-information` | JSON-RPC POST | Odoo -> IAP | Batch-fetch balance, warning_threshold, state for multiple accounts |
| `/iap/1/update-warning-email-alerts` | JSON-RPC POST | Odoo -> IAP | Push alert threshold and recipient email list to server |
| `/iap/1/balance` | JSON-RPC POST | Odoo -> IAP | Get raw credit number for one service (used by `get_credits()`) |
| `/iap/1/credit` | HTTP GET | Odoo -> Browser | Credit purchase portal (URL with hashed token auth) |
| `/iap/clearbit/1/lead_enrichment_email` | JSON-RPC POST | Odoo -> IAP (Clearbit) | Enrich leads with company data |
| `https://iap-services.odoo.com` | Base URL | — | Separate endpoint for enrichment (via `enrich.endpoint` param) |

---

## Context Variables

| Key | Set By | Consumed By | Purpose |
|-----|--------|-------------|---------|
| `disable_iap_fetch` | `web_save()`, `_get_account_information_from_iap()` | `web_read()` | Skip IAP server balance fetch |
| `disable_iap_update` | `_get_account_information_from_iap()` | `write()` | Skip alert-threshold push to IAP server |
| `enrich.endpoint` | Config param | `_contact_iap()` | Override enrichment service base URL |

---

## Consumer Module Extension Pattern

Consumer apps (CRM, partner_autocomplete, snailmail, etc.) should follow this pattern:

```python
from odoo.addons.iap.tools import iap_tools

def _do_enrichment(self, lead):
    try:
        result = iap_tools.iap_jsonrpc(
            'https://iap-services.odoo.com/iap/clearbit/1/lead_enrichment_email',
            params={
                'account_token': self.env['iap.account'].get('reveal').sudo().account_token,
                'dbuuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
                'domains': {lead.id: lead.email},
            },
            timeout=300,
        )
    except iap_tools.InsufficientCreditError as e:
        # e.data contains {credit, service_name, base_url, message}
        lead._notify_insufficient_credits(
            service_name=e.data['service_name'],
            purchase_url=e.data['base_url'],
        )
    except iap_tools.IAPServerError:
        raise UserError("Enrichment service unavailable. Please try again later.")
```

Or by inheriting `iap.enrich.api`:
```python
class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _ Enrich_with_iap(self):
        self.ensure_one()
        enrich_api = self.env['iap.enrich.api']
        result = enrich_api._request_enrich({self.id: self.email})
        if result.get(self.id):
            self.write(result[self.id])
```

---

## Related

- [Modules/CRM](CRM.md) — inherits `iap.enrich.api` for lead enrichment
- [Modules/partner_autocomplete](partner_autocomplete.md) — uses IAP for company/contact lookup
- [Modules/snailmail](snailmail.md) — uses IAP for postal service credits
- [Core/API](API.md) — `@api.model`, `@api.constrains`, `@api.model_create_multi` patterns
- [Tools/ORM Operations](ORM Operations.md) — `search()`, `browse()`, `write()` behavior
- [Patterns/Security Patterns](Security Patterns.md) — ACL CSV, `ir.rule` design
