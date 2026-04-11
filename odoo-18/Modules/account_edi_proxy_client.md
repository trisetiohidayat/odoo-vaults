---
Module: account_edi_proxy_client
Version: 18.0
Type: addon
Tags: #account, #edi, #proxy, #peppol
---

# account_edi_proxy_client — EDI Proxy Client

Central authentication and proxy infrastructure for EDI formats (Peppol, etc.). Provides a secure tunnel between Odoo databases and external EDI services via a proxy server.

**Depends:** `account`, `certificate`

**Source path:** `~/odoo/odoo18/odoo/addons/account_edi_proxy_client/`

## Architecture

This module defines the `account_edi_proxy_client.user` model that acts as a proxy between Odoo and external EDI networks. It handles RSA key pair generation, token refresh, request signing, and data encryption/decryption. Each EDI format (e.g., Peppol) extends this module to implement format-specific registration.

## Key Classes

### `AccountEdiProxyClientUser` — `account_edi_proxy_client.user`

**File:** `models/account_edi_proxy_user.py` (lines 26-235)

Fields:
- `active` — Boolean (line 36)
- `id_client` — Char, required, unique (line 37)
- `company_id` — Many2one `res.company`, required (line 38-39)
- `edi_identification` — Char, required; the unique ID for this user in the EDI network (e.g., Peppol VAT ID) (line 40)
- `private_key_id` — Many2one `certificate.key`, domain `public=False` (lines 41-47)
- `refresh_token` — Char, `groups='base.group_system'` (line 48)
- `proxy_type` — Selection, required; extended by format-specific modules (line 49)
- `edi_mode` — Selection `[('prod','Production'), ('test','Test'), ('demo','Demo')]` (lines 50-57)

SQL Constraints:
- `unique_id_client` (line 60)
- `unique_active_edi_identification` (line 61) — partial unique index via `_auto_init` (lines 67-72)
- `unique_active_company_proxy` (line 62) — partial unique index via `_auto_init` (lines 73-78)

Key methods:
- `_get_proxy_urls()` (line 80-82) — Returns `{proxy_type: {edi_mode: url}}` dict; overridden per format
- `_get_server_url()` (line 84-89) — looks up URL from `_get_proxy_urls()`
- `_get_proxy_users()` (line 91-94) — returns active users for company + proxy_type
- `_get_proxy_identification()` (line 96-102) — Returns identifying key; `TO OVERRIDE` (returns False by default)
- `_make_request()` (line 104-154) — HTTP POST via `requests` library; handles `refresh_token_expired` auto-renewal, `no_such_user` deactivation, `invalid_signature` error (lines 138-151)
- `_get_iap_params()` (line 156-165) — builds payload with `dbuuid`, `company_id`, `edi_identification`, public key, proxy_type
- `_register_proxy_user()` (line 167-205) — generates RSA key pair, calls server `create_user` endpoint, creates the user record
- `_renew_token()` (line 207-225) — acquires new refresh token via proxy; uses `FOR UPDATE NOWAIT` lock to prevent concurrent renewal
- `_decrypt_data()` (line 227-235) — decrypts symmetric-key-encrypted data using the user's private RSA key

### `AccountEdiProxyError`

Exception class at line 18-23; wraps error `code` and `message`.

### `ResCompany` (extends)

**File:** `models/res_company.py` — adds `account_edi_proxy_client_ids` One2many field.

### `Key`

**File:** `models/key.py` — `certificate.key` model extended with `_account_edi_fernet_decrypt` class method.

### `AccountEdiProxyAuth`

**File:** `models/account_edi_proxy_auth.py` — HTTP Basic auth using `user` + `user.sudo().refresh_token`.

## Token Refresh Flow

The proxy uses 24-hour refresh tokens. When `refresh_token_expired` is returned, `_renew_token()` is called automatically inside `_make_request()`. Uses `FOR UPDATE NOWAIT` (line 216) to prevent race conditions across workers.

## Security

- RSA key pairs are generated per-company, per-format, per-mode
- All proxy requests signed with private key
- `demo` mode blocks actual network access
- `id_client` uniqueness enforced via SQL constraint
