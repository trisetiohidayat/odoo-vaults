# Microsoft Outlook (`microsoft_outlook`)

**Category:** Hidden
**Depends:** `mail`
**Auto-install:** True
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Adds Microsoft Outlook OAuth2 support for incoming (IMAP) and outgoing (SMTP) mail servers in Odoo. Allows users to connect personal Outlook accounts via OAuth2 without exposing passwords.

## Models

### `microsoft.outlook.mixin` (Abstract)
Provides OAuth2 token management for Outlook integration.

**Key Methods:**
- `_compute_outlook_uri()` — Computes the OAuth authorization URI.
- `open_microsoft_outlook_uri()` — Action to redirect user to Microsoft login.
- `_fetch_outlook_refresh_token(authorization_code)` — Exchanges auth code for refresh token.
- `_fetch_outlook_access_token(refresh_token)` — Gets access token from refresh token.
- `_fetch_outlook_token(grant_type, **values)` — Unified token fetch method.
- `_fetch_outlook_access_token_iap(refresh_token)` — Fetches token via Odoo IAP (In-App Purchase) proxy.
- `_generate_outlook_oauth2_string(login)` — Generates OAuth2 SASL authentication string for IMAP/SMTP.
- `_get_microsoft_endpoint()` — Returns Microsoft Graph or Outlook API endpoint.

### `fetchmail.server` (Extension)
Extends incoming mail server to support Outlook IMAP via OAuth2.

**Fields:**
- `server_type` — Adds `'outlook'` option with display name "Outlook OAuth Authentication"
- `microsoft_outlook_refresh_token` — Stored in mixin

**Methods:**
- `_compute_server_type_info()` — Displays Outlook OAuth description.
- `_check_use_microsoft_outlook_service()` — Constrains: SSL is required for Outlook servers.
- `onchange_server_type()` — Auto-fills `server=imap.outlook.com`, `port=993`, `is_ssl=True` when Outlook type selected.
- `_imap_login__(connection)` — Authenticates via OAuth2 using stored refresh token.
- `_get_connection_type()` — Returns `'outlook'`.

### `ir.mail.server` (Extension)
Extends outgoing mail server to support Outlook SMTP via OAuth2.

**Methods:**
- `_compute_smtp_authentication_info()` — Shows Outlook OAuth authentication method.
- `_onchange_encryption()` — Clears Outlook tokens when encryption changes.
- `_onchange_smtp_authentication_outlook()` — Sets `smtp_user` to current user email when Outlook auth selected.
- `_on_change_smtp_user_outlook()` — Refreshes Outlook token when SMTP user changes.
- `_smtp_login__(connection, smtp_user, smtp_password)` — Authenticates via OAuth2 for SMTP.
- `_check_use_microsoft_outlook_service()` — Ensures Outlook SMTP is only used with TLS.
- `_get_personal_mail_servers_limit()` — Returns per-user limit for personal SMTP servers.

### `res.config.settings` (Extension)
Adds Outlook OAuth2 configuration fields to Settings.

## Data

- `views/fetchmail_server_views.xml` — Outlook server type form view
- `views/ir_mail_server_views.xml` — Outlook SMTP server form view
- `views/res_config_settings_views.xml` — Settings form with Microsoft OAuth fields
- `views/templates.xml` — QWeb templates for Outlook OAuth UI
