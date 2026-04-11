---
Module: website_google_map
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_google_map
---

## Overview

No Python models. This module provides the Google Maps JS SDK integration for Odoo website maps. The actual map rendering and partner location display are handled in QWeb templates and JavaScript widgets.

**Note:** As of Odoo 18, no `models/` directory exists.

**Key Dependencies:** `website_partner`, `base_geolocalize`

---

## Critical Notes

- Map display for partner locations on `/customers` and `/partners` pages uses the Google Maps JavaScript API
- Geocoding (address to lat/lon) is handled by `base_geolocalize` module's `res.partner._geo_localize()` method
- `website_crm_partner_assign` stores geo coordinates on partners for distance-based matching
- The JS widget reads partner lat/lon and renders markers on the map
- No ORM models in this module — purely frontend/JS integration
- v17→v18: No structural changes to the Python layer
