---
Module: web_unsplash
Version: 18.0
Type: addon
Tags: #web, #unsplash, #image, #media, #library
---

# web_unsplash — Unsplash Image Library

## Module Overview

**Category:** Hidden
**Depends:** `base_setup`, `web_editor`, `html_editor`
**License:** LGPL-3
**Installable:** True
**Auto-install:** True

Integrates the Unsplash API into Odoo's media dialog for free high-resolution image search. Adds an Unsplash search tab to the image library modal in both `web_editor` and `html_editor`, allowing users to search and insert royalty-free images directly. Downloads are tracked via Unsplash's download attribution API.

## Data Files

- `data/ir_config_parameter.xml` — Default Unsplash API configuration
- `views/res_config_settings_views.xml` — Settings form view for API key input

## Static Assets (web.assets_frontend / web.assets_backend)

| Bundle | Path | Purpose |
|--------|------|---------|
| Frontend | `web_unsplash/static/src/unsplash_service.js` | Core Unsplash API service (search, download tracking, rate limiting) |
| Frontend | `web_unsplash/static/src/media_dialog/unsplash_beacon.js` | Integrates Unsplash tab into media dialog |
| Frontend | `web_unsplash/static/src/unsplash_credentials/unsplash_access_key/` | API key configuration UI |
| Frontend | `web_unsplash/static/src/unsplash_error/unsplash_errors.js` | Error display component |
| Legacy | `web_unsplash/static/src/media_dialog_legacy/**/*` | Legacy media dialog integration for `web_editor` only mode |

## Static Assets (web.assets_tests)

- `web_unsplash/static/tests/**/*` — QUnit tests

## Models

### `ir.attachment` (`web_unsplash.models.ir_attachment`)

**Inheritance:** `ir.attachment`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `url` | Char | Unsplash images are referenced by their Unsplash CDN URL |

**Methods:**

**`_get_serving_url(res_id)`**
Override: if the attachment URL matches the Unsplash domain pattern, returns the Unsplash URL directly (no local serving).

---

### `ir.qweb.field.image` (`web_unsplash.models.ir_qweb_fields`)

**Inheritance:** `ir.qweb.field.image`

**Methods:**

**`local_url(attachment)`**
If the attachment URL matches the Unsplash domain pattern, returns the Unsplash URL directly.

---

### `res.users` (`web_unsplash.models.res_users`)

**Inheritance:** `res.users`

**Methods:**

**`_has_unsplash_key()`** `@api.model`
Returns `True` if the current user has access to Unsplash (i.e., a valid API key is configured via `ir.config_parameter` `unsplash.unsplash_api_key`).

---

### `res.config.settings` (`web_unsplash.models.res_config_settings`)

**Inheritance:** `res.config.settings`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `unsplash_api_key` | Char | Unsplash Access Key (stored as `ir.config_parameter`) |
| `unsplash_app_id` | Char | Unsplash Application ID (stored as `ir.config_parameter`) |

**Methods:**

**`set_unsplash_api_key()`**
Saves the Unsplash API key to `ir.config_parameter` `unsplash.unsplash_api_key`.

---

## Controllers

### `Web_unsplash` (`web_unsplash.controllers.main`)

**Routes:**

| Route | Auth | Methods | Description |
|-------|------|---------|-------------|
| `/web_unsplash/update_attachment` | user | POST | Creates or updates an `ir.attachment` from an Unsplash image URL + attribution data |
| `/web_unsplash/fetch_unsplash` | user | POST | Proxies Unsplash API requests from the frontend to avoid CORS and hide API keys |

**`update_attachment(url, attachment_id, search_term)`**
Fetches the Unsplash image, processes it via `tools.image_process()`, creates or updates an `ir.attachment` with `public=True`, and returns the attachment metadata.

**`fetch_unsplash(path, params)`**
Proxies HTTP requests to `https://api.unsplash.com/{path}` using the configured API key. Adds `Authorization: Client-ID {api_key}` header. Returns JSON response to frontend.

---

## What It Extends

- `ir.attachment` — Unsplash URL serving override
- `ir.qweb.field.image` — Unsplash image local URL resolution
- `res.users` — Unsplash API key access check
- `res.config.settings` — API key configuration fields
- `web_unsplash_unsplash_beacon` (html_editor asset) — Unsplash tab in media dialog
- `web_unsplash_unsplash_beacon_legacy` (web_editor asset) — Legacy Unsplash tab

---

## Key Behavior

- Unsplash API key is configured via Settings (requires `base_setup`). The key is stored as `ir.config_parameter` `unsplash.unsplash_api_key` and sent to the Unsplash API server-side (never exposed to the browser).
- The frontend JS (`unsplash_service.js`) calls `/web_unsplash/fetch_unsplash` to proxy API requests, avoiding CORS restrictions and keeping the API key secret.
- Downloads are tracked via Unsplash's download attribution API (`GET /photos/{id}/download`) — called when a user inserts an Unsplash image.
- Unsplash images are NOT stored in Odoo's database — they are referenced by URL and fetched from the Unsplash CDN. An `ir.attachment` record is created for the image reference and attribution metadata.
- The `update_attachment` controller creates an `ir.attachment` record with the image data stored in `datas` (base64), enabling Odoo to serve it locally as a cache while preserving attribution.
- Rate limiting and error handling (e.g., invalid API key, network errors) are managed by `unsplash_service.js`.
- The media dialog integration adds an "Unsplash" tab alongside the existing "Media Library" and "Upload" tabs.
- v17 to v18: No significant architectural changes.

---

## See Also

- [[Modules/web_editor]] — WYSIWYG editor base
- [[Modules/html_editor]] — OWL-based HTML editor
- [[Modules/product_images]] — Google Custom Search image fetching
- [[Modules/base_setup]] — System configuration settings
