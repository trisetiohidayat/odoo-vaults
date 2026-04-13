---
tags: [#odoo, #odoo19, #edi, #peppol, #e-invoice, #proxy, #security, #modules]
modLevel: L4
module: account_edi_proxy_client
category: Accounting/Accounting
depends: [account, certificate]
license: LGPL-3
---

# Account EDI Proxy Client

**Module:** `account_edi_proxy_client`
**Manifest version:** 1.0 (Odoo 19)
**Author:** Odoo S.A.
**Category:** Accounting/Accounting
**Depends:** `account`, `certificate`
**License:** LGPL-3
**Post-init hook:** `_create_demo_config_param` (sets `account_edi_proxy_client.demo` param to `'demo'`)

**Source path:** `~/odoo/odoo19/odoo/addons/account_edi_proxy_client/`

---

## L1: account_edi_proxy_client.user, ir.config_parameter Extensions — How Odoo Acts as EDI Proxy

### Overview

`account_edi_proxy_client` is a **generic infrastructure module** that registers an Odoo database as a proxy user on an external EDI relay server. It is the shared foundation for country-specific EDI modules — most notably `account_peppol` (PEPPOL network) and `l10n_it_edi` (Italian SDI). This module does not implement any EDI format logic; it provides the cryptographic identity, authentication handshake, and document decryption layer that all EDI formats depend on.

### The Proxy Architecture

Traditional EDI requires companies to either maintain a static IP endpoint or use a VAN (Value-Added Network). The proxy architecture solves this by making **all connections outbound from Odoo** — Odoo initiates HTTPS requests to the proxy, and the proxy routes inbound documents. This eliminates the need for inbound firewall rules.

```
Counterparty's          Odoo Proxy              Odoo Database
EDI System               Server                   (this module)
     │                     │                           │
     │  sends invoice      │                           │
     │  addressed to       │                           │
     │  vendor's Peppol ID │                           │
     │────────────────────►│                           │
     │                     │  POST /iap/.../recv       │
     │                     │──────────────────────────►│
     │                     │                           │  _decrypt_data()
     │                     │                           │  (RSA + Fernet)
     │                     │◄──────────────────────────│
     │                     │  decrypted document       │
     │                     │  forwarded to Odoo         │
     │                     │                           │
     │                     │  POST /iap/.../ack        │
     │                     │◄──────────────────────────│
     │  acknowledgement    │                           │
     │◄────────────────────│                           │
```

Odoo polls the proxy at regular intervals (via scheduled cron actions in consuming modules) to retrieve new inbound documents. The proxy holds documents until Odoo fetches them, providing a queue that survives brief Odoo downtime.

### Two Roles in the System

**1. Odoo as sender** — Odoo encrypts an outbound document with the receiver's public key and POSTs it to the proxy. The proxy routes it to the receiver.

**2. Odoo as receiver** — The proxy receives a document addressed to this company's Peppol ID (edi_identification), encrypts it with this company's public key, and holds it. Odoo polls and fetches it, then decrypts using its private key.

Both directions use the same `account_edi_proxy_client.user` record.

### What the ir.config_parameter Extension Does

The post-init hook `_create_demo_config_param` sets `account_edi_proxy_client.demo = 'demo'`. This config parameter is read by consuming modules (e.g., `account_peppol`) to detect whether the proxy is in demo mode and adapt UI accordingly. It has no effect on the proxy client's behavior itself.

---

## L2: Field Types, Defaults, Constraints — id_client, proxy_company_id, active

### `account_edi_proxy_client.user` — Complete Field Reference

| Field | Odoo Type | Required | Default | Groups | Description |
|-------|-----------|----------|---------|--------|-------------|
| `active` | `Boolean` | No | `True` | — | Soft-delete flag. When proxy returns `no_such_user`, the record is soft-deactivated (`sudo().active = False`). Inactive records are excluded from uniqueness constraints, allowing deactivation + re-registration without deletion. |
| `id_client` | `Char` | **Yes** | — | — | Opaque unique identifier assigned by the proxy server at registration. Not user-settable. Used in every HTTP header (`odoo-edi-client-id`) to identify the caller. Globally unique across all Odoo databases. |
| `company_id` | `Many2one(res.company)` | **Yes** | `self.env.company` | — | The company this proxy user belongs to. **Indexed.** Enforced unique per `(company_id, proxy_type, edi_mode)` when `active=True`. |
| `edi_identification` | `Char` | **Yes** | — | — | The business identifier used to route documents to this user on the proxy — typically a VAT number for Peppol, C.F./P.IVA for Italian SDI. Must be unique per proxy type within the proxy's namespace. Set by the consuming module via `_get_proxy_identification()`. |
| `private_key_id` | `Many2one(certificate.key)` | **Yes** | — | — | RSA private key for decrypting inbound documents. **Domain filter: `public = False`** — only private keys are valid. The matching public key was transmitted to the proxy at registration. All inbound documents are encrypted with this public key. |
| `refresh_token` | `Char` | No | — | `base.group_system` | HMAC secret for signing outbound requests. Generated by the proxy at registration; expires after 24 hours. Field-level group restriction means invoice-level users cannot see the raw token even if they have read ACL on the record. |
| `is_token_out_of_sync` | `Boolean` | No | `False` | — | **Odoo 19 field.** Flag indicating the local `refresh_token` has diverged from the proxy's copy — e.g., after database duplication without neutralization, or after a backup restore overwrites one copy. Consuming modules use this to detect the need for re-registration. |
| `token_sync_version` | `Integer` | No | — | — | **Odoo 19 field.** Monotonically increasing version counter for token sync state. Allows consuming modules to detect and reconcile stale token state without full re-registration. |
| `proxy_type` | `Selection(selection=[])` | **Yes** | — | — | Identifies the EDI format. **The selection list is empty by default** — it is populated by extending modules (e.g., `account_peppol` adds `('peppol', 'PEPPOL')`). This is the routing key on the proxy. |
| `edi_mode` | `Selection` | No | — | — | Operating mode: `prod` (live), `test` (sandbox), `demo` (simulated, no real network). `_make_request` **blocks all outbound requests in demo mode** — raises `AccountEdiProxyError("block_demo_mode")`. |

### Constraints

```python
_unique_id_client = models.Constraint(
    'unique(id_client)',
    "This id_client is already used on another user."
)
_unique_active_company_proxy = models.UniqueIndex(
    "(company_id, proxy_type, edi_mode) WHERE (active IS TRUE)",
    "This company has an active user already created for this EDI type"
)
```

- **`id_client` global uniqueness** — Each proxy-assigned ID is globally unique across all databases. If the same `id_client` appears in two databases, the proxy will reject the second one.
- **Active-user uniqueness per company/type/mode** — A company cannot have two active proxy users for the same format and mode simultaneously. This prevents accidental dual registration. The partial unique index (WHERE active IS TRUE) excludes inactive records, allowing deactivation + re-registration as a recovery path.

### `res.company` Extension

```python
account_edi_proxy_client_ids = fields.One2many(
    'account_edi_proxy_client.user',
    inverse_name='company_id',
    context={'active_test': True}  # Default domain excludes inactive users
)
```

The `active_test` context means list views on the company form exclude inactive proxy users by default, providing a cleaner UX. The reverse many2one allows company-level search for all proxy users.

### Default Values

| Field | Default | Source |
|-------|---------|--------|
| `company_id` | `self.env.company` | Lambda on field definition |
| `active` | `True` | Implicit Boolean default |
| `is_token_out_of_sync` | `False` | Implicit Boolean default |
| `proxy_type` | Required, no default | Must be set by extending module |
| `edi_identification` | Required, no default | Must be set by `_get_proxy_identification()` |
| `private_key_id` | Required, no default | Generated during `_register_proxy_user()` |

---

## L3: Cross-Model (EDI ↔ Proxy), Override Patterns, Workflow Triggers, Failure Modes

### Cross-Model: EDI Format ↔ Proxy Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     account_peppol / l10n_it_edi                        │
│  Extends:                                                               │
│    - proxy_type selection: ('peppol', 'PEPPOL') / ('l10n_it', 'IT')    │
│    - _get_proxy_urls(): returns {proxy_type: {edi_mode: url}}           │
│    - _get_proxy_identification(): returns company.vat                   │
│    - _register_proxy_user(): called during onboarding wizard            │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ inherits / calls
┌──────────────────────────▼──────────────────────────────────────────────┐
│                  account_edi_proxy_client.user                           │
│  Fields: id_client, refresh_token, private_key_id, edi_identification │
│  Methods:                                                               │
│    - _register_proxy_user() → creates record + RSA key                  │
│    - _make_request() → HTTP with HMAC/RSA auth headers                  │
│    - _renew_token() → 24h token rotation with lock_for_update()         │
│    - _decrypt_data() → RSA-OAEP + Fernet hybrid decryption              │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────┐
│                     certificate.key                                      │
│  (from module: certificate)                                              │
│  _generate_rsa_private_key() → creates key record                      │
│  _decrypt() → RSA-OAEP decryption                                       │
│  _sign() → RSA-SSA-PKCS1-v1_5 signing                                   │
│  _get_public_key_bytes() → PEM-encoded public key for registration    │
│  _account_edi_fernet_decrypt() → Fernet symmetric decryption           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Override Pattern: Consuming Modules

Each EDI format module (Peppol, Italian SDI, etc.) extends `account_edi_proxy_client.user` by:

1. **Adding to `proxy_type` selection** — defining their format code. This is done by overriding the field definition with an extended `selection` attribute. In Odoo, `Selection` fields in `_inherit` models can be extended by appending to the selection list in the child module.

2. **Implementing `_get_proxy_urls()`** — returning the proxy endpoint URLs for each `(proxy_type, edi_mode)` combination. This is the key extension point — without it, `_get_server_url()` raises `KeyError`.

3. **Implementing `_get_proxy_identification()`** — returning the business identifier (VAT for Peppol, C.F. for Italian SDI). Raises `UserError` if the field is not configured.

4. **Calling `_register_proxy_user()`** — during the onboarding wizard, after the user has configured their identification and accepted terms.

### Workflow Trigger: EDI Message Routing Through Proxy

**Outbound flow** (Odoo sends a document):
```
User clicks "Send" on a Peppol invoice
        │
        ▼
account_peppol.models.account_move._send_to_peppol()
        │
        │ (1) Fetch active proxy user for this company
        │ proxy_users = account_edi_proxy_client.user._get_proxy_users(company, 'peppol')
        │
        │ (2) Encrypt document
        │ symmetric_key = Fernet.generate_key()
        │ encrypted_data = Fernet(symmetric_key).encrypt(document)
        │ encrypted_key = proxy_user.company_id.partner_id.public_key.encrypt(symmetric_key)
        │
        │ (3) POST to proxy
        │ proxy_user._make_request(
        │     f'{server_url}/iap/account_edi/2/send_document',
        │     params={
        │         'receiver_id': recipient_peppol_id,
        │         'document': base64(encrypted_data),
        │         'symmetric_key': base64(encrypted_key),
        │     }
        │ )
        │
        ▼
proxy server routes to recipient's SMP (Service Metadata Publisher)
        │
        ▼
recipient's EDI system receives the invoice
```

**Inbound flow** (Odoo receives a document):
```
Proxy receives document addressed to this company's Peppol ID
        │
        ▼
Odoo cron job: account_peppol.models.account_edi_proxy_client._fetch_new_documents()
        │
        │ proxy_user._make_request(f'{server_url}/iap/account_edi/1/get_messages')
        │
        ▼
proxy returns list of {id, document, symmetric_key, metadata}
        │
        │ for each document:
        │   proxy_user._decrypt_data(document, symmetric_key)
        │   → RSA-OAEP decrypt symmetric_key
        │   → Fernet decrypt document
        │
        ▼
decrypted XML parsed and processed by account_peppol
        │
        ▼
account.move created (in_invoice or out_invoice)
        │
        ▼
proxy_user._make_request(f'{server_url}/iap/account_edi/1/ack_messages', {ids: [...]})
        │ (acknowledge to proxy so document is not re-fetched)
        │
        ▼
proxy marks document as delivered
```

### Failure Mode Analysis

| Failure | Proxy error code | Odoo response | Recovery |
|---------|-----------------|---------------|----------|
| **Refresh token expired** | `refresh_token_expired` | `_renew_token()` + `cr.commit()` + retry with `auth_type='hmac'` | Automatic. On retry, uses the new token. |
| **Token renewal race (cron)** | N/A | `lock_for_update()` serializes; second caller returns early | Automatic. Only first requester calls the proxy. |
| **Invalid signature after renewal** | `invalid_signature` | Raises `AccountEdiProxyError` with user-facing message about DB duplication | User must re-register. `is_token_out_of_sync` set by proxy. |
| **no_such_user** | `no_such_user` | Soft-deactivates record (`sudo().active = False`) | User must re-register. |
| **Connection error** | — | `_make_request` catches `requests.exceptions.*` and raises `AccountEdiProxyError('connection_error')` | Network-level; Odoo retries on next cron run. |
| **Proxy returns proxy_error** | Any other code | Raises `AccountEdiProxyError(code, message)` | Depends on error type; generally requires manual intervention. |
| **Demo mode** | N/A | `_make_request` raises `AccountEdiProxyError("block_demo_mode")` before any network call | Expected. Registration in demo mode simulates response locally. |
| **Clock skew** | `invalid_signature` (indirect) | Timestamp is part of signed message; proxy rejects stale timestamps | Sync system clock. |
| **Private key deleted** | — | `_decrypt_data()` fails with `AttributeError` on `private_key_id._decrypt()` | Cannot decrypt documents. Re-registration required; ask counterparties to re-transmit. |
| **Company archived** | `no_such_user` | Proxy may deactivate after repeated failures | Archive proxy user record alongside company. |

---

## L4: Performance, Odoo 18 → 19 Changes, Security, Peppol Transport

### Performance Considerations

| Area | Concern | Mitigation | Impact |
|------|---------|------------|--------|
| **`lock_for_update()` in `_renew_token()`** | Row-level lock held for duration of HTTP request (up to 30s) | Lock is released immediately after the network call completes (method returns before lock expires naturally at transaction end). Contention only occurs when two Odoo workers try to renew the same token simultaneously. | Under normal 24h expiry cadence, contention is rare. High-volume multi-worker environments with many proxy users may see lock waits during token expiry bursts. |
| **`sudo()` on private key access** | `private_key_id._decrypt()` uses `sudo()` to bypass ACLs | `certificate.key` is not ACL-gated in Odoo's default security model — all users can read private keys via sudo. This is intentional to allow the proxy user model to function across user contexts. | A user with database write access (but not necessarily base.group_system) could sudo into the private key if they can trigger decryption. This is an inherent risk of the RSA decryption design. |
| **Base64 decoding overhead** | Two base64 decodes per message (`_decrypt_data`) | Negligible compared to RSA decryption. Modern CPUs handle base64 at multi-Gbps rates. | Minimal for typical EDI volumes (<1000 documents/day). |
| **`requests.post(timeout=30)`** | HTTP timeout bounds all proxy calls | `DEFAULT_TIMEOUT = 30` applies to both connect and read phases. Slow proxies cause `_make_request` to raise `connection_error`. | Timeout exposes Odoo to transient failures; consuming modules should implement retry logic. |
| **RSA key size** | RSA decryption is CPU-intensive | RSA key generation during registration uses Odoo's `certificate.key._generate_rsa_private_key()`. Odoo 19's implementation uses 2048-bit RSA by default, which is fast enough for per-document decryption at EDI volumes. | For high-volume receivers (1000+ documents/day), RSA decryption can become a bottleneck. Consider async processing or batching. |
| **Token sync version counter** | `token_sync_version` increments on every token renewal | Each renewal write increases the field. No cleanup mechanism; version can grow indefinitely. | Storage is trivial (integer). Not a performance concern. |

### Odoo 18 → Odoo 19 Changes

| Aspect | Odoo 18 | Odoo 19 | Impact |
|--------|---------|---------|--------|
| **Token desync detection** | Not explicitly tracked | `is_token_out_of_sync` (Boolean) + `token_sync_version` (Integer) added | Consuming modules can detect DB duplication without parsing error messages. |
| **`_make_request` retry on token expiry** | Token expiry raised as error | Automatically calls `_renew_token()`, commits, retries with `auth_type='hmac'` | Eliminates manual retry logic in consuming modules. |
| **Proxy endpoint version** | `/iap/account_edi/1/create_user` | `/iap/account_edi/2/create_user` for `create_user`; v1 retained for `renew_token` | New API version with potential schema changes. |
| **Certificate key Fernet helper** | Fernet decrypt inline in `_decrypt_data` | Extracted to `certificate.key._account_edi_fernet_decrypt()` | Reusable across modules; cleaner separation of concerns. |
| **`_decrypt_data` method** | Directly called `Fernet(key).decrypt()` via sudo on private_key | Calls `self.env['certificate.key']._account_edi_fernet_decrypt()` via the model method | Centralizes Fernet logic in `certificate.key`; allows future changes without modifying proxy client. |
| **Private key domain filter** | Unspecified | `domain=[('public', '=', False)]` on `private_key_id` field | Prevents accidental assignment of public keys as decryption credentials. |
| **Asymmetric auth fallback** | Present | Present (unchanged) | Used when refresh token is expired but private key is still valid (e.g., during renewal races). |

### Security: JWT Tokens, Company Identification

The module does not use JWT. It uses two complementary signature schemes:

#### 1. HMAC-SHA256 (Primary)

The `refresh_token` is a 256-bit random string generated by the proxy server at registration. It serves as the HMAC secret. Every outbound request signs a canonical message:

```
canonical_message = f"{timestamp}|{url_path}|{id_client}|{sorted_query_json}|{sorted_body_json}"
signature = HMAC-SHA256(refresh_token, canonical_message)
```

**Security properties:**
- **Replay prevention**: `odoo-edi-timestamp` is part of the signed message; proxy rejects requests with timestamps outside its tolerance window.
- **Integrity**: HMAC-SHA256 ensures the request body, URL path, and query params cannot be modified in transit without detection.
- **Anti-impersonation**: The `refresh_token` is a per-database secret. If a database is duplicated without neutralization, two databases share the same token. The first to call `renew_token` wins — the second receives `invalid_signature` and is soft-deactivated.

#### 2. RSA-SSA-PKCS1-v1_5 (Fallback / Asymmetric)

When `auth_type='asymmetric'`, the private key signs the canonical message using RSA-SSA-PKCS1-v1_5. This is used during token renewal races — the renewal request carries the expired token as auth, but if the proxy has already accepted the new token from another worker, it returns `invalid_signature`. In that case, the consuming module may retry with the private key signature as an alternative proof of identity.

#### Company Identification

The `edi_identification` field (typically a VAT number) serves as the company's Peppol/SDI identifier. This is:
- Transmitted to the proxy at registration (`edi_identification` in IAP params)
- Used by the proxy's SMP (Service Metadata Publisher) to route documents addressed to this company
- Unique within the proxy type namespace — two registrations with the same `edi_identification` for the same `proxy_type` will conflict

### How Peppol Transport Works

**Peppol** (Pan-European Public Procurement OnLine) is a network of EDI Service Providers (APs - Access Points) that route UBL documents using the Peppol BIS (Business Interoperability Specifications).

```
Odoo (as sender)                     Peppol Network                       Vendor
    │                                       │                              │
    │ 1. Generate UBL BIS 3 invoice          │                              │
    │ 2. Look up vendor's Peppol ID (via SMP)│                              │
    │ 3. POST to Odoo's AP (proxy)           │                              │
    │───────────────────────────────────────►                              │
    │                                       │ 4. Route via SMP lookup        │
    │                                       │───────────────────────────────►│
    │                                       │                               │
    │                                       │◄──────────────────────────────│ 5. Ack
    │◄───────────────────────────────────────│                               │
    │ 6. Success / error response            │                               │
```

**Key concepts:**
- **SMP (Service Metadata Publisher)** — DNS-based directory that maps a Peppol ID (typically a VAT number with a prefixed scheme like `iso6523-actorid-upis::ZZZ:123456789`) to the recipient's AP endpoint. Odoo does not interact directly with SMP; this is handled by the proxy's routing infrastructure.
- **AP (Access Point)** — The server that receives documents and routes them. Odoo's proxy acts as Odoo's AP. Other companies' APs may be operated by different vendors (Oleti, Basware, etc.) — the Peppol network handles inter-AP routing.
- **Peppol BIS 3** — The specific UBL profile for invoices/orders. Odoo uses `purchase_edi_ubl_bis3` for order export and `account_edi_ubl_cii` (invoices) for billing.
- **Peppol Directory** — Public registry of Peppol participants. Odoo (`account_peppol`) may validate the recipient against this directory before sending.

### Cryptographic Key Lifecycle

```
Registration:
  Odoo → generates RSA-2048 keypair (private key stored in certificate.key)
  Odoo → sends public_key (PEM) + edi_identification to proxy at /iap/account_edi/2/create_user
  Proxy → issues id_client + refresh_token
  Odoo → stores id_client, refresh_token, private_key_id in account_edi_proxy_client.user

Normal operation (every outbound request):
  Odoo → builds canonical message (timestamp|url_path|id_client|query|body)
  Odoo → HMAC-SHA256(canonical_message, refresh_token) → signature header
  Odoo → POST to proxy with odoo-edi-client-id, odoo-edi-timestamp, odoo-edi-signature

Token expiry (every 24h):
  Odoo → calls /iap/account_edi/1/renew_token (HMAC auth with current token)
  Proxy → issues new refresh_token
  Odoo → updates refresh_token field; old token is now invalid

Desync (database duplication):
  DB-A and DB-B share same id_client + refresh_token
  DB-A calls renew_token → DB-A gets new token; DB-B's token is now invalid
  DB-B's next request → proxy returns invalid_signature
  DB-B's record soft-deactivated (active = False)
  DB-B must re-register with a new keypair to get a new id_client
```

### Res Company Extension: One2many Reverse

```python
account_edi_proxy_client_ids = fields.One2many(
    'account_edi_proxy_client.user',
    inverse_name='company_id',
    context={'active_test': True}
)
```

The `active_test` context in the inverse one2many means default domain on the company form's "EDI Proxy Users" tab excludes inactive users. This provides a cleaner UI — only active, relevant proxy users appear by default. The context is applied on the inverse side, meaning it affects reads through `company_id.account_edi_proxy_client_ids` but not the forward relation from `account_edi_proxy_client.user.company_id`.

---

## Security Model

### Access Control (`security/ir.model.access.csv`)

| ID | Name | Model | Group | R | W | C | D |
|----|------|-------|-------|---|---|---|---|
| `access_account_edi_proxy_manager` | access_account_edi_proxy_user | `model_account_edi_proxy_client_user` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_account_edi_proxy_user` | access_account_edi_proxy_user | `model_account_edi_proxy_client_user` | `account.group_account_invoice` | 1 | 0 | 0 | 0 |

- **Invoice users** (`account.group_account_invoice`): read-only — can view proxy user status but cannot modify credentials.
- **System administrators** (`base.group_system`): full CRUD — needed because registration creates records containing sensitive tokens.
- **`refresh_token` field-level group**: restricted to `base.group_system` in the field definition — even invoice users with read ACL cannot see the raw token value.

### Record Rules (`security/account_edi_proxy_client_security.xml`)

```xml
<field name="domain_force">[('company_id', 'in', company_ids)]</field>
```

Multi-company record rules ensure users only see proxy users belonging to companies they have access to. This is enforced alongside group-based ACLs.

### Views: Read-Only Enforcement

Both form and list views have `readonly="1"` on all fields. The list view additionally has `create="false" delete="false" edit="false"`. This makes the views diagnostic tools rather than administrative interfaces — all management (registration, renewal, deactivation) is done through consuming modules' wizards.

### Menu Item: Hidden from Users

```xml
<menuitem name="EDI Proxy Users"
          parent="account.account_invoicing_menu"
          id="menu_account_proxy_client_user"
          action="action_tree_account_edi_proxy_client_user"
          groups="base.group_no_one"/>
```

The menu item is hidden from all users (`groups="base.group_no_one"`). It is a diagnostic/administrative tool accessible only via direct URL to administrators who know it exists.

---

## Module File Map

```
account_edi_proxy_client/
├── __init__.py                         # Calls models/__init__.py; post-init hook
├── __manifest__.py                     # depends: account, certificate; post_init_hook
├── models/
│   ├── __init__.py
│   ├── account_edi_proxy_user.py         # Main model + OdooEdiProxyAuth
│   │                                        # Fields, constraints, _register_proxy_user,
│   │                                        # _make_request, _renew_token, _decrypt_data
│   ├── account_edi_proxy_auth.py          # OdooEdiProxyAuth (requests.auth.AuthBase)
│   │                                        # __get_payload, __sign_request_with_token,
│   │                                        # __sign_with_private_key, __call__
│   ├── key.py                              # certificate.key extension
│   │                                        # _account_edi_fernet_decrypt()
│   └── res_company.py                      # res.company extension
│                                           # account_edi_proxy_client_ids one2many
├── security/
│   ├── ir.model.access.csv                # ACL: base.group_system (full), account group (read)
│   └── account_edi_proxy_client_security.xml  # Record rule: multi-company
├── views/
│   └── account_edi_proxy_user_views.xml   # Form + list (read-only), action, menu
└── i18n/                                  # Translation files
```

---

## See Also

- [Modules/account_peppol](modules/account_peppol.md) — Primary consumer; PEPPOL network integration
- [Modules/l10n_it_edi](modules/l10n_it_edi.md) — Italian SDI integration (extends same proxy)
- [Modules/certificate](modules/certificate.md) — RSA key generation and storage
- [Modules/purchase_edi_ubl_bis3](modules/purchase_edi_ubl_bis3.md) — Purchase order UBL export (uses proxy indirectly via account_peppol)
- [Modules/account_edi_ubl_cii](modules/account_edi_ubl_cii.md) — UBL BIS 3 invoice/credit note export
- [Peppol Network](https://peppol.eu/)
- [Odoo Peppol Documentation](https://www.odoo.com/documentation/17.0/applications/accounting/fiscal_localizations/peppol.html)

---

**Related Tags:** #edi #peppol #e-invoice #proxy #security #l4 #hmac #rsa #cryptography
