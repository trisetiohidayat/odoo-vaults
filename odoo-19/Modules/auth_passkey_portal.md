---
type: module
module: auth_passkey_portal
tags: [odoo, odoo19, auth, security, passkey, portal]
created: 2026-04-06
updated: 2026-04-14
---

# auth_passkey_portal

**Tags:** `#odoo` `#odoo19` `#modules` `#auth` `#security` `#passkey` `#portal`

## Overview

The `auth_passkey_portal` module extends the core `auth_passkey` module to allow **portal users** (external customers, vendors, and other stakeholders who access Odoo through the website portal) to register and use passkeys as their authentication method. It is a thin integration module that adds a portal-specific QWeb template to the portal user's security settings page, enabling passkey management for non-internal users.

```
Dependency chain:
  auth_passkey (core passkey implementation)
       ↑
  auth_passkey_portal (portal UI extension)
       ↑
  auth_passkey + portal (combined)
```

**Module Metadata:**

| Attribute | Value |
|-----------|-------|
| `_name` | `auth_passkey_portal` |
| Category | `Hidden/Tools` |
| Depends | `auth_passkey`, `portal` |
| License | `LGPL-3` |
| Auto-install | `True` |
| Version | `1.0` |

---

## L1: Module Structure

### File Structure

```
auth_passkey_portal/
├── __init__.py              # Empty (no Python code in this module)
├── __manifest__.py          # Module metadata, depends + assets
├── views/
│   └── templates.xml        # Portal QWeb template inheritance
└── tests/
    └── test_passkey_portal.py  # Portal-specific passkey tests
```

### What This Module Does NOT Contain

`auth_passkey_portal` is intentionally minimal. All the heavy lifting is done by its dependencies:

- **`auth_passkey`** provides:
  - The `auth.passkey.key` model (passkey credentials storage)
  - The `auth.passkey.key.create` wizard (passkey registration)
  - WebAuthn protocol implementation via the bundled `_vendor/webauthn/` library
  - Backend controllers for passkey registration/verification
  - `res.users` extensions for passkey login flow

- **`portal`** provides:
  - The `portal.portal_my_security` template (security settings page)
  - Portal user session management
  - Website authentication controllers

### What This Module DOES Add

The only meaningful contribution of `auth_passkey_portal` is a **QWeb template extension** in `views/templates.xml` that injects a "Passkeys" management section into the portal user's security settings page (`portal.portal_my_security`).

---

## L2: The Portal Security Template Extension

**File:** `views/templates.xml`

### Template Inheritance

The module uses QWeb inheritance (`inherit_id="portal.portal_my_security"`) to inject its content at a specific XPath location:

```xml
<template id="passkeys_portal_hook" name="Passkeys Portal hook"
          inherit_id="portal.portal_my_security">
    <xpath expr="//section[@name='portal_revoke_all_devices_popup']" position="before">
        <section name="portal_passkey_management">
            ... passkey management table and button ...
        </section>
    </xpath>
</template>
```

This inserts the "Passkeys" section immediately before the "portal_revoke_all_devices_popup" section on the portal security page.

### Injected Content

The extended template renders:

1. **A table of registered passkeys** for the portal user:
   - Column: Name (editable via pencil icon)
   - Column: Created date
   - Column: Last Used date
   - Column: Rename button (pencil icon, `o_passkey_portal_rename`)
   - Column: Delete button (trash icon, `o_passkey_portal_delete`)
   
   The table iterates over `user_id.auth_passkey_key_ids`, which is the one2many relation from `res.users` to `auth.passkey.key`.

2. **An "Add Passkey" button** with id `portal_passkey_add`:
   ```xml
   <button type="button" class="btn btn-light mt-1" id="portal_passkey_add">
       Add Passkey
   </button>
   ```

### CSS Classes Used

| Class | Purpose |
|-------|---------|
| `o_passkey_portal_entry` | Row container with `t-att-id="key.id"` for JS targeting |
| `o_passkey_name` | Display name field in the table |
| `o_passkey_portal_rename` | Icon button for rename action |
| `o_passkey_portal_delete` | Icon button for delete action |

---

## L3: The auth.passkey.key Model

Since `auth_passkey_portal` does not define any models, it relies entirely on the `auth.passkey.key` model from `auth_passkey`.

### Model: `auth.passkey.key`

**File:** `auth_passkey/models/auth_passkey_key.py`

#### Fields

| Field | Type | Store | Purpose |
|-------|------|-------|---------|
| `name` | `Char` | Yes | Human-readable name assigned by user |
| `credential_identifier` | `Char` | Yes | Unique credential ID from WebAuthn (base64url encoded) |
| `public_key` | `Char` | Yes | Stored as VARCHAR, accessed via `_compute_public_key` |
| `sign_count` | `Integer` | Yes | WebAuthn sign counter (prevents replay attacks) |
| `create_uid` | `Many2one` | Yes | User who created the passkey |

#### Key Methods

| Method | Scope | Purpose |
|--------|-------|---------|
| `_start_registration()` | `@api.model` | Generate WebAuthn registration options (challenge, RP info) |
| `_verify_registration_options()` | `@api.model` | Verify passkey registration response, return credential data |
| `_start_auth()` | `@api.model` | Generate WebAuthn authentication options |
| `_verify_auth()` | `@api.model` | Verify authentication response, update sign_count |
| `action_delete_passkey()` | Instance | Delete passkey (requires identity verification via `@check_identity`) |
| `action_rename_passkey()` | Instance | Open rename dialog |

#### WebAuthn Protocol Flow

```
Step 1: User clicks "Add Passkey" in portal
  ↓ JS calls backend to get registration options
Step 2: _start_registration()
  - Generates challenge (random bytes)
  - Stores challenge in session as 'webauthn_challenge'
  - Returns registration options (RP ID, user info, challenge)
  ↓ Browser creates passkey using platform authenticator
Step 3: _verify_registration_options()
  - Retrieves challenge from session
  - Verifies attestation
  - Stores credential_id and public_key
Step 4: User can now login with passkey
  ↓ JS calls backend for authentication options
Step 5: _start_auth()
  - Generates challenge
  - Stores in session
  - Returns authentication options
Step 6: User uses passkey to sign challenge
  ↓ _verify_auth()
  - Verifies assertion signature
  - Updates sign_count
  - User is authenticated
```

---

## L4: Portal User Experience

### How Portal Users Access Passkey Management

1. Portal user logs in to the Odoo website (portal).
2. Navigates to their account/security settings.
3. Sees the "Passkeys" section added by this module.
4. Can view all registered passkeys (name, created, last used).
5. Can add a new passkey via "Add Passkey" button.
6. Can rename or delete existing passkeys.

### Relationship: res.users

The `auth.passkey.key` model is linked to `res.users` via `create_uid`. The portal user can only see and manage their own passkeys:

```python
# In portal template:
t-foreach="user_id.auth_passkey_key_ids" t-as="key"
```

This iterates only over passkeys created by the current portal user.

### Identity Verification for Deletion

The `action_delete_passkey()` method is decorated with `@check_identity`, which requires the user to re-authenticate (typically via password) before deleting a passkey. This prevents unauthorized deletion if someone gains temporary access to an authenticated session.

```python
@check_identity
def action_delete_passkey(self):
    for key in self:
        if key.create_uid.id == self.env.user.id:
            # Delete via Command on user's auth_passkey_key_ids
            # This properly invalidates the session token cache
            self.env.user.write({
                'auth_passkey_key_ids': [Command.delete(key.id)]
            })
```

### Security: Ownership Verification

When deleting, the code checks `key.create_uid.id == self.env.user.id` to ensure portal users can only delete their own passkeys. An attempt to delete another user's passkey is logged:

```python
_logger.info(
    "%s (#%d) attempted to delete passkey (#%d) belonging to %s (#%d)...",
    ...
)
```

---

## L5: WebAuthn and Passkey Technology

### What are Passkeys?

Passkeys are a passwordless authentication standard built on the **WebAuthn** (Web Authentication) API. Instead of a password, users register a cryptographic key pair with the website. The private key stays on their device (phone, laptop, security key), while the public key is stored by the website.

### How It Works in Odoo

1. **Registration**: When a user adds a passkey, their authenticator (Face ID, Touch ID, Windows Hello, etc.) generates a new key pair and registers the public key with Odoo.

2. **Authentication**: When logging in, Odoo sends a challenge. The user's device signs the challenge with the private key. Odoo verifies the signature using the stored public key.

3. **Security properties**:
   - No password to steal orphish
   - Private key never leaves the device
   - Resistant to replay attacks (via sign_count)
   - Resistant to man-in-the-middle attacks

### Odoo's WebAuthn Implementation

Odoo bundles a Python WebAuthn library (`auth_passkey/_vendor/webauthn/`) containing:
- `generate_authentication_options()` / `generate_registration_options()`
- `verify_authentication_response()` / `verify_registration_response()`
- Helpers for base64url encoding, CBOR parsing, TPM attestation, etc.

The frontend uses the `simplewebauthn` JavaScript library (`auth_passkey/static/lib/simplewebauthn.js`).

### Resident Key Requirement

Odoo requires `resident_key=ResidentKeyRequirement.REQUIRED`, meaning:
- The passkey can be used without entering a username
- The passkey stores the credential ID locally, allowing "passwordless" login on the same device

---

## L6: Auto-Install Behavior

`auth_passkey_portal` has `auto_install: True`. This means when both `auth_passkey` AND `portal` are installed (or upgraded together), this module will automatically be installed too. This ensures portal users automatically get passkey management in their security settings without manual intervention.

The auto-install chain:
```
user installs: auth_passkey + portal
       ↓
Odoo resolves dependencies: auth_passkey_portal (auto)
       ↓
auth_passkey_portal is installed automatically
       ↓
Portal users see Passkeys section in their security settings
```

---

## L7: Related Modules

| Module | Relationship | Description |
|--------|-------------|-------------|
| [Core/Auth Patterns](Core/Authentication.md) | Parent concept | WebAuthn, 2FA, session management |
| `auth_totp_mail` | Related auth | TOTP via email (2FA alternative) |
| `auth_totp` | Related auth | TOTP via authenticator app |
| `portal` | Dependency | Portal user access and templates |
| `auth_passkey` | Dependency | Core passkey model and WebAuthn logic |

---

## See Also

- [[Modules/Auth Totp Mail]] — TOTP via email for internal users
- [[Modules/Auth Totp]] — TOTP authenticator app for internal users
- [[Patterns/Security Patterns]] — ACL, record rules, authentication patterns
- [[Core/Authentication]] — Odoo's authentication framework
