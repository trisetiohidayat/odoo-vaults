# auth_totp_portal

Odoo 19 Security/Authentication Module

## Overview

`auth_totp_portal` extends `auth_totp` (TOTP two-factor authentication) for **portal users**. Enables portal customers to use authenticator apps for 2FA when accessing their customer portal.

## Module Details

- **Category**: Hidden
- **Depends**: `portal`, `auth_totp`
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Auto-install**: Yes

## Key Features

- Adds 2FA TOTP capability to the portal authentication flow.
- Portal users can enroll trusted devices for 2FA from their **My Account > Security** page.
- Portal 2FA redirect URL differs from internal users (goes to `/my/security` instead of `/odoo`).
- Frontend assets for TOTP enrollment and verification UI on the portal.

### Models

#### `res.users` (Inherited)

`get_totp_invite_url()` — Returns `/my/security` (portal security page) for non-internal users instead of the admin settings URL.

## Technical Notes

- Portal 2FA uses the same `auth_totp` mechanism as internal users (TOTP with trusted devices).
- No separate TOTP mail code (email-based) for portal — relies on authenticator app only.
- Security notifications for new connections are sent to portal users as well.
