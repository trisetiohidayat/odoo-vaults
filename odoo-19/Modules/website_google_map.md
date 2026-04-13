# Website Google Map

## Overview

- **Module**: `website_google_map`
- **Category**: Website/Website
- **Summary**: Show your company address on Google Maps
- **Source**: `odoo/addons/website_google_map/`
- **Depends**: `base_geolocalize`, `website_partner`

## Description

Show your company address or partner address on Google Maps. Requires an API key to be configured in the Website settings.

## Key Features

- Displays company address on a Google Map embed
- Integrates with partner contact pages
- Requires Google Maps API key configuration

## Architecture

This module is controller/view-only - it does not define any models. It extends partner address display by adding a Google Maps embed in website partner templates.

### Controllers

- Extends `website_partner` controller to embed Google Maps

### Views

- `google_map_templates.xml` - QWeb templates for map rendering

## Relationships

- Depends on `base_geolocalize` (provides geolocation data)
- Depends on `website_partner` (provides partner contact pages)

## Related

- [Modules/base_geolocalize](odoo-17/Modules/base_geolocalize.md) - Base geolocalization features
- [Modules/website_partner](odoo-18/Modules/website_partner.md) - Partner contact pages on website
- [Modules/website](odoo-18/Modules/website.md) - Website builder

## Notes

- An active Google Maps API key must be configured in Website settings for maps to display
- Module has no models - purely frontend integration
