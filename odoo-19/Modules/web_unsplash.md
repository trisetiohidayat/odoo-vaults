# web_unsplash

Odoo 19 Core Module

## Overview

`web_unsplash` integrates the **Unsplash API** into Odoo's image picker, allowing users to search and insert free, high-resolution Unsplash images directly from the HTML editor and other media dialogs.

## Module Details

- **Category**: Hidden
- **Depends**: `base_setup`, `html_editor`
- **Version**: 1.1
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Auto-install**: Yes

## Key Components

### Configuration

#### `res.config.settings` (Inherited)

| Field | Type | Description |
|---|---|---|
| `unsplash_access_key` | Char | Unsplash API Access Key (config parameter: `unsplash.access_key`) |
| `unsplash_app_id` | Char | Unsplash Application ID (config parameter: `unsplash.app_id`) |

Set via **Settings > General Settings > Integrations > Unsplash**.

### Frontend Services

- `unsplash_service.js` — Service wrapping the Unsplash API for frontend use.
- `media_dialog/**` — Media dialog integration for the image picker.
- `unsplash_credentials/**` — Credentials management.
- `unsplash_error/**` — Error handling for API failures.
- `unsplash_beacon.js` — Analytics beacon for Unsplash image usage.

## Usage

1. Obtain an Unsplash API Access Key from unsplash.com/developers.
2. Enter the Access Key in **Settings > General Settings > Integrations > Unsplash**.
3. In any HTML editor, open the image picker — the Unsplash search tab is now available alongside local/uploaded images.

## Technical Notes

- Images are served directly from Unsplash CDN (not downloaded to Odoo), keeping storage minimal.
- Proper attribution is managed by the Unsplash API license.
- The module is `Hidden` category — does not appear in the Apps list.
