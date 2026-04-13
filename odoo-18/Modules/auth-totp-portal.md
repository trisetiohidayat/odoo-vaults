---
Module: auth_totp_portal
Version: Odoo 18
Type: Extension
Tags: [#odoo, #odoo18, #security, #auth, #totp, #2fa, #portal, #website]
Related: [Modules/auth_totp](modules/auth_totp.md) (base TOTP), [Modules/auth_totp_mail](modules/auth_totp_mail.md) (notifications), [Modules/auth_totp_mail_enforce](modules/auth_totp_mail_enforce.md) (enforcement), [Modules/Portal](modules/portal.md) (portal module)
---

# auth_totp_portal — TOTP for Portal Users

> **Purpose:** Enable portal/website users to set up and use TOTP (2FA) via the `/my/security` portal page. Grants portal users read+write access to the `auth_totp.wizard` model (normally backend-only), and overrides `get_totp_invite_url()` so that portal users are redirected to the portal security page rather than the backend form when receiving 2FA invitations.

**Module:** `auth_totp_portal`
**Depends:** `portal`, `auth_totp`
**Category:** Hidden
**Auto-install:** True
**License:** LGPL-3
**Source path:** `~/odoo/odoo18/odoo/addons/auth_totp_portal/`

---

## Architecture Overview

The base `auth_totp` module provides TOTP 2FA functionality for internal (backend) users. Portal users have a fundamentally different UI model:

- Portal users navigate via the website/portal frontend, not the backend.
- Portal users do **not** have access to non-QWeb views (backend form views) by default.
- Portal users interact with their security settings via `/my/security` (the portal account security page).

`auth_totp_portal` bridges this gap by:

1. Adding a "Two-factor authentication" section to `portal.portal_my_security` via a QWeb template extension.
2. Providing JavaScript widgets (`publicWidget.registry`) to handle the enable/disable/revoke flows entirely from the portal page.
3. Granting portal users CRUD access to `auth_totp.wizard` (normally backend-only) so they can complete the QR-code scanning step.
4. Overriding `get_totp_invite_url()` to redirect invited portal users to `/my/security` instead of the backend form.
5. Overriding `totp_enabled` and `totp_trusted_device_ids` to be readable in portal context via `SELF_READABLE_FIELDS`.

**No new database models.** This module extends existing models and adds frontend JS + CSS.

---

## Extensions to `res.users`

**Model:** `res.users` (extends `auth_totp` extension)

### Key Method: `get_totp_invite_url()` (override)

```python
def get_totp_invite_url(self):
    if not self._is_internal():
        return '/my/security'
    else:
        return super(Users, self).get_totp_invite_url()
```

**L4 — How it works:**
- Checks if the user is internal via `_is_internal()`.
- Portal/external users are redirected to `/my/security` (the portal security page) when clicking "Activate 2FA" from an invitation email.
- Internal users get the backend form view via the parent `auth_totp_mail` URL.
- `auth_totp_mail` defines the original `get_totp_invite_url()` returning the backend action URL. This module overrides it for non-internal users.

**MRO note:** This override sits between `auth_totp_mail` and `auth_totp` in the method resolution order when both are installed. `auth_totp_mail` defines `get_totp_invite_url()`; `auth_totp_portal` overrides it for portal users only.

---

## Security Access Control (ir.model.access)

**File:** `security/security.xml`

The module grants portal users explicit access to `auth_totp.wizard`:

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

**L4 — Why this is needed:**
- `auth_totp.wizard` is the backend form that walks the user through QR code display and 6-digit code entry to activate 2FA.
- By default, portal users have no access to this model — they cannot read it, write it, or create records in it.
- Granting `perm_create=1` is needed because activating 2FA creates a new wizard record.
- `perm_unlink=1` is needed if the user cancels the wizard (prevents ghost records).
- Without this record, the portal JS widget's `orm.read()` and `orm.write()` calls on `auth_totp.wizard` would raise `AccessError` for portal users.

---

## Frontend UI Extension

**File:** `views/templates.xml` — extends `portal.portal_my_security`

The portal security page (`/my/security`) is augmented with a new `<section>` injected after the password change section:

```xml
<template id="totp_portal_hook" name="TOTP Portal hook" inherit_id="portal.portal_my_security">
    <!-- Hidden div: stores the rendered XML of auth_totp.view_totp_wizard -->
    <div class="d-none" id="totp_wizard_view">
        <t t-esc="env.ref('auth_totp.view_totp_wizard').sudo().get_combined_arch()"/>
    </div>

    <section>
        <h4>Two-factor authentication</h4>

        <!-- Not enabled state -->
        <t t-if="not user_id.totp_enabled">
            <div class="alert alert-secondary">Two-factor authentication not enabled</div>
            <button type="button" class="btn btn-secondary" id="auth_totp_portal_enable">
                Enable two-factor authentication
            </button>
        </t>

        <!-- Enabled state -->
        <t t-else="">
            <span class="text-success"><i class="fa fa-check-circle"/> 2FA enabled</span>
            <button type="button" class="btn btn-link" id="auth_totp_portal_disable">
                (Disable two-factor authentication)
            </button>

            <!-- Trusted devices table -->
            <t t-if="len(user_id.totp_trusted_device_ids)">
                <table class="table">
                    <thead><tr><th>Trusted Device</th><th>Added On</th><th></th></tr></thead>
                    <tbody>
                        <tr t-foreach="user_id.totp_trusted_device_ids" t-as="td">
                            <td><span t-field="td.name"/></td>
                            <td><span t-field="td.create_date"/></td>
                            <td><i class="fa fa-trash text-danger" t-att-id="td.id"/></td>
                        </tr>
                    </tbody>
                </table>
                <button class="btn btn-primary" id="auth_totp_portal_revoke_all_devices">Revoke All</button>
            </t>
        </t>
    </section>
</template>
```

**L4 — The "Data Island" Pattern:**
- Portal users cannot access non-QWeb backend views (anything beyond `ir.ui.view` with `type='qweb'`).
- `auth_totp.view_totp_wizard` is a backend form view — portal users cannot normally render it.
- The module works around this by calling `env.ref('auth_totp.view_totp_wizard').sudo().get_combined_arch()` (server-side) to get the raw XML of the wizard form.
- This XML is embedded as a hidden div (`class="d-none"`) and then parsed client-side by the `TOTPButton` JS widget using `DOMParser`.
- The JS widget extracts the `qrcode`, `url`, `code`, and `secret` fields from the XML and renders them as normal HTML form elements inside an `InputConfirmationDialog`.
- This avoids the need for a separate portal-specific wizard form — it reuses the backend wizard's view definition.

---

## JavaScript Widgets (Frontend)

**File:** `static/src/js/totp_frontend.js`

The module registers four `publicWidget` widgets, all extending `publicWidget.Widget`:

### Widget 1: `TOTPButton`

**Selector:** `#auth_totp_portal_enable`

```javascript
async _onClick(e) {
    const w = await handleCheckIdentity(
        this.orm.call("res.users", "action_totp_enable_wizard", [user.userId]),
        this.orm, this.dialog
    );
    // ... parse wizard XML, show InputConfirmationDialog with QR code ...
    await this.orm.write(model, [record.id], { code: inputEl.value });
    await handleCheckIdentity(
        this.orm.call(model, "enable", [record.id]),
        this.orm, this.dialog
    );
    window.location = window.location;
}
```

**L4 — How it works:**
1. Calls `action_totp_enable_wizard` (from `auth_totp`) to create the wizard. This triggers the `@check_identity` decorator — the user must re-confirm their password first.
2. Reads the wizard record to get `qrcode`, `url`, `secret`.
3. Parses the embedded wizard XML (from `#totp_wizard_view`) to extract field definitions.
4. Renders an `InputConfirmationDialog` with the QR code and secret display.
5. User enters the 6-digit code from their authenticator app.
6. Calls `orm.write(model, [record.id], { code: inputEl.value })` to submit the code to the wizard.
7. Calls `handleCheckIdentity` again to call `wizard.enable()` (which writes `totp_secret` on the user and revokes all devices).
8. Reloads the page to show updated state.

### Widget 2: `DisableTOTPButton`

**Selector:** `#auth_totp_portal_disable`

```javascript
async _onClick(e) {
    e.preventDefault();
    await handleCheckIdentity(
        this.orm.call("res.users", "action_totp_disable", [user.userId]),
        this.orm, this.dialog
    )
    window.location = window.location;
}
```

**L4 — How it works:**
- Calls `action_totp_disable` via `@check_identity` — requires password re-confirmation.
- Calls `revoke_all_devices()` as part of the disable flow.
- Reloads the page to reflect disabled state.

### Widget 3: `RevokeTrustedDeviceButton`

**Selector:** `#totp_wizard_view + * .fa.fa-trash.text-danger`

```javascript
async _onClick(e){
    e.preventDefault();
    await handleCheckIdentity(
        this.orm.call("auth_totp.device", "remove", [parseInt(this.el.id)]),
        this.orm, this.dialog
    );
    window.location = window.location;
}
```

**L4 — How it works:**
- Targets the trash icon next to each trusted device row.
- Calls `auth_totp.device.remove()` via `@check_identity` — requires password re-confirmation for each device removal.
- Reloads the page to reflect removed device.

### Widget 4: `RevokeAllTrustedDevicesButton`

**Selector:** `#auth_totp_portal_revoke_all_devices`

```javascript
async _onClick(e){
    e.preventDefault();
    await handleCheckIdentity(
        this.orm.call("res.users", "revoke_all_devices", [user.userId]),
        this.orm, this.dialog
    );
    window.location = window.location;
}
```

**L4 — How it works:**
- Calls `revoke_all_devices` on the current user (from `auth_totp`).
- Triggers `@check_identity` before proceeding.
- Reloads the page.

### `handleCheckIdentity` Integration

All four widgets use `handleCheckIdentity` from `@portal/js/portal_security`. This function:
1. Prompts the user to re-enter their password in a dialog.
2. On success, returns the action returned by the decorated method.
3. On failure, returns `null` or raises.

This pattern ensures that sensitive 2FA operations (enable, disable, revoke devices) require the user's current password as a secondary identity check — even if they are already logged in.

### `fromField()` — XML Field Renderer

The `fromField()` helper function converts Odoo `<field>` XML elements to plain HTML elements for use in the `InputConfirmationDialog`:

| Field name | HTML output |
|-----------|-------------|
| `qrcode` | `<img src="data:image/png;base64,...">` |
| `url` | `<a href="...">...</a>` |
| `code` | `<input name="code" placeholder="6-digit code" required maxlength=6 minlength=6>` |
| `secret` | `<span>` + clipboard copy button |

The clipboard button uses `browser.navigator.clipboard.writeText()` to copy the secret to the clipboard, with a tooltip confirmation.

---

## `fixupViewBody()` — XML-to-HTML Bridge

Chrome cannot safely parse XML in an HTML document context. The `fixupViewBody()` function recursively traverses the wizard view's XML DOM and converts each node to an HTML element, delegating special field handling to `fromField()`.

This is recursive and reconstructs the entire wizard form body using `document.createElement()`. The result is a normal HTML element that can be rendered inside the dialog.

---

## SCSS

**File:** `static/src/scss/auth_totp_portal.scss`

No custom CSS was found in the SCSS file — the module relies on Bootstrap and Portal framework styles for all visual presentation. The file is included as a hook for potential future styling overrides.

---

## Portal 2FA vs. Internal User 2FA (L4 Comparison)

| Aspect | Internal Users (`auth_totp`) | Portal Users (`auth_totp_portal`) |
|--------|------------------------------|-----------------------------------|
| Setup location | Backend: Users form → Security tab | Frontend: `/my/security` page |
| Wizard access | Standard backend form view | Data-island XML injection + JS dialog |
| Identity check | Backend `@check_identity` decorator | Frontend `handleCheckIdentity()` via portal dialog |
| Invite URL | Backend form view action | `/my/security` |
| Device management | Backend user form | Frontend `/my/security` section |
| Email notifications | `auth_totp_mail` events fire | Same — `auth_totp_mail` hooks apply to portal too |
| Enforcement policy | `auth_totp_mail_enforce` applies | Only if `all_required` policy set |
| Login flow | `/web/login/totp` (backend) | `/my/home` → TOTP challenge on any protected route |

**Key differences:**

1. **Setup UX:** Portal users never see the backend. All 2FA interactions happen via JS-driven dialogs on the portal page. The wizard form XML is fetched server-side and rendered client-side as HTML.

2. **Identity verification:** Internal users confirm identity via the backend's `@check_identity` decorator (which shows a modal form). Portal users confirm via `handleCheckIdentity()` which shows the portal-style password dialog.

3. **Invite URL routing:** When an admin sends a 2FA invite via `auth_totp_mail`'s `action_totp_invite()`, portal users are correctly routed to `/my/security` because `auth_totp_portal` overrides `get_totp_invite_url()`.

4. **Rate limiting / enforcement:** Portal users are subject to `auth_totp_mail_enforce` enforcement policies **only if** `auth_totp.policy` is set to `'all_required'`. The `'employee_required'` policy does not cover portal users (since portal users are not internal employees).

---

## How `action_totp_enable_wizard` Works for Portal Users

The flow for a portal user enabling 2FA:

```
User clicks "Enable two-factor authentication" on /my/security
  └─ TOTPButton widget: orm.call("res.users", "action_totp_enable_wizard", [uid])
      ├─ handleCheckIdentity() → password re-confirm dialog
      └─ Wizard record created (auth_totp.wizard)
          └─ Wizard shows QR code + secret + code input

User scans QR code in authenticator app
User enters 6-digit code in portal dialog
  └─ TOTPButton widget: orm.write("auth_totp.wizard", [wizard_id], {code: "123456"})
      ├─ Wizard verifies code against TOTP
      └─ Wizard calls user.sudo().write({totp_secret: secret})
          └─ auth_totp_mail write() hook fires → "2FA Activated" email sent

User clicks "Activate" in portal dialog
  └─ TOTPButton widget: orm.call("auth_totp.wizard", "enable", [wizard_id])
      ├─ handleCheckIdentity() → password re-confirm again
      └─ Wizard calls user.action_totp_disable()... no, enable writes totp_secret
          └─ 2FA is now active for portal user

Page reloads → /my/security shows "Two-factor authentication enabled"
```

---

## Module Dependency Order

```
portal
  └─ auth_totp  (depends: portal is implicit, actually auth_totp depends on base only)
auth_totp_portal  (depends: portal, auth_totp)
```

`auth_totp` does not depend on `portal`, but `auth_totp_portal` bridges them. When both are installed, portal users can use 2FA via the portal frontend.

`auth_totp_mail` (notifications) and `auth_totp_mail_enforce` (enforcement) can be installed alongside `auth_totp_portal`. The notification hooks apply to portal users too; the enforcement policy applies only if `all_required` is set.
