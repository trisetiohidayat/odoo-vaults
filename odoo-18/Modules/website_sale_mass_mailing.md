---
Module: website_sale_mass_mailing
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_sale_mass_mailing #ecommerce #newsletter
---

## Overview

**Module:** `website_sale_mass_mailing`
**Depends:** `website_sale`, `mass_mailing`
**Location:** `~/odoo/odoo18/odoo/addons/website_sale_mass_mailing/`
**Purpose:** Integrates newsletter subscription with eCommerce checkout — adds a newsletter opt-in checkbox and connects it to a mailing list.

## Models

### `website` (website_sale_mass_mailing/models/website.py)

Inherits: `website`

| Field | Type | Description |
|---|---|---|
| `newsletter_id` | Many2one (`mailing.list`) | Newsletter mailing list for this website |

### `res.config.settings` (website_sale_mass_mailing/models/res_config_settings.py)

Inherits: `res.config.settings`

| Field | Type | Description |
|---|---|---|
| `is_newsletter_enabled` | Boolean | Computed/stored; reflects whether the newsletter snippet view is active |
| `newsletter_id` | Many2one (`mailing.list`) | Related to website's newsletter list; editable |

| Method | Decorator | Description |
|---|---|---|
| `_compute_is_newsletter_enabled()` | `@api.depends('website_id')` | Reads `website_sale_mass_mailing.newsletter` view active status |
| `set_values()` | override | Toggles the newsletter view active state based on checkbox |

## Security / Data

No `ir.model.access.csv`. No data XML files — the module relies on views for the newsletter snippet.

## Critical Notes

- v17→v18: No breaking changes.
- The newsletter subscription is a website snippet/view (`website_sale_mass_mailing.newsletter`) that can be toggled per website from settings.
- Frontend JS handles the actual mailing list subscription; this module manages the configuration.