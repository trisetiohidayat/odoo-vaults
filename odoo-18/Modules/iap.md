---
Module: iap
Version: Odoo 18
Type: Core
Tags: [iap,in_app_purchase,credits,JSON-RPC,authorization,capture,charge]
Description: In-App Purchase base module — iap.account, iap.service, iap.enrich.api, credit authorize/capture/cancel pattern, endpoint configuration.
See Also: [mail_plugin](mail_plugin.md), [Modules/crm_iap_enrich](Modules/crm_iap_enrich.md), [Modules/crm_mail_plugin](Modules/crm_mail_plugin.md)
---

# iap — In-App Purchase / IAP Service Base

> **Source:** `~/odoo/odoo18/odoo/addons/iap/`
> **Depends:** `web`, `base_setup`
> **Category:** Hidden/Tools
> **Auto-install:** True (installed by default with all Odoo editions)

The `iap` module is the foundation for all pay-per-use Odoo services (lead enrichment, SMS, VAT validation, etc.). It defines:
- **`iap.service`** — service metadata (name, technical key, unit name)
- **`iap.account`** — per-service account with balance, tokens, and notification settings
- **`iap.enrich.api`** — abstract API client for the enrichment service
- **`iap.tools`** — the JSON-RPC client, authorize/capture/cancel transaction helpers, domain blacklist, and `InsufficientCreditError`

---

## Architecture

```
iap.service (master data)
  └── technical_name (unique), name, description, unit_name, integer_balance
       │
       └── iap.account (per-company service account)
            ├── account_token (UUID, auth key for IAP server)
            ├── balance (char, fetched live from IAP server)
            ├── state (banned/registered/unregistered)
            ├── company_ids (multi-company scoping)
            └── warning_user_ids (credit threshold notification recipients)

iap.enrich.api (abstract model)
  └── _contact_iap() → iap_jsonrpc() → iap.odoo.com endpoints

iap.tools (iap_tools.py)
  ├── iap_jsonrpc(url, params) → server-side JSON-RPC
  ├── iap_authorize(env, key, token, credit) → transaction_token
  ├── iap_capture(env, transaction_token, key, credit)
  ├── iap_cancel(env, transaction_token, key)
  └── iap_charge(env, key, token, credit) → context manager (autoretry)
```

---

## Model: `iap.service` — Service Registry

**File:** `models/iap_service.py`

Master data defining what IAP services exist. Service records are created via XML data (`data/services.xml`).

### Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Display name, translateable (e.g. `"Lead Generation"`) |
| `technical_name` | Char | Unique key used in code (e.g. `"reveal"`), readonly after creation |
| `description` | Char | User-facing description, translateable |
| `unit_name` | Char | Unit label (e.g. `"Credits"`), translateable |
| `integer_balance` | Boolean | If True, balance is rounded to integer; if False, 4 decimal places |

### SQL Constraints

`UNIQUE(technical_name)` — only one service per technical name.

### Demo Data (`data/services.xml`)

```xml
<record id="iap_service_reveal" model="iap.service">
    <field name="name">Lead Generation</field>
    <field name="technical_name">reveal</field>
    <field name="description">Get quality leads and opportunities...</field>
    <field name="unit_name">Credits</field>
    <field name="integer_balance">True</field>
</record>
```

L4: The `reveal` service powers the CRM lead enrichment (`crm_iap_enrich`). Other services (SMS, mail, etc.) have their own dedicated addon modules that each define their own `iap.service` record.

---

## Model: `iap.account` — Service Account

**File:** `models/iap_account.py`

Per-service account that authenticates to the IAP server and stores live balance.

### Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Account name (defaults to service_id.name on create) |
| `service_id` | Many2one(iap.service) | Required — the service this account is for |
| `service_name` | Char | Related → `service_id.technical_name` (read-only) |
| `service_locked` | Boolean | If True, the service cannot be changed (set True when IAP confirms account exists) |
| `description` | Char | Related → `service_id.description` |
| `account_token` | Char | UUID hex (43 chars) — authentication key to IAP server, generated on creation |
| `company_ids` | Many2many(res.company) | Scoping: if set, account only used when current company is in this list; if empty, used for all companies |
| `balance` | Char | Live balance string, e.g. `"42.0 Credits"`, fetched from IAP server on `web_read()` |
| `warning_threshold` | Float | Credit level below which alert email is sent |
| `warning_user_ids` | Many2many(res.users) | Recipients of the credit threshold alert email |
| `state` | Selection | `'banned'` / `'registered'` / `'unregistered'` — fetched from IAP server |

### Key Methods

#### `get(service_name, force_create=True)` — Singleton Resolution

```python
@api.model
def get(self, service_name, force_create=True):
    """
    Returns the iap.account for a service, creating one if needed.
    Algorithm:
      1. Search accounts for service_name + current company (or no-company)
      2. Remove accounts without account_token (cleanup race condition)
      3. If found: prefer accounts with company_ids set
      4. If not found: create new account via iap.server (separate cursor to avoid rollback)
    force_create=False: return empty recordset instead of creating.
    Cursor pattern: uses pool.cursor() to create in separate transaction,
    avoiding rollback of the calling transaction on IAP errors.
    """
```

L4: The separate-cursor pattern is critical. If IAP service call fails after account creation, a rollback in the main cursor would undo the new account — but since the account is created in a separate SQL cursor, it persists.

#### `_get_account_information_from_iap()` — Live Balance Fetch

```python
def _get_account_information_from_iap(self):
    """
    Called on every web_read() unless context 'disable_iap_fetch' is set.
    Makes JSON-RPC to /iap/1/get-accounts-information with:
      {iap_accounts: [{token, service}, ...], dbuuid: <db_uuid>}
    For each account:
      - Rounds balance (4dp or integer based on service_id.integer_balance)
      - Formats balance string: "42.0 Credits"
      - Writes: balance, warning_threshold, state, service_locked=True
    AccessError on RPC → logged, not raised (graceful degradation).
    Skipped during tests (is_running_test_suite() check).
    """
```

#### `write()` — Alert Configuration Sync

```python
def write(self, values):
    # On change to warning_threshold or warning_user_ids:
    # POST /iap/1/update-warning-email-alerts with account_token,
    # threshold, and warning_emails [{email, lang_code}, ...]
    # AccessError on RPC → logged, not raised.
```

#### `get_credits_url(service_name)` — Purchase Credits Link

```python
@api.model
def get_credits_url(self, service_name, base_url='', credit=0, trial=False, account_token=False):
    """
    Builds URL: https://iap.odoo.com/iap/1/credit?dbuuid=...&service_name=...&account_token=...&credit=...
    Used by: buy-more widget, partner_autocomplete error handler,
    ajax crash manager, crm_iap_enrich.
    """
```

#### `get_credits(service_name)` — Real-time Credit Check

```python
@api.model
def get_credits(self, service_name):
    """
    Calls /iap/1/balance with {dbuuid, account_token, service_name}.
    Returns: credit amount (int) or -1 on error.
    Used by iap.enrich.api to check if enrichment is possible.
    """
```

---

## Model: `iap.enrich.api` — Enrichment API Client

**File:** `models/iap_enrich_api.py`

Abstract model providing the enrichment service bridge.

### Constants

`DEFAULT_ENDPOINT = 'https://iap-services.odoo.com'`

L4: This is a different endpoint from the generic `iap.odoo.com` used for account management. Enrichment uses `iap-services.odoo.com` (Clearbit-powered).

### Fields

None — pure abstract model with method-only API.

### Methods

```python
@api.model
def _contact_iap(self, local_endpoint, params):
    """
    1. Get iap.account for 'reveal' service
    2. Add account_token and dbuuid to params
    3. Read endpoint from ir.config_parameter 'enrich.endpoint'
       (falls back to self._DEFAULT_ENDPOINT = 'https://iap-services.odoo.com')
    4. iap_jsonrpc(endpoint + local_endpoint, params, timeout=300)
    """
```

```python
@api.model
def _request_enrich(self, lead_emails):
    """
    Params: {domain: domain} (key doesn't matter, value is the domain string)
    Calls: _contact_iap('/iap/clearbit/1/lead_enrichment_email', params)
    Raises: InsufficientCreditError (from iap_jsonrpc error response)
    Returns: dict {domain: enrichment_data} or enrichment_data
    enrichment_data keys: name, domain, logo, phone_numbers, email,
                          street_name, city, postal_code, country_code, state_code
    """
```

---

## `iap.tools` — JSON-RPC Client and Transaction Helpers

**File:** `tools/iap_tools.py`

### `iap_jsonrpc(url, params, method='call', timeout=15)`

```python
def iap_jsonrpc(url, method='call', params=None, timeout=15):
    """
    Sends JSON-RPC 2.0 request to IAP server.
    Payload: {jsonrpc: '2.0', method, params, id: uuid}
    Raises:
      - InsufficientCreditError: if error data name == 'InsufficientCreditError'
        (error.data contains credit, service_name, base_url, message)
      - IAPServerError: for other server-side errors
      - AccessError: for network/timeout errors
    Skipped during tests (raises AccessError "Unavailable during tests").
    """
```

### Authorization Pattern (Three-Phase Commit)

```
PHASE 1: AUTHORIZE — Hold credit
  iap_authorize(env, key, account_token, credit, ttl=4320h)
  → POST /iap/1/authorize
  → Returns transaction_token
  → Credit is held but NOT yet deducted

PHASE 2: CHARGE (within iap_charge context manager)
  try:
      with iap_charge(env, key, token, credit):
          do_work()  ← actual service call goes here
          iap_capture(env, transaction_token, key, credit)
  except Exception:
      iap_cancel(env, transaction_token, key)  ← release hold
  else:
      iap_capture()  ← finalize deduction
```

### `iap_charge()` — Context Manager

```python
@contextlib.contextmanager
def iap_charge(env, key, account_token, credit, dbuuid=False,
               description=None, credit_template=None, ttl=4320):
    """
    Full authorize → try/capture or cancel pattern:
      transaction_token = iap_authorize(...)
      try:
          transaction = IapTransaction()
          transaction.credit = credit
          yield transaction
      except Exception as e:
          iap_cancel(env, transaction_token, key)
          raise e
      else:
          iap_capture(env, transaction_token, key, transaction.credit)
    credit_template: QWeb template rendered and included in InsufficientCreditError
    description: shown in user's IAP dashboard
    """
```

### `iap_authorize()` / `iap_capture()` / `iap_cancel()`

```python
def iap_authorize(env, key, account_token, credit, dbuuid=False,
                  description=None, credit_template=None, ttl=4320):
    """POST /iap/1/authorize. Returns transaction_token."""

def iap_capture(env, transaction_token, key, credit):
    """POST /iap/1/capture with credit_to_capture."""

def iap_cancel(env, transaction_token, key):
    """POST /iap/1/cancel."""
```

---

## Configuration Parameters

| Parameter | Default | Description |
|---|---|---|
| `iap.endpoint` | `https://iap.odoo.com` | Generic IAP endpoint for account management |
| `enrich.endpoint` | `https://iap-services.odoo.com` | Clearbit enrichment endpoint |
| `database.uuid` | — | Unique DB identifier, sent with all IAP requests |
| `mail.session.batch.size` | `500` | Max emails per batch in mail_group |

All accessed via `env['ir.config_parameter'].sudo().get_param(...)`.

---

## `InsufficientCreditError` Handling Pattern

```python
from odoo.addons.iap.tools import iap_tools

try:
    response = iap_jsonrpc(url, params)
except iap_tools.InsufficientCreditError as e:
    credits_url = iap.account.get_credits_url('reveal')
    # Show buy credits button in UI
    return {'enrichment_info': {'type': 'insufficient_credit', 'info': credits_url}}
```

The error data contains: `credit`, `service_name`, `base_url`, `message`.

---

## Domain Blacklist (`_MAIL_DOMAIN_BLACKLIST`)

`iap_tools.py` maintains a hardcoded blacklist of 200+ consumer email domains (`gmail.com`, `outlook.com`, etc.) plus `'odoo.com'`. Used by `mail_plugin._get_iap_search_term()` to decide whether to search by domain or full email address.

L4: Searching by domain for consumer providers would match millions of contacts. The blacklist forces full-email search for personal addresses.

---

## L4: Credit Consumption Flow (Example: CRM Enrichment)

```
1. User clicks "Enrich" on a CRM lead
2. crm.lead → action_enrich() → iap.enrich.api._request_enrich({lead_id: email})
3. _request_enrich() → _contact_iap('/iap/clearbit/1/lead_enrichment_email', params)
4. Inside _contact_iap():
   a. iap.account.get('reveal') → account_token
   b. iap_jsonrpc(endpoint + local_endpoint, params, timeout=300)
5. IAP server validates account_token, checks credit balance
6. If insufficient: raises InsufficientCreditError → caught and returned as enrichment_info
7. If sufficient:
   a. Server deducts credit (authorizes)
   b. Returns enrichment data (name, logo, phone, etc.)
   c. Odoo creates res.partner.iap record
   d. Post chatter message on lead with enrichment results
   e. IAP server captures the credit
```

---

## Security

- `iap.account` creation is protected by `base.group_system` (inherited from the IAP menu access)
- `account_token` is auto-generated UUID — must never be exposed in logs at DEBUG level
- Database neutralization: `if ir_config_parameter 'database.is_neutralized': account_token += '+disabled'` (prevents accidental IAP calls from copy/clone databases)
- API key stored as plain text in `iap.account.account_token`; IAP server validates using its own copy
- `res.config.settings` view for IAP configuration (endpoint override possible for on-premise/air-gapped deployments)

---

## SQL Constraints

| Model | Constraint | Meaning |
|---|---|---|
| `iap.service` | `unique_technical_name` | One service per technical name |
| `iap.account` | No explicit SQL constraint | Company scoping handled via domain search |