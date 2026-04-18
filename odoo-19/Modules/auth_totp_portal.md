---
uuid: auth-totp-portal-001
module: auth_totp_portal
type: module
tags: [odoo, odoo19, security, authentication, 2fa, totp, portal]
---

# auth_totp_portal

> **Source location:** `~/odoo/odoo19/odoo/addons/auth_totp_portal/`

## Overview

- **Name:** TOTPortal
- **Category:** Hidden
- **Depends:** `portal`, `auth_totp`
- **Auto-install:** `True` — automatically installed when both `portal` and `auth_totp` are installed
- **Author:** Odoo S.A.
- **License:** LGPL-3

`auth_totp_portal` extends the `auth_totp` (Time-based One-Time Password) module to support **portal users**. It enables external customers and vendors who authenticate via the customer portal to enroll a TOTP authenticator app (Google Authenticator, Authy, etc.) as a second authentication factor. Portal users do not have access to the Odoo backend settings, so they enroll 2FA from their portal **My Account > Security** page instead.

## Dependency Graph

```
auth_totp_portal
├── depends: portal         ← Portal user management, /my/* routes
└── depends: auth_totp       ← TOTP engine (wizard, trusted devices, secret key storage)
         └── depends: base   ← res.users, base security

auth_totp (server side)
├── auth_totp.models.auth_totp_device  ← stores TOTP secrets (irreversibly encrypted)
└── auth_totp.models.res_users        ← adds totp_enabled, totp_trusted_device_ids fields

auth_totp_portal (portal extension)
├── auth_totp_portal.models.res_users    ← overrides get_totp_invite_url()
└── auth_totp_portal.controllers.portal  ← enables TOTP enrollment from /my/security
```

## Module Components

| File | Type | Purpose |
|------|------|---------|
| `models/res_users.py` | Python | Overrides `get_totp_invite_url()` for non-internal users |
| `controllers/portal.py` | Python | (Empty init; TOTP portal uses standard portal controller) |
| `views/templates.xml` | QWeb | Inherits `portal.portal_my_security` to add TOTP section |
| `security/security.xml` | ACL | Grants `base.group_portal` full access to `auth_totp.wizard` |
| `static/src/**/*` | JS/CSS | TOTP enrollment UI (QR code display, enable/disable buttons) |

## Key Mechanism: `get_totp_invite_url()` Override

The critical piece of this module is a single method override in `models/res_users.py`:

```python
class ResUsers(models.Model):
    _inherit = 'res.users'

    def get_totp_invite_url(self):
        if not self._is_internal():
            return '/my/security'      # Portal: redirect to portal security page
        else:
            return super().get_totp_invite_url()  # Backend: /auth_totp/install_totp
```

**Why this matters:**

| User Type | `_is_internal()` | `get_totp_invite_url()` returns | Behavior |
|-----------|-----------------|--------------------------------|---------|
| Internal user (employee) | `True` | `/auth_totp/install_totp` | Backend TOTP enrollment page |
| Portal user | `False` | `/my/security` | Portal Security page |

The `_is_internal()` method returns `True` for users in the `base.group_user` group and `False` for portal users (typically `base.group_portal`).

This override is triggered when a user clicks "Enable two-factor authentication" from either the Odoo backend user form or the portal security page. The backend route in `auth_totp` (`/auth_totp/install_totp`) is **not accessible to portal users** — they are redirected to `/my/security` instead.

## TOTP Enrollment Flow (Portal)

### Step-by-Step: How a Portal User Enrolls TOTP

```
1. Portal user visits /my/security
   → portal.portal_my_security template renders

2. Template inheritance (templates.xml):
   auth_totp_portal.totp_portal_hook extends portal.portal_my_security
   → Adds TOTP section after the "Change Password" section

3. If TOTP not enabled:
   User sees "Two-factor authentication not enabled" alert
   Clicks "Enable two-factor authentication" button
   → Triggers JavaScript handler: #auth_totp_portal_enable

4. JavaScript calls Odoo RPC:
   POST /web/auth/validate_totp_invite   (auth_totp handles this)
   → Server generates a new TOTP secret, stores in auth_totp_device
   → Server returns a QR code (TOTP URI + secret)

5. User scans QR code with authenticator app (Google Authenticator, Authy, etc.)

6. User enters 6-digit code from app
   → POST /web/auth/validate_totp_code
   → auth_totp verifies code against stored secret
   → On success: user record marked totp_enabled = True
   → Trusted device (current browser) is recorded in auth_totp_device

7. On next login:
   After password, user prompted for 6-digit TOTP code
   → Verified against stored secret
```

### Difference from Backend TOTP Enrollment

| Aspect | Backend (`auth_totp`) | Portal (`auth_totp_portal`) |
|--------|----------------------|------------------------------|
| Enrollment URL | `/auth_totp/install_totp` | `/my/security` |
| Route access | Backend users only | Portal users only |
| TOTP wizard | Standalone QWeb form | Embedded in portal security page |
| Secret generation | Same (`auth_totp` engine) | Same (`auth_totp` engine) |
| Device model | `auth_totp.device` (irreversibly encrypted secret) | Same |
| TOTP mail code | Supported (sends email) | Not supported (portal has no email 2FA) |
| Trusted devices | Supported | Supported |
| Security notifications | Supported | Supported |

## Portal Security Template Extension (`views/templates.xml`)

```xml
<template id="totp_portal_hook" name="TOTP Portal hook"
          inherit_id="portal.portal_my_security">
    <xpath expr="//section[@name='portal_change_password']" position="after">
        <!-- Embed auth_totp wizard QWeb form as hidden div for JS access -->
        <div class="d-none" id="totp_wizard_view">
            <t t-esc="env.ref('auth_totp.view_totp_wizard').sudo().get_combined_arch()"/>
        </div>

        <section>
            <h4>Two-factor authentication ...</h4>

            <!-- NOT enabled: show enable button -->
            <t t-if="not user_id.totp_enabled">
                <div class="alert alert-secondary">Two-factor authentication not enabled</div>
                <button type="button" class="btn btn-light"
                        id="auth_totp_portal_enable">
                    Enable two-factor authentication
                </button>
            </t>

            <!-- Enabled: show status + disable + trusted devices -->
            <t t-else="">
                <span class="text-success"><i class="fa fa-check-circle"/>
                    Two-factor authentication enabled
                </span>
                <button type="button" class="btn btn-link"
                        id="auth_totp_portal_disable">
                    (Disable two-factor authentication)
                </button>

                <!-- Trusted devices table -->
                <t t-if="len(user_id.totp_trusted_device_ids)">
                    <table class="table o_main_table">
                        <thead>
                            <tr>
                                <th>Trusted Device</th>
                                <th>Added On</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr t-foreach="user_id.totp_trusted_device_ids" t-as="td">
                                <td><span t-field="td.name"/></td>
                                <td><span t-field="td.create_date"/></td>
                                <td><i class="fa fa-trash text-danger" t-att-id="td.id"/></td>
                            </tr>
                        </tbody>
                    </table>
                    <button class="btn btn-primary" type="button"
                            id="auth_totp_portal_revoke_all_devices">
                        Revoke All
                    </button>
                </t>
            </t>
        </section>
    </xpath>
</template>
```

**Key design decision:** The TOTP wizard QWeb form is embedded as a hidden `<div id="totp_wizard_view">` inside the portal page. This allows the JavaScript to call `get_combined_arch()` on the wizard view without navigating away from the portal security page. The wizard itself renders in a modal/dialog.

## Security ACL (`security/security.xml`)

```xml
<record model="ir.model.access" id="access_auth_totp_portal_wizard">
    <field name="name">auth_totp_portal wizard access rules</field>
    <field name="model_id" ref="auth_totp.model_auth_totp_wizard"/>
    <field name="group_id" ref="base.group_portal"/>
    <field name="perm_read">1</field>
    <field name="perm_write">1</field>
    <field name="perm_create">1</field>
    <field name="perm_unlink">1</field>
</record>
```

This grants portal users **full CRUD access** to the `auth_totp.wizard` model (the model behind the TOTP enrollment wizard). Without this ACL, portal users would get an `AccessError` when trying to enroll.

## TOTP Secret Storage (`auth_totp` Module)

The actual secret storage is handled by `auth_totp` (not `auth_totp_portal`):

```python
# auth_totp/models/auth_totp_device.py
class AuthTotpDevice(models.Model):
    _name = 'auth_totp.device'
    _description = 'TOTP Device'

    name = fields.Char(...)          # Device name (e.g., "Chrome on MacBook")
    user_id = fields.Many2one(...)   # Owner (portal user)
    key = fields.Binary(...)         # TOTP secret (encrypted, irreversible)
    secret = fields.Char(...)        # Crypted/encrypted TOTP secret

    @api.model
    def _generate_secret(self):
        """Generate a new TOTP secret using pyotp."""
        import pyotp
        return pyotp.random_base32()
```

**Important:** The `key` field stores the TOTP secret irreversibly encrypted. There is **no way to retrieve the plain secret** after enrollment — this is by design for security. Users who lose their authenticator app must **revoke all trusted devices** and re-enroll.

## `res.users` Extensions (from `auth_totp`)

`auth_totp` adds these fields to `res.users`:

| Field | Type | Description |
|-------|------|-------------|
| `totp_enabled` | Boolean | Whether TOTP is active for this user |
| `totp_trusted_device_ids` | One2many (`auth_totp.device`) | Trusted devices (browser/app pairs) |

These fields are accessible to portal users through the portal security template.

## Portal vs Backend TOTP Differences

| Feature | Backend | Portal |
|---------|---------|--------|
| Enroll URL | `/auth_totp/install_totp` | `/my/security` |
| Wizard location | Standalone page | Embedded in portal security page |
| Email 2FA code | Supported (`auth_totp_mail`) | Not supported |
| Security notification | Yes | Yes (to portal user's email) |
| Groups check | `_is_internal() = True` | `_is_internal() = False` |
| ACL for wizard | Default ACL (user is admin) | Explicit ACL in `security.xml` |

## Related Modules

| Module | Role |
|--------|------|
| [[Modules/auth_totp|auth_totp]] | Core TOTP engine: secret generation, verification, trusted devices |
| [[Modules/auth_totp_mail|auth_totp_mail]] | Email-based 2FA backup codes (backend only) |
| [[Modules/auth_totp_portal|auth_totp_portal]] | Portal TOTP enrollment (this module) |
| [[Modules/auth_totp_practical|auth_totp_practical]] | Enhanced TOTP UX, brute-force protection |
| [[Modules/auth_passkey|auth_passkey]] | Passkey/WebAuthn as alternative to TOTP |
| [[Modules/portal|portal]] | Portal framework, `/my/*` routes, `portal_my_security` template |

## Security Considerations

1. **Secret irreversibility:** The TOTP secret is stored encrypted with no decryption path. Loss of authenticator app = must re-enroll.

2. **Trusted devices:** A trusted device can skip TOTP challenge for a configurable period. Portal users can revoke their own trusted devices.

3. **Brute-force protection:** `auth_totp` implements rate limiting on TOTP code verification to prevent brute-force attacks (6-digit code = 1,000,000 combinations).

4. **Portal ACL:** Without `access_auth_totp_portal_wizard`, portal users cannot enroll because they lack access to the `auth_totp.wizard` model.

5. **No email 2FA for portal:** Portal users do not get email-based 2FA (no `auth_totp_mail` integration). If they lose their authenticator, they must contact support to reset their TOTP enrollment.

6. **`_is_internal()` check:** The `get_totp_invite_url()` override uses the internal Odoo method `_is_internal()`. This method checks whether the user belongs to `base.group_user` (internal/employee) vs `base.group_portal`. It is the authoritative gate for internal vs portal users in Odoo.

## Notes

- **Auto-installs with `auth_totp` and `portal`:** When both dependencies are installed, `auth_totp_portal` installs automatically because `auto_install: True` and the dependencies are satisfied.
- **No Python controller override:** `auth_totp_portal` does not add any HTTP routes. It only modifies the QWeb template that `portal.portal_my_security` renders, and overrides the `get_totp_invite_url()` model method.
- **JavaScript is loaded via `web.assets_frontend`:** The TOTP enrollment JS runs in the portal frontend, not the backend.
- **Inherited from `portal.portal_my_security`:** The parent template is defined by the `portal` module and provides the overall portal "My Account" page structure (change password, personal info, etc.).

## Login Flow Comparison: Internal vs Portal

### Internal User Login (with TOTP)

```
1. User visits Odoo backend: /web
2. Enter login + password → POST /web/login
3. Password verified → check totp_enabled on res.users
4. If totp_enabled:
   → Render TOTP challenge page (/auth_totp/verify)
   → User enters 6-digit code from authenticator app
   → POST /auth_totp/verify
   → auth_totp.models.res_users._verify_totp_pin(user, code)
   → Success → create session → redirect to /web
5. If totp_enabled and trusted device cookie:
   → Skip TOTP challenge → create session → redirect to /web
```

### Portal User Login (with TOTP via auth_totp_portal)

```
1. User visits portal: /my
2. Enter login + password → /web/login (same endpoint)
3. Password verified → check totp_enabled on res.users
4. If totp_enabled:
   → Render TOTP challenge page (same auth_totp verify endpoint)
   → User enters 6-digit code
   → POST /auth_totp/verify
   → Success → create session → redirect to /my
5. If trusted device cookie:
   → Skip TOTP challenge → create session → redirect to /my
```

**Key insight:** The actual TOTP verification is handled entirely by `auth_totp`. `auth_totp_portal` only changes **where the user enrolls** (not how they log in).

## `_is_internal()` Method

This method from `auth_totp` (and base Odoo) determines whether a user is internal or portal:

```python
# auth_totp/models/res_users.py (inherited from base)
def _is_internal(self):
    """Return True if this user is internal (employee), False if portal."""
    return self.has_group('base.group_user')
```

- `base.group_user` = internal employees (access to backend)
- `base.group_portal` = external portal users (access to /my/* only)
- A user can technically belong to both groups, but in standard Odoo configuration, a portal user belongs only to `base.group_portal`.

## TOTP Secret Generation and Storage

The secret is generated and stored by `auth_totp`:

```python
# auth_totp/models/auth_totp_wizard.py
import pyotp

class AuthTotpWizard(models.TransientModel):
    def _generate_secret(self):
        """Generate a random 32-character base32 TOTP secret."""
        return pyotp.random_base32()

    def action_enable(self):
        secret = self._generate_secret()
        # Store irreversibly encrypted
        self.env.user.write({
            'totp_enabled': True,
        })
        # Create the device record (stores the secret)
        self.env['auth_totp.device'].create({
            'name': self.env.user.name + "'s device",
            'user_id': self.env.user.id,
            'key': self.env['auth_totp.device']._encrypt_secret(secret),
        })
        return self._make_qr_code(secret)
```

The TOTP URI (used in the QR code) follows the **Key URI Format**:

```
otpauth://totp/{issuer}:{account}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30
```

- `issuer`: Usually the Odoo database name or configured company name
- `account`: User's login (email)
- `secret`: The 32-character base32 secret
- `period`: 30 seconds (standard TOTP)
- `digits`: 6 (standard)
- `algorithm`: SHA1 (standard, compatible with all authenticator apps)

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Portal user cannot see TOTP section | `auth_totp_portal` not installed | Install `auth_totp_portal` module |
| "Access Error" when clicking Enable | Missing ACL | Check `access_auth_totp_portal_wizard` exists in `security.xml` |
| QR code does not scan | Clock skew | Ensure IoT box/server clocks are synchronized (NTP) |
| TOTP codes always wrong | Clock skew, wrong account | Re-enroll: disable → revoke all devices → re-enable |
| Portal user redirected to backend | `_is_internal()` returns True | User must be in `base.group_portal`, not `base.group_user` |

## Auto-Install Logic

The `auto_install: True` flag in the manifest works because:

```python
# __manifest__.py
'auto_install': True,
'depends': ['portal', 'auth_totp'],
```

Odoo's auto-install resolver checks: if both `portal` AND `auth_totp` are installed (or will be installed), then `auth_totp_portal` must also be installed to satisfy its dependencies. This ensures the TOTP portal extension is always present when both prerequisites are active.

## File Reference

| Path | Lines | Purpose |
|------|--------|---------|
| `models/res_users.py` | 14 | `get_totp_invite_url()` override |
| `views/templates.xml` | 67 | QWeb template extending `portal.portal_my_security` |
| `security/security.xml` | 12 | ACL granting portal users access to `auth_totp.wizard` |
| `static/src/**/*` | JS/CSS | TOTP enrollment/disable/revoke UI |

## Related Documentation

- [[Modules/auth_totp|auth_totp]] — Core TOTP engine (secret generation, verification, trusted devices)
- [[Modules/auth_totp_mail|auth_totp_mail]] — Email-based 2FA (backup codes, backend only)
- [[Modules/auth_passkey|auth_passkey]] — Passkey/WebAuthn alternative to TOTP
- [[Modules/portal|portal]] — Portal framework, `/my/*` routes
