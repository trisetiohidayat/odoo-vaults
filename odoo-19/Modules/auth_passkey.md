---
type: module
module: auth_passkey
tags: [odoo, odoo19, security, authentication, webauthn, passkeys, mfa, passwordless]
created: 2026-04-14
updated: 2026-04-14
depth: L4
related:
  - Modules/auth_totp.md
  - Modules/auth_totp_mail.md
  - New Features/What's New.md
  - Patterns/Cross-Module-Integration.md
summary: Implements WebAuthn-based passkey authentication for Odoo 19, covering credential registration, authentication flow, session token management, and security model.
---

# Passkeys (auth_passkey)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `auth_passkey` |
| **Category** | Hidden/Tools |
| **License** | LGPL-3 |
| **Auto Install** | Yes |
| **Author** | Odoo S.A. |
| **Odoo Version** | 19.0+ |
| **Version** | 1.1 |
| **Depends** | `base_setup`, `web` |

## Description

The `auth_passkey` module implements the [WebAuthn (Web Authentication) standard](https://www.w3.org/TR/webauthn-3/) to enable **passkey-based login** in Odoo. Passkeys are a FIDO2-based credential scheme that replaces passwords with cryptographic key pairs stored on devices (e.g., Windows Hello, Touch ID, hardware security keys, phone unlock keys). When a user logs in with a passkey, Multi-Factor Authentication (MFA) is automatically **bypassed** — making passkeys both more secure and faster than password+MFA combinations.

This module is introduced in Odoo 19 as part of the broader push toward passwordless authentication. See [New Features/What's New.md](../New%20Features/What's%20New.md) for the full list of Odoo 19 authentication changes.

---

## L1: Module Structure and Files

```
auth_passkey/
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── auth_passkey_key.py       # Core passkey model
│   └── res_users.py              # res.users extensions
├── controllers/
│   ├── __init__.py
│   └── main.py                   # JSON-RPC endpoints
├── views/
│   ├── auth_passkey_key_views.xml         # Kanban + rename form
│   ├── auth_passkey_login_templates.xml   # Login UI components
│   ├── res_users_identitycheck_views.xml  # Identity check wizard
│   └── res_users_views.xml                # User form extensions
├── security/
│   ├── ir.model.access.csv       # ACL for passkey models
│   └── security.xml              # Record rules (per-user isolation)
└── static/
    ├── lib/
    │   └── simplewebauthn.js    # Browser-side WebAuthn API wrapper
    └── src/
        ├── views/                # Backend JS interaction layer
        ├── interactions/         # Frontend passkey interaction
        └── scss/
            └── res_users.scss    # User form styling
```

### Key Manifest Entries

```python
{
    'name': 'Passkeys',
    'version': '1.1',
    'depends': ['base_setup', 'web'],
    'auto_install': True,
    'assets': {
        'web.assets_backend': [
            'auth_passkey/static/lib/simplewebauthn.js',
            'auth_passkey/static/src/views/*',
        ],
        'web.assets_frontend': [
            'auth_passkey/static/lib/simplewebauthn.js',
            'auth_passkey/static/src/interactions/*',
        ],
    },
}
```

The `auto_install: True` flag means Odoo installs this module automatically when both `base_setup` and `web` are present, ensuring passkey login is available out of the box on any Odoo 19 installation.

---

## L2: Data Model

### Model: `auth.passkey.key`

Stores a registered passkey credential for a user. Each record represents one authenticator device bound to one user account.

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `name` | Char | All users | Human-readable label (e.g., "MacBook Touch ID", "YubiKey") |
| `credential_identifier` | Char | System only | Base64URL-encoded credential ID — used to look up the passkey during login |
| `public_key` | Char (computed) | System only | DER-encoded public key stored as base64. Not directly readable by non-admin users |
| `sign_count` | Integer | System only | Authenticator signature counter — incremented on each authentication to detect cloned devices |
| `create_uid` | Many2one | All users | The user who registered this passkey |

#### SQL Table Structure

The `auth_passkey_key` table is created via `models/init.py` or ORM migration, with a unique constraint on `credential_identifier`:

```sql
CREATE TABLE auth_passkey_key (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    credential_identifier VARCHAR NOT NULL UNIQUE,
    public_key VARCHAR,          -- Added via migration in init()
    sign_count INTEGER DEFAULT 0,
    create_uid INTEGER REFERENCES res_users(id),
    create_date TIMESTAMP,
    write_date TIMESTAMP
);
```

The `public_key` column is **not** part of the initial table definition. It is added by `init()` (a legacy hook that runs after table creation), checking `sql.column_exists` before adding the column. This handles the upgrade path for databases that had `auth_passkey` installed before the column was split out:

```python
def init(self):
    super().init()
    if not sql.column_exists(self.env.cr, 'auth_passkey_key', 'public_key'):
        self.env.cr.execute(SQL(
            'ALTER TABLE auth_passkey_key ADD COLUMN public_key varchar'
        ))
```

#### `public_key` Field Split (Compute/Inverse)

The `public_key` field uses a split compute/inverse pattern:

```python
public_key = fields.Char(
    required=True,
    groups='base.group_system',
    compute='_compute_public_key',
    inverse='_inverse_public_key'
)

def _compute_public_key(self):
    query = 'SELECT public_key FROM auth_passkey_key WHERE id = %s'
    for passkey in self:
        self.env.cr.execute(SQL(query, passkey.id))
        public_key = self.env.cr.fetchone()[0]
        passkey.public_key = public_key

def _inverse_public_key(self):
    pass  # No-op: written directly via raw SQL in make_key()
```

The reason for the split is that `public_key` must be `groups='base.group_system'` (restricted to admin), but the ORM would apply that restriction to the compute method too, causing access errors. By using a direct SQL read in the compute and a no-op inverse, the field value is readable (at the ORM level) by system admins but the actual database column can be written only via the `make_key()` method's direct SQL update.

### Model: `auth.passkey.key.create`

A **TransientModel** wizard used during passkey registration. It holds the user-supplied name for the new passkey and triggers the WebAuthn registration ceremony.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required) | User-provided label for the authenticator |

### `res.users` Extensions

```python
class ResUsers(models.Model):
    _inherit = 'res.users'

    auth_passkey_key_ids = fields.One2many('auth.passkey.key', 'create_uid')
```

This one2many gives each user a list of their registered passkeys. It is included in the session token computation (see [L3: Session Token Management](#l3-session-token-management)), so adding or removing a passkey invalidates all existing sessions.

---

## L3: WebAuthn Registration Flow

The registration flow is initiated when a user clicks "Create Passkey" on their user preferences form. It consists of three phases:

### Phase 1: Start Registration (`_start_registration`)

```python
@api.model
def _start_registration(self):
    registration_options = generate_registration_options(
        rp_id=url_parse(self.get_base_url()).host,   # e.g., "odoo.example.com"
        rp_name='Odoo',
        user_id=str(self.env.user.id).encode(),       # Odoo's internal user ID
        user_name=self.env.user.login,                # Login name shown on device
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED
        )
    )
    request.session['webauthn_challenge'] = registration_options.challenge
    return json.loads(options_to_json(registration_options))
```

**Key parameters:**
- `rp_id` (Relying Party ID) must match the hostname. The authenticator will only use this credential on that exact domain.
- `resident_key=REQUIRED` means the credential is "discoverable" — the authenticator stores the credential ID internally and can authenticate without the user first providing a username. This enables passwordless login flows.
- `user_verification=REQUIRED` means the user must actively verify (e.g., fingerprint, PIN) before the authenticator signs. This prevents someone who steals an unlocked device from using a passive authenticator.

The returned options (excluding the challenge) are sent to the browser, which calls `simplewebauthn`'s `startRegistration()` API. The authenticator generates a new key pair and returns an `attestation` response.

### Phase 2: Verify Registration (`_verify_registration_options`)

```python
@api.model
def _verify_registration_options(self, registration):
    verification = verify_registration_response(
        credential=registration,
        expected_challenge=base64url_to_bytes(self._get_session_challenge()),
        expected_origin=parsed_url.replace(path='').to_url(),
        expected_rp_id=parsed_url.host,
        require_user_verification=True,
    )
    return {
        'credential_id': verification.credential_id,
        'credential_public_key': verification.credential_public_key,
    }
```

The server verifies the attestation by checking:
1. The challenge matches what was stored in session
2. The origin (scheme + host + port) matches the server URL
3. The RP ID matches the expected hostname
4. The authenticator's signature over the registration data is valid
5. User verification was performed (fingerprint/PIN checked)

On success, it returns the `credential_id` and `credential_public_key`.

### Phase 3: Persist Credential (`make_key` wizard method)

```python
def make_key(self, registration=None):
    verification = request.env['auth.passkey.key']._verify_registration_options(registration)

    # Create passkey record through the One2many (triggers session token invalidation)
    self.env.user.write({'auth_passkey_key_ids': [Command.create({
        'name': self.name,
        'credential_identifier': bytes_to_base64url(verification['credential_id']),
    })]})

    passkey = self.env.user.auth_passkey_key_ids[0]
    self.env.cr.execute(SQL(
        "UPDATE auth_passkey_key SET public_key = %s WHERE id = %s",
        base64.urlsafe_b64encode(verification['credential_public_key']).decode(),
        passkey.id,
    ))

    # Invalidate all existing sessions for this user
    new_token = self.env.user._compute_session_token(request.session.sid)
    request.session.session_token = new_token
```

The critical detail is that the record is created **through the One2many** (`auth_passkey_key_ids`) rather than directly on `auth.passkey.key`. This forces the session token cache invalidation path in `res.users.write()` via `_get_invalidation_fields`, which ensures all old sessions are invalidated the moment a new passkey is added.

---

## L3: Authentication Flow (Login)

### Step 1: Credential ID Lookup (`_login`)

When the user submits a WebAuthn assertion at the login screen, the browser sends the credential ID. The server first looks up which user owns that credential:

```python
def _login(self, credential, user_agent_env):
    if credential['type'] == 'webauthn':
        webauthn = json.loads(credential['webauthn_response'])
        self.env.cr.execute(SQL("""
            SELECT login
                FROM auth_passkey_key key
                JOIN res_users usr ON usr.id = key.create_uid
                WHERE credential_identifier=%s
        """, webauthn['id']))
        res = self.env.cr.fetchone()
        if not res:
            raise AccessDenied(_('Unknown passkey'))
        credential['login'] = res[0]
    return super()._login(credential, user_agent_env=user_agent_env)
```

This is a raw SQL join query because the `credential_identifier` field is restricted to `base.group_system` — it cannot be accessed through the ORM in a non-admin context.

### Step 2: Assertion Verification (`_check_credentials`)

After the user is identified, Odoo verifies the authentication assertion:

```python
def _check_credentials(self, credential, env):
    if credential['type'] == 'webauthn':
        webauthn = json.loads(credential['webauthn_response'])
        passkey = self.env['auth.passkey.key'].sudo().search([
            ("create_uid", "=", self.env.user.id),
            ("credential_identifier", "=", webauthn['id']),
        ])
        if not passkey:
            raise AccessDenied(_('Unknown passkey'))

        new_sign_count = self.env['auth.passkey.key']._verify_auth(
            webauthn, passkey.public_key, passkey.sign_count,
        )
        passkey.sign_count = new_sign_count
        return {
            'uid': self.env.user.id,
            'auth_method': 'passkey',
            'mfa': 'skip',           # Bypass MFA when using passkey
        }
    return super()._check_credentials(credential, env)
```

**Key verification checks inside `_verify_auth`:**
- The challenge in the assertion matches the one stored in session
- The origin and RP ID match the server
- The signature over the authenticator data is valid using the stored public key
- The `sign_count` in the assertion is **greater than** the stored counter (prevents replay of cloned credentials)
- User verification was required and performed

### Step 3: WebAuthn Challenge Retrieval

Challenges are single-use and stored in the session:

```python
@api.model
def _get_session_challenge(self):
    challenge = request.session.pop('webauthn_challenge', None)
    if not challenge:
        raise AccessDenied('Cannot find a challenge for this session')
    return challenge
```

The `pop()` call ensures each challenge can only be used once, preventing replay attacks.

---

## L3: Session Token Management

Odoo's session tokens are computed as a hash of the user's credentials. When a passkey is added or removed, existing sessions must be invalidated. This is handled through two mechanisms:

### Mechanism 1: `_get_session_token_fields` (Fields List)

```python
def _get_session_token_fields(self):
    return super()._get_session_token_fields() | {'auth_passkey_key_ids'}
```

By including `auth_passkey_key_ids` in the session token fields, any change to the user's passkey collection will change the computed token, immediately invalidating all sessions that used the old token.

### Mechanism 2: `_get_session_token_query_params` (SQL Join)

```python
def _get_session_token_query_params(self):
    params = super()._get_session_token_query_params()
    params['select'] = SQL(
        "%s, ARRAY_AGG(key.id ORDER BY key.id DESC) FILTER (WHERE key.id IS NOT NULL) as auth_passkey_key_ids",
        params['select']
    )
    params['joins'] = SQL(
        "%s LEFT JOIN auth_passkey_key key ON res_users.id = key.create_uid",
        params['joins']
    )
    return params
```

This SQL-level join ensures that when Odoo validates a session token, it includes the passkey IDs in the hash computation, linking session validity to the current state of the passkey collection.

### Manual Token Recomputation After Delete

```python
def action_delete_passkey(self):
    for key in self:
        if key.create_uid.id == self.env.user.id:
            self.env.user.write({'auth_passkey_key_ids': [Command.delete(key.id)]})
            new_token = self.env.user._compute_session_token(request.session.sid)
            request.session.session_token = new_token
```

---

## L3: Credential Deletion and Invalidation

The `@check_identity` decorator (from `odoo.addons.base.models.res_users`) requires the user to re-authenticate (password or TOTP) before deleting a passkey:

```python
@check_identity
def action_delete_passkey(self):
    for key in self:
        if key.create_uid.id == self.env.user.id:
            self.env.user.write({'auth_passkey_key_ids': [Command.delete(key.id)]})
            new_token = self.env.user._compute_session_token(request.session.sid)
            request.session.session_token = new_token
        else:
            _logger.info("...attempted to delete passkey belonging to another user...")
```

Audit logging records every passkey creation and deletion with the actor's user ID, IP address, and passkey ID.

---

## L4: Security Considerations

### Threat Model and Mitigations

| Threat | Mitigation |
|--------|-----------|
| Cloned authenticator (device copy) | Sign counter (`sign_count`) detects cloning |
| Replay attack (replay of old assertion) | Single-use challenge in session, popped on use |
| Phishing (fake website) | RP ID is hostname-matched; credential IDs are domain-scoped |
| Credential ID enumeration | Credential IDs are 16–256 byte opaque base64URL strings |
| Silently removing passkeys via XSS | `@check_identity` requires password/TOTP before any modification |
| Passkey used on wrong domain | `expected_origin` validation rejects assertions from any other domain |
| Unrestricted public_key read | Field is `groups='base.group_system'`; SQL bypasses ORM group restrictions |

### Credential Storage Security

- The **private key never leaves the authenticator**. It is generated on-device and cannot be exported.
- Only the **public key** is stored in the Odoo database.
- The `credential_identifier` (credential ID) is the lookup key — unique per credential and scoped to the RP ID domain.
- The `sign_count` is stored to detect cloned authenticators. If an assertion arrives with a counter lower than stored, authentication is rejected.

### MFA Bypass Design

The `mfa: 'skip'` return value means passkey users are **not** prompted for a second factor:

| Authentication method | Factors |
|----------------------|---------|
| Password + passkey | Knowledge (password) + possession + biometric (passkey) |
| Password + TOTP | Knowledge (password) + knowledge (code) — vulnerable to phishing |
| Passkey alone | Possession + biometric — phishing-resistant |

### JSON-RPC Controller Endpoint

```python
class WebauthnController(http.Controller):
    @http.route(['/auth/passkey/start-auth'], type='jsonrpc', auth='public')
    def json_start_authentication(self):
        auth_options = request.env['auth.passkey.key']._start_auth()
        return auth_options
```

Returns WebAuthn authentication options (challenge + RP ID + allowed credentials) to the browser. It is `auth='public'` because the user has not yet logged in.

---

## L4: Record Rules and Access Control

Three record rules in `security/security.xml`:

| Rule | Scope | Groups | Permissions |
|------|-------|--------|------------|
| `rule_auth_passkey_key_user` | `[('create_uid', '=', user.id)]` | Portal, User | Read, Write, Create, Unlink (own passkeys only) |
| `rule_auth_passkey_key_create_portal` | `[('create_uid', '=', user.id)]` | Portal, User | Read, Write, Create (own wizard records only) |
| `rule_auth_passkey_key_admin` | `[(1, '=', 1)]` | ERP Manager | Read, Unlink (view/delete any passkey) |

The admin rule explicitly sets `perm_write="0"` and `perm_create="0"`, preventing admins from inserting rogue credentials into other users' accounts.

---

## L4: Module Dependencies and Architecture

```
base_setup/                 (required: provides user preferences UI)
    │
    └── web/               (required: JSON-RPC controller + session support)
           │
           └── auth_passkey/
                  ├── auth.passkey.key              (passkey storage)
                  ├── auth.passkey.key.create        (registration wizard)
                  └── res.users (extended)           (login hooks + session tokens)
```

### Comparison with auth_totp

| Aspect | [auth_totp](Modules/auth_totp.md) | auth_passkey |
|--------|---------------------------|-------------|
| Protocol | TOTP (RFC 6238) | FIDO2/WebAuthn |
| Secret storage | Server-side (encrypted in DB) | Device-side (private key never leaves authenticator) |
| Phishing resistance | Low (codes can be phished) | High (RP ID binding) |
| Hardware key support | No | Yes (YubiKey, etc.) |
| MFA bypass | No | Yes (passkey replaces both factors) |

---

## Related

- [Modules/auth_totp](Modules/auth_totp.md) — TOTP-based two-factor authentication
- [Modules/auth_totp_mail](Modules/auth_totp_mail.md) — TOTP enforcement via email
- [New Features/What's New](New%20Features/What's%20New.md) — Odoo 19 authentication changes
- [Patterns/Cross-Module-Integration](Cross-Module-Integration.md) — How `auth_passkey` connects to the web authentication stack
