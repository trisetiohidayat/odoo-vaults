---
type: module
module: auth_passkey_portal
tags: [odoo, odoo19, auth, security, passkey, portal]
created: 2026-04-06
---

# Auth Passkey Portal

## Overview
| Property | Value |
|----------|-------|
| **Name** | Passkeys Portal |
| **Technical** | `auth_passkey_portal` |
| **Category** | Hidden/Tools |
| **Depends** | `auth_passkey`, `portal` |
| **License** | LGPL-3 |

## Description
Extends `auth_passkey` to allow portal users to register and use passkeys for authentication. Integrates passkey registration and login flows with the portal (website login) experience.

## Technical Notes
- No additional models; purely an extension of `auth_passkey` for portal context.
- Depends on `portal` module for portal user access.
