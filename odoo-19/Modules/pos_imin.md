# POS iMin

## Overview
- **Name:** POS iMin
- **Category:** Sales/Point of Sale
- **Depends:** `point_of_sale`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Use iMin ePOS Printers without the IoT Box in the Point of Sale. Provides direct printer integration via iMin ePOS SDK (JavaScript) loaded in POS.

## Key Features
- Direct thermal printer integration (no IoT box required)
- iMin ePOS printer service in POS
- Receipt and order ticket printing

## Data Files
- `views/pos_config_views.xml` — POS configuration views
- `views/res_config_settings_views.xml` — Settings

## Assets
- `pos_imin/static/lib/imin-printer/imin-printer.js` — iMin ePOS SDK
- POS frontend assets for iMin printer service

## Related
- [Modules/point_of_sale](modules/point_of_sale.md) — Base POS module
