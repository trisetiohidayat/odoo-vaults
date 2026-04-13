# Stock Maintenance

## Overview
- **Name:** Stock - Maintenance
- **Category:** Supply Chain/Inventory
- **Depends:** `stock`, `maintenance`
- **Auto-install:** Yes
- **License:** LGPL-3

## Description
Links equipment serial numbers to stock lots. When an equipment's serial number matches a stock lot, this module enables opening the lot record directly from the equipment form, providing full traceability from maintenance to inventory.

## Models

### `maintenance.equipment` (extends `maintenance.equipment`)
| Field | Type | Description |
|-------|------|-------------|
| `location_id` | Many2one (`stock.location`) | Internal stock location of this equipment |
| `match_serial` | Boolean | Computed — True if a stock lot exists with this equipment's serial number |

Computed via `_compute_match_serial()`:
- Searches `stock.lot` for records matching the equipment's `serial_no`.
- Requires read access to lots and `group_production_lot` group.

Method:
- `action_open_matched_serial()`: Opens the matching stock lot record. If multiple lots match (shouldn't happen), shows a list; otherwise opens the single lot form.

## Data
- `maintenance_views.xml`: Adds location and serial lot link to equipment form.
- `stock_location.xml`: Location field on equipment view.

## Related
- [Modules/Stock](odoo-18/Modules/stock.md) - Stock lot management
- [Modules/maintenance](odoo-18/Modules/maintenance.md) - Equipment and maintenance requests
