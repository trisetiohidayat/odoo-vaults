---
type: module
module: auth_password_policy_portal
tags: [odoo, odoo19, auth, security, password, portal, web]
created: 2026-04-06
uuid: c3b2d4e5-6f7a-8901-bcde-f12345678901
---

# Auth Password Policy Portal

## Overview

| Property | Value |
|----------|-------|
| **Name** | Password Policy support for Portal |
| **Technical** | `auth_password_policy_portal` |
| **Category** | Tools |
| **Depends** | `auth_password_policy`, `portal` |
| **Auto-install** | True |
| **License** | LGPL-3 |

## What It Does

`auth_password_policy_portal` is a thin glue module that extends the password policy enforcement system -- provided by the base `auth_password_policy` module -- to the portal (external customer/supplier) user experience. It does not add any Python model code; instead it overrides the portal controller's layout values method to pass the configured `password_minimum_length` value into QWeb templates, and uses XML view inheritance to add a visual password-strength meter (the `<Meter>` Owl component) and a `minlength` HTML attribute to the password field in the portal password-change form.

The module is `auto_install: True`. This means that when a database has both `auth_password_policy` and `portal` installed but not `auth_password_policy_portal`, Odoo automatically installs it. This fills the missing user-facing experience layer for portal users.

## Module Structure

```
auth_password_policy_portal/
├── __init__.py                      # Imports controllers and models submodules
├── __manifest__.py                  # Metadata
├── controllers.py                   # Extends CustomerPortal to pass policy config
└── models/
    ├── __init__.py                 # Imports ir_http
    └── ir_http.py                  # Registers auth_password_policy for translation
    views/
        └── templates.xml            # QWeb template extension: adds meter + minlength
```

### `__manifest__.py`

```python
{
    'name': "Password Policy support for Portal",
    'depends': ['auth_password_policy', 'portal'],
    'category': 'Tools',
    'auto_install': True,
    'data': ['views/templates.xml'],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

The module has **no Python model code** that runs at install time. Its only runtime contribution is the controller override and the QWeb template extension.

## Architecture: How the Pieces Fit Together

```
auth_password_policy          auth_password_policy_portal         portal
(base module, no UI)              (this module)              (customer UI)
      |                                   |                       |
      | ir.config_parameter               |                       |
      | stores: auth_password_policy.      |                       |
      | minlength (integer)               |                       |
      |                                   |                       |
      |                      +------------+-------------------->  |
      |                      |  _prepare_portal_layout_values()|
      |                      |  injects password_minimum_length |
      |                      |  into template context           |
      |                                   |                       |
      |                                   |   portal_my_security  |
      |                                   |   (QWeb template)     |
      |                                   |                       |
      |                                   +----> adds <Meter>    |
      |                                   +----> adds minlength  |
      |                                           attribute      |
      +----------------------------------------> Owl component  |
                  (Meter widget JS loaded via                       |
                   auth_password_policy/assets)                      |
```

## Controller Extension

### `controllers.py`

```python
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class CustomerPortalPasswordPolicy(CustomerPortal):
    def _prepare_portal_layout_values(self):
        d = super()._prepare_portal_layout_values()
        d['password_minimum_length'] = request.env['ir.config_parameter'].sudo().get_param(
            'auth_password_policy.minlength'
        )
        return d
```

**What it does:**
- Inherits from `portal.controllers.portal.CustomerPortal`.
- Overrides `_prepare_portal_layout_values()` -- the method called by nearly every portal page handler (including the password-change page) to populate the template context.
- Reads the system-wide `auth_password_policy.minlength` config parameter (stored in `ir.config_parameter`) and injects it into the template context as `password_minimum_length`.
- The value is retrieved with `sudo()` because `ir.config_parameter` records are system-level and portal users should not need elevated privileges to access the setting.

**Why it inherits `CustomerPortal`**: The `portal` module defines `CustomerPortal` as the base controller for all portal pages. Its `_prepare_portal_layout_values()` is called by `__init__` before rendering any portal template, making it the ideal hook to inject arbitrary values into the template context for all portal pages simultaneously.

**Template context**: The `password_minimum_length` value is then available in the QWeb template as a variable passed from the controller:

```python
# Inside portal template (simplified):
values = {
    # ... other values from super() ...
    'password_minimum_length': request.env['ir.config_parameter']
        .sudo().get_param('auth_password_policy.minlength'),
}
return request.render('portal.portal_my_security', values)
```

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

**What it does:**
- Adds `auth_password_policy` to the list of modules whose translations are loaded into the frontend (JavaScript).
- The `auth_password_policy` module contains translatable strings for password policy error messages displayed by the Owl `<Meter>` component (e.g., "Password too short", "Password must contain a digit").
- Without this registration, the frontend password meter would display English strings even when the portal is accessed in a non-English locale.

**`_get_translation_frontend_modules_name`**: This is a hook method on the abstract `ir.http` model called at web client startup. The returned list of module names is used by the web client to determine which translation files (`.po` -> compiled `.mo`) to load into the JavaScript locale bundle.

## QWeb Template Extension

### `views/templates.xml`

```xml
<odoo>
    <template id="portal_my_security" inherit_id="portal.portal_my_security"
              name="Password policy data for portal">
        <!--
            Add the visual password strength meter after the label for the
            "new password" field. The selector "input[name=new1]" targets the
            first of the two identical new-password inputs (new1 and new2 must
            match); only the first needs the meter.
        -->
        <xpath expr="//label[@for='new']" position="after">
            <owl-component name="password_meter"
                props='{"selector": "input[name=new1]"}'/>
        </xpath>
        <!--
            Add a minlength HTML attribute to the first new-password field.
            The value is injected from the controller context variable
            password_minimum_length. If the config parameter is unset,
            this renders as no minlength attribute (browser default applies).
        -->
        <xpath expr="//input[@name='new1']" position="attributes">
            <attribute name="t-att-minlength">password_minimum_length</attribute>
        </xpath>
    </template>
</odoo>
```

**Two injection points:**

1. **Password Meter**: A `<owl-component name="password_meter">` is injected after the `<label for='new'">` (the label for the new password field). This renders the `<Meter>` Owl component from `auth_password_policy/static/src/password_meter.js`. The `props='{"selector": "input[name=new1]"}'` tells the meter which `<input>` element to monitor for real-time strength feedback.

2. **HTML5 `minlength` attribute**: The `t-att-minlength` directive dynamically sets the `minlength` attribute on the `<input name="new1">` element to the integer value of `password_minimum_length` from the controller context. The `t-att-` prefix means the attribute value is evaluated as a QWeb expression. The rendered HTML will look like:

   ```html
   <input name="new1" minlength="8" type="password" .../>
   ```

   This provides **client-side enforcement** via the browser's built-in HTML5 validation, in addition to server-side validation done by `auth_signup` or `portal` controllers.

**Note on the `portal_my_security` template**: This template is rendered by the `CustomerPortal.portal_change_password()` method when a portal user visits their security settings page (typically at `/my/security`). The page has three password fields: `current` (old password), `new1` (new password), and `new2` (confirm new password).

## Related: `auth_password_policy` Base Module

The `auth_password_policy` module (which this module depends on) provides:

| Component | Description |
|-----------|-------------|
| `ir.config_parameter`: `auth_password_policy.minlength` | Integer, default 8. Minimum password length. Set via **Settings > General Settings > Password Policy**. |
| `res.users`: `_check_password_policy()` | ORM method called by `write()` when password is changed. Raises `UserError` if password is too short. |
| `static/src/password_meter.js` | Owl component that shows a colored bar (red/orange/green) based on password entropy |
| `static/src/password_policy.js` | Logic for computing password strength score |
| `static/src/password_meter.xml` | XML Owl component definition for the `<Meter>` widget |

The password strength meter runs entirely in the browser. It does **not** send the password to the server. The server-side validation happens only when the form is submitted and `auth_signup` / portal controller processes the `new_password` field.

## Password Change Flow (Portal)

The complete flow when a portal user changes their password:

1. User navigates to `/my/security` -> `CustomerPortal.portal_change_password()` is called.
2. Controller calls `_prepare_portal_layout_values()` -> our override adds `password_minimum_length`.
3. Controller renders `portal.portal_my_security` (extended by our `templates.xml`).
4. Template renders password fields with `minlength` attribute and the `<Meter>` Owl component.
5. User types in the new password field -> the `<Meter>` Owl component reacts in real time, showing strength (red/orange/green bar).
6. User submits the form -> browser validates `minlength` client-side first.
7. Controller receives POST data -> calls `request.env.user._update_password(current, new1, new2)`.
8. `_update_password()` calls `_check_password_policy(new1)` from `auth_password_policy`.
9. If the password is too short or too weak, `UserError` is raised and displayed to the user.
10. If valid, the password is updated and the session is re-authenticated.

## Integration with `auth_signup`

The portal password change flow uses `auth_signup`'s `AuthSignupHome` controller internally for the actual password update logic. The `auth_password_policy_portal` module does **not** directly override `AuthSignupHome`; instead it extends the portal-specific security template and injects values into the portal controller's context.

For the **signup** flow (new user self-registration via `/web/signup`), see [Modules/auth_password_policy_signup](auth_password_policy_signup.md) -- a separate but related module that handles the signup form.

## Security Considerations

| Aspect | Detail |
|--------|--------|
| **No direct validation here** | Server-side password policy validation is handled by `auth_password_policy`'s `_check_password_policy()` called from `res.users.write()`. This module only adds UI hints. |
| **Client-side `minlength` bypass** | The `minlength` HTML attribute is advisory only. A malicious client can bypass it. Server-side validation is mandatory and is enforced by `_check_password_policy()`. |
| **Sudo access** | The controller uses `sudo()` to read `ir.config_parameter`. This is safe because the parameter is a public integer; no sensitive data is exposed. |
| **Strength meter is client-side only** | The `<Meter>` component runs entirely in the browser. It never sends the password to the server. |

## Related

- [Modules/auth_password_policy](auth_password_policy.md) -- Base module that stores the policy config and provides server-side validation
- [Modules/auth_password_policy_signup](auth_password_policy_signup.md) -- Same pattern for the signup (self-registration) form
- [Modules/auth_signup](auth_signup.md) -- Self-registration controller and template
- [Modules/portal](portal.md) -- Customer portal base controller and templates
- [Patterns/Security Patterns](Security Patterns.md) -- Odoo's ACL, record rules, and ir.config_parameter patterns

## Differences from `auth_password_policy_signup`

Both `auth_password_policy_portal` and [Modules/auth_password_policy_signup](auth_password_policy_signup.md) implement the same architectural pattern (controller override + QWeb extension) but target different user flows. Here is a head-to-head comparison:

| Criterion | `auth_password_policy_portal` | `auth_password_policy_signup` |
|-----------|-------------------------------|-------------------------------|
| **User type** | Existing portal user changing password | New visitor creating an account |
| **URL route** | `/my/security` | `/web/signup` |
| **Controller** | `portal.controllers.portal.CustomerPortal` | `auth_signup.controllers.main.AuthSignupHome` |
| **Overridden method** | `_prepare_portal_layout_values()` | `get_auth_signup_config()` |
| **Extended template** | `portal.portal_my_security` | `auth_signup.fields` (shared partial) |
| **Target password field** | `input[name="new1"]` (first of two identical fields) | `input[name="password"]` |
| **Meter props selector** | `{"selector": "input[name=new1]"}` | `{"selector": "input[name=password]"}` |
| **minlength target** | `new1` field | `password` field |
| **Groups required** | Portal user (any authenticated portal user) | Public (no account required to view the page) |
| **Translation registration** | Yes (`models/ir_http.py`) | Yes (`models/ir_http.py`) |
| **Demo data** | None | None |

The key practical difference for administrators:
- Enable `auth_signup` + `auth_password_policy` + `auth_password_policy_signup` to enforce password policy at **account registration**.
- Enable `portal` + `auth_password_policy` + `auth_password_policy_portal` to enforce password policy at **password change** for existing portal customers.
- For a complete password policy enforcement, enable all four modules together.

## Configuration Checklist

To enable password policy enforcement for portal users, verify that all of the following are true:

1. **`auth_password_policy`** is installed (provides the config parameter and `_check_password_policy()`)
2. **`portal`** is installed (provides the portal user flows)
3. **`auth_password_policy_portal`** is installed (or auto-installed when both deps are present)
4. **Settings > General Settings > Password Policy**: `Minimum password length` is set to a value > 0
5. **Website > Configuration > Settings > Allow portal signup**: Enabled if you also want the signup flow to use the policy

Once configured, portal users will see the password strength meter when changing their password at `/my/security`, and any password shorter than the configured minimum will be rejected server-side.
