---
Module: certificate
Version: Odoo 18
Type: Core
Tags: [#odoo, #odoo18, #certificate, #cryptography, #security, #x509, #signing]
---

# Certificate Module

**Module:** `certificate`
**Path:** `~/odoo/odoo18/odoo/addons/certificate/`
**Category:** Hidden/Tools
**Depends:** `base_setup`
**License:** OEEL-1

Manages X.509 digital certificates and cryptographic keys for electronic document signing. Used by modules like `l10n_*` localization and e-invoicing to sign invoices, tax declarations, and compliance documents.

> **L4 Architecture:** Certificate is a security module. It loads PKI material (certificates + private keys), validates compatibility between certificate/key pairs, and exposes signing primitives used by other Odoo modules. It does NOT manage certificate lifecycle (expiry alerts, renewal workflows) — that is the responsibility of consuming modules.

---

## Models

### `certificate.certificate`

X.509 certificate record. Stores the certificate file and resolves associated cryptographic keys.

**Inheritance:** `models.Model`
**External ID:** `certificate.model_certificate_certificate`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Display name |
| `content` | Binary (file) | The certificate file (DER, PEM, or PKCS12) — **required** |
| `pkcs12_password` | Char | Password to decrypt PKCS12 (.p12/.pfx) files |
| `private_key_id` | Many2one `certificate.key` | Linked private key. Domain: `public = False`. Computed automatically from PKCS12, or manually assigned |
| `public_key_id` | Many2one `certificate.key` | Override public key when the certificate's embedded key is wrong. Domain: `public = True` |
| `scope` | Selection | Certificate scope. Currently only `'general'` — extensible by other modules |
| `content_format` | Selection | Original format auto-detected: `'der'`, `'pem'`, `'pkcs12'`. Computed, stored |
| `pem_certificate` | Binary | Normalized PEM-format certificate. Computed, stored |
| `subject_common_name` | Char | Extracted from certificate subject's CN field |
| `serial_number` | Char | Certificate serial number — used in electronic documents |
| `date_start` | Datetime | Validity start (UTC). Extracted from cert |
| `date_end` | Datetime | Validity expiry (UTC). Extracted from cert |
| `loading_error` | Text | Set if certificate fails to parse; shown as warning banner |
| `is_valid` | Boolean | Computed validity based on dates + no loading error. Supports domain search |
| `active` | Boolean | Archive/unarchive. Default `True` |
| `company_id` | Many2one `res.company` | Multi-company scoping. Required, default `self.env.company` |
| `country_code` | Char (related) | Derives from `company_id.country_code` |

#### Key Methods

**`_compute_pem_certificate()`** — `api.depends('content', 'pkcs12_password')`
Attempts to parse `content` as DER, then PKCS12, then PEM. On success, extracts: `content_format`, `pem_certificate`, `subject_common_name`, `serial_number`, `date_start`, `date_end`. On failure, sets `loading_error`. UTC timezone handling differs for `cryptography >= 42.0.0` (uses `not_valid_before_utc` / `not_valid_after_utc`).

**`_compute_is_valid()`** — `api.depends('date_start', 'date_end', 'loading_error')`
Compares `datetime.now(datetime.timezone.utc)` against validity window. Returns `False` if any date is missing or if `loading_error` is set.

**`_search_is_valid()`** — Custom search method (supports `'='` and `'!='`)
Returns domain for valid/invalid certificates. Valid = `pem_certificate != False AND date_start <= now AND date_end >= now AND loading_error = ''`.

**`_constrains_certificate_key_compatibility()`** — `@api.constrains`
Uses `cryptography.hazmat.primitives.constant_time.bytes_eq` to compare public keys. Raises `UserError` if certificate and linked keys are not cryptographically compatible.

**`_get_der_certificate_bytes(formatting)`** — Returns DER-encoded bytes. `formatting`: `'encodebytes'` (base64 with 76-char lines), `'base64'` (raw), other (raw bytes).

**`_get_fingerprint_bytes(hashing_algorithm, formatting)`** — SHA1 or SHA256 fingerprint. Uses `STR_TO_HASH` map from `key.py`.

**`_get_signature_bytes(formatting)`** — Raw signature bytes from the certificate.

**`_get_public_key_numbers_bytes(formatting)`** — Returns `(e, n)` bytes for RSA, or `(x, y)` bytes for EC public keys.

**`_get_public_key_bytes(encoding, formatting)`** — DER or PEM public key bytes. Prefers external `public_key_id` or `private_key_id` if set, otherwise extracts from certificate content.

**`_sign(message, hashing_algorithm, formatting)`** — **Primary signing method.** Validates `is_valid` and presence of `private_key_id`, then delegates to `certificate.key._sign()`. Raises `UserError` if cert is expired or key is missing.

---

### `certificate.key`

Cryptographic key record (private or public). Keys can be standalone or linked to a certificate.

**Inheritance:** `models.Model`
**External ID:** `certificate.model_certificate_key`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Key name, default `"New key"` |
| `content` | Binary (file) | Key file (DER, PEM, or PKCS8) — **required** |
| `password` | Char | Optional password for encrypted PEM/DER key |
| `pem_key` | Binary | Normalized PEM-format key. Computed, stored |
| `public` | Boolean | `True` = public key, `False` = private key. Computed |
| `loading_error` | Text | Set if key fails to parse |
| `active` | Boolean | Archive/unarchive. Default `True` |
| `company_id` | Many2one `res.company` | Required, default `self.env.company` |

#### Key Methods

**`_compute_pem_key()`** — `api.depends('content', 'password')`
Attempts load in order: DER private key → PEM private key → DER public key → PEM public key. Sets `public` and `pem_key` accordingly.

**`_sign(message, hashing_algorithm, formatting)`** — Signs a message using the private key. Supports RSA (PKCS1v15) and EC (ECDSA). Raises if used on a public key. Supports SHA1 and SHA256.

**`_decrypt(message, hashing_algorithm)`** — RSA OAEP decryption. Only supported for RSA private keys. Raises for EC keys or public keys.

**`_get_public_key_bytes(encoding, formatting)`** — DER or PEM public key bytes.

**`_get_public_key_numbers_bytes(formatting)`** — `(e, n)` for RSA or `(x, y)` for EC.

**`_sign_with_key(message, pem_key, pwd, hashing_algorithm, formatting)`** — `@api.model` (static). Signs using a raw PEM key string. Used by `certificate.certificate._sign()` as the implementation layer.

**`_numbers_public_key_bytes_with_key(pem_key, formatting)`** — `@api.model` (static). Extracts public number bytes from a PEM key string.

**`_generate_ec_private_key(company, name, curve)`** — `@api.model` (factory). Generates SECP256R1 EC key. Returns `certificate.key` record.

**`_generate_rsa_private_key(company, name, public_exponent, key_size)`** — `@api.model` (factory). Generates RSA key. `public_exponent` must be 65537 (or 3 for legacy). `key_size` default 2048, minimum 512.

---

## Security Rules

From `security/certificate_security.xml`:

- `certificate_rule_company`: Records scoped to current company hierarchy via `company_id.parent_of company_ids`
- `key_rule_company`: Same multi-company scoping for `certificate.key`

---

## Data Files

- `views/certificate_views.xml` — Form, list, search views for certificate
- `views/key_views.xml` — Form/list for cryptographic keys
- `views/action_menus.xml` — Action menus
- `views/res_config_settings_view.xml` — Settings view
- `security/certificate_security.xml` — Multi-company rules

---

## Usage Pattern

```python
# Find a valid certificate for signing
cert = env['certificate.certificate'].search([
    ('company_id', '=', company.id),
    ('is_valid', '=', True),
    ('private_key_id', '!=', False),
], limit=1)

# Sign a message
signature = cert._sign(
    "Invoice data to sign",
    hashing_algorithm='sha256',
    formatting='encodebytes'
)
```

---

## L4: How Certificates Work

```
certificate.certificate (X.509 cert file)
    ├── content (raw binary: DER/PEM/PKCS12)
    ├── content_format (auto-detected)
    └── pem_certificate (normalized PEM)
            │
            ├─► linked via private_key_id ──► certificate.key (private key)
            └─► linked via public_key_id  ──► certificate.key (public key, optional)
```

**Certificate upload → parsing → key resolution:**

1. User uploads certificate file (`content`)
2. `_compute_pem_certificate` tries DER → PKCS12 → PEM in order
3. If PKCS12 and no manual `private_key_id`: auto-creates a `certificate.key` record from the embedded key
4. `subject_common_name`, `serial_number`, `date_start`, `date_end` extracted and stored
5. `is_valid` computed from date window
6. Other modules can link via `private_key_id` to perform signing operations

**Signing flow:**

```
certificate._sign(message)
    → checks is_valid
    → checks private_key_id exists
    → certificate.key._sign(message)
        → loads PEM private key
        → EC: uses ECDSA(algorithm)
        → RSA: uses PKCS1v15
        → returns formatted signature bytes
```

**Multi-company:** Each certificate and key belongs to a company. IrRule enforces hierarchical scoping.

**Extensibility:** The `scope` selection field has only `'general'` by default. Other modules can extend this selection to add domain-specific certificate scopes (e.g., `'l10n_ar_fiscal'` for Argentine e-invoicing).