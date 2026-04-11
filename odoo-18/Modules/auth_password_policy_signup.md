---
Module: auth_password_policy_signup
Version: 18.0
Type: addon
Tags: #auth, #signup, #security
---

# auth_password_policy_signup — Password Policy for Signup

## Module Overview

**Category:** Hidden/Tools
**Depends:** `auth_password_policy`, `auth_signup`
**License:** LGPL-3
**Auto-install:** True

Extends the `auth_signup` registration form with password policy enforcement. Adds the password strength meter and minimum length requirement to the signup page. Reuses the same JS assets as `auth_password_policy_portal`.

## Data Files

- `views/signup_templates.xml` — Modified signup form templates with password policy UI

## Static Assets (web.assets_frontend)

- `auth_password_policy_signup/static/src/public/**/*` — public-facing assets for signup
- `auth_password_policy/static/src/password_meter.js` — shared password strength indicator
- `auth_password_policy/static/src/password_policy.js` — shared policy enforcement logic

## What It Extends

### Controllers

#### `AddPolicyData` (extends `auth_signup.controllers.main.AuthSignupHome`)

**`get_auth_signup_config()`**
Extends the parent method to add `password_minimum_length` to the signup configuration JSON returned to the frontend, enabling the password strength meter on the signup form.

### Models

No server-side Python models. Pure bridge module.

### `ir.http`

**`_get_translation_frontend_modules_name()`**
Adds `'auth_password_policy'` to the frontend translation module list.

## What It Extends

- `auth_signup.AuthSignupHome.get_auth_signup_config` — injects password policy config into signup response
- `ir.http._get_translation_frontend_modules_name` — registers for i18n

## Key Behavior

- Reuses `auth_password_policy.minlength` ir.config_parameter for the minimum length threshold.
- Both the password meter JS and policy check JS are loaded on the signup page via web.assets_frontend.

## See Also

- `auth_password_policy` — base password policy module (defines the config parameter)
- `auth_signup` — signup controller
- [[Modules/Auth Password Policy Portal]] (`auth_password_policy_portal`) — portal equivalent
