# Google Account

## Overview
- **Module:** Google Users
- **Technical Name:** `google_account`
- **Location:** `/Users/tri-mac/odoo/odoo19/odoo/addons/google_account/`
- **Category:** Hidden/Tools
- **Depends:** `base_setup`
- **License:** LGPL-3

## Description

Provides the foundational Google OAuth2 integration used by all Google-related Odoo modules (Calendar, Drive, Gmail, etc.). Defines the abstract `google.service` model with methods for OAuth2 authentication, token management, and API request handling.

This module does not provide end-user functionality on its own. It is a dependency for other Google integration modules.

## Key Features

- **OAuth2 Authentication:** Full OAuth2 authorization code flow with Google
- **Token Management:** Exchange authorization codes for access/refresh tokens
- **Token Refresh:** Automatic refresh of expired access tokens
- **HTTP Request Abstraction:** Centralized `POST`/`GET`/`PATCH`/`PUT`/`DELETE` methods for Google APIs
- **Security:** Client secrets are never logged or exposed in error messages
- **Config Parameters:** Stores `google_<service>_client_id` and `google_<service>_client_secret` in `ir.config_parameter`

## Configuration

Stored in **Settings > General Settings > Integrations > Google**:
- `google_<service>_client_id` — OAuth2 Client ID
- `google_<service>_client_secret` — OAuth2 Client Secret

## Models

### `google.service` (Abstract Model)

Abstract base class providing Google API integration. Used as a mixin by `google_calendar`, `google_drive`, etc.

**Constants:**
| Constant | Value |
|----------|-------|
| `TIMEOUT` | `20` (seconds) |
| `GOOGLE_AUTH_ENDPOINT` | `https://accounts.google.com/o/oauth2/auth` |
| `GOOGLE_TOKEN_ENDPOINT` | `https://accounts.google.com/o/oauth2/token` |
| `GOOGLE_API_BASE_URL` | `https://www.googleapis.com` |

**Key Methods:**
- `_get_client_id(service)` — Retrieve `google_<service>_client_id` from config parameters
- `_get_authorize_uri(service, scope, redirect_uri, state, approval_prompt, access_type)` — Build the Google OAuth2 authorization URL with required parameters
- `_get_google_tokens(authorize_code, service, redirect_uri)` — Exchange authorization code for access + refresh tokens via POST to token endpoint
- `_refresh_google_token(service, refresh_token)` — Use refresh token to obtain a new access token
- `_do_request(uri, params, headers, method, preuri, timeout)` — Execute HTTP request to Google API. Validates host, strips secrets from logs, handles JSON responses and HTTP errors

**Hook for Extensions:**
- `_get_client_secret(ICP_sudo, service)` — Returns client secret from config. Can be overridden by other modules to provide custom keys.

## Security Notes

- Refresh tokens are stored in `ir.config_parameter` (system-wide, not per-user)
- Access tokens are short-lived; refresh is handled automatically
- Client secret is masked in logs (`"****"`)

## Related

- [Modules/google_calendar](modules/google_calendar.md) — Google Calendar synchronization (depends on this)
- `google_gmail` — Gmail integration (depends on this)
- `google_drive` — Google Drive integration (depends on this)

---
*Documented: 2026-04-06*
