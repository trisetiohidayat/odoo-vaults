---
Module: website_payment_authorize
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_payment_authorize #payment #authorize
---

## Overview

**Module:** `website_payment_authorize`
**Depends:** `website_payment`, `payment_authorize`
**Location:** `~/odoo/odoo18/odoo/addons/website_payment_authorize/`
**Purpose:** Adds Authorize.net capture method configuration (auto vs. manual) accessible from the website payment settings page.

## Models

### `res.config.settings` (website_payment_authorize/models/res_config_settings.py)

Inherits: `res.config.settings`

| Field | Type | Description |
|---|---|---|
| `authorize_capture_method` | Selection | `'auto'` ("Automatically Capture Payment") or `'manual'` ("Manually Charge Later") |

| Method | Decorator | Description |
|---|---|---|
| `get_values()` | override | Reads `capture_manually` from `payment.payment_provider_authorize` record; returns `'manual'` if True else `'auto'` |
| `set_values()` | override | Writes `capture_manually` to the Authorize provider based on selection |

## Security / Data

No `ir.model.access.csv`. No data XML files.

## Critical Notes

- v17→v18: No breaking changes.
- This module only provides a UI convenience — the actual capture behavior is handled by `payment_authorize`.
- The provider is referenced via `ir.model.data` XML ID: `payment.payment_provider_authorize`.