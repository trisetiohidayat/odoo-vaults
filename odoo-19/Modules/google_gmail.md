# Google Gmail (`google_gmail`)

**Category:** Hidden
**Depends:** `mail`
**Auto-install:** True
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Adds Google Gmail OAuth2 support for incoming (IMAP) and outgoing (SMTP) mail servers in Odoo. Users can connect personal Gmail accounts via OAuth2 without app passwords or less-secure app access.

## Models

### `google.gmail.mixin` (Abstract)
Provides OAuth2 token management for Gmail integration.

**Key Methods:**
- `_compute_gmail_uri()` — Computes the Google OAuth authorization URI.
- `open_google_gmail_uri()` — Action to redirect user to Google login.
- `_fetch_gmail_refresh_token(authorization_code)` — Exchanges auth code for refresh token.
- `_fetch_gmail_access_token(refresh_token)` — Gets access token from refresh token.
- `_fetch_gmail_token(grant_type, **values)` — Unified token fetch method.
- `_fetch_gmail_access_token_iap(refresh_token)` — Fetches token via Odoo IAP proxy.
- `_generate_oauth2_string(user, refresh_token)` — Generates OAuth2 SASL authentication string for IMAP/SMTP.
- `_get_gmail_csrf_token()` — Generates CSRF token for OAuth flow.

### `fetchmail.server` (Extension)
Extends incoming mail server to support Gmail IMAP via OAuth2.

**Methods:**
- `_compute_server_type_info()` — Displays Gmail OAuth description.
- `_check_use_google_gmail_service()` — Validates Gmail service configuration.
- `onchange_server_type()` — Auto-fills Gmail IMAP defaults when Gmail type selected.
- `_imap_login__(connection)` — Authenticates via OAuth2 using stored refresh token.
- `_get_connection_type()` — Returns `'gmail'`.

### `ir.mail.server` (Extension)
Extends outgoing mail server to support Gmail SMTP via OAuth2.

**Methods:**
- `_compute_smtp_authentication_info()` — Shows Gmail OAuth authentication method.
- `_onchange_encryption()` — Clears Gmail tokens when encryption changes.
- `_onchange_smtp_authentication_gmail()` — Sets `smtp_user` to current user email when Gmail auth selected.
- `_on_change_smtp_user_gmail()` — Refreshes Gmail token when SMTP user changes.
- `_check_use_google_gmail_service()` — Validates Gmail SMTP configuration.
- `_smtp_login__(connection, smtp_user, smtp_password)` — Authenticates via OAuth2 for SMTP.

### `res.config.settings` (Extension)
Adds Gmail OAuth2 configuration fields to Settings.

## Data

- `views/fetchmail_server_views.xml` — Gmail server type form view
- `views/ir_mail_server_views.xml` — Gmail SMTP server form view
- `views/res_config_settings_views.xml` — Settings form with Google OAuth fields
- `views/templates.xml` — QWeb templates for Gmail OAuth UI
