---
tags: [odoo, odoo17, module, auth, totp, security, email]
research_depth: medium
---

# Auth TOTP Mail — TOTP Device Email Notifications

**Source:** `addons/auth_totp_mail/models/`

## Overview

Extends `auth_totp` to send email notifications to users when trusted devices are added or removed from their accounts. This provides visibility into account security events — users can detect unauthorized device additions quickly.

## Key Models

### auth_totp.device — Device Notification on Unlink

**File:** `auth_totp_device.py`

Extends `auth_totp.device` to notify users when a trusted device is removed.

**`unlink()` override:**
When a device is unlinked (deleted), the user is notified via email using `_notify_security_setting_update(...)` with the message: "A trusted device has just been removed from your account: {device_names}"

**`_generate()` override:**
When a trusted device is created, the current user is notified: "A trusted device has just been added to your account: {device_name}"

> Note: `_generate()` is overridden rather than `create()` because device records are inserted directly via raw SQL in the `res.users.apikeys` mixin, bypassing the ORM `create()` method.

**`_classify_by_user()`:**
Helper method that groups devices by user into a `defaultdict` of `auth_totp.device` recordsets. Used by `unlink()` to batch notifications per user.

### res.users — 2FA Status Notifications and Invitations

**File:** `res_users.py`

Extends `res.users` to send email notifications when 2FA is enabled or disabled, and to allow administrators to invite users to enable 2FA.

#### Security Update Notifications on 2FA Toggle

`write()` is overridden to detect changes to `totp_secret`:
- If `totp_secret` is set → send "Security Update: 2FA Activated" email
- If `totp_secret` is cleared → send "Security Update: 2FA Deactivated" email

Both use `_notify_security_setting_update()` (from base `res.users`) with `suggest_2fa=False` to prevent recursive promotion.

#### `_notify_security_setting_update_prepare_values()`

Extends the base notification template values to conditionally include 2FA promotion:
```python
values['suggest_2fa'] = suggest_2fa and not self.totp_enabled
```
This causes the email template to show a "Enable 2FA" call-to-action button only to users who don't already have 2FA enabled.

#### Invite Users to Enable 2FA

**`action_totp_invite()`** — Sends an invitation email to users who do not have 2FA enabled:
1. Sends `auth_totp_mail.mail_template_totp_invite` email to each user without a `totp_secret`
2. Shows a toaster notification confirming invitations sent
3. The email uses `email_from` and `author_id` from the inviting user (admin)

**`action_open_my_account_settings()`** — Opens the user's own account form in the auth_totp_mail custom view (with 2FA management).

**`get_totp_invite_url()`** — Returns the URL to the 2FA activation action: `/web#action=auth_totp_mail.action_activate_two_factor_authentication`

**`action_totp_invite`** — requires `base.group_system` (admin) to send invitations to other users.

## Security Notification Flow

```
User enables 2FA
  → write({'totp_secret': '...'})
  → _notify_security_setting_update(
        title="Security Update: 2FA Activated",
        content=...)
  → mail.mail sent to user
```

## See Also

- [Modules/auth_totp](odoo-18/Modules/auth_totp.md) — core TOTP authentication
- [Modules/auth_totp_enforce](Modules/auth_totp_enforce.md) — enforces TOTP for all users
- [Modules/auth_totp_portal](odoo-17/Modules/auth_totp_portal.md) — TOTP access for portal users
- [Modules/res_users](odoo-19/Modules/res_users.md) — user model with security notification support