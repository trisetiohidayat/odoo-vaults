---
Module: auth_password_policy_portal
Version: 18.0
Type: addon
Tags: #auth, #portal, #security
---

# auth_password_policy_portal — Password Policy for Portal Users

## Module Overview

**Category:** Tools
**Depends:** `auth_password_policy`, `portal`
**License:** LGPL-3
**Auto-install:** True

Extends the portal user account page to display the password minimum length requirement from `auth_password_policy` configuration. Integrates the client-side password meter (JS) into the portal frontend.

## Data Files

- `views/templates.xml` — QWeb templates for password policy display on portal pages

## Static Assets (web.assets_frontend)

- All files under `static/src/**/*` — client-side JS/CSS for password strength display

## What It Extends

### `auth_password_policy` — Frontend Integration for Portal

Adds password policy configuration display to portal-facing pages.

### Models

No server-side Python models. Purely a bridge module for frontend assets and templates.

### Controllers

#### `CustomerPortalPasswordPolicy` (extends `portal.CustomerPortal`)

**`_prepare_portal_layout_values()`**
Injects `password_minimum_length` into the portal layout values dict (available to all portal pages), sourced from `ir.config_parameter` key `auth_password_policy.minlength`.

#### `IrHttp`

**`_get_translation_frontend_modules_name()`**
Adds `'auth_password_policy'` to the list of modules whose strings are extracted for frontend translation.

## What It Extends

- `portal.CustomerPortal._prepare_portal_layout_values` — adds password policy config to portal context
- `ir.http._get_translation_frontend_modules_name` — registers for i18n

## See Also

- [Modules/Auth Signup](Modules/Auth-Signup.md) (`auth_signup`) — signup flow
- `auth_password_policy` — base password policy module
- [Modules/Portal](odoo-18/Modules/portal.md) — portal controller base
