---
type: module
module: auth_password_policy_signup
tags: [odoo, odoo19, auth, security, password, signup, web]
created: 2026-04-06
uuid: d4c3e5f6-7a8b-9012-cdef-123456789012
---

# Auth Password Policy Signup

## Overview

| Property | Value |
|----------|-------|
| **Name** | Password Policy support for Signup |
| **Technical** | `auth_password_policy_signup` |
| **Category** | Hidden/Tools |
| **Depends** | `auth_password_policy`, `auth_signup` |
| **Auto-install** | True |
| **License** | LGPL-3 |

## What It Does

`auth_password_policy_signup` is a thin glue module that bridges the password policy enforcement system (from the base `auth_password_policy` module) to the **self-registration (signup)** user flow provided by `auth_signup`. Like its sibling module [Modules/auth_password_policy_portal](auth_password_policy_portal.md), it adds no Python model code. Instead it overrides the signup controller's `get_auth_signup_config()` method to pass the configured `password_minimum_length` into the template context, and uses QWeb XML inheritance to inject a visual password-strength `<Meter>` Owl component and a dynamic `minlength` HTML attribute onto the password field in the signup form.

The module is `auto_install: True`. This means that whenever a database has both `auth_password_policy` and `auth_signup` installed but not `auth_password_policy_signup`, Odoo automatically installs it. This ensures that any database enabling both the password policy and the signup feature will automatically get the policy UI on the signup page.

## Module Structure

```
auth_password_policy_signup/
├── __init__.py                      # Imports controllers and models submodules
├── __manifest__.py                  # Metadata; includes assets for frontend JS
├── controllers.py                   # Extends AuthSignupHome to pass policy config
├── models/
│   ├── __init__.py                 # Imports ir_http
│   └── ir_http.py                  # Registers auth_password_policy for translation
├── views/
│   └── signup_templates.xml         # QWeb extension: adds meter + minlength
└── static/
    └── src/
        └── public/
            └── components/
                └── password_meter/
                    └── password_meter.xml   # Owl component template for signup
```

### `__manifest__.py`

```python
{
    'name': "Password Policy support for Signup",
    'depends': ['auth_password_policy', 'auth_signup'],
    'category': 'Hidden/Tools',
    'auto_install': True,
    'data': [
        'views/signup_templates.xml',
    ],
    'assets': {
        # Load this module's static JS and the base auth_password_policy JS
        # into the web.assets_frontend bundle (the website/portal frontend)
        'web.assets_frontend': [
            'auth_password_policy_signup/static/src/public/**/*',
            'auth_password_policy/static/src/password_meter.js',
            'auth_password_policy/static/src/password_policy.js',
        ],
    },
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

Key aspects:
- **`category: 'Hidden/Tools'`**: The module does not appear in the Apps list by default (useful for infrastructure modules).
- **`assets`**: Explicitly loads the frontend JavaScript bundle. The `auth_password_policy_signup/static/src/public/**/*` path loads the module's own static files, while the two references to `auth_password_policy/static/src/*.js` pull in the shared password meter widget and strength-evaluator logic.
- The `<Meter>` Owl component itself is defined in `auth_password_policy/static/src/password_meter.xml`, but the **template** that uses it for the signup context is provided here as `static/src/public/components/password_meter/password_meter.xml`.

## Architecture: How the Pieces Fit Together

```
auth_password_policy          auth_password_policy_signup        auth_signup
(base module, no UI)               (this module)              (self-registration)
      |                                   |                        |
      | ir.config_parameter               |                        |
      | stores: auth_password_policy.     |                        |
      | minlength (integer)                |                        |
      |                                   |                        |
      |                      +-----------+-------------------->   |
      |                      |  get_auth_signup_config()         |
      |                      |  injects password_minimum_length |
      |                      |  into template context            |
      |                                   |                        |
      |                                   |   auth_signup.fields  |
      |                                   |   (QWeb template)     |
      |                                   |                        |
      |                                   +----> adds <Meter>     |
      |                                   +----> adds minlength   |
      |                                           attribute        |
      |                                   |                        |
      +------------------------------------> Owl <Meter> JS       |
                    (loaded via assets:                           |
                     auth_password_policy/                         |
                     static/src/password_meter.js)                |
```

## Controller Extension

### `controllers.py`

```python
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome

class AddPolicyData(AuthSignupHome):
    def get_auth_signup_config(self):
        d = super(AddPolicyData, self).get_auth_signup_config()
        d['password_minimum_length'] = request.env['ir.config_parameter'].sudo().get_param(
            'auth_password_policy.minlength'
        )
        return d
```

**What it does:**
- Inherits from `auth_signup.controllers.main.AuthSignupHome`, the base controller for all auth_signup pages (signup, reset password, magic link).
- Overrides `get_auth_signup_config()`, which is called by the template rendering methods (`signup()` and `reset_password()`) to populate the template context.
- Reads the `auth_password_policy.minlength` config parameter (an integer stored in `ir.config_parameter`, defaulting to 8) and injects it as `password_minimum_length` into the returned dictionary.
- The method is called `get_auth_signup_config` rather than `_prepare_portal_layout_values` because each auth_signup page (signup form, reset password form) calls this same method to get their shared configuration values.

**Why it inherits `AuthSignupHome`**: `auth_signup` defines `AuthSignupHome.get_auth_signup_config()` specifically as a configuration-injection hook. Unlike portal (which uses `_prepare_portal_layout_values`), auth_signup uses this dedicated method to keep the config values scoped to authentication flows.

## Model Extension

### `models/ir_http.py`

```python
from odoo import models

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        mods = super()._get_translation_frontend_modules_name()
        return mods + ['auth_password_policy']
```

This is identical in purpose to the same method in `auth_password_policy_portal/models/ir_http.py`. It ensures that the translation strings from `auth_password_policy` (e.g., "Password too short", "Must contain a digit") are loaded into the JavaScript locale bundle for the frontend, so the `<Meter>` Owl component displays properly translated messages.

## QWeb Template Extension

### `views/signup_templates.xml`

```xml
<odoo>
    <template id="fields" inherit_id="auth_signup.fields"
              name="Password policy data for auth_signup">
        <!--
            Inject the <Meter> Owl component after the <label> for the password field.
            The Meter watches the <input name="password"> field and displays a
            colored strength bar (red/orange/green) as the user types.
        -->
        <xpath expr="//label[@for='password']" position="after">
            <owl-component name="password_meter"
                props='{"selector": "input[name=password]"}'/>
        </xpath>
        <!--
            Add a dynamic minlength HTML attribute to the password <input>.
            t-att-minlength evaluates the QWeb expression password_minimum_length
            from the controller context. If the config parameter is unset (empty),
            the attribute is omitted and the browser uses its default validation.
        -->
        <xpath expr="//input[@name='password']" position="attributes">
            <attribute name="t-att-minlength">password_minimum_length</attribute>
        </xpath>
    </template>
</odoo>
```

**Two injection points:**

1. **`<Meter>` Owl component**: Inserted after the `<label for='password'>` element in the `auth_signup.fields` template (the shared partial that renders the signup form fields). The `<Meter>` Owl component (`auth_password_policy/static/src/password_meter.xml`) renders a colored bar indicating password strength in real time as the user types. The `props='{"selector": "input[name=password]"}'` tells the component which input field to monitor.

2. **`minlength` attribute**: Added to the `<input name="password">` element via `t-att-minlength`. The value comes from `password_minimum_length` injected by `get_auth_signup_config()`. The rendered HTML looks like:

   ```html
   <input name="password" minlength="8" type="password" required="required" .../>
   ```

   This provides **client-side validation** -- the browser blocks form submission if fewer than 8 characters are entered.

## The `<Meter>` Owl Component (Signup-Specific Template)

### `static/src/public/components/password_meter/password_meter.xml`

```xml
<templates xml:space="preserve">
    <t t-name="auth_password_policy_signup.PasswordMeter">
        <Meter t-if="state.password and hasMinlength"
            password="state.password"
            required="required"
            recommended="recommended"/>
    </t>
</templates>
```

This is the **signup-specific QWeb template** for the `password_meter` Owl component. It wraps the generic `<Meter>` component (defined in `auth_password_policy/static/src/password_meter.xml`) and passes the `required` and `recommended` flags.

- `state.password`: The current value of the watched password input.
- `required="required"`: The password field is required (sign-up cannot proceed without one).
- `recommended="recommended"`: The meter shows the "recommended" strength threshold (as opposed to "acceptable" minimum).

The component template name `auth_password_policy_signup.PasswordMeter` is referenced in the main template extension (`signup_templates.xml`) via `name="password_meter"`. Odoo's Owl component registry maps this name to the template.

## Related: `auth_password_policy` Base Module

The `auth_password_policy` module (which both `auth_password_policy_signup` and `auth_password_policy_portal` depend on) provides:

| Component | Description |
|-----------|-------------|
| `ir.config_parameter`: `auth_password_policy.minlength` | Integer, default 8. Set via **Settings > General Settings > Password Policy**. |
| `res.users`: `_check_password_policy()` | ORM method called by `write()` when password is changed. Raises `UserError` if policy is violated. |
| `static/src/password_meter.js` | Owl component controller: computes entropy, updates `state.password` and `hasMinlength` |
| `static/src/password_meter.xml` | Generic `<Meter>` Owl component template |
| `static/src/password_policy.js` | Pure JS password strength evaluation: length, uppercase, digit, special char scoring |

The `<Meter>` component does not send the password to the server. It evaluates strength entirely in the browser using the `password_policy.js` utilities.

## Complete Signup Flow with Password Policy

1. User navigates to `/web/signup` -> `AuthSignupHome.signup()` is called.
2. Controller calls `get_auth_signup_config()` -> our override injects `password_minimum_length`.
3. Controller renders `auth_signup.fields` (extended by `signup_templates.xml`).
4. Template renders the signup form with the `<Meter>` Owl component and `minlength` on the password field.
5. User types a password -> the `<Meter>` Owl component updates its colored strength bar in real time.
6. User submits the form -> browser validates `minlength` client-side first.
7. Controller receives POST data -> calls `auth_signup.models.res_users.signup()`.
8. The `signup()` method creates the `res.users` record and calls `write({'password': ...})`.
9. `write()` triggers `_check_password_policy(password)` from `auth_password_policy`.
10. If the password is too short or fails the strength check, `UserError` is raised and the user sees an error message.
11. If valid, the user record is created and the user is automatically logged in (or sent a confirmation email, depending on configuration).

## Comparison: `auth_password_policy_signup` vs `auth_password_policy_portal`

| Aspect | `auth_password_policy_signup` | `auth_password_policy_portal` |
|--------|------------------------------|-------------------------------|
| **Target flow** | Self-registration (new user creates account) | Password change (existing portal user updates password) |
| **Controller** | `auth_signup.controllers.main.AuthSignupHome` | `portal.controllers.portal.CustomerPortal` |
| **Overridden method** | `get_auth_signup_config()` | `_prepare_portal_layout_values()` |
| **Extended template** | `auth_signup.fields` | `portal.portal_my_security` |
| **Input field targeted** | `input[name=password]` | `input[name=new1]` |
| **Meter props selector** | `{"selector": "input[name=password]"}` | `{"selector": "input[name=new1]"}` |
| **Meter template** | `auth_password_policy_signup.PasswordMeter` | Same (from `auth_password_policy`) |
| **Static assets** | Own bundle + auth_password_policy JS | Uses auth_password_policy's bundle via inheritance |

Both modules follow the identical architectural pattern: read the config parameter, inject it into the controller context, and use XML inheritance to add the `<Meter>` component and `minlength` attribute to the relevant password input field.

## Security Considerations

| Aspect | Detail |
|--------|--------|
| **Client-side meter is read-only** | The `<Meter>` Owl component runs entirely in the browser. It never sends the actual password to the server for strength evaluation. |
| **Server validation is mandatory** | The `minlength` HTML attribute is advisory; server-side `_check_password_policy()` in `auth_password_policy` is the authoritative enforcement. |
| **`sudo()` on config read** | `ir.config_parameter` is read with `sudo()` in the controller. This is safe because the parameter holds a public integer (minimum length); no secrets are exposed. |
| **No new SQL tables** | The module creates no new database tables. |
| **`auto_install` safety** | Since `auto_install` only triggers when both dependencies (`auth_password_policy` and `auth_signup`) are already installed, there is no risk of partial installation. |

## Related

- [Modules/auth_password_policy](auth_password_policy.md) -- Base module: stores the policy config and provides `_check_password_policy()`
- [Modules/auth_password_policy_portal](auth_password_policy_portal.md) -- Same pattern for the portal password-change page
- [Modules/auth_signup](auth_signup.md) -- Self-registration controller, token-based password reset
- [Modules/portal](portal.md) -- Customer portal base controller and security templates
- [Patterns/Security Patterns](Security Patterns.md) -- Odoo's ACL, record rules, and ir.config_parameter patterns
