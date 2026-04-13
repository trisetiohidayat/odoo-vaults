# Certificate

**Module:** `certificate`
**Category:** Hidden/Tools
**Depends:** `base_setup`
**License:** LGPL-3
**Version:** `0.1`
**Author:** Odoo S.A.

## Overview

The `certificate` module manages X.509 digital certificates and cryptographic keys within Odoo. It supports loading certificates in PEM, DER, or PKCS12 formats, extracting metadata (subject, serial, validity dates), validating key-certificate compatibility, generating keys, and performing cryptographic operations (sign, verify, decrypt, fingerprinting). It is the foundation for EDI e-invoicing modules that require document signing.

The module has two core models: `certificate.certificate` (X.509 certificates) and `certificate.key` (asymmetric key pairs). Both are company-scoped records.

> **Note on survey_certificate:** The training/survey completion certificate feature (e.g., certification after a survey) is in `survey_certificate` (`addons/survey_certificate`). This `certificate` module is strictly about X.509 cryptographic certificates and is unrelated to that feature.

---

## Dependencies

| Dependency | Purpose |
|---|---|
| `base_setup` | Base configuration, company defaults, multi-company support |

**No heavy ORM dependencies.** The module uses the `cryptography` Python library directly (imported as `from cryptography import x509`, `from cryptography.hazmat.primitives import ...`). It does not depend on `account`, `sale`, or any EDI module — those depend on `certificate`.

---

## Models

### `certificate.certificate`

X.509 v3 certificate storage with metadata extraction and signing capabilities.

**Internal name:** `certificate.certificate`
**Description:** Certificate
**Order:** `date_end DESC`
**Company:** Required (multi-company, `check_company_auto=True`)

#### Fields

| Field | Type | Default | Constraints | L2 Rationale |
|---|---|---|---|---|
| `name` | `Char` | — | — | Display name chosen by user, not extracted from cert. Distinguishable from `subject_common_name` which is auto-extracted. |
| `content` | `Binary` | — | Required on write | Raw certificate file. Format auto-detected (PEM, DER, or PKCS12). Stored as base64 in DB. |
| `pkcs12_password` | `Char` | `False` | — | Password for PKCS12 (`.pfx`/`.p12`) files only. Not used for PEM/DER. The field stores the password in plaintext in DB — see Security section. |
| `private_key_id` | `Many2one(certificate.key)` | Computed | `domain: [('public', '=', False)]` | Linked private key. Computed automatically from PKCS12 unpacking; manually settable for PEM/DER certs. |
| `public_key_id` | `Many2one(certificate.key)` | `False` | `domain: [('public', '=', True)]` | Override field. Used when the self-contained public key in the certificate is erroneous but a correct external key is available. Rarely needed in practice. |
| `scope` | `Selection(general)` | `False` | — | Intended scope. Base module ships only `'general'`. Localization modules extend this (e.g., `'sii'` for Spain, `'ksef'` for Poland). The field is currently `invisible="1"` in the base form view — it is designed to be extended. |
| `content_format` | `Selection(der/pem/pkcs12)` | Computed | — | Auto-detected on upload. Determines which parsing path `_compute_pem_certificate` takes. Stored for audit/debugging. |
| `pem_certificate` | `Binary` | Computed | — | Certificate normalized to PEM format. All downstream business methods operate on this canonical form. |
| `subject_common_name` | `Char` | Computed | — | Extracted from `cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)`. May be empty for certs without a CN (e.g., some CA certs). |
| `serial_number` | `Char` | Computed | — | Certificate serial number (integer as string). Written into EDI documents as the certificate identifier. |
| `date_start` | `Datetime` | Computed | — | Certificate validity start (`not_valid_before`). Timezone: naive UTC. |
| `date_end` | `Datetime` | Computed | — | Certificate validity end (`not_valid_after`). Timezone: naive UTC. |
| `loading_error` | `Text` | Computed | — | If certificate failed to parse, contains the i18n error message. Used as a signal throughout validation. |
| `is_valid` | `Boolean` | Computed | Search: `_search_is_valid` | `True` if within validity window and no `loading_error`. `False` if cert is expired, not-yet-valid, or failed to load. |
| `active` | `Boolean` | `True` | — | Soft-delete / archive flag. Archived certs retain the record but are excluded from validity searches. |
| `company_id` | `Many2one(res.company)` | `lambda self: self.env.company` | Required, `ondelete='cascade'` | Company scoping. Certificate is only usable within its company hierarchy. |
| `country_code` | `Char` | `related: company_id.country_code` | — | Read-only derived field. Used by localization modules to conditionally show country-specific settings. |

#### Computed Logic

**`_compute_pem_certificate()`** — triggered by `@api.depends('content', 'pkcs12_password')`.

Format detection cascade (in order):
1. **DER** — `x509.load_der_x509_certificate(content)` → sets `content_format='der'`
2. **PKCS12** — `pkcs12.load_key_and_certificates(content, pkcs12_password)` → sets `content_format='pkcs12'`
3. **PEM** — `x509.load_pem_x509_certificate(content)` → sets `content_format='pem'`

If all three fail → `loading_error` set, all metadata fields cleared.

Metadata extraction on success:
- `pem_certificate` = PEM-encoded cert (canonical form)
- `serial_number` = `cert.serial_number` (Python int, cast to string)
- `subject_common_name` = first CN attribute value from subject DN
- `date_start` / `date_end` = validity bounds. **Odoo 19 cryptography compatibility:** uses `cert.not_valid_before_utc` / `cert.not_valid_after_utc` with `replace(tzinfo=None)` when `cryptography >= 42.0.0`. Falls back to `not_valid_before` / `not_valid_after` for older library versions. This is a silent compatibility fix — no version pinning required in `__manifest__.py`.

**`_compute_private_key()`** — triggered by `@api.depends('pem_certificate')`.

Only acts when:
- `content_format == 'pkcs12'`
- `private_key_id` is not already set

On PKCS12 load, the embedded private key is extracted, wrapped in PKCS8 PEM, and a `certificate.key` record is auto-created if one matching the same PEM content does not already exist (deduplication via `ir.attachment` search on `res_id` + `datas` + `company_id`).

**`_compute_is_valid()`** — triggered by `@api.depends('date_start', 'date_end', 'loading_error')`.

```
is_valid = (date_start <= now <= date_end) and (loading_error == '')
```

Uses `fields.Datetime.now()` (naive UTC). `date_start` and `date_end` are also naive UTC (cert validity timestamps are UTC by RFC 5280).

**`_search_is_valid()`** — custom `search()` method for the `is_valid` computed field.

Only supports `operator='in'` with boolean values. Returns a domain:
```
[('pem_certificate', '!=', False),
 ('date_start', '<=', now),
 ('date_end', '>=', now),
 ('loading_error', '=', '')]
```
The `pem_certificate != False` check implicitly validates that the cert loaded successfully.

#### Constraints

**`_constrains_certificate_key_compatibility()`** — `@api.constrains('pem_certificate', 'private_key_id', 'public_key_id')`

Fires on create and write. Compares public key bytes of the certificate against the linked private/public key using `constant_time.bytes_eq()` to prevent timing attacks.

- If `private_key_id` is set: compares cert's public key vs. `private_key_id`'s derived public key
- If `public_key_id` is set: compares cert's public key vs. `public_key_id`'s public key

Raises `UserError` with the specific mismatch message. This constraint is the primary guard against an invalid (mismatched) certificate-key pair being recorded.

#### Business Methods

| Method | Signature | Description |
|---|---|---|
| `_get_der_certificate_bytes` | `(formatting='encodebytes') -> bytes` | DER-encoded certificate bytes |
| `_get_fingerprint_bytes` | `(hashing_algorithm='sha256', formatting='encodebytes') -> bytes` | SHA1 or SHA256 fingerprint |
| `_get_signature_bytes` | `(formatting='encodebytes') -> bytes` | Certificate's own signature bytes (not a signing operation) |
| `_get_public_key_bytes` | `(encoding='der', formatting='encodebytes') -> bytes` | Public key in DER or PEM |
| `_get_public_key_numbers_bytes` | `(formatting='encodebytes') -> tuple(bytes, bytes)` | (n, e) for RSA or (x, y) for EC |
| `_sign` | `(message, hashing_algorithm='sha256', formatting='encodebytes') -> bytes` | Signs `message` with linked private key. Pre-checked `is_valid` and presence of `private_key_id`. |

All methods use `ensure_one()` (singleton enforcement).

---

### `certificate.key`

Asymmetric cryptographic key storage. Supports RSA, EC (SECP256R1 / P-256), and Ed25519 algorithms.

**Internal name:** `certificate.key`
**Description:** Cryptographic Keys
**Company:** Required, `default=lambda self: self.env.company`

#### Fields

| Field | Type | Default | Constraints | L2 Rationale |
|---|---|---|---|---|
| `name` | `Char` | `"New key"` | — | User-friendly name |
| `content` | `Binary` | — | Required | Raw key file (PEM or DER, public or private). Stored as base64. |
| `password` | `Char` | `False` | — | Decryption password for encrypted private keys. Plaintext storage in DB — see Security section. |
| `pem_key` | `Binary` | Computed | — | Normalized PEM representation. All operations use this canonical form. Stored for performance (avoids re-parsing on every method call). |
| `public` | `Boolean` | Computed | — | `True` = public key, `False` = private key. Detected during `_compute_pem_key` by which `cryptography` loader succeeded. |
| `loading_error` | `Text` | Computed | — | Error message if key failed to parse. Clears on successful load. |
| `active` | `Boolean` | `True` | — | Archive flag |
| `company_id` | `Many2one(res.company)` | `lambda self: self.env.company` | Required, `ondelete='cascade'` | Company scoping |

#### Computed Logic

**`_compute_pem_key()`** — triggered by `@api.depends('content', 'password')`.

Load cascade (in order):
1. `serialization.load_der_private_key(content, password)` → `public=False`
2. `serialization.load_pem_private_key(content, password)` → `public=False`
3. `serialization.load_der_public_key(content)` → `public=True`
4. `serialization.load_pem_public_key(content)` → `public=True`

If all fail → `loading_error = "This key could not be loaded. Either its content or its password is erroneous."`

On success, normalizes to PKCS8 format:
- Private keys → `PrivateFormat.PKCS8`, optionally encrypted with `BestAvailableEncryption(password)` if password set
- Public keys → `PublicFormat.SubjectPublicKeyInfo`

#### Business Methods

| Method | Signature | Notes |
|---|---|---|
| `_sign` | `(message, hashing_algorithm='sha256', formatting='encodebytes')` | Instance method. Signs with this key. Raises if `public=True` or `loading_error` set. |
| `_verify` | `(signed_message, signature, hashing_algorithm='sha256') -> bool` | Returns `True`/`False`. Raises on bad key. |
| `_decrypt` | `(message, hashing_algorithm='sha256') -> str` | RSA-OAEP decryption. EC and Ed25519 keys raise `UserError` — Ed25519 cannot decrypt by design. |
| `_get_public_key_bytes` | `(encoding='der', formatting='encodebytes') -> bytes` | DER or PEM public key |
| `_get_public_key_numbers_bytes` | `(formatting='encodebytes') -> tuple(bytes, bytes)` | (n,e) for RSA, (x,y) for EC |
| `_sign_with_key` | `@api.model` static — `(message, pem_key, pwd, hashing_algorithm, formatting)` | Static utility for signing with arbitrary PEM key bytes |
| `_verify_with_key` | `@api.model` static — `(signed_message, signature, pem_key, signature_algorithm)` | Static utility |
| `_numbers_public_key_bytes_with_key` | `@api.model` static — `(pem_key, formatting)` | Static utility |
| `_generate_ec_private_key` | `@api.model` — `(company, name, curve, password)` | Generates EC key. Only `SECP256R1` supported. |
| `_generate_rsa_private_key` | `@api.model` — `(company, name, public_exponent, key_size, password)` | Generates RSA key. Default 2048-bit. Public exponent must be 65537 or 3. |
| `_generate_ed25519_private_key` | `@api.model` — `(company, name, password)` | Generates Ed25519 key |

**Signing algorithm selection (in `_sign_with_key`):**
```
match private_key:
    case ec.EllipticCurvePrivateKey():  ECDSA + STR_TO_HASH[hashing_algorithm]
    case rsa.RSAPrivateKey():          PKCS1v15 padding + STR_TO_HASH[hashing_algorithm]
    case ed25519.Ed25519PrivateKey():  Ed25519 (hash algorithm fixed, ignores parameter)
```
Ed25519 ignores the `hashing_algorithm` parameter entirely — it is a fixed SHA512-based scheme.

**Supported Algorithms Summary:**

| Key Type | Can Sign | Can Decrypt | Notes |
|---|---|---|---|
| RSA Private | Yes (PKCS1v15) | Yes (RSA-OAEP) | — |
| EC Private (SECP256R1) | Yes (ECDSA) | No | — |
| Ed25519 Private | Yes (fixed) | No | Ed25519 has no decryption primitive |

---

## Security

### Access Control

| ID | Name | Model | Group | CRUD |
|---|---|---|---|---|
| `certificate.access_certificate_admin` | certificate.access_certificate | `model_certificate_certificate` | `base.group_system` | READ+WRITE+CREATE+UNLINK |
| `certificate.access_key_admin` | certificate.access_key | `model_certificate_key` | `base.group_system` | READ+WRITE+CREATE+UNLINK |

**Both models require `base.group_system`** — only administrators can manage certificates and keys. There are no read/write separate ACLs. This is intentional: cryptographic material should only be accessible to trusted admins.

### Record Rules (Multi-Company)

```xml
domain_force: ['|', ('company_id', '=', False), ('company_id', 'parent_of', company_ids)]
```

Both `certificate.certificate` and `certificate.key` use the `parent_of` operator, meaning a child company can access parent company certificates/keys. This is deliberate — subsidiary companies often share signing certificates with the parent entity. Set `company_id=False` for truly shared certificates.

### Plaintext Password Storage

`pkcs12_password` (on certificate) and `password` (on key) are stored as plaintext Char fields in the database. This is a known trade-off:
- The alternative (key wrapping or external KMS) adds complexity disproportionate to the typical Odoo deployment model
- The DB should already be protected by `pg_database` permissions and filesystem `pg_hba.conf`
- The `neutralize.sql` data file sets all password fields to `'dummy'` during database neutralization (post-copy sanitization), preventing leaked plaintext passwords in test/staging environments

### Timing Attack Prevention

`_constrains_certificate_key_compatibility()` uses `constant_time.bytes_eq()` from `cryptography.hazmat.primitives` for the key comparison. This prevents an attacker who can measure response timing from inferring key material. Plain `==` comparison would leak information byte-by-byte.

### `CertificateAdapter` (PyOpenSSL SSL Injection)

The `CertificateAdapter` in `tools/certificate_adapter.py` overrides the `requests` HTTP adapter to inject in-memory X.509 certificates into TLS client auth handshakes. It:
1. Patches `urllib3` to use PyOpenSSL via `inject_into_urllib3()`
2. Adds CA certificates to the `ssl_context._ctx.get_cert_store()`
3. Patches `context.load_cert_chain` to read from `pem_certificate` + `private_key_id.pem_key` rather than filesystem paths

This is used by e-invoicing modules (e.g., `l10n_sa_edi`, `l10n_es_edi_sii`) to perform mTLS with government tax authorities without writing certs to disk.

---

## Performance Implications

### Stored Computed Fields

All certificate/key metadata fields (`pem_certificate`, `subject_common_name`, `serial_number`, `date_start`, `date_end`, `content_format`, `pem_key`, `public`, `loading_error`, `is_valid`) are `store=True`. This means:
- **On upload:** One full parse + field write. Certificate parsing is O(1) for single-file uploads.
- **On read:** No recomputation — data served from DB. Ideal for frequent EDI operations.
- **On company change:** All stored fields recompute. For large binary blobs, this triggers DB writes.

### `CertificateAdapter` and SSL Context Re-creation

`CertificateAdapter.init_poolmanager()` calls `inject_into_urllib3()` on every pool manager initialization. In high-throughput scenarios (e.g., batch e-invoicing to government portals), this adds overhead. However, Odoo's EDI flows are typically low-volume (per-document), so this is not a bottleneck in practice.

### Key Generation

Key generation (`_generate_rsa_private_key`, `_generate_ec_private_key`, `_generate_ed25519_private_key`) is CPU-intensive, especially RSA at 2048+ bits. These should not be called in hot paths. The methods are `@api.model` (no active record context, runs as superuser) and create a `certificate.key` record in the DB.

---

## Cross-Module Integrations

### Extending `scope` Selection

Localization modules add scope values to filter certificates by use case:

| Module | Scope Value | Purpose |
|---|---|---|
| `l10n_es_edi_sii` | `'sii'` | Spanish SII (Suministro Immediate de Informacion) |
| `l10n_pl_edi` | `'ksef'` | Polish KSeF e-invoicing |
| `l10n_sa_edi` | (custom) | Saudi ZATCA e-invoicing |

### Certificate Key Methods Extended

**`l10n_sa_edi`** (`l10n_sa_edi/models/certificate.py`) extends `certificate.certificate` with ZATCA-specific CSR generation:
- `_l10n_sa_get_issuer_name()` — extracts issuer DN string
- `_l10n_sa_get_csr_vals(journal)` — builds CSR subject fields from journal/company data
- `_l10n_sa_validate_csr_vals(journal)` — enforces 64-character max on CSR field values
- `_l10n_sa_get_csr_str(journal)` — generates DER CSR bytes signed by the company's `certificate.key`

**`l10n_pl_edi`** stores a certificate reference on `res.company`:
```python
l10n_pl_edi_certificate = fields.Many2one('certificate.certificate', "KSeF Certificate")
```
This links the KSeF credential directly to the company for Poland's e-invoicing API.

### Account Peppol

`account_peppol/wizard/peppol_registration.py` uses `certificate.certificate._sign()` for Peppol participant registration signatures. The `account_peppol/tools/demo_utils.py` uses certificate fingerprinting for endpoint verification.

### IoT Drivers

`iot_drivers/tools/certificate.py` is a separate, unrelated system. It manages **TLS certificates for IoT Box** (the device that connects scales, cameras, etc. to Odoo). It parses system-level PEM files (`/etc/ssl/certs/nginx-cert.crt`) and communicates the expiry date back to Odoo via `/iot/box/update_certificate_status`. It does **not** use the `certificate` module's ORM models.

---

## Views and UI

### Certificate Form View
- **Alert banner:** Shows `loading_error` in a yellow warning box when present
- **Input group (`certificate_input`):** `name`, `company_id` (readonly, multi-company only), `content` (binary widget), `pkcs12_password`
- **Extracted fields:** `subject_common_name`, `private_key_id`, `public_key_id` — all invisible until `pem_certificate` is set
- **Scope:** `invisible="1"` — ready for localization overrides to unhide
- **Data group (`certificate_data`):** Validity dates with `widget="remaining_days"`, serial number

### Certificate List View
Columns: `name`, `subject_common_name`, `is_valid` (validity indicator), `company_id`
Search filters: `scope_general`, `valid`, `not_valid`, `archived`

### Key Form View
- Alert banner for `loading_error`
- `content` (binary), `password` (password widget)

### Key List/Search
List: `name`, `company_id`
Search filters: `archived`, `private`, `public`, `invalid`

### Settings (Res Config)
The module adds a "Certificates and Keys" section to `res.config.settings` (Settings > General Settings), accessible only to `base.group_system`. Two shortcut buttons link directly to the Certificate and Key list views. The settings view is `company_dependent="1"` (per-company configuration).

---

## Neutralize SQL

The `data/neutralize.sql` file (loaded as post-copy data):
```sql
UPDATE certificate_certificate SET pkcs12_password = 'dummy';
UPDATE certificate_key SET password = 'dummy';
```
This sanitizes plaintext password fields when a production database is neutralized (copied for testing/support). It does not clear the certificate content or key content — only the passwords, which are set to a dummy value.

---

## Test Coverage

Tests in `tests/test_keys_certificates.py` (`@tagged: post_install`):

| Test | What It Covers |
|---|---|
| `test_ec_key_generated` | EC key generation + successful re-parsing of PEM output |
| `test_rsa_key_generated` | RSA key generation + successful re-parsing |
| `test_ed25519_key_generated` | Ed25519 key generation + successful re-parsing |
| `test_key_loading_wrong_password` | Wrong password sets `loading_error`, correct password clears it |
| `test_der_certificate` | DER format auto-detection sets `content_format='der'` |
| `test_pem_certificate` | PEM format auto-detection sets `content_format='pem'` |
| `test_pfx_certificate` | PKCS12 format auto-detection sets `content_format='pkcs12'` |
| `test_is_valid` | Expired cert gets `is_valid=False` |
| `test_keys_certificate_not_matching` | Mismatched cert+key raises `UserError` on create |

---

## Historical Notes (Odoo 18 → 19)

- The `certificate` module is a relatively new addition to Odoo's standard library. It was introduced to consolidate cryptographic operations previously scattered across localization EDI modules.
- **cryptography 42.0.0 compatibility:** Odoo 19 added a version check (`parse_version(metadata.version('cryptography')) < parse_version('42.0.0')`) to handle the renamed `not_valid_before` / `not_valid_after` → `not_valid_before_utc` / `not_valid_after_utc` in the `cryptography` library. This is the most notable version-specific change.
- The `scope` field was designed from the start to be extended by localization modules rather than having hard-coded country-specific values in the base module.
- **PyOpenSSL (CertificateAdapter):** The use of `urllib3.contrib.pyopenssl.inject_into_urllib3()` is a known pattern for mTLS in Odoo. It was present in earlier localization modules and consolidated here.

---

## Related

- [Modules/l10n_es_edi_sii](modules/l10n_es_edi_sii.md) — Spanish SII e-invoicing
- [Modules/l10n_pl_edi](modules/l10n_pl_edi.md) — Polish KSeF e-invoicing
- [Modules/l10n_sa_edi](modules/l10n_sa_edi.md) — Saudi ZATCA e-invoicing
- [Modules/account_peppol](modules/account_peppol.md) — Peppol network participation
- [Patterns/Security Patterns](patterns/security-patterns.md) — ACL, ir.rule, field groups
