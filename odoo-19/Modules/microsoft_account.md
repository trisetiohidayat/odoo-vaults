# Microsoft Account (`microsoft_account`)

**Category:** Hidden/Tools
**Depends:** `base_setup`
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Adds Microsoft OAuth2 account management for Odoo users. Provides shared infrastructure (token management, OAuth endpoints) used by `microsoft_calendar` and `microsoft_outlook` modules.

## Models

### `res.users` (Extension)
Extends `res.users` with Microsoft calendar token fields.

| Field | Type | Description |
|-------|------|-------------|
| `microsoft_calendar_rtoken` | Char | Microsoft OAuth refresh token |
| `microsoft_calendar_token` | Char | Microsoft OAuth access token |
| `microsoft_calendar_token_validity` | Datetime | Token expiration timestamp |

**Methods:**
- `_set_microsoft_auth_tokens(access_token, refresh_token, ttl)` — Stores OAuth tokens on the user record with computed validity.

### `microsoft.service` (Abstract)
Abstract model providing shared Microsoft OAuth2 functionality.

**Key Methods:**
- `_get_microsoft_client_id(service)` — Returns OAuth client ID from `ir.config_parameter`.
- `_refresh_microsoft_token(service, rtoken)` — Exchanges refresh token for new access token via Microsoft OAuth2 token endpoint.
- `_get_authorize_uri(from_url, service, scope, redirect_uri)` — Builds Microsoft OAuth2 authorization URI with encoded state (db name, service, from_url, database uuid).
- `_get_microsoft_tokens(authorize_code, service, redirect_uri)` — Exchanges authorization code for access/refresh tokens.
- `_do_request(uri, params, headers, method, preuri, timeout)` — Executes HTTP requests to Microsoft Graph API. Validates host is Microsoft token or Graph endpoint.

**Constants:**
- `DEFAULT_MICROSOFT_AUTH_ENDPOINT` — `https://login.microsoftonline.com/common/oauth2/v2.0/authorize`
- `DEFAULT_MICROSOFT_TOKEN_ENDPOINT` — `https://login.microsoftonline.com/common/oauth2/v2.0/token`
- `DEFAULT_MICROSOFT_GRAPH_ENDPOINT` — `https://graph.microsoft.com`
- `TIMEOUT` = 20 seconds

**Hooks:**
- `_get_calendar_scope()` — Returns `'offline_access openid Calendars.ReadWrite'`
- `_get_microsoft_client_secret(ICP_sudo, service)` — Hook for modules to share client secrets; override point.

## Data

- `data/microsoft_account_data.xml` — External provider configuration for Microsoft calendar.
