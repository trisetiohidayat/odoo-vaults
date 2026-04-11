---
type: module
module: google_address_autocomplete
tags: [odoo, odoo19, address, google, autocomplete]
created: 2026-04-06
---

# Google Address Autocomplete

## Overview
| Property | Value |
|----------|-------|
| **Name** | Google Address Autocomplete |
| **Technical** | `google_address_autocomplete` |
| **Category** | Hidden/Tools |
| **Depends** | `web` |
| **License** | LGPL-3 |

## Description
Provides address autocomplete functionality using the Google Places API. As users type in address fields on partner or delivery forms, suggestions from Google Maps are shown and can be selected to auto-fill the complete address.

## Key Models

### `res.config.settings` (extended)
| Field | Purpose |
|-------|---------|
| `google_places_api_key` | Google Places API key for autocomplete requests |

## Features
- Real-time address suggestions as user types
- Auto-fills street, city, state, zip, country from Google Places data
- Integrates with `res.partner` address fields

## Technical Notes
- Requires Google Maps/Places API key.
- Used on partner address forms in both frontend and backend.
