---
Module: website_sale_autocomplete
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sale_autocomplete #ecommerce
---

## Overview

**Module:** `website_sale_autocomplete`
**Depends:** `website_sale`, `website`
**Location:** `~/odoo/odoo18/odoo/addons/website_sale_autocomplete/`
**Purpose:** Adds Google Places API key management for address autocomplete on eCommerce checkout pages.

## Models

### `res.config.settings` (website_sale_autocomplete/res_config_settings.py)

Inherits: `res.config.settings`

| Field | Type | Description |
|---|---|---|
| `google_places_api_key` | Char | Related to `website_id.google_places_api_key`; allows setting the API key from settings UI |

No methods beyond inherited CRUD.

### `website` (website_sale_autocomplete/models/website.py)

Inherits: `website` (from `website` module)

| Field | Type | Description |
|---|---|---|
| `google_places_api_key` | Char | Google Places API key for address autocomplete; protected by `base.group_system` |

| Method | Decorator | Description |
|---|---|---|
| `has_google_places_api_key()` | `@api.returns` | Returns bool; checks if key is set (sudo access) |

## Security / Data

No `ir.model.access.csv` — relies on `base.group_system` for the API key field (field-level groups).

Data: `neutralize.sql` — neutralize demo data.

## Critical Notes

- v17→v18: No breaking changes noted.
- The API key is stored on `website` record and gated to System Admin group.
- Frontend JS uses this key to power Google Places autocomplete in checkout address forms.