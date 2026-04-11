---
Module: auth_totp_mail
Version: Odoo 18
Type: Extension
Tags: [#odoo, #odoo18, #security, #auth, #totp, #2fa, #mail]
Related: [[Modules/auth_totp]] (base TOTP), [[Modules/auth_totp_mail_enforce]] (enforcement), [[Modules/auth_totp_portal]] (portal 2FA), [[Core/API]] (security notifications)
---

# auth_totp_mail — TOTP Email Notification

> **Purpose:** Send email notifications when TOTP (2FA) is enabled, disabled, or when a trusted device is added/removed from a user account. Also provides an admin-side "Invite to use 2FA" action that emails users and links them to their security settings.

**Module:** `auth_totp_mail`
**Depends:** `auth_totp`, `mail`
**Category:** Extra Tools
**Auto-install:** True (installed automatically with `auth_totp`)
**License:** LGPL-3
**Source path:** `~/odoo/odoo18/odoo/addons/auth_totp_mail/`

---

## Architecture Overview

`auth_totp_mail` extends the base `auth_totp` module by layering on email notifications for security-relevant events. It does **not** add new TOTP verification mechanisms — it piggybacks on `auth_totp` for all 2FA checks. Instead, it:

1. Intercepts `write()` on `res.users` when `totp_secret` changes and fires `_notify_security_setting_update()`.
2. Overrides `AuthTotpDevice._generate()` and `unlink()` to send device add/remove emails.
3. Adds an admin "Invite to use 2FA" server action bound on the Users list view.
4. Overrides the base `_notify_security_setting_update_prepare_values()` to inject a `suggest_2fa` flag into the email rendering qweb template.

**No new database models.** This module adds zero new persistent models. The `auth_totp.device` record is still managed by `auth_totp`; this module only hooks into its lifecycle.

---

## Extensions to `res.users`

**Model:** `res.users` (extends `auth_totp` extension)
**Inherited fields:** `totp_secret`, `totp_enabled`, `totp_trusted_device_ids` (all from `auth_totp`)

### Key Method: `write()`

```python
def write(self, vals):
    res = super().write(vals)
    if 'totp_secret' in vals:
        if vals.get('totp_secret'):
            self._notify_security_setting_update(
                _("Security Update: 2FA Activated"),
                _("Two-factor authentication has been activated on your account"),
                suggest_2fa=False,
            )
        else:
            self._notify_security_setting_update(
                _("Security Update: 2FA Deactivated"),
                _("Two-factor authentication has been deactivated on your account"),
                suggest_2fa=False,
            )
    return res
```

**L4 — How it works:**
- Intercepts any write to `totp_secret` field.
- Fires `_notify_security_setting_update()` from the base `auth_totp` ORM layer.
- `suggest_2fa=False` because 2FA is already being turned on/off (no need to suggest it).
- Both activation and deactivation are tracked — the user receives a distinct email for each event.
- This is a `res.users` write trigger, not an `@api.onchange` — it fires on actual ORM write, which is the correct trigger for the wizard-based enable/disable flow.

### Key Method: `_notify_security_setting_update_prepare_values()`

```python
def _notify_security_setting_update_prepare_values(self, content, suggest_2fa=True, **kwargs):
    values = super()._notify_security_setting_update_prepare_values(content, **kwargs)
    values['suggest_2fa'] = suggest_2fa and not self.totp_enabled
    return values
```

**L4 — How it works:**
- Called by the base `auth_totp` ORM layer when rendering the `mail.account_security_setting_update` qweb email template.
- Adds a `suggest_2fa` boolean to the template rendering context.
- `suggest_2fa` is only `True` if: (a) the caller asked for it (`suggest_2fa=True`), AND (b) the user does not already have 2FA enabled (`not self.totp_enabled`).
- The qweb template (in `security_notifications_template.xml`) then conditionally renders a list item: "Consider activating Two-factor Authentication" with a link to the Odoo documentation.

### Key Method: `action_totp_invite()`

```python
def action_totp_invite(self):
    invite_template = self.env.ref('auth_totp_mail.mail_template_totp_invite')
    users_to_invite = self.sudo().filtered(lambda user: not user.totp_secret)
    for user in users_to_invite:
        email_values = {
            'email_from': self.env.user.email_formatted,
            'author_id': self.env.user.partner_id.id,
        }
        invite_template.send_mail(user.id, force_send=True, email_values=email_values,
                                  email_layout_xmlid='mail.mail_notification_light')
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'type': 'info',
            'sticky': False,
            'message': _("Invitation to use two-factor authentication sent for the following user(s): %s",
                         ', '.join(users_to_invite.mapped('name'))),
        }
    }
```

**L4 — How it works:**
- Iterates over `self` (the selected users from the list view).
- Filters to `users_to_invite`: only those without a `totp_secret` (i.e., not already enrolled in 2FA).
- Sends the `mail_template_totp_invite` email using the **current admin user's email as `email_from`** (not the system email), making it feel like a personal invitation.
- Sets `author_id` to the admin's partner so the email threading is correct.
- Returns a `display_notification` client action to show a toaster confirming the email was sent.
- Bound via `ir.actions.server` (`action_invite_totp`) in `ir_action_data.xml` — appears as "Invite to use two-factor authentication" button in the Users list view, visible only to `base.group_erp_manager`.

### Key Method: `action_open_my_account_settings()`

```python
def action_open_my_account_settings(self):
    action = {
        "name": _("Account Security"),
        "type": "ir.actions.act_window",
        "res_model": "res.users",
        "views": [[self.env.ref('auth_totp_mail.res_users_view_form').id, "form"]],
        "res_id": self.id,
    }
    return action
```

**L4 — How it works:**
- Opens the user's own form view as a read-only security settings page (via a dedicated form view that strips most fields).
- Called by the `action_activate_two_factor_authentication` server action triggered when the user clicks the link in the invitation email.
- The custom form view (`res_users_view_form`) is minimal: hides the notebook, hides footer, hides the preferences page, and disables create/edit/delete.
- Internal users go to this backend form view; portal users are redirected to `/my/security` (handled by `auth_totp_portal` override).

### Key Method: `get_totp_invite_url()`

```python
def get_totp_invite_url(self):
    return '/odoo/action-auth_totp_mail.action_activate_two_factor_authentication'
```

**L4 — How it works:**
- Returns the URL (action ID) that the "Activate my two-factor Authentication" button in the invite email links to.
- `auth_totp_portal` overrides this for portal users to return `/my/security` instead.
- Overridable on `res.users` so each extension module can redirect to the correct 2FA setup UI for that user type.

---

## Extension to `auth_totp.device`

**Model:** `auth_totp.device` (extends `auth_totp` extension)
**Inherited fields:** `name`, `user_id`, `key`, `scope`, `create_date` (all from `auth_totp`)

### Key Method: `_generate()` (override)

```python
def _generate(self, scope, name, expiration_date):
    res = super()._generate(scope, name, expiration_date)
    self.env.user._notify_security_setting_update(
        _("Security Update: Device Added"),
        _("A trusted device has just been added to your account: %(device_name)s",
          device_name=name),
    )
    return res
```

**L4 — How it works:**
- Overrides the parent `_generate()` which is called internally when a trusted device is being created (records inserted via raw SQL in the parent).
- The parent returns a dict with `key_id` and `key`; this module sends a security notification after the device is persisted.
- Runs as `self.env.user` (the currently logged-in user) — NOT the user who owns the device.
- Triggered when a user opts "Remember this device" during the TOTP login flow.

### Key Method: `unlink()` (override)

```python
def unlink(self):
    removed_devices_by_user = self._classify_by_user()
    for user, removed_devices in removed_devices_by_user.items():
        user._notify_security_setting_update(
            _("Security Update: Device Removed"),
            _("A trusted device has just been removed from your account: %(device_names)s",
              device_names=', '.join([device.name for device in removed_devices])),
        )
    return super().unlink()
```

**L4 — How it works:**
- Classifies devices being deleted by their `user_id` using `_classify_by_user()`.
- Sends one `_notify_security_setting_update()` per user (handles multi-user unlink in a single call).
- If deleting multiple devices for the same user in one operation, device names are joined as a comma-separated list.
- Runs before `super().unlink()` so the notification fires even if the DB operation fails (via try/finally not used here — notifications are best-effort).

### Key Method: `_classify_by_user()` (private helper)

```python
def _classify_by_user(self):
    devices_by_user = defaultdict(lambda: self.env['auth_totp.device'])
    for device in self:
        devices_by_user[device.user_id] |= device
    return devices_by_user
```

**L4 — How it works:**
- Groups all devices in `self` by their `user_id`.
- Returns a `defaultdict` keyed on `res.users` records.
- Used by `unlink()` to batch notifications per user.

---

## Data Files

### `data/mail_template_data.xml`

**Template:** `mail_template_totp_invite`
**Model:** `res.users`
**Subject:** "Invitation to activate two-factor authentication on your Odoo account"
**Auto-delete:** True

The template body explains what 2FA is and includes a prominent "Activate my two-factor Authentication" button linking to `object.get_totp_invite_url()` (returns the backend form view for internal users, `/my/security` for portal users).

**Email From:** `(object.company_id.email_formatted or user.email_formatted)` — uses the company email if set, falls back to the inviting admin's email.
**Lang:** `object.partner_id.lang` — rendered in the recipient user's language.

### `data/security_notifications_template.xml`

**Template:** Extends `mail.account_security_setting_update` (base mail template)

Injects a list item into the "suggestions" section of the base security email:

```xml
<li t-if="suggest_2fa">
    <span>Consider</span>
    <a href="https://www.odoo.com/documentation/master/applications/general/auth/2fa.html">
        activating Two-factor Authentication
    </a>
</li>
```

The `suggest_2fa` flag is only present when `_notify_security_setting_update_prepare_values()` sets it (user has no TOTP secret).

---

## UI Extensions

### View: `res_users_view_form` (custom minimal form)

Used as the landing page when a user clicks the invite link. Key features:
- Inherits `base.view_users_form_simple_modif`
- Mode: `primary` (creates a standalone view, not an extension)
- Disables create/edit/delete
- Strips the notebook to just the security-related pages
- Removes footer (no save button — it is read-only by default)

### View: `view_users_form` (TOTP form override)

Inherits `auth_totp.view_totp_form` and adds the "Invite to use 2FA" button next to "Enable 2FA":
```xml
<button groups="base.group_erp_manager" invisible="id == uid"
        name="action_totp_invite" string="Invite to use 2FA" type="object" class="btn btn-secondary"/>
```
- Only visible to ERP managers.
- Hidden when viewing your own user (`invisible="id == uid"`).

---

## Mail Flow on Login (L4 Integration with auth_totp)

The `auth_totp_mail` module does not handle the actual TOTP code verification during login — that is entirely the domain of `auth_totp`. This module's role in the login flow is indirect:

1. **Trusted device remembered:** When a user completes TOTP during login and checks "Remember this device," `auth_totp` creates an `auth_totp.device` record. `auth_totp_mail`'s `_generate()` override fires and sends a "Device Added" email.
2. **Device forgotten:** When a user revokes a trusted device, `auth_totp_mail`'s `unlink()` override fires and sends a "Device Removed" email.
3. **2FA toggled by admin:** When an admin modifies a user's `totp_secret` via the Users form, `auth_totp_mail`'s `write()` override fires and sends an "Activated" or "Deactivated" email.

The email-based TOTP login code (where a code is sent by email rather than entered from an authenticator app) is **not** handled by `auth_totp_mail` — that is handled by `auth_totp_mail_enforce`.

---

## Security Notifications vs. Invite Emails

| Event | Method | Template | Trigger |
|-------|--------|----------|---------|
| 2FA activated | `_notify_security_setting_update()` | base `mail.account_security_setting_update` | `write(totp_secret=...)` |
| 2FA deactivated | `_notify_security_setting_update()` | base `mail.account_security_setting_update` | `write(totp_secret=False)` |
| Trusted device added | `_notify_security_setting_update()` | base `mail.account_security_setting_update` | `auth_totp.device._generate()` |
| Trusted device removed | `_notify_security_setting_update()` | base `mail.account_security_setting_update` | `auth_totp.device.unlink()` |
| Invite to use 2FA | `send_mail()` | `mail_template_totp_invite` | `action_totp_invite()` server action |

---

## Dependencies and Auto-install

`auth_totp_mail` depends on both `auth_totp` and `mail`, and has `auto_install: True`. This means if `auth_totp` is installed, `mail` is installed, and Odoo detects that `auth_totp_mail` should be active (no conditional logic — it is always auto-installed when its dependencies are met), it is installed automatically.

This also means `auth_totp_mail` is in the **activation order**: `auth_totp` → `auth_totp_mail` (if mail present).

---

## Comparison: auth_totp_mail vs auth_totp_mail_enforce

| Feature | `auth_totp_mail` | `auth_totp_mail_enforce` |
|---------|------------------|--------------------------|
| Email on 2FA enable/disable | Yes | Yes (same base mechanism) |
| Email on device add/remove | Yes | No |
| Invite to use 2FA | Yes | No |
| Email code on login | No | Yes |
| Rate limiting on email | No | Yes (10 emails/hour) |
| Policy enforcement | No | Yes (`employee_required`, `all_required`) |
| New persistent models | No | Yes (`auth.totp.rate.limit.log`) |
| Portal support | No | No (only internal users) |
